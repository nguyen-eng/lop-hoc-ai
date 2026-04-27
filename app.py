# app.py
# ============================================================
# T05 Interactive Class (Optimized for 100+ concurrent students)
# Goals:
# 1) STUDENT: submit-only, NO live refresh, NO class-wide results visibility.
# 2) TEACHER: full features + live dashboards (including WordCloud preserved).
# ============================================================

import os
import re
import json
import uuid
import time
import threading
import copy
import hashlib
from datetime import datetime

import streamlit as st
import pandas as pd
import numpy as np

# Optional: live refresh helper (teacher-only usage)
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# Optional: dialog decorator (teacher-only usage)
_DIALOG_DECORATOR = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)

# ============================================================
# 0) CONFIG (UI)
# ============================================================
st.set_page_config(
    page_title="T05 Interactive Class",
    page_icon="📶",
    layout="wide",
    initial_sidebar_state="collapsed",
)

LOGO_URL = "https://drive.google.com/thumbnail?id=1PsUr01oeleJkW2JB1gqnID9WJNsTMFGW&sz=w1000"
MAP_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/Blank_map_of_Vietnam.svg/858px-Blank_map_of_Vietnam.svg.png"

PRIMARY_COLOR = "#006a4e"
BG_COLOR = "#f0f2f5"
TEXT_COLOR = "#111827"
MUTED = "#64748b"

# Hide Streamlit chrome
st.markdown(
    """
<style>
header, footer, #MainMenu {display:none !important;}
.block-container {padding-top: 0.2rem !important;}
</style>
""",
    unsafe_allow_html=True,
)

# Keep your big-font style (OK), but avoid overly heavy selectors
st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap');
html, body, [class*="css"] {{
  font-family: 'Montserrat', sans-serif;
  background-color: {BG_COLOR};
  color: {TEXT_COLOR};
}}
/* Buttons */
div.stButton > button {{
  background-color: {PRIMARY_COLOR};
  color: white;
  border: none;
  border-radius: 16px;
  padding: 14px 16px;
  font-weight: 800;
  width: 100%;
}}
div.stButton > button:hover {{ background-color: #00503a; }}
/* Cards */
.viz-card {{
  background: white;
  padding: 18px;
  border-radius: 18px;
  border: 1px solid #e2e8f0;
  box-shadow: 0 8px 24px rgba(0,0,0,0.06);
}}
.note-card {{
  background: #fff;
  padding: 14px 14px;
  border-radius: 14px;
  border-left: 6px solid {PRIMARY_COLOR};
  margin-bottom: 10px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.06);
}}
.small-muted {{ color: {MUTED}; font-weight: 700; }}
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# 1) AI (Teacher-only)
#   - Do NOT initialize Gemini for students to reduce load
# ============================================================
@st.cache_resource(show_spinner=False)
def get_ai_client():
    """
    Khởi tạo Google Gen AI client.
    Ưu tiên lấy GEMINI_API_KEY từ biến môi trường, sau đó lấy từ st.secrets.
    """
    try:
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            try:
                api_key = st.secrets.get("GEMINI_API_KEY")
            except Exception:
                api_key = None

        if not api_key or not str(api_key).strip():
            return None, "Chưa cấu hình GEMINI_API_KEY trong ENV hoặc st.secrets."

        client = genai.Client(api_key=str(api_key).strip())
        return client, None

    except ImportError:
        return None, "Chưa cài thư viện google-genai. Hãy chạy: pip install -U google-genai"

    except Exception as e:
        return None, f"Lỗi khởi tạo Gemini: {repr(e)}"


def run_gemini_ai(payload: str, model_name: str = "gemini-2.5-flash-lite") -> tuple[str | None, str | None]:
    client, err = get_ai_client()
    if err:
        return None, err
    try:
        response = client.models.generate_content(
            model=model_name,
            contents=payload[:12000],
        )
        text = getattr(response, "text", None)
        if not text:
            try:
                parts = response.candidates[0].content.parts
                text = "\n".join([getattr(p, "text", "") for p in parts if getattr(p, "text", "")])
            except Exception:
                text = None
        if not text or not str(text).strip():
            return None, "Gemini đã phản hồi nhưng không có nội dung text. Raw response rút gọn: " + repr(response)[:2500]
        return str(text).strip(), None
    except Exception as e:
        msg = str(e)
        raw = repr(e)[:2200]
        if "RESOURCE_EXHAUSTED" in msg or "Quota exceeded" in msg or "429" in msg:
            return None, "Đã vượt quota Gemini API hoặc model hiện tại không còn quota miễn phí. Đây là lỗi quota/billing, không phải lỗi giao diện. Chi tiết: " + raw
        if "PERMISSION_DENIED" in msg or "403" in msg:
            return None, "API key chưa có quyền sử dụng Gemini API hoặc dịch vụ Gemini API chưa được bật. Chi tiết: " + raw
        if "API_KEY_INVALID" in msg or "API key not valid" in msg:
            return None, "API key Google AI không hợp lệ hoặc không còn dùng được. Chi tiết: " + raw
        if "NOT_FOUND" in msg or "404" in msg:
            return None, "Không tìm thấy model hoặc model này chưa hỗ trợ key hiện tại. Thử gemini-2.0-flash hoặc gemini-1.5-flash. Chi tiết: " + raw
        return None, "Lỗi khi gọi Gemini API: " + raw

# ============================================================
# 2) DATA LAYER (CSV append-only + teacher cached reads)
# ============================================================
data_lock = threading.Lock()

def safe_text(s: str) -> str:
    s = str(s or "")
    s = s.replace("|", "-").replace("\n", " ").strip()
    return s

def get_path(cid: str, act: str, suffix: str = "") -> str:
    suffix = str(suffix or "").strip()
    if suffix:
        return f"data_{cid}_{act}_{suffix}.csv"
    return f"data_{cid}_{act}.csv"

def save_row(cid: str, act: str, name: str, content: str, suffix: str = ""):
    """Append-only write. Students only hit this function."""
    name = safe_text(name)
    content = safe_text(content)
    ts = datetime.now().strftime("%H:%M:%S")
    row = f"{name}|{content}|{ts}\n"
    path = get_path(cid, act, suffix)
    with data_lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(row)


def class_display_name(cid: str) -> str:
    """Return the human-readable class name from class id."""
    return next((k for k, v in CLASSES.items() if v == cid), cid)


def safe_filename_part(text: str) -> str:
    """Make a Vietnamese-friendly but filesystem-safe file name segment."""
    text = str(text or "").strip()
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^\w\-\u00C0-\u1EF9]+", "", text, flags=re.UNICODE)
    return text[:80] or "du_lieu"


def build_external_ai_export(
    cid: str,
    act: str,
    qtext: str,
    df: pd.DataFrame,
    ai_prompt: str,
    extra_context: str = "",
) -> str:
    """
    Build a self-contained Markdown package for teachers to upload to ChatGPT or another AI.
    Includes class name, active activity/question, teacher AI instruction, and learner responses.
    """
    cls_name = class_display_name(cid)
    act_name = ACT_LABELS.get(act, act)
    exported_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if df is None or df.empty:
        data_block = "Chưa có dữ liệu phản hồi của học viên."
        total = 0
        unique_students = 0
    else:
        export_df = df.copy()
        for col in ["Học viên", "Nội dung", "Thời gian"]:
            if col not in export_df.columns:
                export_df[col] = ""
        export_df = export_df[["Học viên", "Nội dung", "Thời gian"]].fillna("")
        total = int(len(export_df))
        unique_students = int(export_df["Học viên"].astype(str).str.strip().replace("", pd.NA).dropna().nunique())
        def _md_escape(value):
            text = str(value).replace("\r", " ").replace("\n", " ").strip()
            return text.replace("|", "\\|")
        
        columns = ["Học viên", "Nội dung", "Thời gian"]
        lines = [
            "| " + " | ".join(columns) + " |",
            "| " + " | ".join(["---"] * len(columns)) + " |",
        ]
        
        for _, row in export_df.iterrows():
            lines.append("| " + " | ".join(_md_escape(row[col]) for col in columns) + " |")
        
        data_block = "\n".join(lines)
    ai_prompt = str(ai_prompt or "").strip()
    if not ai_prompt:
        ai_prompt = "Giảng viên chưa nhập yêu cầu AI phân tích riêng. Hãy phân tích dữ liệu theo hướng sư phạm, chỉ ra xu hướng, hiểu lầm, điểm mạnh/yếu và gợi ý can thiệp trên lớp."

    qtext = str(qtext or "").strip() or "Chưa thiết lập câu hỏi/vấn đề."
    extra_context = str(extra_context or "").strip()

    parts = [
        "# GÓI DỮ LIỆU PHÂN TÍCH PHẢN HỒI HỌC VIÊN",
        "",
        "## 1. Thông tin lớp học và hoạt động",
        f"- Lớp học: {cls_name}",
        f"- Mã lớp: {cid}",
        f"- Hoạt động: {act_name}",
        f"- Thời điểm trích xuất: {exported_at}",
        f"- Tổng lượt phản hồi: {total}",
        f"- Số học viên tham gia: {unique_students}",
        "",
        "## 2. Câu hỏi/vấn đề đang kích hoạt",
        qtext,
        "",
    ]
    if extra_context:
        parts.extend(["## 3. Bối cảnh/cấu hình bổ sung", extra_context, ""])
        prompt_heading = "## 4. Yêu cầu AI phân tích của giảng viên"
        data_heading = "## 5. Dữ liệu phản hồi của học viên"
        final_heading = "## 6. Nhiệm vụ cho AI nhận file này"
    else:
        prompt_heading = "## 3. Yêu cầu AI phân tích của giảng viên"
        data_heading = "## 4. Dữ liệu phản hồi của học viên"
        final_heading = "## 5. Nhiệm vụ cho AI nhận file này"

    parts.extend([
        prompt_heading,
        ai_prompt,
        "",
        data_heading,
        data_block,
        "",
        final_heading,
        "Hãy phân tích trực tiếp dữ liệu trên theo đúng yêu cầu của giảng viên; ưu tiên nhận diện xu hướng nhận thức, phân nhóm câu trả lời, phát hiện hiểu lầm/sai lệch, chọn ví dụ tiêu biểu và đề xuất can thiệp sư phạm khả thi ngay trên lớp.",
        "",
    ])
    return "\n".join(parts)

