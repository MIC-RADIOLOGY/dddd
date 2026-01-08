# app.py
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(page_title="Medical Aid Cashflow Dashboard", layout="wide")

# ------------------------------------------------------------
# CONSTANTS
# ------------------------------------------------------------
MONTHS = [
    "JANUARY","FEBRUARY","MARCH","APRIL","MAY","JUNE",
    "JULY","AUGUST","SEPTEMBER","OCTOBER","NOVEMBER","DECEMBER"
]

TRAILING_MONTHS = 3

# ------------------------------------------------------------
# HELPERS
# ------------------------------------------------------------
def load_workbook(uploaded_file, year):
    xls = pd.ExcelFile(uploaded_file)
    all_rows = []

    for sheet in xls.sheet_names:
        sheet_upper = sheet.upper()
        if sheet_upper not in MONTHS:
            continue

        df = pd.read_excel(uploaded_file, sheet_name=sheet, header=None)

        # Try to locate header row
        header_row = None
        for i in range(min(10, len(df))):
            row = df.iloc[i].astype(str).str.lower()
            if "date" in row.values and "amount" in row.values:
                header_row = i
                break

        if header_row is None:
            continue

        df = pd.read_excel(uploaded_file, sheet_name=sheet, header=header_row)
        df.columns = [c.lower().strip() for c in df.columns]

        # Normalize expected columns
        col_map = {}
        for c in df.columns:
            if "date" in c:
                col_map[c] = "date"
            elif "payer" in c or "medical" in c:
                col_map[c] = "payer"
            elif "amount" in c or "paid" in c:
                col_map[c] = "amount"

        df = df.rename(columns=col_map)

        if not {"date","payer","amount"}.issubset(df.columns):
            continue

        df = df[["date","payer","amount"]]
        df["month"] = sheet_upper
        df["year"] = year

        all_rows.append(df)

    if not all_rows:
        st.error("No usable data found.")
        st.stop()

    out = pd.concat(all_rows, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["amount"] = pd.to_numeric(out["amount"], errors="coerce").fillna(0)

    return out


def cashflow_status(pct):
    if pct <= -10:
        return "🔴 Cashflow Risk"
    elif pct < 5:
        return "🟠 Monitor Closely"
    return "🟢 Healthy Growth"


def payment_risk(days):
    if days >= 45:
        return "🔴 High Risk"
    elif days >= 30:
        return "🟠 Delayed"
    return "🟢 Active"


# ------------------------------------------------------------
# UI
# ------------------------------------------------------------
st.title("📊 Medical Aid Cashflow Early-Warning Dashboard")

uploaded = st.file_uploader("Upload Direct Deposit Excel", type=["xlsx"])
year = st.number_input("Financial Year", value=datetime.now().year)

if not uploaded:
    st.stop()

df = load_workbook(uploaded, year)

# ------------------------------------------------------------
# MONTH SELECTION
# ------------------------------------------------------------
available_months = sorted(df["month"].unique(), key=lambda x: MONTHS.index(x))
selected_month = st.selectbox("Select Month", available_months)

current_idx = MONTHS.index(selected_month)
prev_month = MONTHS[current_idx - 1] if current_idx > 0 else None

current_df = df[df["month"] == selected_month]
prev_df = df[df["month"] == prev_month] if prev_month else None

total_current = current_df["amount"].sum()
total_previous = prev_df["amount"].sum() if prev_df is not None else None

# ------------------------------------------------------------
# KPI ROW
# ------------------------------------------------------------
c1, c2, c3 = st.columns(3)

c1.metric("Total Collections", f"{total_current:,.2f}")

if total_previous and total_previous != 0:
    pct = ((total_current - total_previous) / total_previous) * 100
    label = f"MoM Change ({prev_month[:3]} → {selected_month[:3]})"
    c2.metric(label, f"{pct:.1f}%", delta=f"{pct:.1f}%")
    c3.metric("Cashflow Status", cashflow_status(pct))
else:
    c2.metric("MoM Change", "N/A")
    c3.metric("Cashflow Status", "N/A")

st.caption(
    "ℹ️ MoM Change = ((Current Month − Previous Month) ÷ Previous Month) × 100"
)

# ------------------------------------------------------------
# MONTHLY TREND + SPARKLINE
# ------------------------------------------------------------
monthly_totals = (
    df.groupby("month")["amount"]
    .sum()
    .reindex(MONTHS)
    .dropna()
)

st.subheader("📈 Monthly Collections Trend")
st.line_chart(monthly_totals)

last_6 = monthly_totals.iloc[max(0, current_idx - 5): current_idx + 1]
st.caption("Last 6 months trend")
st.line_chart(last_6, height=120)

# ------------------------------------------------------------
# FORECAST
# ------------------------------------------------------------
forecast = monthly_totals.tail(TRAILING_MONTHS).mean()

st.subheader("🧠 Next-Month Forecast")
st.metric(
    f"Expected Collections (Trailing {TRAILING_MONTHS}-Month Avg)",
    f"{forecast:,.2f}"
)

# ------------------------------------------------------------
# TOP MEDICAL AIDS (BAR CHART)
# ------------------------------------------------------------
st.subheader("🏥 Top Medical Aids – Selected Month")

top_payers = (
    current_df.groupby("payer")["amount"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
)

st.bar_chart(top_payers)

# ------------------------------------------------------------
# DAYS SINCE LAST PAYMENT
# ------------------------------------------------------------
latest_date = df["date"].max()

dslp = (
    df.groupby("payer")["date"]
    .max()
    .reset_index()
)

dslp["days_since_last_payment"] = (latest_date - dslp["date"]).dt.days
dslp["status"] = dslp["days_since_last_payment"].apply(payment_risk)
dslp = dslp.sort_values("days_since_last_payment", ascending=False)

st.subheader("⏳ Days Since Last Payment (Risk View)")
st.dataframe(dslp, use_container_width=True)

# Graph
st.subheader("📉 Payment Delay by Medical Aid")
delay_chart = dslp.set_index("payer")["days_since_last_payment"]
st.bar_chart(delay_chart)
