import streamlit as st
import pandas as pd
from logic.srri_monitoring_transformation import process_monitoring_file
from logic.permalink_transformation import process_permalink_file
from logic.compare_and_export import compare_srri_values

st.set_page_config(page_title="SRRI Update Checker", layout="wide")
st.title("📊 SRRI Update Checker")

# File Uploads
file_monitoring = st.file_uploader("Upload SRRI Monitoring Excel", type="xlsx")
file_permalink = st.file_uploader("Upload Permalink CSV", type="csv")

# Process files if both are uploaded
if file_monitoring and file_permalink:
    with st.spinner("Processing..."):
        try:
            df_monitoring = process_monitoring_file(file_monitoring)
        except Exception as e:
            st.error(f"❌ Error while processing Monitoring Excel file:\n\n{e}")
            st.stop()

        try:
            df_permalink = process_permalink_file(file_permalink)
        except Exception as e:
            st.error(f"❌ Error while processing Permalink CSV file:\n\n{e}")
            st.stop()

        # Optional previews of input files
        with st.expander("🔍 Preview Monitoring Data"):
            st.dataframe(df_monitoring)

        with st.expander("🔍 Preview Permalink Data"):
            st.dataframe(df_permalink)

        # Perform comparison
        result_df = compare_srri_values(df_monitoring, df_permalink)

        # Display results
        if result_df.empty:
            st.info("✅ No SRRI mismatches found.")
        else:
            st.success(f"⚠️ Found {len(result_df)} mismatches.")
            st.dataframe(result_df)

            csv = result_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Update File",
                data=csv,
                file_name="srri_updates_needed_v2.csv",
                mime="text/csv"
            )
