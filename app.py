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
import random
import json
import re
import uuid

# ✅ Live refresh (thay cho st.autorefresh)
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# ✅ Helper mở "fullscreen" tương thích nhiều phiên bản Streamlit
_DIALOG_DECORATOR = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)

def open_wc_fullscreen_dialog(wc_html_fs: str, live: bool):
    """Mở dialog fullscreen cho wordcloud (tương thích Streamlit cũ/mới)."""
    if _DIALOG_DECORATOR is not None:
        @_DIALOG_DECORATOR("🖥 Fullscreen Wordcloud")
        def _inner():
            if live and st_autorefresh is not None:
                st_autorefresh(interval=1500, key="wc_live_refresh_modal")
            st.components.v1.html(wc_html_fs, height=760, scrolling=False)
            if st.button("ĐÓNG FULLSCREEN", key="wc_close_full"):
                st.session_state["wc_fullscreen"] = False
                st.rerun()
        _inner()
        return

    st.warning("Streamlit phiên bản hiện tại chưa hỗ trợ dialog/modal. Đang dùng chế độ hiển thị thay thế.")
    if live and st_autorefresh is not None:
        st_autorefresh(interval=1500, key="wc_live_refresh_modal_fallback")
    st.components.v1.html(wc_html_fs, height=760, scrolling=False)
    if st.button("ĐÓNG FULLSCREEN", key="wc_close_full"):
        st.session_state["wc_fullscreen"] = False
        st.rerun()
def open_poll_fullscreen_dialog(fig):
    """Mở dialog fullscreen cho biểu đồ Poll (tương thích Streamlit cũ/mới)."""
    if _DIALOG_DECORATOR is not None:
        @_DIALOG_DECORATOR("🖥 Fullscreen Poll")
        def _inner():
            st.plotly_chart(fig, use_container_width=True)
            if st.button("ĐÓNG FULLSCREEN", key="poll_close_full"):
                st.session_state["poll_fullscreen"] = False
                st.rerun()
        _inner()
        return

    st.warning("Streamlit phiên bản hiện tại chưa hỗ trợ dialog/modal. Đang dùng chế độ hiển thị thay thế.")
    st.plotly_chart(fig, use_container_width=True)
    if st.button("ĐÓNG FULLSCREEN", key="poll_close_full_fallback"):
        st.session_state["poll_fullscreen"] = False
        st.rerun()
