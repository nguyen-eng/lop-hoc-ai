# app.py
# ============================================================
# T05 Interactive Class — tối ưu chịu tải 100+ học viên
# Triết lý tối ưu:
#  - Học viên: chỉ GỬI dữ liệu (không live refresh, không vẽ biểu đồ nặng)
#  - Giảng viên: có dashboard + live (tùy bật) + AI phân tích (tùy bật)
#  - Backend: SQLite (WAL) thay CSV; hạn chế import nặng theo vai trò & trang
# ============================================================

import os
import re
import json
import time
import uuid
import sqlite3
from datetime import datetime
import streamlit as st

# ---------------------------
# 0) CẤU HÌNH STREAMLIT
# ---------------------------
st.set_page_config(
    page_title="T05 Interactive Class",
    page_icon="📶",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# (Tùy chọn) Giảm bớt chrome
st.markdown(
    """
<style>
header, footer, #MainMenu {display:none !important;}
.block-container{padding-top:0.6rem;}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------
# 1) THÔNG SỐ HỆ THỐNG
# ---------------------------
APP_TITLE_VN = "TRƯỜNG ĐẠI HỌC CẢNH SÁT NHÂN DÂN"
APP_TITLE_EN = "People's Police University"

LOGO_URL = "https://drive.google.com/thumbnail?id=1PsUr01oeleJkW2JB1gqnID9WJNsTMFGW&sz=w1000"
MAP_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/Blank_map_of_Vietnam.svg/858px-Blank_map_of_Vietnam.svg.png"

PRIMARY_COLOR = "#006a4e"
MUTED = "#64748b"

CLASSES = {f"Lớp học {i}": f"lop{i}" for i in range(1, 11)}
PASSWORDS = {f"lop{i}": (f"T05-{i}" if i <= 8 else f"LH{i}") for i in range(1, 11)}
TEACHER_PASSWORD = "779"

DB_PATH = os.environ.get("T05_DB_PATH", "t05_interactive.db")
TOKEN_TTL_HOURS_DEFAULT = 12

# ---------------------------
# 2) AUTORESET / AUTOREFRESH (CHỈ GV DÙNG)
# ---------------------------
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# ---------------------------
# 3) GEMINI (CHỈ GV DÙNG)
# ---------------------------
def get_gemini_model():
    """Chỉ khởi tạo khi giảng viên mở AI (tránh nặng cho học viên)."""
    try:
        import google.generativeai as genai  # import muộn
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        if not api_key:
            return None
        genai.configure(api_key=api_key)
        return genai.GenerativeModel("gemini-2.5-flash")
    except Exception:
        return None


# ---------------------------
# 4) SQLITE: KẾT NỐI & SCHEMA
# ---------------------------
def _db_connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # WAL: tăng khả năng chịu concurrent read/write
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA busy_timeout=5000;")  # 5s
    return conn


def db_init():
    conn = _db_connect()
    cur = conn.cursor()

    # submissions: dữ liệu chung
    cur.execute(
        """
CREATE TABLE IF NOT EXISTS submissions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  class_id TEXT NOT NULL,
  activity TEXT NOT NULL,
  qid TEXT NOT NULL,
  name TEXT NOT NULL,
  content TEXT NOT NULL,
  device_id TEXT,
  created_at TEXT NOT NULL
);
"""
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_submissions_lookup ON submissions(class_id, activity, qid);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_submissions_time ON submissions(created_at);")

    # poll vote lock
    cur.execute(
        """
CREATE TABLE IF NOT EXISTS poll_votes (
  class_id TEXT NOT NULL,
  qid TEXT NOT NULL,
  device_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (class_id, qid, device_id)
);
"""
    )

    # question bank: cho wordcloud & openended (mở rộng sau)
    cur.execute(
        """
CREATE TABLE IF NOT EXISTS questions (
  class_id TEXT NOT NULL,
  activity TEXT NOT NULL,         -- 'wordcloud' | 'openended'
  qid TEXT NOT NULL,              -- 'Q1', 'Q2',...
  text TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (class_id, activity, qid)
);
"""
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_questions_active ON questions(class_id, activity, is_active);")

    # prompt bank (GV)
    cur.execute(
        """
CREATE TABLE IF NOT EXISTS prompts (
  class_id TEXT NOT NULL,
  activity TEXT NOT NULL,         -- 'wordcloud' | 'openended'
  qid TEXT NOT NULL,
  prompt TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (class_id, activity, qid, prompt)
);
"""
    )
    conn.commit()
    conn.close()


db_init()


def now_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------
# 5) DỮ LIỆU CHỦ ĐỀ & CÂU HỎI MẶC ĐỊNH (seed)
# ---------------------------
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


DEFAULT_ACT = {
    "lop1": {
        "wordcloud": "Nêu 1 từ khóa để phân biệt *nguyên nhân* với *nguyên cớ*.",
        "openended": "Hãy viết 3–5 câu: phân biệt *nguyên nhân – nguyên cớ – điều kiện* trong một vụ án giả định (tự chọn).",
        "poll_q": "Trong tình huống va quẹt xe rồi phát sinh đánh nhau, 'va quẹt xe' là gì?",
        "poll_opts": ["Nguyên nhân trực tiếp", "Nguyên cớ", "Kết quả", "Điều kiện đủ"],
        "poll_correct": "Nguyên cớ",
        "scales_criteria": ["Nhận diện nguyên nhân", "Nhận diện nguyên cớ", "Nhận diện điều kiện", "Lập luận logic"],
        "ranking_items": ["Thu thập dấu vết vật chất", "Xác minh chuỗi nguyên nhân", "Loại bỏ 'nguyên cớ' ngụy biện", "Kiểm tra điều kiện cần/đủ"],
        "pin_q": "Ghim 'điểm nóng' nơi dễ phát sinh nguyên cớ (kích động, tin đồn...) trong một sơ đồ lớp/bản đồ.",
    },
    "lop2": {},  # sẽ fallback lop1 (cùng nhóm)
    "lop3": {
        "wordcloud": "1 từ khóa mô tả đúng nhất 'tính kế thừa' trong phủ định biện chứng?",
        "openended": "Nêu 1 ví dụ trong công tác/đời sống thể hiện phát triển theo 'đường xoáy ốc' (tối thiểu 5 câu).",
        "poll_q": "Điểm phân biệt cốt lõi giữa 'phủ định biện chứng' và 'phủ định siêu hình' là gì?",
        "poll_opts": ["Có tính kế thừa", "Phủ định sạch trơn", "Ngẫu nhiên thuần túy", "Không dựa mâu thuẫn nội tại"],
        "poll_correct": "Có tính kế thừa",
        "scales_criteria": ["Nêu đúng 2 lần phủ định", "Chỉ ra yếu tố kế thừa", "Chỉ ra yếu tố vượt bỏ", "Kết nối thực tiễn"],
        "ranking_items": ["Xác định cái cũ cần vượt bỏ", "Giữ lại yếu tố hợp lý", "Tạo cơ chế tự phủ định", "Ổn định cái mới thành cái 'đang là'"],
        "pin_q": "Ghim vị trí trên sơ đồ để minh họa 'điểm bẻ gãy' khi mâu thuẫn chín muồi dẫn tới phủ định.",
    },
    "lop4": {},
    "lop5": {
        "wordcloud": "1 từ khóa mô tả 'bản chất con người' trong quan điểm Mác?",
        "openended": "Mô tả một biểu hiện 'tha hóa' trong lao động (5–7 câu) và gợi ý 1 hướng 'giải phóng'.",
        "poll_q": "Theo Mác, bản chất con người trước hết là gì?",
        "poll_opts": ["Tổng hòa các quan hệ xã hội", "Bản năng sinh học cố định", "Tinh thần thuần túy", "Ý chí cá nhân đơn lẻ"],
        "poll_correct": "Tổng hòa các quan hệ xã hội",
        "scales_criteria": ["Nêu đúng biểu hiện tha hóa", "Chỉ ra nguyên nhân xã hội", "Nêu hướng khắc phục", "Tính thực tiễn"],
        "ranking_items": ["Cải thiện điều kiện lao động", "Dân chủ hóa tổ chức", "Phát triển năng lực người lao động", "Phân phối công bằng thành quả"],
        "pin_q": "Ghim nơi thể hiện mâu thuẫn giữa 'con người' và 'cơ chế' gây tha hóa (tượng trưng).",
    },
    "lop6": {},
    "lop7": {
        "wordcloud": "1 từ khóa mô tả quan hệ *cá nhân – xã hội* theo cách nhìn biện chứng?",
        "openended": "Nêu 1 vấn đề con người ở Việt Nam hiện nay và phân tích theo 2 chiều: cá nhân – xã hội.",
        "poll_q": "Khẳng định nào đúng nhất về quan hệ cá nhân – xã hội?",
        "poll_opts": ["Cá nhân và xã hội quy định lẫn nhau", "Xã hội chỉ là tổng số cá nhân", "Cá nhân quyết định tuyệt đối", "Xã hội quyết định tuyệt đối"],
        "poll_correct": "Cá nhân và xã hội quy định lẫn nhau",
        "scales_criteria": ["Nêu vấn đề đúng trọng tâm", "Phân tích chiều cá nhân", "Phân tích chiều xã hội", "Đề xuất giải pháp"],
        "ranking_items": ["Giáo dục đạo đức – pháp luật", "Môi trường xã hội lành mạnh", "Cơ chế khuyến khích cái tốt", "Xử lý lệch chuẩn công bằng"],
        "pin_q": "Ghim vị trí 'điểm nghẽn' giữa cá nhân – tổ chức – xã hội (tượng trưng).",
    },
    "lop8": {},
    "lop9": {
        "wordcloud": "1 từ khóa mô tả 'hạt nhân' của phép biện chứng duy vật?",
        "openended": "Viết 5–7 câu: Vì sao người cán bộ (nhất là ĐTV) cần lập trường duy vật biện chứng khi xử lý chứng cứ?",
        "poll_q": "Trong triết học Mác – Lênin, vấn đề cơ bản của triết học là gì?",
        "poll_opts": ["Quan hệ vật chất – ý thức", "Quan hệ cái riêng – cái chung", "Quan hệ lượng – chất", "Quan hệ hình thức – nội dung"],
        "poll_correct": "Quan hệ vật chất – ý thức",
        "scales_criteria": ["Tôn trọng khách quan", "Chứng cứ vật chất", "Phân tích mâu thuẫn", "Kết luận có thể kiểm chứng"],
        "ranking_items": ["Tôn trọng khách quan", "Chứng cứ vật chất", "Phân tích mâu thuẫn", "Kết luận có thể kiểm chứng"],
        "pin_q": "Ghim vị trí 'nơi phát sinh sai lệch nhận thức' trong quy trình xử lý thông tin (tượng trưng).",
    },
    "lop10": {},
}

# alias nhóm
GROUP_ALIAS = {
    "lop2": "lop1",
    "lop4": "lop3",
    "lop6": "lop5",
    "lop8": "lop7",
    "lop10": "lop9",
}


def get_default_cfg(cid: str) -> dict:
    base = GROUP_ALIAS.get(cid, cid)
    return DEFAULT_ACT.get(base, DEFAULT_ACT["lop9"])


def seed_questions_if_missing(cid: str):
    conn = _db_connect()
    cur = conn.cursor()
    base = get_default_cfg(cid)

    # wordcloud
    cur.execute("SELECT COUNT(*) AS n FROM questions WHERE class_id=? AND activity='wordcloud';", (cid,))
    if cur.fetchone()["n"] == 0:
        cur.execute(
            """
INSERT INTO questions(class_id, activity, qid, text, is_active, created_at, updated_at)
VALUES (?, 'wordcloud', 'Q1', ?, 1, ?, ?);
""",
            (cid, base["wordcloud"], now_ts(), now_ts()),
        )

    # openended
    cur.execute("SELECT COUNT(*) AS n FROM questions WHERE class_id=? AND activity='openended';", (cid,))
    if cur.fetchone()["n"] == 0:
        cur.execute(
            """
INSERT INTO questions(class_id, activity, qid, text, is_active, created_at, updated_at)
VALUES (?, 'openended', 'Q1', ?, 1, ?, ?);
""",
            (cid, base["openended"], now_ts(), now_ts()),
        )

    conn.commit()
    conn.close()


# ---------------------------
# 6) LOGIN TOKEN (NHẸ, DB)
# ---------------------------
def _token_table_init():
    conn = _db_connect()
    conn.execute(
        """
CREATE TABLE IF NOT EXISTS tokens (
  token TEXT PRIMARY KEY,
  role TEXT NOT NULL,
  class_id TEXT NOT NULL,
  exp REAL NOT NULL,
  created_at TEXT NOT NULL
);
"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tokens_exp ON tokens(exp);")
    conn.commit()
    conn.close()


