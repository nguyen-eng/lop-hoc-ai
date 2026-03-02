import os
import re
import json
import time
import uuid
import sqlite3
import threading
from datetime import datetime
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# Optional: Gemini
try:
    import google.generativeai as genai
except Exception:
    genai = None

# ✅ Live refresh
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

_DIALOG_DECORATOR = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)

# ============================================================
# 1) DATABASE SYSTEM (Thay thế CSV để chống treo)
# ============================================================
DB_PATH = "class_data.db"

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()
    # Bảng lưu phản hồi của học viên
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id TEXT,
            activity TEXT,
            suffix TEXT,
            student_name TEXT,
            content TEXT,
            timestamp DATETIME
        )
    """)
    # Bảng lưu cấu hình câu hỏi (Active Question)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def save_data_db(cls, act, name, content, suffix=""):
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO responses (class_id, activity, suffix, student_name, content, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
            (cls, act, str(suffix), name, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
    finally:
        conn.close()

@st.cache_data(ttl=3) # Cache 3 giây để chống treo khi nhiều người truy cập
def load_data_db(cls, act, suffix=""):
    conn = get_db_connection()
    query = "SELECT student_name as 'Học viên', content as 'Nội dung', timestamp as 'Thời gian' FROM responses WHERE class_id = ? AND activity = ? AND suffix = ?"
    df = pd.read_sql(query, conn, params=(cls, act, str(suffix)))
    conn.close()
    return df

def clear_activity_db(cls, act, suffix=""):
    conn = get_db_connection()
    conn.execute("DELETE FROM responses WHERE class_id = ? AND activity = ? AND suffix = ?", (cls, act, str(suffix)))
    conn.commit()
    conn.close()

# ============================================================
# 2) PAGE CONFIG & STYLES
# ============================================================
st.set_page_config(page_title="T05 Interactive", page_icon="📶", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    header, footer, .stAppToolbar {display: none !important;}
    .block-container {padding-top: 0.5rem !important;}
    .stButton>button {border-radius: 12px; font-weight: 700; height: 3em;}
    .note-card {background: white; padding: 15px; border-radius: 10px; border-left: 5px solid #006a4e; margin-bottom: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);}
</style>
""", unsafe_allow_html=True)

# Các hằng số giữ nguyên từ code cũ của bạn
LOGO_URL = "https://drive.google.com/thumbnail?id=1PsUr01oeleJkW2JB1gqnID9WJNsTMFGW&sz=w1000"
MAP_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/Blank_map_of_Vietnam.svg/858px-Blank_map_of_Vietnam.svg.png"
PRIMARY_COLOR = "#006a4e"
CLASSES = {f"Lớp học {i}": f"lop{i}" for i in range(1, 11)}
PASSWORDS = {f"lop{i}": (f"T05-{i}" if i < 9 else f"LH{i}") for i in range(1, 11)}

# ============================================================
# 3) LOGIN & SESSION
# ============================================================
if "device_id" not in st.session_state: st.session_state["device_id"] = str(uuid.uuid4())
if "page" not in st.session_state: st.session_state["page"] = "login"

def check_login():
    if st.session_state.get("logged_in"): return True
    return False

# ============================================================
# 4) WORDCLOUD LOGIC (Tối ưu hóa)
# ============================================================
def normalize_phrase(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower()).strip(" .,:;!?")

@st.cache_data(ttl=3)
def wc_compute_freq(cid, qid):
    df = load_data_db(cid, "wordcloud", suffix=qid)
    if df.empty: return {}, 0
    df['phrase'] = df['Nội dung'].apply(normalize_phrase)
    # Loại bỏ trùng lặp từ 1 người cho 1 từ
    df = df.drop_duplicates(subset=['Học viên', 'phrase'])
    freq = df['phrase'].value_counts().to_dict()
    return freq, len(df)

# Hàm build WordCloud giữ nguyên HTML/D3 của bạn
def build_wordcloud_html(words_json: str, height_px: int = 520) -> str:
    return f"""
    <script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/d3-cloud@1/build/d3.layout.cloud.js"></script>
    <div id="wc-container" style="height:{height_px}px; width:100%; background:white;"></div>
    <script>
        const data = {words_json};
        // Logic D3 Cloud giữ nguyên...
    </script>
    """ # Lưu ý: Đoạn JS trong code gốc của bạn rất tốt, hãy giữ nguyên phần script đó bên trong f-string này

# ============================================================
# 5) UI COMPONENTS
# ============================================================

