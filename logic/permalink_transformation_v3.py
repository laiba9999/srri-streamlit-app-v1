import pandas as pd
import re
import requests
import pdfplumber
import fitz  # PyMuPDF
from io import BytesIO

def process_and_extract_permalink_file(file, output_path="output-monitoring-tsfm-v2.csv"):
    # === Step 1: Handle both Streamlit uploads and local file paths ===
    if isinstance(file, str):
        # Called from script: file is a path string
        with open(file, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    else:
        # Called from Streamlit: file is a file-like object (UploadedFile)
        content = file.read().decode('utf-8-sig')

    raw_lines = content.splitlines()

    # === Step 2: Filter KIID lines (English + UK + proper KIID URL) ===
    kiid_lines = [
        line.strip()
        for line in raw_lines
        if (
            "UCITS KIID" in line and
            "KIID.pdf" in line and
            "English" in line and
            ("UK Professional Investor" in line or "UK Retail Investor" in line)
        )
    ]

    # === Step 3: Filter Fact Sheet lines ===
    factsheet_lines = [
        line.strip()
        for line in raw_lines
        if (
            "Fact Sheet" in line and
            "FactSheet.pdf" in line and
            "English" in line and
            ("UK Professional Investor" in line or "UK Retail Investor" in line)
        )
    ]

    # === Step 4: Extract data from KIID lines ===
    kiid_data = []
    for line in kiid_lines:
        url_match = re.search(r"https?://\S+?KIID\.pdf", line)
        url = url_match.group() if url_match else None

        isin_match = re.search(r"\bIE[0-9A-Z]{10}\b", line)
        isin = isin_match.group() if isin_match else None

        fields = line.strip('"').split(',')
        if len(fields) >= 4:
            fund_name = fields[1].strip()
            third = fields[2].strip()
            fourth = fields[3].strip()
            share_class = third if fourth.startswith("IE") else f"{third} - {fourth}"

            kiid_data.append({
                "Line": line,
                "Fund Name": fund_name,
                "Share Class": share_class,
                "ISIN": isin,
                "KIID PDF URL": url
            })

    kiid_df = pd.DataFrame(kiid_data)

    # === Step 5: Extract Fact Sheet URLs ===
    factsheet_data = []
    for line in factsheet_lines:
        url_match = re.search(r"https?://\S+?FactSheet\.pdf", line)
        url = url_match.group() if url_match else None

        isin_match = re.search(r"\bIE[0-9A-Z]{10}\b", line)
        isin = isin_match.group() if isin_match else None

        if isin:
            factsheet_data.append({
                "ISIN": isin,
                "Fact Sheet URL": url
            })

    factsheet_df = pd.DataFrame(factsheet_data).drop_duplicates(subset="ISIN")

    # === Step 6: Merge KIID + Fact Sheet ===
    merged_df = kiid_df.merge(factsheet_df, on="ISIN", how="left")

    # === Step 7: Generate clean identifier from Share Class ===
    def clean_alpha_only(name):
        if pd.isna(name):
            return ""
        name = name.lower()
        name = re.sub(r'[®¬Æ]', '', name)
        name = name.replace('class ', '')
        name = name.replace('accu', 'acc')
        hedged_suffix = ''
        match = re.search(r'([a-z]{3})\s*\(hedged\)', name)
        if match:
            hedged_suffix = match.group(1) + 'hedged'
        name = re.sub(r'[^a-z]', '', name)
        if hedged_suffix:
            name += hedged_suffix
        return name

    merged_df["Identifier"] = merged_df["Share Class"].apply(clean_alpha_only)
    merged_df = merged_df.drop_duplicates(subset="Identifier", keep="first")

    # === Step 8: Extract SRRI and Management Fee from KIID PDF ===
    def extract_srri_and_fee(url):
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            pdf_bytes = resp.content
            srri_value = management_fee = None

            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)

            marker = r"Risk and Reward Profile\s*1\s*2\s*3\s*4\s*5\s*6\s*7"
            parts = re.split(marker, text, flags=re.IGNORECASE | re.DOTALL)
            if len(parts) >= 2:
                match = re.search(r"\b\d(\.\d)?\b", parts[1])
                if match:
                    srri_value = float(match.group())

            fee_match = re.search(r"Ongoing charges[^%]{0,100}?(\d{1,2}(?:\.\d{1,2})?)\s?%", text, re.IGNORECASE)
            if fee_match:
                management_fee = float(fee_match.group(1))

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
            srri_value = management_fee = None

        return pd.Series({
            "Risk_Reward_Ranking": srri_value,
            "Management_Fee": management_fee
        })

    # === 🔽 ADDED SECTION: Extract Share Class Inception Date from Fact Sheet PDF ===
    def extract_inception_date(factsheet_url):
        try:
            # ✅ Skip rows where the URL is missing or not a proper link
            if pd.isna(factsheet_url) or not isinstance(factsheet_url, str) or not factsheet_url.startswith("http"):
                return None
            resp = requests.get(factsheet_url, timeout=15)
            resp.raise_for_status()
            doc = fitz.open(stream=BytesIO(resp.content), filetype="pdf")
            full_text = "".join(page.get_text() for page in doc)

            # Try to find a date like "01 January 2020" after 'Share Class Inception'
            # Match date after "Share Class Inception", supporting both "09.05.2017" and "01 January 2020"
            match = re.search(
                r"Share Class Inception\s*[:\-]?\s*([0-9]{1,2}[./ -][0-9]{1,2}[./ -][0-9]{2,4}|[0-9]{1,2} [A-Za-z]{3,9} \d{4})",
                full_text
            )
            if match:
                date_str = match.group(1)
                date_obj = pd.to_datetime(date_str, dayfirst=True, errors="coerce")
                if pd.notnull(date_obj):
                    return date_obj.strftime("%Y-%m-%d")
        except Exception as e:
            print(f"❌ Failed to extract inception date for {factsheet_url}: {e}")
        return None
# === 🔼 END ADDED SECTION ===

    # === Step 9: Apply extraction functions to KIID and Fact Sheet URLs ===
    srri_fee_data = merged_df["KIID PDF URL"].apply(extract_srri_and_fee)
    inception_data = merged_df["Fact Sheet URL"].apply(extract_inception_date)

    # === Step 10: Merge extracted data into final DataFrame ===
    final_df = pd.concat([merged_df, srri_fee_data], axis=1)
    final_df["Share_Class_Inception"] = pd.to_datetime(inception_data, errors="coerce").dt.strftime("%Y-%m-%d")

    # === Step 11: Save to CSV and return DataFrame ===
    final_df.to_csv(output_path, index=False)
    print(f"✅ Output saved to {output_path}")
    return final_df

