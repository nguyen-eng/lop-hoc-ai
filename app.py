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

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Montserrat', sans-serif;
        background-color: {BG_COLOR};
        color: {TEXT_COLOR};
    }}

    header {{visibility: hidden;}} footer {{visibility: hidden;}}

    /* LOGIN BOX */
    .login-box {{
        background: white; padding: 40px; border-radius: 20px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.1); text-align: center;
        max-width: 600px; margin: 0 auto; border-top: 6px solid {PRIMARY_COLOR};
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
        border-radius: 50px; padding: 12px 24px; font-weight: 700;
        text-transform: uppercase; letter-spacing: 1px; width: 100%;
        box-shadow: 0 4px 15px rgba(0, 106, 78, 0.3);
    }}
    div.stButton > button:hover {{ background-color: #00503a; transform: translateY(-2px); }}

    /* NOTE CARD */
    .note-card {{
        background: #fff; padding: 15px; border-radius: 12px;
        border-left: 5px solid {PRIMARY_COLOR}; margin-bottom: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08); font-size: 15px;
    }}

    /* SIDEBAR */
    [data-testid="stSidebar"] {{ background-color: #111827; }}
    [data-testid="stSidebar"] * {{ color: #ffffff; }}

    /* ===== NEW: Gradescope-like activity list ===== */
    .page-title {{
        font-size: 30px; font-weight: 800; margin: 0 0 6px 0;
        display:flex; align-items:center; gap:10px;
    }}
    .subtle {{
        color: #64748b; font-weight: 600; margin-top: 2px;
    }}
    .activity-row {{
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 16px 18px;
        box-shadow: 0 6px 16px rgba(0,0,0,0.03);
        margin-bottom: 14px;
    }}
    .activity-title {{
        font-weight: 800;
        margin: 0;
        font-size: 16px;
        color: #0f172a;
    }}
    .activity-meta {{
        margin: 6px 0 0 0;
        color: #64748b;
        font-weight: 600;
        font-size: 13px;
    }}
    .pill {{
        display:inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        background: #f1f5f9;
        color: #0f172a;
        font-weight: 700;
        font-size: 12px;
        margin-right: 8px;
    }}
</style>
""", unsafe_allow_html=True)

# --- KẾT NỐI AI ---
model = None
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

if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'role': '', 'class_id': ''})

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

# ==========================================
# 2.1. NEW: CẤU HÌNH NỘI DUNG THEO LỚP (Mentimeter-like)
# ==========================================
def _topic_for_class(cid: str) -> str:
    n = int(cid.replace("lop", ""))
    if n in [1, 2]:
        return "Cặp phạm trù Nguyên nhân – Kết quả (và phân biệt nguyên cớ, điều kiện)"
    if n in [3, 4]:
        return "Quy luật Phủ định của phủ định (đường xoáy ốc phát triển)"
    if n in [5, 6]:
        return "Triết học về con người: quan niệm – bản chất; tha hóa trong lao động; giải phóng con người"
    if n in [7, 8]:
        return "Triết học về con người: quan hệ cá nhân – xã hội; vấn đề con người ở Việt Nam"
    return "Triết học Mác-xít (tổng quan: thế giới quan, phương pháp luận, các quy luật/cặp phạm trù)"

def class_content(cid: str) -> dict:
    topic = _topic_for_class(cid)
    n = int(cid.replace("lop", ""))

    # --- DEFAULTS (sẽ override theo nhóm lớp) ---
    content = {
        "topic": topic,
        "wordcloud": {
            "title": "Từ khóa phân biệt",
            "question": "Hãy nêu 01 từ khóa then chốt của chủ đề hôm nay.",
            "hint": "Ví dụ: 'tất yếu', 'kế thừa', 'tha hóa', 'giải phóng', ...",
        },
        "poll": {
            "title": "Chọn đúng bản chất",
            "question": "Theo bạn, phát biểu nào đúng nhất?",
            "options": ["Phương án A", "Phương án B", "Phương án C", "Phương án D"],
            "correct": None,  # có thể đặt đáp án đúng (A/B/C/D) để GV xem
            "explain": "",    # giải thích ngắn gọn
        },
        "openended": {
            "title": "Tình huống/vụ việc",
            "question": "Trả lời ngắn gọn theo ý bạn (2–5 dòng).",
            "teacher_key": "Gợi ý chấm: nêu tiêu chí, lập luận, ví dụ minh họa.",
        },
        "scales": {
            "title": "Tự đánh giá năng lực",
            "question": "Tự đánh giá (1: thấp – 5: cao) theo các tiêu chí:",
            "criteria": ["Tiêu chí 1", "Tiêu chí 2", "Tiêu chí 3", "Tiêu chí 4"],
        },
        "ranking": {
            "title": "Ưu tiên phân tích",
            "question": "Sắp xếp mức ưu tiên (quan trọng nhất lên đầu):",
            "items": ["Mục 1", "Mục 2", "Mục 3", "Mục 4"],
        },
        "pin": {
            "title": "Điểm nóng tình huống",
            "question": "Ghim vị trí mô phỏng nơi 'điểm nóng' xuất hiện.",
            "image": MAP_IMAGE,
        }
    }

    # --- GROUP-SPECIFIC OVERRIDES ---
    if n in [1, 2]:
        content["wordcloud"].update({
            "question": "1 từ khóa giúp bạn phân biệt 'nguyên nhân' với 'nguyên cớ/điều kiện' là gì?",
            "hint": "Ví dụ: 'sinh ra', 'tất yếu', 'bên trong', 'ngoại tại', 'khả năng', ...",
        })
        content["poll"].update({
            "question": "Đâu là mô tả đúng nhất về 'nguyên cớ'?",
            "options": [
                "A. Yếu tố bên trong sinh ra kết quả",
                "B. Yếu tố xuất hiện trước kết quả nhưng chỉ là quan hệ ngẫu nhiên, không sinh ra kết quả",
                "C. Tổng hợp mọi điều kiện cần và đủ",
                "D. Kết quả quay lại tạo ra nguyên nhân ban đầu"
            ],
            "correct": "B",
            "explain": "Nguyên cớ có thể đi trước và 'đi kèm' kết quả, nhưng không mang quan hệ sinh thành tất yếu như nguyên nhân."
        })
        content["openended"].update({
            "question": "Từ một vụ va quẹt xe dẫn tới đánh nhau: hãy phân biệt 'nguyên nhân', 'nguyên cớ', 'điều kiện' của hậu quả.",
            "teacher_key": "Nguyên nhân: mâu thuẫn/động cơ bạo lực; Nguyên cớ: va quẹt; Điều kiện: hung khí, kích động đám đông, thiếu can ngăn..."
        })
        content["scales"].update({
            "criteria": [
                "Phân biệt được nguyên nhân vs nguyên cớ",
                "Nhận diện được điều kiện cần/đủ",
                "Lập luận quan hệ tất yếu–ngẫu nhiên",
                "Liên hệ thực tiễn điều tra/đánh giá tình huống"
            ]
        })
        content["ranking"].update({
            "items": [
                "Xác định nguyên nhân trực tiếp",
                "Xác định nguyên nhân sâu xa",
                "Xác định nguyên cớ kích hoạt",
                "Xác định chuỗi điều kiện làm bùng phát"
            ]
        })
        content["pin"].update({
            "question": "Ghim vị trí mô phỏng nơi 'điểm kích hoạt' xảy ra (nguyên cớ) so với nơi 'nguyên nhân' tích tụ.",
        })

    elif n in [3, 4]:
        content["wordcloud"].update({
            "question": "1 từ khóa mô tả đúng nhất 'phủ định biện chứng' (khách quan/kế thừa) là gì?",
            "hint": "Ví dụ: 'tự thân', 'mâu thuẫn', 'kế thừa', 'vượt bỏ', 'xoáy ốc'...",
        })
        content["poll"].update({
            "question": "Phát biểu nào phản ánh đúng 'đường xoáy ốc'?",
            "options": [
                "A. Phát triển là lặp lại y nguyên cái cũ",
                "B. Phát triển là đường thẳng tăng dần, không quanh co",
                "C. Phát triển có tính lặp lại nhưng ở trình độ cao hơn, thông qua các khâu trung gian",
                "D. Phát triển là vòng tròn khép kín quay về điểm xuất phát"
            ],
            "correct": "C",
            "explain": "Xoáy ốc: có tính lặp lại (kế thừa) nhưng không quay lại nguyên trạng; trình độ mới cao hơn."
        })
        content["openended"].update({
            "question": "Chọn 1 ví dụ (tự nhiên/xã hội/tư duy) và giải thích vì sao cần ít nhất 'hai lần phủ định' để hình thành cái mới.",
            "teacher_key": "Nêu: mâu thuẫn nội tại → phủ định lần 1 tạo cái đối lập; phủ định lần 2 loại bỏ yếu tố phi lý của đối lập và giữ hạt nhân hợp lý..."
        })
        content["scales"].update({
            "criteria": [
                "Hiểu phủ định biện chứng (khách quan)",
                "Nhận ra tính kế thừa (giữ hạt nhân hợp lý)",
                "Phân biệt phủ định siêu hình vs biện chứng",
                "Vận dụng giải thích ví dụ mới"
            ]
        })
        content["ranking"].update({
            "items": [
                "Chỉ ra mâu thuẫn nội tại",
                "Xác định cái bị phủ định và cái được kế thừa",
                "Mô tả khâu trung gian",
                "Chứng minh 'cao hơn' ở lần phủ định thứ hai"
            ]
        })

    elif n in [5, 6]:
        content["wordcloud"].update({
            "question": "1 từ khóa diễn tả 'bản chất con người' theo quan điểm Mác là gì?",
            "hint": "Ví dụ: 'tổng hòa', 'quan hệ xã hội', 'thực tiễn', 'lao động'...",
        })
        content["poll"].update({
            "question": "Câu nào gần nhất với quan điểm Mác về bản chất con người?",
            "options": [
                "A. Bản chất con người là bất biến, do sinh học quyết định",
                "B. Bản chất con người là tổng hòa các quan hệ xã hội",
                "C. Bản chất con người chỉ là ý thức cá nhân",
                "D. Bản chất con người là bản năng tự nhiên thuần túy"
            ],
            "correct": "B",
            "explain": "Trọng tâm: tính lịch sử–xã hội, thực tiễn; không quy giản vào sinh học hay ý thức chủ quan."
        })
        content["openended"].update({
            "question": "Nêu 1 biểu hiện 'tha hóa trong lao động' và đề xuất 1 hướng 'giải phóng con người' (gợi ý theo Mác).",
            "teacher_key": "Tha hóa: sản phẩm/hoạt động/lao động như lực lượng xa lạ; Giải phóng: cải biến quan hệ xã hội, điều kiện lao động, khôi phục tính người..."
        })
        content["scales"].update({
            "criteria": [
                "Hiểu quan niệm về con người (tự nhiên–xã hội)",
                "Hiểu 'bản chất con người' theo Mác",
                "Nhận diện cơ chế tha hóa",
                "Đề xuất giải pháp giải phóng (thực tiễn)"
            ]
        })
        content["ranking"].update({
            "items": [
                "Tha hóa sản phẩm lao động",
                "Tha hóa quá trình lao động",
                "Tha hóa bản chất loài (species-being)",
                "Tha hóa quan hệ người–người"
            ]
        })

    elif n in [7, 8]:
        content["wordcloud"].update({
            "question": "1 từ khóa mô tả đúng quan hệ cá nhân – xã hội là gì?",
            "hint": "Ví dụ: 'thống nhất', 'tác động qua lại', 'điều kiện', 'chủ thể'...",
        })
        content["poll"].update({
            "question": "Phát biểu nào đúng nhất về quan hệ cá nhân – xã hội?",
            "options": [
                "A. Cá nhân hoàn toàn quyết định xã hội",
                "B. Xã hội hoàn toàn quyết định cá nhân theo cơ học",
                "C. Cá nhân là sản phẩm xã hội nhưng đồng thời là chủ thể cải biến xã hội",
                "D. Cá nhân và xã hội tách rời, không liên quan"
            ],
            "correct": "C",
            "explain": "Quan hệ biện chứng: xã hội tạo điều kiện/khung; cá nhân hành động cải biến trong thực tiễn."
        })
        content["openended"].update({
            "question": "Trong bối cảnh Việt Nam hiện nay, bạn thấy 'vấn đề con người' nổi bật nhất là gì? Nêu 1 luận điểm + 1 ví dụ.",
            "teacher_key": "Có thể theo hướng: phát triển con người toàn diện, đạo đức công vụ, năng lực số, văn hóa pháp luật, trách nhiệm xã hội..."
        })
        content["scales"].update({
            "criteria": [
                "Nhìn được cá nhân trong mạng quan hệ xã hội",
                "Nhìn được vai trò chủ thể của cá nhân",
                "Liên hệ bối cảnh Việt Nam (đúng trọng tâm)",
                "Đề xuất giải pháp phát triển con người"
            ]
        })
        content["ranking"].update({
            "items": [
                "Đạo đức và văn hóa pháp luật",
                "Năng lực nghề nghiệp và kỷ luật",
                "Năng lực số và thích ứng biến đổi",
                "Trách nhiệm công dân và cộng đồng"
            ]
        })

    else:  # 9,10
        content["wordcloud"].update({
            "question": "1 từ khóa cốt lõi của triết học Mác-xít (thế giới quan/phương pháp luận) là gì?",
            "hint": "Ví dụ: 'thực tiễn', 'biện chứng', 'vật chất', 'lịch sử'...",
        })
        content["poll"].update({
            "question": "Đâu là điểm nhấn phương pháp luận của triết học Mác-xít?",
            "options": [
                "A. Giải thích thế giới bằng trực giác cá nhân",
                "B. Coi thực tiễn là cơ sở, tiêu chuẩn của nhận thức và cải tạo hiện thực",
                "C. Phủ nhận hoàn toàn vai trò của con người",
                "D. Đồng nhất ý thức với vật chất"
            ],
            "correct": "B",
            "explain": "Thực tiễn: nền tảng của nhận thức và hành động cải biến hiện thực."
        })
        content["openended"].update({
            "question": "Chọn 1 cặp phạm trù/1 quy luật và nêu cách vận dụng vào tư duy nghề nghiệp (tổ chức, chỉ huy, ĐTV/trinh sát).",
            "teacher_key": "Nhấn mạnh: tư duy chứng cứ, phân tích mâu thuẫn, điều kiện–nguyên nhân, phát triển biện chứng, tránh duy ý chí..."
        })
        content["scales"].update({
            "criteria": [
                "Nắm thế giới quan duy vật biện chứng",
                "Nắm phương pháp luận biện chứng",
                "Vận dụng phân tích tình huống",
                "Trình bày lập luận chặt chẽ"
            ]
        })
        content["ranking"].update({
            "items": [
                "Thực tiễn – nhận thức – hành động",
                "Mâu thuẫn và giải quyết mâu thuẫn",
                "Nguyên nhân – điều kiện – kết quả",
                "Phát triển và phủ định biện chứng"
            ]
        })

    return content


# ==========================================
# 3. MÀN HÌNH ĐĂNG NHẬP
# ==========================================
if not st.session_state['logged_in']:
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(f"""
        <div class="login-box">
            <img src="{LOGO_URL}" width="100">
            <h2 style="color:{PRIMARY_COLOR}; margin-top:15px;">TRƯỜNG ĐH CẢNH SÁT NHÂN DÂN</h2>
            <p style="color:#64748b; font-weight:600;">HỆ THỐNG TƯƠNG TÁC LỚP HỌC</p>
            <div style="text-align:left; background:#f1f5f9; padding:15px; border-radius:10px; margin:20px 0; font-size:14px; color:#334155;">
                <b>Khoa:</b> LLCT & KHXHNV<br>
                <b>Giảng viên:</b> Trần Nguyễn Sĩ Nguyên
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.write("")
        tab_sv, tab_gv = st.tabs(["CỔNG HỌC VIÊN", "CỔNG GIẢNG VIÊN"])

        with tab_sv:
            c_class = st.selectbox("Chọn Lớp:", list(CLASSES.keys()))
            c_pass = st.text_input("Mã lớp:", type="password", placeholder="Ví dụ: T05-1")
            if st.button("THAM GIA LỚP HỌC"):
                cid = CLASSES[c_class]
                if c_pass.strip() == PASSWORDS[cid]:
                    st.session_state.update({'logged_in': True, 'role': 'student', 'class_id': cid})
                    # NEW: default landing page is Activity Catalog
                    st.session_state["menu"] = "📚 Danh mục hoạt động"
                    st.rerun()
                else:
                    st.error("Sai mã lớp!")

        with tab_gv:
            t_pass = st.text_input("Mật khẩu Admin:", type="password")
            if st.button("VÀO QUẢN TRỊ"):
                if t_pass == "T05":
                    st.session_state.update({'logged_in': True, 'role': 'teacher', 'class_id': 'lop1'})
                    # NEW: default landing page is Activity Catalog
                    st.session_state["menu"] = "📚 Danh mục hoạt động"
                    st.rerun()
                else:
                    st.error("Sai mật khẩu.")

# ==========================================
# 4. GIAO DIỆN CHÍNH
# ==========================================
else:
    # NEW: menu state
    if "menu" not in st.session_state:
        st.session_state["menu"] = "📚 Danh mục hoạt động"

    # --- SIDEBAR ---
    with st.sidebar:
        st.image(LOGO_URL, width=80)
        st.markdown("---")
        st.caption("🎵 NHẠC NỀN")
        st.audio("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3")

        cls_txt = [k for k, v in CLASSES.items() if v == st.session_state['class_id']][0]
        role = "HỌC VIÊN" if st.session_state['role'] == 'student' else "GIẢNG VIÊN"
        st.info(f"👤 {role}\n\n🏫 {cls_txt}")

        if st.session_state['role'] == 'teacher':
            st.warning("CHUYỂN LỚP QUẢN LÝ")
            s_cls = st.selectbox("", list(CLASSES.keys()), label_visibility="collapsed")
            st.session_state['class_id'] = CLASSES[s_cls]

        st.markdown("---")

        # UPDATED: include Activity Catalog like Gradescope
        menu_items = [
            "📚 Danh mục hoạt động",
            "🏠 Dashboard",
            "1️⃣ Word Cloud (Từ khóa)",
            "2️⃣ Poll (Bình chọn)",
            "3️⃣ Open Ended (Hỏi đáp)",
            "4️⃣ Scales (Thang đo)",
            "5️⃣ Ranking (Xếp hạng)",
            "6️⃣ Pin on Image (Ghim ảnh)"
        ]

        # Keep selection persistent
        current_index = menu_items.index(st.session_state["menu"]) if st.session_state["menu"] in menu_items else 0
        menu = st.radio("ĐIỀU HƯỚNG", menu_items, index=current_index)
        st.session_state["menu"] = menu

        st.markdown("---")
        if st.button("THOÁT"):
            st.session_state.clear()
            st.rerun()

    # --- HEADER ---
    cfg = class_content(st.session_state["class_id"])
    if menu == "📚 Danh mục hoạt động":
        st.markdown(f"<div class='page-title'>🗂️ Danh mục hoạt động của lớp</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='subtle'>Chủ đề lớp: {cfg['topic']}</div>", unsafe_allow_html=True)
        st.markdown("<hr style='border:0;border-top:2px solid #e2e8f0;margin:12px 0 18px 0;'/>", unsafe_allow_html=True)
    else:
        st.markdown(
            f"<h2 style='color:{PRIMARY_COLOR}; border-bottom:2px solid #e2e8f0; padding-bottom:10px;'>{menu}</h2>",
            unsafe_allow_html=True
        )
        st.caption(f"Chủ đề lớp: {cfg['topic']}")

    # Lấy key hoạt động để lưu file
    act_map = {
        "1️⃣ Word Cloud (Từ khóa)": "wordcloud",
        "2️⃣ Poll (Bình chọn)": "poll",
        "3️⃣ Open Ended (Hỏi đáp)": "openended",
        "4️⃣ Scales (Thang đo)": "scales",
        "5️⃣ Ranking (Xếp hạng)": "ranking",
        "6️⃣ Pin on Image (Ghim ảnh)": "pin"
    }
    current_act_key = act_map.get(menu, "dashboard")

    # ==========================================
    # NEW: GRADESCOPE-LIKE ACTIVITY CATALOG (Mentimeter-like list)
    # ==========================================
    if menu == "📚 Danh mục hoạt động":
        # Render list rows with counts + OPEN button
        rows = [
            ("1️⃣ Word Cloud (Từ khóa)", "Từ khóa / Word Cloud", cfg["wordcloud"]["title"]),
            ("2️⃣ Poll (Bình chọn)", "Bình chọn / Poll", cfg["poll"]["title"]),
            ("3️⃣ Open Ended (Hỏi đáp)", "Trả lời mở / Open Ended", cfg["openended"]["title"]),
            ("4️⃣ Scales (Thang đo)", "Thang đo / Scales", cfg["scales"]["title"]),
            ("5️⃣ Ranking (Xếp hạng)", "Xếp hạng / Ranking", cfg["ranking"]["title"]),
            ("6️⃣ Pin on Image (Ghim ảnh)", "Ghim trên ảnh / Pin", cfg["pin"]["title"]),
        ]

        for label, meta, title in rows:
            act_key = act_map[label]
            df_count = load_data(st.session_state['class_id'], act_key)
            count = len(df_count)

            left, right = st.columns([6, 1])
            with left:
                st.markdown(f"""
                <div class="activity-row">
                    <p class="activity-title">{title}</p>
                    <p class="activity-meta">
                        <span class="pill">{meta}</span>
                        Số lượt trả lời: <b>{count}</b>
                    </p>
                </div>
                """, unsafe_allow_html=True)
            with right:
                # IMPORTANT: unique key per button
                if st.button("MỞ", key=f"open_{st.session_state['class_id']}_{act_key}"):
                    st.session_state["menu"] = label
                    st.rerun()

        st.info("💡 Học viên bấm **MỞ** để trả lời. Giảng viên bấm **MỞ** để xem kết quả + dùng AI phân tích.")

    # ==========================================
    # DASHBOARD
    # ==========================================
    elif "Dashboard" in menu:
        cols = st.columns(3)
        activities = ["wordcloud", "poll", "openended", "scales", "ranking", "pin"]
        names = ["Word Cloud", "Poll", "Open Ended", "Scales", "Ranking", "Pin Image"]

        for i, act in enumerate(activities):
            df = load_data(st.session_state['class_id'], act)
            with cols[i % 3]:
                st.markdown(f"""
                <div class="viz-card" style="text-align:center;">
                    <h1 style="color:{PRIMARY_COLOR}; margin:0; font-size:40px;">{len(df)}</h1>
                    <p style="color:#64748b; font-weight:600; text-transform:uppercase;">{names[i]}</p>
                </div>
                """, unsafe_allow_html=True)

    # ==========================================
    # 1. WORD CLOUD
    # ==========================================
    elif "Word Cloud" in menu:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.info(f"Câu hỏi: **{cfg['wordcloud']['question']}**\n\nGợi ý: {cfg['wordcloud']['hint']}")
            if st.session_state['role'] == 'student':
                with st.form("f_wc"):
                    n = st.text_input("Tên:")
                    txt = st.text_input("Nhập 1 từ khóa:")
                    if st.form_submit_button("GỬI TỪ KHÓA"):
                        save_data(st.session_state['class_id'], current_act_key, n, txt)
                        st.success("Đã gửi!")
                        time.sleep(0.5)
                        st.rerun()
            else:
                st.warning("Giảng viên xem kết quả bên phải.")

        with c2:
            st.markdown("##### ☁️ KẾT QUẢ HIỂN THỊ")
            df = load_data(st.session_state['class_id'], current_act_key)
            with st.container(border=True):
                if not df.empty:
                    text = " ".join(df["Nội dung"].astype(str))
                    wc = WordCloud(width=800, height=400, background_color='white', colormap='ocean').generate(text)
                    fig, ax = plt.subplots()
                    ax.imshow(wc, interpolation='bilinear')
                    ax.axis("off")
                    st.pyplot(fig)
                else:
                    st.info("Chưa có dữ liệu. Mời lớp nhập từ khóa.")

    # ==========================================
    # 2. POLL
    # ==========================================
    elif "Poll" in menu:
        c1, c2 = st.columns([1, 2])
        options = cfg["poll"]["options"]
        with c1:
            st.info(f"Câu hỏi: **{cfg['poll']['question']}**")
            if st.session_state['role'] == 'student':
                with st.form("f_poll"):
                    n = st.text_input("Tên:")
                    vote = st.radio("Lựa chọn:", options)
                    if st.form_submit_button("BÌNH CHỌN"):
                        save_data(st.session_state['class_id'], current_act_key, n, vote)
                        st.success("Đã chọn!")
                        time.sleep(0.5)
                        st.rerun()

            # NEW: show answer key only to teacher
            if st.session_state["role"] == "teacher" and cfg["poll"]["correct"]:
                st.markdown("---")
                st.success(f"Đáp án gợi ý: **{cfg['poll']['correct']}**")
                if cfg["poll"]["explain"]:
                    st.caption(cfg["poll"]["explain"])

        with c2:
            st.markdown("##### 📊 THỐNG KÊ LỰA CHỌN")
            df = load_data(st.session_state['class_id'], current_act_key)
            with st.container(border=True):
                if not df.empty:
                    cnt = df["Nội dung"].value_counts().reset_index()
                    cnt.columns = ["Lựa chọn", "Số lượng"]
                    fig = px.bar(cnt, x="Lựa chọn", y="Số lượng", color="Lựa chọn", text_auto=True)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Chưa có bình chọn nào.")

    # ==========================================
    # 3. OPEN ENDED
    # ==========================================
    elif "Open Ended" in menu:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.info(f"**{cfg['openended']['question']}**")
            if st.session_state['role'] == 'student':
                with st.form("f_open"):
                    n = st.text_input("Tên:")
                    c = st.text_area("Câu trả lời của bạn:")
                    if st.form_submit_button("GỬI BÀI"):
                        save_data(st.session_state['class_id'], current_act_key, n, c)
                        st.success("Đã gửi!")
                        time.sleep(0.5)
                        st.rerun()

            if st.session_state["role"] == "teacher":
                with st.expander("🔑 Gợi ý chấm / định hướng đáp án", expanded=False):
                    st.write(cfg["openended"]["teacher_key"])

        with c2:
            st.markdown("##### 💬 BỨC TƯỜNG Ý KIẾN")
            df = load_data(st.session_state['class_id'], current_act_key)
            with st.container(border=True, height=500):
                if not df.empty:
                    for _, r in df.iterrows():
                        st.markdown(
                            f'<div class="note-card"><b>{r["Học viên"]}</b>: {r["Nội dung"]}</div>',
                            unsafe_allow_html=True
                        )
                else:
                    st.info("Sàn ý kiến trống.")

    # ==========================================
    # 4. SCALES
    # ==========================================
    elif "Scales" in menu:
        c1, c2 = st.columns([1, 2])
        criteria = cfg["scales"]["criteria"]
        with c1:
            st.info(f"**{cfg['scales']['question']}**")
            if st.session_state['role'] == 'student':
                with st.form("f_scale"):
                    n = st.text_input("Tên:")
                    scores = []
                    for cri in criteria:
                        scores.append(st.slider(cri, 1, 5, 3))
                    if st.form_submit_button("GỬI ĐÁNH GIÁ"):
                        val = ",".join(map(str, scores))
                        save_data(st.session_state['class_id'], current_act_key, n, val)
                        st.success("Đã lưu!")
                        time.sleep(0.5)
                        st.rerun()

        with c2:
            st.markdown("##### 🕸️ MẠNG NHỆN NĂNG LỰC")
            df = load_data(st.session_state['class_id'], current_act_key)
            with st.container(border=True):
                if not df.empty:
                    try:
                        data_matrix = []
                        for item in df["Nội dung"]:
                            data_matrix.append([int(x) for x in str(item).split(',')])
                        if len(data_matrix) > 0:
                            avg_scores = np.mean(data_matrix, axis=0)
                            fig = go.Figure(data=go.Scatterpolar(
                                r=avg_scores, theta=criteria, fill='toself', name='Lớp học'
                            ))
                            fig.update_layout(
                                polar=dict(radialaxis=dict(visible=True, range=[0, 5])),
                                showlegend=False
                            )
                            st.plotly_chart(fig, use_container_width=True)
                    except:
                        st.error("Dữ liệu lỗi định dạng.")
                else:
                    st.info("Chưa có dữ liệu thang đo.")

    # ==========================================
    # 5. RANKING
    # ==========================================
    elif "Ranking" in menu:
        c1, c2 = st.columns([1, 2])
        items = cfg["ranking"]["items"]
        with c1:
            st.info(f"**{cfg['ranking']['question']}**")
            if st.session_state['role'] == 'student':
                with st.form("f_rank"):
                    n = st.text_input("Tên:")
                    rank = st.multiselect("Thứ tự:", items)
                    if st.form_submit_button("NỘP BẢNG XẾP HẠNG"):
                        if len(rank) == len(items):
                            save_data(st.session_state['class_id'], current_act_key, n, "->".join(rank))
                            st.success("Đã nộp!")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.warning(f"Vui lòng chọn đủ {len(items)} mục.")

        with c2:
            st.markdown("##### 🏆 KẾT QUẢ XẾP HẠNG")
            df = load_data(st.session_state['class_id'], current_act_key)
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

                    fig = px.bar(x=vals, y=labels, orientation='h',
                                 labels={'x': 'Tổng điểm', 'y': 'Mục'}, text=vals)
                    fig.update_layout(yaxis={'categoryorder': 'total ascending'})
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Chưa có xếp hạng.")

    # ==========================================
    # 6. PIN ON IMAGE
    # ==========================================
    elif "Pin on Image" in menu:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.info(f"**{cfg['pin']['question']}**")
            if st.session_state['role'] == 'student':
                with st.form("f_pin"):
                    n = st.text_input("Tên:")
                    x_val = st.slider("Vị trí Ngang (Trái -> Phải)", 0, 100, 50)
                    y_val = st.slider("Vị trí Dọc (Dưới -> Trên)", 0, 100, 50)
                    if st.form_submit_button("GHIM VỊ TRÍ"):
                        save_data(st.session_state['class_id'], current_act_key, n, f"{x_val},{y_val}")
                        st.success("Đã ghim!")
                        time.sleep(0.5)
                        st.rerun()

        with c2:
            st.markdown("##### 📍 BẢN ĐỒ NHIỆT (HEATMAP)")
            df = load_data(st.session_state['class_id'], current_act_key)
            with st.container(border=True):
                if not df.empty:
                    try:
                        xs, ys = [], []
                        for item in df["Nội dung"]:
                            coords = str(item).split(',')
                            xs.append(int(coords[0]))
                            ys.append(int(coords[1]))

                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=xs, y=ys, mode='markers',
                            marker=dict(size=12, color='red', opacity=0.7,
                                        line=dict(width=1, color='white')),
                            name='Vị trí ghim'
                        ))

                        fig.update_layout(
                            xaxis=dict(range=[0, 100], showgrid=False, zeroline=False, visible=False),
                            yaxis=dict(range=[0, 100], showgrid=False, zeroline=False, visible=False),
                            images=[dict(
                                source=cfg["pin"]["image"],
                                xref="x", yref="y",
                                x=0, y=100, sizex=100, sizey=100,
                                sizing="stretch", layer="below"
                            )],
                            width=600, height=400, margin=dict(l=0, r=0, t=0, b=0)
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    except:
                        st.error("Lỗi dữ liệu ghim.")
                else:
                    st.info("Chưa có ghim nào.")

    # ==========================================
    # CONTROL PANEL CHO GIẢNG VIÊN (CHUNG CHO MỌI TAB)
    # ==========================================
    if st.session_state['role'] == 'teacher' and (menu not in ["📚 Danh mục hoạt động", "🏠 Dashboard"]):
        st.markdown("---")
        with st.expander("👮‍♂️ BẢNG ĐIỀU KHIỂN GIẢNG VIÊN (Dành riêng cho hoạt động này)", expanded=True):
            col_ai, col_reset = st.columns([3, 1])

            with col_ai:
                st.markdown("###### 🤖 AI Trợ giảng")
                prompt = st.text_input("Nhập lệnh cho AI:", placeholder=f"Ví dụ: Phân tích xu hướng của {menu}...")
                if st.button("PHÂN TÍCH NGAY") and prompt:
                    curr_df = load_data(st.session_state['class_id'], current_act_key)
                    if not curr_df.empty:
                        with st.spinner("AI đang suy nghĩ..."):
                            if model is None:
                                st.warning("Chưa cấu hình GEMINI_API_KEY trong secrets.")
                            else:
                                # Provide the class topic + activity config for better AI analysis
                                activity_cfg = cfg.get(current_act_key, {})
                                payload = {
                                    "topic": cfg["topic"],
                                    "activity": menu,
                                    "activity_cfg": activity_cfg,
                                    "data_preview": curr_df.to_dict(orient="records")[:200]
                                }
                                res = model.generate_content(
                                    f"Dữ liệu lớp học (JSON): {payload}. Yêu cầu giảng viên: {prompt}"
                                )
                                st.info(res.text)
                    else:
                        st.warning("Chưa có dữ liệu để phân tích.")

            with col_reset:
                st.markdown("###### 🗑 Xóa dữ liệu")
                if st.button(f"RESET {menu}", type="secondary"):
                    clear_activity(st.session_state['class_id'], current_act_key)
                    st.toast(f"Đã xóa sạch dữ liệu {menu}")
                    time.sleep(1)
                    st.rerun()
