# app.py
# ============================================================
# T05 Interactive Class (Streamlit)
# - Login token (anti-refresh logout, Mentimeter-like)
# - Class Home + Dashboard
# - Activities: Wordcloud (bank câu hỏi + prompt bank + fullscreen page),
#              Poll (1 device = 1 vote + fullscreen dialog),
#              OpenEnded (bank câu hỏi + fullscreen page + AI),
#              Scales (radar),
#              Ranking (Borda-like),
#              Pin (ghim trên ảnh, lưu tọa độ + overlay)
# ============================================================

import os
import re
import json
import time
import uuid
import random
import threading
from io import BytesIO
from datetime import datetime

import numpy as np
import pandas as pd
import streamlit as st

import plotly.express as px
import plotly.graph_objects as go

# Optional: Gemini
try:
    import google.generativeai as genai
except Exception:
    genai = None

# ✅ Live refresh (thay cho st.autorefresh)
try:
    from streamlit_autorefresh import st_autorefresh
except Exception:
    st_autorefresh = None

# ✅ Helper mở "fullscreen" tương thích nhiều phiên bản Streamlit
_DIALOG_DECORATOR = getattr(st, "dialog", None) or getattr(st, "experimental_dialog", None)


# ============================================================
# 0) PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="T05 Interactive Class",
    page_icon="📶",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================
# 1) GLOBAL STYLES (hide chrome robust)
# ============================================================
st.markdown(
    """
<style>
/* Hide Streamlit chrome */
header, header[data-testid="stHeader"], [data-testid="stHeader"], .stApp > header {
  display: none !important; visibility: hidden !important; height: 0 !important;
}
footer, footer[data-testid="stFooter"], [data-testid="stFooter"] {
  display: none !important; visibility: hidden !important; height: 0 !important;
}
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"],
[data-testid="stAppViewContainer"] > .stAppToolbar, #MainMenu {
  display: none !important;
}
.block-container { padding-top: 0rem !important; }
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# 2) CONSTANTS / ASSETS
# ============================================================
LOGO_URL = "https://drive.google.com/thumbnail?id=1PsUr01oeleJkW2JB1gqnID9WJNsTMFGW&sz=w1000"
MAP_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/Blank_map_of_Vietnam.svg/858px-Blank_map_of_Vietnam.svg.png"

PRIMARY_COLOR = "#006a4e"
BG_COLOR = "#f0f2f5"
TEXT_COLOR = "#111827"
MUTED = "#64748b"

# ============================================================
# 3) QUERY PARAM HELPERS (compat)
# ============================================================
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


# ============================================================
# 4) DATA IO (CSV) + LOCK
# ============================================================
data_lock = threading.Lock()


def get_path(cls: str, act: str, suffix: str = "") -> str:
    suffix = str(suffix or "").strip()
    if suffix:
        return f"data_{cls}_{act}_{suffix}.csv"
    return f"data_{cls}_{act}.csv"


def save_data(cls: str, act: str, name: str, content: str, suffix: str = ""):
    content = str(content).replace("|", "-").replace("\n", " ").strip()
    name = str(name).replace("|", "-").replace("\n", " ").strip()
    timestamp = datetime.now().strftime("%H:%M:%S")
    row = f"{name}|{content}|{timestamp}\n"
    with data_lock:
        with open(get_path(cls, act, suffix=suffix), "a", encoding="utf-8") as f:
            f.write(row)


def load_data(cls: str, act: str, suffix: str = "") -> pd.DataFrame:
    path = get_path(cls, act, suffix=suffix)
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
        for c in ["Học viên", "Nội dung", "Thời gian"]:
            if c not in df.columns:
                df[c] = ""
        return df[["Học viên", "Nội dung", "Thời gian"]]
    except Exception:
        return pd.DataFrame(columns=["Học viên", "Nội dung", "Thời gian"])


def clear_activity(cls: str, act: str, suffix: str = ""):
    with data_lock:
        path = get_path(cls, act, suffix=suffix)
        if os.path.exists(path):
            os.remove(path)


# ============================================================
# 5) LOGIN TOKEN STORE (ANTI-REFRESH LOGOUT)
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


def reset_to_login():
    st.session_state.clear()
    qp_clear()
    st.rerun()


# ============================================================
# 6) POLL: 1 DEVICE = 1 VOTE
# ============================================================
def poll_vote_lock_path(cid: str) -> str:
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


# ============================================================
# 7) CLASSES + PASSWORDS
# ============================================================
CLASSES = {f"Lớp học {i}": f"lop{i}" for i in range(1, 11)}

PASSWORDS = {}
for i in range(1, 9):
    PASSWORDS[f"lop{i}"] = f"T05-{i}"
for i in range(9, 11):
    PASSWORDS[f"lop{i}"] = f"LH{i}"


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


# ============================================================
# 8) ACTIVITY CONFIG PER CLASS
# ============================================================
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
        pin_q = "Ghim 'điểm nóng' nơi dễ phát sinh nguyên cớ (kích động, tin đồn...) trên bản đồ."
    elif cid in ["lop3", "lop4"]:
        wc_q = "1 từ khóa mô tả đúng nhất 'tính kế thừa' trong phủ định biện chứng?"
        poll_q = "Điểm phân biệt cốt lõi giữa 'phủ định biện chứng' và 'phủ định siêu hình' là gì?"
        poll_opts = ["Có tính kế thừa", "Phủ định sạch trơn", "Ngẫu nhiên thuần túy", "Không dựa mâu thuẫn nội tại"]
        poll_correct = "Có tính kế thừa"
        open_q = "Nêu 1 ví dụ trong công tác/đời sống thể hiện phát triển theo 'đường xoáy ốc' (tối thiểu 5 câu)."
        criteria = ["Nêu đúng 2 lần phủ định", "Chỉ ra yếu tố kế thừa", "Chỉ ra yếu tố vượt bỏ", "Kết nối thực tiễn"]
        rank_items = ["Xác định cái cũ cần vượt bỏ", "Giữ lại yếu tố hợp lý", "Tạo cơ chế tự phủ định", "Ổn định cái mới thành cái 'đang là'"]
        pin_q = "Ghim vị trí để minh họa 'điểm bẻ gãy' khi mâu thuẫn chín muồi dẫn tới phủ định."
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
        "poll": {
            "name": "Poll: Chọn đúng bản chất",
            "type": "Bình chọn / Poll",
            "question": poll_q,
            "options": poll_opts,
            "correct": poll_correct,
        },
        "openended": {"name": "Open Ended: Tình huống – lập luận", "type": "Trả lời mở / Open Ended", "question": open_q},
        "scales": {"name": "Scales: Tự đánh giá năng lực", "type": "Thang đo / Scales", "question": "Tự đánh giá theo các tiêu chí (1: thấp – 5: cao).", "criteria": criteria},
        "ranking": {"name": "Ranking: Ưu tiên thao tác", "type": "Xếp hạng / Ranking", "question": "Sắp xếp thứ tự ưu tiên (quan trọng nhất lên đầu).", "items": rank_items},
        "pin": {"name": "Pin: Điểm nóng tình huống", "type": "Ghim trên ảnh / Pin", "question": pin_q, "image": MAP_IMAGE},
    }


# ============================================================
# 9) BANKS: WORDCLOUD QUESTIONS + PROMPTS
# ============================================================
def wc_bank_path(cid: str) -> str:
    return f"wc_questions_{cid}.json"


def _wc_seed_default_questions(cid: str) -> dict:
    default_q = CLASS_ACT_CONFIG[cid]["wordcloud"]["question"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    qid = "Q1"
    return {"active_id": qid, "questions": [{"id": qid, "text": default_q, "created_at": now, "updated_at": now}]}


def load_wc_bank(cid: str) -> dict:
    path = wc_bank_path(cid)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                bank = json.load(f)
            if "questions" not in bank or not isinstance(bank["questions"], list) or not bank["questions"]:
                bank = _wc_seed_default_questions(cid)
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


def wc_get_active_question(cid: str, bank: dict) -> dict:
    aid = bank.get("active_id")
    for q in bank.get("questions", []):
        if q.get("id") == aid:
            return q
    qs = bank.get("questions", [])
    return qs[0] if qs else {"id": "Q1", "text": CLASS_ACT_CONFIG[cid]["wordcloud"]["question"]}


def wc_make_new_id(bank: dict) -> str:
    nums = []
    for q in bank.get("questions", []):
        m = re.match(r"^Q(\d+)$", str(q.get("id", "")).strip(), flags=re.I)
        if m:
            nums.append(int(m.group(1)))
    nxt = (max(nums) + 1) if nums else 2
    return f"Q{nxt}"


def wc_count_answers(cid: str, qid: str) -> int:
    df = load_data(cid, "wordcloud", suffix=qid)
    return int(len(df)) if df is not None else 0


# prompt bank per qid
def wc_prompt_bank_path(cid: str) -> str:
    return f"wc_prompts_{cid}.json"


def load_wc_prompts(cid: str) -> dict:
    path = wc_prompt_bank_path(cid)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


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
        dedup = []
        for p in bank[qid]:
            if p not in dedup:
                dedup.append(p)
        bank[qid] = dedup
        save_wc_prompts(cid, bank)


# ============================================================
# 10) BANKS: OPEN ENDED QUESTIONS
# ============================================================
def oe_bank_path(cid: str) -> str:
    return f"oe_questions_{cid}.json"


def _oe_seed_default_questions(cid: str) -> dict:
    default_q = CLASS_ACT_CONFIG[cid]["openended"]["question"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    qid = "Q1"
    return {"active_id": qid, "questions": [{"id": qid, "text": default_q, "created_at": now, "updated_at": now}]}


def load_oe_bank(cid: str) -> dict:
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


def oe_get_active_question(cid: str, bank: dict) -> dict:
    aid = bank.get("active_id")
    for q in bank.get("questions", []):
        if q.get("id") == aid:
            return q
    qs = bank.get("questions", [])
    return qs[0] if qs else {"id": "Q1", "text": CLASS_ACT_CONFIG[cid]["openended"]["question"]}


def oe_make_new_id(bank: dict) -> str:
    nums = []
    for q in bank.get("questions", []):
        m = re.match(r"^Q(\d+)$", str(q.get("id", "")).strip(), flags=re.I)
        if m:
            nums.append(int(m.group(1)))
    nxt = (max(nums) + 1) if nums else 2
    return f"Q{nxt}"


def oe_count_answers(cid: str, qid: str) -> int:
    df = load_data(cid, "openended", suffix=qid)
    return int(len(df)) if df is not None else 0


# ============================================================
# 11) GEMINI SETUP
# ============================================================
model = None
if genai is not None:
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", None)
        if api_key:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.5-flash")
    except Exception:
        model = None


# ============================================================
# 12) SESSION STATE INIT
# ============================================================
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "role": "", "class_id": ""})

if "device_id" not in st.session_state:
    st.session_state["device_id"] = str(uuid.uuid4())

if "page" not in st.session_state:
    st.session_state["page"] = "login"  # login | class_home | activity | dashboard

if "current_act_key" not in st.session_state:
    st.session_state["current_act_key"] = "dashboard"


# ============================================================
# 13) AUTO RESTORE SESSION FROM URL TOKEN
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

if (not st.session_state.get("logged_in", False)) or (st.session_state.get("page", "login") == "login"):
    st.session_state["page"] = "login"


# ============================================================
# 14) UI STYLE PACK (MAIN APP - NOT LOGIN)
# ============================================================
def inject_main_styles():
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {{
  font-family: 'Montserrat', sans-serif;
  background-color: {BG_COLOR};
  color: {TEXT_COLOR};
}}

.block-container {{
  max-width: 100% !important;
  padding: 0.6rem 1.0rem !important;
}}

label, .stMarkdown, .stText, .stCaption, p, span, div {{
  font-size: 20px;
}}

div.stButton > button {{
  background-color: {PRIMARY_COLOR};
  color: white;
  border: none;
  border-radius: 14px;
  padding: 14px 14px !important;
  font-weight: 800 !important;
  width: 100%;
}}

div.stButton > button:hover {{
  background-color: #00503a;
}}

.viz-card {{
  background: white;
  padding: 18px;
  border-radius: 18px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.05);
  border: 1px solid #e2e8f0;
}}

.note-card {{
  background: #fff;
  padding: 14px;
  border-radius: 14px;
  border-left: 6px solid {PRIMARY_COLOR};
  margin-bottom: 10px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  font-size: 20px;
  line-height: 1.25;
}}

.list-wrap {{ max-width: 100% !important; }}
.act-row {{
  background: white;
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  padding: 16px;
  box-shadow: 0 10px 30px rgba(0,0,0,0.06);
  margin-bottom: 12px;
}}
.act-name {{ font-weight: 900; font-size: 22px; margin: 0 0 6px 0; }}
.act-meta {{ margin: 0; color: {MUTED}; font-weight: 700; }}

@media (max-width: 600px) {{
  label, .stMarkdown, .stText, .stCaption, p, span, div {{ font-size: 16px !important; }}
  .note-card {{ font-size: 16px !important; }}
}}
</style>
""",
        unsafe_allow_html=True,
    )


