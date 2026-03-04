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
def get_ai_client():
    """Lazy init Gemini client (teacher only). Reads key from ENV (systemd) first."""
    try:
        import os
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY")

        # fallback secrets (local only)
        if not api_key:
            try:
                import streamlit as st
                api_key = st.secrets.get("GEMINI_API_KEY")
            except Exception:
                api_key = None

        if not api_key or not str(api_key).strip():
            print("❌ GEMINI_API_KEY not found (env/secrets).")
            return None

        return genai.Client(api_key=str(api_key).strip())

    except Exception as e:
        print("❌ Gemini init error:", repr(e))
        return None

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
        open_q = "Hãy viết 3–5 câu: phân biệt *nguyên nhân – nguyên cớ – điều kiện* trong một vụ án giả định (tự chọn)."
        criteria = ["Nhận diện nguyên nhân", "Nhận diện nguyên cớ", "Nhận diện điều kiện", "Lập luận logic"]
        rank_items = ["Thu thập dấu vết vật chất", "Xác minh chuỗi nguyên nhân", "Loại bỏ 'nguyên cớ' ngụy biện", "Kiểm tra điều kiện cần/đủ"]
        pin_q = "Ghim 'điểm nóng' nơi dễ phát sinh nguyên cớ (kích động, tin đồn...) trong sơ đồ."
    elif cid in ["lop3", "lop4"]:
        wc_q = "1 từ khóa mô tả đúng nhất 'tính kế thừa' trong phủ định biện chứng?"
        poll_q = "Điểm phân biệt cốt lõi giữa 'phủ định biện chứng' và 'phủ định siêu hình' là gì?"
        poll_opts = ["Có tính kế thừa", "Phủ định sạch trơn", "Ngẫu nhiên thuần túy", "Không dựa mâu thuẫn nội tại"]
        open_q = "Nêu 1 ví dụ trong công tác/đời sống thể hiện phát triển theo 'đường xoáy ốc' (tối thiểu 5 câu)."
        criteria = ["Nêu đúng 2 lần phủ định", "Chỉ ra yếu tố kế thừa", "Chỉ ra yếu tố vượt bỏ", "Kết nối thực tiễn"]
        rank_items = ["Xác định cái cũ cần vượt bỏ", "Giữ lại yếu tố hợp lý", "Tạo cơ chế tự phủ định", "Ổn định cái mới"]
        pin_q = "Ghim vị trí minh họa 'điểm bẻ gãy' khi mâu thuẫn chín muồi dẫn tới phủ định."
    elif cid in ["lop5", "lop6"]:
        wc_q = "1 từ khóa mô tả 'bản chất con người' trong quan điểm Mác?"
        poll_q = "Theo Mác, bản chất con người trước hết là gì?"
        poll_opts = ["Tổng hòa các quan hệ xã hội", "Bản năng sinh học cố định", "Tinh thần thuần túy", "Ý chí cá nhân đơn lẻ"]
        open_q = "Mô tả một biểu hiện 'tha hóa' trong lao động (5–7 câu) và gợi ý 1 hướng 'giải phóng'."
        criteria = ["Nêu đúng biểu hiện tha hóa", "Chỉ ra nguyên nhân xã hội", "Nêu hướng khắc phục", "Tính thực tiễn"]
        rank_items = ["Cải thiện điều kiện lao động", "Dân chủ hóa tổ chức", "Phát triển năng lực NLĐ", "Phân phối công bằng"]
        pin_q = "Ghim nơi thể hiện mâu thuẫn giữa 'con người' và 'cơ chế' gây tha hóa (tượng trưng)."
    elif cid in ["lop7", "lop8"]:
        wc_q = "1 từ khóa mô tả quan hệ *cá nhân – xã hội* theo cách nhìn biện chứng?"
        poll_q = "Khẳng định nào đúng nhất về quan hệ cá nhân – xã hội?"
        poll_opts = ["Cá nhân và xã hội quy định lẫn nhau", "Xã hội chỉ là tổng số cá nhân", "Cá nhân quyết định tuyệt đối", "Xã hội quyết định tuyệt đối"]
        open_q = "Nêu 1 vấn đề con người ở Việt Nam hiện nay và phân tích theo 2 chiều: cá nhân – xã hội."
        criteria = ["Nêu vấn đề đúng trọng tâm", "Phân tích chiều cá nhân", "Phân tích chiều xã hội", "Đề xuất giải pháp"]
        rank_items = ["Giáo dục đạo đức – pháp luật", "Môi trường xã hội lành mạnh", "Cơ chế khuyến khích", "Xử lý lệch chuẩn công bằng"]
        pin_q = "Ghim vị trí 'điểm nghẽn' giữa cá nhân – tổ chức – xã hội (tượng trưng)."
    else:
        wc_q = "1 từ khóa mô tả 'hạt nhân' của phép biện chứng duy vật?"
        poll_q = "Trong triết học Mác – Lênin, vấn đề cơ bản của triết học là gì?"
        poll_opts = ["Quan hệ vật chất – ý thức", "Quan hệ cái riêng – cái chung", "Quan hệ lượng – chất", "Quan hệ hình thức – nội dung"]
        open_q = "Viết 5–7 câu: Vì sao người cán bộ cần lập trường duy vật biện chứng khi xử lý chứng cứ?"
        criteria = ["Nêu đúng nguyên tắc", "Lập luận chặt chẽ", "Liên hệ nghề nghiệp", "Diễn đạt rõ ràng"]
        rank_items = ["Tôn trọng khách quan", "Chứng cứ vật chất", "Phân tích mâu thuẫn", "Kết luận kiểm chứng được"]
        pin_q = "Ghim vị trí 'nơi phát sinh sai lệch nhận thức' trong quy trình xử lý thông tin (tượng trưng)."

    CLASS_ACT_CONFIG[cid] = {
        "topic": topic,
        "wordcloud": {"name": "Word Cloud", "question": wc_q},
        "poll": {"name": "Poll", "question": poll_q, "options": poll_opts},
        "openended": {"name": "Open Ended", "question": open_q},
        "scales": {"name": "Scales", "question": "Tự đánh giá theo thang 1–5.", "criteria": criteria},
        "ranking": {"name": "Ranking", "question": "Sắp xếp ưu tiên (quan trọng nhất lên đầu).", "items": rank_items},
        "pin": {"name": "Pin", "question": pin_q, "image": MAP_IMAGE},
    }

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

