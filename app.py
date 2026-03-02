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

# ✅ 0. Cấu hình ban đầu
st.set_page_config(page_title="T05 Interactive Class", page_icon="📶", layout="wide", initial_sidebar_state="collapsed")

# ✅ 1. DATABASE SYSTEM (Thay thế CSV hoàn toàn)
DB_PATH = "interactive_class.db"

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    # Lưu phản hồi (WC, OE, Poll, Scales, Rank, Pin)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id TEXT, activity TEXT, suffix TEXT, 
            student_name TEXT, content TEXT, timestamp TEXT
        )
    """)
    # Lưu trạng thái câu hỏi active (Bank câu hỏi)
    conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    # Lưu thiết bị đã vote để chặn spam
    conn.execute("CREATE TABLE IF NOT EXISTS vote_locks (class_id TEXT, device_id TEXT, PRIMARY KEY(class_id, device_id))")
    conn.commit()
    conn.close()

init_db()

# --- Helper DB ---
def save_data(cls, act, name, content, suffix=""):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO responses (class_id, activity, suffix, student_name, content, timestamp) VALUES (?,?,?,?,?,?)",
                 (cls, act, str(suffix), name, str(content), datetime.now().strftime("%H:%M:%S")))
    conn.commit()
    conn.close()

@st.cache_data(ttl=3) # Tối ưu: Chỉ đọc từ đĩa 3 giây một lần
def load_data(cls, act, suffix=""):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT student_name as 'Học viên', content as 'Nội dung', timestamp as 'Thời gian' FROM responses WHERE class_id=? AND activity=? AND suffix=?", 
                     conn, params=(cls, act, str(suffix)))
    conn.close()
    return df

def clear_data(cls, act, suffix=""):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM responses WHERE class_id=? AND activity=? AND suffix=?", (cls, act, str(suffix)))
    conn.commit()
    conn.close()

# --- Quản lý câu hỏi active (Bank) ---
def get_active_qid(cls, act):
    conn = sqlite3.connect(DB_PATH)
    res = conn.execute("SELECT value FROM settings WHERE key=?", (f"{cls}_{act}_active",)).fetchone()
    conn.close()
    return res[0] if res else "Q1"

def set_active_qid(cls, act, qid):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (f"{cls}_{act}_active", qid))
    conn.commit()
    conn.close()

# ✅ 2. STYLE & CSS (Giữ nguyên giao diện đẹp của bạn)
LOGO_URL = "https://drive.google.com/thumbnail?id=1PsUr01oeleJkW2JB1gqnID9WJNsTMFGW&sz=w1000"
MAP_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/Blank_map_of_Vietnam.svg/858px-Blank_map_of_Vietnam.svg.png"
PRIMARY_COLOR = "#006a4e"

st.markdown(f"""
<style>
    header, footer, .stAppToolbar {{display: none !important;}}
    .block-container {{padding-top: 0rem !important;}}
    .stButton>button {{background-color: {PRIMARY_COLOR}; color: white; border-radius: 14px; font-weight: 800; height: 3.5em;}}
    .note-card {{background: white; padding: 15px; border-radius: 14px; border-left: 6px solid {PRIMARY_COLOR}; margin-bottom: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.06); font-size: 20px;}}
    .act-row {{background: white; border: 1px solid #e2e8f0; border-radius: 18px; padding: 16px; margin-bottom: 12px;}}
</style>
""", unsafe_allow_html=True)

# ✅ 3. CONFIG LỚP HỌC (Giữ cấu trúc gốc)
CLASSES = {f"Lớp học {i}": f"lop{i}" for i in range(1, 11)}
PASSWORDS = {f"lop{i}": (f"T05-{i}" if i < 9 else f"LH{i}") for i in range(1, 11)}

CLASS_ACT_CONFIG = {}
for i in range(1, 11):
    cid = f"lop{i}"
    CLASS_ACT_CONFIG[cid] = {
        "wordcloud": {"name": "Word Cloud", "type": "Từ khóa", "question": "Nêu 1 từ khóa đặc trưng..."},
        "poll": {"name": "Poll", "type": "Bình chọn", "question": "Bản chất là gì?", "options": ["Option A", "Option B", "Option C", "Option D"]},
        "openended": {"name": "Open Ended", "type": "Trả lời mở", "question": "Phân tích ví dụ sau..."},
        "scales": {"name": "Scales", "type": "Thang đo", "question": "Tự đánh giá năng lực (1-5)", "criteria": ["Lý luận", "Thực tiễn", "Kỹ năng", "Thái độ"]},
        "ranking": {"name": "Ranking", "type": "Xếp hạng", "question": "Sắp xếp thứ tự ưu tiên", "items": ["Bước 1", "Bước 2", "Bước 3", "Bước 4"]},
        "pin": {"name": "Pin", "type": "Ghim ảnh", "question": "Ghim điểm nóng trên bản đồ", "image": MAP_IMAGE}
    }

# ✅ 4. WORDCLOUD D3 LOGIC (Full code JS của bạn)
def build_wordcloud_html(words_json, height_px=520):
    return f"""
    <div id="wc-wrap" style="width:100%; height:{height_px}px; background:white; border-radius:12px;"></div>
    <script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/d3-cloud@1/build/d3.layout.cloud.js"></script>
    <script>
        const data = {words_json};
        const W = document.getElementById('wc-wrap').offsetWidth || 800;
        const H = {height_px};
        const fontScale = d3.scaleSqrt().domain([1, d3.max(data, d => d.value) || 10]).range([20, 80]);
        d3.layout.cloud().size([W, H]).words(data.map(d => ({{text: d.text, size: fontScale(d.value)}})))
            .padding(5).rotate(0).font("Montserrat").fontSize(d => d.size).on("end", draw).start();
        function draw(words) {{
            d3.select("#wc-wrap").append("svg").attr("width", W).attr("height", H).append("g")
                .attr("transform", "translate(" + W/2 + "," + H/2 + ")").selectAll("text")
                .data(words).enter().append("text").style("font-size", d => d.size + "px")
                .style("fill", () => d3.schemeCategory10[Math.floor(Math.random() * 10)])
                .attr("text-anchor", "middle").attr("transform", d => "translate(" + [d.x, d.y] + ")")
                .text(d => d.text);
        }}
    </script>
    """

# ✅ 5. ROUTER & PAGES
if "page" not in st.session_state: st.session_state["page"] = "login"
if "device_id" not in st.session_state: st.session_state["device_id"] = str(uuid.uuid4())

# --- LOGIN ---
def render_login():
    st.markdown("<div style='text-align:center; padding: 20px;'><img src='"+LOGO_URL+"' width='120'></div>", unsafe_allow_html=True)
    with st.container():
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            st.title(" Interactive T05")
            portal = st.radio("Cổng đăng nhập", ["Học viên", "Giảng viên"], horizontal=True)
            c_label = st.selectbox("Lớp học phần", list(CLASSES.keys()))
            pwd = st.text_input("Mã bảo mật", type="password")
            if st.button("ĐĂNG NHẬP"):
                cid = CLASSES[c_label]
                if (portal == "Học viên" and pwd == PASSWORDS[cid]) or (portal == "Giảng viên" and pwd == "779"):
                    st.session_state.update({"logged_in": True, "role": "student" if portal == "Học viên" else "teacher", "class_id": cid, "page": "home"})
                    st.rerun()
                else: st.error("Sai mã bảo mật!")

# --- HOME ---
def render_home():
    cid = st.session_state["class_id"]
    st.title(f"📚 Hoạt động lớp: {cid.upper()}")
    for key, act in CLASS_ACT_CONFIG[cid].items():
        colL, colR = st.columns([5, 1])
        with colL:
            st.markdown(f"<div class='act-row'><b>{act['name']}</b><br><small>{act['type']}</small></div>", unsafe_allow_html=True)
        with colR:
            if st.button("MỞ", key=f"btn_{key}"):
                st.session_state.update({"page": "activity", "act_key": key})
                st.rerun()

# --- ACTIVITIES ---
def render_activity():
    cid = st.session_state["class_id"]
    key = st.session_state["act_key"]
    cfg = CLASS_ACT_CONFIG[cid][key]
    qid = get_active_qid(cid, key)

    if st.button("⬅️ QUAY LẠI"): st.session_state["page"] = "home"; st.rerun()
    st.header(cfg["name"])

    # 1. WORD CLOUD
    if key == "wordcloud":
        col1, col2 = st.columns([1, 2])
        with col1:
            st.info(cfg["question"])
            if st.session_state["role"] == "student":
                with st.form("f_wc"):
                    n = st.text_input("Tên"); t = st.text_input("Từ khóa")
                    if st.form_submit_button("GỬI"): save_data(cid, key, n, t, qid); st.success("Đã gửi!"); st.rerun()
            else:
                new_q = st.text_input("Quản trị QID (Q1, Q2...)", value=qid)
                if st.button("Kích hoạt QID"): set_active_qid(cid, key, new_q); st.rerun()
                if st.button("Xóa dữ liệu câu này"): clear_data(cid, key, qid); st.rerun()
        with col2:
            # Autorefresh động: GV 2s, HV 5s để chống treo
            refresh = 2000 if st.session_state["role"] == "teacher" else 5000
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=refresh, key="wc_refresh")
            df = load_data(cid, key, qid)
            if not df.empty:
                freq = df['Nội dung'].str.lower().value_counts().to_dict()
                words_json = json.dumps([{"text": k, "value": v} for k, v in freq.items()])
                st.components.v1.html(build_wordcloud_html(words_json), height=550)
            else: st.warning("Chưa có phản hồi.")

    # 2. POLL
    elif key == "poll":
        col1, col2 = st.columns([1, 2])
        with col1:
            st.write(cfg["question"])
            conn = sqlite3.connect(DB_PATH)
            voted = conn.execute("SELECT 1 FROM vote_locks WHERE class_id=? AND device_id=?", (cid, st.session_state["device_id"])).fetchone()
            conn.close()
            if voted: st.success("Bạn đã bình chọn.")
            else:
                with st.form("f_poll"):
                    n = st.text_input("Tên"); c = st.radio("Chọn", cfg["options"])
                    if st.form_submit_button("BÌNH CHỌN"):
                        save_data(cid, key, n, c)
                        conn = sqlite3.connect(DB_PATH); conn.execute("INSERT INTO vote_locks VALUES (?,?)", (cid, st.session_state["device_id"])); conn.commit(); conn.close()
                        st.rerun()
        with col2:
            df = load_data(cid, key)
            if not df.empty:
                st.plotly_chart(px.bar(df['Nội dung'].value_counts()), use_container_width=True)

    # 3. OPEN ENDED
    elif key == "openended":
        col1, col2 = st.columns([1, 2])
        with col1:
            st.write(cfg["question"])
            if st.session_state["role"] == "student":
                with st.form("f_oe"):
                    n = st.text_input("Tên"); c = st.text_area("Câu trả lời")
                    if st.form_submit_button("GỬI"): save_data(cid, key, n, c, qid); st.rerun()
        with col2:
            df = load_data(cid, key, qid)
            for _, r in df.tail(30).iterrows(): # Chỉ hiện 30 câu mới nhất để mượt
                st.markdown(f"<div class='note-card'><b>{r['Học viên']}:</b> {r['Nội dung']}</div>", unsafe_allow_html=True)

    # 4. SCALES (Radar chart)
    elif key == "scales":
        col1, col2 = st.columns([1, 2])
        criteria = cfg["criteria"]
        with col1:
            with st.form("f_sc"):
                n = st.text_input("Tên")
                vals = [st.slider(c, 1, 5, 3) for c in criteria]
                if st.form_submit_button("GỬI"): save_data(cid, key, n, ",".join(map(str, vals))); st.rerun()
        with col2:
            df = load_data(cid, key)
            if not df.empty:
                all_vals = np.array([list(map(int, x.split(','))) for x in df['Nội dung']])
                avg = np.mean(all_vals, axis=0)
                fig = go.Figure(data=go.Scatterpolar(r=avg, theta=criteria, fill='toself'))
                st.plotly_chart(fig, use_container_width=True)

    # 5. RANKING
    elif key == "ranking":
        col1, col2 = st.columns([1, 2])
        items = cfg["items"]
        with col1:
            with st.form("f_rk"):
                n = st.text_input("Tên")
                order = st.multiselect("Thứ tự ưu tiên", items, default=items)
                if st.form_submit_button("NỘP"): save_data(cid, key, n, "->".join(order)); st.rerun()
        with col2:
            df = load_data(cid, key)
            if not df.empty:
                scores = {it: 0 for it in items}
                for row in df['Nội dung']:
                    parts = row.split("->")
                    for i, p in enumerate(parts): scores[p] += (len(items) - i)
                st.plotly_chart(px.bar(x=list(scores.values()), y=list(scores.keys()), orientation='h'), use_container_width=True)

    # 6. PIN
    elif key == "pin":
        col1, col2 = st.columns([1, 2])
        with col1:
            with st.form("f_pin"):
                n = st.text_input("Tên")
                x = st.slider("X (%)", 0, 100, 50); y = st.slider("Y (%)", 0, 100, 50)
                if st.form_submit_button("GHIM"): save_data(cid, key, n, f"{x},{y}"); st.rerun()
        with col2:
            df = load_data(cid, key)
            fig = go.Figure()
            fig.add_layout_image(dict(source=cfg["image"], xref="x", yref="y", x=0, y=100, sizex=100, sizey=100, sizing="stretch", layer="below"))
            if not df.empty:
                pts = [list(map(float, x.split(','))) for x in df['Nội dung']]
                pxs, pys = zip(*pts)
                fig.add_trace(go.Scatter(x=pxs, y=[100-y for y in pys], mode='markers', marker=dict(size=15, color='red')))
            fig.update_xaxes(range=[0, 100], visible=False); fig.update_yaxes(range=[0, 100], visible=False)
            st.plotly_chart(fig, use_container_width=True)

# ✅ 6. MAIN ROUTER
def main():
    if st.session_state["page"] == "login": render_login()
    elif st.session_state["page"] == "home":
        with st.sidebar:
            st.image(LOGO_URL, width=100)
            if st.button("🚪 ĐĂNG XUẤT"): st.session_state.clear(); st.rerun()
        render_home()
    elif st.session_state["page"] == "activity":
        render_activity()

if __name__ == "__main__": main()