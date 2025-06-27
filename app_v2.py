import streamlit as st
import pandas as pd
from logic.srri_monitoring_transformation_v2 import process_monitoring_file
from logic.permalink_transformation_v2 import process_and_extract_permalink_file  # <-- Combined function
from logic.compare_and_export_v2 import compare_srri_values

st.set_page_config(page_title="SRRI Update Checker", layout="wide")
st.title("📊 SRRI Update Checker")

# === File Uploads ===
file_monitoring = st.file_uploader("Upload SRRI Monitoring Excel", type="xlsx")
file_permalink = st.file_uploader("Upload Permalink CSV", type="csv")

# === Main Processing ===
if file_monitoring and file_permalink:
    with st.spinner("Processing..."):
        # STEP 1: Process Monitoring Excel
        try:
            df_monitoring = process_monitoring_file(file_monitoring)
        except Exception as e:
            st.error(f"❌ Error while processing Monitoring Excel:\n\n{e}")
            st.stop()

        # STEP 2: Process Permalink CSV + extract SRRI/Fees
        try:
            df_permalink = process_and_extract_permalink_file(file_permalink)
        except Exception as e:
            st.error(f"❌ Error while processing Permalink CSV or extracting SRRI/Fees:\n\n{e}")
            st.stop()

        # === Preview Inputs ===
        with st.expander("🔍 Preview Monitoring Data"):
            st.dataframe(df_monitoring)

        with st.expander("🔍 Preview Permalink Data + Extracted Values"):
            st.dataframe(df_permalink)

        # === Compare SRRI Values ===
        try:
            result_df = compare_srri_values(df_monitoring, df_permalink)

            if result_df.empty:
                st.info("✅ No SRRI mismatches found.")
            else:
                st.success(f"⚠️ Found {len(result_df)} mismatches.")
                st.dataframe(result_df)

                csv_data = result_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Download SRRI Update File",
                    data=csv_data,
                    file_name="srri_updates_needed_v2.csv",
                    mime="text/csv"
                )
        except Exception as e:
            st.error(f"❌ Error comparing SRRI values:\n\n{e}")
