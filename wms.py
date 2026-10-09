import streamlit as st
import pandas as pd
from datetime import datetime, date
import hashlib, time
# --- Google Sheet 連接 ---
try:
    from streamlit_gsheets import GSheetsConnection
    USE_GSHEET = True
except:
    USE_GSHEET = False

def hash_pw(pw): return hashlib.sha256(pw.encode()).hexdigest()

st.set_page_config(page_title="WMS 永久版", layout="wide")
# --- 連接 ---
if USE_GSHEET and "connections" in st.secrets:
    conn = st.connection("gsheets", type=GSheetsConnection)
    def read_sheet(name):
        try: return conn.read(worksheet=name, ttl=0)
        except: return pd.DataFrame()
    def write_sheet(name, df):
        conn.update(worksheet=name, data=df)
else:
    st.warning("未偵測到Google Sheet Secrets，暫用本地模式(會洗DB)，請跟教學設定Secrets")
    import sqlite3
    DB="wms.db"
    def get_conn():
        c=sqlite3.connect(DB, check_same_thread=False)
        c.execute("CREATE TABLE IF NOT EXISTS skus (sku_code TEXT PRIMARY KEY, name TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS inventory (sku_code TEXT PRIMARY KEY, qty REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS ledger (time TEXT,type TEXT,sku_code TEXT,qty REAL,uom TEXT,inspection_note TEXT,transfer_note TEXT,mfd TEXT,receiving_date TEXT,release_date TEXT,user TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY,password TEXT,role TEXT)")
        if not c.execute("SELECT * FROM users").fetchone():
            c.execute("INSERT INTO users VALUES (?,?,?)",("admin",hash_pw("admin123"),"Admin")); c.commit()
        return c
    sql_conn=get_conn()
    def read_sheet(name):
        return pd.read_sql(f"SELECT * FROM {name}", sql_conn)
    def write_sheet(name, df):
        df.to_sql(name, sql_conn, if_exists="replace", index=False); sql_conn.commit()

# --- Login ---
if "logged_in" not in st.session_state: st.session_state.logged_in=False
if not st.session_state.logged_in:
    st.title("🔐 WMS 登入 - 永久版")
   # ---  st.info("預設: admin / admin123") ---
    u=st.text_input("帳號"); p=st.text_input("密碼", type="password")
    if st.button("登入", type="primary"):
        users=read_sheet("users")
        if not users.empty and ((users["username"]==u) & (users["password"]==hash_pw(p))).any():
            st.session_state.logged_in=True; st.session_state.user=u
            st.session_state.role=users[users["username"]==u].iloc[0]["role"]; st.rerun()
        else: st.error("錯")
    st.stop()

st.sidebar.write(f"👤 {st.session_state.user}")
if st.sidebar.button("登出"): st.session_state.logged_in=False; st.rerun()
func=st.sidebar.selectbox("功能", ["庫存總覽","1. 入庫收貨","2. 出庫發貨","庫存流水","SKU管理","用戶管理"])

if func=="庫存總覽":
    skus=read_sheet("skus"); inv=read_sheet("inventory")
    if not skus.empty and not inv.empty: df=pd.merge(skus, inv, on="sku_code", how="left").fillna(0)
    else: df=skus
    st.title("庫存總覽 - 永久版"); st.dataframe(df, use_container_width=True)

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
            if sku in inv["sku_code"].values: inv.loc[inv["sku_code"]==sku, "qty"]+=qty
            else: inv=pd.concat([inv, pd.DataFrame([{"sku_code":sku,"qty":qty}])], ignore_index=True)
            new_row={"time":now_str,"type":"IN","sku_code":sku,"qty":qty,"uom":uom,"inspection_note":ins,"transfer_note":"","mfd":mfd.strftime("%d/%m/%Y"),"receiving_date":now_str,"release_date":"","user":st.session_state.user}
            led=pd.concat([led, pd.DataFrame([new_row])], ignore_index=True)
            write_sheet("inventory", inv); write_sheet("ledger", led); st.success("收貨成功寫入Google Sheet!"); st.balloons()

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
        cur_qty=inv[inv["sku_code"]==sku]["qty"].values[0] if sku in inv["sku_code"].values else 0
        if cur_qty < qty: st.error(f"庫存不足 {cur_qty}")
        else:
            inv.loc[inv["sku_code"]==sku, "qty"]-=qty
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
    