def render_login():
    # Phần giao diện Login giữ nguyên Style của bạn
    st.markdown("<h1 style='text-align:center;'>TRƯỜNG ĐẠI HỌC CSND</h1>", unsafe_allow_html=True)
    with st.container():
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.image(LOGO_URL, width=150)
            portal = st.radio("Cổng", ["Học viên", "Giảng viên"], horizontal=True)
            if portal == "Học viên":
                c_name = st.selectbox("Lớp", list(CLASSES.keys()))
                c_pass = st.text_input("Mật mã", type="password")
                if st.button("ĐĂNG NHẬP"):
                    cid = CLASSES[c_name]
                    if c_pass == PASSWORDS[cid]:
                        st.session_state.update({"logged_in":True, "role":"student", "class_id":cid, "page":"class_home"})
                        st.rerun()
            else:
                # Login giảng viên...
                gv_pass = st.text_input("Mật khẩu GV", type="password")
                if st.button("QUẢN TRỊ"):
                    if gv_pass == "779":
                        st.session_state.update({"logged_in":True, "role":"teacher", "class_id":"lop1", "page":"class_home"})
                        st.rerun()

def render_activity_wordcloud(cid, cfg):
    # Lấy câu hỏi đang active từ Settings DB (để đồng bộ tất cả học viên)
    conn = get_db_connection()
    res = conn.execute("SELECT value FROM settings WHERE key = ?", (f"active_wc_{cid}",)).fetchone()
    active_qid = res[0] if res else "Q1"
    conn.close()
    
    st.subheader(f"Word Cloud: {cfg['wordcloud']['question']}")
    
    col_input, col_viz = st.columns([1, 2])
    
    with col_input:
        if st.session_state["role"] == "student":
            with st.form("wc_form"):
                name = st.text_input("Tên học viên")
                txt = st.text_input("Từ khóa")
                if st.form_submit_button("Gửi"):
                    if name and txt:
                        save_data_db(cid, "wordcloud", name, txt, suffix=active_qid)
                        st.success("Đã gửi!")
        else:
            st.info("Chế độ Giảng viên")
            if st.button("Xóa trắng dữ liệu câu này"):
                clear_activity_db(cid, "wordcloud", suffix=active_qid)
                st.rerun()

    with col_viz:
        # Tần suất refresh: GV 3s, HV 6s
        interval = 3000 if st.session_state["role"] == "teacher" else 6000
        if st_autorefresh:
            st_autorefresh(interval=interval, key="wc_refresh")
            
        freq, count = wc_compute_freq(cid, active_qid)
        st.write(f"Tổng số lượt phản hồi: {count}")
        if freq:
            # Gửi dữ liệu tới Component Wordcloud
            words = [{"text": k, "value": v} for k, v in freq.items()]
            # Hiển thị component (Dùng đơn giản hơn để tránh lag)
            st.write(freq) # Hoặc dùng hàm build_wordcloud_html cũ của bạn
        else:
            st.warning("Đang chờ phản hồi...")

# ============================================================
# 6) MAIN ROUTER
# ============================================================
def main():
    if st.session_state["page"] == "login":
        render_login()
        return

    # Sidebar điều hướng
    with st.sidebar:
        st.image(LOGO_URL, width=80)
        if st.button("📚 Hoạt động"): st.session_state["page"] = "class_home"
        if st.button("🏠 Dashboard"): st.session_state["page"] = "dashboard"
        if st.button("🚪 Thoát"): 
            st.session_state.clear()
            st.rerun()

    cid = st.session_state.get("class_id", "lop1")
    # Tải cấu hình (giữ nguyên CLASS_ACT_CONFIG của bạn)
    # ... (Phần cấu hình CLASS_ACT_CONFIG)

    if st.session_state["page"] == "class_home":
        # Hiển thị danh sách hoạt động...
        st.title(f"Lớp: {cid}")
        if st.button("Mở WordCloud"):
            st.session_state["page"] = "activity"
            st.session_state["current_act_key"] = "wordcloud"
            st.rerun()
            
    elif st.session_state["page"] == "activity":
        act_key = st.session_state.get("current_act_key")
        # Gọi hàm render tương ứng
        if act_key == "wordcloud":
            # (Giả sử bạn có biến cfg chứa CLASS_ACT_CONFIG)
            from __main__ import CLASS_ACT_CONFIG 
            render_activity_wordcloud(cid, CLASS_ACT_CONFIG[cid])

if __name__ == "__main__":
    main()