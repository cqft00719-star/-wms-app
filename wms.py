import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime

st.set_page_config(page_title="WMS 永久版", layout="wide")

# --- 連接Google Sheet ---
@st.cache_resource
def get_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    sheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
    # 如果你用 [connections.gsheets] 就改上面做 st.secrets["connections.gsheets"]["spreadsheet"]
    try:
        sheet_id = st.secrets["connections"]["gsheets"]["spreadsheet"]
    except:
        sheet_id = st.secrets["connections.gsheets"]["spreadsheet"]
    return client.open_by_key(sheet_id)

def load_data(tab):
    try:
        sh = get_sheet()
        ws = sh.worksheet(tab)
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def save_row(tab, row_dict):
    sh = get_sheet()
    ws = sh.worksheet(tab)
    ws.append_row(list(row_dict.values()))

# --- 登入 ---
if "login" not in st.session_state:
    st.session_state.login = False
if not st.session_state.login:
    st.title("Login")
    pw = st.text_input("密碼", type="password")
    if st.button("登入"):
        if pw == "1234": # 你嘅密碼
            st.session_state.login = True
            st.rerun()
        else:
            st.error("密碼錯")
    st.stop()

# --- 主程式 ---
st.title("WMS 永久版 - 已連Google Sheet")

tab1, tab2 = st.tabs(["1.入庫收貨", "查看Ledger"])

with tab1:
    sku = st.text_input("SKU")
    qty = st.number_input("數量", min_value=1, value=1)
    if st.button("入庫"):
        if sku:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_row("ledger", {"date": now, "sku": sku, "type": "IN", "qty": qty, "remark": "入庫"})
            st.success(f"{sku} 入庫 {qty} 成功！已寫入Google Sheet")
        else:
            st.error("請入SKU")

with tab2:
    df = load_data("ledger")
    st.dataframe(df, use_container_width=True)