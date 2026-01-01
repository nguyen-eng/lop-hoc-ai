import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
import time
from datetime import datetime
import threading
import numpy as np
import sqlite3
import random
from io import BytesIO
try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st.error("Thiếu thư viện. Vui lòng chạy: pip install streamlit-autorefresh")
    st_autorefresh = None

# ==========================================
# 1. CẤU HÌNH & GIAO DIỆN (UI/UX)
# ==========================================
st.set_page_config(
    page_title="T05 Interactive Class",
    page_icon="📶",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- TÀI NGUYÊN ---
LOGO_URL = "https://drive.google.com/thumbnail?id=1PsUr01oeleJkW2JB1gqnID9WJNsTMFGW&sz=w1000"
MAP_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/Blank_map_of_Vietnam.svg/858px-Blank_map_of_Vietnam.svg.png"

PRIMARY_COLOR = "#006a4e"
BG_COLOR = "#f0f2f5"
TEXT_COLOR = "#111827"
MUTED = "#64748b"

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Montserrat', sans-serif;
        background-color: {BG_COLOR};
        color: {TEXT_COLOR};
    }}

    header {{visibility: hidden;}} footer {{visibility: hidden;}}

    /* HERO / LOGIN */
    .hero-wrap {{
        max-width: 980px;
        margin: 0 auto;
        padding: 28px 10px 10px 10px;
    }}
    .hero-card {{
        background: white;
        border-radius: 22px;
        box-shadow: 0 18px 55px rgba(0,0,0,0.10);
        overflow: hidden;
        border: 1px solid #e2e8f0;
    }}
    .hero-top {{
        background: linear-gradient(135deg, rgba(0,106,78,0.12), rgba(0,106,78,0.03));
        padding: 26px 26px 18px 26px;
        border-bottom: 1px solid #e2e8f0;
        display:flex;
        gap:18px;
        align-items:center;
    }}
    .hero-badge {{
        width: 78px; height: 78px;
        border-radius: 18px;
        background: white;
        border: 1px solid #e2e8f0;
        display:flex;
        align-items:center;
        justify-content:center;
        box-shadow: 0 8px 25px rgba(0,0,0,0.06);
        flex: 0 0 auto;
    }}
    .hero-title {{
        font-weight: 800;
        color: {PRIMARY_COLOR};
        font-size: 26px;
        line-height: 1.2;
        margin: 0;
        word-break: break-word;
    }}
    .hero-sub {{
        color: {MUTED};
        font-weight: 600;
        margin-top: 6px;
        margin-bottom: 0;
    }}
    .hero-body {{
        padding: 18px 26px 22px 26px;
    }}
    .hero-meta {{
        background:#f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 14px 14px;
        color:#334155;
        font-size: 14px;
        margin-bottom: 12px;
    }}

    /* VIZ CARD */
    .viz-card {{
        background: white; padding: 25px; border-radius: 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        margin-bottom: 20px; border: 1px solid #e2e8f0;
    }}

    /* INPUT */
    .stTextInput input, .stTextArea textarea {{
        border: 2px solid #e2e8f0; border-radius: 12px; padding: 12px;
    }}

    /* BUTTONS */
    div.stButton > button {{
        background-color: {PRIMARY_COLOR}; color: white; border: none;
        border-radius: 14px; padding: 12px 18px; font-weight: 800;
        letter-spacing: 0.5px; width: 100%;
        box-shadow: 0 6px 18px rgba(0, 106, 78, 0.22);
    }}
    div.stButton > button:hover {{ background-color: #00503a; transform: translateY(-1px); }}

    /* NOTE CARD */
    .note-card {{
        background: #fff; padding: 15px; border-radius: 12px;
        border-left: 5px solid {PRIMARY_COLOR}; margin-bottom: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08); font-size: 15px;
    }}

    /* SIDEBAR */
    [data-testid="stSidebar"] {{ background-color: #111827; }}
    [data-testid="stSidebar"] * {{ color: #ffffff; }}

    /* CLASS HOME (Gradescope-ish list) */
    .list-wrap {{
        background: transparent;
        max-width: 1080px;
        margin: 0 auto;
    }}
    .list-header {{
        display:flex;
        align-items:flex-end;
        justify-content:space-between;
        gap:12px;
        margin: 6px 0 12px 0;
    }}
    .list-title {{
        font-size: 26px;
        font-weight: 900;
        color: #0f172a;
        margin: 0;
    }}
    .list-sub {{
        margin: 6px 0 0 0;
        color: {MUTED};
        font-weight: 600;
        font-size: 14px;
    }}
    .act-row {{
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 16px 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.06);
        margin-bottom: 12px;
    }}
    .act-name {{
        font-weight: 900;
        font-size: 16px;
        margin: 0 0 4px 0;
        color: #0f172a;
    }}
    .act-meta {{
        margin: 0;
        color: {MUTED};
        font-weight: 600;
        font-size: 13px;
    }}
</style>
""", unsafe_allow_html=True)

# --- KẾT NỐI AI ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
except:
    model = None

# ==========================================
# 2. XỬ LÝ DỮ LIỆU (BACKEND - SQLITE)
# ==========================================
CLASSES = {f"Lớp học {i}": f"lop{i}" for i in range(1, 11)}

PASSWORDS = {}
for i in range(1, 9):
    PASSWORDS[f"lop{i}"] = f"T05-{i}"
for i in range(9, 11):
    PASSWORDS[f"lop{i}"] = f"LH{i}"

# ---- INIT DB ----
def init_db():
    conn = sqlite3.connect('class_data.db', check_same_thread=False)
    c = conn.cursor()
    # Tạo bảng nếu chưa có
    c.execute('''CREATE TABLE IF NOT EXISTS responses 
                 (class_id TEXT, activity TEXT, student TEXT, content TEXT, timestamp TEXT)''')
    conn.commit()
    return conn

conn = init_db()
db_lock = threading.Lock()

# ---- SESSION STATE ----
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "role": "", "class_id": ""})

if "page" not in st.session_state:
    st.session_state["page"] = "login"

if "current_act_key" not in st.session_state:
    st.session_state["current_act_key"] = "dashboard"

# ---- DB FUNCTIONS ----
def save_data(cls, act, name, content):
    timestamp = datetime.now().strftime("%H:%M:%S")
    with db_lock:
        c = conn.cursor()
        c.execute("INSERT INTO responses VALUES (?, ?, ?, ?, ?)", (cls, act, name, str(content), timestamp))
        conn.commit()

def load_data(cls, act):
    # Không dùng lock khi đọc để tăng tốc độ
    c = conn.cursor()
    c.execute("SELECT student, content, timestamp FROM responses WHERE class_id=? AND activity=?", (cls, act))
    data = c.fetchall()
    return pd.DataFrame(data, columns=["Học viên", "Nội dung", "Thời gian"])

def clear_activity(cls, act):
    with db_lock:
        c = conn.cursor()
        c.execute("DELETE FROM responses WHERE class_id=? AND activity=?", (cls, act))
        conn.commit()

def reset_to_login():
    st.session_state.clear()
    st.rerun()

# ==========================================
# 3. CẤU HÌNH HOẠT ĐỘNG
# ==========================================
def class_topic(cid: str) -> str:
    if cid in ["lop1", "lop2"]: return "Cặp phạm trù Nguyên nhân – Kết quả"
    if cid in ["lop3", "lop4"]: return "Quy luật Phủ định của phủ định"
    if cid in ["lop5", "lop6"]: return "Triết học về con người: tha hóa & giải phóng"
    if cid in ["lop7", "lop8"]: return "Triết học về con người: cá nhân – xã hội"
    return "Triết học Mác-xít (tổng quan)"

CLASS_ACT_CONFIG = {}
for i in range(1, 11):
    cid = f"lop{i}"
    topic = class_topic(cid)
    
    # (Giữ nguyên cấu hình câu hỏi của Thầy)
    if cid in ["lop1", "lop2"]:
        wc_q = "Nêu 1 từ khóa để phân biệt *nguyên nhân* với *nguyên cớ*."
        poll_q = "Trong tình huống va quẹt xe rồi phát sinh đánh nhau, 'va quẹt xe' là gì?"
        poll_opts = ["Nguyên nhân trực tiếp", "Nguyên cớ", "Kết quả", "Điều kiện đủ"]
        poll_correct = "Nguyên cớ"
        open_q = "Phân biệt *nguyên nhân – nguyên cớ – điều kiện* trong một vụ án giả định."
        criteria = ["Nhận diện nguyên nhân", "Nhận diện nguyên cớ", "Nhận diện điều kiện", "Lập luận logic"]
        rank_items = ["Thu thập dấu vết", "Xác minh chuỗi nhân quả", "Loại bỏ 'nguyên cớ'", "Kiểm tra điều kiện"]
        pin_q = "Ghim 'điểm nóng' nơi dễ phát sinh nguyên cớ (kích động, tin đồn...)."
    elif cid in ["lop3", "lop4"]:
        wc_q = "1 từ khóa mô tả 'tính kế thừa' trong phủ định biện chứng?"
        poll_q = "Điểm phân biệt cốt lõi giữa 'phủ định biện chứng' và 'phủ định siêu hình'?"
        poll_opts = ["Có tính kế thừa", "Phủ định sạch trơn", "Ngẫu nhiên", "Không dựa mâu thuẫn"]
        poll_correct = "Có tính kế thừa"
        open_q = "Ví dụ thực tiễn về phát triển theo 'đường xoáy ốc'."
        criteria = ["Đúng 2 lần phủ định", "Yếu tố kế thừa", "Yếu tố vượt bỏ", "Liên hệ thực tiễn"]
        rank_items = ["Xác định cái cũ", "Giữ lại cái hợp lý", "Tạo cơ chế tự phủ định", "Ổn định cái mới"]
        pin_q = "Ghim vị trí 'điểm bẻ gãy' khi mâu thuẫn chín muồi."
    # ... (Các lớp khác giữ mặc định logic như cũ để gọn code)
    else:
        wc_q = "1 từ khóa mô tả 'hạt nhân' của phép biện chứng?"
        poll_q = "Vấn đề cơ bản của triết học là gì?"
        poll_opts = ["Vật chất – ý thức", "Riêng – chung", "Lượng – chất", "Hình thức – nội dung"]
        poll_correct = "Vật chất – ý thức"
        open_q = "Vì sao cán bộ cần lập trường duy vật biện chứng khi xử lý chứng cứ?"
        criteria = ["Tính khách quan", "Lập luận", "Liên hệ nghề nghiệp", "Diễn đạt"]
        rank_items = ["Tôn trọng khách quan", "Chứng cứ vật chất", "Phân tích mâu thuẫn", "Kiểm chứng"]
        pin_q = "Ghim nơi phát sinh sai lệch nhận thức trong quy trình."

    CLASS_ACT_CONFIG[cid] = {
        "topic": topic,
        "wordcloud": {"name": "Word Cloud: Từ khóa", "type": "Word Cloud", "question": wc_q},
        "poll": {"name": "Poll: Trắc nghiệm", "type": "Poll", "question": poll_q, "options": poll_opts, "correct": poll_correct},
        "openended": {"name": "Open Ended: Trả lời mở", "type": "Open Ended", "question": open_q},
        "scales": {"name": "Scales: Đánh giá", "type": "Scales", "question": "Tự đánh giá theo tiêu chí.", "criteria": criteria},
        "ranking": {"name": "Ranking: Xếp hạng", "type": "Ranking", "question": "Sắp xếp thứ tự ưu tiên.", "items": rank_items},
        "pin": {"name": "Pin: Ghim ảnh", "type": "Pin", "question": pin_q, "image": MAP_IMAGE},
    }

# ==========================================
# 4. LOGIN
# ==========================================
if (not st.session_state.get("logged_in", False)) or (st.session_state.get("page", "login") == "login"):
    st.session_state["page"] = "login"
    st.markdown("<div class='hero-wrap'>", unsafe_allow_html=True)
    st.markdown(f"""
        <div class="hero-card">
            <div class="hero-top">
                <div class="hero-badge"><img src="{LOGO_URL}" style="width:60px; height:60px; object-fit:contain;" /></div>
                <div>
                    <p class="hero-title">TRƯỜNG ĐẠI HỌC CẢNH SÁT NHÂN DÂN</p>
                    <p class="hero-sub">Hệ thống tương tác lớp học (v2.0)</p>
                </div>
            </div>
            <div class="hero-body">
                <div class="hero-meta"><b>Khoa:</b> LLCT & KHXHNV<br><b>Giảng viên:</b> Trần Nguyễn Sĩ Nguyên</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    tab_sv, tab_gv = st.tabs(["CỔNG HỌC VIÊN", "CỔNG GIẢNG VIÊN"])
    with tab_sv:
        c_class = st.selectbox("Chọn lớp", list(CLASSES.keys()))
        c_pass = st.text_input("Mã lớp", type="password")
        if st.button("THAM GIA LỚP HỌC", key="btn_join"):
            cid = CLASSES[c_class]
            if c_pass.strip() == PASSWORDS[cid]:
                st.session_state.update({"logged_in": True, "role": "student", "class_id": cid, "page": "class_home"})
                st.rerun()
            else:
                st.error("Sai mã lớp!")

    with tab_gv:
        t_pass = st.text_input("Mật khẩu Admin", type="password")
        if st.button("VÀO QUẢN TRỊ", key="btn_admin"):
            if t_pass == "T05":
                st.session_state.update({"logged_in": True, "role": "teacher", "class_id": "lop1", "page": "class_home"})
                st.rerun()
            else:
                st.error("Sai mật khẩu.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ==========================================
# 5. SIDEBAR (CÓ CÔNG CỤ GV)
# ==========================================
with st.sidebar:
    st.image(LOGO_URL, width=80)
    st.markdown("---")
    
    cls_txt = [k for k, v in CLASSES.items() if v == st.session_state["class_id"]][0]
    role = "HỌC VIÊN" if st.session_state["role"] == "student" else "GIẢNG VIÊN"
    st.info(f"👤 {role}\n\n🏫 {cls_txt}")

    if st.session_state["role"] == "teacher":
        st.warning("CHUYỂN LỚP QUẢN LÝ")
        s_cls = st.selectbox("", list(CLASSES.keys()), label_visibility="collapsed")
        st.session_state["class_id"] = CLASSES[s_cls]
        
        # --- CÔNG CỤ GV (MỚI) ---
        st.markdown("---")
        st.header("⏱️ Công cụ lớp")
        
        # 1. Timer
        with st.expander("Đồng hồ đếm ngược"):
            t_min = st.number_input("Phút", 0, 60, 2)
            if st.button("Bắt đầu đếm"):
                t_ph = st.empty()
                for i in range(t_min * 60, -1, -1):
                    m, s = divmod(i, 60)
                    t_ph.markdown(f"<h2 style='text-align:center; color:red'>{m:02d}:{s:02d}</h2>", unsafe_allow_html=True)
                    time.sleep(1)
                st.toast("HẾT GIỜ!", icon="🔔")

        # 2. Random Picker
        with st.expander("Gọi tên ngẫu nhiên"):
            if st.button("🎲 Quay số"):
                # Lấy tất cả học viên đã tương tác trong lớp này
                c = conn.cursor()
                c.execute("SELECT DISTINCT student FROM responses WHERE class_id=?", (st.session_state["class_id"],))
                students = [row[0] for row in c.fetchall()]
                
                if students:
                    lucky = random.choice(students)
                    st.success(f"🎯 Mời đồng chí: **{lucky}**")
                    st.balloons()
                else:
                    st.warning("Chưa có học viên nào nộp bài.")

    st.markdown("---")
    if st.button("📚 Danh mục hoạt động"):
        st.session_state["page"] = "class_home"
        st.rerun()
    if st.button("🏠 Dashboard"):
        st.session_state["page"] = "dashboard"
        st.rerun()
    st.markdown("---")
    if st.button("↩️ Đăng xuất"):
        reset_to_login()

# ==========================================
# 6. TRANG DANH MỤC
# ==========================================
def render_class_home():
    cid = st.session_state["class_id"]
    cfg = CLASS_ACT_CONFIG[cid]
    
    st.markdown("<div class='list-wrap'>", unsafe_allow_html=True)
    st.markdown(f"""
        <div class="list-header">
            <div>
                <p class="list-title">📚 Danh mục hoạt động</p>
                <p class="list-sub">{cfg['topic']}</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    act_order = ["wordcloud", "poll", "openended", "scales", "ranking", "pin"]
    
    for key in act_order:
        a = cfg[key]
        df = load_data(cid, key)
        colL, colR = st.columns([6, 1])
        with colL:
            st.markdown(f"""
                <div class="act-row">
                    <p class="act-name">{a["name"]}</p>
                    <p class="act-meta">{a["type"]} • {len(df)} lượt trả lời</p>
                </div>
            """, unsafe_allow_html=True)
        with colR:
            if st.button("MỞ", key=f"open_{key}"):
                st.session_state["current_act_key"] = key
                st.session_state["page"] = "activity"
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 7. DASHBOARD
# ==========================================
def render_dashboard():
    cid = st.session_state["class_id"]
    st.header("🏠 Dashboard Tổng quan")
    cols = st.columns(3)
    acts = ["wordcloud", "poll", "openended", "scales", "ranking", "pin"]
    
    for i, act in enumerate(acts):
        df = load_data(cid, act)
        with cols[i%3]:
            st.markdown(f"""
            <div class="viz-card" style="text-align:center;">
                <h1 style="color:{PRIMARY_COLOR}; margin:0; font-size:40px;">{len(df)}</h1>
                <p style="color:{MUTED}; font-weight:800; text-transform:uppercase;">{act}</p>
            </div>
            """, unsafe_allow_html=True)

# ==========================================
# 8. TRANG HOẠT ĐỘNG CHI TIẾT
# ==========================================
def render_activity():
    cid = st.session_state["class_id"]
    act = st.session_state.get("current_act_key", "wordcloud")
    cfg = CLASS_ACT_CONFIG[cid][act]

    # --- AUTO REFRESH CHO GV ---
    if st.session_state["role"] == "teacher" and st_autorefresh:
        st_autorefresh(interval=2000, key="data_refresh")

    # Header
    topL, topR = st.columns([1, 5])
    with topL:
        if st.button("↩️ Quay lại"):
            st.session_state["page"] = "class_home"
            st.rerun()
    with topR:
        st.markdown(f"<h2 style='color:{PRIMARY_COLOR}'>{cfg['name']}</h2>", unsafe_allow_html=True)

    # --- NỘI DUNG CHÍNH ---
    c1, c2 = st.columns([1, 2])
    
    # CỘT TRÁI: INPUT / INFO
    with c1:
        st.info(f"**{cfg['question']}**")
        
        if st.session_state["role"] == "student":
            # Form WordCloud
            if act == "wordcloud":
                with st.form("f_wc"):
                    n = st.text_input("Tên")
                    txt = st.text_input("Từ khóa (1 từ/cụm)")
                    if st.form_submit_button("GỬI"):
                        if n and txt: 
                            save_data(cid, act, n, txt)
                            st.success("Đã gửi!"); st.rerun()
            
            # Form Poll
            elif act == "poll":
                with st.form("f_poll"):
                    n = st.text_input("Tên")
                    v = st.radio("Chọn", cfg["options"])
                    if st.form_submit_button("CHỌN"):
                        if n: save_data(cid, act, n, v); st.success("Đã chọn!"); st.rerun()

            # Form OpenEnded
            elif act == "openended":
                with st.form("f_open"):
                    n = st.text_input("Tên")
                    c = st.text_area("Câu trả lời")
                    if st.form_submit_button("GỬI"):
                        if n and c: save_data(cid, act, n, c); st.success("Đã gửi!"); st.rerun()

            # Form Scales
            elif act == "scales":
                with st.form("f_scale"):
                    n = st.text_input("Tên")
                    scores = [st.slider(c,1,5,3) for c in cfg["criteria"]]
                    if st.form_submit_button("GỬI"):
                        if n: save_data(cid, act, n, ",".join(map(str,scores))); st.success("Đã gửi!"); st.rerun()

            # Form Ranking
            elif act == "ranking":
                with st.form("f_rank"):
                    n = st.text_input("Tên")
                    r = st.multiselect("Thứ tự ưu tiên", cfg["items"])
                    if st.form_submit_button("NỘP"):
                        if n and len(r)==len(cfg["items"]): 
                            save_data(cid, act, n, "->".join(r)); st.success("Đã nộp!"); st.rerun()
                        else: st.warning("Chọn đủ các mục.")

            # Form Pin
            elif act == "pin":
                with st.form("f_pin"):
                    n = st.text_input("Tên")
                    x = st.slider("Ngang",0,100,50); y = st.slider("Dọc",0,100,50)
                    if st.form_submit_button("GHIM"):
                        if n: save_data(cid, act, n, f"{x},{y}"); st.success("Đã ghim!"); st.rerun()
        else:
            st.caption("Giảng viên theo dõi kết quả bên phải.")
            if act == "poll": st.caption(f"Đáp án đúng: {cfg['correct']}")

    # CỘT PHẢI: VISUALIZATION
    with c2:
        df = load_data(cid, act)
        st.markdown("##### 📡 KẾT QUẢ TRỰC TUYẾN")
        
        with st.container(border=True):
            if df.empty:
                st.info("Đang chờ dữ liệu từ lớp...")
            else:
                # VIZ: Word Cloud
                if act == "wordcloud":
                    text = " ".join(df["Nội dung"].tolist())
                    if text:
                        wc = WordCloud(width=800, height=400, background_color='white', colormap='ocean').generate(text)
                        plt.figure(figsize=(10,5))
                        plt.imshow(wc, interpolation='bilinear'); plt.axis("off")
                        st.pyplot(plt)
                        st.dataframe(df["Nội dung"].value_counts().head(10), use_container_width=True)

                # VIZ: Poll
                elif act == "poll":
                    cnt = df["Nội dung"].value_counts().reset_index()
                    cnt.columns = ["Lựa chọn", "Số lượng"]
                    fig = px.bar(cnt, x="Lựa chọn", y="Số lượng", text_auto=True, color="Lựa chọn")
                    st.plotly_chart(fig, use_container_width=True)

                # VIZ: Open Ended
                elif act == "openended":
                    for _, r in df.iterrows():
                        st.markdown(f"<div class='note-card'><b>{r['Học viên']}</b>: {r['Nội dung']}</div>", unsafe_allow_html=True)

                # VIZ: Scales
                elif act == "scales":
                    try:
                        mtx = [[int(x) for x in str(i).split(",")] for i in df["Nội dung"]]
                        avg = np.mean(mtx, axis=0)
                        fig = go.Figure(data=go.Scatterpolar(r=avg, theta=cfg["criteria"], fill='toself'))
                        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5])))
                        st.plotly_chart(fig, use_container_width=True)
                    except: st.error("Lỗi dữ liệu")

                # VIZ: Ranking
                elif act == "ranking":
                    sc = {k:0 for k in cfg["items"]}
                    for r in df["Nội dung"]:
                        for i, item in enumerate(str(r).split("->")):
                            sc[item] += (len(cfg["items"]) - i)
                    s_items = sorted(sc.items(), key=lambda x:x[1], reverse=True)
                    fig = px.bar(x=[x[1] for x in s_items], y=[x[0] for x in s_items], orientation='h')
                    st.plotly_chart(fig, use_container_width=True)

                # VIZ: Pin
                elif act == "pin":
                    xs = [int(i.split(",")[0]) for i in df["Nội dung"]]
                    ys = [int(i.split(",")[1]) for i in df["Nội dung"]]
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=xs, y=ys, mode='markers', marker=dict(size=12, color='red')))
                    fig.update_layout(
                        xaxis=dict(range=[0,100], visible=False), yaxis=dict(range=[0,100], visible=False),
                        images=[dict(source=cfg["image"], xref="x", yref="y", x=0, y=100, sizex=100, sizey=100, layer="below")],
                        width=700, height=420, margin=dict(l=0, r=0, t=0, b=0)
                    )
                    st.plotly_chart(fig, use_container_width=True)

    # --- CONTROL PANEL GV ---
    if st.session_state["role"] == "teacher":
        st.markdown("---")
        with st.expander("👮‍♂️ BẢNG ĐIỀU KHIỂN & BÁO CÁO", expanded=True):
            c_ai, c_tool = st.columns([3, 1])
            
            with c_ai:
                st.markdown("###### 🤖 AI Phân tích")
                prompt = st.text_input("Yêu cầu AI", placeholder="Ví dụ: Xu hướng trả lời của lớp là gì?")
                if st.button("PHÂN TÍCH"):
                    if model:
                        with st.spinner("Đang xử lý..."):
                            res = model.generate_content(f"Dữ liệu lớp {cid}, bài {act}: {df.to_string()}\n\nYêu cầu: {prompt}")
                            st.info(res.text)
                    else: st.warning("Chưa có API Key")

            with c_tool:
                st.markdown("###### 🛠️ Công cụ")
                # XUẤT EXCEL
                def to_excel(df):
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                        df.to_excel(writer, index=False, sheet_name='Sheet1')
                    return output.getvalue()
                
                if not df.empty:
                    st.download_button("📥 Xuất Excel", data=to_excel(df), file_name=f"{cid}_{act}.xlsx", mime="application/vnd.ms-excel")
                
                if st.button("🗑 RESET DATA", type="primary"):
                    clear_activity(cid, act)
                    st.rerun()

# ==========================================
# 9. ROUTER
# ==========================================
if page == "class_home": render_class_home()
elif page == "dashboard": render_dashboard()
else: render_activity()
