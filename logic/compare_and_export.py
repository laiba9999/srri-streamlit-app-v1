import pandas as pd

def compare_srri_values(monitoring_df, permalink_df):
    # Clean column names
    monitoring_df.columns = monitoring_df.columns.str.strip()
    permalink_df.columns = permalink_df.columns.str.strip()

    # === Step 1: Merge on Identifier ===
    merged_df = pd.merge(
        permalink_df,
        monitoring_df[["Identifier", "Latest SRRI", "Week_of_Change"]],
        on="Identifier",
        how="inner"
    )

    # Normalize merged_df columns
    merged_df.columns = merged_df.columns.str.strip().str.replace(" ", "_")

    print("Merged DF Columns:", merged_df.columns.tolist())  # ✅ Check again

    # === Step 2: Compare SRRI values
    diff_df = merged_df[
        merged_df["Risk_Reward_Ranking"] != merged_df["Latest SRRI"]
    ]

    # === Step 3: Select required columns only ===
    result_df = diff_df[
        [
            "Fund Name",
            "Share Class",
            "ISIN",
            "KIID PDF URL",
            "Fact Sheet UR",
            "Identifier",
            "Risk_Reward_Ranking",
            "Latest SRRI",
            "Week of Change",
            "Management_Fee"
        ]
    ]

    # === Step 4: Save to CSV ===
    output_file = "srri_updates_needed_v2.csv"
    result_df.to_csv(output_file, index=False)
    return result_df

# print(f"✅ CSV saved with only SRRI changes needed: {output_file}")

# ✅ Return the result for use in Streamlit return result_df