_token_table_init()


def issue_login_token(role: str, cid: str, ttl_hours: int = TOKEN_TTL_HOURS_DEFAULT) -> str:
    tok = str(uuid.uuid4())
    exp = time.time() + ttl_hours * 3600
    conn = _db_connect()
    conn.execute(
        "INSERT INTO tokens(token, role, class_id, exp, created_at) VALUES (?,?,?,?,?);",
        (tok, role, cid, exp, now_ts()),
    )
    conn.commit()
    conn.close()
    return tok


def validate_login_token(tok: str):
    tok = str(tok or "").strip()
    if not tok:
        return None
    conn = _db_connect()
    row = conn.execute("SELECT role, class_id, exp FROM tokens WHERE token=?;", (tok,)).fetchone()
    if not row:
        conn.close()
        return None
    if float(row["exp"]) < time.time():
        conn.execute("DELETE FROM tokens WHERE token=?;", (tok,))
        conn.commit()
        conn.close()
        return None
    conn.close()
    return {"role": row["role"], "class_id": row["class_id"]}


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


# ---------------------------
# 7) SESSION STATE
# ---------------------------
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "role" not in st.session_state:
    st.session_state["role"] = ""
if "class_id" not in st.session_state:
    st.session_state["class_id"] = ""
if "page" not in st.session_state:
    st.session_state["page"] = "login"  # login | class_home | activity | dashboard
