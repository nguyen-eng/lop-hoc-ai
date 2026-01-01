import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
import time
from datetime import datetime
import threading
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import numpy as np
from collections import Counter
from io import BytesIO

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
# 2. XỬ LÝ DỮ LIỆU (BACKEND)
# ==========================================
data_lock = threading.Lock()
CLASSES = {f"Lớp học {i}": f"lop{i}" for i in range(1, 11)}

PASSWORDS = {}
for i in range(1, 9):
    PASSWORDS[f"lop{i}"] = f"T05-{i}"
for i in range(9, 11):
    PASSWORDS[f"lop{i}"] = f"LH{i}"

# ---- SESSION STATE ----
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "role": "", "class_id": ""})

# page routing: login | class_home | activity | dashboard
if "page" not in st.session_state:
    st.session_state["page"] = "login"

# which activity: wordcloud/poll/openended/scales/ranking/pin
if "current_act_key" not in st.session_state:
    st.session_state["current_act_key"] = "dashboard"

def get_path(cls, act):
    return f"data_{cls}_{act}.csv"

def save_data(cls, act, name, content):
    content = str(content).replace("|", "-").replace("\n", " ")
    timestamp = datetime.now().strftime("%H:%M:%S")
    row = f"{name}|{content}|{timestamp}\n"
    with data_lock:
        with open(get_path(cls, act), "a", encoding="utf-8") as f:
            f.write(row)

def load_data(cls, act):
    path = get_path(cls, act)
    if os.path.exists(path):
        try:
            return pd.read_csv(path, sep="|", names=["Học viên", "Nội dung", "Thời gian"])
        except:
            return pd.DataFrame(columns=["Học viên", "Nội dung", "Thời gian"])
    return pd.DataFrame(columns=["Học viên", "Nội dung", "Thời gian"])

def clear_activity(cls, act):
    with data_lock:
        path = get_path(cls, act)
        if os.path.exists(path):
            os.remove(path)

def reset_to_login():
    st.session_state.clear()
    st.rerun()

# ==========================================
# 3. CẤU HÌNH HOẠT ĐỘNG THEO LỚP (Mentimeter-like)
# ==========================================
def class_topic(cid: str) -> str:
    if cid in ["lop1", "lop2"]:
        return "Cặp phạm trù Nguyên nhân – Kết quả (phân biệt nguyên cớ, điều kiện)"
    if cid in ["lop3", "lop4"]:
        return "Quy luật Phủ định của phủ định"
    if cid in ["lop5", "lop6"]:
        return "Triết học về con người: quan niệm – bản chất; tha hóa lao động; giải phóng con người"
    if cid in ["lop7", "lop8"]:
        return "Triết học về con người: cá nhân – xã hội; vấn đề con người trong Việt Nam"
    return "Triết học Mác-xít (tổng quan các vấn đề cơ bản)"

