import pandas as pd

def compare_srri_values(monitoring_df, permalink_df):
    # Clean column names
    monitoring_df.columns = monitoring_df.columns.str.strip()
    permalink_df.columns = permalink_df.columns.str.strip()

    # === Step 1: Check for required columns ===
    required_cols = ["Identifier", "Latest SRRI", "Week_of_Change"]
    for col in required_cols:
        if col not in monitoring_df.columns:
            raise ValueError(f"Missing column in monitoring_df: {col}")

    # === Step 2: Merge on Identifier ===
    merged_df = pd.merge(
        permalink_df,
        monitoring_df[["Identifier", "Latest SRRI", "Week_of_Change"]],
        on="Identifier",
        how="inner"
    )

    # Normalize merged_df columns: make sure you use updated names after this
    merged_df.columns = merged_df.columns.str.strip().str.replace(" ", "_")

    print("Merged DF Columns:", merged_df.columns.tolist())

    # === Step 3: Compare SRRI values ===
    diff_df = merged_df[
        merged_df["Risk_Reward_Ranking"] != merged_df["Latest_SRRI"]
    ]

    # === Step 4: Select required columns only ===
    result_df = diff_df[
        [
            "Fund_Name",
            "Share_Class",
            "ISIN",
            "KIID_PDF_URL",
            "Fact_Sheet_URL",  # Updated this too
            "Identifier",
            "Risk_Reward_Ranking",
            "Latest_SRRI",
            "Week_of_Change",
            "Management_Fee",
            "Share_Class_Inception"
        ]
    ]

    # === Step 5: Save to CSV ===
    output_file = "srri_updates_needed_v2.csv"
    result_df.to_csv(output_file, index=False)

    return result_df
