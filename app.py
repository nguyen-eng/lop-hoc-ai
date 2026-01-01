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
import random  # Import random ở đầu file để tránh lỗi thiếu thư viện

# ✅ Live refresh (thay cho st.autorefresh)
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# ✅ Helper mở "fullscreen" tương thích nhiều phiên bản Streamlit
_DIALOG_DECORATOR = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)

def open_wc_fullscreen_dialog(wc_html_fs: str, live: bool):
    """Mở dialog fullscreen cho wordcloud (tương thích Streamlit cũ/mới)."""

    # Nếu có dialog/experimental_dialog thì dùng đúng chuẩn decorator
    if _DIALOG_DECORATOR is not None:
        @_DIALOG_DECORATOR("🖥 Fullscreen Wordcloud")
        def _inner():
            # Live update trong fullscreen
            if live and st_autorefresh is not None:
                st_autorefresh(interval=1500, key="wc_live_refresh_modal")

            st.components.v1.html(wc_html_fs, height=760, scrolling=False)

            if st.button("ĐÓNG FULLSCREEN", key="wc_close_full"):
                st.session_state["wc_fullscreen"] = False
                st.rerun()

        _inner()
        return

    # Fallback: nếu Streamlit quá cũ không có dialog => hiển thị dạng "khung lớn"
    st.warning("Streamlit phiên bản hiện tại chưa hỗ trợ dialog/modal. Đang dùng chế độ hiển thị thay thế.")
    if live and st_autorefresh is not None:
        st_autorefresh(interval=1500, key="wc_live_refresh_modal_fallback")

    st.components.v1.html(wc_html_fs, height=760, scrolling=False)

    if st.button("ĐÓNG FULLSCREEN", key="wc_close_full"):
        st.session_state["wc_fullscreen"] = False
        st.rerun()

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

    /* ✅ Nút fullscreen riêng (không dùng toolbar dataframe) */
    .wc-toolbar {{
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:10px;
        margin: 6px 0 10px 0;
        padding: 8px 10px;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        background: #fff;
    }}
    .wc-toolbar small {{
        color: {MUTED};
        font-weight: 700;
    }}