if "current_act" not in st.session_state:
    st.session_state["current_act"] = "dashboard"
if "device_id" not in st.session_state:
    st.session_state["device_id"] = str(uuid.uuid4())


def reset_to_login():
    qp_clear()
    st.session_state.clear()
    st.rerun()


# ---------------------------
# 8) AUTO RESTORE TOKEN
# ---------------------------
if not st.session_state.get("logged_in", False):
    tok = qp_get("t", "")
    info = validate_login_token(tok)
    if info:
        st.session_state["logged_in"] = True
        st.session_state["role"] = info["role"]
        st.session_state["class_id"] = info["class_id"]
        st.session_state["page"] = "class_home"


# ---------------------------
# 9) DB HELPERS (NHẸ + AN TOÀN)
# ---------------------------
def clean_text(s: str, max_len: int = 2000) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s[:max_len]


def get_active_question(cid: str, activity: str):
    seed_questions_if_missing(cid)
    conn = _db_connect()
    row = conn.execute(
        "SELECT qid, text FROM questions WHERE class_id=? AND activity=? AND is_active=1 LIMIT 1;",
        (cid, activity),
    ).fetchone()
    if not row:
        # fallback: lấy Q1
        row = conn.execute(
            "SELECT qid, text FROM questions WHERE class_id=? AND activity=? ORDER BY qid LIMIT 1;",
            (cid, activity),
        ).fetchone()
    conn.close()
    if not row:
        return {"qid": "Q1", "text": ""}
    return {"qid": row["qid"], "text": row["text"]}


def list_questions(cid: str, activity: str):
    seed_questions_if_missing(cid)
    conn = _db_connect()
    rows = conn.execute(
        "SELECT qid, text, is_active, updated_at FROM questions WHERE class_id=? AND activity=? ORDER BY CAST(SUBSTR(qid,2) AS INT) ASC;",
        (cid, activity),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def make_new_qid(existing_qids):
    nums = []
    for q in existing_qids:
        m = re.match(r"^Q(\d+)$", str(q).strip(), flags=re.I)
        if m:
            nums.append(int(m.group(1)))
    nxt = (max(nums) + 1) if nums else 1
    return f"Q{nxt}"


def set_active_question(cid: str, activity: str, qid: str):
    conn = _db_connect()
    conn.execute("UPDATE questions SET is_active=0 WHERE class_id=? AND activity=?;", (cid, activity))
    conn.execute(
        "UPDATE questions SET is_active=1, updated_at=? WHERE class_id=? AND activity=? AND qid=?;",
        (now_ts(), cid, activity, qid),
    )
    conn.commit()
    conn.close()


def upsert_question(cid: str, activity: str, qid: str, text: str, make_active: bool):
    text = clean_text(text, 5000)
    ts = now_ts()
    conn = _db_connect()
    conn.execute(
        """
INSERT INTO questions(class_id, activity, qid, text, is_active, created_at, updated_at)
VALUES(?,?,?,?,0,?,?)
ON CONFLICT(class_id, activity, qid) DO UPDATE SET
  text=excluded.text,
  updated_at=excluded.updated_at;
""",
        (cid, activity, qid, text, ts, ts),
    )
    if make_active:
        conn.execute("UPDATE questions SET is_active=0 WHERE class_id=? AND activity=?;", (cid, activity))
        conn.execute(
            "UPDATE questions SET is_active=1, updated_at=? WHERE class_id=? AND activity=? AND qid=?;",
            (ts, cid, activity, qid),
        )
    conn.commit()
    conn.close()


def delete_question_from_list(cid: str, activity: str, qid: str):
    # chỉ xóa khỏi bank; submissions vẫn giữ (lịch sử)
    conn = _db_connect()
    # nếu đang active thì chuyển active sang q khác
    active = conn.execute(
        "SELECT qid FROM questions WHERE class_id=? AND activity=? AND is_active=1;",
        (cid, activity),
    ).fetchone()
    conn.execute(
        "DELETE FROM questions WHERE class_id=? AND activity=? AND qid=?;",
        (cid, activity, qid),
    )
    # nếu vừa xóa active -> set active câu đầu
    if active and active["qid"] == qid:
        row = conn.execute(
            "SELECT qid FROM questions WHERE class_id=? AND activity=? ORDER BY CAST(SUBSTR(qid,2) AS INT) ASC LIMIT 1;",
            (cid, activity),
        ).fetchone()
        if row:
            conn.execute("UPDATE questions SET is_active=0 WHERE class_id=? AND activity=?;", (cid, activity))
            conn.execute(
                "UPDATE questions SET is_active=1, updated_at=? WHERE class_id=? AND activity=? AND qid=?;",
                (now_ts(), cid, activity, row["qid"]),
            )
    conn.commit()
    conn.close()


def submit(cid: str, activity: str, qid: str, name: str, content: str, device_id: str | None = None):
    name = clean_text(name, 120)
    content = clean_text(content, 5000)
    if not name or not content:
        return False

    conn = _db_connect()
    conn.execute(
        """
INSERT INTO submissions(class_id, activity, qid, name, content, device_id, created_at)
VALUES(?,?,?,?,?,?,?);
""",
        (cid, activity, qid, name, content, device_id, now_ts()),
    )
    conn.commit()
    conn.close()
    return True


@st.cache_data(ttl=2)
def count_submissions(cid: str, activity: str, qid: str | None = None) -> int:
    conn = _db_connect()
    if qid is None:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM submissions WHERE class_id=? AND activity=?;",
            (cid, activity),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM submissions WHERE class_id=? AND activity=? AND qid=?;",
            (cid, activity, qid),
        ).fetchone()
    conn.close()
    return int(row["n"] if row else 0)


