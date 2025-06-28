import pandas as pd
import re
import requests
import pdfplumber
import fitz  # PyMuPDF: used for reading low-level PDF content when pdfplumber fails
from io import BytesIO

def process_and_extract_permalink_file(file, output_path="output_permalink_tsfm_v1.csv"):
    # === STEP 1: READ INPUT FILE CONTENT ===
    # This handles both local file paths (string) and Streamlit uploads (UploadedFile)
    if isinstance(file, str):
        with open(file, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    else:
        content = file.read().decode('utf-8-sig')  # Decode byte stream into string for Streamlit upload

    raw_lines = content.splitlines()  # Split entire file into a list of lines (raw CSV text)

    # === STEP 2: FILTER RELEVANT LINES ===
    # Extract only lines containing valid English KIID PDF links and investor type
    kiid_lines = [
        line.strip() for line in raw_lines
        if "UCITS KIID" in line and "KIID.pdf" in line and "English" in line and
           ("UK Professional Investor" in line or "UK Retail Investor" in line)
    ]

    # Similarly extract valid English FactSheet lines
    factsheet_lines = [
        line.strip() for line in raw_lines
        if "Fact Sheet" in line and "FactSheet.pdf" in line and "English" in line and
           ("UK Professional Investor" in line or "UK Retail Investor" in line)
    ]

    # === STEP 3: PARSE KIID LINES INTO STRUCTURED DATA ===
    kiid_data = []
    for line in kiid_lines:
        # Extract KIID PDF URL
        url = re.search(r"https?://\S+?KIID\.pdf", line)
        # Extract ISIN code (starting with IE, 12 characters)
        isin = re.search(r"\bIE[0-9A-Z]{10}\b", line)
        # Split CSV line safely
        fields = line.strip('"').split(',')

        # Only proceed if all critical data is present
        if url and isin and len(fields) >= 4:
            fund_name = fields[1].strip()  # Fund name from second column
            third, fourth = fields[2].strip(), fields[3].strip()
            # Create a normalized share class name
            share_class = third if fourth.startswith("IE") else f"{third} - {fourth}"

            kiid_data.append({
                "Line": line,
                "Fund Name": fund_name,
                "Share Class": share_class,
                "ISIN": isin.group(),
                "KIID PDF URL": url.group()
            })

    # Convert list of dicts into a DataFrame
    kiid_df = pd.DataFrame(kiid_data)

    # === STEP 4: PARSE FACTSHEET LINES ===
    factsheet_data = []
    for line in factsheet_lines:
        url = re.search(r"https?://\S+?FactSheet\.pdf", line)
        isin = re.search(r"\bIE[0-9A-Z]{10}\b", line)
        if url and isin:
            factsheet_data.append({
                "ISIN": isin.group(),
                "Fact Sheet URL": url.group()
            })

    factsheet_df = pd.DataFrame(factsheet_data).drop_duplicates(subset="ISIN")  # Remove duplicate ISINs

    # === STEP 5: MERGE KIID AND FACTSHEET DATA ===
    # Combine KIID and FactSheet info by ISIN
    merged_df = kiid_df.merge(factsheet_df, on="ISIN", how="left")

    # === STEP 6: GENERATE CLEAN IDENTIFIER FROM SHARE CLASS ===
    def clean_alpha_only(name):
        if pd.isna(name):
            return ""
        name = name.lower()
        name = re.sub(r'[®¬Æ]', '', name)  # Remove special characters
        name = name.replace('class ', '').replace('accu', 'acc')  # Normalize class name
        hedged_suffix = re.search(r'([a-z]{3})\s*\(hedged\)', name)
        name = re.sub(r'[^a-z]', '', name)  # Remove everything except a-z
        if hedged_suffix:
            name += hedged_suffix.group(1) + 'hedged'
        return name

    merged_df["Identifier"] = merged_df["Share Class"].apply(clean_alpha_only)

    # === STEP 7: EXTRACT DATA FROM KIID & FACTSHEET PDFs ===

    # Extract SRRI and Management Fee from KIID PDFs
    def extract_srri_and_fee(url):
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            pdf_bytes = resp.content
            srri_value = management_fee = None

            # Try pdfplumber first
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)

            # Look for SRRI scale
            marker = r"Risk and Reward Profile\s*1\s*2\s*3\s*4\s*5\s*6\s*7"
            parts = re.split(marker, text, flags=re.IGNORECASE | re.DOTALL)
            if len(parts) >= 2:
                srri_match = re.search(r"\b\d(\.\d)?\b", parts[1])
                if srri_match:
                    srri_value = float(srri_match.group())

            # Look for management fee (ongoing charges %)
            fee_match = re.search(r"Ongoing charges[^%]{0,100}?(\d{1,2}(?:\.\d{1,2})?)\s?%", text, re.IGNORECASE)
            if fee_match:
                management_fee = float(fee_match.group(1))

            # Fallback to PyMuPDF if not found
            if srri_value is None or management_fee is None:
                doc = fitz.open(stream=BytesIO(pdf_bytes), filetype="pdf")
                full_text = "".join(page.get_text() for page in doc)

                if srri_value is None:
                    srri_patterns = [
                        r'The lowest category does not mean that the investment is risk free\D+(\d)',
                        r'Risk and Reward Profile.*?1\s*2\s*3\s*4\s*5\s*6\s*7.*?(\d)',
                        r'category\s+(\d)\s+reflects',
                        r'(?:risk profile|risk and reward).*?([1-7])'
                    ]
                    for pattern in srri_patterns:
                        match = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)
                        if match:
                            srri_value = int(match.group(1))
                            break

                if management_fee is None:
                    fee_match = re.search(r"Ongoing charges[^%]{0,100}?(\d{1,2}(?:\.\d{1,2})?)\s?%", full_text, re.IGNORECASE)
                    if fee_match:
                        management_fee = float(fee_match.group(1))

        except Exception as e:
            print(f"❌ Failed to extract SRRI or Fee for {url}: {e}")

        return pd.Series({"KIID_SRRI": srri_value, "Management_FEE": management_fee})

    # Extract share class inception date from factsheet PDFs
    def extract_inception_date(url):
        try:
            if pd.isna(url) or not isinstance(url, str) or not url.startswith("http"):
                return None
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            doc = fitz.open(stream=BytesIO(resp.content), filetype="pdf")
            full_text = "".join(page.get_text() for page in doc)

            match = re.search(
                r"Share Class Inception\s*[:\-]?\s*([0-9]{1,2}[./ -][0-9]{1,2}[./ -][0-9]{2,4}|[0-9]{1,2} [A-Za-z]{3,9} \d{4})",
                full_text
            )
            if match:
                date_obj = pd.to_datetime(match.group(1), dayfirst=True, errors="coerce")
                if pd.notnull(date_obj):
                    return date_obj
        except Exception as e:
            print(f"❌ Failed to extract inception date for {url}: {e}")
        return None

    # Apply PDF extractors to each row
    srri_fee_data = merged_df["KIID PDF URL"].apply(extract_srri_and_fee)
    inception_data = merged_df["Fact Sheet URL"].apply(extract_inception_date)

    # === STEP 8: BUILD FINAL DATAFRAME ===
    final_df = pd.concat([merged_df, srri_fee_data], axis=1)
    final_df["Share_Class_Inception"] = pd.to_datetime(inception_data, errors="coerce")

    # Convert types
    final_df["KIID_SRRI"] = pd.to_numeric(final_df["KIID_SRRI"], errors="coerce").astype("Int64")
    final_df["Management_FEE"] = pd.to_numeric(final_df["Management_FEE"], errors="coerce").astype("float64")
    final_df["Share_Class_Inception"] = final_df["Share_Class_Inception"].dt.strftime("%Y-%m-%d")

    # Convert other string columns
    string_cols = [
        "Line", "Fund Name", "Share Class", "ISIN",
        "KIID PDF URL", "Fact Sheet URL", "Identifier"
    ]
    final_df[string_cols] = final_df[string_cols].astype(str)

    # === STEP 9: FILTER & CLEAN ===
    # Remove rows with missing Share Class or SRRI
    final_df = final_df[
        final_df["Share Class"].str.strip().ne("") &
        final_df["KIID_SRRI"].notna()
    ]

    # Remove duplicate identifiers, keep first
    final_df = final_df.drop_duplicates(subset="Identifier", keep="first")

    # Format column names to UPPERCASE_WITH_UNDERSCORES
    final_df.columns = (
        final_df.columns
        .str.upper()
        .str.replace(" ", "_")
        .str.replace("-", "_")
    )

    # === STEP 10: EXPORT AND RETURN ===
    final_df.to_csv(output_path, index=False)
    print(f"✅ Output saved to {output_path}")

    print("\n📋 Final DataFrame column types:\n")
    print(final_df.dtypes)
    print(final_df.head())

    return final_df


process_and_extract_permalink_file("data/Permalink File.csv")  # Example usage with a sample file