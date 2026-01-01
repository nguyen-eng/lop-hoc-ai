import os
import json
import time
import uuid
import sqlite3
from datetime import datetime

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from wordcloud import WordCloud
import matplotlib.pyplot as plt

try:
    import google.generativeai as genai
except Exception:
    genai = None

# =========================
# 0) CONFIG
# =========================
st.set_page_config(
    page_title="T05 Interactive Class (Mentimeter-like)",
    page_icon="📶",
    layout="wide",
    initial_sidebar_state="collapsed",
)

LOGO_URL = "https://drive.google.com/thumbnail?id=1PsUr01oeleJkW2JB1gqnID9WJNsTMFGW&sz=w1000"
DEFAULT_PIN_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/Blank_map_of_Vietnam.svg/858px-Blank_map_of_Vietnam.svg.png"

PRIMARY_COLOR = "#006a4e"
BG_COLOR = "#f0f2f5"
TEXT_COLOR = "#111827"

# =========================
# 1) STYLES
# =========================
st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] {{
    font-family: 'Montserrat', sans-serif;
    background-color: {BG_COLOR};
    color: {TEXT_COLOR};
}}
header {{visibility: hidden;}} footer {{visibility: hidden;}}

.card {{
    background: white; padding: 18px; border-radius: 16px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.06);
    border: 1px solid #e2e8f0;
}}
.badge {{
    display:inline-block; padding:6px 10px; border-radius:999px;
    background: rgba(0,106,78,0.12); color:{PRIMARY_COLOR}; font-weight:700;
    font-size:12px;
}}
.smallmuted {{ color:#64748b; font-weight:600; }}

div.stButton > button {{
    background-color: {PRIMARY_COLOR}; color: white; border: none;
    border-radius: 50px; padding: 12px 18px; font-weight: 800;
    text-transform: uppercase; letter-spacing: 0.7px; width: 100%;
    box-shadow: 0 4px 15px rgba(0, 106, 78, 0.25);
}}
div.stButton > button:hover {{ background-color: #00503a; transform: translateY(-1px); }}

.note {{
    background:#fff; padding:12px 14px; border-radius:12px;
    border-left:5px solid {PRIMARY_COLOR}; margin-bottom:10px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
}}

hr {{ border:none; border-top:1px solid #e2e8f0; margin: 12px 0; }}
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# 2) DB (SQLite)
# =========================
@st.cache_resource
def get_db():
    conn = sqlite3.connect("t05_interactive.db", check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn

DB = get_db()

def db_init():
    DB.execute("""
    CREATE TABLE IF NOT EXISTS sessions(
        session_id TEXT PRIMARY KEY,
        session_code TEXT UNIQUE,
        title TEXT,
        class_name TEXT,
        created_at TEXT,
        is_locked INTEGER DEFAULT 0
    )""")
    DB.execute("""
    CREATE TABLE IF NOT EXISTS questions(
        q_id TEXT PRIMARY KEY,
        session_id TEXT,
        q_type TEXT,
        title TEXT,
        config_json TEXT,
        is_open INTEGER DEFAULT 1,
        created_at TEXT,
        FOREIGN KEY(session_id) REFERENCES sessions(session_id)
    )""")
    DB.execute("""
    CREATE TABLE IF NOT EXISTS responses(
        r_id TEXT PRIMARY KEY,
        q_id TEXT,
        session_id TEXT,
        student_name TEXT,
        anon INTEGER DEFAULT 0,
        content TEXT,
        created_at TEXT,
        FOREIGN KEY(q_id) REFERENCES questions(q_id),
        FOREIGN KEY(session_id) REFERENCES sessions(session_id)
    )""")
    DB.commit()

db_init()

def now_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def gen_code():
    # 6 chars code
    return uuid.uuid4().hex[:6].upper()

def db_fetch_df(query, params=()):
    return pd.read_sql_query(query, DB, params=params)

def db_exec(query, params=()):
    DB.execute(query, params)
    DB.commit()

# =========================
# 3) AI (Gemini)
# =========================
def get_ai_model():
    if genai is None:
        return None
    api_key = None
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", None)
    except Exception:
        api_key = None
    if not api_key:
        return None
    genai.configure(api_key=api_key)
    # Bạn có thể đổi model ở đây
    return genai.GenerativeModel("gemini-2.5-flash")

AI_MODEL = get_ai_model()

def ai_analyze(question_title: str, q_type: str, cfg: dict, df_resp: pd.DataFrame, teacher_prompt: str) -> str:
    if AI_MODEL is None:
        return "AI chưa sẵn sàng (thiếu GEMINI_API_KEY hoặc thiếu thư viện google-generativeai)."

    # Giảm nhiễu dữ liệu: chỉ lấy cột cần thiết
    payload = {
        "question_title": question_title,
        "question_type": q_type,
        "config": cfg,
        "n_responses": int(len(df_resp)),
        "responses_sample": df_resp[["student_name", "content", "created_at", "anon"]].tail(200).to_dict(orient="records")
    }

    system_frame = """
Bạn là trợ giảng cho giảng viên đại học (định hướng năng lực lãnh đạo/chỉ huy).
Hãy phân tích dữ liệu tương tác lớp học theo hướng:
(1) Xu hướng chính (patterns) + tỷ lệ/điểm nhấn;
(2) Nhóm ý kiến (themes) & ví dụ tiêu biểu (không nêu tên nếu anon=1);
(3) Điểm lệch/ngoại lệ (outliers) và diễn giải;
(4) Gợi ý can thiệp sư phạm (2-5 hành động cụ thể trong 10 phút tới);
(5) 3 câu hỏi gợi mở/khai vấn để kéo lớp lên cấp độ tư duy cao hơn.
Viết bằng tiếng Việt, súc tích nhưng sắc.
Nếu câu hỏi là Poll/Ranking/Scales: ưu tiên đọc dữ liệu như phân phối.
Nếu Open Ended/Wordcloud: ưu tiên theme + trích dẫn ngắn (<= 12 từ).
"""

    prompt = f"""{system_frame}

Yêu cầu riêng của giảng viên:
{teacher_prompt}

Dữ liệu (JSON):
{json.dumps(payload, ensure_ascii=False)}
"""
    res = AI_MODEL.generate_content(prompt)
    return getattr(res, "text", str(res))

# =========================
# 4) AUTH STATE
# =========================
if "role" not in st.session_state:
    st.session_state.role = None  # "student" | "teacher"
if "teacher_pass" not in st.session_state:
    st.session_state.teacher_pass = ""
if "session_code" not in st.session_state:
    st.session_state.session_code = ""
if "student_name" not in st.session_state:
    st.session_state.student_name = ""
if "anon" not in st.session_state:
    st.session_state.anon = 0

# Hỗ trợ link dạng ?code=ABC123
qp = st.query_params
if "code" in qp and not st.session_state.session_code:
    st.session_state.session_code = str(qp["code"]).strip().upper()

# =========================
# 5) HELPERS: sessions/questions
# =========================
def get_session_by_code(code: str):
    df = db_fetch_df("SELECT * FROM sessions WHERE session_code = ?", (code,))
    if df.empty:
        return None
    return df.iloc[0].to_dict()

def get_questions(session_id: str):
    return db_fetch_df(
        "SELECT * FROM questions WHERE session_id=? ORDER BY created_at ASC",
        (session_id,)
    )

def get_open_questions(session_id: str):
    return db_fetch_df(
        "SELECT * FROM questions WHERE session_id=? AND is_open=1 ORDER BY created_at ASC",
        (session_id,)
    )

def get_responses(q_id: str):
    return db_fetch_df(
        "SELECT * FROM responses WHERE q_id=? ORDER BY created_at ASC",
        (q_id,)
    )

def insert_response(session_id: str, q_id: str, student_name: str, anon: int, content: str):
    r_id = uuid.uuid4().hex
    db_exec(
        "INSERT INTO responses(r_id,q_id,session_id,student_name,anon,content,created_at) VALUES(?,?,?,?,?,?,?)",
        (r_id, q_id, session_id, student_name, int(anon), content, now_ts())
    )

# =========================
# 6) UI: LOGIN / PORTALS
# =========================
st.markdown("<br>", unsafe_allow_html=True)

c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    st.markdown(
        f"""
<div class="card" style="text-align:center; border-top:6px solid {PRIMARY_COLOR};">
  <img src="{LOGO_URL}" width="90">
  <h2 style="color:{PRIMARY_COLOR}; margin:10px 0 0 0;">T05 Interactive Class</h2>
  <div class="smallmuted">Mentimeter-like • Streamlit • Live Analytics • AI Teaching Assistant</div>
</div>
""",
        unsafe_allow_html=True,
    )

st.write("")
tab_student, tab_teacher = st.tabs(["🎓 Cổng Học viên", "👮‍♂️ Cổng Giảng viên"])

# ---------- STUDENT ----------
with tab_student:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Vào phiên học (Session)")
    code = st.text_input("Mã phiên (session code)", value=st.session_state.session_code, placeholder="Ví dụ: A1B2C3")
    st.session_state.session_code = code.strip().upper()

    colA, colB = st.columns([2, 1])
    with colA:
        st.session_state.student_name = st.text_input("Tên hiển thị", value=st.session_state.student_name)
    with colB:
        st.session_state.anon = 1 if st.checkbox("Ẩn danh", value=bool(st.session_state.anon)) else 0

    go_btn = st.button("VÀO LÀM BÀI")
    st.markdown("</div>", unsafe_allow_html=True)

    if go_btn:
        sess = get_session_by_code(st.session_state.session_code)
        if not sess:
            st.error("Không tìm thấy phiên. Kiểm tra lại mã phiên.")
        elif int(sess["is_locked"]) == 1:
            st.warning("Phiên đang bị khóa. Chờ giảng viên mở lại.")
        else:
            st.session_state.role = "student"
            st.rerun()

# ---------- TEACHER ----------
with tab_teacher:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Quản trị phiên (Teacher Console)")
    st.session_state.teacher_pass = st.text_input("Mật khẩu giảng viên", type="password", value=st.session_state.teacher_pass)
    t_login = st.button("ĐĂNG NHẬP GIẢNG VIÊN")
    st.markdown("</div>", unsafe_allow_html=True)

    if t_login:
        # Bạn đổi mật khẩu tại đây
        if st.session_state.teacher_pass == "T05":
            st.session_state.role = "teacher"
            st.rerun()
        else:
            st.error("Sai mật khẩu.")

# =========================
# 7) STUDENT APP
# =========================
def render_student(sess: dict):
    st.sidebar.image(LOGO_URL, width=70)
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Vai trò:** Học viên")
    st.sidebar.markdown(f"**Phiên:** `{sess['session_code']}`")
    st.sidebar.markdown(f"**Tiêu đề:** {sess['title']}")
    st.sidebar.markdown("---")
    if st.sidebar.button("Thoát"):
        st.session_state.role = None
        st.rerun()

    st.markdown(
        f"""
<div class="card">
  <span class="badge">STUDENT</span>
  <h3 style="margin:8px 0 0 0;">{sess['title']}</h3>
  <div class="smallmuted">Mã phiên: {sess['session_code']} • {sess['class_name']} • {sess['created_at']}</div>
</div>
""",
        unsafe_allow_html=True
    )

    dfq = get_open_questions(sess["session_id"])
    if dfq.empty:
        st.info("Hiện chưa có câu hỏi/hoạt động đang mở. Chờ giảng viên.")
        st.stop()

    # Chọn câu hỏi đang làm
    q_titles = [f"{i+1}. [{row['q_type']}] {row['title']}" for i, row in dfq.iterrows()]
    idx = st.selectbox("Chọn hoạt động đang làm", range(len(q_titles)), format_func=lambda i: q_titles[i])
    q = dfq.iloc[idx].to_dict()
    cfg = json.loads(q["config_json"]) if q.get("config_json") else {}

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"### {q['title']}")
    st.caption(f"Loại hoạt động: {q['q_type']} • Trạng thái: OPEN")

    student_name = st.session_state.student_name.strip() or "Học viên"
    anon = int(st.session_state.anon)

    # ====== Render by type ======
    q_type = q["q_type"]

    if q_type == "wordcloud":
        with st.form("student_wc"):
            token = st.text_input("Nhập 1 từ khóa", placeholder="Ví dụ: kỷ luật / dữ liệu / AI / trách nhiệm ...")
            ok = st.form_submit_button("GỬI")
        if ok:
            if not token.strip():
                st.warning("Bạn chưa nhập từ khóa.")
            else:
                insert_response(sess["session_id"], q["q_id"], student_name, anon, token.strip())
                st.success("Đã gửi.")
                time.sleep(0.3)
                st.rerun()

    elif q_type == "poll":
        options = cfg.get("options", ["A", "B", "C", "D"])
        with st.form("student_poll"):
            vote = st.radio("Chọn 1 phương án", options)
            ok = st.form_submit_button("BÌNH CHỌN")
        if ok:
            insert_response(sess["session_id"], q["q_id"], student_name, anon, vote)
            st.success("Đã bình chọn.")
            time.sleep(0.3)
            st.rerun()

    elif q_type == "openended":
        with st.form("student_open"):
            ans = st.text_area("Câu trả lời", height=140, placeholder="Viết ngắn gọn, đi thẳng vào ý…")
            ok = st.form_submit_button("GỬI")
        if ok:
            if not ans.strip():
                st.warning("Bạn chưa nhập câu trả lời.")
            else:
                insert_response(sess["session_id"], q["q_id"], student_name, anon, ans.strip())
                st.success("Đã gửi.")
                time.sleep(0.3)
                st.rerun()

    elif q_type == "scales":
        criteria = cfg.get("criteria", ["Tiêu chí 1", "Tiêu chí 2", "Tiêu chí 3", "Tiêu chí 4"])
        lo, hi = int(cfg.get("min", 1)), int(cfg.get("max", 5))
        default = int(cfg.get("default", (lo+hi)//2))
        with st.form("student_scales"):
            scores = []
            for c in criteria:
                scores.append(st.slider(c, lo, hi, default))
            ok = st.form_submit_button("GỬI THANG ĐO")
        if ok:
            insert_response(sess["session_id"], q["q_id"], student_name, anon, json.dumps(scores))
            st.success("Đã gửi.")
            time.sleep(0.3)
            st.rerun()

    elif q_type == "ranking":
        items = cfg.get("items", ["Mục 1", "Mục 2", "Mục 3", "Mục 4"])
        st.write("Chọn đủ tất cả mục theo thứ tự ưu tiên (quan trọng nhất đứng đầu).")
        with st.form("student_rank"):
            chosen = st.multiselect("Thứ tự ưu tiên", items, default=[])
            ok = st.form_submit_button("NỘP XẾP HẠNG")
        if ok:
            if len(chosen) != len(items):
                st.warning(f"Cần chọn đủ {len(items)} mục.")
            else:
                insert_response(sess["session_id"], q["q_id"], student_name, anon, json.dumps(chosen))
                st.success("Đã nộp.")
                time.sleep(0.3)
                st.rerun()

    elif q_type == "pin":
        img = cfg.get("image_url", DEFAULT_PIN_IMAGE)
        st.image(img, caption="Ảnh nền ghim (giảng viên có thể thay bằng bản đồ/sơ đồ chiến thuật)", use_container_width=True)
        with st.form("student_pin"):
            x_val = st.slider("Ngang (trái → phải)", 0, 100, 50)
            y_val = st.slider("Dọc (dưới → trên)", 0, 100, 50)
            note = st.text_input("Ghi chú (tuỳ chọn)", placeholder="Ví dụ: điểm nóng / khu vực ưu tiên / ...")
            ok = st.form_submit_button("GHIM")
        if ok:
            payload = {"x": x_val, "y": y_val, "note": note.strip()}
            insert_response(sess["session_id"], q["q_id"], student_name, anon, json.dumps(payload, ensure_ascii=False))
            st.success("Đã ghim.")
            time.sleep(0.3)
            st.rerun()

    else:
        st.warning("Loại hoạt động chưa được hỗ trợ.")

    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# 8) TEACHER APP
# =========================
def render_teacher():
    st.sidebar.image(LOGO_URL, width=70)
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Vai trò:** Giảng viên")
    st.sidebar.markdown("---")

    # --- Session management ---
    st.sidebar.subheader("Phiên (Session)")
    sessions_df = db_fetch_df("SELECT * FROM sessions ORDER BY created_at DESC")
    session_options = ["(Tạo phiên mới)"] + [
        f"{r['session_code']} • {r['title']} • {r['class_name']} • {'LOCK' if r['is_locked']==1 else 'OPEN'}"
        for _, r in sessions_df.iterrows()
    ]
    sel = st.sidebar.selectbox("Chọn phiên", session_options)

    # Create new session
    if sel == "(Tạo phiên mới)":
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("Tạo phiên mới (Mentimeter-like Room)")
        title = st.text_input("Tiêu đề phiên", value="Tiết học tương tác")
        class_name = st.text_input("Lớp/đơn vị", value="T05")
        create = st.button("TẠO PHIÊN")
        if create:
            sid = uuid.uuid4().hex
            code = gen_code()
            db_exec(
                "INSERT INTO sessions(session_id,session_code,title,class_name,created_at,is_locked) VALUES(?,?,?,?,?,0)",
                (sid, code, title.strip(), class_name.strip(), now_ts())
            )
            st.success(f"Đã tạo phiên. Mã phiên: {code}")
            st.info(f"Link gợi ý: thêm `?code={code}` vào URL sau khi deploy.")
            st.markdown("</div>", unsafe_allow_html=True)
            st.stop()
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    # Load selected session
    code = sel.split("•")[0].strip()
    sess = get_session_by_code(code)
    if not sess:
        st.error("Không tải được phiên.")
        st.stop()

    if st.sidebar.button("Thoát"):
        st.session_state.role = None
        st.rerun()

    st.markdown(
        f"""
<div class="card">
  <span class="badge">TEACHER</span>
  <h3 style="margin:8px 0 0 0;">{sess['title']}</h3>
  <div class="smallmuted">Mã phiên: <b>{sess['session_code']}</b> • {sess['class_name']} • {sess['created_at']}</div>
</div>
""",
        unsafe_allow_html=True
    )

    # Lock/unlock
    col_lock, col_refresh = st.columns([1, 1])
    with col_lock:
        if int(sess["is_locked"]) == 0:
            if st.button("KHÓA PHIÊN (Stop entry)"):
                db_exec("UPDATE sessions SET is_locked=1 WHERE session_id=?", (sess["session_id"],))
                st.rerun()
        else:
            if st.button("MỞ PHIÊN (Allow entry)"):
                db_exec("UPDATE sessions SET is_locked=0 WHERE session_id=?", (sess["session_id"],))
                st.rerun()
    with col_refresh:
        auto = st.checkbox("Tự cập nhật (3s)", value=True)

    if auto:
        time.sleep(0.3)  # tránh giật
        st.experimental_set_query_params(code=sess["session_code"])
        st_autorefresh = st.empty()
        # hack nhẹ: refresh bằng rerun định kỳ
        # (Streamlit official: st.autorefresh có trong st.experimental? tuỳ version)
        if "last_tick" not in st.session_state:
            st.session_state.last_tick = time.time()
        if time.time() - st.session_state.last_tick > 3:
            st.session_state.last_tick = time.time()
            st.rerun()

    st.write("")

    # --- Create / manage questions ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Tạo hoạt động (Word cloud / Poll / Open / Scales / Ranking / Pin)")
    q_type = st.selectbox(
        "Chọn loại hoạt động",
        ["wordcloud", "poll", "openended", "scales", "ranking", "pin"],
        format_func=lambda x: {
            "wordcloud": "Word Cloud",
            "poll": "Poll",
            "openended": "Open Ended",
            "scales": "Scales",
            "ranking": "Ranking",
            "pin": "Pin on Image",
        }[x],
    )
    q_title = st.text_input("Câu hỏi/Đề bài", value="Nhập câu hỏi tại đây…")

    cfg = {}
    if q_type == "poll":
        opts = st.text_area("Danh sách lựa chọn (mỗi dòng 1 lựa chọn)", value="Phương án A\nPhương án B\nPhương án C\nPhương án D")
        cfg["options"] = [x.strip() for x in opts.splitlines() if x.strip()]

    if q_type == "scales":
        crit = st.text_area("Tiêu chí (mỗi dòng 1 tiêu chí)", value="Kỹ năng A\nKỹ năng B\nKỹ năng C\nKỹ năng D")
        cfg["criteria"] = [x.strip() for x in crit.splitlines() if x.strip()]
        c1, c2, c3 = st.columns(3)
        with c1:
            cfg["min"] = st.number_input("Min", value=1)
        with c2:
            cfg["max"] = st.number_input("Max", value=5)
        with c3:
            cfg["default"] = st.number_input("Default", value=3)

    if q_type == "ranking":
        items = st.text_area("Các mục xếp hạng (mỗi dòng 1 mục)", value="Tiêu chí 1\nTiêu chí 2\nTiêu chí 3\nTiêu chí 4")
        cfg["items"] = [x.strip() for x in items.splitlines() if x.strip()]

    if q_type == "pin":
        cfg["image_url"] = st.text_input("URL ảnh nền để ghim", value=DEFAULT_PIN_IMAGE)

    create_q = st.button("TẠO HOẠT ĐỘNG")
    if create_q:
        if not q_title.strip():
            st.warning("Chưa nhập tiêu đề câu hỏi.")
        else:
            qid = uuid.uuid4().hex
            db_exec(
                "INSERT INTO questions(q_id,session_id,q_type,title,config_json,is_open,created_at) VALUES(?,?,?,?,?,1,?)",
                (qid, sess["session_id"], q_type, q_title.strip(), json.dumps(cfg, ensure_ascii=False), now_ts())
            )
            st.success("Đã tạo hoạt động và đang mở (OPEN).")
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # --- Question list ---
    dfq = get_questions(sess["session_id"])
    if dfq.empty:
        st.info("Chưa có hoạt động. Hãy tạo ở phần trên.")
        st.stop()

    st.write("")
    st.subheader("Bảng điều khiển hoạt động & phân tích")
    q_labels = [f"{i+1}. [{r['q_type']}] {r['title']} • {'OPEN' if r['is_open']==1 else 'CLOSED'}" for i, r in dfq.iterrows()]
    q_idx = st.selectbox("Chọn hoạt động để theo dõi", range(len(q_labels)), format_func=lambda i: q_labels[i])
    q = dfq.iloc[q_idx].to_dict()
    cfg = json.loads(q["config_json"]) if q.get("config_json") else {}

    col_open, col_clear, col_export = st.columns([1, 1, 1])
    with col_open:
        if int(q["is_open"]) == 1:
            if st.button("ĐÓNG HOẠT ĐỘNG"):
                db_exec("UPDATE questions SET is_open=0 WHERE q_id=?", (q["q_id"],))
                st.rerun()
        else:
            if st.button("MỞ HOẠT ĐỘNG"):
                db_exec("UPDATE questions SET is_open=1 WHERE q_id=?", (q["q_id"],))
                st.rerun()

    with col_clear:
        if st.button("XÓA DỮ LIỆU TRẢ LỜI (của hoạt động này)"):
            db_exec("DELETE FROM responses WHERE q_id=?", (q["q_id"],))
            st.success("Đã xóa.")
            st.rerun()

    with col_export:
        df_resp = get_responses(q["q_id"])
        csv = df_resp.to_csv(index=False).encode("utf-8-sig")
        st.download_button("TẢI CSV", data=csv, file_name=f"{sess['session_code']}_{q['q_type']}.csv", mime="text/csv")

    # --- Analytics area ---
    df_resp = get_responses(q["q_id"])
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"### {q['title']}")
    st.caption(f"Loại: {q['q_type']} • Tổng phản hồi: {len(df_resp)}")

    q_type = q["q_type"]

    if df_resp.empty:
        st.info("Chưa có phản hồi.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    # helper: anonymize display
    def display_name(row):
        return "Ẩn danh" if int(row.get("anon", 0)) == 1 else row.get("student_name", "Học viên")

    # ====== Charts by type ======
    if q_type == "wordcloud":
        text = " ".join(df_resp["content"].astype(str).tolist())
        wc = WordCloud(width=900, height=420, background_color="white").generate(text)
        fig, ax = plt.subplots()
        ax.imshow(wc, interpolation="bilinear")
        ax.axis("off")
        st.pyplot(fig, use_container_width=True)

        # Top tokens quick table
        counts = pd.Series([t.strip().lower() for t in df_resp["content"].astype(str).tolist() if t.strip()]).value_counts().head(12)
        st.write("**Top từ khóa:**")
        st.dataframe(counts.rename("count").reset_index().rename(columns={"index": "token"}), use_container_width=True)

    elif q_type == "poll":
        cnt = df_resp["content"].value_counts().reset_index()
        cnt.columns = ["Lựa chọn", "Số lượng"]
        fig = px.bar(cnt, x="Lựa chọn", y="Số lượng", text_auto=True)
        st.plotly_chart(fig, use_container_width=True)

    elif q_type == "openended":
        # Wall
        wall = df_resp.copy()
        wall["who"] = wall.apply(display_name, axis=1)
        wall = wall.sort_values("created_at", ascending=False).head(80)
        for _, r in wall.iterrows():
            st.markdown(f'<div class="note"><b>{r["who"]}</b>: {r["content"]}</div>', unsafe_allow_html=True)

    elif q_type == "scales":
        criteria = cfg.get("criteria", ["Tiêu chí 1", "Tiêu chí 2", "Tiêu chí 3", "Tiêu chí 4"])
        mat = []
        for s in df_resp["content"].tolist():
            try:
                arr = json.loads(s)
                if isinstance(arr, list) and len(arr) == len(criteria):
                    mat.append([float(x) for x in arr])
            except Exception:
                pass
        if not mat:
            st.warning("Dữ liệu scales có lỗi định dạng.")
        else:
            avg_scores = pd.Series(pd.DataFrame(mat).mean(axis=0).values, index=criteria)
            fig = go.Figure(data=go.Scatterpolar(r=avg_scores.values, theta=criteria, fill="toself"))
            fig.update_layout(polar=dict(radialaxis=dict(visible=True)), showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

            # distribution table
            st.write("**Trung bình theo tiêu chí:**")
            st.dataframe(avg_scores.rename("mean").reset_index().rename(columns={"index":"criteria"}), use_container_width=True)

    elif q_type == "ranking":
        items = cfg.get("items", ["Mục 1", "Mục 2", "Mục 3", "Mục 4"])
        scores = {k: 0 for k in items}
        n = len(items)
        for s in df_resp["content"].tolist():
            try:
                order = json.loads(s)
                if isinstance(order, list) and len(order) == n:
                    for idx, item in enumerate(order):
                        if item in scores:
                            scores[item] += (n - idx)
            except Exception:
                pass
        res = pd.DataFrame({"Mục": list(scores.keys()), "Tổng điểm": list(scores.values())}).sort_values("Tổng điểm", ascending=False)
        fig = px.bar(res, x="Tổng điểm", y="Mục", orientation="h", text="Tổng điểm")
        fig.update_layout(yaxis={"categoryorder":"total ascending"})
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(res, use_container_width=True)

    elif q_type == "pin":
        img = cfg.get("image_url", DEFAULT_PIN_IMAGE)
        xs, ys, notes = [], [], []
        for s in df_resp["content"].tolist():
            try:
                obj = json.loads(s)
                xs.append(int(obj.get("x", 50)))
                ys.append(int(obj.get("y", 50)))
                notes.append(obj.get("note", ""))
            except Exception:
                pass

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="markers",
            text=notes,
            marker=dict(size=12, opacity=0.75, line=dict(width=1, color="white"))
        ))
        fig.update_layout(
            xaxis=dict(range=[0, 100], showgrid=False, zeroline=False, visible=False),
            yaxis=dict(range=[0, 100], showgrid=False, zeroline=False, visible=False),
            images=[dict(source=img, xref="x", yref="y", x=0, y=100, sizex=100, sizey=100, sizing="stretch", layer="below")],
            height=520, margin=dict(l=0, r=0, t=10, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)

        # Notes quick list
        show_notes = [(n.strip()) for n in notes if n and n.strip()]
        if show_notes:
            st.write("**Ghi chú (trích):**")
            st.write(" • " + "\n • ".join(show_notes[:12]))

    st.markdown("</div>", unsafe_allow_html=True)

    # --- AI analysis (teacher prompt) ---
    st.write("")
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🤖 AI phân tích theo yêu cầu giảng viên")
    st.caption("Gợi ý: yêu cầu AI phân loại theme, tìm mâu thuẫn, đề xuất câu hỏi gợi mở, soạn mini-debrief 3 phút…")

    teacher_prompt = st.text_input(
        "Nhập yêu cầu phân tích",
        value="Phân tích xu hướng chính, chia nhóm ý kiến, chỉ ra điểm lệch và gợi ý 3 câu hỏi gợi mở để nâng cấp thảo luận.",
    )
    do_ai = st.button("PHÂN TÍCH NGAY")

    if do_ai:
        with st.spinner("AI đang phân tích…"):
            out = ai_analyze(q["title"], q["q_type"], cfg, df_resp, teacher_prompt)
        st.markdown(out)

    st.markdown("</div>", unsafe_allow_html=True)

# =========================
# 9) ROUTER
# =========================
if st.session_state.role == "student":
    sess = get_session_by_code(st.session_state.session_code)
    if not sess:
        st.session_state.role = None
        st.error("Phiên không tồn tại. Quay lại nhập mã phiên.")
    else:
        render_student(sess)

elif st.session_state.role == "teacher":
    render_teacher()

else:
    st.info("Chọn Cổng Học viên hoặc Cổng Giảng viên để bắt đầu.")
