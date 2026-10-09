import streamlit as st
import pandas as pd
from datetime import datetime, date
import hashlib, time
import gspread
from google.oauth2.service_account import Credentials

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()
st.set_page_config(page_title="WMS 永久版", layout="wide")

# --- Google Sheet 連接 (新版gspread) ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
if "gcp_service_account" in st.secrets:
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
    gc = gspread.authorize(creds)
    SPREADSHEET_ID = st.secrets["connections"]["gsheets"]["spreadsheet"] if "connections" in st.secrets else st.secrets["connections.gsheets"]["spreadsheet"]
    sh = gc.open_by_key(SPREADSHEET_ID)

    def read_sheet(name):
        try:
            ws = sh.worksheet(name)
            data = ws.get_all_records()
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"讀取 {name} 失敗: {e}")
            return pd.DataFrame()

    def write_sheet(name, df):
        ws = sh.worksheet(name)
        ws.clear()
        ws.update([df.columns.values.tolist()] + df.values.tolist())

    # 初始化 users
    try:
        users = read_sheet("users")
        if users.empty:
            write_sheet("users", pd.DataFrame([{"username":"admin","password":hash_pw("admin123"),"role":"Admin"}]))
    except:
        pass
    USE_GSHEET = True
else:
    st.error("❌ 未偵測到Secrets！請檢查.streamlit/secrets.toml")
    st.stop()

# --- Login ---
if "logged_in" not in st.session_state: st.session_state.logged_in=False
if not st.session_state.logged_in:
    st.title("🔐 WMS 登入 - 永久版")
    st.info("預設: admin / admin123")
    u=st.text_input("帳號"); p=st.text_input("密碼", type="password")
    if st.button("登入", type="primary"):
        users=read_sheet("users")
        if not users.empty and ((users["username"]==u) & (users["password"]==hash_pw(p))).any():
            st.session_state.logged_in=True; st.session_state.user=u
            st.session_state.role=users[users["username"]==u].iloc[0]["role"]; st.rerun()
        else: st.error("帳號或密碼錯")
    st.stop()

st.sidebar.write(f"👤 {st.session_state.user} - {st.session_state.role}")
if st.sidebar.button("登出"): st.session_state.logged_in=False; st.rerun()
func=st.sidebar.selectbox("功能", ["庫存總覽","1. 入庫收貨","2. 出庫發貨","庫存流水","SKU管理","用戶管理"])

if func=="庫存總覽":
    skus=read_sheet("skus"); inv=read_sheet("inventory")
    if not skus.empty and not inv.empty: df=pd.merge(skus, inv, on="sku_code", how="left").fillna(0)
    else: df=skus
    st.title("庫存總覽 - 永久版 (Google Sheet)"); st.dataframe(df, use_container_width=True)

elif func=="1. 入庫收貨":
    now_str=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.title("入庫收貨"); st.text_input("Receiving Date", value=now_str, disabled=True)
    c1,c2=st.columns(2)
    with c1:
        ins=st.text_input("Inspection Note # *"); mfd=st.date_input("MFD *", value=date.today(), format="DD/MM/YYYY")
    with c2:
        uom=st.selectbox("UOM *",["","PCS","KG"]); qty=st.number_input("QTY *", min_value=0.0, step=1.0)
    skus=read_sheet("skus"); sku=st.selectbox("SKU *",[""]+list(skus["sku_code"]) if not skus.empty else [])
    if st.button("✅ 確認收貨", type="primary"):
        if not all([ins, uom, qty>0, sku]): st.error("必填未填")
        else:
            inv=read_sheet("inventory"); led=read_sheet("ledger")
            if not inv.empty and sku in inv["sku_code"].values: inv.loc[inv["sku_code"]==sku, "qty"]=inv.loc[inv["sku_code"]==sku, "qty"].astype(float)+qty
            else: inv=pd.concat([inv, pd.DataFrame([{"sku_code":sku,"qty":qty}])], ignore_index=True)
            new_row={"time":now_str,"type":"IN","sku_code":sku,"qty":qty,"uom":uom,"inspection_note":ins,"transfer_note":"","mfd":mfd.strftime("%d/%m/%Y"),"receiving_date":now_str,"release_date":"","user":st.session_state.user}
            led=pd.concat([led, pd.DataFrame([new_row])], ignore_index=True)
            write_sheet("inventory", inv); write_sheet("ledger", led); st.success("✅ 已寫入Google Sheet！去Sheet睇下！"); st.balloons()

elif func=="2. 出庫發貨":
    now_str=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.title("出庫發貨"); st.text_input("Release Date", value=now_str, disabled=True)
    c1,c2=st.columns(2)
    with c1:
        tr=st.text_input("Transfer Note # *"); mfd=st.date_input("MFD *", value=date.today(), format="DD/MM/YYYY", key="mfd2")
    with c2:
        uom=st.selectbox("UOM *",["","PCS","KG"], key="uom2"); qty=st.number_input("QTY *", min_value=0.0, step=1.0, key="qty2")
    skus=read_sheet("skus"); sku=st.selectbox("SKU *",[""]+list(skus["sku_code"]) if not skus.empty else [], key="sku2")
    if st.button("✅ 確認發貨", type="primary"):
        inv=read_sheet("inventory"); led=read_sheet("ledger")
        cur_qty=float(inv[inv["sku_code"]==sku]["qty"].values[0]) if not inv.empty and sku in inv["sku_code"].values else 0
        if cur_qty < qty: st.error(f"庫存不足 {cur_qty}")
        else:
            inv.loc[inv["sku_code"]==sku, "qty"]=inv.loc[inv["sku_code"]==sku, "qty"].astype(float)-qty
            new_row={"time":now_str,"type":"OUT","sku_code":sku,"qty":qty,"uom":uom,"inspection_note":"","transfer_note":tr,"mfd":mfd.strftime("%d/%m/%Y"),"receiving_date":"","release_date":now_str,"user":st.session_state.user}
            led=pd.concat([led, pd.DataFrame([new_row])], ignore_index=True)
            write_sheet("inventory", inv); write_sheet("ledger", led); st.success("發貨成功寫入Google Sheet!")

elif func=="庫存流水":
    st.title("庫存流水"); df=read_sheet("ledger"); st.dataframe(df, use_container_width=True)

elif func=="SKU管理":
    st.title("SKU管理"); up=st.file_uploader("上傳Master", type=["xlsx","csv"])
    if up:
        df=pd.read_excel(up, sheet_name="Master") if "Master" in pd.ExcelFile(up).sheet_names else pd.read_excel(up)
        df=df.iloc[:,0:2]; df.columns=["sku_code","name"]
        write_sheet("skus", df)
        inv=pd.DataFrame([{"sku_code":s,"qty":0} for s in df["sku_code"]]); write_sheet("inventory", inv)
        st.success(f"導入 {len(df)} 個SKU入Google Sheet永久儲存!")
    st.dataframe(read_sheet("skus"), use_container_width=True)

elif func=="用戶管理":
    st.title("用戶管理"); users=read_sheet("users"); st.dataframe(users[["username","role"]], use_container_width=True)
    c1,c2,c3=st.columns(3)
    with c1: nu=st.text_input("新帳號")
    with c2: np=st.text_input("新密碼")
    with c3: nr=st.selectbox("權限",["Staff","Admin"])
    if st.button("新增"):
        new=pd.DataFrame([{"username":nu,"password":hash_pw(np),"role":nr}])
        write_sheet("users", pd.concat([users,new], ignore_index=True)); st.success("已新增")