def _read_csv(cid: str, act: str, suffix: str = "") -> pd.DataFrame:
    path = get_path(cid, act, suffix)
    if not os.path.exists(path):
        return pd.DataFrame(columns=["Học viên", "Nội dung", "Thời gian"])
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
        # Ensure columns
        for c in ["Học viên", "Nội dung", "Thời gian"]:
            if c not in df.columns:
                df[c] = ""
        return df[["Học viên", "Nội dung", "Thời gian"]]
    except Exception:
        return pd.DataFrame(columns=["Học viên", "Nội dung", "Thời gian"])

@st.cache_data(ttl=1.5, show_spinner=False)
def load_data_cached(cid: str, act: str, suffix: str = "") -> pd.DataFrame:
    """Teacher-only usage: cached read to reduce disk thrash during live refresh."""
    return _read_csv(cid, act, suffix)

def clear_activity(cid: str, act: str, suffix: str = ""):
    path = get_path(cid, act, suffix)
    with data_lock:
        if os.path.exists(path):
            os.remove(path)
    # bust cache
    load_data_cached.clear()

# ============================================================
# 3) AUTH (Token in URL to keep login through reruns)
# ============================================================
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

def validate_login_token(tok: str):
    tok = str(tok or "").strip()
    if not tok:
        return None
    tokens = _load_tokens()
    info = tokens.get(tok)
    if not info:
        return None
    try:
        if float(info.get("exp", 0)) < time.time():
            tokens.pop(tok, None)
            _save_tokens(tokens)
            return None
    except Exception:
        return None
    return info

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

def reset_to_login():
    qp_clear()
    st.session_state.clear()
    st.rerun()

# ============================================================
# 4) CLASS + PASSWORDS + ACT CONFIG
# ============================================================
CLASSES = {f"Lớp học {i}": f"lop{i}" for i in range(1, 11)}

PASSWORDS = {f"lop{i}": f"T05-{i}" for i in range(1, 9)}
PASSWORDS.update({f"lop{i}": f"LH{i}" for i in range(9, 11)})

# Không gắn sẵn chủ đề/câu hỏi cho từng lớp.
# Giảng viên vào từng hoạt động để thiết lập câu hỏi/vấn đề, phương án,
# tiêu chí, mục xếp hạng và prompt AI.
CLASS_ACT_CONFIG = {}
for i in range(1, 11):
    cid = f"lop{i}"
    CLASS_ACT_CONFIG[cid] = {
        "wordcloud": {"name": "Word Cloud", "question": ""},
        "poll": {"name": "Poll", "question": "", "options": []},
        "openended": {"name": "Open Ended", "question": ""},
        "scales": {"name": "Scales", "question": "", "criteria": []},
        "ranking": {"name": "Ranking", "question": "", "items": []},
        "pin": {"name": "Pin", "question": "", "image": MAP_IMAGE, "zones": []},
    }


# ============================================================
# 4B) TEACHER-CUSTOMIZABLE ACTIVITY CONFIG
# ============================================================
ACT_LABELS = {"wordcloud":"Word Cloud","poll":"Poll","openended":"Open Ended","scales":"Scales","ranking":"Ranking","pin":"Pin"}
DEFAULT_CLASS_ACT_CONFIG = copy.deepcopy(CLASS_ACT_CONFIG)
DEFAULT_AI_PROMPTS = {
    "wordcloud":"Phân tích dữ liệu phản hồi của học viên theo yêu cầu sư phạm của giảng viên. Không áp dụng khuôn cố định; hãy bám sát câu hỏi, dữ liệu thực tế và mục tiêu bài học.",
    "openended":"Phân tích dữ liệu phản hồi của học viên theo yêu cầu sư phạm của giảng viên. Không áp dụng khuôn cố định; hãy bám sát câu hỏi, dữ liệu thực tế và mục tiêu bài học.",
    "poll":"Phân tích dữ liệu phản hồi của học viên theo yêu cầu sư phạm của giảng viên. Không áp dụng khuôn cố định; hãy bám sát câu hỏi, dữ liệu thực tế và mục tiêu bài học.",
    "scales":"Phân tích dữ liệu phản hồi của học viên theo yêu cầu sư phạm của giảng viên. Không áp dụng khuôn cố định; hãy bám sát câu hỏi, dữ liệu thực tế và mục tiêu bài học.",
    "ranking":"Phân tích dữ liệu phản hồi của học viên theo yêu cầu sư phạm của giảng viên. Không áp dụng khuôn cố định; hãy bám sát câu hỏi, dữ liệu thực tế và mục tiêu bài học.",
    "pin":"Phân tích dữ liệu phản hồi của học viên theo yêu cầu sư phạm của giảng viên. Không áp dụng khuôn cố định; hãy bám sát câu hỏi, dữ liệu thực tế và mục tiêu bài học.",
}
DEFAULT_ZONES = ["Bắc","Trung","Nam","Khu vực đông dân","Khu vực trường học","Khu vực công nghiệp","Khác"]

def activity_config_path(cid: str, act: str) -> str:
    return f"activity_config_{cid}_{act}.json"

def _normalize_list(items, fallback):
    if isinstance(items, str):
        items = [x.strip() for x in items.splitlines() if x.strip()]
    if not isinstance(items, list):
        items = []
    items = [str(x).strip() for x in items if str(x).strip()]
    return items if items else list(fallback)

def default_activity_config(cid: str, act: str) -> dict:
    base = copy.deepcopy(DEFAULT_CLASS_ACT_CONFIG[cid][act])
    base.setdefault("enabled", True)
    base.setdefault("ai_prompt", DEFAULT_AI_PROMPTS.get(act, DEFAULT_AI_PROMPTS["openended"]))
    if act == "pin":
        base.setdefault("zones", [])
    return base

def load_activity_config(cid: str, act: str) -> dict:
    base = default_activity_config(cid, act)
    path = activity_config_path(cid, act)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                base.update(saved)
        except Exception:
            pass
    base["name"] = ACT_LABELS.get(act, base.get("name", act))
    base["enabled"] = bool(base.get("enabled", True))
    base["question"] = str(base.get("question", "")).strip()
    base["ai_prompt"] = str(base.get("ai_prompt", DEFAULT_AI_PROMPTS.get(act, ""))).strip()
    if act == "poll":
        base["options"] = _normalize_list(base.get("options"), [])[:12]
    if act == "scales":
        base["criteria"] = _normalize_list(base.get("criteria"), [])[:12]
    if act == "ranking":
        base["items"] = _normalize_list(base.get("items"), [])[:12]
    if act == "pin":
        base["image"] = str(base.get("image", MAP_IMAGE)).strip() or MAP_IMAGE
        base["zones"] = _normalize_list(base.get("zones"), [])[:20]
    return base