def build_wordcloud_html(words_json: str, height_px: int = 520) -> str:
    # Preserved: D3 + d3-cloud wordcloud (same idea as your current version)
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

def open_wc_fullscreen_dialog(wc_html: str, live: bool):
    """Teacher-only fullscreen wordcloud."""
    if _DIALOG_DECORATOR is not None:
        @_DIALOG_DECORATOR("🖥 Fullscreen Wordcloud")
        def _inner():
            if live and st_autorefresh is not None:
                st_autorefresh(interval=1500, key="wc_live_refresh_modal")
            st.components.v1.html(wc_html, height=760, scrolling=False)
            if st.button("ĐÓNG FULLSCREEN", key="wc_close_full"):
                st.session_state["wc_fullscreen"] = False
                st.rerun()
        _inner()
    else:
        st.warning("Streamlit phiên bản hiện tại chưa hỗ trợ dialog. Đang hiển thị chế độ thay thế.")
        if live and st_autorefresh is not None:
            st_autorefresh(interval=1500, key="wc_live_refresh_modal_fallback")
        st.components.v1.html(wc_html, height=760, scrolling=False)
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
    cfg = CLASS_ACT_CONFIG[cid]
    role = st.session_state["role"]
    cls_txt = next((k for k, v in CLASSES.items() if v == cid), cid)

    st.markdown(f"## 📚 Danh mục hoạt động • **{cls_txt}**")
    st.caption(f"Chủ đề: {cfg['topic']}")

    acts = [("wordcloud", "Word Cloud"), ("poll", "Poll"), ("openended", "Open Ended"), ("scales", "Scales"), ("ranking", "Ranking"), ("pin", "Pin")]
    for key, title in acts:
        box = st.container(border=True)
        with box:
            st.markdown(f"### {title}")
            st.caption(cfg[key]["question"])
            # Only teacher sees counts (avoid disk reads by students)
            if role == "teacher":
                # For wc/oe use active Q
                if key == "wordcloud":
                    bank = load_bank(cid, "wc", cfg["wordcloud"]["question"])
                    aq = get_active_question(bank, cfg["wordcloud"]["question"])
                    df = load_data_cached(cid, "wordcloud", suffix=aq["id"])
                    st.caption(f"Đang kích hoạt: **{aq['id']}** • Lượt gửi (câu active): **{len(df)}** • Tổng câu: **{len(bank['questions'])}**")
                elif key == "openended":
                    bank = load_bank(cid, "oe", cfg["openended"]["question"])
                    aq = get_active_question(bank, cfg["openended"]["question"])
                    df = load_data_cached(cid, "openended", suffix=aq["id"])
                    st.caption(f"Đang kích hoạt: **{aq['id']}** • Lượt gửi (câu active): **{len(df)}** • Tổng câu: **{len(bank['questions'])}**")
                else:
                    df = load_data_cached(cid, key)
                    st.caption(f"Lượt gửi: **{len(df)}**")
            if st.button("MỞ", key=f"open_{key}"):
                st.session_state["current_act"] = key
                st.session_state["page"] = "activity"
                st.rerun()

