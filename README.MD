# Direct Deposit Cashflow Analytics

## Purpose
This Streamlit application analyses direct deposit data from medical aid providers
to provide early warning signals for cashflow risks in a radiology practice.

## Key Features
- Sheet-based monthly ingestion
- One financial year per workbook
- USD and ZWL analysed separately
- Automatic month detection
- Month-on-month comparison starts automatically when a new month is added
- Medical aid rankings and risk alerts

## File Requirements
- One Excel workbook per financial year
- Each sheet represents one month (e.g. January, Feb, Mar 2025)
- Workbook can be updated daily

## How It Works
1. Upload the workbook
2. App detects all monthly sheets
3. Latest month becomes the reporting month
4. Previous month used automatically for comparison (if available)

## January Rule
If only January exists:
- Reporting only
- No comparisons
- No alerts

Comparisons activate automatically from February onward.

## Running the App
```bash
pip install -r requirements.txt
streamlit run app.py