@st.cache_data(ttl=2)
def fetch_latest(cid: str, activity: str, qid: str, limit: int = 60):
    conn = _db_connect()
    rows = conn.execute(
        """
SELECT name, content, created_at
FROM submissions
WHERE class_id=? AND activity=? AND qid=?
ORDER BY id DESC
LIMIT ?;
""",
        (cid, activity, qid, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@st.cache_data(ttl=2)
def fetch_poll_counts(cid: str, qid: str):
    conn = _db_connect()
    rows = conn.execute(
        """
SELECT content AS option, COUNT(*) AS n
FROM submissions
WHERE class_id=? AND activity='poll' AND qid=?
GROUP BY content
ORDER BY n DESC;
""",
        (cid, qid),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def poll_has_voted(cid: str, qid: str, device_id: str) -> bool:
    conn = _db_connect()
    row = conn.execute(
        "SELECT 1 FROM poll_votes WHERE class_id=? AND qid=? AND device_id=? LIMIT 1;",
        (cid, qid, device_id),
    ).fetchone()
    conn.close()
    return bool(row)


def poll_mark_voted(cid: str, qid: str, device_id: str) -> bool:
    try:
        conn = _db_connect()
        conn.execute(
            "INSERT INTO poll_votes(class_id, qid, device_id, created_at) VALUES(?,?,?,?);",
            (cid, qid, device_id, now_ts()),
        )
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


# ---------------------------
# 10) UI: LOGIN (NHẸ)
# ---------------------------
def render_login():
    st.markdown(
        f"""
<style>
.login-card {{
  max-width: 520px; margin: 3vh auto; background:#fff;
  border:1px solid #e5e7eb; padding: 24px; border-radius: 16px;
  box-shadow: 0 18px 55px rgba(0,0,0,0.08);
}}
.brand {{
  display:flex; gap:14px; align-items:center; margin-bottom:16px;
}}
.brand img {{ width:72px; height:auto; }}
.brand h1 {{
  margin:0; font-size: 20px; font-weight: 900; color: #111827;
}}
.brand p {{ margin:0; color:{MUTED}; font-weight:700; font-size: 13px; }}
.small {{ color:{MUTED}; font-size: 12px; font-weight: 700; }}
hr {{ border:none; border-top:1px solid #e5e7eb; margin:14px 0; }}
</style>
""",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='login-card'>", unsafe_allow_html=True)
    st.markdown(
        f"""
<div class="brand">
  <img src="{LOGO_URL}"/>
  <div>
    <h1>{APP_TITLE_VN}</h1>
    <p>{APP_TITLE_EN}</p>
  </div>
</div>
<div class="small">Hệ thống tương tác lớp học — tối ưu chịu tải (HV chỉ gửi, GV xem/điều khiển)</div>
<hr/>
""",
        unsafe_allow_html=True,
    )

    portal = st.radio("Cổng đăng nhập", ["Học viên", "Giảng viên"], horizontal=True, label_visibility="collapsed")

    if portal == "Học viên":
        c_class = st.selectbox("Lớp học phần", list(CLASSES.keys()))
        c_pass = st.text_input("Mã bảo mật", type="password", placeholder="Nhập mã lớp...")
        remember = st.checkbox("Ghi nhớ đăng nhập (12 giờ)", value=True)

        if st.button("ĐĂNG NHẬP"):
            cid = CLASSES[c_class]
            if c_pass.strip() == PASSWORDS.get(cid, ""):
                tok = issue_login_token("student", cid, ttl_hours=(TOKEN_TTL_HOURS_DEFAULT if remember else 2))
                qp_set(t=tok)
                st.session_state["logged_in"] = True
                st.session_state["role"] = "student"
                st.session_state["class_id"] = cid
                st.session_state["page"] = "class_home"
                st.rerun()
            else:
                st.error("Mã bảo mật không chính xác.")
    else:
        gv_class = st.selectbox("Lớp quản lý", list(CLASSES.keys()))
        t_pass = st.text_input("Mật khẩu Giảng viên", type="password", placeholder="Nhập mật khẩu...")
        remember = st.checkbox("Ghi nhớ đăng nhập (12 giờ)", value=True)

        if st.button("TRUY CẬP QUẢN TRỊ"):
            if t_pass.strip() != TEACHER_PASSWORD:
                st.error("Sai mật khẩu.")
            else:
                cid = CLASSES[gv_class]
                tok = issue_login_token("teacher", cid, ttl_hours=(TOKEN_TTL_HOURS_DEFAULT if remember else 2))
                qp_set(t=tok)
                st.session_state["logged_in"] = True
                st.session_state["role"] = "teacher"
                st.session_state["class_id"] = cid
                st.session_state["page"] = "class_home"
                st.rerun()

    st.markdown(
        """
<hr/>
<div class="small" style="text-align:center;">
Phát triển bởi Giảng viên <b>Trần Nguyễn Sĩ Nguyên</b>
</div>
""",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# ---------------------------
# 11) SIDEBAR (GIẢM TẢI: bỏ audio)
# ---------------------------
def render_sidebar():
    with st.sidebar:
        st.image(LOGO_URL, width=86)
        st.markdown("---")
        cls_txt = next((k for k, v in CLASSES.items() if v == st.session_state["class_id"]), st.session_state["class_id"])
        role = "HỌC VIÊN" if st.session_state["role"] == "student" else "GIẢNG VIÊN"
        st.info(f"👤 {role}\n\n🏫 {cls_txt}")

        if st.session_state["role"] == "teacher":
            st.markdown("**Chuyển lớp quản lý**")
            cls_keys = list(CLASSES.keys())
            curr_cid = st.session_state.get("class_id", "lop1")
            curr_label = next((k for k, v in CLASSES.items() if v == curr_cid), cls_keys[0])
            idx = cls_keys.index(curr_label) if curr_label in cls_keys else 0
            new_label = st.selectbox("Chọn lớp", cls_keys, index=idx)
            new_cid = CLASSES[new_label]
            if new_cid != curr_cid:
                st.session_state["class_id"] = new_cid
                st.session_state["page"] = "class_home"
                st.rerun()

        st.markdown("---")
        if st.button("📚 Danh mục hoạt động"):
            st.session_state["page"] = "class_home"
            st.rerun()
        if st.button("🏠 Dashboard"):
            st.session_state["page"] = "dashboard"
            st.rerun()
        st.markdown("---")
        if st.button("↩️ Quay lại đăng nhập"):
            reset_to_login()


# ---------------------------
# 12) CLASS HOME
# ---------------------------
ACTS = [
    ("wordcloud", "Word Cloud (từ khóa)"),
    ("poll", "Poll (trắc nghiệm nhanh)"),
    ("openended", "Open Ended (trả lời mở)"),
    ("scales", "Scales (tự đánh giá)"),
    ("ranking", "Ranking (xếp hạng)"),
    ("pin", "Pin (ghim tọa độ)"),
]


def render_class_home():
    cid = st.session_state["class_id"]
    seed_questions_if_missing(cid)
    cfg = get_default_cfg(cid)
    topic = class_topic(cid)

    cls_txt = next((k for k, v in CLASSES.items() if v == cid), cid)
    st.markdown(
        f"""
<h2 style="margin:0;color:{PRIMARY_COLOR};font-weight:900;">📚 Danh mục hoạt động</h2>
<div style="color:{MUTED};font-weight:800;">{cls_txt} • Chủ đề: {topic}</div>
""",
        unsafe_allow_html=True,
    )

    colA, colB = st.columns([1, 5])
    with colA:
        if st.button("↩️ Đăng xuất"):
            reset_to_login()
    with colB:
        st.caption("Học viên: vào hoạt động và gửi. Giảng viên: xem thống kê/điều khiển ở Dashboard/Activity.")

    # Count: wordcloud & openended theo câu active; còn lại theo Q1 (ổn định)
    wc_active = get_active_question(cid, "wordcloud")
    oe_active = get_active_question(cid, "openended")

    for key, title in ACTS:
        c1, c2 = st.columns([6, 1])
        with c1:
            if key == "wordcloud":
                n = count_submissions(cid, "wordcloud", wc_active["qid"])
                extra = f" • Active: <b>{wc_active['qid']}</b>"
            elif key == "openended":
                n = count_submissions(cid, "openended", oe_active["qid"])
                extra = f" • Active: <b>{oe_active['qid']}</b>"
            else:
                n = count_submissions(cid, key, "Q1")
                extra = ""

            st.markdown(
                f"""
<div style="background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:16px;
box-shadow:0 10px 28px rgba(0,0,0,0.06);margin:10px 0;">
  <div style="font-weight:900;font-size:18px;">{title}</div>
  <div style="color:{MUTED};font-weight:800;">
    Lượt gửi: <b>{n}</b>{extra}
  </div>
</div>
""",
                unsafe_allow_html=True,
            )
        with c2:
            if st.button("MỞ", key=f"open_{key}"):
                st.session_state["page"] = "activity"
                st.session_state["current_act"] = key
                st.rerun()


# ---------------------------
# 13) DASHBOARD (GV: có thể auto refresh; HV: chỉ xem số liệu)
# ---------------------------
def render_dashboard():
    cid = st.session_state["class_id"]
    topic = class_topic(cid)

    st.markdown(
        f"<h2 style='margin:0;color:{PRIMARY_COLOR};font-weight:900;'>🏠 Dashboard</h2>",
        unsafe_allow_html=True,
    )
    st.caption(f"Chủ đề lớp: {topic}")

    # Teacher can autorefresh; student NEVER autorefresh
    if st.session_state["role"] == "teacher":
        colX, colY = st.columns([2, 6])
        with colX:
            live = st.toggle("🔴 Live (2s)", value=False, key="dash_live")
        with colY:
            st.caption("Khuyến nghị: chỉ bật live khi cần trình chiếu; mặc định tắt để giảm tải.")
        if live:
            if st_autorefresh is not None:
                st_autorefresh(interval=2000, key="dash_refresh")
            else:
                st.warning("Thiếu streamlit-autorefresh (GV mới cần).")

    wc_active = get_active_question(cid, "wordcloud")
    oe_active = get_active_question(cid, "openended")

    metrics = [
        ("WORDCLOUD (ACTIVE)", count_submissions(cid, "wordcloud", wc_active["qid"])),
        ("POLL", count_submissions(cid, "poll", "Q1")),
        ("OPEN ENDED (ACTIVE)", count_submissions(cid, "openended", oe_active["qid"])),
        ("SCALES", count_submissions(cid, "scales", "Q1")),
        ("RANKING", count_submissions(cid, "ranking", "Q1")),
        ("PIN", count_submissions(cid, "pin", "Q1")),
    ]

    cols = st.columns(3)
    for i, (label, val) in enumerate(metrics):
        with cols[i % 3]:
            st.markdown(
                f"""
<div style="background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:16px;
box-shadow:0 10px 28px rgba(0,0,0,0.06);text-align:center;margin:10px 0;">
  <div style="font-size:44px;font-weight:900;color:{PRIMARY_COLOR};line-height:1;">{val}</div>
  <div style="color:{MUTED};font-weight:900;text-transform:uppercase;font-size:12px;margin-top:8px;">{label}</div>
</div>
""",
                unsafe_allow_html=True,
            )


# ---------------------------
# 14) ACTIVITY PAGES — HV: chỉ gửi | GV: xem + live tùy bật + AI tùy bật
# ---------------------------
def render_wordcloud(cid: str):
    q = get_active_question(cid, "wordcloud")
    qid, qtext = q["qid"], q["text"]

    st.markdown(f"### ☁️ Word Cloud — Câu đang kích hoạt ({qid})")
    st.info(qtext)

    # HỌC VIÊN: chỉ form gửi, KHÔNG live
    if st.session_state["role"] == "student":
        with st.form("wc_form"):
            name = st.text_input("Tên")
            kw = st.text_input("Nhập 1 từ khóa / cụm từ")
            ok = st.form_submit_button("GỬI")
        if ok:
            if submit(cid, "wordcloud", qid, name, kw, device_id=st.session_state.get("device_id")):
                st.success("Đã gửi!")
            else:
                st.warning("Vui lòng nhập đủ Tên và Từ khóa.")
        st.caption("Học viên không cần refresh; giảng viên sẽ xem kết quả ở chế độ giảng viên.")
        return

    # GIẢNG VIÊN
    topA, topB, topC = st.columns([2, 2, 6])
    with topA:
        live = st.toggle("🔴 Live (2s)", value=False, key="wc_live_teacher")
    with topB:
        if st.button("🔄 Làm mới (manual)"):
            st.cache_data.clear()
            st.rerun()
    with topC:
        st.caption("Khuyến nghị: live chỉ bật khi trình chiếu; mặc định tắt để giảm tải.")

    if live:
        if st_autorefresh is not None:
            st_autorefresh(interval=2000, key="wc_refresh_teacher")
        else:
            st.warning("Thiếu streamlit-autorefresh (không bắt buộc).")

    # Kết quả: hiển thị dạng Top list (nhẹ hơn wordcloud JS)
    rows = fetch_latest(cid, "wordcloud", qid, limit=300)

    # normalize + count unique by person (tránh spam)
    def norm(s: str) -> str:
        s = (s or "").strip().lower()
        s = re.sub(r"\s+", " ", s)
        s = s.strip(" .,:;!?\"'`()[]{}<>|\\/+-=*#@~^_")
        return s

    seen = set()
    freq = {}
    for r in rows:
        name = (r.get("name") or "").strip()
        ph = norm(r.get("content") or "")
        if not name or not ph:
            continue
        key = (name, ph)
        if key in seen:
            continue
        seen.add(key)
        freq[ph] = freq.get(ph, 0) + 1

    st.markdown("#### 📌 Top cụm từ (đếm theo số người nhập, đã chống trùng theo tên)")
    if not freq:
        st.info("Chưa có dữ liệu.")
    else:
        items = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:30]
        st.dataframe(
            [{"Từ/cụm": k, "Số người nhập": v} for k, v in items],
            use_container_width=True,
            hide_index=True,
        )

    # Quản trị câu hỏi
    st.markdown("---")
    with st.expander("🧠 Quản trị câu hỏi Wordcloud (thêm/sửa/kích hoạt/xóa khỏi danh sách)", expanded=True):
        qs = list_questions(cid, "wordcloud")
        qids = [x["qid"] for x in qs]
        active = next((x for x in qs if x["is_active"] == 1), qs[0])

        st.success(f"Đang active: ({active['qid']}) {active['text']}")

        c1, c2 = st.columns([2, 2])
        with c1:
            with st.form("wc_add_q"):
                new_text = st.text_area("Thêm câu hỏi mới", height=90)
                make_active = st.checkbox("Kích hoạt ngay", value=True)
                if st.form_submit_button("TẠO"):
                    new_id = make_new_qid(qids)
                    upsert_question(cid, "wordcloud", new_id, new_text, make_active=make_active)
                    st.cache_data.clear()
                    st.toast("Đã tạo câu hỏi.")
                    st.rerun()

        with c2:
            with st.form("wc_edit_active"):
                edit_text = st.text_area("Sửa câu đang active", value=active["text"], height=90)
                if st.form_submit_button("LƯU SỬA"):
                    upsert_question(cid, "wordcloud", active["qid"], edit_text, make_active=True)
                    st.cache_data.clear()
                    st.toast("Đã cập nhật.")
                    st.rerun()

        st.markdown("**Kích hoạt câu bất kỳ**")
        pick = st.selectbox("Chọn Q", [f"{x['qid']} — {x['text'][:70]}" for x in qs])
        pick_qid = pick.split("—")[0].strip()
        if st.button("KÍCH HOẠT"):
            set_active_question(cid, "wordcloud", pick_qid)
            st.cache_data.clear()
            st.toast("Đã kích hoạt.")
            st.rerun()

        st.markdown("**Xóa khỏi danh sách (không xóa submissions lịch sử)**")
        del_pick = st.selectbox("Chọn Q để xóa", [x["qid"] for x in qs], key="wc_del_pick")
        if st.button("XÓA Q"):
            if len(qs) <= 1:
                st.warning("Phải còn ít nhất 1 câu.")
            else:
                delete_question_from_list(cid, "wordcloud", del_pick)
                st.cache_data.clear()
                st.toast("Đã xóa khỏi danh sách.")
                st.rerun()

    # AI (tùy bật)
    st.markdown("---")
    with st.expander("🤖 AI phân tích (Wordcloud) — chỉ bật khi cần", expanded=False):
        show_ai = st.toggle("Bật AI", value=False, key="wc_ai_on")
        if not show_ai:
            st.caption("Tắt AI để giảm gọi mạng/chi phí; bật khi cần phân tích nhanh.")
            return
        model = get_gemini_model()
        if model is None:
            st.warning("Chưa cấu hình GEMINI_API_KEY trong st.secrets hoặc lỗi khởi tạo.")
            return
        prompt = st.text_area(
            "Yêu cầu phân tích",
            value="Rút ra 5 insight, phân nhóm từ khóa theo chủ đề, chỉ ra 3 hiểu lầm có thể có và 3 can thiệp sư phạm ngay tại lớp.",
            height=120,
        )
        if st.button("PHÂN TÍCH"):
            if not freq:
                st.warning("Chưa có dữ liệu để phân tích.")
            else:
                top_items = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:25]
                payload = f"""
Bạn là trợ giảng cho giảng viên.
CHỦ ĐỀ LỚP: {class_topic(cid)}
WORDCLOUD ({qid}): {qtext}

TOP 25 CỤM (chuẩn hoá) theo số người nhập:
{top_items}

YÊU CẦU:
{prompt}

Trả lời theo cấu trúc:
1) 3–5 phát hiện chính
2) Nhóm chủ đề + ví dụ
3) 2–3 hiểu lầm phổ biến + cách chỉnh
4) 3 can thiệp sư phạm
5) 3 câu hỏi gợi mở
"""
                with st.spinner("AI đang phân tích..."):
                    res = model.generate_content(payload)
                st.info(res.text)


def render_poll(cid: str):
    cfg = get_default_cfg(cid)
    qid = "Q1"  # poll giữ ổn định
    st.markdown("### 📊 Poll")
    st.info(cfg["poll_q"])

    options = cfg["poll_opts"]
    device_id = st.session_state.get("device_id", "")

    # HỌC VIÊN
    if st.session_state["role"] == "student":
        if poll_has_voted(cid, qid, device_id):
            st.error("Thiết bị này đã bình chọn. Mỗi thiết bị 1 lần.")
            return
        with st.form("poll_form"):
            name = st.text_input("Tên")
            vote = st.radio("Lựa chọn", options)
            ok = st.form_submit_button("BÌNH CHỌN")
        if ok:
            if not name.strip():
                st.warning("Vui lòng nhập Tên.")
                return
            if not poll_mark_voted(cid, qid, device_id):
                st.error("Không thể khóa bình chọn (có thể do đã vote). Thử tải lại trang.")
                return
            submit(cid, "poll", qid, name, vote, device_id=device_id)
            st.success("Đã bình chọn!")
        return

    # GIẢNG VIÊN
    topA, topB = st.columns([2, 8])
    with topA:
        live = st.toggle("🔴 Live (2s)", value=False, key="poll_live_teacher")
    with topB:
        st.caption(f"Đáp án gợi ý (GV): **{cfg['poll_correct']}** • Live mặc định tắt để giảm tải.")
    if live and st_autorefresh is not None:
        st_autorefresh(interval=2000, key="poll_refresh_teacher")

    counts = fetch_poll_counts(cid, qid)
    if not counts:
        st.info("Chưa có bình chọn.")
        return

    # Plotly import muộn (chỉ GV)
    import plotly.graph_objects as go

    x = [c["option"] for c in counts]
    y = [c["n"] for c in counts]
    fig = go.Figure(data=[go.Bar(x=x, y=y, text=y, textposition="auto")])
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)


def render_openended(cid: str):
    q = get_active_question(cid, "openended")
    qid, qtext = q["qid"], q["text"]

    st.markdown(f"### 💬 Open Ended — Câu đang kích hoạt ({qid})")
    st.info(qtext)

    # HỌC VIÊN: chỉ gửi
    if st.session_state["role"] == "student":
        with st.form("oe_form"):
            name = st.text_input("Tên")
            ans = st.text_area("Câu trả lời", height=160)
            ok = st.form_submit_button("GỬI")
        if ok:
            if submit(cid, "openended", qid, name, ans, device_id=st.session_state.get("device_id")):
                st.success("Đã gửi!")
            else:
                st.warning("Vui lòng nhập đủ Tên và nội dung.")
        st.caption("Học viên không live refresh để tránh nghẽn; giảng viên sẽ xem theo chế độ giảng viên.")
        return

    # GIẢNG VIÊN
    topA, topB, topC = st.columns([2, 2, 6])
    with topA:
        live = st.toggle("🔴 Live (2s)", value=False, key="oe_live_teacher")
    with topB:
        if st.button("🔄 Làm mới (manual)"):
            st.cache_data.clear()
            st.rerun()
    with topC:
        st.caption("Khuyến nghị: live chỉ bật khi trình chiếu; mặc định tắt để giảm tải.")

    if live and st_autorefresh is not None:
        st_autorefresh(interval=2000, key="oe_refresh_teacher")

    wall = fetch_latest(cid, "openended", qid, limit=80)  # giới hạn để nhẹ
    st.markdown("#### 🧱 Bức tường (80 ý mới nhất)")
    if not wall:
        st.info("Chưa có câu trả lời.")
    else:
        for r in wall:
            st.markdown(
                f"""
<div style="background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:12px;
box-shadow:0 6px 18px rgba(0,0,0,0.05);margin:10px 0;">
  <b>{r['name']}</b>: {r['content']}
  <div style="color:{MUTED};font-size:12px;font-weight:700;margin-top:6px;">{r['created_at']}</div>
</div>
""",
                unsafe_allow_html=True,
            )

    # Quản trị câu hỏi
    st.markdown("---")
    with st.expander("🧠 Quản trị câu hỏi Open Ended", expanded=True):
        qs = list_questions(cid, "openended")
        qids = [x["qid"] for x in qs]
        active = next((x for x in qs if x["is_active"] == 1), qs[0])
        st.success(f"Đang active: ({active['qid']}) {active['text']}")

        c1, c2 = st.columns([2, 2])
        with c1:
            with st.form("oe_add_q"):
                new_text = st.text_area("Thêm câu hỏi mới", height=90)
                make_active = st.checkbox("Kích hoạt ngay", value=True, key="oe_make_active")
                if st.form_submit_button("TẠO"):
                    new_id = make_new_qid(qids)
                    upsert_question(cid, "openended", new_id, new_text, make_active=make_active)
                    st.cache_data.clear()
                    st.toast("Đã tạo câu hỏi.")
                    st.rerun()
        with c2:
            with st.form("oe_edit_active"):
                edit_text = st.text_area("Sửa câu đang active", value=active["text"], height=90)
                if st.form_submit_button("LƯU SỬA"):
                    upsert_question(cid, "openended", active["qid"], edit_text, make_active=True)
                    st.cache_data.clear()
                    st.toast("Đã cập nhật.")
                    st.rerun()

        st.markdown("**Kích hoạt câu bất kỳ**")
        pick = st.selectbox("Chọn Q", [f"{x['qid']} — {x['text'][:70]}" for x in qs], key="oe_pick")
        pick_qid = pick.split("—")[0].strip()
        if st.button("KÍCH HOẠT", key="oe_activate"):
            set_active_question(cid, "openended", pick_qid)
            st.cache_data.clear()
            st.toast("Đã kích hoạt.")
            st.rerun()

        st.markdown("**Xóa khỏi danh sách (không xóa submissions lịch sử)**")
        del_pick = st.selectbox("Chọn Q để xóa", [x["qid"] for x in qs], key="oe_del_pick")
        if st.button("XÓA Q", key="oe_del_btn"):
            if len(qs) <= 1:
                st.warning("Phải còn ít nhất 1 câu.")
            else:
                delete_question_from_list(cid, "openended", del_pick)
                st.cache_data.clear()
                st.toast("Đã xóa khỏi danh sách.")
                st.rerun()

    # AI (tùy bật)
    st.markdown("---")
    with st.expander("🤖 AI phân tích (Open Ended) — chỉ bật khi cần", expanded=False):
        show_ai = st.toggle("Bật AI", value=False, key="oe_ai_on")
        if not show_ai:
            st.caption("Tắt AI để giảm gọi mạng/chi phí; bật khi cần tổng hợp nhanh.")
            return
        model = get_gemini_model()
        if model is None:
            st.warning("Chưa cấu hình GEMINI_API_KEY trong st.secrets hoặc lỗi khởi tạo.")
            return
        prompt = st.text_area(
            "Yêu cầu phân tích",
            value="Tóm tắt 3 xu hướng nổi bật, 3 lỗi lập luận phổ biến, trích 3 ví dụ tiêu biểu, và 3 can thiệp sư phạm.",
            height=140,
        )
        if st.button("PHÂN TÍCH", key="oe_ai_run"):
            if not wall:
                st.warning("Chưa có dữ liệu.")
                return
            # đưa cho AI bảng nhỏ (giới hạn để nhanh & rẻ)
            table = "\n".join([f"- {r['name']}: {r['content']}" for r in wall[:60]])
            payload = f"""
Bạn là trợ giảng cho giảng viên.
CHỦ ĐỀ LỚP: {class_topic(cid)}
OPEN ENDED ({qid}): {qtext}

DỮ LIỆU (60 ý mới nhất):
{table}

YÊU CẦU:
{prompt}

Trả lời theo cấu trúc:
1) 3 xu hướng nổi bật
2) 3 lỗi/thiếu sót phổ biến
3) 3 trích dẫn minh họa (nêu tên)
4) 3 can thiệp sư phạm
5) 3 câu hỏi gợi mở
"""
            with st.spinner("AI đang phân tích..."):
                res = model.generate_content(payload)
            st.info(res.text)


def render_scales(cid: str):
    cfg = get_default_cfg(cid)
    qid = "Q1"
    criteria = cfg["scales_criteria"]

    st.markdown("### 🕸️ Scales")
    st.info("Tự đánh giá theo tiêu chí (1: thấp – 5: cao).")

    if st.session_state["role"] == "student":
        with st.form("scales_form"):
            name = st.text_input("Tên")
            scores = [st.slider(c, 1, 5, 3) for c in criteria]
            ok = st.form_submit_button("GỬI")
        if ok:
            if not name.strip():
                st.warning("Vui lòng nhập Tên.")
                return
            submit(cid, "scales", qid, name, ",".join(map(str, scores)), device_id=st.session_state.get("device_id"))
            st.success("Đã lưu!")
        return

    # GV: tổng hợp (plotly import muộn)
    topA, topB = st.columns([2, 8])
    with topA:
        live = st.toggle("🔴 Live (2s)", value=False, key="scales_live_teacher")
    with topB:
        st.caption("Live mặc định tắt để giảm tải.")
    if live and st_autorefresh is not None:
        st_autorefresh(interval=2000, key="scales_refresh_teacher")

    # fetch latest to compute mean (giới hạn 400)
    rows = fetch_latest(cid, "scales", qid, limit=400)
    if not rows:
        st.info("Chưa có dữ liệu.")
        return

    matrix = []
    for r in rows:
        parts = (r["content"] or "").split(",")
        if len(parts) != len(criteria):
            continue
        try:
            matrix.append([int(x) for x in parts])
        except Exception:
            continue

    if not matrix:
        st.warning("Dữ liệu lỗi định dạng.")
        return

    import numpy as np
    import plotly.graph_objects as go

    avg = np.mean(np.array(matrix), axis=0).tolist()
    fig = go.Figure(data=go.Scatterpolar(r=avg, theta=criteria, fill="toself"))
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5])), showlegend=False)
    st.plotly_chart(fig, use_container_width=True)