</style>
""", unsafe_allow_html=True)

# --- KẾT NỐI AI ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception:
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

# which activity
if "current_act_key" not in st.session_state:
    st.session_state["current_act_key"] = "dashboard"

# ✅ fullscreen state (optional)
if "wc_fullscreen" not in st.session_state:
    st.session_state["wc_fullscreen"] = False

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
    """
    Load dữ liệu robust:
    - Nếu file hỏng delimiter/thiếu cột => cố gắng chuẩn hoá về 3 cột: Học viên | Nội dung | Thời gian
    """
    path = get_path(cls, act)
    if not os.path.exists(path):
        return pd.DataFrame(columns=["Học viên", "Nội dung", "Thời gian"])

    try:
        df = pd.read_csv(path, sep="|", names=["Học viên", "Nội dung", "Thời gian"], engine="python")
        # Nếu có dòng header cũ bị ghi vào như dữ liệu (ví dụ: "Học viên|Nội dung|Thời gian")
        if not df.empty and str(df.iloc[0]["Học viên"]).strip().lower() in ["học viên", "hoc vien"]:
            df = df.iloc[1:].reset_index(drop=True)
        return df
    except Exception:
        # Fallback: đọc raw, tự tách
        try:
            rows = []
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip("\n")
                    if not line.strip():
                        continue
                    parts = line.split("|")
                    if len(parts) >= 3:
                        rows.append([parts[0], "|".join(parts[1:-1]), parts[-1]])
                    elif len(parts) == 2:
                        rows.append([parts[0], parts[1], ""])
                    else:
                        rows.append(["", line, ""])
            return pd.DataFrame(rows, columns=["Học viên", "Nội dung", "Thời gian"])
        except Exception:
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
                    <p class="hero-sub">Hệ thống tương tác lớp học </p>
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

    # Query param (fullscreen riêng cho wordcloud)
    q = st.experimental_get_query_params()
    is_wc_fs = (act == "wordcloud") and (q.get("wcfs", ["0"])[0] == "1")

    # ------------------------------------------
    # FULLSCREEN WORDCLOUD: render NGAY và stop để tránh "lọt" xuống dưới góc
    # ------------------------------------------
    if is_wc_fs:
        # Full screen layout: tắt sidebar, sát mép, không render phần khác
        st.markdown(f"""
        <style>
          header, footer {{visibility:hidden;}}
          [data-testid="stSidebar"] {{display:none;}}
          .block-container {{
            max-width: 100% !important;
            padding: 0.35rem 0.6rem !important;
          }}
        </style>
        """, unsafe_allow_html=True)

        # Nút thoát
        bar1, bar2, bar3 = st.columns([2, 6, 2])
        with bar1:
            if st.button("⬅️ Thoát Fullscreen", key="wc_exit_fs"):
                st.experimental_set_query_params()
                st.rerun()
        with bar3:
            st.caption("Toàn màn hình")

        # Live refresh trong fullscreen
        live_fs = True
        if st_autorefresh is not None:
            st_autorefresh(interval=1500, key="wc_live_refresh_fs")
        else:
            st.warning("Thiếu gói streamlit-autorefresh. Thêm vào requirements.txt: streamlit-autorefresh")

        # Load + build freq (đếm theo NGƯỜI)
        df_fs = load_data(cid, "wordcloud")
        import re, json

        def normalize_phrase(s: str) -> str:
            s = str(s or "").strip().lower()
            s = re.sub(r"\s+", " ", s)
            s = s.strip(" .,:;!?\"'`()[]{}<>|\\/+-=*#@~^_")
            return s

        tmp = df_fs[["Học viên", "Nội dung"]].dropna().copy() if not df_fs.empty else pd.DataFrame(columns=["Học viên", "Nội dung"])
        tmp["Học viên"] = tmp["Học viên"].astype(str).str.strip()
        tmp["phrase"] = tmp["Nội dung"].astype(str).apply(normalize_phrase) if "Nội dung" in tmp.columns else ""
        tmp = tmp[(tmp["Học viên"] != "") & (tmp["phrase"] != "")]
        tmp = tmp.drop_duplicates(subset=["Học viên", "phrase"]) if ("phrase" in tmp.columns) else tmp
        freq = tmp["phrase"].value_counts().to_dict() if ("phrase" in tmp.columns and not tmp.empty) else {}

        # Build HTML (dùng viewport height để đúng “toàn màn hình”)
        def build_wordcloud_html(words_json: str) -> str:
            comp_html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    body {{ margin:0; background:white; }}
    #wc-wrap {{
      width: 100vw;
      height: 90vh;
      background: #ffffff;
      overflow: hidden;
    }}
    svg {{ width:100%; height:100%; display:block; }}
    .word {{
      font-family: 'Montserrat', system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      font-weight: 800;
      cursor: default;
      user-select: none;
    }}
  </style>
</head>
<body>
  <div id="wc-wrap"></div>

  <script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/d3-cloud@1/build/d3.layout.cloud.js"></script>
  <script>
    const data = {words_json};

    const wrap = document.getElementById("wc-wrap");

    function sizeNow() {{
      const W = Math.max(960, wrap.clientWidth || 960);
      const H = Math.max(520, wrap.clientHeight || 720);
      return {{W, H}};
    }}

    function mulberry32(a) {{
      return function() {{
        var t = a += 0x6D2B79F5;
        t = Math.imul(t ^ t >>> 15, t | 1);
        t ^= t + Math.imul(t ^ t >>> 7, t | 61);
        return ((t ^ t >>> 14) >>> 0) / 4294967296;
      }}
    }}
    const rng = mulberry32(42);

    const vals = data.map(d => d.value);
    const vmin = Math.max(1, d3.min(vals));
    const vmax = Math.max(1, d3.max(vals));

    function makeScale(vmin, vmax) {{
      // Mentimeter-like: nếu tất cả = 1 => cùng size, nhưng KHÔNG to quá (tránh lộn xộn)
      if (vmax === vmin) {{
        return () => 58;
      }}
      return d3.scaleSqrt()
        .domain([vmin, vmax])
        .range([26, 110])
        .clamp(true);
    }}

    function rotateFn() {{
      return (rng() < 0.85) ? 0 : -90;   // ưu tiên ngang cho dễ đọc
    }}

    // Màu ít hơn để đỡ rối (2 tone)
    function colorFor(v) {{
      return (v >= vmax) ? "hsl(265,85%,45%)" : "hsl(292,85%,52%)";
    }}

    function render() {{
      const {{W, H}} = sizeNow();
      wrap.innerHTML = "";
      const svg = d3.select("#wc-wrap").append("svg")
        .attr("viewBox", `0 0 ${{W}} ${{H}}`)
        .attr("preserveAspectRatio", "xMidYMid meet");

      const g = svg.append("g")
        .attr("transform", `translate(${{W/2}},${{H/2}})`);

      // Giảm số từ khi tất cả đều =1 để tránh "lộn xộn"
      let maxWords = 140;
      if (vmax === 1) maxWords = Math.min(45, data.length);

      const fontScale = makeScale(vmin, vmax);

      const words = data
        .slice()
        .sort((a,b) => d3.descending(a.value, b.value))
        .slice(0, maxWords)
        .map(d => ({{
          text: d.text,
          value: d.value,
          size: Math.round(fontScale(d.value)),
          rotate: rotateFn(),
          __key: d.text
        }}));

      // Padding thích ứng: càng nhiều từ, padding càng lớn
      const pad = (words.length > 80) ? 10 : (words.length > 50 ? 11 : 12);

      const layout = d3.layout.cloud()
        .size([W, H])
        .words(words)
        .padding(pad)
        .spiral("rectangular")
        .rotate(d => d.rotate)
        .font("Montserrat")
        .fontSize(d => d.size)
        .random(() => rng())
        .on("end", placed => {{
          if (!placed || placed.length === 0) return;

          // bbox centering
          let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
          placed.forEach(w => {{
            const x0 = w.x - (w.width  || 0)/2;
            const x1 = w.x + (w.width  || 0)/2;
            const y0 = w.y - (w.height || 0)/2;
            const y1 = w.y + (w.height || 0)/2;
            if (x0 < minX) minX = x0;
            if (x1 > maxX) maxX = x1;
            if (y0 < minY) minY = y0;
            if (y1 > maxY) maxY = y1;
          }});
          const cx = (minX + maxX) / 2;
          const cy = (minY + maxY) / 2;
          placed.forEach(w => {{ w.x -= cx; w.y -= cy; }});

          const sel = g.selectAll("text.word").data(placed, d => d.__key);

          sel.exit().remove();

          sel.enter().append("text")
            .attr("class", "word")
            .attr("text-anchor", "middle")
            .style("opacity", 1)
            .style("fill", d => colorFor(d.value))
            .style("font-size", d => `${{d.size}}px`)
            .attr("transform", d => `translate(${{d.x}},${{d.y}}) rotate(${{d.rotate}})`)
            .text(d => d.text);
        }});

      layout.start();
    }}

    render();
    // Resize để luôn đúng toàn màn hình
    window.addEventListener("resize", () => {{
      clearTimeout(window.__wc_t);
      window.__wc_t = setTimeout(render, 150);
    }});
  </script>
</body>
</html>
"""
            return comp_html

        if not freq:
            st.info("Chưa có dữ liệu. Mời lớp nhập từ khóa.")
            st.stop()

        items_fs = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        words_payload_fs = [{"text": k, "value": int(v)} for k, v in items_fs]
        words_json_fs = json.dumps(words_payload_fs, ensure_ascii=False)

        wc_html_fs = build_wordcloud_html(words_json_fs)
        st.components.v1.html(wc_html_fs, height=920, scrolling=False)
        st.stop()

    # ------------------------------------------
    # NORMAL PAGE HEADER
    # ------------------------------------------
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
    # 1) WORD CLOUD
    # ------------------------------------------
    if act == "wordcloud":
        c1, c2 = st.columns([1, 2])

        # --- CỘT TRÁI: NHẬP LIỆU ---
        with c1:
            st.info(f"Câu hỏi: **{cfg['question']}**")
            if st.session_state["role"] == "student":
                with st.form("f_wc"):
                    n = st.text_input("Tên")
                    txt = st.text_input("Nhập 1 từ khóa / cụm từ (giữ nguyên cụm)")
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

        # --- CỘT PHẢI: HIỂN THỊ KẾT QUẢ ---
        with c2:
            import re, json

            # ✅ Live update toggle + Fullscreen button + show table toggle
            tcol1, tcol2, tcol3 = st.columns([2, 2, 2])
            with tcol1:
                live = st.toggle("🔴 Live update (1.5s)", value=True, key="wc_live_toggle")
            with tcol2:
                if st.button("🖥 Fullscreen Wordcloud", key="wc_btn_full"):
                    st.experimental_set_query_params(wcfs="1")
                    st.rerun()
            with tcol3:
                show_table = st.toggle("Hiện bảng Top từ", value=False, key="wc_show_table")

            # ✅ Auto refresh (thay st.autorefresh)
            if live:
                if st_autorefresh is not None:
                    st_autorefresh(interval=1500, key="wc_live_refresh")
                else:
                    st.warning("Thiếu gói streamlit-autorefresh. Thêm vào requirements.txt: streamlit-autorefresh")

            st.markdown("##### ☁️ KẾT QUẢ")
            df = load_data(cid, current_act_key)

            def normalize_phrase(s: str) -> str:
                s = str(s or "").strip().lower()
                s = re.sub(r"\s+", " ", s)
                s = s.strip(" .,:;!?\"'`()[]{}<>|\\/+-=*#@~^_")
                return s

            # ✅ FIX KeyError 'phrase' + chuẩn hoá robust
            if df is None or df.empty:
                tmp = pd.DataFrame(columns=["Học viên", "Nội dung", "phrase"])
            else:
                base = df.copy()
                # đảm bảo có 2 cột
                for col in ["Học viên", "Nội dung"]:
                    if col not in base.columns:
                        base[col] = ""
                tmp = base[["Học viên", "Nội dung"]].dropna().copy()
                tmp["Học viên"] = tmp["Học viên"].astype(str).str.strip()
                tmp["phrase"] = tmp["Nội dung"].astype(str).apply(normalize_phrase)

            tmp = tmp[(tmp["Học viên"] != "") & (tmp["phrase"] != "")] if ("Học viên" in tmp.columns and "phrase" in tmp.columns) else tmp
            tmp = tmp.drop_duplicates(subset=["Học viên", "phrase"]) if ("Học viên" in tmp.columns and "phrase" in tmp.columns and not tmp.empty) else tmp
            freq = tmp["phrase"].value_counts().to_dict() if ("phrase" in tmp.columns and not tmp.empty) else {}

            total_answers = int(df["Nội dung"].dropna().shape[0]) if (df is not None and not df.empty and "Nội dung" in df.columns) else 0
            total_people = int(tmp["Học viên"].nunique()) if (not tmp.empty and "Học viên" in tmp.columns) else 0
            total_unique_phrases = int(len(freq)) if freq else 0

            def build_wordcloud_html(words_json: str, height_px: int = 520) -> str:
                # ✅ Ít rối hơn:
                # - nếu tất cả =1 => giới hạn số từ + font vừa phải
                # - ưu tiên chữ ngang
                # - spiral rectangular, padding thích ứng
                comp_html = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    body {{ margin:0; background:white; }}
    #wc-wrap {{
      width: 100%;
      height: {height_px}px;
      border-radius: 12px;
      background: #ffffff;
      overflow: hidden;
    }}
    svg {{ width:100%; height:100%; display:block; }}
    .word {{
      font-family: 'Montserrat', system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      font-weight: 800;
      cursor: default;
      user-select: none;
    }}
  </style>