# ============================================================
# 12) DASHBOARD (Teacher-only)
# ============================================================
def render_dashboard():
    if st.session_state["role"] != "teacher":
        st.warning("Dashboard chỉ dành cho giảng viên.")
        return

    cid = st.session_state["class_id"]
    cfg = CLASS_ACT_CONFIG[cid]

    st.markdown("## 🏠 Dashboard (Giảng viên)")
    st.caption(f"Chủ đề lớp: {cfg['topic']}")

    # Teacher may want live refresh here
    live = st.toggle("🔴 Live update (1.5s)", value=True)
    if live and st_autorefresh is not None:
        st_autorefresh(interval=1500, key="dash_live")

    # Counts (cached reads)
    bank_wc = load_bank(cid, "wc", cfg["wordcloud"]["question"])
    aq_wc = get_active_question(bank_wc, cfg["wordcloud"]["question"])
    n_wc = len(load_data_cached(cid, "wordcloud", suffix=aq_wc["id"]))

    bank_oe = load_bank(cid, "oe", cfg["openended"]["question"])
    aq_oe = get_active_question(bank_oe, cfg["openended"]["question"])
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
    cfg = CLASS_ACT_CONFIG[cid][act]

    top = st.columns([1, 6])
    with top[0]:
        if st.button("↩️ Về danh mục"):
            st.session_state["page"] = "class_home"
            st.rerun()
    with top[1]:
        st.markdown(f"## {cfg['name']}")

    # -----------------------------
    # WORDCLOUD
    # -----------------------------
    if act == "wordcloud":
        bank = load_bank(cid, "wc", cfg["question"])
        aq = get_active_question(bank, cfg["question"])
        qid = aq["id"]
        qtext = aq["text"]

        st.info(f"Câu hỏi đang kích hoạt ({qid}): **{qtext}**")

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
                    open_wc_fullscreen_dialog(wc_html, live=live)

                if show_table:
                    topk = pd.DataFrame(items[:25], columns=["Từ/cụm (chuẩn hoá)", "Số người nhập"])
                    st.dataframe(topk, use_container_width=True, hide_index=True)

        st.caption(f"👥 Lượt gửi: **{total_answers}** • 👤 Người tham gia (unique): **{total_people}** • 🧩 Cụm duy nhất: **{total_unique}**")

        # Teacher: question bank management
        with st.expander("🧠 Quản trị câu hỏi WordCloud", expanded=False):
            st.success(f"Đang kích hoạt: ({qid}) {qtext}")

            with st.form("wc_add_q", clear_on_submit=True):
                new_q = st.text_area("Thêm câu hỏi mới", height=100)
                make_active = st.checkbox("Kích hoạt ngay", value=True)
                if st.form_submit_button("TẠO"):
                    if not new_q.strip():
                        st.warning("Vui lòng nhập nội dung.")
                    else:
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        new_id = make_new_qid(bank)
                        bank["questions"].append({"id": new_id, "text": new_q.strip(), "created_at": now, "updated_at": now})
                        if make_active:
                            bank["active_id"] = new_id
                        save_bank(cid, "wc", bank)
                        st.toast("Đã tạo câu hỏi.")
                        st.rerun()

            labels = [f"{q['id']} — {q['text'][:80]}{'...' if len(q['text'])>80 else ''}" for q in bank["questions"]]
            pick = st.selectbox("Chọn câu để kích hoạt", labels, index=max(0, next((i for i,l in enumerate(labels) if l.startswith(qid+' —')), 0)))
            if st.button("KÍCH HOẠT"):
                new_active = pick.split(" —", 1)[0].strip()
                bank["active_id"] = new_active
                save_bank(cid, "wc", bank)
                st.toast("Đã kích hoạt.")
                st.rerun()

        # Teacher: AI analysis (optional)
        with st.expander("🤖 AI phân tích WordCloud (GV)", expanded=False):
            model = get_ai_model()
            if model is None:
                st.warning("Chưa cấu hình GEMINI_API_KEY trong st.secrets.")
            else:
                prompt = st.text_area(
                    "Prompt phân tích",
                    value="Rút ra 3–5 insight chính, phân nhóm từ khóa theo chủ đề, chỉ ra 2–3 hiểu lầm có thể có và đề xuất 3 can thiệp sư phạm.",
                    height=120,
                )
                if st.button("PHÂN TÍCH NGAY"):
                    if df.empty:
                        st.warning("Chưa có dữ liệu.")
                    else:
                        top_items = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:25]
                        with st.spinner("AI đang phân tích..."):
                            payload = f"""
Bạn là trợ giảng cho giảng viên.

CHỦ ĐỀ LỚP:
{CLASS_ACT_CONFIG[cid]['topic']}

CÂU HỎI ({qid}):
{qtext}

TOP 25 CỤM (chuẩn hoá):
{top_items}

DỮ LIỆU THÔ:
{df.to_string(index=False)}

YÊU CẦU:
{prompt}

Trả lời theo cấu trúc:
1) Insights (3–5)
2) Nhóm chủ đề + ví dụ
3) Hiểu lầm có thể có + cách chỉnh
4) 3 can thiệp sư phạm
5) 3 câu hỏi gợi mở
"""
                            res = model.generate_content(payload)
                            st.info(res.text)

        return

    # -----------------------------
    # POLL
    # -----------------------------
    if act == "poll":
        st.info(f"Câu hỏi: **{cfg['question']}**")
        options = cfg["options"]

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
        return

    # -----------------------------
    # OPEN ENDED
    # -----------------------------
    if act == "openended":
        bank = load_bank(cid, "oe", cfg["question"])
        aq = get_active_question(bank, cfg["question"])
        qid = aq["id"]
        qtext = aq["text"]

        st.info(f"Câu hỏi đang kích hoạt ({qid}): **{qtext}**")

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

        with st.expander("🧠 Quản trị câu hỏi OpenEnded", expanded=False):
            st.success(f"Đang kích hoạt: ({qid}) {qtext}")
            with st.form("oe_add_q", clear_on_submit=True):
                new_q = st.text_area("Thêm câu hỏi mới", height=100)
                make_active = st.checkbox("Kích hoạt ngay", value=True)
                if st.form_submit_button("TẠO"):
                    if not new_q.strip():
                        st.warning("Vui lòng nhập nội dung.")
                    else:
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        new_id = make_new_qid(bank)
                        bank["questions"].append({"id": new_id, "text": new_q.strip(), "created_at": now, "updated_at": now})
                        if make_active:
                            bank["active_id"] = new_id
                        save_bank(cid, "oe", bank)
                        st.toast("Đã tạo câu hỏi.")
                        st.rerun()

            labels = [f"{q['id']} — {q['text'][:80]}{'...' if len(q['text'])>80 else ''}" for q in bank["questions"]]
            pick = st.selectbox("Chọn câu để kích hoạt", labels, index=max(0, next((i for i,l in enumerate(labels) if l.startswith(qid+' —')), 0)))
            if st.button("KÍCH HOẠT", key="oe_activate_btn"):
                new_active = pick.split(" —", 1)[0].strip()
                bank["active_id"] = new_active
                save_bank(cid, "oe", bank)
                st.toast("Đã kích hoạt.")
                st.rerun()

        with st.expander("🤖 AI phân tích OpenEnded (GV)", expanded=False):
            model = get_ai_model()
            if model is None:
                st.warning("Chưa cấu hình GEMINI_API_KEY trong st.secrets.")
            else:
                prompt = st.text_input(
                    "Yêu cầu phân tích",
                    value="Phân nhóm quan điểm, chỉ ra điểm mạnh/yếu, trích 3 ví dụ tiêu biểu, và đề xuất 3 can thiệp sư phạm.",
                )
                if st.button("PHÂN TÍCH NGAY", key="oe_ai_run"):
                    if df.empty:
                        st.warning("Chưa có dữ liệu.")
                    else:
                        with st.spinner("AI đang phân tích..."):
                            payload = f"""
Bạn là trợ giảng cho giảng viên.

CHỦ ĐỀ LỚP:
{CLASS_ACT_CONFIG[cid]['topic']}

CÂU HỎI ({qid}):
{qtext}

DỮ LIỆU:
{df.to_string(index=False)}

YÊU CẦU:
{prompt}

Trả lời theo cấu trúc:
1) Tóm tắt chủ đề nổi bật
2) Phân loại quan điểm/lập luận
3) Trích dẫn minh họa (ngắn, nêu tên)
4) 3 can thiệp sư phạm
5) 3 câu hỏi gợi mở
"""
                            res = model.generate_content(payload)
                            st.info(res.text)

        return

    # -----------------------------
    # SCALES
    # -----------------------------
    if act == "scales":
        criteria = cfg["criteria"]
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
        return

    # -----------------------------
    # RANKING
    # -----------------------------
    if act == "ranking":
        items = cfg["items"]
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
        return

    # -----------------------------
    # PIN (Lightweight version to avoid heavy image click libs)
    # - Student: choose a "zone" label + optional note (submit-only)
    # - Teacher: aggregates counts + shows list
    # -----------------------------
    if act == "pin":
        st.info(f"**{cfg['question']}**")
        st.image(cfg["image"], caption="Sơ đồ minh họa (tượng trưng)", use_container_width=True)

        zones = ["Bắc", "Trung", "Nam", "Khu vực đông dân", "Khu vực trường học", "Khu vực công nghiệp", "Khác"]

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