def render_ranking(cid: str):
    cfg = get_default_cfg(cid)
    qid = "Q1"
    items = cfg["ranking_items"]

    st.markdown("### 🏆 Ranking")
    st.info("Sắp xếp thứ tự ưu tiên (quan trọng nhất lên đầu).")

    if st.session_state["role"] == "student":
        with st.form("rank_form"):
            name = st.text_input("Tên")
            rank = st.multiselect("Chọn theo thứ tự (chọn đủ tất cả mục)", items)
            ok = st.form_submit_button("NỘP")
        if ok:
            if not name.strip():
                st.warning("Vui lòng nhập Tên.")
                return
            if len(rank) != len(items):
                st.warning(f"Vui lòng chọn đủ {len(items)} mục.")
                return
            submit(cid, "ranking", qid, name, "->".join(rank), device_id=st.session_state.get("device_id"))
            st.success("Đã nộp!")
        return

    # GV: tổng hợp điểm (plotly import muộn)
    topA, topB = st.columns([2, 8])
    with topA:
        live = st.toggle("🔴 Live (2s)", value=False, key="rank_live_teacher")
    with topB:
        st.caption("Live mặc định tắt để giảm tải.")
    if live and st_autorefresh is not None:
        st_autorefresh(interval=2000, key="rank_refresh_teacher")

    rows = fetch_latest(cid, "ranking", qid, limit=400)
    if not rows:
        st.info("Chưa có dữ liệu.")
        return

    scores = {k: 0 for k in items}
    for r in rows:
        parts = (r["content"] or "").split("->")
        if len(parts) != len(items):
            continue
        for idx, it in enumerate(parts):
            if it in scores:
                scores[it] += (len(items) - idx)

    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    labels = [x[0] for x in sorted_items]
    vals = [x[1] for x in sorted_items]

    import plotly.express as px

    fig = px.bar(x=vals, y=labels, orientation="h", text=vals, labels={"x": "Tổng điểm", "y": "Mục"})
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)