</head>
<body>
  <div id="wc-wrap"></div>

  <script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/d3-cloud@1/build/d3.layout.cloud.js"></script>
  <script>
    const data = {words_json};

    const wrap = document.getElementById("wc-wrap");
    const W = Math.max(900, wrap.clientWidth || 900);
    const H = Math.max(520, wrap.clientHeight || {height_px});

    function mulberry32(a) {{
      return function() {{
        var t = a += 0x6D2B79F5;
        t = Math.imul(t ^ t >>> 15, t | 1);
        t ^= t + Math.imul(t ^ t >>> 7, t | 61);
        return ((t ^ t >>> 14) >>> 0) / 4294967296;
      }}
    }}
    const rng = mulberry32(42);

    const vals = data.map(d => d.value);
    const vmin = Math.max(1, d3.min(vals));
    const vmax = Math.max(1, d3.max(vals));

    // ✅ Mentimeter-like size: dùng sqrt, clamp; nếu tất cả =1 => size vừa phải
    let fontScale;
    if (vmax === vmin) {{
      fontScale = () => 54;
    }} else {{
      fontScale = d3.scaleSqrt()
        .domain([vmin, vmax])
        .range([24, 96])
        .clamp(true);
    }}

    function rotateFn() {{
      return (rng() < 0.88) ? 0 : -90;
    }}

    // ✅ Màu ít hơn để đỡ lộn xộn
    function colorFor(v) {{
      if (v >= vmax) return "hsl(265,85%,45%)";
      if (v > 1) return "hsl(278,85%,48%)";
      return "hsl(292,85%,52%)";
    }}

    // ✅ Nếu tất cả đều unique (=1), giới hạn số từ để tránh rối
    let maxWords = 80;
    if (vmax === 1) maxWords = Math.min(35, data.length);

    const words = data
      .slice()
      .sort((a,b) => d3.descending(a.value, b.value))
      .slice(0, maxWords)
      .map(d => ({{
        text: d.text,
        value: d.value,
        size: Math.round(fontScale(d.value)),
        rotate: rotateFn(),
        __key: d.text
      }}));

    const pad = (words.length > 60) ? 10 : 12;

    const svg = d3.select("#wc-wrap").append("svg")
      .attr("viewBox", `0 0 ${{W}} ${{H}}`)
      .attr("preserveAspectRatio","xMidYMid meet");

    const g = svg.append("g")
      .attr("transform", `translate(${{W/2}},${{H/2}})`);

    const layout = d3.layout.cloud()
      .size([W, H])
      .words(words)
      .padding(pad)
      .spiral("rectangular")
      .rotate(d => d.rotate)
      .font("Montserrat")
      .fontSize(d => d.size)
      .random(() => rng());

    layout.on("end", draw);
    layout.start();

    function draw(placed) {{
      if (!placed || placed.length === 0) return;

      // ✅ bbox centering
      let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
      placed.forEach(w => {{
        const x0 = w.x - (w.width  || 0)/2;
        const x1 = w.x + (w.width  || 0)/2;
        const y0 = w.y - (w.height || 0)/2;
        const y1 = w.y + (w.height || 0)/2;
        if (x0 < minX) minX = x0;
        if (x1 > maxX) maxX = x1;
        if (y0 < minY) minY = y0;
        if (y1 > maxY) maxY = y1;
      }});
      const cx = (minX + maxX) / 2;
      const cy = (minY + maxY) / 2;
      placed.forEach(w => {{ w.x -= cx; w.y -= cy; }});

      const sel = g.selectAll("text.word")
        .data(placed, d => d.__key);

      sel.exit().remove();

      sel.enter().append("text")
        .attr("class", "word")
        .attr("text-anchor", "middle")
        .style("opacity", 1)
        .style("fill", d => colorFor(d.value))
        .style("font-size", d => `${{d.size}}px`)
        .attr("transform", d => `translate(${{d.x}},${{d.y}}) rotate(${{d.rotate}})`)
        .text(d => d.text);
    }}
  </script>
