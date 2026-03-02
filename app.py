# app.py
import os
import time
import sqlite3
from datetime import datetime

import streamlit as st

# =========================
# 0) CONFIG
# =========================
st.set_page_config(page_title="T05 Interactive", page_icon="🟩", layout="centered")

APP_TITLE = "T05 Interactive – Open Ended"
DB_PATH = os.environ.get("APP_DB_PATH", "app.db")

# Demo lớp & mật khẩu (giữ đúng logic của bạn, nhưng tối giản)
CLASSES = {f"Lớp học {i}": f"lop{i}" for i in range(1, 11)}
PASSWORDS = {f"lop{i}": f"T05-{i}" for i in range(1, 9)}
PASSWORDS.update({f"lop9": "LH9", "lop10": "LH10"})

TEACHER_PASSWORD = os.environ.get("TEACHER_PASSWORD", "779")

DEFAULT_QUESTION = "Hãy viết 3–7 câu trả lời cho câu hỏi của giảng viên."

# =========================
# 1) DB (SQLite WAL)
# =========================
def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA busy_timeout=5000;")  # 5s wait if locked
    return conn

def db_init():
    conn = db_connect()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_id TEXT NOT NULL,
        qid TEXT NOT NULL,
        student_name TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)
    # seed default question per class if missing
    conn.commit()
    conn.close()

def get_active_question(class_id: str) -> tuple[str, str]:
    # return (qid, question_text)
    conn = db_connect()
    # active qid
    cur = conn.execute(
        "SELECT value FROM settings WHERE key=?",
        (f"{class_id}:active_qid",)
    )
    row = cur.fetchone()
    qid = row[0] if row else "Q1"

    cur = conn.execute(
        "SELECT value FROM settings WHERE key=?",
        (f"{class_id}:question:{qid}",)
    )
    row = cur.fetchone()
    qtext = row[0] if row else DEFAULT_QUESTION

    conn.close()
    return qid, qtext

def set_active_question(class_id: str, qid: str, qtext: str):
    conn = db_connect()
    conn.execute(
        "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
        (f"{class_id}:active_qid", qid)
    )
    conn.execute(
        "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
        (f"{class_id}:question:{qid}", qtext.strip() or DEFAULT_QUESTION)
    )
    conn.commit()
    conn.close()

def list_questions(class_id: str) -> list[tuple[str, str]]:
    # returns [(qid, text), ...] sorted by qid number if possible
    conn = db_connect()
    cur = conn.execute(
        "SELECT key, value FROM settings WHERE key LIKE ?",
        (f"{class_id}:question:%",)
    )
    rows = cur.fetchall()
    conn.close()

    out = []
    for k, v in rows:
        # key format: class:question:Qn
        qid = k.split(":")[-1]
        out.append((qid, v))
    # stable sort
    def qnum(q):  # Q12 -> 12
        try:
            return int(q[0].lstrip("Qq"))
        except Exception:
            return 10**9
    out.sort(key=qnum)
    return out