def open_openended_fullscreen_dialog(title: str, df_wall: pd.DataFrame, model, analysis_prompt_default: str):
    """Fullscreen cho bức tường Open Ended, kèm nút AI phân tích (tương thích Streamlit cũ/mới)."""
    def _render_wall():
                # ✅ ÉP dialog Open Ended fullscreen (gần full màn hình) + font lớn để nhìn xa
        st.markdown("""
        <style>
        /* 1) Ép Dialog/Modal rộng – cao gần full màn hình */
        [data-testid="stDialog"] > div[role="dialog"],
        div[role="dialog"]{
            width: 95vw !important;
            max-width: 95vw !important;
            height: 95vh !important;
            max-height: 95vh !important;
        }

        /* 2) Ép nội dung trong dialog dùng hết chiều cao + scroll nếu dài */
        [data-testid="stDialog"] div[role="dialog"] > div{
            height: 95vh !important;
            max-height: 95vh !important;
            overflow: auto !important;
        }

        /* 3) Tăng cỡ chữ trong fullscreen Open Ended */
        [data-testid="stDialog"] .note-card,
        div[role="dialog"] .note-card{
            font-size: 35px !important;
            line-height: 1.25 !important;
        }

        /* 4) Tăng chữ tiêu đề và các label trong dialog */
        [data-testid="stDialog"] h3, 
        [data-testid="stDialog"] h4,
        [data-testid="stDialog"] p,
        [data-testid="stDialog"] span,
        div[role="dialog"] h3,
        div[role="dialog"] h4,
        div[role="dialog"] p,
        div[role="dialog"] span{
            font-size: 35px !important;
        }
                /* ================================
           FORCE FONT SIZE FOR OPEN ENDED
           (ĐỌC XA – TRÌNH CHIẾU)
        ================================ */
        
        /* Bản thân khung */
        .note-card{
            font-size: 34px !important;
            line-height: 1.35 !important;
            font-weight: 600;
        }
        
        /* TẤT CẢ nội dung con bên trong */
        .note-card *,
        .note-card p,
        .note-card span,
        .note-card div,
        .note-card li,
        .note-card strong,
        .note-card em{
            font-size: 34px !important;
            line-height: 1.35 !important;
        }
        
        /* Tên học viên (đậm hơn, to hơn chút) */
        .note-card b{
            font-size: 36px !important;
            font-weight: 800 !important;
        }
        /* ===== FOOTER CHỐNG RỚT CHỮ (MOBILE SAFE) ===== */
        .login-footer{
          margin-top: 34px;
          padding-top: 18px;
          border-top: 1px solid #f0f0f0;
          text-align: center;
          color: #94a3b8;
          font-family: 'Inter', sans-serif;
        }
        .login-footer .f1{
          font-size: 12px;
          font-weight: 700;
          color:#64748b;
          line-height: 1.25;
        }
        .login-footer .f2{
          font-size: 12px;
          font-weight: 600;
          color:#94a3b8;
          line-height: 1.25;
        }
        
        @media (max-width: 600px){
          .login-footer{
            margin-top: 22px;
            padding-top: 14px;
          }
          .login-footer .f1,
          .login-footer .f2{
            font-size: 11px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
        }

        </style>
        """, unsafe_allow_html=True)

        st.markdown(f"### 💬 {title}")
        if df_wall is None or df_wall.empty:
            st.info("Chưa có câu trả lời.")
        else:
            with st.container(border=True, height=820):
                for _, r in df_wall.iterrows():
                    st.markdown(
                        f'<div class="note-card"><b>{r["Học viên"]}</b>: {r["Nội dung"]}</div>',
                        unsafe_allow_html=True
                    )

        st.markdown("---")
        st.markdown("#### 🤖 AI phân tích (toàn bộ ý kiến của câu này)")
        user_prompt = st.text_input("Yêu cầu phân tích", value=analysis_prompt_default, key="oe_fs_ai_prompt")
        if st.button("PHÂN TÍCH NGAY", key="oe_fs_ai_btn"):
            if df_wall is None or df_wall.empty:
                st.warning("Chưa có dữ liệu để phân tích.")
            elif model is None:
                st.warning("Chưa cấu hình GEMINI_API_KEY trong st.secrets.")
            elif not str(user_prompt).strip():
                st.warning("Vui lòng nhập yêu cầu phân tích.")
            else:
                with st.spinner("AI đang phân tích..."):
                    payload = f"""
Bạn là trợ giảng cho giảng viên. Đây là toàn bộ ý kiến học viên của hoạt động Open Ended.

TIÊU ĐỀ / CÂU HỎI:
{title}

DỮ LIỆU (bảng):
{df_wall.to_string(index=False)}

YÊU CẦU PHÂN TÍCH:
{user_prompt}

Hãy trả lời theo cấu trúc:
1) Tóm tắt chủ đề nổi bật (3–5 ý)
2) Phân loại lập luận (đúng/thiếu/nhầm, hoặc các nhóm quan điểm)
3) Trích dẫn minh họa (trích ngắn, nêu tên học viên)
4) Gợi ý can thiệp sư phạm (3 gợi ý)
5) 3 câu hỏi gợi mở để thảo luận tiếp
"""
                    res = model.generate_content(payload)
                    st.info(res.text)

    if _DIALOG_DECORATOR is not None:
        @_DIALOG_DECORATOR("🖥 Fullscreen Open Ended")
        def _inner():
            _render_wall()
            if st.button("ĐÓNG FULLSCREEN", key="oe_close_full"):
                st.session_state["oe_fullscreen"] = False
                st.rerun()
        _inner()
        return

    st.warning("Streamlit phiên bản hiện tại chưa hỗ trợ dialog/modal. Đang dùng chế độ hiển thị thay thế.")
    _render_wall()
    if st.button("ĐÓNG FULLSCREEN", key="oe_close_full_fallback"):
        st.session_state["oe_fullscreen"] = False
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
# --- DÁN ĐOẠN NÀY VÀO DÒNG 244 ---
st.markdown("""
    <style>
        /* Đổi màu nền chính sang màu tối chuyên nghiệp */
        .stApp {
            background-color: #0f172a !important;
            color: #f1f5f9 !important;
        }

        /* Tùy chỉnh Sidebar */
        [data-testid="stSidebar"] {
            background-color: #1e293b !important;
        }

        /* Làm các nút bấm đẹp hơn (bo góc, đổi màu) */
        div.stButton > button {
            background-color: #006a4e !important; /* Dùng màu PRIMARY_COLOR của bạn */
            color: white !important;
            border-radius: 12px !important;
            border: none !important;
            height: 3em !important;
            font-weight: 600 !important;
        }
        
        /* Hiệu ứng khi di chuột qua nút */
        div.stButton > button:hover {
            border: 1px solid #006a4e !important;
            color: #006a4e !important;
            background-color: white !important;
        }
    </style>
    """, unsafe_allow_html=True)
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

    /* =========================
       GLOBAL: FULLSCREEN 16:9 + BIG FONTS (>=35)
       ========================= */
    html {{
        font-size: 36px; /* ✅ toàn bộ chữ >= 35 */
    }}

    html, body, [class*="css"] {{
        font-family: 'Montserrat', sans-serif;
        background-color: {BG_COLOR};
        color: {TEXT_COLOR};
        font-size: 36px; /* ✅ áp dụng mạnh */
        line-height: 1.25;
    }}

    /* ✅ Full-width / full-screen (tối ưu trình chiếu 16:9) */
    .block-container {{
        max-width: 100% !important;
        padding-top: 0.6rem !important;
        padding-bottom: 0.6rem !important;
        padding-left: 1.0rem !important;
        padding-right: 1.0rem !important;
    }}

    /* Ẩn header/footer mặc định */
    header {{
    visibility: hidden;
    height: 0px !important;
}}
    /* XÓA KHOẢNG TRỐNG ĐẦU TRANG */
    .block-container {{
        padding-top: 0rem !important;
    }}
    /* XÓA CONTAINER RỖNG ĐẦU TIÊN (HAY GÂY VỆT TRẮNG) */
    .block-container > div:first-child {{
        margin-top: 0 !important;
        padding-top: 0 !important;
    }}
    footer {{visibility: hidden;}}

    /* =========================
       STREAMLIT NATIVE TEXT OVERRIDES
       ========================= */
    /* Labels / captions / help text */
    label, .stMarkdown, .stText, .stCaption, p, span, div {{
        font-size: 36px !important;
    }}

    /* Caption containers (st.caption) */
    [data-testid="stCaptionContainer"] p {{
        font-size: 35px !important;
        line-height: 1.25 !important;
    }}

    /* Metric-like */
    [data-testid="stMetricValue"] {{
        font-size: 56px !important;
        font-weight: 900 !important;
    }}
    [data-testid="stMetricLabel"] {{
        font-size: 35px !important;
        font-weight: 800 !important;
    }}

    /* Tabs */
    button[data-baseweb="tab"] {{
        font-size: 36px !important;
        font-weight: 900 !important;
        padding: 16px 18px !important;
    }}

    /* Inputs / Selects / Radios / Sliders */
    .stTextInput input, .stTextArea textarea {{
        border: 2px solid #e2e8f0; border-radius: 16px;
        padding: 18px 18px !important;
        font-size: 36px !important;
        line-height: 1.25 !important;
    }}

    [data-baseweb="select"] * {{
        font-size: 36px !important;
    }}

    [data-testid="stRadio"] * {{
        font-size: 36px !important;
    }}

    [data-testid="stSlider"] * {{
        font-size: 36px !important;
    }}

    /* Buttons */
    div.stButton > button {{
        background-color: {PRIMARY_COLOR}; color: white; border: none;
        border-radius: 18px;
        padding: 18px 18px !important;
        font-weight: 900 !important;
        letter-spacing: 0.5px;
        width: 100%;
        font-size: 36px !important;
        box-shadow: 0 10px 26px rgba(0, 106, 78, 0.22);
    }}
    div.stButton > button:hover {{ background-color: #00503a; transform: translateY(-1px); }}

    /* Expander */
    details summary {{
        font-size: 36px !important;
        font-weight: 900 !important;
    }}

    /* Dataframe (tăng font) */
    .stDataFrame, .stDataFrame * {{
        font-size: 32px !important; /* gần 35, nhưng bảng thường dày chữ; vẫn đảm bảo dễ đọc */
    }}

    /* =========================
       HERO / LOGIN
       ========================= */
    .hero-wrap {{
        max-width: 100% !important;
        margin: 0 auto;
        padding: 12px 10px 10px 10px;
    }}
    .hero-card {{
        background: white;
        border-radius: 26px;
        box-shadow: 0 18px 55px rgba(0,0,0,0.10);
        overflow: hidden;
        border: 1px solid #e2e8f0;
    }}
    .hero-top {{
        background: linear-gradient(135deg, rgba(0,106,78,0.12), rgba(0,106,78,0.03));
        padding: 28px 28px 22px 28px;
        border-bottom: 1px solid #e2e8f0;
        display:flex;
        gap:22px;
        align-items:center;
    }}
    .hero-badge {{
        width: 96px; height: 96px;
        border-radius: 20px;
        background: white;
        border: 1px solid #e2e8f0;
        display:flex;
        align-items:center;
        justify-content:center;
        box-shadow: 0 8px 25px rgba(0,0,0,0.06);
        flex: 0 0 auto;
    }}
    .hero-title {{
        font-weight: 900;
        color: {PRIMARY_COLOR};
        font-size: 44px; /* ✅ >=35 */
        line-height: 1.15;
        margin: 0;
        word-break: break-word;
    }}
    .hero-sub {{
        color: {MUTED};
        font-weight: 800;
        margin-top: 10px;
        margin-bottom: 0;
        font-size: 36px; /* ✅ */
    }}
    .hero-body {{
        padding: 22px 28px 26px 28px;
    }}
    .hero-meta {{
        background:#f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 18px 18px;
        color:#334155;
        font-size: 36px; /* ✅ */
        margin-bottom: 12px;
    }}

    /* =========================
       VIZ CARD
       ========================= */
    .viz-card {{
        background: white;
        padding: 26px;
        border-radius: 20px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        margin-bottom: 18px;
        border: 1px solid #e2e8f0;
    }}

    /* NOTE CARD */
    .note-card {{
        background: #fff;
        padding: 18px;
        border-radius: 16px;
        border-left: 7px solid {PRIMARY_COLOR};
        margin-bottom: 14px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        font-size: 36px; /* ✅ */
        line-height: 1.25;
    }}

    /* SIDEBAR */
    [data-testid="stSidebar"] {{ background-color: #111827; }}
    [data-testid="stSidebar"] * {{ color: #ffffff; font-size: 34px !important; }} /* sidebar vẫn lớn */

    /* =========================
       CLASS HOME (Gradescope-ish list) - FULL WIDTH
       ========================= */
    .list-wrap {{
        background: transparent;
        max-width: 100% !important; /* ✅ full */
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
        font-size: 44px; /* ✅ */
        font-weight: 900;
        color: #0f172a;
        margin: 0;
    }}
    .list-sub {{
        margin: 10px 0 0 0;
        color: {MUTED};
        font-weight: 800;
        font-size: 35px; /* ✅ */
    }}
    .act-row {{
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 20px;
        padding: 18px 18px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.06);
        margin-bottom: 14px;
    }}
    .act-name {{
        font-weight: 900;
        font-size: 38px; /* ✅ */
        margin: 0 0 8px 0;
        color: #0f172a;
    }}
    .act-meta {{
        margin: 0;
        color: {MUTED};
        font-weight: 800;
        font-size: 35px; /* ✅ */
        line-height: 1.25;
    }}

    /* ✅ toolbar wordcloud */
    .wc-toolbar {{
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:10px;
        margin: 10px 0 12px 0;
        padding: 12px 12px;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        background: #fff;
    }}
    .wc-toolbar small {{
        color: {MUTED};
        font-weight: 800;
        font-size: 35px; /* ✅ */
    }}

    /* ✅ Plotly container: ưu tiên dùng hết chiều ngang */
    [data-testid="stPlotlyChart"] {{
        width: 100% !important;
    }}
    /* =========================
       MOBILE OVERRIDES (<= 600px)
       Mục tiêu: dễ thao tác, không cần zoom, không gây reload
       ========================= */
    @media (max-width: 600px){{
      html {{ font-size: 16px !important; }}
      html, body, [class*="css"]{{
        font-size: 16px !important;
        line-height: 1.35 !important;
      }}
    
      /* Giảm padding khung chính để khỏi “phình” */
      .block-container{{
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
        padding-top: 0.6rem !important;
        padding-bottom: 0.6rem !important;
      }}
    
      /* Text/label tổng quát */
      label, .stMarkdown, .stText, .stCaption, p, span, div{{
        font-size: 16px !important;
      }}
    
      /* Inputs */
      .stTextInput input, .stTextArea textarea{{
        font-size: 16px !important;
        padding: 12px 12px !important;
        border-radius: 12px !important;
      }}
    
      /* Select */
      [data-baseweb="select"] *{{
        font-size: 16px !important;
      }}
    
      /* Tabs */
      button[data-baseweb="tab"]{{
        font-size: 16px !important;
        padding: 10px 12px !important;
      }}
    
      /* Buttons */
      div.stButton > button{{
        font-size: 16px !important;
        padding: 12px 12px !important;
        border-radius: 14px !important;
        box-shadow: none !important; /* mobile nhẹ, tránh giật */
      }}
    
      /* Note cards (OpenEnded) */
      .note-card, .note-card *{{
        font-size: 16px !important;
        line-height: 1.35 !important;
      }}
    
      /* Dataframe */
      .stDataFrame, .stDataFrame *{{
        font-size: 14px !important;
      }}
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
# device_id: định danh máy/trình duyệt (mỗi máy 1 lần vote)
if "device_id" not in st.session_state:
    st.session_state["device_id"] = str(uuid.uuid4())
# page routing: login | class_home | activity | dashboard
if "page" not in st.session_state:
    st.session_state["page"] = "login"

# which activity
if "current_act_key" not in st.session_state:
    st.session_state["current_act_key"] = "dashboard"

# fullscreen state
if "wc_fullscreen" not in st.session_state:
    st.session_state["wc_fullscreen"] = False
if "poll_fullscreen" not in st.session_state:
    st.session_state["poll_fullscreen"] = False
if "oe_fullscreen" not in st.session_state:
    st.session_state["oe_fullscreen"] = False
# -------------------------------
# PATH HELPERS
# -------------------------------
def get_path(cls, act, suffix: str = ""):
    # suffix dùng cho wordcloud theo câu hỏi (qid)
    suffix = str(suffix or "").strip()
    if suffix:
        return f"data_{cls}_{act}_{suffix}.csv"
    return f"data_{cls}_{act}.csv"

def save_data(cls, act, name, content, suffix: str = ""):
    content = str(content).replace("|", "-").replace("\n", " ")
    name = str(name).replace("|", "-").replace("\n", " ")
    timestamp = datetime.now().strftime("%H:%M:%S")
    row = f"{name}|{content}|{timestamp}\n"
    with data_lock:
        with open(get_path(cls, act, suffix=suffix), "a", encoding="utf-8") as f:
            f.write(row)

def load_data(cls, act, suffix: str = ""):
    path = get_path(cls, act, suffix=suffix)
    if os.path.exists(path):
        try:
            df = pd.read_csv(
                path,
                sep="|",
                header=None,
                names=["Học viên", "Nội dung", "Thời gian"],
                dtype=str,
                engine="python",
                on_bad_lines="skip",
            )
            for c in ["Học viên", "Nội dung", "Thời gian"]:
                if c not in df.columns:
                    df[c] = ""
            return df[["Học viên", "Nội dung", "Thời gian"]]
        except Exception:
            return pd.DataFrame(columns=["Học viên", "Nội dung", "Thời gian"])
    return pd.DataFrame(columns=["Học viên", "Nội dung", "Thời gian"])

def clear_activity(cls, act, suffix: str = ""):
    with data_lock:
        path = get_path(cls, act, suffix=suffix)
        if os.path.exists(path):
            os.remove(path)
# =========================
# LOGIN TOKEN STORE (ANTI-REFRESH LOGOUT)
# =========================
TOKEN_STORE_PATH = "login_tokens.json"

def _load_tokens() -> dict:
    if not os.path.exists(TOKEN_STORE_PATH):
        return {}
    try:
        with open(TOKEN_STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _save_tokens(tokens: dict):
    try:
        with data_lock:
            with open(TOKEN_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(tokens, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def issue_login_token(role: str, cid: str, ttl_hours: int = 12) -> str:
    tok = str(uuid.uuid4())
    exp = time.time() + ttl_hours * 3600
    tokens = _load_tokens()
    tokens[tok] = {"role": role, "class_id": cid, "exp": exp}
    _save_tokens(tokens)
    return tok

def validate_login_token(tok: str) -> dict | None:
    tok = str(tok or "").strip()
    if not tok:
        return None
    tokens = _load_tokens()
    info = tokens.get(tok)
    if not info:
        return None
    try:
        if float(info.get("exp", 0)) < time.time():
            # hết hạn thì xóa
            tokens.pop(tok, None)
            _save_tokens(tokens)
            return None
    except Exception:
        return None
    return info
# =========================
# POLL: 1 DEVICE = 1 VOTE
# =========================
def poll_vote_lock_path(cid: str) -> str:
    # lưu danh sách device_id đã vote theo lớp
    return f"poll_votelock_{cid}.txt"

def poll_has_voted(cid: str, device_id: str) -> bool:
    if not device_id:
        return False
    path = poll_vote_lock_path(cid)
    if not os.path.exists(path):
        return False
    try:
        with data_lock:
            with open(path, "r", encoding="utf-8") as f:
                voted = {line.strip() for line in f if line.strip()}
        return device_id.strip() in voted
    except Exception:
        return False

def poll_mark_voted(cid: str, device_id: str):
    if not device_id:
        return
    path = poll_vote_lock_path(cid)
    try:
        with data_lock:
            # tránh ghi trùng
            existing = set()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    existing = {line.strip() for line in f if line.strip()}
            if device_id.strip() in existing:
                return
            with open(path, "a", encoding="utf-8") as f:
                f.write(device_id.strip() + "\n")
    except Exception:
        pass
def reset_to_login():
    st.session_state.clear()
    st.rerun()
# =========================
# QUERY PARAM HELPERS (GLOBAL)
# =========================
def qp_get(key: str, default: str = "") -> str:
    try:
        v = st.query_params.get(key, None)
        if v is None:
            return default
        if isinstance(v, list):
            return v[0] if v else default
        return str(v)
    except Exception:
        q = st.experimental_get_query_params()
        return q.get(key, [default])[0]

def qp_set(**kwargs):
    try:
        for k, v in kwargs.items():
            st.query_params[k] = str(v)
    except Exception:
        st.experimental_set_query_params(**{k: str(v) for k, v in kwargs.items()})

def qp_clear():
    try:
        st.query_params.clear()
    except Exception:
        st.experimental_set_query_params()
# ==========================================
# 3. CẤU HÌNH HOẠT ĐỘNG THEO LỚP
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
# 3.1. WORDCLOUD QUESTION BANK (MỚI)
# ==========================================
def wc_bank_path(cid: str) -> str:
    return f"wc_questions_{cid}.json"

def _wc_seed_default_questions(cid: str):
    # seed 1 câu mặc định từ config hiện có
    default_q = CLASS_ACT_CONFIG[cid]["wordcloud"]["question"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    qid = "Q1"
    bank = {
        "active_id": qid,
        "questions": [
            {"id": qid, "text": default_q, "created_at": now, "updated_at": now}
        ]
    }
    return bank

def load_wc_bank(cid: str):
    path = wc_bank_path(cid)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                bank = json.load(f)
            if "questions" not in bank or not isinstance(bank["questions"], list):
                bank = _wc_seed_default_questions(cid)
            if not bank.get("questions"):
                bank = _wc_seed_default_questions(cid)
            # ensure active exists
            active_id = bank.get("active_id")
            ids = {q.get("id") for q in bank["questions"]}
            if active_id not in ids:
                bank["active_id"] = bank["questions"][0].get("id", "Q1")
            return bank
        except Exception:
            return _wc_seed_default_questions(cid)
    return _wc_seed_default_questions(cid)

def save_wc_bank(cid: str, bank: dict):
    try:
        with data_lock:
            with open(wc_bank_path(cid), "w", encoding="utf-8") as f:
                json.dump(bank, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def wc_get_active_question(cid: str, bank: dict):
    aid = bank.get("active_id")
    for q in bank.get("questions", []):
        if q.get("id") == aid:
            return q
    # fallback
    qs = bank.get("questions", [])
    return qs[0] if qs else {"id": "Q1", "text": CLASS_ACT_CONFIG[cid]["wordcloud"]["question"]}

def wc_make_new_id(bank: dict) -> str:
    # Q{n+1} ổn định, dễ nhìn
    qs = bank.get("questions", [])
    nums = []
    for q in qs:
        m = re.match(r"^Q(\d+)$", str(q.get("id", "")).strip(), flags=re.I)
        if m:
            nums.append(int(m.group(1)))
    nxt = (max(nums) + 1) if nums else 2
    return f"Q{nxt}"

def wc_count_answers(cid: str, qid: str) -> int:
    df = load_data(cid, "wordcloud", suffix=qid)
    return int(len(df)) if df is not None else 0
# ==========================================
# 3.1b. WORDCLOUD PROMPT BANK (MỚI)
#   - lưu prompt theo từng câu hỏi (qid)
# ==========================================
def wc_prompt_bank_path(cid: str) -> str:
    return f"wc_prompts_{cid}.json"

def _wc_prompt_seed_default() -> dict:
    # cấu trúc: { "<QID>": ["prompt1", "prompt2", ...], ... }
    return {}

def load_wc_prompts(cid: str) -> dict:
    path = wc_prompt_bank_path(cid)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else _wc_prompt_seed_default()
        except Exception:
            return _wc_prompt_seed_default()
    return _wc_prompt_seed_default()

def save_wc_prompts(cid: str, data: dict):
    try:
        with data_lock:
            with open(wc_prompt_bank_path(cid), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def wc_get_prompts_for_qid(cid: str, qid: str) -> list:
    bank = load_wc_prompts(cid)
    prompts = bank.get(str(qid), [])
    return prompts if isinstance(prompts, list) else []

def wc_add_prompt(cid: str, qid: str, prompt: str):
    prompt = str(prompt or "").strip()
    if not prompt:
        return
    bank = load_wc_prompts(cid)
    qid = str(qid)
    bank.setdefault(qid, [])
    # tránh trùng y hệt
    if prompt not in bank[qid]:
        bank[qid].append(prompt)
    save_wc_prompts(cid, bank)

def wc_delete_prompt(cid: str, qid: str, prompt: str):
    bank = load_wc_prompts(cid)
    qid = str(qid)
    if qid in bank and isinstance(bank[qid], list):
        bank[qid] = [p for p in bank[qid] if p != prompt]
        save_wc_prompts(cid, bank)

def wc_update_prompt(cid: str, qid: str, old_prompt: str, new_prompt: str):
    new_prompt = str(new_prompt or "").strip()
    if not new_prompt:
        return
    bank = load_wc_prompts(cid)
    qid = str(qid)
    if qid in bank and isinstance(bank[qid], list):
        bank[qid] = [new_prompt if p == old_prompt else p for p in bank[qid]]
        # loại trùng sau khi sửa
        dedup = []
        for p in bank[qid]:
            if p not in dedup:
                dedup.append(p)
        bank[qid] = dedup
        save_wc_prompts(cid, bank)

# ==========================================
# 3.2. OPEN ENDED QUESTION BANK (MỚI)
# ==========================================
def oe_bank_path(cid: str) -> str:
    return f"oe_questions_{cid}.json"

def _oe_seed_default_questions(cid: str):
    default_q = CLASS_ACT_CONFIG[cid]["openended"]["question"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    qid = "Q1"
    bank = {
        "active_id": qid,
        "questions": [
            {"id": qid, "text": default_q, "created_at": now, "updated_at": now}
        ]
    }
    return bank

def load_oe_bank(cid: str):
    path = oe_bank_path(cid)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                bank = json.load(f)
            if "questions" not in bank or not isinstance(bank["questions"], list) or not bank["questions"]:
                bank = _oe_seed_default_questions(cid)
            active_id = bank.get("active_id")
            ids = {q.get("id") for q in bank["questions"]}
            if active_id not in ids:
                bank["active_id"] = bank["questions"][0].get("id", "Q1")
            return bank
        except Exception:
            return _oe_seed_default_questions(cid)
    return _oe_seed_default_questions(cid)

def save_oe_bank(cid: str, bank: dict):
    try:
        with data_lock:
            with open(oe_bank_path(cid), "w", encoding="utf-8") as f:
                json.dump(bank, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def oe_get_active_question(cid: str, bank: dict):
    aid = bank.get("active_id")
    for q in bank.get("questions", []):
        if q.get("id") == aid:
            return q
    qs = bank.get("questions", [])
    return qs[0] if qs else {"id": "Q1", "text": CLASS_ACT_CONFIG[cid]["openended"]["question"]}

def oe_make_new_id(bank: dict) -> str:
    qs = bank.get("questions", [])
    nums = []
    for q in qs:
        m = re.match(r"^Q(\d+)$", str(q.get("id", "")).strip(), flags=re.I)
        if m:
            nums.append(int(m.group(1)))
    nxt = (max(nums) + 1) if nums else 2
    return f"Q{nxt}"
def oe_count_answers(cid: str, qid: str) -> int:
    df = load_data(cid, "openended", suffix=qid)
    return int(len(df)) if df is not None else 0
# ==========================================
# 4. MÀN HÌNH ĐĂNG NHẬP (MCKINSEY V3 - MOBILE FIX)
# ==========================================
# =========================
# AUTO RESTORE SESSION FROM URL TOKEN (LIKE MENTIMETER)
# =========================
if not st.session_state.get("logged_in", False):
    tok = qp_get("t", "")
    info = validate_login_token(tok)
    if info:
        st.session_state.update({
            "logged_in": True,
            "role": info.get("role", ""),
            "class_id": info.get("class_id", ""),
            "page": "class_home"
        })
if (not st.session_state.get("logged_in", False)) or (st.session_state.get("page", "login") == "login"):
    st.session_state["page"] = "login"

    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Inter:wght@400;600;700&display=swap');

        /* ---- Global reset chống tràn ngang trên mobile ---- */
        html, body, .stApp {{
            background-color: #f2f4f8;
            overflow-x: hidden !important;
        }}
        .block-container {{
            padding-top: 5vh !important;
            max-width: 1100px !important;   /* desktop vừa đẹp */
            padding-left: 16px !important;  /* tránh sát mép */
            padding-right: 16px !important;
        }}
        [data-testid="stHeader"], footer {{ display: none; }}

        /* ---- Wrapper tự quản (không phụ thuộc column nth-of-type) ---- */
        .login-shell {{
            width: 100%;
            display: flex;
            justify-content: center;
        }}
        .login-card {{
            width: 100%;
            max-width: 560px;
            background: #ffffff;
            padding: 50px 40px;
            border-radius: 0px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.08);
            border-top: 6px solid #b71c1c;
            box-sizing: border-box;
        }}

        /* ---- Brand ---- */
        .brand-container {{
            text-align: center;
            margin-bottom: 34px;
        }}
        .brand-logo {{
            width: 130px;
            height: auto;
            margin-bottom: 18px;
        }}
        .uni-vn {{
            font-family: 'Playfair Display', serif;
            color: #111111;
            font-size: 26px;
            font-weight: 900;
            text-transform: uppercase;
            line-height: 1.25;
            margin: 0 0 6px 0;

            /* chống “rớt chữ” + chống tràn ngang */
            word-break: break-word;
            overflow-wrap: anywhere;
        }}
        .uni-en {{
            font-family: 'Inter', sans-serif;
            color: #555555;
            font-size: 14px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin: 0;
        }}

        /* ---- Tabs (streamlit) ---- */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 0px;
            margin-bottom: 22px;
            border-bottom: 2px solid #eeeeee;

            /* quan trọng: không cho tab-list tạo overflow ngang */
            flex-wrap: nowrap;
            overflow-x: hidden;
        }}
        .stTabs [data-baseweb="tab"] {{
            flex: 1;
            text-align: center;
            padding: 14px 6px;
            background: white;
            border: none;
            color: #888;
            font-family: 'Inter', sans-serif;
            font-weight: 700;
            font-size: 14px;
            min-width: 0; /* tránh tab tự kéo rộng */
        }}
        .stTabs [aria-selected="true"] {{
            color: #b71c1c !important;
            border-bottom: 4px solid #b71c1c !important;
        }}

        /* ---- Inputs / Select ---- */
        .stTextInput label, .stSelectbox label {{
            font-family: 'Inter', sans-serif;
            font-size: 14px;
            color: #333;
            font-weight: 700;
        }}
        .stTextInput input {{
            border-radius: 0px;
            border: 1px solid #ccc;
            padding: 14px 14px;
            font-size: 16px;
            color: #000;
            background: #fff;
            width: 100%;
            box-sizing: border-box;
        }}
        .stTextInput input:focus {{
            border-color: #000;
            box-shadow: none;
        }}

        /* ---- Buttons ---- */
        div.stButton > button {{
            width: 100%;
            background-color: #b71c1c;
            color: white;
            border-radius: 0px;
            font-family: 'Inter', sans-serif;
            font-weight: 800;
            text-transform: uppercase;
            padding: 16px;
            font-size: 15px;
            border: none;
            margin-top: 18px;
            transition: 0.3s;
        }}
        div.stButton > button:hover {{
            background-color: #8a0c1a;
        }}

        /* ---- Footer ---- */
        .login-footer {{
            margin-top: 34px;
            padding-top: 18px;
            border-top: 1px solid #f0f0f0;
            text-align: center;
            color: #999;
            font-size: 12px;
            font-family: 'Inter', sans-serif;
        }}
        .login-footer b {{ color: #555; }}

        /* ---- Mobile: card full width, padding nhỏ lại, font giảm, tuyệt đối không tràn ngang ---- */
        @media (max-width: 600px) {{
            .block-container {{
                padding-top: 18px !important;
                padding-left: 10px !important;
                padding-right: 10px !important;
                max-width: 100% !important;
            }}
            .login-card {{
                max-width: 100%;
                padding: 26px 18px;
            }}
            .brand-logo {{
                width: 110px;
            }}
            .uni-vn {{
                font-size: 20px;
                letter-spacing: 0.2px;
            }}
            .uni-en {{
                font-size: 12px;
                letter-spacing: 0.6px;
            }}
        }}
        /* ===== SEGMENTED RADIO (THAY TAB – MOBILE SAFE) ===== */
        div[role="radiogroup"]{{
          display:flex;
          gap:10px;
          justify-content:center;
          margin-bottom: 18px;
        }}
        div[role="radiogroup"] label{{
          border: 1px solid #e2e8f0 !important;
          padding: 10px 14px !important;
          border-radius: 999px !important;
          background: #fff !important;
          font-family: 'Inter', sans-serif !important;
          font-weight: 800 !important;
          color: #64748b !important;
        }}
        div[role="radiogroup"] label:has(input:checked){{
          border-color: #b71c1c !important;
          color: #b71c1c !important;
          background: rgba(183,28,28,0.06) !important;
        }}
    </style>
    """, unsafe_allow_html=True)

    # ---- Wrapper mở ----
    st.markdown("<div class='login-shell'><div class='login-card'>", unsafe_allow_html=True)

    # HEADER
    st.markdown(f"""
        <div class="brand-container">
            <img src="{LOGO_URL}" class="brand-logo">
            <div class="uni-vn">TRƯỜNG ĐẠI HỌC CẢNH SÁT NHÂN DÂN</div>
            <div class="uni-en">People's Police University</div>
        </div>
    """, unsafe_allow_html=True)
    # ===== CHỌN CỔNG ĐĂNG NHẬP (MOBILE-FIRST) =====
    portal = st.radio(
        "Chọn cổng đăng nhập",
        ["Học viên", "Giảng viên"],
        horizontal=True,
        label_visibility="collapsed",
        key="portal_mode"
    )
    
    st.write("")
    
    if portal == "Học viên":
        c_class = st.selectbox("Lớp học phần", list(CLASSES.keys()), key="mck_s_class")
        c_pass = st.text_input(
            "Mã bảo mật",
            type="password",
            placeholder="Nhập mã lớp...",
            key="mck_s_pass"
        )
    
        st.markdown(
            '<div style="margin-top:10px; font-size:13px; font-family:Inter; color:#555;">'
            '<input type="checkbox" checked style="accent-color:#b71c1c"> Ghi nhớ đăng nhập</div>',
            unsafe_allow_html=True
        )
    
        if st.button("ĐĂNG NHẬP", key="mck_btn_s"):
            cid = CLASSES[c_class]
            if c_pass.strip() == PASSWORDS[cid]:
                tok = issue_login_token("student", cid, ttl_hours=12)
                qp_set(t=tok)  # giữ token qua refresh
                st.session_state.update({
                    "logged_in": True,
                    "role": "student",
                    "class_id": cid,
                    "page": "class_home"
                })
                st.rerun()
            else:
                st.error("Mã bảo mật không chính xác.")
    else:
        gv_class = st.selectbox("Lớp quản lý", list(CLASSES.keys()), key="mck_g_class")
        t_pass = st.text_input(
            "Mật khẩu Giảng viên",
            type="password",
            placeholder="Nhập mật khẩu...",
            key="mck_g_pass"
        )
    
        st.markdown(
            '<div style="margin-top:10px; font-size:13px; font-family:Inter; color:#555;">'
            '<input type="checkbox" style="accent-color:#b71c1c"> Ghi nhớ đăng nhập</div>',
            unsafe_allow_html=True
        )
    
        if st.button("TRUY CẬP QUẢN TRỊ", key="mck_btn_g"):
            if not t_pass.strip():
                st.error("Vui lòng nhập mật khẩu giảng viên.")
            elif t_pass == "779":
                cid = CLASSES[gv_class]
                tok = issue_login_token("teacher", cid, ttl_hours=12)
                qp_set(t=tok)
                st.session_state.update({
                    "logged_in": True,
                    "role": "teacher",
                    "class_id": cid,
                    "page": "class_home"
                })
                st.rerun()
            else:
                st.error("Sai mật khẩu.")
    st.markdown("""
        <div class="login-footer">
          <div class="f1">Hệ thống tương tác lớp học</div>
          <div class="f2">Phát triển bởi Giảng viên <b>Trần Nguyễn Sĩ Nguyên</b></div>
        </div>
        """, unsafe_allow_html=True)

    # ---- Wrapper đóng ----
    st.markdown("</div></div>", unsafe_allow_html=True)

    st.stop()

# ==========================================
# 5. SIDEBAR + NAV
# ==========================================
with st.sidebar:
    st.image(LOGO_URL, width=90)
    st.markdown("---")
    st.caption("🎵 NHẠC NỀN")
    st.audio("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3")

    cls_txt = [k for k, v in CLASSES.items() if v == st.session_state["class_id"]][0]
    role = "HỌC VIÊN" if st.session_state["role"] == "student" else "GIẢNG VIÊN"
    st.info(f"👤 {role}\n\n🏫 {cls_txt}")

    if st.session_state["role"] == "teacher":
        st.warning("CHUYỂN LỚP QUẢN LÝ")
    
        # Tính index theo class_id hiện tại để không bị nhảy về Lớp 1 khi rerun
        curr_cid = st.session_state.get("class_id", "lop1")
        cls_keys = list(CLASSES.keys())
        curr_label = next((k for k, v in CLASSES.items() if v == curr_cid), cls_keys[0])
        curr_index = cls_keys.index(curr_label) if curr_label in cls_keys else 0
    
        s_cls = st.selectbox(
            "Chọn lớp",
            cls_keys,
            index=curr_index,
            key="teacher_class_switch"
        )
    
        # Chỉ cập nhật khi thực sự khác
        new_cid = CLASSES[s_cls]
        if new_cid != st.session_state["class_id"]:
            st.session_state["class_id"] = new_cid
            st.rerun()
    st.markdown("---")
    if st.button("📚 Danh mục hoạt động", key="nav_class_home"):
        st.session_state["page"] = "class_home"
        st.rerun()

    if st.button("🏠 Dashboard", key="nav_dashboard"):
        st.session_state["page"] = "dashboard"
        st.rerun()

    st.markdown("---")
    if st.button("↩️ Quay lại đăng nhập", key="nav_logout"):
        qp_clear()
        reset_to_login()

# ==========================================
# 6. TRANG "DANH MỤC HOẠT ĐỘNG CỦA LỚP"
# ==========================================
def render_class_home():
    cid = st.session_state["class_id"]
    cfg = CLASS_ACT_CONFIG[cid]
    topic = cfg["topic"]
    cls_txt = [k for k, v in CLASSES.items() if v == cid][0]

    # wordcloud active question count
    bank = load_wc_bank(cid)
    aq = wc_get_active_question(cid, bank)
    active_wc_count = wc_count_answers(cid, aq.get("id", "Q1"))
    total_wc_questions = len(bank.get("questions", []))

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
        if act_key == "wordcloud":
            count = active_wc_count
            meta_extra = f" • Câu đang kích hoạt: <b>{aq.get('id')}</b> • Tổng câu: <b>{total_wc_questions}</b>"
        else:
            df = load_data(cid, act_key)
            count = len(df)
            meta_extra = ""

        colL, colR = st.columns([6, 1])
        with colL:
            st.markdown(f"""
                <div class="act-row">
                    <p class="act-name">{a["name"]}</p>
                    <p class="act-meta">Loại hoạt động: {a["type"]} • Số lượt trả lời: <b>{count}</b>{meta_extra}</p>
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
        f"<h2 style='color:{PRIMARY_COLOR}; border-bottom:2px solid #e2e8f0; padding-bottom:10px; font-size:46px; font-weight:900;'>🏠 Dashboard</h2>",
        unsafe_allow_html=True
    )
    st.caption(f"Chủ đề lớp: {topic}")

    bank = load_wc_bank(cid)
    aq = wc_get_active_question(cid, bank)
    wc_active_count = wc_count_answers(cid, aq.get("id", "Q1"))

    cols = st.columns(3)
    activities = ["wordcloud", "poll", "openended", "scales", "ranking", "pin"]
    names = ["WORD CLOUD (ACTIVE)", "POLL", "OPEN ENDED", "SCALES", "RANKING", "PIN IMAGE"]

    for i, act in enumerate(activities):
        if act == "wordcloud":
            n = wc_active_count
        else:
            df = load_data(cid, act)
            n = len(df)
        with cols[i % 3]:
            st.markdown(f"""
            <div class="viz-card" style="text-align:center;">
                <h1 style="color:{PRIMARY_COLOR}; margin:0; font-size:72px; font-weight:900;">{n}</h1>
                <p style="color:{MUTED}; font-weight:900; text-transform:uppercase; font-size:35px;">{names[i]}</p>
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

    # ---- helper query params (tương thích nhiều phiên bản Streamlit) ----
    def _get_qp(key: str, default=""):
        try:
            v = st.query_params.get(key, None)
            if v is None:
                return default
            if isinstance(v, list):
                return v[0] if v else default
            return str(v)
        except Exception:
            q = st.experimental_get_query_params()
            return q.get(key, [default])[0]

    def _set_qp(**kwargs):
        try:
            for k, v in kwargs.items():
                st.query_params[k] = str(v)
        except Exception:
            st.experimental_set_query_params(**{k: str(v) for k, v in kwargs.items()})

    def _clear_qp():
        try:
            st.query_params.clear()
        except Exception:
            st.experimental_set_query_params()

    topL, topR = st.columns([1, 5])
    with topL:
        if st.button("↩️ Về danh mục lớp", key="btn_back_class_home"):
            st.session_state["page"] = "class_home"
            st.rerun()
    with topR:
        st.markdown(
            f"<h2 style='color:{PRIMARY_COLOR}; border-bottom:2px solid #e2e8f0; padding-bottom:10px; font-size:46px; font-weight:900;'>{cfg['name']}</h2>",
            unsafe_allow_html=True
        )

    current_act_key = act

    # ------------------------------------------
    # 1) WORD CLOUD (NÂNG CẤP: bank câu hỏi + lịch sử + quick view)
    # ------------------------------------------
    if act == "wordcloud":
        def normalize_phrase(s: str) -> str:
            s = str(s or "").strip().lower()
            s = re.sub(r"\s+", " ", s)
            s = s.strip(" .,:;!?\"'`()[]{}<>|\\/+-=*#@~^_")
            return s

        def build_wordcloud_html(words_json: str, height_px: int = 520) -> str:
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
      position: relative;
    }}
    svg {{ width:100%; height:100%; display:block; }}
    .word {{
      font-family: 'Montserrat', system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;
      font-weight: 800;
      cursor: default;
      user-select: none;
      paint-order: stroke;
      stroke: rgba(255,255,255,0.85);
      stroke-width: 2px;
    }}
  </style>
</head>
<body>
  <div id="wc-wrap"></div>

  <script src="https://cdn.jsdelivr.net/npm/d3@7/dist/d3.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/d3-cloud@1/build/d3.layout.cloud.js"></script>
  <script>
    const data = {words_json};

    function mulberry32(a) {{
      return function() {{
        var t = a += 0x6D2B79F5;
        t = Math.imul(t ^ t >>> 15, t | 1);
        t ^= t + Math.imul(t ^ t >>> 7, t | 61);
        return ((t ^ t >>> 14) >>> 0) / 4294967296;
      }}
    }}
    const rng = mulberry32(42);

    function hashHue(str) {{
      let h = 5381;
      for (let i=0;i<str.length;i++) {{
        h = ((h << 5) + h) + str.charCodeAt(i);
        h = h & 0xffffffff;
      }}
      const hue = Math.abs(h) % 360;
      return hue;
    }}

    function getSizeScale(vals) {{
      const vmin = Math.max(1, d3.min(vals));
      const vmax = Math.max(1, d3.max(vals));
      if (vmax === vmin) {{
        return () => 58;
      }}
      return d3.scaleSqrt()
        .domain([vmin, vmax])
        .range([26, 118])
        .clamp(true);
    }}

    function render() {{
      const wrap = document.getElementById("wc-wrap");
      const rect = wrap.getBoundingClientRect();
      const W = Math.max(720, Math.floor(rect.width || window.innerWidth || 1200));
      const H = Math.max(320, Math.floor(rect.height || {height_px}));

      wrap.innerHTML = "";
      const svg = d3.select("#wc-wrap").append("svg")
        .attr("viewBox", `0 0 ${{W}} ${{H}}`)
        .attr("preserveAspectRatio", "xMidYMid meet");

      const g = svg.append("g");

      const vals = data.map(d => d.value);
      const fontScale = getSizeScale(vals);

      const words = data
        .slice()
        .sort((a,b) => d3.descending(a.value, b.value))
        .map(d => {{
          const hue = hashHue(d.text);
          return {{
            text: d.text,
            value: d.value,
            size: Math.round(fontScale(d.value)),
            rotate: 0,
            hue: hue,
            color: `hsl(${{hue}}, 84%, 50%)`,
            __key: d.text
          }}
        }});

      const layout = d3.layout.cloud()
        .size([W, H])
        .words(words)
        .padding(14)
        .spiral("archimedean")
        .rotate(d => d.rotate)
        .font("Montserrat")
        .fontSize(d => d.size)
        .random(() => rng());

      layout.on("end", draw);
      layout.start();

      function draw(placed) {{
        if (!placed || placed.length === 0) return;

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

        const bw = Math.max(1, maxX - minX);
        const bh = Math.max(1, maxY - minY);
        const cx = (minX + maxX) / 2;
        const cy = (minY + maxY) / 2;

        const margin = 0.92;
        const s = Math.min((W*margin)/bw, (H*margin)/bh);

        g.attr("transform", `translate(${{W/2}},${{H/2}}) scale(${{s}}) translate(${{-cx}},${{-cy}})`);

        const sel = g.selectAll("text.word")
          .data(placed, d => d.__key);

        sel.exit().remove();

        const enter = sel.enter().append("text")
          .attr("class", "word")
          .attr("text-anchor", "middle")
          .style("opacity", 0)
          .text(d => d.text);

        const merged = enter.merge(sel);

        merged
          .attr("transform", `translate(0,0) rotate(0)`)
          .style("fill", d => d.color)
          .style("font-size", d => `${{d.size}}px`);

        merged.transition()
          .duration(650)
          .ease(d3.easeCubicOut)
          .style("opacity", 1)
          .attr("transform", d => `translate(${{d.x}},${{d.y}}) rotate(${{d.rotate}})`);
      }}
    }}

    let tries = 0;
    function boot() {{
      tries += 1;
      const wrap = document.getElementById("wc-wrap");
      const w = wrap.getBoundingClientRect().width;
      if (w && w > 50) {{
        render();
      }} else if (tries < 25) {{
        requestAnimationFrame(boot);
      }} else {{
        render();
      }}
    }}
    boot();

    window.addEventListener("resize", () => {{
      clearTimeout(window.__wc_t);
      window.__wc_t = setTimeout(render, 180);
    }});
  </script>
</body>
</html>
"""
            return comp_html

        def wc_compute_freq_for_qid(cid: str, qid: str):
            df = load_data(cid, "wordcloud", suffix=qid)
            tmp = pd.DataFrame(columns=["Học viên", "Nội dung", "phrase"])
            freq = {}
            total_answers = int(df["Nội dung"].dropna().shape[0]) if ("Nội dung" in df.columns and not df.empty) else 0
            try:
                if not df.empty and ("Học viên" in df.columns) and ("Nội dung" in df.columns):
                    tmp = df[["Học viên", "Nội dung"]].copy()
                    tmp["Học viên"] = tmp["Học viên"].astype(str).str.strip()
                    tmp["phrase"] = tmp["Nội dung"].astype(str).apply(normalize_phrase)
                    tmp = tmp[(tmp["Học viên"] != "") & (tmp["phrase"] != "")]
                    tmp = tmp.drop_duplicates(subset=["Học viên", "phrase"])
                    freq = tmp["phrase"].value_counts().to_dict() if "phrase" in tmp.columns else {}
            except Exception:
                freq = {}

            total_people = int(tmp["Học viên"].nunique()) if (not tmp.empty and "Học viên" in tmp.columns) else 0
            total_unique_phrases = int(len(freq)) if freq else 0
            return freq, total_answers, total_people, total_unique_phrases

        # LOAD BANK + ACTIVE QUESTION
        bank = load_wc_bank(cid)
        active_q = wc_get_active_question(cid, bank)
        active_qid = active_q.get("id", "Q1")
        active_qtext = active_q.get("text", cfg["question"])

        # query params: fullscreen + which question to view
        is_fs = (_get_qp("wcfs", "0") == "1")
        fs_qid = _get_qp("wcq", active_qid) or active_qid

        # ---- FULLSCREEN PAGE
        if is_fs:
            st.markdown("""
            <style>
              header, footer {visibility:hidden;}
              [data-testid="stSidebar"] {display:none !important;}
              .block-container {max-width: 100% !important; padding: 0.4rem 0.7rem !important;}
            </style>
            """, unsafe_allow_html=True)

            b1, b2, b3 = st.columns([2, 6, 2])
            with b1:
                if st.button("⬅️ Thoát Fullscreen", key="wc_exit_fs"):
                    _clear_qp()
                    st.rerun()
            with b2:
                st.markdown(f"**Câu hỏi ({fs_qid}):** {active_qtext if fs_qid == active_qid else ''}")
            with b3:
                st.caption("Tỷ lệ hiển thị 16:9")

            live_fs = bool(st.session_state.get("wc_live_toggle", True))
            if live_fs:
                if st_autorefresh is not None:
                    st_autorefresh(interval=1500, key="wc_live_refresh_fs")
                else:
                    st.warning("Thiếu gói streamlit-autorefresh. Thêm vào requirements.txt: streamlit-autorefresh")

            freq, total_answers, total_people, total_unique_phrases = wc_compute_freq_for_qid(cid, fs_qid)

            if not freq:
                st.info("Chưa có dữ liệu. Mời lớp nhập từ khóa.")
            else:
                MAX_WORDS_SHOW_FS = 120
                items_fs = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:MAX_WORDS_SHOW_FS]
                words_payload_fs = [{"text": k, "value": int(v)} for k, v in items_fs]
                words_json_fs = json.dumps(words_payload_fs, ensure_ascii=False)

                wc_html_fs = build_wordcloud_html(words_json_fs, height_px=820)
                st.components.v1.html(wc_html_fs, height=845, scrolling=False)

            st.caption(
                f"🧾 Câu: **{fs_qid}** • 👥 Lượt gửi: **{total_answers}** • 👤 Người tham gia (unique): **{total_people}** • 🧩 Cụm duy nhất: **{total_unique_phrases}**"
            )
                        # ==========================
            # AI phân tích Wordcloud (riêng theo câu fs_qid) - chỉ GV
            # ==========================
            if st.session_state["role"] == "teacher":
                st.markdown("---")
                st.markdown("### 🤖 AI phân tích Wordcloud (riêng câu đang xem)")

                # load đúng câu hỏi đang fullscreen
                q_obj_fs = next((q for q in bank.get("questions", []) if q.get("id") == fs_qid), None)
                q_text_fs = (q_obj_fs.get("text") if q_obj_fs else active_qtext) or ""

                # Dữ liệu thô (để AI bám sát lời học viên)
                df_wc_fs = load_data(cid, "wordcloud", suffix=fs_qid)

                # Prompt gợi ý (CRUD theo từng câu)
                prompts = wc_get_prompts_for_qid(cid, fs_qid)

                # gợi ý mặc định nếu chưa có prompt nào
                if not prompts:
                    prompts = [
                        "Hãy rút ra 5 từ khóa nổi bật và giải thích vì sao chúng nổi bật trong bối cảnh bài học.",
                        "Hãy phân nhóm các cụm từ theo 3–5 chủ đề, kèm ví dụ minh họa (trích cụm từ).",
                        "Chỉ ra 3 hiểu lầm/nhầm lẫn có thể có từ các từ khóa, và 3 can thiệp sư phạm ngay tại lớp."
                    ]

                st.markdown("#### 🧩 Prompt gợi ý (bấm để phân tích ngay)")
                # hiển thị thành các nút bấm nhanh
                for i, p in enumerate(prompts[:12]):  # giới hạn để UI gọn
                    if st.button(f"▶ {p[:120]}{'...' if len(p) > 120 else ''}", key=f"wc_fs_quick_{fs_qid}_{i}"):
                        st.session_state["wc_fs_prompt"] = p

                # prompt tùy biến
                default_prompt = st.session_state.get(
                    "wc_fs_prompt",
                    "Hãy tóm tắt 3 xu hướng chính, 3 điểm mạnh/yếu và 3 câu hỏi gợi mở để thảo luận tiếp."
                )
                user_prompt = st.text_area("Prompt phân tích (có thể sửa)", value=default_prompt, height=120, key=f"wc_fs_prompt_area_{fs_qid}")

                colA, colB = st.columns([2, 2])
                with colA:
                    run_ai = st.button("PHÂN TÍCH NGAY", key=f"wc_fs_ai_run_{fs_qid}")
                with colB:
                    save_prompt_now = st.button("LƯU PROMPT NÀY VÀO GỢI Ý (câu này)", key=f"wc_fs_prompt_save_{fs_qid}")

                if save_prompt_now:
                    wc_add_prompt(cid, fs_qid, user_prompt)
                    st.toast("Đã lưu prompt cho câu này.")
                    time.sleep(0.15)
                    st.rerun()

                # CRUD prompt (thêm/sửa/xóa) ngay trong fullscreen
                with st.expander("⚙️ Quản lý prompt gợi ý (câu này): thêm / sửa / xóa", expanded=False):
                    existing = wc_get_prompts_for_qid(cid, fs_qid)
                    if not existing:
                        st.info("Chưa có prompt lưu riêng cho câu này.")
                    else:
                        pick = st.selectbox("Chọn prompt để sửa/xóa", existing, key=f"wc_fs_prompt_pick_{fs_qid}")
                        new_text = st.text_area("Nội dung sau khi sửa", value=pick, height=120, key=f"wc_fs_prompt_edit_{fs_qid}")

                        cX, cY = st.columns([1, 1])
                        with cX:
                            if st.button("LƯU SỬA", key=f"wc_fs_prompt_update_{fs_qid}"):
                                wc_update_prompt(cid, fs_qid, pick, new_text)
                                st.toast("Đã cập nhật prompt.")
                                time.sleep(0.15)
                                st.rerun()
                        with cY:
                            if st.button("XÓA PROMPT", key=f"wc_fs_prompt_delete_{fs_qid}"):
                                wc_delete_prompt(cid, fs_qid, pick)
                                st.toast("Đã xóa prompt.")
                                time.sleep(0.15)
                                st.rerun()

                # chạy AI
                if run_ai:
                    if model is None:
                        st.warning("Chưa cấu hình GEMINI_API_KEY trong st.secrets.")
                    elif df_wc_fs is None or df_wc_fs.empty:
                        st.warning("Chưa có dữ liệu để phân tích cho câu này.")
                    else:
                        # lấy top cụm (để AI bám vào kết quả nổi bật)
                        freq_fs, total_answers_fs, total_people_fs, total_unique_fs = wc_compute_freq_for_qid(cid, fs_qid)
                        top_items = sorted(freq_fs.items(), key=lambda x: x[1], reverse=True)[:25]

                        with st.spinner("AI đang phân tích..."):
                            payload = f"""
Bạn là trợ giảng cho giảng viên. Đây là dữ liệu WORDCLOUD của lớp.

CHỦ ĐỀ LỚP:
{CLASS_ACT_CONFIG[cid]['topic']}

CÂU HỎI ({fs_qid}):
{q_text_fs}

TOP 25 CỤM TỪ (chuẩn hoá) theo số người nhập:
{top_items}

DỮ LIỆU THÔ (bảng):
{df_wc_fs.to_string(index=False)}

YÊU CẦU PHÂN TÍCH:
{user_prompt}

Trả lời theo cấu trúc:
1) 3–5 phát hiện chính (insights)
2) Phân nhóm cụm từ theo chủ đề (kèm ví dụ)
3) Dự đoán 2–3 hiểu lầm/nhầm lẫn có thể có + cách chỉnh ngay
4) 3 can thiệp sư phạm (hỏi–đáp, ví dụ, mini-case)
5) 3 câu hỏi gợi mở để kéo thảo luận đi sâu
"""
                            res = model.generate_content(payload)
                            st.info(res.text)
            return

        # ---- NORMAL PAGE
        # Left / Right columns
        c1, c2 = st.columns([1, 2])

        # --- LEFT: student input (only active question appears)
        with c1:
            st.info(f"Câu hỏi đang kích hoạt ({active_qid}): **{active_qtext}**")

            if st.session_state["role"] == "student":
                with st.form("f_wc"):
                    n = st.text_input("Tên")
                    txt = st.text_input("Nhập 1 từ khóa / cụm từ (giữ nguyên cụm)")
                    if st.form_submit_button("GỬI"):
                        if n.strip() and txt.strip():
                            save_data(cid, "wordcloud", n, txt, suffix=active_qid)
                            st.success("Đã gửi!")
                            time.sleep(0.2)
                            st.rerun()
                        else:
                            st.warning("Vui lòng nhập đủ Tên và Từ khóa.")
            else:
                st.warning("Giảng viên xem kết quả bên phải + quản trị câu hỏi bên dưới.")

        # --- RIGHT: results for active question
        with c2:
            tcol1, tcol2, tcol3 = st.columns([2, 2, 2])
            with tcol1:
                is_mobile = (qp_get("m", "0") == "1")
                live = st.toggle("🔴 Live update (1.5s)", value=(False if is_mobile else True), key="wc_live_toggle")
            with tcol2:
                if st.button("🖥 Fullscreen Wordcloud", key="wc_btn_full"):
                    _set_qp(wcfs="1", wcq=active_qid)
                    st.rerun()
            with tcol3:
                show_table = st.toggle("Hiện bảng Top từ", value=False, key="wc_show_table")

            if live:
                if st_autorefresh is not None:
                    st_autorefresh(interval=1500, key="wc_live_refresh")
                else:
                    st.warning("Thiếu gói streamlit-autorefresh. Thêm vào requirements.txt: streamlit-autorefresh")

            st.markdown("##### ☁️ KẾT QUẢ (CÂU ĐANG KÍCH HOẠT)")
            freq, total_answers, total_people, total_unique_phrases = wc_compute_freq_for_qid(cid, active_qid)

            with st.container(border=True):
                if not freq:
                    st.info("Chưa có dữ liệu. Mời lớp nhập từ khóa.")
                    items = []
                else:
                    MAX_WORDS_SHOW = 60
                    items = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:MAX_WORDS_SHOW]
                    words_payload = [{"text": k, "value": int(v)} for k, v in items]
                    words_json = json.dumps(words_payload, ensure_ascii=False)

                    wc_html = build_wordcloud_html(words_json, height_px=520)
                    st.components.v1.html(wc_html, height=540, scrolling=False)

            st.caption(
                f"🧾 Câu: **{active_qid}** • 👥 Lượt gửi: **{total_answers}** • 👤 Người tham gia (unique): **{total_people}** • 🧩 Cụm duy nhất: **{total_unique_phrases}**"
            )

            if show_table and freq:
                topk = pd.DataFrame(items[:20], columns=["Từ/cụm (chuẩn hoá)", "Số người nhập"])
                st.dataframe(topk, use_container_width=True, hide_index=True)

        # --------------------------
        # TEACHER: Question Bank + History + Quick View
        # --------------------------
        if st.session_state["role"] == "teacher":
            st.markdown("---")
            with st.expander("🧠 WORD CLOUD • QUẢN TRỊ CÂU HỎI (Không giới hạn) + Lịch sử + Xem nhanh", expanded=True):
                left_admin, right_admin = st.columns([2, 3])

                # LEFT: create / edit / activate
                with left_admin:
                    st.markdown("###### ✅ Câu hỏi đang kích hoạt")
                    st.success(f"({active_qid}) {active_qtext}")

                    st.markdown("###### ➕ Thêm câu hỏi mới")
                    with st.form("wc_add_q_form"):
                        new_text = st.text_area("Nội dung câu hỏi mới", placeholder="Nhập câu hỏi...", height=120)
                        make_active = st.checkbox("Kích hoạt ngay sau khi tạo", value=True)
                        if st.form_submit_button("TẠO CÂU HỎI"):
                            if not new_text.strip():
                                st.warning("Vui lòng nhập nội dung câu hỏi.")
                            else:
                                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                new_id = wc_make_new_id(bank)
                                bank["questions"].append({"id": new_id, "text": new_text.strip(), "created_at": now, "updated_at": now})
                                if make_active:
                                    bank["active_id"] = new_id
                                save_wc_bank(cid, bank)
                                st.toast("Đã tạo câu hỏi.")
                                time.sleep(0.15)
                                st.rerun()

                    st.markdown("###### ✏️ Sửa nhanh câu đang kích hoạt")
                    with st.form("wc_edit_active_form"):
                        edit_text = st.text_area("Chỉnh nội dung", value=active_qtext, height=120)
                        if st.form_submit_button("LƯU CHỈNH SỬA"):
                            for q in bank["questions"]:
                                if q.get("id") == active_qid:
                                    q["text"] = edit_text.strip()
                                    q["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            save_wc_bank(cid, bank)
                            st.toast("Đã cập nhật câu hỏi.")
                            time.sleep(0.15)
                            st.rerun()

                    st.markdown("###### 🚀 Kích hoạt câu bất kỳ")
                    q_labels = []
                    q_map = {}
                    for q in bank.get("questions", []):
                        qid = q.get("id")
                        txt = q.get("text", "")
                        label = f"{qid} — {txt[:70]}{'...' if len(txt) > 70 else ''}"
                        q_labels.append(label)
                        q_map[label] = qid

                    sel_label = st.selectbox("Chọn câu để kích hoạt", q_labels, index=max(0, q_labels.index(next((l for l in q_labels if l.startswith(active_qid + " —")), q_labels[0]))))
                    if st.button("KÍCH HOẠT CÂU ĐÃ CHỌN", key="wc_activate_btn"):
                        bank["active_id"] = q_map.get(sel_label, active_qid)
                        save_wc_bank(cid, bank)
                        st.toast("Đã kích hoạt.")
                        time.sleep(0.15)
                        st.rerun()

                    st.markdown("###### 🗑 Xóa câu hỏi (không xóa file dữ liệu để tránh mất lịch sử)")
                    del_label = st.selectbox("Chọn câu để xóa khỏi danh sách", q_labels, key="wc_del_select")
                    if st.button("XÓA KHỎI DANH SÁCH", key="wc_del_btn"):
                        del_id = q_map.get(del_label)
                        if del_id == active_qid and len(bank.get("questions", [])) == 1:
                            st.warning("Không thể xóa: phải còn ít nhất 1 câu hỏi.")
                        else:
                            bank["questions"] = [q for q in bank["questions"] if q.get("id") != del_id]
                            # nếu xóa câu active thì chuyển active sang câu đầu
                            if bank.get("active_id") == del_id:
                                bank["active_id"] = bank["questions"][0].get("id", "Q1")
                            save_wc_bank(cid, bank)
                            st.toast("Đã xóa khỏi danh sách (dữ liệu vẫn còn trong file).")
                            time.sleep(0.15)
                            st.rerun()

                # RIGHT: history + quick view per question
                with right_admin:
                    st.markdown("###### 🧾 Lịch sử câu hỏi + nút xem nhanh kết quả từng câu")
                    st.caption("Mỗi câu có file dữ liệu riêng. Bạn có thể xem nhanh và (nếu muốn) kích hoạt lại.")

                    # build a compact table
                    rows = []
                    for q in bank.get("questions", []):
                        qid = q.get("id", "")
                        rows.append({
                            "Câu": qid,
                            "Trạng thái": "ĐANG KÍCH HOẠT" if qid == active_qid else "",
                            "Lượt gửi": wc_count_answers(cid, qid),
                            "Cập nhật": q.get("updated_at", q.get("created_at", "")),
                            "Nội dung": q.get("text", "")
                        })
                    hist_df = pd.DataFrame(rows).sort_values(by=["Câu"], ascending=True) if rows else pd.DataFrame(columns=["Câu","Trạng thái","Lượt gửi","Cập nhật","Nội dung"])
                    st.dataframe(hist_df[["Câu", "Trạng thái", "Lượt gửi", "Cập nhật", "Nội dung"]], use_container_width=True, hide_index=True)

                    st.markdown("###### 🔎 Xem nhanh (Quick View)")
                    qid_quick = st.selectbox("Chọn câu để xem nhanh", [r["Câu"] for r in rows] if rows else [active_qid], key="wc_quick_select")
                    q_obj = next((q for q in bank.get("questions", []) if q.get("id") == qid_quick), None)
                    q_text_quick = (q_obj.get("text") if q_obj else active_qtext) or ""

                    btn_row1, btn_row2, btn_row3 = st.columns([2, 2, 2])
                    with btn_row1:
                        if st.button("🖥 Fullscreen câu này", key="wc_quick_fs"):
                            _set_qp(wcfs="1", wcq=qid_quick)
                            st.rerun()
                    with btn_row2:
                        if st.button("🚀 Kích hoạt câu này", key="wc_quick_activate"):
                            bank["active_id"] = qid_quick
                            save_wc_bank(cid, bank)
                            st.toast("Đã kích hoạt câu được chọn.")
                            time.sleep(0.15)
                            st.rerun()
                    with btn_row3:
                        quick_table = st.toggle("Bảng Top (câu này)", value=False, key="wc_quick_table_toggle")

                    st.info(f"**({qid_quick})** {q_text_quick}")

                    freq_q, total_ans_q, total_people_q, total_unique_q = wc_compute_freq_for_qid(cid, qid_quick)
                    with st.container(border=True):
                        if not freq_q:
                            st.warning("Câu này chưa có dữ liệu.")
                            items_q = []
                        else:
                            MAX_WORDS_SHOW_Q = 60
                            items_q = sorted(freq_q.items(), key=lambda x: x[1], reverse=True)[:MAX_WORDS_SHOW_Q]
                            words_payload_q = [{"text": k, "value": int(v)} for k, v in items_q]
                            words_json_q = json.dumps(words_payload_q, ensure_ascii=False)
                            wc_html_q = build_wordcloud_html(words_json_q, height_px=420)
                            st.components.v1.html(wc_html_q, height=440, scrolling=False)

                    st.caption(
                        f"👥 Lượt gửi: **{total_ans_q}** • 👤 Người tham gia (unique): **{total_people_q}** • 🧩 Cụm duy nhất: **{total_unique_q}**"
                    )
                    if quick_table and freq_q:
                        topk_q = pd.DataFrame(items_q[:20], columns=["Từ/cụm (chuẩn hoá)", "Số người nhập"])
                        st.dataframe(topk_q, use_container_width=True, hide_index=True)

    # ------------------------------------------
    # 2) POLL
    # ------------------------------------------
    elif act == "poll":
        c1, c2 = st.columns([1, 2])
        options = cfg["options"]
        with c1:
            st.info(f"Câu hỏi: **{cfg['question']}**")

            device_id = st.session_state.get("device_id", "")
            already_voted = poll_has_voted(cid, device_id)

            if st.session_state["role"] == "student":
                if already_voted:
                    st.error("Máy này đã bình chọn rồi. Mỗi máy tính chỉ được bình chọn 1 lần.")
                else:
                    with st.form("f_poll"):
                        n = st.text_input("Tên")
                        vote = st.radio("Lựa chọn", options)

                        if st.form_submit_button("BÌNH CHỌN"):
                            if not n.strip():
                                st.warning("Vui lòng nhập Tên.")
                            else:
                                # khóa ngay lập tức để tránh double-click/rerun
                                poll_mark_voted(cid, device_id)
                                save_data(cid, current_act_key, n, vote)
                                st.success("Đã chọn!")
                                time.sleep(0.2)
                                st.rerun()
            else:
                st.caption(f"Đáp án gợi ý (chỉ GV): **{cfg.get('correct','')}**")
                st.caption(f"Thiết bị (debug): {device_id[:8]}…")

        with c2:
            st.markdown("##### 📊 THỐNG KÊ")
            df = load_data(cid, current_act_key)

            # Nút fullscreen chỉ dành cho giảng viên (đúng yêu cầu)
            top_btn1, top_btn2 = st.columns([2, 3])
            with top_btn1:
                if st.session_state["role"] == "teacher":
                    if st.button("🖥 FULLSCREEN BIỂU ĐỒ", key="poll_btn_fullscreen"):
                        st.session_state["poll_fullscreen"] = True
                        st.rerun()
            with top_btn2:
                st.caption("Cột cao nhất = đỏ đậm; các cột còn lại = xanh dương.")

            with st.container(border=True):
                if not df.empty:
                    cnt = df["Nội dung"].value_counts().reset_index()
                    cnt.columns = ["Lựa chọn", "Số lượng"]

                    # Xác định max để tô đỏ cột cao nhất
                    max_val = int(cnt["Số lượng"].max())
                    cnt["Màu"] = np.where(cnt["Số lượng"] == max_val, "#8B0000", "#1D4ED8")

                    # Plotly Graph Objects để set màu theo từng cột
                    fig = go.Figure(
                        data=[
                            go.Bar(
                                x=cnt["Lựa chọn"],
                                y=cnt["Số lượng"],
                                text=cnt["Số lượng"],
                                textposition="auto",
                                marker=dict(color=cnt["Màu"]),
                            )
                        ]
                    )
                    fig.update_layout(
                        margin=dict(l=10, r=10, t=10, b=10),
                        xaxis_title=None,
                        yaxis_title=None,
                    )

                    # Nếu giảng viên bật fullscreen → mở dialog
                    if st.session_state.get("poll_fullscreen", False) and st.session_state["role"] == "teacher":
                        open_poll_fullscreen_dialog(fig)

                    # Hiển thị bình thường
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Chưa có bình chọn nào.")

# ------------------------------------------
    # 3) OPEN ENDED
    # ------------------------------------------
    elif act == "openended":
        # ---- Open Ended Question Bank ----
        bank = load_oe_bank(cid)
        active_q = oe_get_active_question(cid, bank)
        active_qid = active_q.get("id", "Q1")
        active_qtext = active_q.get("text", cfg["question"])

        # dữ liệu theo từng câu hỏi
        df_active = load_data(cid, "openended", suffix=active_qid)
        
        # ---- helper query params ----
        is_oe_fs = (_get_qp("oefs", "0") == "1")
        fs_oe_qid = _get_qp("oeq", active_qid) or active_qid
        
        if is_oe_fs:
            # ✅ Fullscreen page 16:9 (ổn định, không dùng dialog)
            # CHÚ Ý: Đảm bảo st.markdown bao bọc toàn bộ CSS bằng f""" ... """
            st.markdown(f"""
            <style>
              header, footer {{visibility:hidden;}}
              [data-testid="stSidebar"] {{display:none !important;}}
              .block-container {{
                  max-width: 100% !important;
                  padding: 0.4rem 0.8rem !important;
              }}
        
              /* ✅ chữ ý kiến học viên >= 30 */
              .note-card {{
                  background: #fff;
                  padding: 18px;
                  border-radius: 16px;
                  border-left: 7px solid {PRIMARY_COLOR};
                  margin-bottom: 14px;
                  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                  font-size: 34px !important;   /* ✅ >=30, đọc xa tốt */
                  line-height: 1.25 !important;
                  font-weight: 750;
              }}
        
              h1, h2, h3, p, span, div {{
                  font-size: 34px !important;
              }}
            </style>
            """, unsafe_allow_html=True)
        
            # Header bar
            b1, b2, b3 = st.columns([2, 6, 2])
            with b1:
                if st.button("⬅️ Thoát Fullscreen", key="oe_exit_fs"):
                    _clear_qp()
                    st.rerun()
            with b2:
                st.markdown("### 💬 Fullscreen Open Ended")
            with b3:
                st.caption("Tối ưu trình chiếu 16:9")
        
            # ✅ Load đúng dữ liệu theo từng câu hỏi
            df_fs = load_data(cid, "openended", suffix=fs_oe_qid)
        
            # ✅ Hiển thị đúng câu hỏi
            q_obj_fs = next((q for q in bank.get("questions", []) if q.get("id") == fs_oe_qid), None)
            q_text_fs = (q_obj_fs.get("text") if q_obj_fs else active_qtext) or active_qtext
            st.markdown(f"**Câu hỏi ({fs_oe_qid}):** {q_text_fs}")
        
            # AI phân tích trong fullscreen (chỉ GV)
            show_ai = False
            if st.session_state["role"] == "teacher":
                show_ai = st.toggle("Hiện AI phân tích", value=True, key="oe_fs_ai_toggle")
        
            with st.container(border=True, height=820):
                if df_fs is not None and not df_fs.empty:
                    for _, r in df_fs.iterrows():
                        st.markdown(
                            f'<div class="note-card"><b>{r["Học viên"]}</b>: {r["Nội dung"]}</div>',
                            unsafe_allow_html=True
                        )
                else:
                    st.info("Chưa có câu trả lời.")
        
            if show_ai and st.session_state["role"] == "teacher":
                st.markdown("---")
                st.markdown("### 🤖 AI phân tích (toàn bộ ý kiến – đúng câu đang xem)")
                prompt_fs = st.text_input(
                    "Yêu cầu phân tích",
                    value="Hãy rút ra 3 xu hướng chính, 3 lỗi lập luận phổ biến và 3 gợi ý can thiệp sư phạm.",
                    key="oe_fs_ai_prompt"
                )
                if st.button("PHÂN TÍCH NGAY", key="oe_fs_ai_btn"):
                    if df_fs is None or df_fs.empty:
                        st.warning("Chưa có dữ liệu để phân tích.")
                    elif model is None:
                        st.warning("Chưa cấu hình GEMINI_API_KEY trong st.secrets.")
                    else:
                        with st.spinner("AI đang phân tích..."):
                            payload = f"""
        Bạn là trợ giảng cho giảng viên.
        
        CHỦ ĐỀ LỚP:
        {CLASS_ACT_CONFIG[cid]['topic']}
        
        CÂU HỎI ({fs_oe_qid}):
        {q_text_fs}
        
        DỮ LIỆU (bảng):
        {df_fs.to_string(index=False)}
        
        YÊU CẦU:
        {prompt_fs}
        
        Trả lời ngắn gọn nhưng sâu:
        1) 3 xu hướng nổi bật
        2) 3 lỗi/thiếu sót lập luận phổ biến
        3) 3 gợi ý can thiệp sư phạm ngay trên lớp
        4) 3 câu hỏi gợi mở để thảo luận tiếp
        """
                            res = model.generate_content(payload)
                            st.info(res.text)
        
            return # KẾT THÚC CHẾ ĐỘ FULLSCREEN, RETURN ĐỂ KHÔNG CHẠY CODE GIAO DIỆN THƯỜNG

        c1, c2 = st.columns([1, 2])

        # -------------------------
        # LEFT: student submit (active question only)
        # -------------------------
        with c1:
            st.info(f"Câu hỏi đang kích hoạt ({active_qid}): **{active_qtext}**")

            if st.session_state["role"] == "student":
                with st.form("f_open"):
                    n = st.text_input("Tên")
                    c = st.text_area("Câu trả lời")
                    if st.form_submit_button("GỬI"):
                        if n.strip() and c.strip():
                            # ✅ lưu theo suffix = qid để tách file theo câu
                            save_data(cid, "openended", n, c, suffix=active_qid)
                            st.success("Đã gửi!")
                            time.sleep(0.2)
                            st.rerun()
                        else:
                            st.warning("Vui lòng nhập đủ Tên và nội dung.")
            else:
                st.warning("Giảng viên xem bức tường bên phải + quản trị câu hỏi bên dưới.")

        # -------------------------
        # RIGHT: wall + fullscreen + AI per question
        # -------------------------
        with c2:
            st.markdown("##### 💬 BỨC TƯỜNG Ý KIẾN (CÂU ĐANG KÍCH HOẠT)")

            topb1, topb2, topb3 = st.columns([2, 2, 2])
            with topb1:
                live = st.toggle("🔴 Live update (1.5s)", value=True, key="oe_live_toggle")
            with topb2:
                if st.session_state["role"] == "teacher":
                    if st.button("🖥 FULLSCREEN BỨC TƯỜNG", key="oe_btn_full"):
                        _set_qp(oefs="1", oeq=active_qid)  # ✅ fullscreen dạng trang + đúng câu hỏi
                        st.rerun()
            with topb3:
                show_ai = (st.session_state["role"] == "teacher") and st.toggle("Hiện AI phân tích", value=True, key="oe_show_ai_toggle")

            if live:
                if st_autorefresh is not None:
                    st_autorefresh(interval=1500, key="oe_live_refresh")
                else:
                    st.warning("Thiếu gói streamlit-autorefresh. Thêm vào requirements.txt: streamlit-autorefresh")

            # Fullscreen (GV)
            if st.session_state.get("oe_fullscreen", False) and st.session_state["role"] == "teacher":
                default_prompt = "Hãy rút ra 3 xu hướng lập luận chính, chỉ ra 3 lỗi/nhầm phổ biến, và đề xuất 3 câu hỏi gợi mở để thảo luận tiếp."
                open_openended_fullscreen_dialog(
                    title=f"Open Ended ({active_qid}): {active_qtext}",
                    df_wall=df_active,
                    model=model,
                    analysis_prompt_default=default_prompt
                )

            # Wall normal
            with st.container(border=True, height=520):
                if df_active is not None and not df_active.empty:
                    for _, r in df_active.iterrows():
                        st.markdown(
                            f'<div class="note-card"><b>{r["Học viên"]}</b>: {r["Nội dung"]}</div>',
                            unsafe_allow_html=True
                        )
                else:
                    st.info("Chưa có câu trả lời.")

            # AI analysis (GV) for active question
            if show_ai:
                st.markdown("---")
                st.markdown("###### 🤖 AI phân tích (riêng câu đang kích hoạt)")
                default_prompt = "Hãy phân loại ý kiến theo nhóm quan điểm, nêu điểm mạnh/yếu, trích 3 ví dụ tiêu biểu, và đề xuất 3 can thiệp sư phạm."
                oe_prompt = st.text_input("Yêu cầu phân tích", value=default_prompt, key="oe_ai_prompt_active")
                if st.button("PHÂN TÍCH NGAY", key="oe_ai_btn_active"):
                    if df_active is None or df_active.empty:
                        st.warning("Chưa có dữ liệu để phân tích.")
                    elif model is None:
                        st.warning("Chưa cấu hình GEMINI_API_KEY trong st.secrets.")
                    elif not oe_prompt.strip():
                        st.warning("Vui lòng nhập yêu cầu phân tích.")
                    else:
                        with st.spinner("AI đang phân tích..."):
                            payload = f"""
Bạn là trợ giảng cho giảng viên. Đây là dữ liệu Open Ended (theo từng câu hỏi) của {cid}.
Chủ đề lớp: {CLASS_ACT_CONFIG[cid]['topic']}

CÂU HỎI ({active_qid}):
{active_qtext}

DỮ LIỆU (bảng):
{df_active.to_string(index=False)}

YÊU CẦU CỦA GIẢNG VIÊN:
{oe_prompt}

Hãy trả lời theo cấu trúc:
1) Tóm tắt chủ đề nổi bật
2) Phân loại lập luận/quan điểm
3) Trích dẫn minh họa (trích ngắn, nêu tên học viên)
4) Gợi ý can thiệp sư phạm (3 gợi ý)
5) 3 câu hỏi gợi mở để thảo luận tiếp
"""
                            res = model.generate_content(payload)
                            st.info(res.text)

        # -------------------------
        # TEACHER: CRUD question bank + quick view per question
        # -------------------------
        if st.session_state["role"] == "teacher":
            st.markdown("---")
            with st.expander("🧠 OPEN ENDED • QUẢN TRỊ CÂU HỎI (Thêm/Sửa/Xóa) + Lịch sử + Xem nhanh", expanded=True):
                left_admin, right_admin = st.columns([2, 3])

                # LEFT: create / edit / activate / delete
                with left_admin:
                    st.markdown("###### ✅ Câu hỏi đang kích hoạt")
                    st.success(f"({active_qid}) {active_qtext}")

                    st.markdown("###### ➕ Thêm câu hỏi mới")
                    with st.form("oe_add_q_form"):
                        new_text = st.text_area("Nội dung câu hỏi mới", placeholder="Nhập câu hỏi...", height=120, key="oe_add_text")
                        make_active = st.checkbox("Kích hoạt ngay sau khi tạo", value=True, key="oe_make_active")
                        if st.form_submit_button("TẠO CÂU HỎI"):
                            if not new_text.strip():
                                st.warning("Vui lòng nhập nội dung câu hỏi.")
                            else:
                                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                new_id = oe_make_new_id(bank)
                                bank["questions"].append({"id": new_id, "text": new_text.strip(), "created_at": now, "updated_at": now})
                                if make_active:
                                    bank["active_id"] = new_id
                                save_oe_bank(cid, bank)
                                st.toast("Đã tạo câu hỏi.")
                                time.sleep(0.15)
                                st.rerun()

                    st.markdown("###### ✏️ Sửa nhanh câu đang kích hoạt")
                    with st.form("oe_edit_active_form"):
                        edit_text = st.text_area("Chỉnh nội dung", value=active_qtext, height=120, key="oe_edit_text")
                        if st.form_submit_button("LƯU CHỈNH SỬA"):
                            for q in bank["questions"]:
                                if q.get("id") == active_qid:
                                    q["text"] = edit_text.strip()
                                    q["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            save_oe_bank(cid, bank)
                            st.toast("Đã cập nhật câu hỏi.")
                            time.sleep(0.15)
                            st.rerun()

                    st.markdown("###### 🚀 Kích hoạt câu bất kỳ")
                    q_labels = []
                    q_map = {}
                    for q in bank.get("questions", []):
                        qid = q.get("id")
                        txt = q.get("text", "")
                        label = f"{qid} — {txt[:70]}{'...' if len(txt) > 70 else ''}"
                        q_labels.append(label)
                        q_map[label] = qid

                    sel_label = st.selectbox("Chọn câu để kích hoạt", q_labels, key="oe_activate_select")
                    if st.button("KÍCH HOẠT CÂU ĐÃ CHỌN", key="oe_activate_btn"):
                        bank["active_id"] = q_map.get(sel_label, active_qid)
                        save_oe_bank(cid, bank)
                        st.toast("Đã kích hoạt.")
                        time.sleep(0.15)
                        st.rerun()

                    st.markdown("###### 🗑 Xóa câu hỏi (không xóa file dữ liệu để giữ lịch sử)")
                    del_label = st.selectbox("Chọn câu để xóa khỏi danh sách", q_labels, key="oe_del_select")
                    if st.button("XÓA KHỎI DANH SÁCH", key="oe_del_btn"):
                        del_id = q_map.get(del_label)
                        if del_id == active_qid and len(bank.get("questions", [])) == 1:
                            st.warning("Không thể xóa: phải còn ít nhất 1 câu hỏi.")
                        else:
                            bank["questions"] = [q for q in bank["questions"] if q.get("id") != del_id]
                            if bank.get("active_id") == del_id:
                                bank["active_id"] = bank["questions"][0].get("id", "Q1")
                            save_oe_bank(cid, bank)
                            st.toast("Đã xóa khỏi danh sách (dữ liệu vẫn còn trong file).")
                            time.sleep(0.15)
                            st.rerun()

                # RIGHT: history + quick view + AI per selected question
                with right_admin:
                    st.markdown("###### 🧾 Lịch sử câu hỏi + xem nhanh bức tường theo từng câu")
                    rows = []
                    for q in bank.get("questions", []):
                        qid = q.get("id", "")
                        rows.append({
                            "Câu": qid,
                            "Trạng thái": "ĐANG KÍCH HOẠT" if qid == active_qid else "",
                            "Lượt gửi": oe_count_answers(cid, qid),
                            "Cập nhật": q.get("updated_at", q.get("created_at", "")),
                            "Nội dung": q.get("text", "")
                        })
                    hist_df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["Câu","Trạng thái","Lượt gửi","Cập nhật","Nội dung"])
                    if not hist_df.empty:
                        st.dataframe(hist_df[["Câu", "Trạng thái", "Lượt gửi", "Cập nhật", "Nội dung"]], use_container_width=True, hide_index=True)

                    st.markdown("###### 🔎 Xem nhanh (Quick View)")
                    qid_quick = st.selectbox("Chọn câu để xem nhanh", [r["Câu"] for r in rows] if rows else [active_qid], key="oe_quick_select")
                    q_obj = next((q for q in bank.get("questions", []) if q.get("id") == qid_quick), None)
                    q_text_quick = (q_obj.get("text") if q_obj else active_qtext) or ""

                    df_quick = load_data(cid, "openended", suffix=qid_quick)

                    qbtn1, qbtn2, qbtn3 = st.columns([2, 2, 2])
                    with qbtn1:
                        if st.button("🖥 Fullscreen câu này", key="oe_quick_fs"):
                            # dùng chung fullscreen: bật state rồi hiển thị theo active? -> ta hiển thị trực tiếp dialog quick
                            default_prompt = "Hãy tóm tắt 3 chủ đề nổi bật, nêu 3 lỗi/thiếu phổ biến, và đề xuất 3 câu hỏi gợi mở."
                            open_openended_fullscreen_dialog(
                                title=f"Open Ended ({qid_quick}): {q_text_quick}",
                                df_wall=df_quick,
                                model=model,
                                analysis_prompt_default=default_prompt
                            )
                    with qbtn2:
                        if st.button("🚀 Kích hoạt câu này", key="oe_quick_activate"):
                            bank["active_id"] = qid_quick
                            save_oe_bank(cid, bank)
                            st.toast("Đã kích hoạt câu được chọn.")
                            time.sleep(0.15)
                            st.rerun()
                    with qbtn3:
                        quick_ai = st.toggle("Hiện AI (câu này)", value=True, key="oe_quick_ai_toggle")

                    st.info(f"**({qid_quick})** {q_text_quick}")

                    with st.container(border=True, height=420):
                        if df_quick is not None and not df_quick.empty:
                            for _, r in df_quick.iterrows():
                                st.markdown(
                                    f'<div class="note-card"><b>{r["Học viên"]}</b>: {r["Nội dung"]}</div>',
                                    unsafe_allow_html=True
                                )
                        else:
                            st.warning("Câu này chưa có dữ liệu.")

                    if quick_ai:
                        st.markdown("###### 🤖 AI phân tích (riêng câu đang xem nhanh)")
                        q_prompt = st.text_input(
                            "Yêu cầu phân tích",
                            value="Phân nhóm quan điểm, trích 3 ví dụ tiêu biểu, chỉ ra điểm thiếu/nhầm và gợi ý 3 can thiệp sư phạm.",
                            key="oe_quick_ai_prompt"
                        )
                        if st.button("PHÂN TÍCH NGAY (CÂU NÀY)", key="oe_quick_ai_btn"):
                            if df_quick is None or df_quick.empty:
                                st.warning("Chưa có dữ liệu để phân tích.")
                            elif model is None:
                                st.warning("Chưa cấu hình GEMINI_API_KEY trong st.secrets.")
                            elif not q_prompt.strip():
                                st.warning("Vui lòng nhập yêu cầu phân tích.")
                            else:
                                with st.spinner("AI đang phân tích..."):
                                    payload = f"""
Bạn là trợ giảng cho giảng viên. Đây là dữ liệu Open Ended theo từng câu hỏi của {cid}.
Chủ đề lớp: {CLASS_ACT_CONFIG[cid]['topic']}

CÂU HỎI ({qid_quick}):
{q_text_quick}

DỮ LIỆU (bảng):
{df_quick.to_string(index=False)}

YÊU CẦU CỦA GIẢNG VIÊN:
{q_prompt}

Hãy trả lời theo cấu trúc:
1) Tóm tắt chủ đề nổi bật
2) Phân loại lập luận/quan điểm
3) Trích dẫn minh họa (trích ngắn, nêu tên học viên)
4) Gợi ý can thiệp sư phạm (3 gợi ý)
5) 3 câu hỏi gợi mở để thảo luận tiếp
"""
                                    res = model.generate_content(payload)
                                    st.info(res.text)
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
                    # Wordcloud: phân tích câu active (đúng logic)
                    if current_act_key == "wordcloud":
                        bank = load_wc_bank(cid)
                        aq = wc_get_active_question(cid, bank)
                        curr_df = load_data(cid, "wordcloud", suffix=aq.get("id", "Q1"))
                        act_name = f"{cfg['name']} ({aq.get('id')})"
                    else:
                        curr_df = load_data(cid, current_act_key)
                        act_name = cfg["name"]

                    if curr_df.empty:
                        st.warning("Chưa có dữ liệu để phân tích.")
                    elif model is None:
                        st.warning("Chưa cấu hình GEMINI_API_KEY trong st.secrets.")
                    elif not prompt.strip():
                        st.warning("Vui lòng nhập yêu cầu phân tích.")
                    else:
                        with st.spinner("AI đang phân tích..."):
                            payload = f"""
Bạn là trợ giảng cho giảng viên. Đây là dữ liệu hoạt động ({act_name}) của {cid}.
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
                    if current_act_key == "wordcloud":
                        bank = load_wc_bank(cid)
                        aq = wc_get_active_question(cid, bank)
                        clear_activity(cid, "wordcloud", suffix=aq.get("id", "Q1"))
                    else:
                        if current_act_key == "openended":
                            bank = load_oe_bank(cid)
                            aq = oe_get_active_question(cid, bank)
                            clear_activity(cid, "openended", suffix=aq.get("id", "Q1"))
                        else:
                            clear_activity(cid, current_act_key)

                        # nếu reset Poll thì reset luôn vote-lock để lớp vote lại được
                        if current_act_key == "poll":
                            try:
                                with data_lock:
                                    p = poll_vote_lock_path(cid)
                                    if os.path.exists(p):
                                        os.remove(p)
                            except Exception:
                                pass
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