</body>
</html>
"""
                return comp_html

            # --- Normal view container
            with st.container(border=True):
                if not freq:
                    st.info("Chưa có dữ liệu. Mời lớp nhập từ khóa.")
                else:
                    # ✅ Hiển thị ít hơn để gọn, ưu tiên những từ được NHIỀU NGƯỜI nhập
                    items_all = sorted(freq.items(), key=lambda x: x[1], reverse=True)

                    # Nếu có từ lặp (>=2), ưu tiên các từ >=2 + thêm top để đủ mật độ vừa
                    if items_all and items_all[0][1] >= 2:
                        major = [it for it in items_all if it[1] >= 2]
                        rest = [it for it in items_all if it[1] == 1]
                        items = major[:80] + rest[:10]
                    else:
                        items = items_all[:35]

                    words_payload = [{"text": k, "value": int(v)} for k, v in items]
                    words_json = json.dumps(words_payload, ensure_ascii=False)

                    wc_html = build_wordcloud_html(words_json, height_px=520)
                    st.components.v1.html(wc_html, height=540, scrolling=False)

            st.caption(
                f"👥 Lượt gửi: **{total_answers}** • 👤 Người tham gia (unique): **{total_people}** • 🧩 Cụm duy nhất: **{total_unique_phrases}**"
            )

            if show_table and freq:
                items_table = sorted(freq.items(), key=lambda x: x[1], reverse=True)
                topk = pd.DataFrame(items_table[:20], columns=["Từ/cụm (chuẩn hoá)", "Số người nhập"])
                st.dataframe(topk, use_container_width=True, hide_index=True)

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
                    except Exception:
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
                            if item in scores:
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
                    except Exception:
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