CLASS_ACT_CONFIG = {}
for i in range(1, 11):
    cid = f"lop{i}"
    topic = class_topic(cid)

    if cid in ["lop1", "lop2"]:
        wc_q = "Nêu 1 từ khóa để phân biệt *nguyên nhân* với *nguyên cớ*."
        poll_q = "Trong tình huống va quẹt xe rồi phát sinh đánh nhau, 'va quẹt xe' là gì?"
        poll_opts = ["Nguyên nhân trực tiếp", "Nguyên cớ", "Kết quả", "Điều kiện đủ"]
        poll_correct = "Nguyên cớ"
        open_q = "Hãy viết 3–5 câu: phân biệt *nguyên nhân – nguyên cớ – điều kiện* trong một vụ án giả định (tự chọn)."
        criteria = ["Nhận diện nguyên nhân", "Nhận diện nguyên cớ", "Nhận diện điều kiện", "Lập luận logic"]
        rank_items = ["Thu thập dấu vết vật chất", "Xác minh chuỗi nguyên nhân", "Loại bỏ 'nguyên cớ' ngụy biện", "Kiểm tra điều kiện cần/đủ"]
        pin_q = "Ghim 'điểm nóng' nơi dễ phát sinh nguyên cớ (kích động, tin đồn...) trong một sơ đồ lớp/bản đồ."
    elif cid in ["lop3", "lop4"]:
        wc_q = "1 từ khóa mô tả đúng nhất 'tính kế thừa' trong phủ định biện chứng?"
        poll_q = "Điểm phân biệt cốt lõi giữa 'phủ định biện chứng' và 'phủ định siêu hình' là gì?"
        poll_opts = ["Có tính kế thừa", "Phủ định sạch trơn", "Ngẫu nhiên thuần túy", "Không dựa mâu thuẫn nội tại"]
        poll_correct = "Có tính kế thừa"
        open_q = "Nêu 1 ví dụ trong công tác/đời sống thể hiện phát triển theo 'đường xoáy ốc' (tối thiểu 5 câu)."
        criteria = ["Nêu đúng 2 lần phủ định", "Chỉ ra yếu tố kế thừa", "Chỉ ra yếu tố vượt bỏ", "Kết nối thực tiễn"]
        rank_items = ["Xác định cái cũ cần vượt bỏ", "Giữ lại yếu tố hợp lý", "Tạo cơ chế tự phủ định", "Ổn định cái mới thành cái 'đang là'"]
        pin_q = "Ghim vị trí trên sơ đồ để minh họa 'điểm bẻ gãy' khi mâu thuẫn chín muồi dẫn tới phủ định."
    elif cid in ["lop5", "lop6"]:
        wc_q = "1 từ khóa mô tả 'bản chất con người' trong quan điểm Mác?"
        poll_q = "Theo Mác, bản chất con người trước hết là gì?"
        poll_opts = ["Tổng hòa các quan hệ xã hội", "Bản năng sinh học cố định", "Tinh thần thuần túy", "Ý chí cá nhân đơn lẻ"]
        poll_correct = "Tổng hòa các quan hệ xã hội"
        open_q = "Mô tả một biểu hiện 'tha hóa' trong lao động (5–7 câu) và gợi ý 1 hướng 'giải phóng'."
        criteria = ["Nêu đúng biểu hiện tha hóa", "Chỉ ra nguyên nhân xã hội", "Nêu hướng khắc phục", "Tính thực tiễn"]
        rank_items = ["Cải thiện điều kiện lao động", "Dân chủ hóa tổ chức", "Phát triển năng lực người lao động", "Phân phối công bằng thành quả"]
        pin_q = "Ghim nơi thể hiện mâu thuẫn giữa 'con người' và 'cơ chế' gây tha hóa (tượng trưng)."
    elif cid in ["lop7", "lop8"]:
        wc_q = "1 từ khóa mô tả quan hệ *cá nhân – xã hội* theo cách nhìn biện chứng?"
        poll_q = "Khẳng định nào đúng nhất về quan hệ cá nhân – xã hội?"
        poll_opts = ["Cá nhân và xã hội quy định lẫn nhau", "Xã hội chỉ là tổng số cá nhân", "Cá nhân quyết định tuyệt đối", "Xã hội quyết định tuyệt đối"]
        poll_correct = "Cá nhân và xã hội quy định lẫn nhau"
        open_q = "Nêu 1 vấn đề con người ở Việt Nam hiện nay (giá trị, lối sống, kỷ luật, trách nhiệm...) và phân tích theo 2 chiều: cá nhân – xã hội."
        criteria = ["Nêu vấn đề đúng trọng tâm", "Phân tích chiều cá nhân", "Phân tích chiều xã hội", "Đề xuất giải pháp"]
        rank_items = ["Giáo dục đạo đức – pháp luật", "Môi trường xã hội lành mạnh", "Cơ chế khuyến khích cái tốt", "Xử lý lệch chuẩn công bằng"]
        pin_q = "Ghim vị trí 'điểm nghẽn' giữa cá nhân – tổ chức – xã hội (tượng trưng)."
    else:
        wc_q = "1 từ khóa mô tả 'hạt nhân' của phép biện chứng duy vật?"
        poll_q = "Trong triết học Mác – Lênin, vấn đề cơ bản của triết học là gì?"
        poll_opts = ["Quan hệ vật chất – ý thức", "Quan hệ cái riêng – cái chung", "Quan hệ lượng – chất", "Quan hệ hình thức – nội dung"]
        poll_correct = "Quan hệ vật chất – ý thức"
        open_q = "Viết 5–7 câu: Vì sao người cán bộ (nhất là ĐTV) cần lập trường duy vật biện chứng khi xử lý chứng cứ?"
        criteria = ["Nêu đúng nguyên tắc", "Lập luận chặt chẽ", "Liên hệ nghề nghiệp", "Diễn đạt rõ ràng"]
        rank_items = ["Tôn trọng khách quan", "Chứng cứ vật chất", "Phân tích mâu thuẫn", "Kết luận có thể kiểm chứng"]
        pin_q = "Ghim vị trí 'nơi phát sinh sai lệch nhận thức' trong quy trình xử lý thông tin (tượng trưng)."

    CLASS_ACT_CONFIG[cid] = {
        "topic": topic,
        "wordcloud": {"name": "Word Cloud: Từ khóa phân biệt", "type": "Từ khóa / Word Cloud", "question": wc_q},
        "poll": {"name": "Poll: Chọn đúng bản chất", "type": "Bình chọn / Poll", "question": poll_q, "options": poll_opts, "correct": poll_correct},
        "openended": {"name": "Open Ended: Tình huống – lập luận", "type": "Trả lời mở / Open Ended", "question": open_q},
        "scales": {"name": "Scales: Tự đánh giá năng lực", "type": "Thang đo / Scales", "question": "Tự đánh giá theo các tiêu chí (1: thấp – 5: cao).", "criteria": criteria},
        "ranking": {"name": "Ranking: Ưu tiên thao tác", "type": "Xếp hạng / Ranking", "question": "Sắp xếp thứ tự ưu tiên (quan trọng nhất lên đầu).", "items": rank_items},
        "pin": {"name": "Pin: Điểm nóng tình huống", "type": "Ghim trên ảnh / Pin", "question": pin_q, "image": MAP_IMAGE},
    }