# ============================================================
# 15) LOGIN PAGE
# ============================================================
def render_login():
    st.markdown(
        f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Inter:wght@400;600;700&display=swap');

html, body, .stApp {{
  background-color: #f2f4f8;
  overflow-x: hidden !important;
}}
.block-container {{
  padding-top: 5vh !important;
  max-width: 1100px !important;
  padding-left: 16px !important;
  padding-right: 16px !important;
}}

.login-shell {{
  width: 100%;
  display: flex;
  justify-content: center;
}}
.login-card {{
  width: 100%;
  max-width: 560px;
  background: #ffffff;
  padding: 46px 38px;
  border-radius: 0px;
  box-shadow: 0 15px 35px rgba(0,0,0,0.08);
  border-top: 6px solid #b71c1c;
  box-sizing: border-box;
}}

.brand-container {{ text-align:center; margin-bottom: 26px; }}
.brand-logo {{ width: 120px; height:auto; margin-bottom: 14px; }}
.uni-vn {{
  font-family: 'Playfair Display', serif;
  color: #111111;
  font-size: 24px;
  font-weight: 900;
  text-transform: uppercase;
  line-height: 1.25;
  margin: 0 0 6px 0;
  word-break: break-word;
  overflow-wrap: anywhere;
}}
.uni-en {{
  font-family: 'Inter', sans-serif;
  color: #555555;
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin: 0;
}}

div[role="radiogroup"] {{
  display:flex;
  gap:10px;
  justify-content:center;
  margin-bottom: 14px;
}}
div[role="radiogroup"] label {{
  border: 1px solid #e2e8f0 !important;
  padding: 10px 14px !important;
  border-radius: 999px !important;
  background: #fff !important;
  font-family: 'Inter', sans-serif !important;
  font-weight: 800 !important;
  color: #64748b !important;
}}
div[role="radiogroup"] label:has(input:checked) {{
  border-color: #b71c1c !important;
  color: #b71c1c !important;
  background: rgba(183,28,28,0.06) !important;
}}

.stTextInput label, .stSelectbox label {{
  font-family: 'Inter', sans-serif;
  font-size: 13px;
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
  margin-top: 14px;
  transition: 0.3s;
}}
div.stButton > button:hover {{ background-color: #8a0c1a; }}

.login-footer {{
  margin-top: 28px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
  text-align: center;
  color: #94a3b8;
  font-family: 'Inter', sans-serif;
}}
.login-footer .f1 {{ font-size: 12px; font-weight: 800; color:#64748b; }}
.login-footer .f2 {{ font-size: 12px; font-weight: 700; color:#94a3b8; }}

@media (max-width: 600px) {{
  .block-container {{ padding-top: 18px !important; padding-left: 10px !important; padding-right: 10px !important; max-width: 100% !important; }}
  .login-card {{ max-width: 100%; padding: 24px 16px; }}
  .brand-logo {{ width: 108px; }}
  .uni-vn {{ font-size: 19px; }}
  .uni-en {{ font-size: 12px; }}
}}
</style>
""",
        unsafe_allow_html=True,
    )

    st.markdown("<div class='login-shell'><div class='login-card'>", unsafe_allow_html=True)

    st.markdown(
        f"""
<div class="brand-container">
  <img src="{LOGO_URL}" class="brand-logo">
  <div class="uni-vn">TRƯỜNG ĐẠI HỌC CẢNH SÁT NHÂN DÂN</div>
  <div class="uni-en">People's Police University</div>
</div>
""",
        unsafe_allow_html=True,
    )

    portal = st.radio("Chọn cổng đăng nhập", ["Học viên", "Giảng viên"], horizontal=True, label_visibility="collapsed", key="portal_mode")

    st.write("")

    if portal == "Học viên":
        c_class = st.selectbox("Lớp học phần", list(CLASSES.keys()), key="mck_s_class")
        c_pass = st.text_input("Mã bảo mật", type="password", placeholder="Nhập mã lớp...", key="mck_s_pass")

        if st.button("ĐĂNG NHẬP", key="mck_btn_s"):
            cid = CLASSES[c_class]
            if c_pass.strip() == PASSWORDS.get(cid, ""):
                tok = issue_login_token("student", cid, ttl_hours=12)
                qp_set(t=tok)  # giữ token qua refresh
                st.session_state.update({"logged_in": True, "role": "student", "class_id": cid, "page": "class_home"})
                st.rerun()
            else:
                st.error("Mã bảo mật không chính xác.")
    else:
        gv_class = st.selectbox("Lớp quản lý", list(CLASSES.keys()), key="mck_g_class")
        t_pass = st.text_input("Mật khẩu Giảng viên", type="password", placeholder="Nhập mật khẩu...", key="mck_g_pass")

        if st.button("TRUY CẬP QUẢN TRỊ", key="mck_btn_g"):
            if not t_pass.strip():
                st.error("Vui lòng nhập mật khẩu giảng viên.")
            elif t_pass.strip() == "779":
                cid = CLASSES[gv_class]
                tok = issue_login_token("teacher", cid, ttl_hours=12)
                qp_set(t=tok)
                st.session_state.update({"logged_in": True, "role": "teacher", "class_id": cid, "page": "class_home"})
                st.rerun()
            else:
                st.error("Sai mật khẩu.")

    st.markdown(
        """
<div class="login-footer">
  <div class="f1">Hệ thống tương tác lớp học</div>
  <div class="f2">Phát triển bởi Giảng viên <b>Trần Nguyễn Sĩ Nguyên</b></div>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("</div></div>", unsafe_allow_html=True)

    st.stop()


# ============================================================
# 16) SIDEBAR NAV
# ============================================================
def render_sidebar():
    with st.sidebar:
        st.image(LOGO_URL, width=86)
        st.markdown("---")

        cls_txt = next((k for k, v in CLASSES.items() if v == st.session_state.get("class_id", "")), "Lớp?")
        role = "HỌC VIÊN" if st.session_state.get("role") == "student" else "GIẢNG VIÊN"
        st.info(f"👤 {role}\n\n🏫 {cls_txt}")

        if st.session_state.get("role") == "teacher":
            st.warning("CHUYỂN LỚP QUẢN LÝ")
            curr_cid = st.session_state.get("class_id", "lop1")
            cls_keys = list(CLASSES.keys())
            curr_label = next((k for k, v in CLASSES.items() if v == curr_cid), cls_keys[0])
            curr_index = cls_keys.index(curr_label) if curr_label in cls_keys else 0
            s_cls = st.selectbox("Chọn lớp", cls_keys, index=curr_index, key="teacher_class_switch")

            new_cid = CLASSES[s_cls]
            if new_cid != st.session_state.get("class_id"):
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
            reset_to_login()


# ============================================================
# 17) CLASS HOME
# ============================================================
def render_class_home():
    cid = st.session_state["class_id"]
    cfg = CLASS_ACT_CONFIG[cid]
    topic = cfg["topic"]
    cls_txt = next((k for k, v in CLASSES.items() if v == cid), cid)

    bank = load_wc_bank(cid)
    aq = wc_get_active_question(cid, bank)
    active_wc_count = wc_count_answers(cid, aq.get("id", "Q1"))
    total_wc_questions = len(bank.get("questions", []))

    st.markdown("<div class='list-wrap'>", unsafe_allow_html=True)
    st.markdown(
        f"""
<h2 style="color:{PRIMARY_COLOR}; font-weight:900; margin: 0 0 6px 0;">📚 Danh mục hoạt động của lớp</h2>
<p style="color:{MUTED}; font-weight:800; margin:0 0 12px 0;"><b>{cls_txt}</b> • Chủ đề: {topic}</p>
""",
        unsafe_allow_html=True,
    )

    c_back, c_space = st.columns([1, 5])
    with c_back:
        if st.button("↩️ Đăng xuất", key="btn_logout_top"):
            reset_to_login()
    with c_space:
        st.caption("Chọn một hoạt động để vào làm bài / xem kết quả (GV có thêm AI & reset theo từng hoạt động).")

    def open_activity(act_key: str):
        st.session_state["current_act_key"] = act_key
        st.session_state["page"] = "activity"
        st.rerun()

    act_order = ["wordcloud", "poll", "openended", "scales", "ranking", "pin"]

    for act_key in act_order:
        a = cfg[act_key]
        if act_key == "wordcloud":
            count = active_wc_count
            meta_extra = f" • Câu active: <b>{aq.get('id')}</b> • Tổng câu: <b>{total_wc_questions}</b>"
        elif act_key == "openended":
            oe_bank = load_oe_bank(cid)
            oe_aq = oe_get_active_question(cid, oe_bank)
            count = oe_count_answers(cid, oe_aq.get("id", "Q1"))
            meta_extra = f" • Câu active: <b>{oe_aq.get('id')}</b> • Tổng câu: <b>{len(oe_bank.get('questions', []))}</b>"
        else:
            df = load_data(cid, act_key)
            count = len(df)
            meta_extra = ""

        colL, colR = st.columns([6, 1])
        with colL:
            st.markdown(
                f"""
<div class="act-row">
  <p class="act-name">{a["name"]}</p>
  <p class="act-meta">Loại: {a["type"]} • Lượt trả lời: <b>{count}</b>{meta_extra}</p>
</div>
""",
                unsafe_allow_html=True,
            )
        with colR:
            if st.button("MỞ", key=f"open_{cid}_{act_key}"):
                open_activity(act_key)

    st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# 18) DASHBOARD
# ============================================================
def render_dashboard():
    cid = st.session_state["class_id"]
    topic = CLASS_ACT_CONFIG[cid]["topic"]

    st.markdown(
        f"<h2 style='color:{PRIMARY_COLOR}; border-bottom:2px solid #e2e8f0; padding-bottom:10px; font-weight:900;'>🏠 Dashboard</h2>",
        unsafe_allow_html=True,
    )
    st.caption(f"Chủ đề lớp: {topic}")

    wc_bank = load_wc_bank(cid)
    wc_aq = wc_get_active_question(cid, wc_bank)
    wc_active_count = wc_count_answers(cid, wc_aq.get("id", "Q1"))

    oe_bank = load_oe_bank(cid)
    oe_aq = oe_get_active_question(cid, oe_bank)
    oe_active_count = oe_count_answers(cid, oe_aq.get("id", "Q1"))

    activities = ["wordcloud", "poll", "openended", "scales", "ranking", "pin"]
    names = ["WORD CLOUD (ACTIVE)", "POLL", "OPEN ENDED (ACTIVE)", "SCALES", "RANKING", "PIN IMAGE"]

    cols = st.columns(3)
    for i, act in enumerate(activities):
        if act == "wordcloud":
            n = wc_active_count
        elif act == "openended":
            n = oe_active_count
        else:
            df = load_data(cid, act)
            n = len(df)

        with cols[i % 3]:
            st.markdown(
                f"""
<div class="viz-card" style="text-align:center;">
  <div style="color:{PRIMARY_COLOR}; margin:0; font-size:56px; font-weight:900;">{n}</div>
  <div style="color:{MUTED}; font-weight:900; text-transform:uppercase;">{names[i]}</div>
</div>
""",
                unsafe_allow_html=True,
            )

    st.caption("Gợi ý: dùng sidebar → “Danh mục hoạt động” để mở hoạt động như Mentimeter.")


# ============================================================
# 19) FULLSCREEN HELPERS
# ============================================================
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


# ============================================================
# 20) WORDCLOUD UTIL
# ============================================================
def normalize_phrase(s: str) -> str:
    s = str(s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    s = s.strip(" .,:;!?\"'`()[]{}<>|\\/+-=*#@~^_")
    return s


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


def build_wordcloud_html(words_json: str, height_px: int = 520) -> str:
    # D3 cloud
    return f"""
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
</script>
</body>
</html>
"""


# ============================================================
# 21) PIN UTIL (overlay on image using Plotly layout.image)
# ============================================================
def pin_parse_points(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expect Nội dung: "x,y" in [0..100] percents.
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=["Học viên", "x", "y", "Thời gian"])
    rows = []
    for _, r in df.iterrows():
        name = str(r.get("Học viên", "")).strip()
        cont = str(r.get("Nội dung", "")).strip()
        t = str(r.get("Thời gian", "")).strip()
        m = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*,\s*([0-9]+(?:\.[0-9]+)?)\s*$", cont)
        if not m:
            continue
        x = float(m.group(1))
        y = float(m.group(2))
        x = max(0.0, min(100.0, x))
        y = max(0.0, min(100.0, y))
        rows.append({"Học viên": name, "x": x, "y": y, "Thời gian": t})
    return pd.DataFrame(rows)


def pin_make_figure(image_url: str, pts: pd.DataFrame) -> go.Figure:
    # Coordinate system: x/y in 0..100
    fig = go.Figure()

    fig.update_xaxes(range=[0, 100], visible=False)
    fig.update_yaxes(range=[0, 100], visible=False, scaleanchor="x")

    fig.add_layout_image(
        dict(
            source=image_url,
            xref="x",
            yref="y",
            x=0,
            y=100,
            sizex=100,
            sizey=100,
            sizing="stretch",
            opacity=1.0,
            layer="below",
        )
    )

    if pts is not None and not pts.empty:
        fig.add_trace(
            go.Scatter(
                x=pts["x"],
                y=100 - pts["y"],  # invert y to match "top = 0" mental model
                mode="markers+text",
                text=pts["Học viên"],
                textposition="top center",
                marker=dict(size=12, opacity=0.85),
                hovertemplate="<b>%{text}</b><br>x=%{x:.1f}, y=%{y:.1f}<extra></extra>",
            )
        )

    fig.update_layout(
        margin=dict(l=8, r=8, t=8, b=8),
        height=560,
        showlegend=False,
    )
    return fig


# ============================================================
# 22) ACTIVITY PAGE
# ============================================================
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
            f"<h2 style='color:{PRIMARY_COLOR}; border-bottom:2px solid #e2e8f0; padding-bottom:10px; font-weight:900;'>{cfg['name']}</h2>",
            unsafe_allow_html=True,
        )

    # =========================
    # WORDCLOUD
    # =========================
    if act == "wordcloud":
        bank = load_wc_bank(cid)
        active_q = wc_get_active_question(cid, bank)
        active_qid = active_q.get("id", "Q1")
        active_qtext = active_q.get("text", cfg["question"])

        # fullscreen page via query params: wcfs=1&wcq=Qn
        is_fs = (qp_get("wcfs", "0") == "1")
        fs_qid = qp_get("wcq", active_qid) or active_qid

        if is_fs:
            st.markdown(
                """
<style>
[data-testid="stSidebar"] {display:none !important;}
.block-container {max-width: 100% !important; padding: 0.4rem 0.8rem !important;}
</style>
""",
                unsafe_allow_html=True,
            )

            b1, b2, b3 = st.columns([2, 6, 2])
            with b1:
                if st.button("⬅️ Thoát Fullscreen", key="wc_exit_fs"):
                    qp_clear()
                    st.rerun()
            with b2:
                # Show correct question text for fs_qid
                q_obj_fs = next((q for q in bank.get("questions", []) if q.get("id") == fs_qid), None)
                q_text_fs = (q_obj_fs.get("text") if q_obj_fs else active_qtext) or active_qtext
                st.markdown(f"### ☁️ Wordcloud — Câu ({fs_qid})")
                st.markdown(f"**Câu hỏi:** {q_text_fs}")
            with b3:
                live_fs = st.toggle("🔴 Live (1.5s)", value=True, key="wc_live_fs")
                if live_fs and st_autorefresh is not None:
                    st_autorefresh(interval=1500, key="wc_live_refresh_fs")

            freq, total_answers, total_people, total_unique = wc_compute_freq_for_qid(cid, fs_qid)
            if not freq:
                st.info("Chưa có dữ liệu. Mời lớp nhập từ khóa.")
            else:
                items = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:120]
                words_payload = [{"text": k, "value": int(v)} for k, v in items]
                wc_html = build_wordcloud_html(json.dumps(words_payload, ensure_ascii=False), height_px=820)
                st.components.v1.html(wc_html, height=845, scrolling=False)

            st.caption(f"🧾 Câu: **{fs_qid}** • 👥 Lượt gửi: **{total_answers}** • 👤 Người tham gia: **{total_people}** • 🧩 Cụm duy nhất: **{total_unique}**")

            # AI (GV)
            if st.session_state["role"] == "teacher":
                st.markdown("---")
                st.markdown("### 🤖 AI phân tích Wordcloud (câu đang xem)")
                df_wc = load_data(cid, "wordcloud", suffix=fs_qid)

                prompts = wc_get_prompts_for_qid(cid, fs_qid)
                if not prompts:
                    prompts = [
                        "Rút ra 5 từ khóa nổi bật và giải thích ý nghĩa của chúng trong bối cảnh bài học.",
                        "Phân nhóm các cụm từ theo 3–5 chủ đề, kèm ví dụ minh họa.",
                        "Chỉ ra 3 hiểu lầm có thể có + 3 can thiệp sư phạm ngay tại lớp.",
                    ]

                for i, p in enumerate(prompts[:10]):
                    if st.button(f"▶ {p[:120]}{'...' if len(p)>120 else ''}", key=f"wc_fs_quick_{fs_qid}_{i}"):
                        st.session_state["wc_fs_prompt"] = p

                default_prompt = st.session_state.get("wc_fs_prompt", "Tóm tắt 3 xu hướng chính, 3 điểm thiếu/nhầm và 3 câu hỏi gợi mở.")
                user_prompt = st.text_area("Prompt", value=default_prompt, height=120, key=f"wc_fs_prompt_area_{fs_qid}")

                cA, cB = st.columns([2, 2])
                with cA:
                    run_ai = st.button("PHÂN TÍCH NGAY", key=f"wc_fs_ai_run_{fs_qid}")
                with cB:
                    if st.button("LƯU PROMPT (câu này)", key=f"wc_fs_prompt_save_{fs_qid}"):
                        wc_add_prompt(cid, fs_qid, user_prompt)
                        st.toast("Đã lưu prompt.")
                        time.sleep(0.15)
                        st.rerun()

                with st.expander("⚙️ Quản lý prompt gợi ý (thêm/sửa/xóa)", expanded=False):
                    existing = wc_get_prompts_for_qid(cid, fs_qid)
                    if not existing:
                        st.info("Chưa có prompt lưu riêng.")
                    else:
                        pick = st.selectbox("Chọn prompt", existing, key=f"wc_fs_prompt_pick_{fs_qid}")
                        new_text = st.text_area("Sửa prompt", value=pick, height=120, key=f"wc_fs_prompt_edit_{fs_qid}")

                        x1, x2 = st.columns(2)
                        with x1:
                            if st.button("LƯU SỬA", key=f"wc_fs_prompt_update_{fs_qid}"):
                                wc_update_prompt(cid, fs_qid, pick, new_text)
                                st.toast("Đã cập nhật.")
                                time.sleep(0.15)
                                st.rerun()
                        with x2:
                            if st.button("XÓA", key=f"wc_fs_prompt_delete_{fs_qid}"):
                                wc_delete_prompt(cid, fs_qid, pick)
                                st.toast("Đã xóa.")
                                time.sleep(0.15)
                                st.rerun()

                if run_ai:
                    if model is None:
                        st.warning("Chưa cấu hình GEMINI_API_KEY trong st.secrets.")
                    elif df_wc is None or df_wc.empty:
                        st.warning("Chưa có dữ liệu để phân tích.")
                    else:
                        freq_fs, *_ = wc_compute_freq_for_qid(cid, fs_qid)
                        top_items = sorted(freq_fs.items(), key=lambda x: x[1], reverse=True)[:25]
                        q_obj_fs = next((q for q in bank.get("questions", []) if q.get("id") == fs_qid), None)
                        q_text_fs = (q_obj_fs.get("text") if q_obj_fs else active_qtext) or active_qtext

                        with st.spinner("AI đang phân tích..."):
                            payload = f"""
Bạn là trợ giảng cho giảng viên. Đây là dữ liệu WORDCLOUD của lớp.

CHỦ ĐỀ LỚP:
{CLASS_ACT_CONFIG[cid]['topic']}

CÂU HỎI ({fs_qid}):
{q_text_fs}

TOP 25 CỤM (chuẩn hoá):
{top_items}

DỮ LIỆU THÔ (bảng):
{df_wc.to_string(index=False)}

YÊU CẦU:
{user_prompt}

Trả lời theo cấu trúc:
1) 3–5 phát hiện chính
2) Phân nhóm chủ đề (kèm ví dụ)
3) 2–3 hiểu lầm có thể có + cách chỉnh ngay
4) 3 can thiệp sư phạm
5) 3 câu hỏi gợi mở
"""
                            res = model.generate_content(payload)
                            st.info(res.text)

            return  # stop normal render

        # normal view
        c1, c2 = st.columns([1, 2])

        with c1:
            st.info(f"Câu hỏi đang kích hoạt ({active_qid}): **{active_qtext}**")
            if st.session_state["role"] == "student":
                with st.form("f_wc"):
                    n = st.text_input("Tên", key="wc_name")
                    txt = st.text_input("Nhập 1 từ khóa / cụm từ", key="wc_txt")
                    if st.form_submit_button("GỬI"):
                        if n.strip() and txt.strip():
                            save_data(cid, "wordcloud", n, txt, suffix=active_qid)
                            st.success("Đã gửi!")
                            time.sleep(0.15)
                            st.rerun()
                        else:
                            st.warning("Vui lòng nhập đủ Tên và Từ khóa.")
            else:
                st.warning("Giảng viên xem kết quả bên phải + quản trị câu hỏi bên dưới.")

        with c2:
            t1, t2, t3 = st.columns([2, 2, 2])
            with t1:
                is_mobile = (qp_get("m", "0") == "1")
                live = st.toggle("🔴 Live update (1.5s)", value=(False if is_mobile else True), key="wc_live_toggle")
            with t2:
                if st.button("🖥 Fullscreen Wordcloud", key="wc_btn_full"):
                    qp_set(wcfs="1", wcq=active_qid)
                    st.rerun()
            with t3:
                show_table = st.toggle("Hiện bảng Top từ", value=False, key="wc_show_table")

            if live and st_autorefresh is not None:
                st_autorefresh(interval=1500, key="wc_live_refresh")

            st.markdown("##### ☁️ KẾT QUẢ (CÂU ĐANG KÍCH HOẠT)")
            freq, total_answers, total_people, total_unique = wc_compute_freq_for_qid(cid, active_qid)

            with st.container(border=True):
                if not freq:
                    st.info("Chưa có dữ liệu. Mời lớp nhập từ khóa.")
                    items = []
                else:
                    items = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:60]
                    words_payload = [{"text": k, "value": int(v)} for k, v in items]
                    wc_html = build_wordcloud_html(json.dumps(words_payload, ensure_ascii=False), height_px=520)
                    st.components.v1.html(wc_html, height=540, scrolling=False)

            st.caption(f"🧾 Câu: **{active_qid}** • 👥 Lượt gửi: **{total_answers}** • 👤 Người tham gia: **{total_people}** • 🧩 Cụm duy nhất: **{total_unique}**")

            if show_table and freq:
                topk = pd.DataFrame(items[:20], columns=["Từ/cụm (chuẩn hoá)", "Số người nhập"])
                st.dataframe(topk, use_container_width=True, hide_index=True)

        # Teacher admin for WC
        if st.session_state["role"] == "teacher":
            st.markdown("---")
            with st.expander("🧠 WORD CLOUD • QUẢN TRỊ CÂU HỎI (Không giới hạn) + Lịch sử + Xem nhanh", expanded=True):
                left_admin, right_admin = st.columns([2, 3])

                with left_admin:
                    st.success(f"✅ Active: ({active_qid}) {active_qtext}")

                    st.markdown("###### ➕ Thêm câu hỏi mới")
                    with st.form("wc_add_q_form"):
                        new_text = st.text_area("Nội dung câu hỏi mới", height=110, key="wc_new_q_text")
                        make_active = st.checkbox("Kích hoạt ngay sau khi tạo", value=True, key="wc_make_active")
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

                    st.markdown("###### ✏️ Sửa nhanh câu active")
                    with st.form("wc_edit_active_form"):
                        edit_text = st.text_area("Chỉnh nội dung", value=active_qtext, height=110, key="wc_edit_text")
                        if st.form_submit_button("LƯU CHỈNH SỬA"):
                            for q in bank["questions"]:
                                if q.get("id") == active_qid:
                                    q["text"] = edit_text.strip()
                                    q["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            save_wc_bank(cid, bank)
                            st.toast("Đã cập nhật.")
                            time.sleep(0.15)
                            st.rerun()

                    st.markdown("###### 🚀 Kích hoạt câu bất kỳ")
                    q_labels = []
                    q_map = {}
                    for q in bank.get("questions", []):
                        qid = q.get("id")
                        txt = q.get("text", "")
                        label = f"{qid} — {txt[:70]}{'...' if len(txt)>70 else ''}"
                        q_labels.append(label)
                        q_map[label] = qid

                    default_idx = 0
                    for idx, lab in enumerate(q_labels):
                        if lab.startswith(active_qid + " —"):
                            default_idx = idx
                            break

                    sel_label = st.selectbox("Chọn câu", q_labels, index=default_idx, key="wc_activate_select")
                    if st.button("KÍCH HOẠT", key="wc_activate_btn"):
                        bank["active_id"] = q_map.get(sel_label, active_qid)
                        save_wc_bank(cid, bank)
                        st.toast("Đã kích hoạt.")
                        time.sleep(0.15)
                        st.rerun()

                    st.markdown("###### 🗑 Xóa câu (không xóa file dữ liệu)")
                    del_label = st.selectbox("Chọn câu để xóa khỏi danh sách", q_labels, key="wc_del_select")
                    if st.button("XÓA KHỎI DANH SÁCH", key="wc_del_btn"):
                        del_id = q_map.get(del_label)
                        if del_id == active_qid and len(bank.get("questions", [])) == 1:
                            st.warning("Không thể xóa: phải còn ít nhất 1 câu.")
                        else:
                            bank["questions"] = [q for q in bank["questions"] if q.get("id") != del_id]
                            if bank.get("active_id") == del_id:
                                bank["active_id"] = bank["questions"][0].get("id", "Q1")
                            save_wc_bank(cid, bank)
                            st.toast("Đã xóa khỏi danh sách (dữ liệu vẫn còn).")
                            time.sleep(0.15)
                            st.rerun()

                with right_admin:
                    rows = []
                    for q in bank.get("questions", []):
                        qid = q.get("id", "")
                        rows.append(
                            {
                                "Câu": qid,
                                "Trạng thái": "ACTIVE" if qid == active_qid else "",
                                "Lượt gửi": wc_count_answers(cid, qid),
                                "Cập nhật": q.get("updated_at", q.get("created_at", "")),
                                "Nội dung": q.get("text", ""),
                            }
                        )
                    hist_df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["Câu", "Trạng thái", "Lượt gửi", "Cập nhật", "Nội dung"])
                    st.dataframe(hist_df, use_container_width=True, hide_index=True)

                    st.markdown("###### 🔎 Quick View")
                    qid_quick = st.selectbox("Chọn câu", [r["Câu"] for r in rows] if rows else [active_qid], key="wc_quick_select")
                    q_obj = next((q for q in bank.get("questions", []) if q.get("id") == qid_quick), None)
                    q_text_quick = (q_obj.get("text") if q_obj else active_qtext) or ""
                    st.info(f"**({qid_quick})** {q_text_quick}")

                    bq1, bq2, bq3 = st.columns([2, 2, 2])
                    with bq1:
                        if st.button("🖥 Fullscreen", key="wc_quick_fs"):
                            qp_set(wcfs="1", wcq=qid_quick)
                            st.rerun()
                    with bq2:
                        if st.button("🚀 Kích hoạt", key="wc_quick_activate"):
                            bank["active_id"] = qid_quick
                            save_wc_bank(cid, bank)
                            st.toast("Đã kích hoạt.")
                            time.sleep(0.15)
                            st.rerun()
                    with bq3:
                        quick_table = st.toggle("Bảng Top", value=False, key="wc_quick_table")

                    freq_q, ta, tp, tu = wc_compute_freq_for_qid(cid, qid_quick)
                    if freq_q:
                        items_q = sorted(freq_q.items(), key=lambda x: x[1], reverse=True)[:60]
                        words_payload_q = [{"text": k, "value": int(v)} for k, v in items_q]
                        wc_html_q = build_wordcloud_html(json.dumps(words_payload_q, ensure_ascii=False), height_px=420)
                        st.components.v1.html(wc_html_q, height=440, scrolling=False)
                        st.caption(f"👥 Lượt gửi: **{ta}** • 👤 Người tham gia: **{tp}** • 🧩 Cụm duy nhất: **{tu}**")
                        if quick_table:
                            st.dataframe(pd.DataFrame(items_q[:20], columns=["Từ/cụm", "Số người nhập"]), use_container_width=True, hide_index=True)
                    else:
                        st.warning("Câu này chưa có dữ liệu.")

    # =========================
    # POLL
    # =========================
    elif act == "poll":
        c1, c2 = st.columns([1, 2])
        options = cfg["options"]

        with c1:
            st.info(f"Câu hỏi: **{cfg['question']}**")

            device_id = st.session_state.get("device_id", "")
            already_voted = poll_has_voted(cid, device_id)

            if st.session_state["role"] == "student":
                if already_voted:
                    st.error("Máy này đã bình chọn rồi. Mỗi máy chỉ được bình chọn 1 lần.")
                else:
                    with st.form("f_poll"):
                        n = st.text_input("Tên", key="poll_name")
                        vote = st.radio("Lựa chọn", options, key="poll_choice")
                        if st.form_submit_button("BÌNH CHỌN"):
                            if not n.strip():
                                st.warning("Vui lòng nhập Tên.")
                            else:
                                poll_mark_voted(cid, device_id)
                                save_data(cid, "poll", n, vote)
                                st.success("Đã chọn!")
                                time.sleep(0.15)
                                st.rerun()
            else:
                st.caption(f"Đáp án gợi ý (chỉ GV): **{cfg.get('correct','')}**")
                st.caption(f"Thiết bị (debug): {device_id[:8]}…")

        with c2:
            st.markdown("##### 📊 THỐNG KÊ")
            df = load_data(cid, "poll")

            top_btn1, top_btn2 = st.columns([2, 3])
            with top_btn1:
                if st.session_state["role"] == "teacher":
                    if st.button("🖥 FULLSCREEN BIỂU ĐỒ", key="poll_btn_fullscreen"):
                        st.session_state["poll_fullscreen"] = True
                        st.rerun()
            with top_btn2:
                st.caption("Biểu đồ tự co giãn theo màn hình.")

            with st.container(border=True):
                if not df.empty:
                    cnt = df["Nội dung"].value_counts().reset_index()
                    cnt.columns = ["Lựa chọn", "Số lượng"]
                    fig = go.Figure([go.Bar(x=cnt["Lựa chọn"], y=cnt["Số lượng"], text=cnt["Số lượng"], textposition="auto")])
                    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), xaxis_title=None, yaxis_title=None)

                    if st.session_state.get("poll_fullscreen", False) and st.session_state["role"] == "teacher":
                        open_poll_fullscreen_dialog(fig)

                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Chưa có bình chọn nào.")

    # =========================
    # OPEN ENDED
    # =========================
    elif act == "openended":
        bank = load_oe_bank(cid)
        active_q = oe_get_active_question(cid, bank)
        active_qid = active_q.get("id", "Q1")
        active_qtext = active_q.get("text", cfg["question"])

        # fullscreen page via qp: oefs=1&oeq=Qn
        is_oe_fs = (qp_get("oefs", "0") == "1")
        fs_oe_qid = qp_get("oeq", active_qid) or active_qid

        if is_oe_fs:
            st.markdown(
                f"""
<style>
[data-testid="stSidebar"] {{display:none !important;}}
.block-container {{max-width: 100% !important; padding: 0.4rem 0.8rem !important;}}
.note-card {{
  font-size: 28px !important;
  line-height: 1.25 !important;
  font-weight: 700;
}}
</style>
""",
                unsafe_allow_html=True,
            )

            b1, b2, b3 = st.columns([2, 6, 2])
            with b1:
                if st.button("⬅️ Thoát Fullscreen", key="oe_exit_fs"):
                    qp_clear()
                    st.rerun()
            with b2:
                q_obj_fs = next((q for q in bank.get("questions", []) if q.get("id") == fs_oe_qid), None)
                q_text_fs = (q_obj_fs.get("text") if q_obj_fs else active_qtext) or active_qtext
                st.markdown("### 💬 Fullscreen Open Ended")
                st.markdown(f"**Câu hỏi ({fs_oe_qid}):** {q_text_fs}")
            with b3:
                live_fs = st.toggle("🔴 Live (1.5s)", value=True, key="oe_live_fs")
                if live_fs and st_autorefresh is not None:
                    st_autorefresh(interval=1500, key="oe_live_refresh_fs")

            df_fs = load_data(cid, "openended", suffix=fs_oe_qid)
            with st.container(border=True, height=820):
                if df_fs is not None and not df_fs.empty:
                    for _, r in df_fs.iterrows():
                        st.markdown(f'<div class="note-card"><b>{r["Học viên"]}</b>: {r["Nội dung"]}</div>', unsafe_allow_html=True)
                else:
                    st.info("Chưa có câu trả lời.")

            if st.session_state["role"] == "teacher":
                st.markdown("---")
                st.markdown("### 🤖 AI phân tích (đúng câu đang xem)")
                prompt_fs = st.text_input(
                    "Yêu cầu phân tích",
                    value="Rút ra 3 xu hướng chính, 3 lỗi lập luận phổ biến, và 3 gợi ý can thiệp sư phạm.",
                    key="oe_fs_ai_prompt",
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
3) 3 gợi ý can thiệp sư phạm
4) 3 câu hỏi gợi mở
"""
                            res = model.generate_content(payload)
                            st.info(res.text)

            return

        # normal view
        df_active = load_data(cid, "openended", suffix=active_qid)
        c1, c2 = st.columns([1, 2])

        with c1:
            st.info(f"Câu hỏi đang kích hoạt ({active_qid}): **{active_qtext}**")
            if st.session_state["role"] == "student":
                with st.form("f_open"):
                    n = st.text_input("Tên", key="oe_name")
                    c = st.text_area("Câu trả lời", key="oe_answer")
                    if st.form_submit_button("GỬI"):
                        if n.strip() and c.strip():
                            save_data(cid, "openended", n, c, suffix=active_qid)
                            st.success("Đã gửi!")
                            time.sleep(0.15)
                            st.rerun()
                        else:
                            st.warning("Vui lòng nhập đủ Tên và nội dung.")
            else:
                st.warning("Giảng viên xem bức tường bên phải + quản trị câu hỏi bên dưới.")

        with c2:
            st.markdown("##### 💬 BỨC TƯỜNG Ý KIẾN (CÂU ĐANG KÍCH HOẠT)")
            b1, b2, b3 = st.columns([2, 2, 2])
            with b1:
                live = st.toggle("🔴 Live update (1.5s)", value=True, key="oe_live_toggle")
            with b2:
                if st.session_state["role"] == "teacher":
                    if st.button("🖥 FULLSCREEN", key="oe_btn_full"):
                        qp_set(oefs="1", oeq=active_qid)
                        st.rerun()
            with b3:
                show_ai = (st.session_state["role"] == "teacher") and st.toggle("Hiện AI", value=True, key="oe_show_ai")

            if live and st_autorefresh is not None:
                st_autorefresh(interval=1500, key="oe_live_refresh")

            with st.container(border=True, height=520):
                if df_active is not None and not df_active.empty:
                    for _, r in df_active.iterrows():
                        st.markdown(f'<div class="note-card"><b>{r["Học viên"]}</b>: {r["Nội dung"]}</div>', unsafe_allow_html=True)
                else:
                    st.info("Chưa có câu trả lời.")

            if show_ai:
                st.markdown("---")
                st.markdown("###### 🤖 AI phân tích (câu đang kích hoạt)")
                default_prompt = "Phân loại ý kiến theo nhóm quan điểm, nêu điểm mạnh/yếu, trích 3 ví dụ tiêu biểu, và đề xuất 3 can thiệp sư phạm."
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
Bạn là trợ giảng cho giảng viên.

CHỦ ĐỀ LỚP:
{CLASS_ACT_CONFIG[cid]['topic']}

CÂU HỎI ({active_qid}):
{active_qtext}

DỮ LIỆU (bảng):
{df_active.to_string(index=False)}

YÊU CẦU:
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

        # teacher admin OE
        if st.session_state["role"] == "teacher":
            st.markdown("---")
            with st.expander("🧠 OPEN ENDED • QUẢN TRỊ CÂU HỎI + Lịch sử + Quick View", expanded=True):
                left_admin, right_admin = st.columns([2, 3])

                with left_admin:
                    st.success(f"✅ Active: ({active_qid}) {active_qtext}")

                    st.markdown("###### ➕ Thêm câu hỏi mới")
                    with st.form("oe_add_q_form"):
                        new_text = st.text_area("Nội dung câu hỏi mới", height=110, key="oe_new_q_text")
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
                                st.toast("Đã tạo.")
                                time.sleep(0.15)
                                st.rerun()

                    st.markdown("###### ✏️ Sửa nhanh câu active")
                    with st.form("oe_edit_active_form"):
                        edit_text = st.text_area("Chỉnh nội dung", value=active_qtext, height=110, key="oe_edit_text")
                        if st.form_submit_button("LƯU CHỈNH SỬA"):
                            for q in bank["questions"]:
                                if q.get("id") == active_qid:
                                    q["text"] = edit_text.strip()
                                    q["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            save_oe_bank(cid, bank)
                            st.toast("Đã cập nhật.")
                            time.sleep(0.15)
                            st.rerun()

                    st.markdown("###### 🚀 Kích hoạt câu bất kỳ")
                    q_labels = []
                    q_map = {}
                    for q in bank.get("questions", []):
                        qid = q.get("id")
                        txt = q.get("text", "")
                        label = f"{qid} — {txt[:70]}{'...' if len(txt)>70 else ''}"
                        q_labels.append(label)
                        q_map[label] = qid

                    sel_label = st.selectbox("Chọn câu", q_labels, key="oe_activate_select")
                    if st.button("KÍCH HOẠT", key="oe_activate_btn"):
                        bank["active_id"] = q_map.get(sel_label, active_qid)
                        save_oe_bank(cid, bank)
                        st.toast("Đã kích hoạt.")
                        time.sleep(0.15)
                        st.rerun()

                    st.markdown("###### 🗑 Xóa câu (không xóa file dữ liệu)")
                    del_label = st.selectbox("Chọn câu để xóa khỏi danh sách", q_labels, key="oe_del_select")
                    if st.button("XÓA KHỎI DANH SÁCH", key="oe_del_btn"):
                        del_id = q_map.get(del_label)
                        if del_id == active_qid and len(bank.get("questions", [])) == 1:
                            st.warning("Không thể xóa: phải còn ít nhất 1 câu.")
                        else:
                            bank["questions"] = [q for q in bank["questions"] if q.get("id") != del_id]
                            if bank.get("active_id") == del_id:
                                bank["active_id"] = bank["questions"][0].get("id", "Q1")
                            save_oe_bank(cid, bank)
                            st.toast("Đã xóa khỏi danh sách.")
                            time.sleep(0.15)
                            st.rerun()

                with right_admin:
                    rows = []
                    for q in bank.get("questions", []):
                        qid = q.get("id", "")
                        rows.append(
                            {
                                "Câu": qid,
                                "Trạng thái": "ACTIVE" if qid == active_qid else "",
                                "Lượt gửi": oe_count_answers(cid, qid),
                                "Cập nhật": q.get("updated_at", q.get("created_at", "")),
                                "Nội dung": q.get("text", ""),
                            }
                        )
                    hist_df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["Câu", "Trạng thái", "Lượt gửi", "Cập nhật", "Nội dung"])
                    st.dataframe(hist_df, use_container_width=True, hide_index=True)

                    st.markdown("###### 🔎 Quick View")
                    qid_quick = st.selectbox("Chọn câu", [r["Câu"] for r in rows] if rows else [active_qid], key="oe_quick_select")
                    q_obj = next((q for q in bank.get("questions", []) if q.get("id") == qid_quick), None)
                    q_text_quick = (q_obj.get("text") if q_obj else active_qtext) or active_qtext
                    df_quick = load_data(cid, "openended", suffix=qid_quick)

                    qb1, qb2 = st.columns([2, 2])
                    with qb1:
                        if st.button("🖥 Fullscreen (câu này)", key="oe_quick_fs"):
                            qp_set(oefs="1", oeq=qid_quick)
                            st.rerun()
                    with qb2:
                        if st.button("🚀 Kích hoạt (câu này)", key="oe_quick_activate"):
                            bank["active_id"] = qid_quick
                            save_oe_bank(cid, bank)
                            st.toast("Đã kích hoạt.")
                            time.sleep(0.15)
                            st.rerun()

                    st.info(f"**({qid_quick})** {q_text_quick}")

                    with st.container(border=True, height=420):
                        if df_quick is not None and not df_quick.empty:
                            for _, r in df_quick.iterrows():
                                st.markdown(f'<div class="note-card"><b>{r["Học viên"]}</b>: {r["Nội dung"]}</div>', unsafe_allow_html=True)
                        else:
                            st.warning("Câu này chưa có dữ liệu.")

    # =========================
    # SCALES
    # =========================
    elif act == "scales":
        c1, c2 = st.columns([1, 2])
        criteria = cfg["criteria"]

        with c1:
            st.info(f"**{cfg['question']}**")
            if st.session_state["role"] == "student":
                with st.form("f_scale"):
                    n = st.text_input("Tên", key="sc_name")
                    scores = []
                    for cri in criteria:
                        scores.append(st.slider(cri, 1, 5, 3, key=f"sc_{cri}"))
                    if st.form_submit_button("GỬI ĐÁNH GIÁ"):
                        if n.strip():
                            val = ",".join(map(str, scores))
                            save_data(cid, "scales", n, val)
                            st.success("Đã lưu!")
                            time.sleep(0.15)
                            st.rerun()
                        else:
                            st.warning("Vui lòng nhập Tên.")

        with c2:
            st.markdown("##### 🕸️ TỔNG HỢP")
            df = load_data(cid, "scales")
            with st.container(border=True):
                if not df.empty:
                    try:
                        data_matrix = []
                        for item in df["Nội dung"]:
                            data_matrix.append([int(x) for x in str(item).split(",")])
                        avg_scores = np.mean(data_matrix, axis=0)

                        fig = go.Figure(data=go.Scatterpolar(r=avg_scores, theta=criteria, fill="toself", name="Lớp"))
                        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5])), showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception:
                        st.error("Dữ liệu lỗi định dạng.")
                else:
                    st.info("Chưa có dữ liệu thang đo.")

    # =========================
    # RANKING
    # =========================
    elif act == "ranking":
        c1, c2 = st.columns([1, 2])
        items = cfg["items"]

        with c1:
            st.info(f"**{cfg['question']}**")
            if st.session_state["role"] == "student":
                with st.form("f_rank"):
                    n = st.text_input("Tên", key="rk_name")
                    rank = st.multiselect("Chọn theo thứ tự (chọn đủ tất cả mục)", items, key="rk_order")
                    if st.form_submit_button("NỘP"):
                        if not n.strip():
                            st.warning("Vui lòng nhập Tên.")
                        elif len(rank) != len(items):
                            st.warning(f"Vui lòng chọn đủ {len(items)} mục.")
                        else:
                            save_data(cid, "ranking", n, "->".join(rank))
                            st.success("Đã nộp!")
                            time.sleep(0.15)
                            st.rerun()

        with c2:
            st.markdown("##### 🏆 KẾT QUẢ (Borda-like)")
            df = load_data(cid, "ranking")
            with st.container(border=True):
                if not df.empty:
                    scores = {k: 0 for k in items}
                    for r in df["Nội dung"]:
                        parts = str(r).split("->")
                        # Nếu thiếu mục, bỏ qua để tránh bias
                        if len(parts) != len(items):
                            continue
                        for idx, item in enumerate(parts):
                            if item in scores:
                                scores[item] += (len(items) - idx)

                    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                    labels = [x[0] for x in sorted_items]
                    vals = [x[1] for x in sorted_items]

                    fig = px.bar(x=vals, y=labels, orientation="h", labels={"x": "Tổng điểm", "y": "Mục"}, text=vals)
                    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), yaxis={"categoryorder": "total ascending"})
                    st.plotly_chart(fig, use_container_width=True)

                    st.caption("Cách tính: mục được xếp #1 nhận nhiều điểm nhất; cộng dồn toàn lớp.")
                else:
                    st.info("Chưa có dữ liệu ranking.")

    # =========================
    # PIN
    # =========================
    elif act == "pin":
        image_url = cfg.get("image", MAP_IMAGE)
        c1, c2 = st.columns([1, 2])

        with c1:
            st.info(f"**{cfg['question']}**")
            if st.session_state["role"] == "student":
                with st.form("f_pin"):
                    n = st.text_input("Tên", key="pin_name")
                    st.caption("Chọn vị trí (0–100) theo %: x (ngang), y (dọc).")
                    x = st.slider("x (%)", 0, 100, 50, key="pin_x")
                    y = st.slider("y (%)", 0, 100, 50, key="pin_y")
                    if st.form_submit_button("GỬI GHIM"):
                        if not n.strip():
                            st.warning("Vui lòng nhập Tên.")
                        else:
                            save_data(cid, "pin", n, f"{x},{y}")
                            st.success("Đã ghim!")
                            time.sleep(0.15)
                            st.rerun()
            else:
                st.caption("Giảng viên xem overlay bên phải.")

        with c2:
            st.markdown("##### 📍 BẢN ĐỒ GHIM")
            live = st.toggle("🔴 Live update (1.5s)", value=True, key="pin_live")
            if live and st_autorefresh is not None:
                st_autorefresh(interval=1500, key="pin_live_refresh")

            df = load_data(cid, "pin")
            pts = pin_parse_points(df)
            fig = pin_make_figure(image_url, pts)
            st.plotly_chart(fig, use_container_width=True)

            if st.session_state["role"] == "teacher":
                with st.expander("⚙️ Quản trị Pin (GV)", expanded=False):
                    st.caption("Reset toàn bộ ghim của lớp (hoạt động Pin).")
                    if st.button("🧹 RESET PIN", key="pin_reset"):
                        clear_activity(cid, "pin")
                        st.toast("Đã reset Pin.")
                        time.sleep(0.15)
                        st.rerun()

    else:
        st.error("Hoạt động không hợp lệ.")


# ============================================================
# 23) ROUTER
# ============================================================
if st.session_state["page"] == "login":
    render_login()

inject_main_styles()
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