def render_pin(cid: str):
    cfg = get_default_cfg(cid)
    qid = "Q1"
    st.markdown("### 📍 Pin")
    st.info(cfg["pin_q"])

    if st.session_state["role"] == "student":
        with st.form("pin_form"):
            name = st.text_input("Tên")
            x_val = st.slider("Ngang (0–100)", 0, 100, 50)
            y_val = st.slider("Dọc (0–100)", 0, 100, 50)
            ok = st.form_submit_button("GHIM")
        if ok:
            if not name.strip():
                st.warning("Vui lòng nhập Tên.")
                return
            submit(cid, "pin", qid, name, f"{x_val},{y_val}", device_id=st.session_state.get("device_id"))
            st.success("Đã ghim!")
        st.caption("Học viên chỉ gửi toạ độ. Giảng viên xem tổng hợp theo chế độ giảng viên.")
        return

    # GV: tổng hợp nhẹ (chỉ hiển thị ảnh + thống kê phân bố)
    topA, topB = st.columns([2, 8])
    with topA:
        live = st.toggle("🔴 Live (2s)", value=False, key="pin_live_teacher")
    with topB:
        st.caption("Live mặc định tắt để giảm tải.")
    if live and st_autorefresh is not None:
        st_autorefresh(interval=2000, key="pin_refresh_teacher")

    st.image(MAP_IMAGE, caption="Ảnh nền (minh hoạ)", use_container_width=True)

    rows = fetch_latest(cid, "pin", qid, limit=400)
    if not rows:
        st.info("Chưa có dữ liệu.")
        return

    pts = []
    for r in rows:
        try:
            x, y = (r["content"] or "").split(",")
            pts.append((int(x), int(y)))
        except Exception:
            continue

    if not pts:
        st.warning("Dữ liệu toạ độ lỗi định dạng.")
        return

    import numpy as np
    import plotly.express as px

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    df = {"x": xs, "y": ys}
    fig = px.density_heatmap(df, x="x", y="y", nbinsx=20, nbinsy=20)
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)