# ==========================================
# 4. MÀN HÌNH ĐĂNG NHẬP (PRO)
# ==========================================
if (not st.session_state.get("logged_in", False)) or (st.session_state.get("page", "login") == "login"):
    st.session_state["page"] = "login"

    st.markdown("<div class='hero-wrap'>", unsafe_allow_html=True)
    st.markdown("""
        <div class="hero-card">
            <div class="hero-top">
                <div class="hero-badge">
                    <img src="{logo}" style="width:60px; height:60px; object-fit:contain;" />
                </div>
                <div>
                    <p class="hero-title">TRƯỜNG ĐẠI HỌC CẢNH SÁT NHÂN DÂN</p>
                    <p class="hero-sub">Hệ thống tương tác lớp học (Mentimeter-style)</p>
                </div>
            </div>
            <div class="hero-body">
                <div class="hero-meta">
                    <b>Khoa:</b> LLCT &amp; KHXHNV<br>
                    <b>Giảng viên:</b> Trần Nguyễn Sĩ Nguyên
                </div>
            </div>
        </div>
    """.format(logo=LOGO_URL), unsafe_allow_html=True)

    st.write("")
    tab_sv, tab_gv = st.tabs(["CỔNG HỌC VIÊN", "CỔNG GIẢNG VIÊN"])

    with tab_sv:
        c_class = st.selectbox("Chọn lớp", list(CLASSES.keys()))
        c_pass = st.text_input("Mã lớp", type="password")  # ✅ bỏ placeholder để không lộ gợi ý
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
# 5. SIDEBAR + NAV
# ==========================================
with st.sidebar:
    st.image(LOGO_URL, width=80)
    st.markdown("---")
    st.caption("🎵 NHẠC NỀN")
    st.audio("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3")

    cls_txt = [k for k, v in CLASSES.items() if v == st.session_state["class_id"]][0]
    role = "HỌC VIÊN" if st.session_state["role"] == "student" else "GIẢNG VIÊN"
    st.info(f"👤 {role}\n\n🏫 {cls_txt}")

    if st.session_state["role"] == "teacher":
        st.warning("CHUYỂN LỚP QUẢN LÝ")
        s_cls = st.selectbox("", list(CLASSES.keys()), label_visibility="collapsed")
        st.session_state["class_id"] = CLASSES[s_cls]

    st.markdown("---")
    if st.button("📚 Danh mục hoạt động", key="nav_class_home"):
        st.session_state["page"] = "class_home"
        st.rerun()

    if st.button("🏠 Dashboard", key="nav_dashboard"):
        st.session_state["page"] = "dashboard"
        st.rerun()

    st.markdown("---")
    if st.button("↩️ Quay lại đăng nhập", key="nav_logout"):
        reset_to_login()

