import pandas as pd

def compare_srri_values(monitoring_df, permalink_df):
    """
    Compare the KIID_SRRI from the permalink data with the LATEST_SRRI from the monitoring data.
    Returns and saves a DataFrame of rows where the SRRI values do not match.
    """

    # === Step 1: Load input files if passed as file paths ===
    # This allows the function to be called with either file paths or already-loaded DataFrames
    if isinstance(monitoring_df, str):
        monitoring_df = pd.read_csv(monitoring_df)
    if isinstance(permalink_df, str):
        permalink_df = pd.read_csv(permalink_df)

    # === Step 2: Standardize column names to a consistent format ===
    # Converts all column names to uppercase and replaces spaces/hyphens with underscores
    # This makes downstream column access safer and more consistent
    monitoring_df.columns = (
        monitoring_df.columns
        .str.strip()
        .str.upper()
        .str.replace(" ", "_")
        .str.replace("-", "_")
    )
    permalink_df.columns = (
        permalink_df.columns
        .str.strip()
        .str.upper()
        .str.replace(" ", "_")
        .str.replace("-", "_")
    )

    # === Step 3: Ensure the monitoring file has the required columns ===
    # These are necessary for SRRI comparison and to track when the change happened
    required_monitoring_cols = {"IDENTIFIER", "LATEST_SRRI", "WEEK_OF_CHANGE"}
    missing_monitoring = required_monitoring_cols - set(monitoring_df.columns)
    if missing_monitoring:
        raise ValueError(f"❌ Missing columns in monitoring_df: {missing_monitoring}")

    # === Step 4: Ensure the permalink file has the required columns ===
    # These columns are expected to contain extracted SRRI values from KIID PDFs
    required_permalink_cols = {"IDENTIFIER", "KIID_SRRI"}
    missing_permalink = required_permalink_cols - set(permalink_df.columns)
    if missing_permalink:
        raise ValueError(f"❌ Missing columns in permalink_df: {missing_permalink}")

    # === Step 5: Merge both datasets using the common 'IDENTIFIER' column ===
    # We use an inner join to retain only records present in both datasets
    merged_df = pd.merge(
        permalink_df,
        monitoring_df[["IDENTIFIER", "LATEST_SRRI", "WEEK_OF_CHANGE"]],
        on="IDENTIFIER",
        how="inner"
    )

    # === Step 6: Identify rows where the SRRI values do not match ===
    # We only care about mismatches between extracted and monitored SRRI values
    diff_df = merged_df[
        merged_df["KIID_SRRI"] != merged_df["LATEST_SRRI"]
    ]

    # === Step 7: Select and reorder output columns to make results useful and readable ===
    # Columns include identifiers, SRRI values, URLs, and metadata like inception date and management fee
    final_columns = [
        "FUND_NAME",                # Name of the fund
        "SHARE_CLASS",             # Share class of the fund
        "ISIN",                    # International Securities Identification Number
        "KIID_PDF_URL",            # URL to the KIID PDF
        "FACT_SHEET_URL",          # URL to the fund's fact sheet
        "IDENTIFIER",              # Cleaned unique string ID used for joins
        "KIID_SRRI",               # SRRI extracted from KIID PDF
        "LATEST_SRRI",            # Latest SRRI from monitoring file
        "WEEK_OF_CHANGE",         # When the SRRI changed in the monitoring system
        "MANAGEMENT_FEE",         # Management fee extracted from KIID
        "SHARE_CLASS_INCEPTION"   # Share class inception date from the Fact Sheet
    ]

    # Filter to only keep columns that actually exist in the merged data
    result_df = diff_df[[col for col in final_columns if col in diff_df.columns]]

    # === Step 8: Save the mismatched rows to a CSV file for manual or automated review ===
    output_file = "srri_updates_needed_v2.csv"
    result_df.to_csv(output_file, index=False)
    print(f"✅ Mismatch report saved to: {output_file} ({len(result_df)} rows)")

    return result_df

# === Optional command-line run for testing or scripting ===
# When the script is run directly, it compares the latest monitoring and permalink outputs
if __name__ == "__main__":
    compare_srri_values("srri_monitoring_output_v1.csv", "output_permalink_tsfm_v1.csv")