def save_activity_config(cid: str, act: str, cfg: dict):
    with data_lock:
        with open(activity_config_path(cid, act), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

# ============================================================
# 4C) TEACHER-CUSTOMIZABLE AI REQUEST BANK
# ============================================================
def ai_request_bank_path(cid: str, act: str) -> str:
    return f"ai_requests_{cid}_{act}.json"

def _seed_ai_request_bank(default_prompt: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "active_id": "AI1",
        "requests": [{"id": "AI1", "text": str(default_prompt or "").strip(), "created_at": now, "updated_at": now}],
    }

def load_ai_request_bank(cid: str, act: str, default_prompt: str = "") -> dict:
    path = ai_request_bank_path(cid, act)
    if not os.path.exists(path):
        return _seed_ai_request_bank(default_prompt)
    try:
        with open(path, "r", encoding="utf-8") as f:
            bank = json.load(f)
        if not isinstance(bank, dict):
            return _seed_ai_request_bank(default_prompt)
        reqs = bank.get("requests", [])
        if not isinstance(reqs, list) or not reqs:
            return _seed_ai_request_bank(default_prompt)
        clean = []
        for r in reqs:
            if isinstance(r, dict) and str(r.get("text", "")).strip():
                clean.append({
                    "id": str(r.get("id", "")).strip() or "AI1",
                    "text": str(r.get("text", "")).strip(),
                    "created_at": str(r.get("created_at", "")),
                    "updated_at": str(r.get("updated_at", "")),
                })
        if not clean:
            return _seed_ai_request_bank(default_prompt)
        bank["requests"] = clean
        ids = {r.get("id") for r in clean}
        if bank.get("active_id") not in ids:
            bank["active_id"] = clean[0].get("id", "AI1")
        return bank
    except Exception:
        return _seed_ai_request_bank(default_prompt)

def save_ai_request_bank(cid: str, act: str, bank: dict):
    try:
        with data_lock:
            with open(ai_request_bank_path(cid, act), "w", encoding="utf-8") as f:
                json.dump(bank, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def make_new_ai_request_id(bank: dict) -> str:
    nums = []
    for r in bank.get("requests", []):
        m = re.match(r"^AI(\d+)$", str(r.get("id", "")).strip(), flags=re.I)
        if m:
            nums.append(int(m.group(1)))
    return f"AI{(max(nums) + 1) if nums else 2}"

def get_active_ai_request(bank: dict, fallback_text: str = "") -> dict:
    active_id = bank.get("active_id", "AI1")
    for r in bank.get("requests", []):
        if r.get("id") == active_id:
            return r
    return {"id": "AI1", "text": str(fallback_text or "").strip()}

def render_ai_request_bank_manager(cid: str, act: str, bank: dict):
    active = get_active_ai_request(bank, "")
    with st.expander("🧩 Ngân hàng yêu cầu AI", expanded=False):
        st.caption(f"Yêu cầu AI đang kích hoạt: ({active.get('id')}) {active.get('text')[:140]}{'...' if len(active.get('text','')) > 140 else ''}")
        with st.form(f"{act}_add_ai_request", clear_on_submit=True):
            new_req = st.text_area("Thêm yêu cầu AI mới", height=110, key=f"{act}_new_ai_req_text")
            make_active = st.checkbox("Kích hoạt ngay", value=True, key=f"{act}_new_ai_req_active")
            if st.form_submit_button("TẠO YÊU CẦU AI"):
                if not new_req.strip():
                    st.warning("Vui lòng nhập yêu cầu AI.")
                else:
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    rid = make_new_ai_request_id(bank)
                    bank["requests"].append({"id": rid, "text": new_req.strip(), "created_at": now, "updated_at": now})
                    if make_active:
                        bank["active_id"] = rid
                    save_ai_request_bank(cid, act, bank)
                    st.toast("Đã tạo yêu cầu AI.")
                    st.rerun()

        labels = [f"{r['id']} — {r['text'][:120]}{'...' if len(r['text'])>120 else ''}" for r in bank.get("requests", [])]
        if labels:
            idx = max(0, next((i for i, label in enumerate(labels) if label.startswith(str(bank.get('active_id', 'AI1')) + ' —')), 0))
            pick = st.selectbox("Chọn yêu cầu AI để kích hoạt", labels, index=idx, key=f"{act}_ai_req_pick")
            if st.button("KÍCH HOẠT YÊU CẦU AI", key=f"{act}_ai_req_activate"):
                bank["active_id"] = pick.split(" —", 1)[0].strip()
                save_ai_request_bank(cid, act, bank)
                st.toast("Đã kích hoạt yêu cầu AI.")
                st.rerun()
            if st.button("CẬP NHẬT YÊU CẦU ACTIVE TỪ Ô SOẠN", key=f"{act}_ai_req_update_active"):
                edited = st.session_state.get(f"{act}_ai_prompt_runtime", "").strip()
                if not edited:
                    st.warning("Ô soạn yêu cầu AI đang trống.")
                else:
                    for r in bank.get("requests", []):
                        if r.get("id") == bank.get("active_id"):
                            r["text"] = edited
                            r["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    save_ai_request_bank(cid, act, bank)
                    st.toast("Đã cập nhật yêu cầu AI active.")
                    st.rerun()

def describe_activity_setup(cid: str, act: str, qtext: str, cfg: dict | None = None) -> str:
    cfg = cfg or load_activity_config(cid, act)
    lines = []
    if act == "wordcloud":
        bank = load_bank(cid, "wc", qtext or cfg.get("question", ""))
        active = get_active_question(bank, qtext or cfg.get("question", ""))
        lines.append(f"Câu hỏi đang kích hoạt: {active.get('id')} — {active.get('text', '')}")
        lines.append("Ngân hàng câu hỏi:")
        for q in bank.get("questions", []):
            mark = " [ACTIVE]" if q.get("id") == bank.get("active_id") else ""
            lines.append(f"- {q.get('id')}{mark}: {q.get('text', '')}")
    elif act == "openended":
        bank = load_bank(cid, "oe", qtext or cfg.get("question", ""))
        active = get_active_question(bank, qtext or cfg.get("question", ""))
        lines.append(f"Câu hỏi đang kích hoạt: {active.get('id')} — {active.get('text', '')}")
        lines.append("Ngân hàng câu hỏi:")
        for q in bank.get("questions", []):
            mark = " [ACTIVE]" if q.get("id") == bank.get("active_id") else ""
            lines.append(f"- {q.get('id')}{mark}: {q.get('text', '')}")
    else:
        lines.append(f"Câu hỏi/vấn đề: {cfg.get('question', '')}")
        if act == "poll":
            lines.append("Phương án trả lời:")
            lines += [f"- {x}" for x in cfg.get("options", [])]
        elif act == "scales":
            lines.append("Tiêu chí thang đo:")
            lines += [f"- {x}" for x in cfg.get("criteria", [])]
        elif act == "ranking":
            lines.append("Các mục xếp hạng:")
            lines += [f"- {x}" for x in cfg.get("items", [])]
        elif act == "pin":
            lines.append(f"Ảnh/sơ đồ: {cfg.get('image', '')}")
            lines.append("Vùng/điểm lựa chọn:")
            lines += [f"- {x}" for x in cfg.get("zones", [])]
    return "\n".join(lines)

def render_activity_settings(cid: str, act: str, cfg: dict, active_q_text: str | None = None):
    with st.expander("⚙️ Thiết lập hoạt động (chỉ giảng viên)", expanded=False):
        enabled = st.toggle("Kích hoạt hoạt động cho học viên", value=bool(cfg.get("enabled", True)), key=f"set_enabled_{act}")
        question = st.text_area("Câu hỏi / vấn đề đặt ra", value=str(active_q_text or cfg.get("question", "")), height=100, key=f"set_question_{act}")
        new_cfg = copy.deepcopy(cfg)
        new_cfg["enabled"] = enabled
        if act not in ["wordcloud", "openended"]:
            new_cfg["question"] = question.strip()

        if act == "poll":
            opts = st.text_area("Các phương án trả lời — mỗi dòng một phương án", value="\n".join(cfg.get("options", [])), height=150, key="poll_opts_editor")
            new_cfg["options"] = _normalize_list(opts, cfg.get("options", []))[:12]
        elif act == "scales":
            criteria = st.text_area("Các tiêu chí thang đo — mỗi dòng một tiêu chí", value="\n".join(cfg.get("criteria", [])), height=150, key="scales_criteria_editor")
            new_cfg["criteria"] = _normalize_list(criteria, cfg.get("criteria", []))[:12]
        elif act == "ranking":
            items = st.text_area("Các mục xếp hạng — mỗi dòng một mục", value="\n".join(cfg.get("items", [])), height=150, key="ranking_items_editor")
            new_cfg["items"] = _normalize_list(items, cfg.get("items", []))[:12]
        elif act == "pin":
            image = st.text_input("Link ảnh/sơ đồ minh họa", value=cfg.get("image", MAP_IMAGE), key="pin_image_editor")
            zones = st.text_area("Vùng/điểm lựa chọn — mỗi dòng một mục", value="\n".join(cfg.get("zones", [])), height=150, key="pin_zones_editor")
            new_cfg["image"] = image.strip() or MAP_IMAGE
            new_cfg["zones"] = _normalize_list(zones, [])[:20]

        st.caption("Yêu cầu AI không còn cố định tại đây. Giảng viên quản lý nhiều yêu cầu AI trong mục 🤖 AI phân tích và kích hoạt yêu cầu cần dùng.")

        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 Lưu thiết lập", key=f"save_settings_{act}"):
                save_activity_config(cid, act, new_cfg)
                st.toast("Đã lưu thiết lập hoạt động.")
                st.rerun()
        with c2:
            if st.button("🧹 Reset dữ liệu hoạt động hiện tại", key=f"reset_settings_{act}"):
                if act == "wordcloud":
                    bank = load_bank(cid, "wc", cfg.get("question", ""))
                    qid = get_active_question(bank, cfg.get("question", ""))["id"]
                    clear_activity(cid, "wordcloud", suffix=qid)
                elif act == "openended":
                    bank = load_bank(cid, "oe", cfg.get("question", ""))
                    qid = get_active_question(bank, cfg.get("question", ""))["id"]
                    clear_activity(cid, "openended", suffix=qid)
                else:
                    clear_activity(cid, act)
                st.toast("Đã reset dữ liệu hoạt động.")
                st.rerun()
        if act in ["wordcloud", "openended"]:
            st.caption("Với WordCloud/OpenEnded, dùng ngân hàng câu hỏi bên dưới để tạo nhiều câu và chọn câu đang kích hoạt.")

def render_question_bank_manager(cid: str, kind: str, bank: dict, current_qid: str, act: str):
    title = "WordCloud" if kind == "wc" else "OpenEnded"
    with st.expander(f"🧠 Ngân hàng câu hỏi {title}", expanded=False):
        aq = get_active_question(bank, "")
        st.caption(f"Câu đang chọn: ({aq.get('id')}) {aq.get('text') or 'chưa có nội dung'}")
        with st.form(f"{kind}_add_q", clear_on_submit=True):
            new_q = st.text_area("Thêm câu hỏi/vấn đề mới", height=100, key=f"{kind}_new_q_text")
            make_active = st.checkbox("Kích hoạt ngay", value=True, key=f"{kind}_make_active")
            if st.form_submit_button("TẠO"):
                if not new_q.strip():
                    st.warning("Vui lòng nhập nội dung.")
                else:
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    new_id = make_new_qid(bank)
                    bank["questions"].append({"id": new_id, "text": new_q.strip(), "created_at": now, "updated_at": now})
                    if make_active:
                        bank["active_id"] = new_id
                    save_bank(cid, kind, bank)
                    st.toast("Đã tạo câu hỏi.")
                    st.rerun()
        labels = [f"{q['id']} — {q['text'][:100]}{'...' if len(q['text'])>100 else ''}" for q in bank["questions"]]
        idx = max(0, next((i for i, l in enumerate(labels) if l.startswith(current_qid + ' —')), 0))
        pick = st.selectbox("Chọn câu để kích hoạt", labels, index=idx, key=f"{kind}_activate_pick")
        if st.button("KÍCH HOẠT", key=f"{kind}_activate_btn"):
            bank["active_id"] = pick.split(" —", 1)[0].strip()
            save_bank(cid, kind, bank)
            st.toast("Đã kích hoạt.")
            st.rerun()
        if st.button("CẬP NHẬT NỘI DUNG CÂU ACTIVE TỪ Ô THIẾT LẬP", key=f"{kind}_update_active_btn"):
            new_text = st.session_state.get(f"set_question_{act}", "").strip()
            if not new_text:
                st.warning("Ô câu hỏi/vấn đề đang trống.")
            else:
                for q in bank["questions"]:
                    if q.get("id") == current_qid:
                        q["text"] = new_text
                        q["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_bank(cid, kind, bank)
                st.toast("Đã cập nhật câu active.")
                st.rerun()

def render_ai_panel(cid: str, act: str, qtext: str, df: pd.DataFrame, payload_builder):
    cfg = load_activity_config(cid, act)

    stable_id = hashlib.md5(f"{cid}|{act}|{qtext}".encode("utf-8")).hexdigest()[:12]
    result_key = f"ai_result_{stable_id}"
    error_key = f"ai_error_{stable_id}"
    status_key = f"ai_status_{stable_id}"
    last_payload_key = f"ai_last_payload_{stable_id}"
    last_model_key = f"ai_last_model_{stable_id}"

    with st.expander("🤖 AI phân tích câu trả lời học viên (chỉ giảng viên)", expanded=True):
        st.caption("AI chỉ chạy khi giảng viên bấm PHÂN TÍCH NGAY; học viên không gọi API.")

        ai_bank = load_ai_request_bank(cid, act, cfg.get("ai_prompt", DEFAULT_AI_PROMPTS.get(act, "")))
        active_ai_request = get_active_ai_request(ai_bank, DEFAULT_AI_PROMPTS.get(act, ""))
        prompt = st.text_area(
            "Yêu cầu AI đang kích hoạt",
            value=active_ai_request.get("text", ""),
            height=130,
            key=f"{act}_ai_prompt_runtime",
            help="Có thể chỉnh nhanh tại đây. Muốn lưu lại nội dung chỉnh sửa, mở Ngân hàng yêu cầu AI và bấm CẬP NHẬT YÊU CẦU ACTIVE TỪ Ô SOẠN.",
        )
        st.caption(f"Đang dùng yêu cầu AI: {active_ai_request.get('id', 'AI1')}")
        render_ai_request_bank_manager(cid, act, ai_bank)

        extra_lines = []
        if act == "poll" and cfg.get("options"):
            extra_lines.append("Phương án trả lời:\n" + "\n".join([f"- {x}" for x in cfg.get("options", [])]))
        elif act == "scales" and cfg.get("criteria"):
            extra_lines.append("Tiêu chí thang đo:\n" + "\n".join([f"- {x}" for x in cfg.get("criteria", [])]))
        elif act == "ranking" and cfg.get("items"):
            extra_lines.append("Các mục xếp hạng:\n" + "\n".join([f"- {x}" for x in cfg.get("items", [])]))
        elif act == "pin" and cfg.get("zones"):
            extra_lines.append("Vùng/điểm lựa chọn:\n" + "\n".join([f"- {x}" for x in cfg.get("zones", [])]))
        question_context = describe_activity_setup(cid, act, qtext, cfg)
        extra_context_parts = [question_context]
        if extra_lines:
            extra_context_parts.append("\n\n".join(extra_lines))
        export_text = build_external_ai_export(cid, act, qtext, df, prompt, extra_context="\n\n".join(extra_context_parts))
        export_filename = f"phan_tich_{safe_filename_part(class_display_name(cid))}_{safe_filename_part(ACT_LABELS.get(act, act))}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        st.download_button(
            "⬇️ Tải file dữ liệu để đưa vào ChatGPT/AI khác",
            data=export_text.encode("utf-8-sig"),
            file_name=export_filename,
            mime="text/markdown",
            key=f"{act}_download_external_ai_file",
            help="File gồm: dữ liệu câu hỏi/cấu hình hoạt động, dữ liệu trả lời theo lớp học và yêu cầu AI đang kích hoạt.",
        )

        model_name = st.selectbox(
            "Model Gemini",
            ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"],
            index=0,
            key=f"{act}_ai_model_runtime",
            help="Nếu không ra kết quả, thử gemini-2.0-flash hoặc gemini-1.5-flash để kiểm tra model/quota.",
        )

        c1, c2, c3 = st.columns([1, 1, 1])
        with c1:
            run_clicked = st.button("PHÂN TÍCH NGAY", key=f"{act}_ai_run")
        with c2:
            test_clicked = st.button("TEST API", key=f"{act}_ai_test")
        with c3:
            clear_clicked = st.button("XOÁ KẾT QUẢ AI", key=f"{act}_ai_clear")

        if clear_clicked:
            st.session_state[result_key] = ""
            st.session_state[error_key] = ""
            st.session_state[status_key] = "Đã xoá kết quả AI."
            st.session_state[last_payload_key] = ""
            st.session_state[last_model_key] = ""
            st.rerun()

        if test_clicked:
            st.session_state[result_key] = ""
            st.session_state[error_key] = ""
            st.session_state[status_key] = "Đã bấm TEST API. Đang gọi Gemini..."
            test_payload = "Hãy trả lời đúng một dòng duy nhất: OK"
            st.session_state[last_payload_key] = test_payload
            st.session_state[last_model_key] = model_name
            with st.spinner("Đang test Gemini API..."):
                text, err = run_gemini_ai(test_payload, model_name=model_name)
            if err:
                st.session_state[error_key] = err
                st.session_state[status_key] = "TEST API thất bại."
            else:
                st.session_state[result_key] = text
                st.session_state[status_key] = "TEST API thành công."
            st.rerun()

        if run_clicked:
            st.session_state[result_key] = ""
            st.session_state[error_key] = ""
            st.session_state[status_key] = "Đã bấm PHÂN TÍCH NGAY. Đang kiểm tra dữ liệu..."
            if df is None or df.empty:
                st.session_state[error_key] = "Chưa có dữ liệu để AI phân tích. Hãy chờ học viên gửi câu trả lời trước."
                st.session_state[status_key] = "Không gọi AI vì chưa có dữ liệu."
                st.rerun()
            else:
                payload = payload_builder(prompt)
                st.session_state[last_payload_key] = payload[:8000]
                st.session_state[last_model_key] = model_name
                with st.spinner("AI đang phân tích..."):
                    text, err = run_gemini_ai(payload, model_name=model_name)
                if err:
                    st.session_state[error_key] = err
                    st.session_state[status_key] = "Gemini trả về lỗi. Xem ô lỗi bên dưới."
                else:
                    st.session_state[result_key] = text
                    st.session_state[status_key] = "Phân tích AI thành công."
                st.rerun()

        st.markdown("### Kết quả phân tích của AI")
        with st.container(border=True):
            if st.session_state.get(status_key):
                st.info(st.session_state[status_key])
            if st.session_state.get(error_key):
                st.error(st.session_state[error_key])
            elif st.session_state.get(result_key):
                st.markdown(st.session_state[result_key])
            else:
                st.caption("Kết quả AI sẽ hiển thị tại đây sau khi bấm PHÂN TÍCH NGAY hoặc TEST API.")

        with st.expander("🧪 Kiểm tra kỹ thuật", expanded=True):
            client, ai_err = get_ai_client()
            if ai_err:
                st.error(f"Tình trạng API: {ai_err}")
            else:
                st.success("Tình trạng API: đã tìm thấy GEMINI_API_KEY và khởi tạo được client.")
            st.write(f"Model vừa dùng: {st.session_state.get(last_model_key, 'Chưa gọi')}")
            st.write(f"Số dòng dữ liệu hiện có: {0 if df is None else len(df)}")
            st.write(f"Có result_key: {bool(st.session_state.get(result_key))}")
            st.write(f"Có error_key: {bool(st.session_state.get(error_key))}")
            if st.session_state.get(last_payload_key):
                st.text_area("Payload đã gửi gần nhất — rút gọn", st.session_state[last_payload_key], height=220)

# ============================================================
# 5) QUESTION BANK (Wordcloud + OpenEnded) - teacher full, student sees active only
# ============================================================
def _seed_bank(default_q: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {"active_id": "Q1", "questions": [{"id": "Q1", "text": default_q, "created_at": now, "updated_at": now}]}

def bank_path(cid: str, kind: str) -> str:
    return f"{kind}_questions_{cid}.json"  # kind in {"wc","oe"}

def load_bank(cid: str, kind: str, default_q: str) -> dict:
    path = bank_path(cid, kind)
    if not os.path.exists(path):
        return _seed_bank(default_q)
    try:
        with open(path, "r", encoding="utf-8") as f:
            b = json.load(f)
        if "questions" not in b or not isinstance(b["questions"], list) or not b["questions"]:
            return _seed_bank(default_q)
        ids = {q.get("id") for q in b["questions"]}
        if b.get("active_id") not in ids:
            b["active_id"] = b["questions"][0].get("id", "Q1")
        return b
    except Exception:
        return _seed_bank(default_q)

def save_bank(cid: str, kind: str, bank: dict):
    try:
        with data_lock:
            with open(bank_path(cid, kind), "w", encoding="utf-8") as f:
                json.dump(bank, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def make_new_qid(bank: dict) -> str:
    nums = []
    for q in bank.get("questions", []):
        m = re.match(r"^Q(\d+)$", str(q.get("id", "")).strip(), flags=re.I)
        if m:
            nums.append(int(m.group(1)))
    nxt = (max(nums) + 1) if nums else 2
    return f"Q{nxt}"

def get_active_question(bank: dict, fallback_text: str) -> dict:
    aid = bank.get("active_id", "Q1")
    for q in bank.get("questions", []):
        if q.get("id") == aid:
            return q
    return {"id": "Q1", "text": fallback_text}

# ============================================================
# 6) WORDCLOUD (Teacher render preserved with D3)
# ============================================================
def normalize_phrase(s: str) -> str:
    s = str(s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.strip(" .,:;!?\"'`()[]{}<>|\\/+-=*#@~^_")
    return s

def wc_compute_freq(df: pd.DataFrame):
    """Count by unique student for same phrase."""
    if df is None or df.empty:
        return {}, 0, 0, 0
    tmp = df.copy()
    tmp["Học viên"] = tmp["Học viên"].astype(str).str.strip()
    tmp["phrase"] = tmp["Nội dung"].astype(str).apply(normalize_phrase)
    tmp = tmp[(tmp["Học viên"] != "") & (tmp["phrase"] != "")]
    total_answers = int(len(tmp))
    tmp = tmp.drop_duplicates(subset=["Học viên", "phrase"])
    freq = tmp["phrase"].value_counts().to_dict()
    total_people = int(tmp["Học viên"].nunique())
    total_unique = int(len(freq))
    return freq, total_answers, total_people, total_unique

def build_wordcloud_html(words_json: str, height_px: int = 520, fullscreen_button: bool = False) -> str:
    # Preserved: D3 + d3-cloud wordcloud (same idea as your current version)
    fs_button_html = """
  <button id="fs-btn" type="button">⛶ BẬT TOÀN MÀN HÌNH TRÌNH CHIẾU</button>
""" if fullscreen_button else ""
    fs_button_css = """
    #fs-btn {
      position: fixed; right: 18px; bottom: 18px; z-index: 9999;
      border: 0; border-radius: 14px; padding: 14px 18px;
      background: #047857; color: white; font-weight: 900; font-size: 15px;
      box-shadow: 0 10px 30px rgba(0,0,0,.25); cursor: pointer;
    }
    #fs-btn:hover { filter: brightness(1.05); }
""" if fullscreen_button else ""
    fs_button_js = """
    const fsBtn = document.getElementById("fs-btn");
    if (fsBtn) {
      fsBtn.addEventListener("click", async () => {
        const root = document.documentElement;
        try {
          if (!document.fullscreenElement) {
            await root.requestFullscreen();
            fsBtn.textContent = "⛶ THOÁT TOÀN MÀN HÌNH";
          } else {
            await document.exitFullscreen();
            fsBtn.textContent = "⛶ BẬT TOÀN MÀN HÌNH TRÌNH CHIẾU";
          }
          setTimeout(render, 250);
        } catch (e) {
          fsBtn.textContent = "Trình duyệt đang chặn fullscreen - bấm F11/Ctrl+Cmd+F";
        }
      });
      document.addEventListener("fullscreenchange", () => {
        const isFs = !!document.fullscreenElement;
        document.body.classList.toggle("is-fullscreen", isFs);
        fsBtn.textContent = isFs ? "⛶ THOÁT TOÀN MÀN HÌNH" : "⛶ BẬT TOÀN MÀN HÌNH TRÌNH CHIẾU";
        setTimeout(render, 250);
      });
    }
""" if fullscreen_button else ""
    return f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <style>
    body {{ margin:0; background:white; }}
    body.is-fullscreen #wc-wrap {{ height: 100vh !important; border-radius: 0; }}
    {fs_button_css}
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
      user-select: none;
      paint-order: stroke;
      stroke: rgba(255,255,255,0.85);
      stroke-width: 2px;
    }}
  </style>
</head>
<body>
  <div id="wc-wrap"></div>
  {fs_button_html}

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
      return Math.abs(h) % 360;
    }}

    function getSizeScale(vals) {{
      const vmin = Math.max(1, d3.min(vals));
      const vmax = Math.max(1, d3.max(vals));
      if (vmax === vmin) return () => 58;
      return d3.scaleSqrt().domain([vmin, vmax]).range([26, 118]).clamp(true);
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

        const sel = g.selectAll("text.word").data(placed, d => d.__key);
        sel.exit().remove();

        const enter = sel.enter().append("text")
          .attr("class", "word")
          .attr("text-anchor", "middle")
          .style("opacity", 0)
          .text(d => d.text);

        const merged = enter.merge(sel);

        merged
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
      if (w && w > 50) render();
      else if (tries < 25) requestAnimationFrame(boot);
      else render();
    }}
    boot();

    window.addEventListener("resize", () => {{
      clearTimeout(window.__wc_t);
      window.__wc_t = setTimeout(render, 180);
    }});

    {fs_button_js}
  </script>
</body>
</html>
"""

def open_wc_fullscreen_dialog(wc_html: str, live: bool, wc_full_html: str | None = None):
    """Teacher-only fullscreen wordcloud."""
    if _DIALOG_DECORATOR is not None:
        @_DIALOG_DECORATOR("🖥 Fullscreen Wordcloud")
        def _inner():
            if live and st_autorefresh is not None:
                st_autorefresh(interval=1500, key="wc_live_refresh_modal")
            st.components.v1.html(wc_full_html or wc_html, height=880, scrolling=False)
            if st.button("ĐÓNG FULLSCREEN", key="wc_close_full"):
                st.session_state["wc_fullscreen"] = False
                st.rerun()
        _inner()
    else:
        st.warning("Streamlit phiên bản hiện tại chưa hỗ trợ dialog. Đang hiển thị chế độ thay thế.")
        if live and st_autorefresh is not None:
            st_autorefresh(interval=1500, key="wc_live_refresh_modal_fallback")
        st.components.v1.html(wc_full_html or wc_html, height=880, scrolling=False)
        if st.button("ĐÓNG FULLSCREEN", key="wc_close_full_fallback"):
            st.session_state["wc_fullscreen"] = False
            st.rerun()

# ============================================================
# 7) SESSION STATE
# ============================================================
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "role": "", "class_id": "", "page": "login"})
if "device_id" not in st.session_state:
    st.session_state["device_id"] = str(uuid.uuid4())
if "current_act" not in st.session_state:
    st.session_state["current_act"] = "wordcloud"
if "wc_fullscreen" not in st.session_state:
    st.session_state["wc_fullscreen"] = False

# ============================================================
# 8) AUTO RESTORE FROM URL TOKEN
# ============================================================
if not st.session_state.get("logged_in", False):
    tok = qp_get("t", "")
    info = validate_login_token(tok)
    if info:
        st.session_state.update(
            {
                "logged_in": True,
                "role": info.get("role", ""),
                "class_id": info.get("class_id", ""),
                "page": "class_home",
            }
        )

# ============================================================
# 9) LOGIN PAGE
# ============================================================
def render_login():
    st.markdown(
        f"""
<div class="viz-card" style="max-width:620px;margin:30px auto;">
  <div style="text-align:center;">
    <img src="{LOGO_URL}" style="width:120px;height:auto;margin-bottom:10px;">
    <div style="font-weight:900;font-size:24px;color:#111;">TRƯỜNG ĐẠI HỌC CẢNH SÁT NHÂN DÂN</div>
    <div class="small-muted" style="text-transform:uppercase;letter-spacing:1px;">People's Police University</div>
  </div>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0;">
</div>
""",
        unsafe_allow_html=True,
    )

    box = st.container()
    with box:
        col = st.columns([1, 1])[0]
        portal = st.radio("Cổng", ["Học viên", "Giảng viên"], horizontal=True, label_visibility="collapsed")

        if portal == "Học viên":
            c_class = st.selectbox("Lớp học phần", list(CLASSES.keys()))
            c_pass = st.text_input("Mã bảo mật", type="password", placeholder="Nhập mã lớp…")
            if st.button("ĐĂNG NHẬP"):
                cid = CLASSES[c_class]
                if c_pass.strip() == PASSWORDS.get(cid, ""):
                    tok = issue_login_token("student", cid, ttl_hours=12)
                    qp_set(t=tok)
                    st.session_state.update({"logged_in": True, "role": "student", "class_id": cid, "page": "class_home"})
                    st.rerun()
                else:
                    st.error("Mã bảo mật không chính xác.")
        else:
            gv_class = st.selectbox("Lớp quản lý", list(CLASSES.keys()))
            gv_pass = st.text_input("Mật khẩu giảng viên", type="password", placeholder="Nhập mật khẩu…")
            if st.button("TRUY CẬP QUẢN TRỊ"):
                if gv_pass.strip() == "779":
                    cid = CLASSES[gv_class]
                    tok = issue_login_token("teacher", cid, ttl_hours=12)
                    qp_set(t=tok)
                    st.session_state.update({"logged_in": True, "role": "teacher", "class_id": cid, "page": "class_home"})
                    st.rerun()
                else:
                    st.error("Sai mật khẩu.")

    st.markdown(
        """
<div style="text-align:center;margin-top:12px;color:#94a3b8;font-weight:700;">
  Hệ thống tương tác lớp học • Phát triển bởi GV Trần Nguyễn Sĩ Nguyên
</div>
""",
        unsafe_allow_html=True,
    )

# ============================================================
# 10) SIDEBAR (Teacher has more controls; Student minimal)
# ============================================================
def render_sidebar():
    with st.sidebar:
        st.image(LOGO_URL, width=90)
        st.markdown("---")

        cid = st.session_state["class_id"]
        cls_txt = next((k for k, v in CLASSES.items() if v == cid), cid)
        role = st.session_state["role"]
        st.info(f"👤 {'GIẢNG VIÊN' if role=='teacher' else 'HỌC VIÊN'}\n\n🏫 {cls_txt}")

        if role == "teacher":
            st.markdown("### 🔁 Chuyển lớp")
            cls_keys = list(CLASSES.keys())
            curr_label = next((k for k, v in CLASSES.items() if v == cid), cls_keys[0])
            idx = cls_keys.index(curr_label) if curr_label in cls_keys else 0
            pick = st.selectbox("Lớp", cls_keys, index=idx)
            new_cid = CLASSES[pick]
            if new_cid != cid:
                st.session_state["class_id"] = new_cid
                st.rerun()

        st.markdown("---")
        if st.button("📚 Danh mục hoạt động"):
            st.session_state["page"] = "class_home"
            st.rerun()
        if st.session_state["role"] == "teacher":
            if st.button("🏠 Dashboard"):
                st.session_state["page"] = "dashboard"
                st.rerun()

        st.markdown("---")
        if st.button("↩️ Đăng xuất"):
            reset_to_login()

# ============================================================
# 11) CLASS HOME
# ============================================================
def render_class_home():
    cid = st.session_state["class_id"]
    role = st.session_state["role"]
    cls_txt = next((k for k, v in CLASSES.items() if v == cid), cid)

    st.markdown(f"## 📚 Danh mục hoạt động • **{cls_txt}**")

    acts = [("wordcloud", "Word Cloud"), ("poll", "Poll"), ("openended", "Open Ended"), ("scales", "Scales"), ("ranking", "Ranking"), ("pin", "Pin")]
    for key, title in acts:
        acfg = load_activity_config(cid, key)
        box = st.container(border=True)
        with box:
            st.markdown(f"### {title}")
            if str(acfg.get("question", "")).strip():
                st.caption(acfg.get("question", ""))
            elif role == "teacher":
                st.caption("Chưa thiết lập câu hỏi/vấn đề. Bấm MỞ để cấu hình hoạt động.")

            if role == "teacher":
                if key == "wordcloud":
                    bank = load_bank(cid, "wc", acfg.get("question", ""))
                    aq = get_active_question(bank, acfg.get("question", ""))
                    df = load_data_cached(cid, "wordcloud", suffix=aq["id"])
                    st.caption(f"Câu active: **{aq['id']}** • Lượt gửi: **{len(df)}** • Tổng câu: **{len(bank['questions'])}**")
                elif key == "openended":
                    bank = load_bank(cid, "oe", acfg.get("question", ""))
                    aq = get_active_question(bank, acfg.get("question", ""))
                    df = load_data_cached(cid, "openended", suffix=aq["id"])
                    st.caption(f"Câu active: **{aq['id']}** • Lượt gửi: **{len(df)}** • Tổng câu: **{len(bank['questions'])}**")
                else:
                    df = load_data_cached(cid, key)
                    st.caption(f"Lượt gửi: **{len(df)}**")

            if role == "teacher" or acfg.get("enabled", True):
                if st.button("MỞ", key=f"open_{key}"):
                    st.session_state["current_act"] = key
                    st.session_state["page"] = "activity"
                    st.rerun()
            else:
                st.caption("Hoạt động chưa mở cho học viên.")

# ============================================================
# 12) DASHBOARD (Teacher-only)
# ============================================================
def render_dashboard():
    if st.session_state["role"] != "teacher":
        st.warning("Dashboard chỉ dành cho giảng viên.")
        return

    cid = st.session_state["class_id"]

    st.markdown("## 🏠 Dashboard (Giảng viên)")

    live = st.toggle("🔴 Live update (1.5s)", value=True)
    if live and st_autorefresh is not None:
        st_autorefresh(interval=1500, key="dash_live")

    wc_cfg = load_activity_config(cid, "wordcloud")
    bank_wc = load_bank(cid, "wc", wc_cfg.get("question", ""))
    aq_wc = get_active_question(bank_wc, wc_cfg.get("question", ""))
    n_wc = len(load_data_cached(cid, "wordcloud", suffix=aq_wc["id"]))

    oe_cfg = load_activity_config(cid, "openended")
    bank_oe = load_bank(cid, "oe", oe_cfg.get("question", ""))
    aq_oe = get_active_question(bank_oe, oe_cfg.get("question", ""))
    n_oe = len(load_data_cached(cid, "openended", suffix=aq_oe["id"]))

    n_poll = len(load_data_cached(cid, "poll"))
    n_scales = len(load_data_cached(cid, "scales"))
    n_rank = len(load_data_cached(cid, "ranking"))
    n_pin = len(load_data_cached(cid, "pin"))

    cols = st.columns(3)
    cards = [
        ("WORDCLOUD (ACTIVE)", n_wc),
        ("POLL", n_poll),
        ("OPEN ENDED (ACTIVE)", n_oe),
        ("SCALES", n_scales),
        ("RANKING", n_rank),
        ("PIN", n_pin),
    ]
    for i, (label, val) in enumerate(cards):
        with cols[i % 3]:
            st.markdown(
                f"""
<div class="viz-card" style="text-align:center;">
  <div style="font-size:54px;font-weight:900;color:{PRIMARY_COLOR};line-height:1.0;">{val}</div>
  <div class="small-muted" style="text-transform:uppercase;">{label}</div>
</div>
""",
                unsafe_allow_html=True,
            )

# ============================================================
# 13) ACTIVITY PAGES
#     - STUDENT: submit-only, NO refresh, NO results
#     - TEACHER: full view + live (optional)
# ============================================================
def render_activity():
    cid = st.session_state["class_id"]
    role = st.session_state["role"]
    act = st.session_state["current_act"]
    cfg = load_activity_config(cid, act)

    top = st.columns([1, 6])
    with top[0]:
        if st.button("↩️ Về danh mục"):
            st.session_state["page"] = "class_home"
            st.rerun()
    with top[1]:
        st.markdown(f"## {cfg['name']}")

    if role == "teacher":
        render_activity_settings(cid, act, cfg)
    elif not cfg.get("enabled", True):
        st.warning("Hoạt động này hiện chưa được giảng viên mở cho học viên.")
        return

    def _missing_setup(message: str):
        if role == "teacher":
            st.warning(message + " Hãy mở phần thiết lập hoạt động phía trên để cấu hình.")
        else:
            st.warning("Hoạt động này chưa có câu hỏi/vấn đề do giảng viên thiết lập.")

    # -----------------------------
    # WORDCLOUD
    # -----------------------------
    if act == "wordcloud":
        bank = load_bank(cid, "wc", cfg["question"])
        aq = get_active_question(bank, cfg["question"])
        qid = aq["id"]
        qtext = str(aq.get("text", "")).strip()

        if not qtext:
            _missing_setup("WordCloud chưa có câu hỏi/vấn đề.")
            if role == "teacher":
                render_question_bank_manager(cid, "wc", bank, qid, "wordcloud")
            return

        st.info(f"Câu hỏi: **{qtext}**")

        # STUDENT: submit-only
        if role == "student":
            with st.form("wc_student_form", clear_on_submit=True):
                n = st.text_input("Tên")
                txt = st.text_input("Nhập 1 từ khóa / cụm từ")
                ok = st.form_submit_button("GỬI")
                if ok:
                    if n.strip() and txt.strip():
                        save_row(cid, "wordcloud", n, txt, suffix=qid)
                        st.success("✅ Đã gửi! Bạn có thể đóng trang hoặc chờ câu tiếp theo.")
                    else:
                        st.warning("Vui lòng nhập đủ Tên và Từ khóa.")
            st.caption("🔒 Học viên không xem kết quả của lớp (giảm tải & chống nghẽn).")
            return

        # TEACHER: full features
        # live refresh optional (teacher-only)
        live = st.toggle("🔴 Live update (1.5s)", value=True, key="wc_live_teacher")
        if live and st_autorefresh is not None:
            st_autorefresh(interval=1500, key="wc_live_teacher_tick")

        # Load data (cached)
        df = load_data_cached(cid, "wordcloud", suffix=qid)
        freq, total_answers, total_people, total_unique = wc_compute_freq(df)

        # Render wordcloud
        with st.container(border=True):
            if not freq:
                st.info("Chưa có dữ liệu.")
            else:
                items = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:80]
                payload = [{"text": k, "value": int(v)} for k, v in items]
                wc_html = build_wordcloud_html(json.dumps(payload, ensure_ascii=False), height_px=520)
                st.components.v1.html(wc_html, height=540, scrolling=False)

                c1, c2, c3 = st.columns([2, 2, 2])
                with c1:
                    if st.button("🖥 Fullscreen Wordcloud"):
                        st.session_state["wc_fullscreen"] = True
                        st.rerun()
                with c2:
                    show_table = st.toggle("Hiện bảng Top", value=False)
                with c3:
                    if st.button("🧹 Reset dữ liệu (câu active)"):
                        clear_activity(cid, "wordcloud", suffix=qid)
                        st.toast("Đã reset dữ liệu câu active.")
                        st.rerun()

                if st.session_state.get("wc_fullscreen", False):
                    open_wc_fullscreen_dialog(wc_html, live=live, wc_full_html=build_wordcloud_html(json.dumps(payload, ensure_ascii=False), height_px=860, fullscreen_button=True))

                if show_table:
                    topk = pd.DataFrame(items[:25], columns=["Từ/cụm (chuẩn hoá)", "Số người nhập"])
                    st.dataframe(topk, use_container_width=True, hide_index=True)

        st.caption(f"👥 Lượt gửi: **{total_answers}** • 👤 Người tham gia (unique): **{total_people}** • 🧩 Cụm duy nhất: **{total_unique}**")

        render_question_bank_manager(cid, "wc", bank, qid, "wordcloud")

        def _wc_payload(prompt):
            top_items = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:25]
            return f"""
Bạn là trợ giảng cho giảng viên.


CÂU HỎI ({qid}):
{qtext}

TÓM TẮT DỮ LIỆU:
- Số lượt gửi: {len(df)}
- Số người tham gia unique: {df["Học viên"].nunique() if "Học viên" in df.columns else "không rõ"}
- Top cụm từ: {top_items}

YÊU CẦU:
{prompt}

CÁCH TRẢ LỜI:
Bám sát yêu cầu AI đang kích hoạt của giảng viên. Không ép theo khuôn số lượng cố định; chỉ nêu những điểm thật sự có căn cứ từ dữ liệu.
"""
        render_ai_panel(cid, "wordcloud", qtext, df, _wc_payload)

        return
        return
    # -----------------------------
    # POLL
    # -----------------------------
    if act == "poll":
        options = cfg["options"]
        if not str(cfg.get("question", "")).strip() or not options:
            _missing_setup("Poll chưa có đủ câu hỏi và phương án trả lời.")
            return
        st.info(f"Câu hỏi: **{cfg['question']}**")

        if role == "student":
            with st.form("poll_student_form", clear_on_submit=True):
                n = st.text_input("Tên")
                v = st.radio("Chọn 1 đáp án", options)
                ok = st.form_submit_button("BÌNH CHỌN")
                if ok:
                    if not n.strip():
                        st.warning("Vui lòng nhập Tên.")
                    else:
                        save_row(cid, "poll", n, v)
                        st.success("✅ Đã bình chọn! (Học viên không xem kết quả lớp).")
            return

        # Teacher view
        import plotly.graph_objects as go

        live = st.toggle("🔴 Live update (1.5s)", value=True, key="poll_live_teacher")
        if live and st_autorefresh is not None:
            st_autorefresh(interval=1500, key="poll_live_tick")

        df = load_data_cached(cid, "poll")
        with st.container(border=True):
            if df.empty:
                st.info("Chưa có bình chọn.")
            else:
                cnt = df["Nội dung"].value_counts().reindex(options).fillna(0).astype(int)
                fig = go.Figure(data=[go.Bar(x=cnt.index.tolist(), y=cnt.values.tolist(), text=cnt.values.tolist(), textposition="auto")])
                fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig, use_container_width=True)

        c1, c2 = st.columns([2, 2])
        with c1:
            if st.button("🧹 Reset Poll"):
                clear_activity(cid, "poll")
                st.rerun()
        with c2:
            st.caption("GV có thể reset để làm lượt mới.")

        def _poll_payload(prompt):
            return f"""
Bạn là trợ giảng cho giảng viên.


CÂU HỎI:
{cfg.get("question", "")}

PHƯƠNG ÁN:
{options}

DỮ LIỆU BÌNH CHỌN:
{df.to_string(index=False)}

YÊU CẦU:
{prompt}
"""
        render_ai_panel(cid, "poll", cfg.get("question", ""), df, _poll_payload)
        return

    # -----------------------------
    # OPEN ENDED
    # -----------------------------
    if act == "openended":
        bank = load_bank(cid, "oe", cfg["question"])
        aq = get_active_question(bank, cfg["question"])
        qid = aq["id"]
        qtext = str(aq.get("text", "")).strip()

        if not qtext:
            _missing_setup("OpenEnded chưa có câu hỏi/vấn đề.")
            if role == "teacher":
                render_question_bank_manager(cid, "oe", bank, qid, "openended")
            return

        st.info(f"Câu hỏi: **{qtext}**")

        if role == "student":
            with st.form("oe_student_form", clear_on_submit=True):
                n = st.text_input("Tên")
                ans = st.text_area("Câu trả lời", height=160)
                ok = st.form_submit_button("GỬI")
                if ok:
                    if n.strip() and ans.strip():
                        save_row(cid, "openended", n, ans, suffix=qid)
                        st.success("✅ Đã gửi! (Học viên không xem bức tường lớp).")
                    else:
                        st.warning("Vui lòng nhập đủ Tên và nội dung.")
            return

        # Teacher view
        live = st.toggle("🔴 Live update (1.5s)", value=True, key="oe_live_teacher")
        if live and st_autorefresh is not None:
            st_autorefresh(interval=1500, key="oe_live_tick")

        df = load_data_cached(cid, "openended", suffix=qid)
        with st.container(border=True, height=520):
            if df.empty:
                st.info("Chưa có câu trả lời.")
            else:
                for _, r in df.tail(120).iterrows():  # limit render
                    st.markdown(f'<div class="note-card"><b>{r["Học viên"]}</b>: {r["Nội dung"]}</div>', unsafe_allow_html=True)

        c1, c2, c3 = st.columns([2, 2, 2])
        with c1:
            if st.button("🧹 Reset OpenEnded (câu active)"):
                clear_activity(cid, "openended", suffix=qid)
                st.rerun()
        with c2:
            st.caption("Render giới hạn 120 ý kiến để tránh lag.")
        with c3:
            pass

        render_question_bank_manager(cid, "oe", bank, qid, "openended")

        def _oe_payload(prompt):
            sample_df = df.head(80)
            return f"""
Bạn là trợ giảng cho giảng viên.


CÂU HỎI ({qid}):
{qtext}

DỮ LIỆU PHẢN HỒI:
{sample_df.to_string(index=False)}

YÊU CẦU:
{prompt}

CÁCH TRẢ LỜI:
Bám sát yêu cầu AI đang kích hoạt của giảng viên. Không ép theo khuôn số lượng cố định; chỉ nêu những điểm thật sự có căn cứ từ dữ liệu.
"""
        render_ai_panel(cid, "openended", qtext, df, _oe_payload)

        return
        return
    # -----------------------------
    # SCALES
    # -----------------------------
    if act == "scales":
        criteria = cfg["criteria"]
        if not str(cfg.get("question", "")).strip() or not criteria:
            _missing_setup("Scales chưa có đủ câu hỏi và tiêu chí thang đo.")
            return
        st.info(f"**{cfg['question']}**")

        if role == "student":
            with st.form("sc_student", clear_on_submit=True):
                n = st.text_input("Tên")
                scores = []
                for cri in criteria:
                    scores.append(st.slider(cri, 1, 5, 3))
                ok = st.form_submit_button("GỬI")
                if ok:
                    if not n.strip():
                        st.warning("Vui lòng nhập Tên.")
                    else:
                        save_row(cid, "scales", n, ",".join(map(str, scores)))
                        st.success("✅ Đã gửi! (Học viên không xem tổng hợp lớp).")
            return

        # Teacher
        import plotly.graph_objects as go

        live = st.toggle("🔴 Live update (1.5s)", value=True, key="sc_live_teacher")
        if live and st_autorefresh is not None:
            st_autorefresh(interval=1500, key="sc_live_tick")

        df = load_data_cached(cid, "scales")
        with st.container(border=True):
            if df.empty:
                st.info("Chưa có dữ liệu.")
            else:
                mat = []
                for x in df["Nội dung"].astype(str):
                    try:
                        mat.append([int(v) for v in x.split(",")])
                    except Exception:
                        pass
                if not mat:
                    st.warning("Dữ liệu lỗi định dạng.")
                else:
                    avg = np.mean(mat, axis=0)
                    fig = go.Figure(data=go.Scatterpolar(r=avg, theta=criteria, fill="toself"))
                    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5])), showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)

        if st.button("🧹 Reset Scales"):
            clear_activity(cid, "scales")
            st.rerun()

        def _scales_payload(prompt):
            return f"""
Bạn là trợ giảng cho giảng viên.


CÂU HỎI:
{cfg.get("question", "")}

TIÊU CHÍ:
{criteria}

DỮ LIỆU THANG ĐO:
{df.to_string(index=False)}

YÊU CẦU:
{prompt}
"""
        render_ai_panel(cid, "scales", cfg.get("question", ""), df, _scales_payload)
        return

    # -----------------------------
    # RANKING
    # -----------------------------
    if act == "ranking":
        items = cfg["items"]
        if not str(cfg.get("question", "")).strip() or not items:
            _missing_setup("Ranking chưa có đủ câu hỏi và các mục xếp hạng.")
            return
        st.info(f"**{cfg['question']}**")

        if role == "student":
            with st.form("rk_student", clear_on_submit=True):
                n = st.text_input("Tên")
                rank = st.multiselect("Chọn theo thứ tự (đủ tất cả mục)", items)
                ok = st.form_submit_button("NỘP")
                if ok:
                    if not n.strip():
                        st.warning("Vui lòng nhập Tên.")
                    elif len(rank) != len(items):
                        st.warning(f"Vui lòng chọn đủ {len(items)} mục.")
                    else:
                        save_row(cid, "ranking", n, "->".join(rank))
                        st.success("✅ Đã nộp! (Học viên không xem kết quả lớp).")
            return

        # Teacher
        import plotly.express as px

        live = st.toggle("🔴 Live update (1.5s)", value=True, key="rk_live_teacher")
        if live and st_autorefresh is not None:
            st_autorefresh(interval=1500, key="rk_live_tick")

        df = load_data_cached(cid, "ranking")
        with st.container(border=True):
            if df.empty:
                st.info("Chưa có dữ liệu.")
            else:
                scores = {k: 0 for k in items}
                for r in df["Nội dung"].astype(str):
                    parts = r.split("->")
                    for idx, it in enumerate(parts):
                        if it in scores:
                            scores[it] += (len(items) - idx)
                pairs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                lab = [p[0] for p in pairs]
                val = [p[1] for p in pairs]
                fig = px.bar(x=val, y=lab, orientation="h", text=val, labels={"x": "Tổng điểm", "y": "Mục"})
                fig.update_layout(yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig, use_container_width=True)

        if st.button("🧹 Reset Ranking"):
            clear_activity(cid, "ranking")
            st.rerun()

        def _ranking_payload(prompt):
            return f"""
Bạn là trợ giảng cho giảng viên.


CÂU HỎI:
{cfg.get("question", "")}

CÁC MỤC XẾP HẠNG:
{items}

DỮ LIỆU XẾP HẠNG:
{df.to_string(index=False)}

YÊU CẦU:
{prompt}
"""
        render_ai_panel(cid, "ranking", cfg.get("question", ""), df, _ranking_payload)
        return

    # -----------------------------
    # PIN (Lightweight version to avoid heavy image click libs)
    # - Student: choose a "zone" label + optional note (submit-only)
    # - Teacher: aggregates counts + shows list
    # -----------------------------
    if act == "pin":
        zones = cfg.get("zones", [])
        if not str(cfg.get("question", "")).strip() or not zones:
            _missing_setup("Pin chưa có đủ câu hỏi và vùng/điểm lựa chọn.")
            return
        st.info(f"**{cfg['question']}**")
        st.image(cfg.get("image", MAP_IMAGE), caption="Sơ đồ minh họa (tượng trưng)", use_container_width=True)

        if role == "student":
            with st.form("pin_student", clear_on_submit=True):
                n = st.text_input("Tên")
                z = st.selectbox("Chọn vùng/điểm nóng (tượng trưng)", zones)
                note = st.text_input("Ghi chú ngắn (tuỳ chọn)")
                ok = st.form_submit_button("GỬI GHIM")
                if ok:
                    if not n.strip():
                        st.warning("Vui lòng nhập Tên.")
                    else:
                        payload = f"{z}::{note}".strip()
                        save_row(cid, "pin", n, payload)
                        st.success("✅ Đã gửi ghim! (Học viên không xem ghim của lớp).")
            return

        # Teacher
        live = st.toggle("🔴 Live update (1.5s)", value=True, key="pin_live_teacher")
        if live and st_autorefresh is not None:
            st_autorefresh(interval=1500, key="pin_live_tick")

        df = load_data_cached(cid, "pin")
        with st.container(border=True):
            if df.empty:
                st.info("Chưa có ghim.")
            else:
                # Aggregate by zone
                def parse_zone(x: str) -> str:
                    x = str(x or "")
                    return x.split("::", 1)[0].strip() if "::" in x else x.strip()

                df2 = df.copy()
                df2["Zone"] = df2["Nội dung"].apply(parse_zone)
                cnt = df2["Zone"].value_counts().reindex(zones).fillna(0).astype(int)
                st.markdown("### 📌 Thống kê ghim theo vùng")
                st.dataframe(pd.DataFrame({"Vùng": cnt.index, "Số ghim": cnt.values}), hide_index=True, use_container_width=True)

                st.markdown("### 🧾 Danh sách ghim (mới nhất)")
                for _, r in df.tail(80).iterrows():
                    st.markdown(f'<div class="note-card"><b>{r["Học viên"]}</b>: {r["Nội dung"]}</div>', unsafe_allow_html=True)

        if st.button("🧹 Reset Pin"):
            clear_activity(cid, "pin")
            st.rerun()

        def _pin_payload(prompt):
            return f"""
Bạn là trợ giảng cho giảng viên.


CÂU HỎI:
{cfg.get("question", "")}

CÁC VÙNG/ĐIỂM:
{zones}

DỮ LIỆU GHIM:
{df.to_string(index=False)}

YÊU CẦU:
{prompt}
"""
        render_ai_panel(cid, "pin", cfg.get("question", ""), df, _pin_payload)
        return

# ============================================================
# 14) ROUTER
# ============================================================
if not st.session_state.get("logged_in", False):
    render_login()
else:
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
