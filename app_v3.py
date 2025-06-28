import streamlit as st  # Import Streamlit for UI
import pandas as pd  # pandas for data manipulation
# Import custom logic modules
from logic.srri_monitoring_transformation_v2 import process_monitoring_file  # Processes the monitoring Excel
from logic.permalink_transformation_v3 import process_and_extract_permalink_file  # Processes permalink CSV and extracts SRRI/Fees
from logic.compare_and_export_v2 import compare_srri_values  # Compares extracted SRRI values

# === Streamlit page setup ===
st.set_page_config(page_title="SRRI Update Checker", layout="wide")  # Set browser tab title and layout
st.title("📊 SRRI Update Checker")  # Display app title

# === File upload widgets ===
file_monitoring = st.file_uploader("Upload SRRI Monitoring Excel", type="xlsx")  # Upload widget for monitoring file
file_permalink = st.file_uploader("Upload Permalink CSV", type="csv")  # Upload widget for permalink file

# === Process only if both files are uploaded ===
if file_monitoring and file_permalink:
    with st.spinner("Processing..."):  # Show spinner while backend is working

        # STEP 1: Process Monitoring Excel
        try:
            df_monitoring = process_monitoring_file(file_monitoring)  # Transform monitoring Excel to DataFrame
        except Exception as e:
            st.error(f"❌ Error while processing Monitoring Excel:\n\n{e}")  # Show error if processing fails
            st.stop()  # Exit the app gracefully

        # STEP 2: Process Permalink CSV + extract SRRI/Fees from PDFs
        try:
            df_permalink = process_and_extract_permalink_file(file_permalink)  # Process and enrich permalink data
        except Exception as e:
            st.error(f"❌ Error while processing Permalink CSV or extracting SRRI/Fees:\n\n{e}")  # Show error
            st.stop()

        # === Show preview of processed inputs ===
        with st.expander("🔍 Preview Monitoring Data"):
            st.dataframe(df_monitoring)  # Show processed monitoring data

        with st.expander("🔍 Preview Permalink Data + Extracted Values"):
            st.dataframe(df_permalink)  # Show enriched permalink data with SRRI and fees

        # === Download processed intermediate files ===
        monitoring_csv = df_monitoring.to_csv(index=False).encode("utf-8")  # Convert monitoring DataFrame to CSV
        st.download_button(
            label="⬇️ Download Processed Monitoring Excel",  # Button label
            data=monitoring_csv,  # File content
            file_name="processed_monitoring_data.csv",  # File name on download
            mime="text/csv"  # MIME type
        )

        permalink_csv = df_permalink.to_csv(index=False).encode("utf-8")  # Convert permalink DataFrame to CSV
        st.download_button(
            label="⬇️ Download Processed Permalink CSV + SRRI/Fees",  # Button label
            data=permalink_csv,  # File content
            file_name="processed_permalink_data.csv",  # File name on download
            mime="text/csv"  # MIME type
        )

        # === Compare SRRI values ===
        try:
            result_df = compare_srri_values(df_monitoring, df_permalink)  # Compare monitoring vs extracted values

            if result_df.empty:
                st.info("✅ No SRRI mismatches found.")  # Inform user if all SRRI values match
            else:
                st.success(f"⚠️ Found {len(result_df)} mismatches.")  # Inform user of mismatches
                st.dataframe(result_df)  # Show mismatches in a table

                # Allow user to download the mismatched results
                csv_data = result_df.to_csv(index=False).encode("utf-8")  # Convert result DataFrame to CSV
                st.download_button(
                    label="📥 Download SRRI Update File",  # Button label
                    data=csv_data,  # File content
                    file_name="srri_updates_needed_v2.csv",  # File name on download
                    mime="text/csv"  # MIME type
                )

        except Exception as e:
            st.error(f"❌ Error comparing SRRI values:\n\n{e}")  # Show error if comparison fails