# ==========================================
# 6. TRANG "DANH MỤC HOẠT ĐỘNG CỦA LỚP"
# ==========================================
def render_class_home():
    cid = st.session_state["class_id"]
    cfg = CLASS_ACT_CONFIG[cid]
    topic = cfg["topic"]
    cls_txt = [k for k, v in CLASSES.items() if v == cid][0]

    st.markdown("<div class='list-wrap'>", unsafe_allow_html=True)
    st.markdown(f"""
        <div class="list-header">
            <div>
                <p class="list-title">📚 Danh mục hoạt động của lớp</p>
                <p class="list-sub"><b>{cls_txt}</b> • Chủ đề: {topic}</p>
            </div>
        </div>
    """, unsafe_allow_html=True)

    c_back, c_space = st.columns([1, 5])
    with c_back:
        if st.button("↩️ Đăng xuất", key="btn_logout_top"):
            reset_to_login()
    with c_space:
        st.caption("Chọn một hoạt động để vào làm bài / xem kết quả (GV có thêm phân tích AI & reset).")

    def open_activity(act_key: str):
        st.session_state["current_act_key"] = act_key
        st.session_state["page"] = "activity"
        st.rerun()

    act_order = [
        ("wordcloud", "wordcloud_row"),
        ("poll", "poll_row"),
        ("openended", "openended_row"),
        ("scales", "scales_row"),
        ("ranking", "ranking_row"),
        ("pin", "pin_row"),
    ]

    for act_key, ksuffix in act_order:
        a = cfg[act_key]
        df = load_data(cid, act_key)
        count = len(df)

        colL, colR = st.columns([6, 1])
        with colL:
            st.markdown(f"""
                <div class="act-row">
                    <p class="act-name">{a["name"]}</p>
                    <p class="act-meta">Loại hoạt động: {a["type"]} • Số lượt trả lời: <b>{count}</b></p>
                </div>
            """, unsafe_allow_html=True)
        with colR:
            if st.button("MỞ", key=f"open_{ksuffix}"):
                open_activity(act_key)

    st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# 7. DASHBOARD
# ==========================================
def render_dashboard():
    cid = st.session_state["class_id"]
    topic = CLASS_ACT_CONFIG[cid]["topic"]
    st.markdown(
        f"<h2 style='color:{PRIMARY_COLOR}; border-bottom:2px solid #e2e8f0; padding-bottom:10px;'>🏠 Dashboard</h2>",
        unsafe_allow_html=True
    )
    st.caption(f"Chủ đề lớp: {topic}")

    cols = st.columns(3)
    activities = ["wordcloud", "poll", "openended", "scales", "ranking", "pin"]
    names = ["WORD CLOUD", "POLL", "OPEN ENDED", "SCALES", "RANKING", "PIN IMAGE"]

    for i, act in enumerate(activities):
        df = load_data(cid, act)
        with cols[i % 3]:
            st.markdown(f"""
            <div class="viz-card" style="text-align:center;">
                <h1 style="color:{PRIMARY_COLOR}; margin:0; font-size:40px;">{len(df)}</h1>
                <p style="color:{MUTED}; font-weight:800; text-transform:uppercase;">{names[i]}</p>
            </div>
            """, unsafe_allow_html=True)

    st.caption("Gợi ý: dùng sidebar → “Danh mục hoạt động” để mở hoạt động như Mentimeter.")

