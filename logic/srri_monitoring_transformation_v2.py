import pandas as pd
import re

def process_monitoring_file(file):
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

    # === STEP 7: Extract change info ===
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
            "Week of SRRI Change": change_week,
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
        "Week of SRRI Change": "Week_of_Change"
    }

    summary_df = df[list(columns_to_show.keys())].rename(columns=columns_to_show)
    summary_df["Has SRRI Value Changed"] = ~df["SRRI Stable (All Weeks)"]
    summary_df = summary_df[summary_df["Has SRRI Value Changed"] == True].copy()

    # === STEP 10: Clean date formatting and drop duplicates ===
    summary_df["Last validated document"] = pd.to_datetime(
        summary_df["Last validated document"], dayfirst=True, errors="coerce"
    )
    summary_df = summary_df.sort_values("Last validated document", ascending=False)
    summary_df = summary_df.drop_duplicates(subset="Identifier", keep="first")
    summary_df["Last validated document"] = summary_df["Last validated document"].dt.strftime("%Y-%m-%d")

    # Optional: Save output for debug/testing
    # summary_df.to_csv("srri_summary_output_2.csv", index=False)

    return summary_df
