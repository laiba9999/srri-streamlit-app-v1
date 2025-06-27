import pandas as pd
import re
import io

def process_permalink_file(file):
    # === Step 1: Read the file content ===
    content = file.read().decode('utf-8-sig')
    raw_lines = content.splitlines()

    # === Step 2: Filter KIID lines ===
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

    # === Step 6: Merge Fact Sheets into KIID data ===
    merged_df = kiid_df.merge(factsheet_df, on="ISIN", how="left")

    # === Step 7: Create clean identifier ===
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

    # === Step 8: Drop duplicates on Identifier ===
    final_df = merged_df.drop_duplicates(subset="Identifier", keep="first")

    return final_df