# ==========================================
# 8. TRANG HOẠT ĐỘNG
# ==========================================
def render_activity():
    cid = st.session_state["class_id"]
    act = st.session_state.get("current_act_key", "wordcloud")
    cfg = CLASS_ACT_CONFIG[cid][act]

    topL, topR = st.columns([1, 5])
    with topL:
        if st.button("↩️ Về danh mục lớp", key="btn_back_class_home"):
            st.session_state["page"] = "class_home"
            st.rerun()
    with topR:
        st.markdown(
            f"<h2 style='color:{PRIMARY_COLOR}; border-bottom:2px solid #e2e8f0; padding-bottom:10px;'>{cfg['name']}</h2>",
            unsafe_allow_html=True
        )

    current_act_key = act

    # ------------------------------------------
    # 1) WORD CLOUD (GIỮ NGUYÊN CỤM TỪ)
    # ------------------------------------------
    if act == "wordcloud":
        c1, c2 = st.columns([1, 2])
        with c1:
            st.info(f"Câu hỏi: **{cfg['question']}**")
            if st.session_state["role"] == "student":
                with st.form("f_wc"):
                    n = st.text_input("Tên")
                    txt = st.text_input("Nhập 1 từ khóa / cụm từ (giữ nguyên, có thể có khoảng trắng)")
                    if st.form_submit_button("GỬI"):
                        if n.strip() and txt.strip():
                            save_data(cid, current_act_key, n, txt)
                            st.success("Đã gửi!")
                            time.sleep(0.2)
                            st.rerun()
                        else:
                            st.warning("Vui lòng nhập đủ Tên và Từ khóa.")
            else:
                st.warning("Giảng viên xem kết quả bên phải.")
        with c2:
            st.markdown("##### ☁️ KẾT QUẢ")
            df = load_data(cid, current_act_key)
            with st.container(border=True):
                if not df.empty:
                    # =========================
                    # Mentimeter-like WordCloud (tự layout)
                    # - SIZE theo TẦN SUẤT (đúng logic Mentimeter)
                    # - cùng tần suất => cùng font size
                    # - ưu tiên ngang, màu tươi, nền trắng
                    # - render PIL để nét trên Streamlit Cloud
                    # =========================
                    from PIL import Image, ImageDraw, ImageFont
                    import math
                    import random
                    from pathlib import Path

                    # 1) Chuẩn hoá: giữ nguyên CỤM TỪ (không tách)
                    phrases = (
                        df["Nội dung"]
                        .astype(str)
                        .map(lambda x: " ".join(x.strip().split()))  # gom nhiều space
                        .tolist()
                    )
                    # lọc rỗng
                    phrases = [p for p in phrases if p]

                    # (khuyến nghị) chuẩn hoá nhẹ để tránh "trước sau" vs "trước  sau"
                    # bạn có thể bổ sung .lower() nếu muốn gộp hoa/thường:
                    # phrases = [p.lower() for p in phrases]

                    freq = Counter(phrases)  # tần suất theo đúng cụm từ

                    # 2) Font: ưu tiên Montserrat nếu có (Streamlit Cloud: fallback DejaVu)
                    def pick_font():
                        # nếu bạn có font trong repo: assets/fonts/Montserrat-SemiBold.ttf
                        cand = Path("assets/fonts/Montserrat-SemiBold.ttf")
                        if cand.exists():
                            return str(cand)

                        # fallback DejaVu (thường có sẵn)
                        try:
                            import matplotlib
                            dejavu = Path(matplotlib.get_data_path()) / "fonts/ttf/DejaVuSans.ttf"
                            if dejavu.exists():
                                return str(dejavu)
                        except:
                            pass

                        # fallback cuối: None (PIL load mặc định)
                        return None

                    font_path = pick_font()

                    # 3) Palette kiểu Mentimeter (tươi + sạch)
                    menti_palette = [
                        "#00BFA5",  # teal
                        "#2E7DFF",  # blue
                        "#7C4DFF",  # purple
                        "#FF4D8D",  # pink
                        "#FFB300",  # amber
                        "#00C853",  # green
                        "#FF6D00",  # orange
                    ]

                    # 4) Hàm map frequency -> font size (đúng tinh thần Mentimeter)
                    #    - dùng sqrt/log để tần suất nổi bật rõ nhưng không "nổ" quá
                    def size_map(count, c_min, c_max, s_min=22, s_max=140):
                        if c_max == c_min:
                            return int((s_min + s_max) / 2)
                        # sqrt scaling: nổi bật tốt hơn tuyến tính, ổn định hơn log khi dữ liệu ít
                        x = (math.sqrt(count) - math.sqrt(c_min)) / (math.sqrt(c_max) - math.sqrt(c_min))
                        return int(s_min + x * (s_max - s_min))

                    # 5) Tự layout (không dùng WordCloud.fit_words) để:
                    #    - cùng tần suất => cùng size
                    #    - tránh chuyện "1 người nhập nhưng chữ to nhỏ khác nhau" do thuật toán fit
                    W, H = 1200, 650
                    img = Image.new("RGBA", (W, H), (255, 255, 255, 255))
                    draw = ImageDraw.Draw(img)

                    # sắp xếp: freq giảm dần, cùng freq ưu tiên cụm ngắn trước (dễ đặt)
                    items = sorted(freq.items(), key=lambda x: (-x[1], len(x[0])))

                    counts = [c for _, c in items]
                    c_min, c_max = min(counts), max(counts)

                    # để kiểm tra overlap bằng rectangles
                    placed_rects = []

                    # spiral placement từ tâm ra ngoài (Mentimeter-ish)
                    center_x, center_y = W // 2, H // 2
                    max_tries_per_word = 1400

                    # deterministic để không nhảy layout mỗi rerun (Mentimeter cũng “ổn định”)
                    rng = random.Random(42)

                    def stable_color(word: str) -> str:
                        idx = abs(hash(word)) % len(menti_palette)
                        return menti_palette[idx]

                    def rects_intersect(r1, r2):
                        return not (r1[2] <= r2[0] or r1[0] >= r2[2] or r1[3] <= r2[1] or r1[1] >= r2[3])

                    def can_place(rect):
                        # trong khung + không đè lên chữ khác
                        if rect[0] < 18 or rect[1] < 18 or rect[2] > W - 18 or rect[3] > H - 18:
                            return False
                        for r in placed_rects:
                            if rects_intersect(rect, r):
                                return False
                        return True

                    for word, count in items:
                        base_size = size_map(count, c_min, c_max, s_min=22, s_max=140)

                        # nếu cụm quá dài, shrink để fit theo bề ngang (giữ logic Mentimeter: dài thì nhỏ hơn chút)
                        # vẫn đảm bảo: tần suất cao -> base_size cao hơn rõ rệt
                        size = base_size

                        # load font
                        def load_font(sz):
                            if font_path:
                                return ImageFont.truetype(font_path, sz)
                            return ImageFont.load_default()

                        font = load_font(size)

                        # đo bbox
                        bbox = draw.textbbox((0, 0), word, font=font)
                        text_w = bbox[2] - bbox[0]
                        text_h = bbox[3] - bbox[1]

                        # shrink nếu quá rộng (để tránh “bị ép” làm méo logic)
                        max_w = int(W * 0.86)
                        if text_w > max_w:
                            scale = max_w / max(1, text_w)
                            size = max(18, int(size * scale))
                            font = load_font(size)
                            bbox = draw.textbbox((0, 0), word, font=font)
                            text_w = bbox[2] - bbox[0]
                            text_h = bbox[3] - bbox[1]

                        placed = False
                        # spiral params
                        a = 4.2
                        b = 4.2
                        angle = rng.random() * 2 * math.pi

                        for t in range(max_tries_per_word):
                            # spiral radius grows
                            r = a + b * (t / 35.0)
                            x = int(center_x + r * math.cos(angle + t * 0.35) - text_w / 2)
                            y = int(center_y + r * math.sin(angle + t * 0.35) - text_h / 2)

                            rect = (x, y, x + text_w, y + text_h)
                            if can_place(rect):
                                # shadow nhẹ (Mentimeter “clean” nhưng có độ tách)
                                shadow = (0, 0, 0, 28)
                                draw.text((x + 2, y + 2), word, font=font, fill=shadow)

                                draw.text((x, y), word, font=font, fill=stable_color(word))
                                placed_rects.append(rect)
                                placed = True
                                break

                        # nếu không place được, giảm nhẹ size và thử lại 1 vòng nhanh
                        if not placed and size > 18:
                            size2 = max(18, int(size * 0.86))
                            font2 = load_font(size2)
                            bbox2 = draw.textbbox((0, 0), word, font=font2)
                            tw2 = bbox2[2] - bbox2[0]
                            th2 = bbox2[3] - bbox2[1]

                            for t in range(900):
                                r = a + b * (t / 35.0)
                                x = int(center_x + r * math.cos(angle + t * 0.35) - tw2 / 2)
                                y = int(center_y + r * math.sin(angle + t * 0.35) - th2 / 2)
                                rect = (x, y, x + tw2, y + th2)
                                if can_place(rect):
                                    draw.text((x + 2, y + 2), word, font=font2, fill=(0, 0, 0, 24))
                                    draw.text((x, y), word, font=font2, fill=stable_color(word))
                                    placed_rects.append(rect)
                                    break

                    # xuất PNG nét
                    out = Image.new("RGB", (W, H), (255, 255, 255))
                    out.paste(img, mask=img.split()[3])

                    buf = BytesIO()
                    out.save(buf, format="PNG", optimize=True)
                    st.image(buf.getvalue(), use_container_width=True)

                    # hiển thị thêm thống kê nhỏ (Mentimeter có counter)
                    st.caption(f"👥 Lượt trả lời: **{len(df)}** • 🧩 Số cụm từ duy nhất: **{len(freq)}**")

                else:
                    st.info("Chưa có dữ liệu. Mời lớp nhập từ khóa.")

    # ------------------------------------------
    # 2) POLL
    # ------------------------------------------
    elif act == "poll":
        c1, c2 = st.columns([1, 2])
        options = cfg["options"]
        with c1:
            st.info(f"Câu hỏi: **{cfg['question']}**")
            if st.session_state["role"] == "student":
                with st.form("f_poll"):
                    n = st.text_input("Tên")
                    vote = st.radio("Lựa chọn", options)
                    if st.form_submit_button("BÌNH CHỌN"):
                        if n.strip():
                            save_data(cid, current_act_key, n, vote)
                            st.success("Đã chọn!")
                            time.sleep(0.2)
                            st.rerun()
                        else:
                            st.warning("Vui lòng nhập Tên.")
            else:
                st.caption(f"Đáp án gợi ý (chỉ GV): **{cfg.get('correct','')}**")
        with c2:
            st.markdown("##### 📊 THỐNG KÊ")
            df = load_data(cid, current_act_key)
            with st.container(border=True):
                if not df.empty:
                    cnt = df["Nội dung"].value_counts().reset_index()
                    cnt.columns = ["Lựa chọn", "Số lượng"]
                    fig = px.bar(cnt, x="Lựa chọn", y="Số lượng", text_auto=True)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Chưa có bình chọn nào.")

    # ------------------------------------------
    # 3) OPEN ENDED
    # ------------------------------------------
    elif act == "openended":
        c1, c2 = st.columns([1, 2])
        with c1:
            st.info(f"**{cfg['question']}**")
            if st.session_state["role"] == "student":
                with st.form("f_open"):
                    n = st.text_input("Tên")
                    c = st.text_area("Câu trả lời")
                    if st.form_submit_button("GỬI"):
                        if n.strip() and c.strip():
                            save_data(cid, current_act_key, n, c)
                            st.success("Đã gửi!")
                            time.sleep(0.2)
                            st.rerun()
                        else:
                            st.warning("Vui lòng nhập đủ Tên và nội dung.")
        with c2:
            st.markdown("##### 💬 BỨC TƯỜNG Ý KIẾN")
            df = load_data(cid, current_act_key)
            with st.container(border=True, height=520):
                if not df.empty:
                    for _, r in df.iterrows():
                        st.markdown(
                            f'<div class="note-card"><b>{r["Học viên"]}</b>: {r["Nội dung"]}</div>',
                            unsafe_allow_html=True
                        )
                else:
                    st.info("Chưa có câu trả lời.")

    # ------------------------------------------
    # 4) SCALES
    # ------------------------------------------
    elif act == "scales":
        c1, c2 = st.columns([1, 2])
        criteria = cfg["criteria"]
        with c1:
            st.info(f"**{cfg['question']}**")
            if st.session_state["role"] == "student":
                with st.form("f_scale"):
                    n = st.text_input("Tên")
                    scores = []
                    for cri in criteria:
                        scores.append(st.slider(cri, 1, 5, 3))
                    if st.form_submit_button("GỬI ĐÁNH GIÁ"):
                        if n.strip():
                            val = ",".join(map(str, scores))
                            save_data(cid, current_act_key, n, val)
                            st.success("Đã lưu!")
                            time.sleep(0.2)
                            st.rerun()
                        else:
                            st.warning("Vui lòng nhập Tên.")
        with c2:
            st.markdown("##### 🕸️ TỔNG HỢP")
            df = load_data(cid, current_act_key)
            with st.container(border=True):
                if not df.empty:
                    try:
                        data_matrix = []
                        for item in df["Nội dung"]:
                            data_matrix.append([int(x) for x in str(item).split(",")])
                        avg_scores = np.mean(data_matrix, axis=0)

                        fig = go.Figure(data=go.Scatterpolar(
                            r=avg_scores, theta=criteria, fill='toself', name='Lớp'
                        ))
                        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5])), showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)
                    except:
                        st.error("Dữ liệu lỗi định dạng.")
                else:
                    st.info("Chưa có dữ liệu thang đo.")

    # ------------------------------------------
    # 5) RANKING
    # ------------------------------------------
    elif act == "ranking":
        c1, c2 = st.columns([1, 2])
        items = cfg["items"]
        with c1:
            st.info(f"**{cfg['question']}**")
            if st.session_state["role"] == "student":
                with st.form("f_rank"):
                    n = st.text_input("Tên")
                    rank = st.multiselect("Chọn theo thứ tự (đủ tất cả mục)", items)
                    if st.form_submit_button("NỘP"):
                        if not n.strip():
                            st.warning("Vui lòng nhập Tên.")
                        elif len(rank) != len(items):
                            st.warning(f"Vui lòng chọn đủ {len(items)} mục.")
                        else:
                            save_data(cid, current_act_key, n, "->".join(rank))
                            st.success("Đã nộp!")
                            time.sleep(0.2)
                            st.rerun()
        with c2:
            st.markdown("##### 🏆 KẾT QUẢ")
            df = load_data(cid, current_act_key)
            with st.container(border=True):
                if not df.empty:
                    scores = {k: 0 for k in items}
                    for r in df["Nội dung"]:
                        parts = str(r).split("->")
                        for idx, item in enumerate(parts):
                            scores[item] += (len(items) - idx)

                    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                    labels = [x[0] for x in sorted_items]
                    vals = [x[1] for x in sorted_items]

                    fig = px.bar(x=vals, y=labels, orientation='h', labels={'x': 'Tổng điểm', 'y': 'Mục'}, text=vals)
                    fig.update_layout(yaxis={'categoryorder': 'total ascending'})
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Chưa có xếp hạng.")

    # ------------------------------------------
    # 6) PIN ON IMAGE
    # ------------------------------------------
    elif act == "pin":
        c1, c2 = st.columns([1, 2])
        with c1:
            st.info(f"**{cfg['question']}**")
            if st.session_state["role"] == "student":
                with st.form("f_pin"):
                    n = st.text_input("Tên")
                    x_val = st.slider("Vị trí ngang (Trái → Phải)", 0, 100, 50)
                    y_val = st.slider("Vị trí dọc (Dưới → Trên)", 0, 100, 50)
                    if st.form_submit_button("GHIM"):
                        if n.strip():
                            save_data(cid, current_act_key, n, f"{x_val},{y_val}")
                            st.success("Đã ghim!")
                            time.sleep(0.2)
                            st.rerun()
                        else:
                            st.warning("Vui lòng nhập Tên.")
        with c2:
            st.markdown("##### 📍 BẢN ĐỒ NHIỆT / ĐIỂM GHIM")
            df = load_data(cid, current_act_key)
            with st.container(border=True):
                if not df.empty:
                    try:
                        xs, ys = [], []
                        for item in df["Nội dung"]:
                            coords = str(item).split(",")
                            xs.append(int(coords[0]))
                            ys.append(int(coords[1]))

                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=xs, y=ys, mode='markers',
                            marker=dict(size=12, color='red', opacity=0.7, line=dict(width=1, color='white')),
                            name='Vị trí'
                        ))

                        fig.update_layout(
                            xaxis=dict(range=[0, 100], showgrid=False, zeroline=False, visible=False),
                            yaxis=dict(range=[0, 100], showgrid=False, zeroline=False, visible=False),
                            images=[dict(
                                source=cfg.get("image", MAP_IMAGE),
                                xref="x", yref="y",
                                x=0, y=100, sizex=100, sizey=100,
                                sizing="stretch", layer="below"
                            )],
                            width=700, height=420, margin=dict(l=0, r=0, t=0, b=0)
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    except:
                        st.error("Lỗi dữ liệu ghim.")
                else:
                    st.info("Chưa có ghim nào.")

    # ==========================================
    # CONTROL PANEL CHO GIẢNG VIÊN (CHUNG)
    # ==========================================
    if st.session_state["role"] == "teacher":
        st.markdown("---")
        with st.expander("👮‍♂️ BẢNG ĐIỀU KHIỂN GIẢNG VIÊN (Hoạt động hiện tại)", expanded=True):
            col_ai, col_reset = st.columns([3, 1])

            with col_ai:
                st.markdown("###### 🤖 AI Trợ giảng")
                prompt = st.text_input("Nhập lệnh cho AI", placeholder="Ví dụ: Hãy rút ra 3 xu hướng chính và 2 gợi ý giảng dạy.")
                if st.button("PHÂN TÍCH NGAY", key="btn_ai"):
                    curr_df = load_data(cid, current_act_key)
                    if curr_df.empty:
                        st.warning("Chưa có dữ liệu để phân tích.")
                    elif model is None:
                        st.warning("Chưa cấu hình GEMINI_API_KEY trong st.secrets.")
                    elif not prompt.strip():
                        st.warning("Vui lòng nhập yêu cầu phân tích.")
                    else:
                        with st.spinner("AI đang phân tích..."):
                            payload = f"""
Bạn là trợ giảng cho giảng viên. Đây là dữ liệu hoạt động ({cfg['name']}) của {cid}.
Chủ đề lớp: {CLASS_ACT_CONFIG[cid]['topic']}

DỮ LIỆU (dạng bảng):
{curr_df.to_string(index=False)}

YÊU CẦU CỦA GIẢNG VIÊN:
{prompt}

Hãy trả lời theo cấu trúc:
1) Nhận xét xu hướng
2) Điểm mạnh/yếu của lớp
3) Gợi ý can thiệp sư phạm (3 gợi ý)
4) Câu hỏi gợi mở để thảo luận tiếp (3 câu)
"""
                            res = model.generate_content(payload)
                            st.info(res.text)

            with col_reset:
                st.markdown("###### 🗑 Xóa dữ liệu")
                if st.button("RESET HOẠT ĐỘNG", key="btn_reset"):
                    clear_activity(cid, current_act_key)
                    st.toast("Đã xóa dữ liệu hoạt động")
                    time.sleep(0.4)
                    st.rerun()

# ==========================================
# 9. ROUTER
# ==========================================
page = st.session_state.get("page", "class_home")

if page == "class_home":
    render_class_home()
elif page == "dashboard":
    render_dashboard()
else:
    render_activity()