def insert_response(class_id: str, qid: str, name: str, content: str):
    name = (name or "").strip()[:80]
    content = (content or "").strip()[:2000]
    if not name or not content:
        raise ValueError("missing")
    conn = db_connect()
    conn.execute(
        "INSERT INTO responses(class_id,qid,student_name,content,created_at) VALUES(?,?,?,?,?)",
        (class_id, qid, name, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()

def fetch_latest(class_id: str, qid: str, limit: int = 50):
    conn = db_connect()
    cur = conn.execute(
        "SELECT student_name, content, created_at FROM responses WHERE class_id=? AND qid=? "
        "ORDER BY id DESC LIMIT ?",
        (class_id, qid, int(limit))
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def fetch_all_text(class_id: str, qid: str, limit: int = 500):
    # dùng cho AI: lấy tối đa N câu (tránh prompt quá dài)
    conn = db_connect()
    cur = conn.execute(
        "SELECT student_name, content FROM responses WHERE class_id=? AND qid=? "
        "ORDER BY id DESC LIMIT ?",
        (class_id, qid, int(limit))
    )
    rows = cur.fetchall()
    conn.close()
    # đảo để AI đọc theo thời gian gần-đến-cũ hoặc tùy bạn
    rows.reverse()
    return rows

def clear_responses(class_id: str, qid: str):
    conn = db_connect()
    conn.execute("DELETE FROM responses WHERE class_id=? AND qid=?", (class_id, qid))
    conn.commit()
    conn.close()

# =========================
# 2) AI (Gemini) – only when teacher clicks
# =========================
@st.cache_resource
def get_gemini_model():
    try:
        import google.generativeai as genai
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        if not api_key:
            return None
        genai.configure(api_key=api_key)
        return genai.GenerativeModel("gemini-2.5-flash")
    except Exception:
        return None

# =========================
# 3) UI
# =========================
db_init()

st.markdown(f"## {APP_TITLE}")

if "auth" not in st.session_state:
    st.session_state.auth = {"ok": False, "role": None, "class_id": None}

def logout():
    st.session_state.auth = {"ok": False, "role": None, "class_id": None}
    st.rerun()

if not st.session_state.auth["ok"]:
    tab1, tab2 = st.tabs(["Học viên", "Giảng viên"])

    with tab1:
        cls_label = st.selectbox("Lớp học phần", list(CLASSES.keys()))
        class_id = CLASSES[cls_label]
        pw = st.text_input("Mã bảo mật lớp", type="password")
        if st.button("Đăng nhập (Học viên)", use_container_width=True):
            if pw.strip() == PASSWORDS.get(class_id, ""):
                st.session_state.auth = {"ok": True, "role": "student", "class_id": class_id}
                st.rerun()
            else:
                st.error("Sai mã lớp.")

    with tab2:
        cls_label = st.selectbox("Lớp quản lý", list(CLASSES.keys()), key="t_cls")
        class_id = CLASSES[cls_label]
        pw = st.text_input("Mật khẩu giảng viên", type="password", key="t_pw")
        if st.button("Đăng nhập (Giảng viên)", use_container_width=True):
            if pw.strip() == TEACHER_PASSWORD:
                st.session_state.auth = {"ok": True, "role": "teacher", "class_id": class_id}
                st.rerun()
            else:
                st.error("Sai mật khẩu giảng viên.")

    st.stop()

role = st.session_state.auth["role"]
class_id = st.session_state.auth["class_id"]
qid, question = get_active_question(class_id)

top = st.columns([4, 1])
with top[0]:
    st.caption(f"Vai trò: **{role.upper()}** • Lớp: **{class_id}** • Câu đang kích hoạt: **{qid}**")
with top[1]:
    if st.button("Đăng xuất"):
        logout()

st.markdown("---")
st.markdown(f"### 🧩 Câu hỏi ({qid})")
st.info(question)

# ---- Student submit ----
if role == "student":
    with st.form("submit_form", clear_on_submit=True):
        name = st.text_input("Tên")
        content = st.text_area("Câu trả lời", height=140)
        submitted = st.form_submit_button("GỬI", use_container_width=True)
    if submitted:
        try:
            insert_response(class_id, qid, name, content)
            st.success("Đã gửi.")
            # KHÔNG rerun liên tục; chỉ rerun đúng 1 lần sau gửi để UI sạch
            time.sleep(0.1)
            st.rerun()
        except ValueError:
            st.warning("Vui lòng nhập đủ Tên và nội dung.")
        except Exception as e:
            st.error(f"Lỗi ghi dữ liệu: {e}")

# ---- Wall (teacher + student can view) ----
st.markdown("### 💬 Bức tường (mới nhất)")
# Không live-refresh tự động. Ai cần thì bấm nút.
btns = st.columns([1, 1, 2])
with btns[0]:
    if st.button("🔄 Tải lại", use_container_width=True):
        st.rerun()
with btns[1]:
    limit = st.selectbox("Hiển thị", [30, 50, 100], index=0)
rows = fetch_latest(class_id, qid, limit=limit)

if not rows:
    st.info("Chưa có câu trả lời.")
else:
    # Hiển thị gọn để tránh lag
    for name, text, ts in rows:
        st.markdown(f"**{name}** — {ts}\n\n{text}\n\n---")

# ---- Teacher panel ----
if role == "teacher":
    st.markdown("## 👨‍🏫 Điều khiển giảng viên")

    with st.expander("1) Đổi / tạo câu hỏi", expanded=False):
        qs = list_questions(class_id)
        existing_ids = [q[0] for q in qs] if qs else ["Q1"]

        colA, colB = st.columns(2)
        with colA:
            new_qid = st.text_input("QID (ví dụ Q2, Q3…)", value="Q2")
        with colB:
            activate = st.checkbox("Kích hoạt ngay", value=True)

        new_qtext = st.text_area("Nội dung câu hỏi", height=120, value=question)

        if st.button("💾 Lưu câu hỏi", use_container_width=True):
            nq = (new_qid or "").strip().upper()
            if not nq.startswith("Q"):
                st.warning("QID phải dạng Q2, Q3...")
            else:
                set_active_question(class_id, nq if activate else qid, new_qtext)
                st.success("Đã lưu.")
                time.sleep(0.1)
                st.rerun()

        st.caption("Câu đã có:")
        if qs:
            st.write(", ".join([f"{a}" for a, _ in qs]))
        else:
            st.write("Chưa có câu nào ngoài Q1.")

    with st.expander("2) AI phân tích (chỉ chạy khi bấm)", expanded=True):
        model = get_gemini_model()
        prompt = st.text_area(
            "Yêu cầu phân tích",
            height=140,
            value=(
                "Hãy trả lời theo cấu trúc:\n"
                "1) 3–5 xu hướng chính\n"
                "2) 3 lỗi/nhầm lập luận phổ biến\n"
                "3) Trích 3–5 câu tiêu biểu (nêu tên)\n"
                "4) 3 can thiệp sư phạm ngay tại lớp\n"
                "5) 3 câu hỏi gợi mở thảo luận tiếp"
            )
        )

        if st.button("🤖 PHÂN TÍCH NGAY", use_container_width=True):
            if model is None:
                st.error("Chưa có GEMINI_API_KEY trong secrets.")
            else:
                data = fetch_all_text(class_id, qid, limit=300)
                if not data:
                    st.warning("Chưa có dữ liệu để phân tích.")
                else:
                    blob = "\n".join([f"- {n}: {t}" for n, t in data])
                    payload = (
                        f"CHỦ ĐỀ: {class_id}\n"
                        f"CÂU HỎI ({qid}): {question}\n\n"
                        f"DỮ LIỆU HỌC VIÊN:\n{blob}\n\n"
                        f"YÊU CẦU:\n{prompt}\n"
                    )
                    with st.spinner("AI đang phân tích..."):
                        res = model.generate_content(payload)
                    st.success("Xong.")
                    st.markdown(res.text)

    with st.expander("3) Dọn dữ liệu câu hiện tại (cẩn thận)", expanded=False):
        if st.button("🗑 XÓA TOÀN BỘ TRẢ LỜI CỦA CÂU ĐANG KÍCH HOẠT", use_container_width=True):
            clear_responses(class_id, qid)
            st.success("Đã xóa.")
            time.sleep(0.1)
            st.rerun()
