# 📊 SRRI Update Checker – Streamlit App

This is a Streamlit-based tool built to automate the reconciliation of **SRRI (Synthetic Risk and Reward Indicator)** values between internal monitoring files and values extracted from official **KIID (Key Investor Information Document)** and **Fact Sheet PDFs**.

The app also extracts **management fees** and **share class inception dates** to assist in fund data validation workflows.

---

## 🚀 Features

- Upload two input files:
  - 📄 SRRI Monitoring Excel file
  - 🔗 Permalink CSV with KIID and Fact Sheet links
- Automatically extracts from PDFs:
  - SRRI values
  - Management fees (from KIID)
  - Share class inception dates (from Fact Sheets)
- Compares extracted SRRI values against monitoring report
- Highlights mismatches
- Exports results as downloadable CSV

---

## 📁 Project Structure
srri_app_package/
├── app.py # Main Streamlit app
├── requirements.txt # Dependencies
├── .gitignore
├── README.md
└── logic/
├── srri_monitoring_transformation.py
├── permalink_transformation.py
├── compare_and_export.py


---

## 💻 How to Run the App Locally

### 1. Clone the repository
bash
git clone https://github.com/YOUR_USERNAME/srri-streamlit-app.git
cd srri-streamlit-app


### 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate


### 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate


### 3. Install dependencies
pip install -r requirements.txt\


### 4. Run the Streamlit app
streamlit run app.py

This will launch the app in your browser at http://localhost:8501.


📤 Input File Formats
1. SRRI Monitoring Excel File
Should contain fund data including columns for Identifier, Latest SRRI, and Week of Change.

The app processes the Excel headers and data layout automatically.

2. Permalink CSV File
Should contain URLs for:
KIID PDF
Fact Sheet PDF
ISIN
Must include share class names to generate a matchable identifier.

📤 Output
After comparing SRRI values, the app produces a table of mismatches (if any).
You can download the results as a CSV file for updates or reporting.

🌐 Deploying to Streamlit Cloud
You can deploy this app for free using Streamlit Community Cloud:
Push this repo to GitHub
Go to https://streamlit.io/cloud
Click "New App", connect your repo, and choose app.py
Share your app via the public link provided

👤 Author
Laiba Kirmani
