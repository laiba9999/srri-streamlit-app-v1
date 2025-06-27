import pandas as pd
# pip install openpyxl
# pip install pandas
import re

def process_monitoring_file(file):
    # include everything from your Excel logic (STEP 1–10)
    # return summary_df with columns: Identifier, Fund, Previous SRRI, Latest SRRI, etc.
    # === STEP 1: Load the raw Excel file ===
    # Note: Row 0 contains week info (e.g. Week 1, Week 2)
    #       Row 1 contains actual column labels (Fund, Sub-Fund, SRRI Report, etc.)
    #file_path = "data/SRRI Monitoring First Trust.xlsx"clea
    #raw_df = pd.read_excel(file_path, header=None)
    raw_df = pd.read_excel(file, header=None)

    # === STEP 2: Construct meaningful column headers from rows 0 and 1 ===
    week_row = raw_df.iloc[0]           # Week info
    column_names = raw_df.iloc[1]       # Actual labels (like "SRRI Report", "SRRI Result")

    multi_headers = []
    for week, label in zip(week_row, column_names):
        if pd.isna(week):               # Columns without week info (e.g. Fund, Currency)
            multi_headers.append(label)
        else:                           # For SRRI fields, combine label with week (e.g. SRRI Result (Week 3))
            multi_headers.append(f"{label} ({week})")

    # === STEP 3: Load the actual data from row 3 down ===
    df = raw_df.iloc[2:].copy()
    df.columns = multi_headers          # Apply combined headers

    # === STEP 4: Re-label SRRI Result columns with corresponding week numbers ===
    adjusted_columns = []
    week_context = None

    for col in df.columns:
        if "SRRI Report" in col:
            week_context = col.split("(")[-1].replace(")", "").strip()
            adjusted_columns.append(col)
        elif col == "SRRI Result" and week_context:
            adjusted_columns.append(f"SRRI Result ({week_context})")
        else:
            adjusted_columns.append(col)

    df.columns = adjusted_columns       # Apply restructured headers

    # === STEP 5: Identify all SRRI Result columns ===
    srri_columns = [col for col in df.columns if "SRRI Result (Week" in col]

    # === STEP 6: Check if SRRI stayed the same across all weeks ===
    def srri_always_stable(row):
        values = row[srri_columns].dropna().astype(str)
        return values.nunique() == 1    # True if all values identical

    df["SRRI Stable (All Weeks)"] = df.apply(srri_always_stable, axis=1)

    # === STEP 7: Extract previous/latest SRRI, week and date of change ===
    def extract_srri_change_info(row):
        srri_series = row[srri_columns].dropna()
        srri_values = srri_series.astype(str).tolist()
        week_names = srri_series.index.tolist()

        previous_srri = None
        latest_srri = None
        change_week = None
        change_date = None

        if srri_values:
            latest_srri = srri_values[-1]
            previous_srri = next((v for v in reversed(srri_values[:-1]) if v != latest_srri), latest_srri)

            for i in range(len(srri_values) - 2, -1, -1):
                if srri_values[i] != latest_srri:
                    change_week = week_names[i + 1]
                    corresponding_report_col = change_week.replace("SRRI Result", "SRRI Report")
                    if corresponding_report_col in row.index:
                        change_date = row[corresponding_report_col]
                    break

        return pd.Series({
            "Previous SRRI": previous_srri,
            "Latest SRRI": latest_srri,
            "Week of SRRI Change": change_week,
            "Date of SRRI Change": change_date
        })

    change_info_df = df.apply(extract_srri_change_info, axis=1)
    df = pd.concat([df, change_info_df], axis=1)

    # === STEP 8: Generate clean identifier from Fund/Sub-Fund/Share Class ===

    """
    SRRI Monitoring First Trust file example:
    Share Class	                                                            Currency
    First Trust FactorFX UCITS ETF Class B GBP (Hedged) ACCU	            GBP
    First Trust US Equity Income UCITS ETF Class B ACCU	                    USD
    First Trust FactorFX UCITS ETF Class A USD ACCU	                        USD
    """
    def generate_identifier(share_class, currency):
        if pd.isna(share_class):
            return ""

        original = share_class.lower()
        name = original

        # Normalize known variants
        name = re.sub(r'[®¬Æ]', '', name)
        name = name.replace('class ', '')
        name = name.replace('accu', 'acc')

        # Extract Hedged logic
        hedged_suffix = ''
        match = re.search(r'([a-z]{3})\s*\(hedged\)', original)
        if match:
            hedged_suffix = match.group(1) + 'hedged'

        # Remove all non-alphabet characters
        name = re.sub(r'[^a-z]', '', name)

        # Remove currency from middle if present
        currency_lower = currency.lower()
        name = name.replace(currency_lower, '')

        # Add currency back to the end
        name += currency_lower

        # Add hedged if found
        if hedged_suffix:
            name += 'hedged'

        return name


    df["Identifier"] = df.apply(
        lambda row: generate_identifier(row.get("Share Class", ""), row.get("Currency", "")), axis=1
    )

    # === STEP 9: Build final summary for delivery or reporting ===
    columns_to_show = {
        "Fund": "Fund",
        "Sub-Fund": "Sub-Fund",
        "Share Class": "Share Class",
        "Identifier": "Identifier",
        "Currency": "Currency",
        "last validated document date": "Last validated document",
        "SRRI Stable (All Weeks)": "Has SRRI Value Changed",  # Inverted logic below
        "Previous SRRI": "Previous SRRI",
        "Latest SRRI": "Latest SRRI",
        "Week of SRRI Change": "Week of Change"
    }

    # Subset and rename
    summary_df = df[list(columns_to_show.keys())].rename(columns=columns_to_show)

    # Flip logic: if SRRI was stable, then "Has SRRI Changed" = False
    summary_df["Has SRRI Value Changed"] = ~df["SRRI Stable (All Weeks)"]

    # Keep only records where SRRI has changed - remove this during testing
    summary_df = summary_df[summary_df["Has SRRI Value Changed"] == True].copy()


    # === STEP 10: Clean and export ===

    # 10.1 Fix invalid date formats in 'Last validated document'
    summary_df["Last validated document"] = pd.to_datetime(
        summary_df["Last validated document"],
        dayfirst=True,       # interpret dates as DD/MM/YYYY (common UK format)
        errors="coerce"      # set invalid formats to NaT (Not a Time)
    )

    # 10.2 Sort by date descending so we keep the most recent validated record for each identifier
    summary_df = summary_df.sort_values("Last validated document", ascending=False)

    # 10.3 Drop duplicates based on the 'Identifier' column
    #      This keeps only the most recent entry per identifier (i.e., latest SRRI validation)
    summary_df = summary_df.drop_duplicates(subset="Identifier", keep="first")

    # 10.4 Format date back to string format YYYY-MM-DD (common format for output)
    summary_df["Last validated document"] = summary_df["Last validated document"].dt.strftime("%Y-%m-%d")

    # 10.5 Export cleaned and deduplicated results
    summary_df.to_csv("srri_summary_output_2.csv", index=False)
    #summary_df.to_excel("srri_summary_output_V2.xlsx", index=False)

    print("✅ Clean SRRI summary created and exported as 'srri_summary_output_2.csv'")

    return summary_df  # Return the final summary DataFrame for further use or testing
()
process_monitoring_file