def render_activity():
    cid = st.session_state["class_id"]
    act = st.session_state.get("current_act", "wordcloud")

    # header
    topL, topR = st.columns([1, 7])
    with topL:
        if st.button("↩️ Về danh mục"):
            st.session_state["page"] = "class_home"
            st.rerun()
    with topR:
        st.markdown(
            f"<h2 style='margin:0;color:{PRIMARY_COLOR};font-weight:900;'>Hoạt động: {act}</h2>",
            unsafe_allow_html=True,
        )

    if act == "wordcloud":
        render_wordcloud(cid)
    elif act == "poll":
        render_poll(cid)
    elif act == "openended":
        render_openended(cid)
    elif act == "scales":
        render_scales(cid)
    elif act == "ranking":
        render_ranking(cid)
    elif act == "pin":
        render_pin(cid)
    else:
        st.info("Hoạt động không hợp lệ.")


# ---------------------------
# 15) ROUTER
# ---------------------------
if not st.session_state.get("logged_in", False):
    render_login()

render_sidebar()

page = st.session_state.get("page", "class_home")
if page == "class_home":
    render_class_home()
elif page == "dashboard":
    render_dashboard()
elif page == "activity":
    render_activity()
else:
    st.session_state["page"] = "class_home"
    st.rerun()
