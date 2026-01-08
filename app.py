# app.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(
    page_title="Direct Deposit Cashflow Analytics",
    layout="wide"
)

st.title("Direct Deposit Cashflow Analytics")
st.caption("Radiology Services | Medical Aid Cashflow Intelligence")

# ------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------
MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------
def normalise_month(sheet_name: str):
    s = sheet_name.lower()
    for k, v in MONTH_MAP.items():
        if k in s:
            return v
    return None


def extract_payer(description: str):
    if pd.isna(description):
        return "UNKNOWN"
    text = description.upper()
    for key in ["PSMAS", "CIMAS", "NSSA", "MEDCOR", "FIRST MUTUAL", "ZIMNAT"]:
        if key in text:
            return key
    return "OTHER"


def clean_month_sheet(df: pd.DataFrame, year: int, month: int):
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Heuristic column detection
    date_col = next((c for c in df.columns if "date" in c), None)
    desc_col = next((c for c in df.columns if "desc" in c or "narr" in c), None)
    usd_col = next((c for c in df.columns if "usd" in c), None)
    zwl_col = next((c for c in df.columns if "zwl" in c or "zwg" in c), None)

    if not any([usd_col, zwl_col]):
        return pd.DataFrame()

    out = pd.DataFrame()
    out["date"] = pd.to_datetime(df[date_col], errors="coerce") if date_col else pd.NaT
    out["payer"] = df[desc_col].apply(extract_payer) if desc_col else "UNKNOWN"
    out["amount_usd"] = pd.to_numeric(df[usd_col], errors="coerce") if usd_col else 0.0
    out["amount_zwl"] = pd.to_numeric(df[zwl_col], errors="coerce") if zwl_col else 0.0
    out["year_month"] = f"{year}-{month:02d}"

    return out.dropna(subset=["amount_usd", "amount_zwl"], how="all")


def load_workbook(file, year):
    try:
        sheets = pd.read_excel(file, sheet_name=None)
    except ImportError:
        st.error("Missing dependency: openpyxl is required to read Excel files. Install it via `pip install openpyxl`.")
        st.stop()
    except Exception as e:
        st.error(f"Failed to read Excel file: {e}")
        st.stop()

    frames = []

    for sheet, df in sheets.items():
        month = normalise_month(sheet)
        if not month:
            continue
        cleaned = clean_month_sheet(df, year, month)
        frames.append(cleaned)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)

# ------------------------------------------------------------
# UI – FILE UPLOAD
# ------------------------------------------------------------
uploaded = st.file_uploader(
    "Upload Financial Year Direct Deposit Workbook",
    type=["xlsx"]
)

if not uploaded:
    st.info("Upload the Excel file to begin analysis.")
    st.stop()

financial_year = st.number_input(
    "Financial Year",
    min_value=2000,
    max_value=2100,
    value=datetime.now().year
)

data = load_workbook(uploaded, financial_year)

if data.empty:
    st.error("No valid monthly sheets detected.")
    st.stop()

# ------------------------------------------------------------
# MONTH LOGIC
# ------------------------------------------------------------
months = sorted(data["year_month"].unique())
current_month = months[-1]
previous_month = months[-2] if len(months) > 1 else None

# ------------------------------------------------------------
# CURRENCY SELECTION
# ------------------------------------------------------------
currency = st.radio("Currency", ["USD", "ZWL"], horizontal=True)

amount_col = "amount_usd" if currency == "USD" else "amount_zwl"

# ------------------------------------------------------------
# DASHBOARD
# ------------------------------------------------------------
st.subheader(f"Reporting Month: {current_month}")

current_df = data[data["year_month"] == current_month]
prev_df = data[data["year_month"] == previous_month] if previous_month else None

total_current = current_df[amount_col].sum()
total_previous = prev_df[amount_col].sum() if prev_df is not None else None

col1, col2, col3 = st.columns(3)

col1.metric(
    f"Total {currency}",
    f"{total_current:,.2f}",
)

if total_previous is not None and total_previous != 0:
    change_pct = ((total_current - total_previous) / total_previous) * 100
    col2.metric(
        "MoM Change",
        f"{change_pct:.1f}%",
        delta=f"{change_pct:.1f}%"
    )
else:
    col2.metric("MoM Change", "N/A")

col3.metric(
    "Active Medical Aids",
    current_df[current_df[amount_col] > 0]["payer"].nunique()
)

# ------------------------------------------------------------
# RANKINGS
# ------------------------------------------------------------
st.subheader("Medical Aid Rankings")

ranking = (
    current_df.groupby("payer")[amount_col]
    .sum()
    .sort_values(ascending=False)
    .reset_index()
)

ranking["rank"] = range(1, len(ranking) + 1)
ranking["contribution_%"] = (ranking[amount_col] / total_current * 100).round(2)

st.dataframe(ranking, use_container_width=True)

# ------------------------------------------------------------
# COMPARISON (AUTO-DISABLED FOR JAN)
# ------------------------------------------------------------
st.subheader("Month-on-Month Comparison")

if previous_month is None:
    st.info("Only one month available. Comparisons will activate automatically once a new month is added.")
else:
    comparison = (
        current_df.groupby("payer")[amount_col].sum()
        .to_frame("current")
        .join(
            prev_df.groupby("payer")[amount_col].sum().to_frame("previous"),
            how="outer"
        )
        .fillna(0)
    )

    comparison["change"] = comparison["current"] - comparison["previous"]
    comparison["change_%"] = np.where(
        comparison["previous"] == 0,
        np.nan,
        (comparison["change"] / comparison["previous"]) * 100
    )

    st.dataframe(comparison.reset_index(), use_container_width=True)

# ------------------------------------------------------------
# RISK ALERTS
# ------------------------------------------------------------
st.subheader("Risk Alerts")

alerts = []

if previous_month is not None:
    for payer, row in comparison.iterrows():
        if row["previous"] > 0 and row["change_%"] < -30:
            alerts.append({
                "payer": payer,
                "issue": "Significant drop",
                "change_%": round(row["change_%"], 1)
            })

if alerts:
    st.dataframe(pd.DataFrame(alerts))
else:
    st.success("No critical alerts detected.")
