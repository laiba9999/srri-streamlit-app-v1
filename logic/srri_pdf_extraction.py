import re
import requests
import pdfplumber
import fitz  # PyMuPDF
from io import BytesIO
import pandas as pd

# === Step 1: Load CSV with KIID PDF URLs ===
permalink_df = pd.read_csv("permalink_with_factsheet.csv")  # Ensure this file contains a "KIID PDF URL" column

def process_permalink_file(file):  # ← Accept file from Streamlit
    content = file.read().decode('utf-8-sig')
    raw_lines = content.splitlines()
    
# === Step 2: Define the SRRI and Management Fee extraction function ===
def extract_srri_and_fee(url):
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        pdf_bytes = resp.content

        srri_value = None
        management_fee = None

        # === Method 1: Try with pdfplumber ===
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        # -- Extract SRRI value using known layout pattern --
        marker = r"Risk and Reward Profile\s*1\s*2\s*3\s*4\s*5\s*6\s*7"
        parts = re.split(marker, text, flags=re.IGNORECASE | re.DOTALL)
        if len(parts) >= 2:
            after_graph_text = parts[1].strip()
            paragraph_match = re.search(r"(.{0,300}?\b\d(\.\d)?\b.{0,100})", after_graph_text, re.DOTALL)
            if paragraph_match:
                srri_paragraph = paragraph_match.group(1)
                srri_match = re.search(r"\b\d(\.\d)?\b", srri_paragraph)
                if srri_match:
                    srri_value = float(srri_match.group())

        # -- Extract Management Fee from 'Ongoing charges' section --
        fee_match = re.search(r"Ongoing charges[^%]{0,100}?(\d{1,2}(?:\.\d{1,2})?)\s?%", text, re.IGNORECASE)
        if fee_match:
            management_fee = float(fee_match.group(1))

        # === Fallback Method: Try with PyMuPDF ===
        if srri_value is None:
            doc = fitz.open(stream=BytesIO(pdf_bytes), filetype="pdf")
            full_text = ""
            for page in doc:
                full_text += page.get_text()

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

            # Try to re-extract fee if not already found
            if management_fee is None:
                fee_match = re.search(r"Ongoing charges[^%]{0,100}?(\d{1,2}(?:\.\d{1,2})?)\s?%", full_text, re.IGNORECASE)
                if fee_match:
                    management_fee = float(fee_match.group(1))

    except Exception as e:
        print(f"❌ Failed for {url}: {e}")

    # Return both values as a row
    return pd.Series({
        "Risk_Reward_Ranking": srri_value,
        "Management_Fee": management_fee
    })

# === Step 3: Apply function to all URLs ===
results_df = permalink_df["KIID PDF URL"].apply(extract_srri_and_fee)

# === Step 4: Merge and save ===
permalink_df = pd.concat([permalink_df, results_df], axis=1)
permalink_df.to_csv("output-monitoring-tsfm.csv", index=False)


# === Step 5: Preview output ===
permalink_df.head()
