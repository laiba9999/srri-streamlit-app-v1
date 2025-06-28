import pandas as pd
import re

def process_monitoring_file(file):
    # === STEP 1: Load Excel data correctly ===
    raw_df = pd.read_excel(file, header=None)

    # === STEP 2: Construct meaningful column headers ===
    week_row = raw_df.iloc[0]
    column_names = raw_df.iloc[1]
    multi_headers = [
        f"{label} ({week})" if not pd.isna(week) else label
        for week, label in zip(week_row, column_names)
    ]

    # === STEP 3: Load actual data ===
    df = raw_df.iloc[2:].copy()
    df.columns = multi_headers

    # === STEP 4: Re-label duplicate SRRI columns ===
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
    df.columns = adjusted_columns

    # === STEP 5: Identify SRRI columns ===
    srri_columns = [col for col in df.columns if "SRRI Result (Week" in col]

    # === STEP 6: Check for SRRI stability ===
    df["SRRI Stable (All Weeks)"] = df.apply(
        lambda row: row[srri_columns].dropna().astype(str).nunique() == 1, axis=1
    )

    # === STEP 7: Extract SRRI change info ===
    def extract_srri_change_info(row):
        srri_series = row[srri_columns].dropna()
        srri_values = srri_series.astype(str).tolist()
        week_names = srri_series.index.tolist()

        previous_srri = latest_srri = change_week = change_date = None
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
        "Week of SRRI Change": (
            re.search(r"Week\s*\d+", change_week).group(0)
            if isinstance(change_week, str) and re.search(r"Week\s*\d+", change_week)
            else None
        ),
        "Date of SRRI Change": change_date
    })


    df = pd.concat([df, df.apply(extract_srri_change_info, axis=1)], axis=1)

    # === STEP 8: Generate Identifier ===
    def generate_identifier(share_class, currency):
        if pd.isna(share_class): return ""
        name = share_class.lower()
        name = re.sub(r'[®¬Æ]', '', name).replace('class ', '').replace('accu', 'acc')
        hedged_suffix = ''
        match = re.search(r'([a-z]{3})\s*\(hedged\)', name)
        if match: hedged_suffix = match.group(1) + 'hedged'
        name = re.sub(r'[^a-z]', '', name)
        name = name.replace(currency.lower(), '') + currency.lower()
        if hedged_suffix: name += hedged_suffix
        return name

    df["Identifier"] = df.apply(
        lambda row: generate_identifier(row.get("Share Class", ""), row.get("Currency", "")),
        axis=1
    )

    # === STEP 9: Select and rename output columns ===
    columns_to_show = {
        "Fund": "Fund",
        "Sub-Fund": "Sub-Fund",
        "Share Class": "Share Class",
        "Identifier": "Identifier",
        "Currency": "Currency",
        "last validated document date": "Last validated document",
        "SRRI Stable (All Weeks)": "Has SRRI Value Changed",
        "Previous SRRI": "Previous SRRI",
        "Latest SRRI": "Latest SRRI",
        "Week of SRRI Change": "Week_of_Change",
    }

    summary_df = df[list(columns_to_show.keys())].rename(columns=columns_to_show)

    # Ensure boolean column is correctly evaluated
    summary_df["Has SRRI Value Changed"] = ~df["SRRI Stable (All Weeks)"]

    # Filter for rows where SRRI has changed
    summary_df = summary_df[summary_df["Has SRRI Value Changed"] == True].copy()

    # === STEP 10: Convert column types ===

    # Step 1: Try parsing the column to datetime - passing a cast on an object to convert it to datetime
    # Step 1: Parse the date column robustly
    summary_df["Last validated document"] = pd.to_datetime(
        summary_df["Last validated document"], dayfirst=True, errors="coerce"
    )

    # Step 2: Try fallback parsing for unparsed strings
    mask_failed = summary_df["Last validated document"].isna()
    if mask_failed.any():
        fallback = pd.to_datetime(summary_df.loc[mask_failed, "Last validated document"], errors="coerce", dayfirst=True)
        summary_df.loc[mask_failed, "Last validated document"] = fallback

    # Step 3: Convert SRRI columns to numeric
    summary_df["Previous SRRI"] = pd.to_numeric(summary_df["Previous SRRI"], errors="coerce")
    summary_df["Latest SRRI"] = pd.to_numeric(summary_df["Latest SRRI"], errors="coerce")

    # Step 4: Ensure all remaining object columns are strings
    for col in summary_df.columns:
        if summary_df[col].dtype == "object":
            summary_df[col] = summary_df[col].astype(str)

    # Sort and deduplicate
    summary_df = summary_df.sort_values("Last validated document", ascending=False)
    summary_df = summary_df.drop_duplicates(subset="Identifier", keep="first")

    # ✅ Format date to YYYY-MM-DD to be in line with ISO format
    summary_df["Last validated document"] = summary_df["Last validated document"].dt.strftime("%Y-%m-%d")


    # === STEP 11: De-duplicate Identifiers only if associated data differs ===
    # Group by Identifier and count unique rows (excluding Identifier itself)
    duplicated_groups = summary_df.groupby("Identifier").filter(lambda x: len(x) > 1)

    # From those, keep only the most recent row (by Last validated document)
    if not duplicated_groups.empty:
        before = len(summary_df)
        summary_df = summary_df.sort_values("Last validated document", ascending=False)
        summary_df = summary_df.drop_duplicates(subset="Identifier", keep="first")
        after = len(summary_df)
        print(f"ℹ️ Removed {before - after} duplicate Identifier rows with differing associated data.")
    else:
        print("✅ No duplicate Identifiers found.")

    # === STEP 13: Format column names to UPPERCASE_WITH_UNDERSCORES ===
    summary_df.columns = (
        summary_df.columns
        .str.upper()                    # Convert to uppercase
        .str.replace(" ", "_")         # Replace spaces with underscores
        .str.replace("-", "_")         # Replace hyphens with underscores (like SUB-FUND → SUB_FUND)
    )



    # OPTIONAL: If you want to see remaining Identifier counts
    # print(summary_df["Identifier"].value_counts())

    # === Debug: Print final data types ===
    print(summary_df.dtypes)
    print(summary_df.head())
    summary_df.to_csv("srri_summary_output_3.csv", index=False)

    return summary_df


process_monitoring_file("data/SRRI Monitoring First Trust.xlsx")  # Example usage