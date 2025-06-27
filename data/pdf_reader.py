import fitz  # PyMuPDF
import requests
from io import BytesIO
import os

def read_factsheet_pdf(source):
    try:
        # Check if source is a URL or a local file
        if source.startswith("http"):
            print("🔗 Downloading PDF from URL...")
            response = requests.get(source, timeout=15)
            response.raise_for_status()
            pdf_stream = BytesIO(response.content)
            doc = fitz.open(stream=pdf_stream, filetype="pdf")
        else:
            if not os.path.exists(source):
                print(f"❌ File not found: {source}")
                return
            print("📄 Opening local PDF...")
            doc = fitz.open(source)

        # Extract and print all text
        print("\n=== 📃 PDF Content Start ===\n")
        for page_num, page in enumerate(doc, start=1):
            print(f"\n--- Page {page_num} ---\n")
            print(page.get_text())
        print("\n=== 📃 PDF Content End ===\n")

    except Exception as e:
        print(f"❌ Error reading PDF: {e}")

# === Example usage ===

# Option 1: Remote Fact Sheet URL
read_factsheet_pdf("https://www.ftglobalportfolios.com/srp/documents-id/c37cc806-5e96-4d09-b610-b1173be5afe4/FactSheet.pdf")

# Option 2: Local PDF file
# read_factsheet_pdf("data/sample_factsheet.pdf")
