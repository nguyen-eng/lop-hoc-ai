# ============================================================
# T05 Interactive Class (UPGRADE: Class-based Mentimeter-like activities)
# Giữ nguyên toàn bộ code gốc, chỉ "THÊM" cấu hình nội dung theo từng lớp.
#
# Tham chiếu (links nằm trong code theo yêu cầu):
# - Mentimeter (mô hình hoạt động): https://www.mentimeter.com/
# - Streamlit widgets: https://docs.streamlit.io/develop/api-reference/widgets
# - Plotly charts: https://plotly.com/python/
# - WordCloud: https://amueller.github.io/word_cloud/
# - Google Generative AI (Gemini python): https://ai.google.dev/gemini-api/docs/quickstart?lang=python
#
# Gợi ý vận hành:
# - Mỗi lớp (lop1...lop10) sẽ tự thấy câu hỏi/đáp án/tiêu chí khác nhau cho 6 hoạt động.
# - Giảng viên xem "Gợi ý đáp án / rubric" ngay trong từng tab (không chấm tự động).
# ============================================================

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
# Ảnh nền cho hoạt động Pin (mặc định)
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

    /* VIZ CARD (Khung hiển thị biểu đồ) */
    .viz-card {{
        background: white; padding: 25px; border-radius: 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        margin-bottom: 20px; border: 1px solid #e2e8f0;
    }}

    /* INPUT FORM */
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

    /* NOTE CARD (Open Ended) */
    .note-card {{
        background: #fff; padding: 15px; border-radius: 12px;
        border-left: 5px solid {PRIMARY_COLOR}; margin-bottom: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08); font-size: 15px;
    }}

    /* SIDEBAR */
    [data-testid="stSidebar"] {{ background-color: #111827; }}
    [data-testid="stSidebar"] * {{ color: #ffffff; }}
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
for i in range(1, 9): PASSWORDS[f"lop{i}"] = f"T05-{i}"
for i in range(9, 11): PASSWORDS[f"lop{i}"] = f"LH{i}"

if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'role': '', 'class_id': ''})

def get_path(cls, act): return f"data_{cls}_{act}.csv"

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
        if os.path.exists(path): os.remove(path)

# ==========================================================
# 2.1. (THÊM) NỘI DUNG HOẠT ĐỘNG THEO LỚP (Mentimeter-like)
# ==========================================================
def _cfg_group_cause_effect():
    return {
        "topic": "Cặp phạm trù Nguyên nhân – Kết quả (và phân biệt nguyên cớ, điều kiện)",
        "wordcloud": {
            "question": "Nhập 1–2 từ khóa mô tả chuẩn nhất quan hệ **nguyên nhân – kết quả** (và điểm khác với *nguyên cớ*).",
            "expected_keywords": [
                "sinh ra", "tất yếu", "mâu thuẫn", "tác động", "quy định", "điều kiện",
                "nguyên cớ", "ngẫu nhiên", "bên ngoài", "chuỗi nguyên nhân", "cơ chế"
            ],
            "teacher_note": (
                "Gợi ý chấm nhanh: HV dùng được các từ khóa thể hiện **quan hệ sinh thành** (cause → effect), "
                "phân biệt được *nguyên cớ* là cái đi kèm/đi trước nhưng **không sinh ra** kết quả; "
                "và *điều kiện* là cái làm cho nguyên nhân phát huy tác dụng."
            )
        },
        "poll": {
            "question": "Tình huống: *Sự kiện Vịnh Bắc Bộ* được viện dẫn để Mỹ mở rộng đánh phá miền Bắc. Theo phép biện chứng, đó chủ yếu là gì?",
            "options": [
                "A. Nguyên nhân trực tiếp sinh ra kết quả",
                "B. Nguyên cớ (cái cớ) được sử dụng để hợp thức hóa hành động",
                "C. Điều kiện quyết định duy nhất",
                "D. Kết quả của nguyên nhân bên trong Việt Nam"
            ],
            "answer": "B. Nguyên cớ (cái cớ) được sử dụng để hợp thức hóa hành động",
            "teacher_note": "Điểm nhấn: *nguyên cớ* có thể xuất hiện trước, nhưng không mang cơ chế sinh thành kết quả; nó thường được **diễn giải/khai thác**."
        },
        "openended": {
            "question": "Hãy phân biệt **nguyên nhân – nguyên cớ – điều kiện** trong một vụ việc nghiệp vụ/đời sống (3–5 câu, nêu rõ tiêu chí).",
            "rubric": [
                "Nêu tiêu chí: nguyên nhân = quan hệ sinh thành; nguyên cớ = liên hệ ngẫu nhiên/bên ngoài; điều kiện = hoàn cảnh cho nguyên nhân phát huy.",
                "Chỉ ra cơ chế/đường tác động (không chỉ kể hiện tượng).",
                "Ví dụ gắn đúng tiêu chí (không lẫn nguyên cớ thành nguyên nhân)."
            ]
        },
        "scales": {
            "question": "Tự đánh giá mức độ nắm vững (1 thấp – 5 cao):",
            "criteria": [
                "Phân biệt nguyên nhân vs nguyên cớ",
                "Phân biệt nguyên nhân vs điều kiện",
                "Xây dựng chuỗi nguyên nhân trong tình huống",
                "Vận dụng vào phân tích vụ việc"
            ],
            "teacher_note": "Nếu tiêu chí (3)-(4) thấp, nên dạy thêm **chuỗi nguyên nhân** và **điều kiện đủ/điều kiện cần** (mức phổ thông, không sa vào hình thức logic học)."
        },
        "ranking": {
            "question": "Xếp hạng quy trình phân tích nguyên nhân trong tình huống (quan trọng nhất lên đầu).",
            "items": [
                "Xác định kết quả/hiện tượng cần giải thích",
                "Tìm nguyên nhân chủ yếu (bên trong) và cơ chế tác động",
                "Phân loại nguyên nhân – điều kiện – nguyên cớ",
                "Kiểm tra bằng đối chứng: nếu bỏ yếu tố A thì kết quả còn không?"
            ],
            "suggested_order": [
                "Xác định kết quả/hiện tượng cần giải thích",
                "Tìm nguyên nhân chủ yếu (bên trong) và cơ chế tác động",
                "Phân loại nguyên nhân – điều kiện – nguyên cớ",
                "Kiểm tra bằng đối chứng: nếu bỏ yếu tố A thì kết quả còn không?"
            ],
            "teacher_note": "Đúng tinh thần: bắt đầu từ **cái cần giải thích**, rồi đi vào **cơ chế sinh thành**, sau đó mới phân loại và kiểm tra."
        },
        "pin": {
            "question": "Ghim vị trí gắn với ví dụ bạn dùng để minh họa (VD: Vịnh Bắc Bộ, hoặc địa bàn tình huống của bạn).",
            "image": MAP_IMAGE,
            "teacher_note": "Không chấm đúng-sai theo tọa độ; mục tiêu là *gợi lại ký ức tình huống* và kích hoạt thảo luận."
        }
    }

def _cfg_group_negation():
    return {
        "topic": "Quy luật Phủ định của phủ định (đường xoáy ốc, tính kế thừa)",
        "wordcloud": {
            "question": "Nhập 1–2 từ khóa mô tả đúng nhất *phủ định biện chứng* và *phủ định của phủ định*.",
            "expected_keywords": [
                "kế thừa", "vượt bỏ", "mâu thuẫn", "xoáy ốc", "phát triển",
                "khâu trung gian", "tái lập", "hình thức khác", "không quay lại"
            ],
            "teacher_note": "Ưu tiên từ khóa ‘kế thừa’ + ‘vượt bỏ’ + ‘mâu thuẫn’ + ‘xoáy ốc’ (tránh hiểu thành ‘quay về nguyên trạng’)."
        },
        "poll": {
            "question": "Chọn phát biểu đúng nhất về *phủ định của phủ định*: ",
            "options": [
                "A. Cứ --A = A nên kết quả quay lại điểm xuất phát",
                "B. Phát triển là lặp lại y nguyên cái cũ nhưng đổi tên",
                "C. Cái mới ‘dường như’ lặp lại cái cũ nhưng ở trình độ cao hơn, qua kế thừa và vượt bỏ",
                "D. Phát triển luôn theo đường thẳng"
            ],
            "answer": "C. Cái mới ‘dường như’ lặp lại cái cũ nhưng ở trình độ cao hơn, qua kế thừa và vượt bỏ",
            "teacher_note": "Chốt ngộ nhận A: ‘--A = A’ chỉ là ký hiệu hình thức; biện chứng nhấn **nội dung đã biến đổi**."
        },
        "openended": {
            "question": "Dùng một ví dụ (tự nhiên/xã hội/tư duy) để giải thích vì sao phải qua *ít nhất hai lần phủ định* mới thấy khuynh hướng phát triển.",
            "rubric": [
                "Có mô tả 2 lần phủ định (A → -A → -(-A)).",
                "Nêu yếu tố kế thừa + yếu tố vượt bỏ (không ‘đập đi làm lại’).",
                "Chỉ ra ‘trình độ cao hơn’ là gì (tiêu chí đo)."
            ]
        },
        "scales": {
            "question": "Tự đánh giá mức độ nắm vững (1 thấp – 5 cao):",
            "criteria": [
                "Hiểu ‘kế thừa’ trong phủ định biện chứng",
                "Phân biệt phủ định biện chứng vs phủ định siêu hình",
                "Giải thích ‘đường xoáy ốc’ không phải vòng tròn",
                "Vận dụng vào phân tích một tiến trình lịch sử"
            ],
            "teacher_note": "Nếu (2) thấp, cần thêm tình huống phản ví dụ ‘phủ định sạch trơn’ và ‘bê nguyên’."
        },
        "ranking": {
            "question": "Xếp hạng các đặc trưng (quan trọng nhất lên đầu) để tránh hiểu sai quy luật:",
            "items": [
                "Tính kế thừa (giữ cái hợp lý của cái cũ)",
                "Mâu thuẫn nội tại là nguồn gốc vận động",
                "Có khâu trung gian và những bước quanh co",
                "Khuynh hướng phát triển theo ‘xoáy ốc’"
            ],
            "suggested_order": [
                "Mâu thuẫn nội tại là nguồn gốc vận động",
                "Tính kế thừa (giữ cái hợp lý của cái cũ)",
                "Có khâu trung gian và những bước quanh co",
                "Khuynh hướng phát triển theo ‘xoáy ốc’"
            ],
            "teacher_note": "Có thể chấp nhận hoán vị (1)-(2) tùy cách dạy; cốt lõi: *mâu thuẫn* + *kế thừa*."
        },
        "pin": {
            "question": "Ghim vào vị trí ‘bước ngoặt’ trong ví dụ lịch sử bạn chọn (ví dụ: một mốc cải cách/đổi mới).",
            "image": MAP_IMAGE,  # giữ bản đồ VN để thầy tiện dùng ví dụ lịch sử VN
            "teacher_note": "Pin chỉ để kích hoạt kể chuyện theo mốc; không chấm tọa độ."
        }
    }

def _cfg_group_human_labor():
    return {
        "topic": "Triết học về con người: quan niệm & bản chất; tha hóa trong lao động; giải phóng con người",
        "wordcloud": {
            "question": "Nhập 1–2 từ khóa mô tả *bản chất con người* theo triết học Mác (gợi ý: quan hệ xã hội, lao động...).",
            "expected_keywords": [
                "quan hệ xã hội", "lao động", "thực tiễn", "lịch sử", "sáng tạo",
                "tha hóa", "giải phóng", "tự do", "toàn diện"
            ],
            "teacher_note": "Chốt ý: bản chất con người không phải ‘tính cố định’ mà là **tổng hòa các quan hệ xã hội** (được hiện thực hóa trong thực tiễn)."
        },
        "poll": {
            "question": "Chọn phát biểu gần đúng nhất với quan điểm Mác về bản chất con người:",
            "options": [
                "A. Bản chất con người là bản năng sinh học bất biến",
                "B. Bản chất con người là tổng hòa các quan hệ xã hội",
                "C. Bản chất con người chỉ là ý thức cá nhân",
                "D. Bản chất con người quyết định hoàn toàn bởi bẩm sinh"
            ],
            "answer": "B. Bản chất con người là tổng hòa các quan hệ xã hội",
            "teacher_note": "Điểm nhấn: không phủ nhận tự nhiên-sinh học, nhưng ‘bản chất’ (triết học) là bình diện xã hội-lịch sử."
        },
        "openended": {
            "question": "Nêu một biểu hiện *tha hóa trong lao động* trong đời sống hiện nay và đề xuất một hướng *giải phóng/khắc phục* (5–7 câu).",
            "rubric": [
                "Mô tả đúng dạng tha hóa (xa lạ với sản phẩm/quá trình/lao động/đồng loại/bản thân).",
                "Chỉ ra điều kiện xã hội – tổ chức gây ra (không quy hết cho đạo đức cá nhân).",
                "Đề xuất giải pháp có cấp độ: cá nhân + tổ chức + thể chế."
            ]
        },
        "scales": {
            "question": "Tự đánh giá mức độ nắm vững (1 thấp – 5 cao):",
            "criteria": [
                "Hiểu bản chất con người là quan hệ xã hội",
                "Phân tích được cơ chế tha hóa",
                "Phân biệt ‘giải phóng’ với ‘giải tỏa cảm xúc’",
                "Liên hệ vào xây dựng nhân cách người cán bộ"
            ],
            "teacher_note": "Nếu (3) thấp, nhấn ‘giải phóng’ = cải biến quan hệ xã hội tạo ra tha hóa + phát triển năng lực người."
        },
        "ranking": {
            "question": "Xếp hạng các điều kiện để hạn chế tha hóa và hướng tới giải phóng con người:",
            "items": [
                "Tổ chức lao động hợp lý, tôn trọng nhân phẩm",
                "Phát triển giáo dục – văn hóa – năng lực sáng tạo",
                "Cải thiện quan hệ xã hội, giảm áp bức/bất công",
                "Mở rộng cơ hội tham gia, tự quản, làm chủ"
            ],
            "suggested_order": [
                "Cải thiện quan hệ xã hội, giảm áp bức/bất công",
                "Mở rộng cơ hội tham gia, tự quản, làm chủ",
                "Tổ chức lao động hợp lý, tôn trọng nhân phẩm",
                "Phát triển giáo dục – văn hóa – năng lực sáng tạo"
            ],
            "teacher_note": "Chấp nhận nhiều cách xếp, miễn có lập luận: *quan hệ xã hội* → *làm chủ* → *tổ chức lao động* → *phát triển toàn diện*."
        },
        "pin": {
            "question": "Ghim nơi bạn cho là ‘điểm nóng’ của vấn đề lao động/đời sống (địa bàn, khu công nghiệp, đô thị...).",
            "image": MAP_IMAGE,
            "teacher_note": "Pin để tạo bản đồ thảo luận; không chấm đúng-sai."
        }
    }

def _cfg_group_individual_society_vn():
    return {
        "topic": "Triết học về con người: quan hệ cá nhân – xã hội; vấn đề con người ở Việt Nam",
        "wordcloud": {
            "question": "Nhập 1–2 từ khóa về mối quan hệ **cá nhân – xã hội** (gợi ý: quyền, trách nhiệm, cộng đồng...).",
            "expected_keywords": [
                "quyền", "trách nhiệm", "cộng đồng", "kỷ cương", "tự do",
                "đoàn kết", "pháp luật", "văn hóa", "nhân phẩm", "phát triển"
            ],
            "teacher_note": "Ưu tiên từ khóa cân bằng: *tự do* ↔ *trách nhiệm*, *quyền* ↔ *nghĩa vụ*, *cá nhân* ↔ *cộng đồng*."
        },
        "poll": {
            "question": "Chọn phát biểu đúng nhất về quan hệ cá nhân – xã hội theo quan điểm mácxít:",
            "options": [
                "A. Cá nhân là tuyệt đối, xã hội chỉ là bối cảnh",
                "B. Xã hội là tuyệt đối, cá nhân chỉ là công cụ",
                "C. Cá nhân hình thành trong xã hội và đồng thời có vai trò cải biến xã hội",
                "D. Cá nhân và xã hội không liên quan nhau"
            ],
            "answer": "C. Cá nhân hình thành trong xã hội và đồng thời có vai trò cải biến xã hội",
            "teacher_note": "Điểm nhấn: tính hai chiều — xã hội tạo hình cá nhân, cá nhân (qua thực tiễn) tác động cải biến xã hội."
        },
        "openended": {
            "question": "Chọn một ‘vấn đề con người’ ở Việt Nam hiện nay (đạo đức, văn hóa, pháp luật, kỷ cương, mạng xã hội...) và nêu cách tiếp cận giải quyết ở cấp độ triết học (5–7 câu).",
            "rubric": [
                "Nêu vấn đề cụ thể (không chỉ khẩu hiệu).",
                "Chỉ ra nguyên nhân xã hội-lịch sử và cơ chế tác động đến nhân cách.",
                "Đề xuất giải pháp đa tầng: giáo dục – pháp luật – văn hóa – tổ chức."
            ]
        },
        "scales": {
            "question": "Tự đánh giá mức độ nắm vững (1 thấp – 5 cao):",
            "criteria": [
                "Hiểu tính xã hội của cá nhân",
                "Hiểu vai trò chủ thể của cá nhân",
                "Phân tích ‘vấn đề con người’ ở Việt Nam",
                "Đề xuất giải pháp có tính hệ thống"
            ],
            "teacher_note": "Nếu (2) thấp, nhấn mạnh vai trò chủ thể: cá nhân không bị ‘định mệnh hóa’ bởi hoàn cảnh."
        },
        "ranking": {
            "question": "Xếp hạng ưu tiên chính sách/giải pháp phát triển con người ở Việt Nam (quan trọng nhất lên đầu):",
            "items": [
                "Nâng cao chất lượng giáo dục – đào tạo",
                "Củng cố pháp quyền và kỷ cương xã hội",
                "Phát triển văn hóa và chuẩn mực đạo đức công",
                "Thu hẹp bất bình đẳng, mở rộng cơ hội phát triển"
            ],
            "suggested_order": [
                "Nâng cao chất lượng giáo dục – đào tạo",
                "Củng cố pháp quyền và kỷ cương xã hội",
                "Thu hẹp bất bình đẳng, mở rộng cơ hội phát triển",
                "Phát triển văn hóa và chuẩn mực đạo đức công"
            ],
            "teacher_note": "Không có ‘đáp án cứng’; yêu cầu HV lập luận theo quan hệ *thể chế–văn hóa–giáo dục–cơ hội*."
        },
        "pin": {
            "question": "Ghim nơi bạn cho là cần ưu tiên can thiệp ‘vấn đề con người’ (địa bàn, vùng, đô thị/nông thôn...).",
            "image": MAP_IMAGE,
            "teacher_note": "Pin để nhìn ‘phân bố cảm nhận’ trong lớp."
        }
    }

def _cfg_group_general_marxism():
    return {
        "topic": "Triết học Mác-xít nói chung (vật chất–ý thức; biện chứng; lịch sử; thực tiễn)",
        "wordcloud": {
            "question": "Nhập 1–2 từ khóa về ‘thế giới quan và phương pháp luận’ của triết học Mác – Lênin.",
            "expected_keywords": [
                "vật chất", "ý thức", "thực tiễn", "biện chứng", "lịch sử",
                "quy luật", "mâu thuẫn", "phát triển", "tính đảng", "khoa học"
            ],
            "teacher_note": "Ưu tiên ‘thực tiễn’ + ‘biện chứng’ để tránh học thuộc như khẩu hiệu."
        },
        "poll": {
            "question": "Theo triết học Mác – Lênin, tiêu chuẩn kiểm tra chân lý là gì?",
            "options": [
                "A. Trực giác cá nhân",
                "B. Uy tín của người nói",
                "C. Thực tiễn",
                "D. Số đông đồng ý"
            ],
            "answer": "C. Thực tiễn",
            "teacher_note": "Chốt: thực tiễn vừa là cơ sở, động lực, mục đích, vừa là tiêu chuẩn của nhận thức."
        },
        "openended": {
            "question": "Liên hệ một nguyên lý/phạm trù/quy luật triết học mácxít vào công tác học tập – rèn luyện – nghề nghiệp (5–7 câu).",
            "rubric": [
                "Nêu đúng khái niệm (không ‘trộn’ phạm trù).",
                "Có tình huống cụ thể (học tập/điều tra/đội nhóm).",
                "Rút ra phương pháp hành động (không dừng ở mô tả)."
            ]
        },
        "scales": {
            "question": "Tự đánh giá mức độ nắm vững (1 thấp – 5 cao):",
            "criteria": [
                "Hiểu vật chất quyết định ý thức",
                "Hiểu ý thức tác động trở lại vật chất",
                "Phân tích mâu thuẫn như động lực phát triển",
                "Vận dụng vào xử lý vấn đề thực tiễn"
            ],
            "teacher_note": "Nếu (2) thấp, bổ sung ví dụ ‘tổ chức – kỷ luật – kế hoạch’ như hình thức ý thức tác động trở lại."
        },
        "ranking": {
            "question": "Xếp hạng các nguyên tắc phương pháp luận (quan trọng nhất lên đầu):",
            "items": [
                "Xuất phát từ thực tiễn khách quan",
                "Nhìn sự vật trong mối liên hệ và phát triển",
                "Tôn trọng quy luật, chống chủ quan duy ý chí",
                "Kết hợp phân tích và tổng hợp"
            ],
            "suggested_order": [
                "Xuất phát từ thực tiễn khách quan",
                "Tôn trọng quy luật, chống chủ quan duy ý chí",
                "Nhìn sự vật trong mối liên hệ và phát triển",
                "Kết hợp phân tích và tổng hợp"
            ],
            "teacher_note": "Chấp nhận hoán vị (2)-(3) nếu HV lập luận tốt."
        },
        "pin": {
            "question": "Ghim nơi bạn muốn lấy ví dụ minh họa cho một vấn đề triết học (địa bàn, sự kiện, hiện tượng).",
            "image": MAP_IMAGE,
            "teacher_note": "Pin để ‘neo’ ví dụ khi thảo luận."
        }
    }

# Gán cấu hình theo lớp (đúng yêu cầu của thầy)
CLASS_CONFIG = {
    "lop1": _cfg_group_cause_effect(),
    "lop2": _cfg_group_cause_effect(),
    "lop3": _cfg_group_negation(),
    "lop4": _cfg_group_negation(),
    "lop5": _cfg_group_human_labor(),
    "lop6": _cfg_group_human_labor(),
    "lop7": _cfg_group_individual_society_vn(),
    "lop8": _cfg_group_individual_society_vn(),
    "lop9": _cfg_group_general_marxism(),
    "lop10": _cfg_group_general_marxism(),
}

def get_class_cfg(class_id: str) -> dict:
    return CLASS_CONFIG.get(class_id, _cfg_group_general_marxism())

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
                    st.rerun()
                else:
                    st.error("Sai mã lớp!")

        with tab_gv:
            t_pass = st.text_input("Mật khẩu Admin:", type="password")
            if st.button("VÀO QUẢN TRỊ"):
                if t_pass == "T05":
                    st.session_state.update({'logged_in': True, 'role': 'teacher', 'class_id': 'lop1'})
                    st.rerun()
                else:
                    st.error("Sai mật khẩu.")

# ==========================================
# 4. GIAO DIỆN CHÍNH (FULL INTERACTIVE)
# ==========================================
else:
    # --- SIDEBAR ---
    with st.sidebar:
        st.image(LOGO_URL, width=80)
        st.markdown("---")
        st.caption("🎵 NHẠC NỀN")
        st.audio("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3")

        cls_txt = [k for k,v in CLASSES.items() if v==st.session_state['class_id']][0]
        role = "HỌC VIÊN" if st.session_state['role'] == 'student' else "GIẢNG VIÊN"
        st.info(f"👤 {role}\n\n🏫 {cls_txt}")

        # (THÊM) Hiển thị chủ đề lớp
        cfg_now = get_class_cfg(st.session_state['class_id'])
        st.caption("📌 CHỦ ĐỀ LỚP")
        st.write(f"**{cfg_now.get('topic','')}**")

        if st.session_state['role'] == 'teacher':
            st.warning("CHUYỂN LỚP QUẢN LÝ")
            s_cls = st.selectbox("", list(CLASSES.keys()), label_visibility="collapsed")
            st.session_state['class_id'] = CLASSES[s_cls]
            cfg_now = get_class_cfg(st.session_state['class_id'])

        st.markdown("---")
        # DANH SÁCH HOẠT ĐỘNG
        menu = st.radio("CHỌN HOẠT ĐỘNG", [
            "🏠 Dashboard",
            "1️⃣ Word Cloud (Từ khóa)",
            "2️⃣ Poll (Bình chọn)",
            "3️⃣ Open Ended (Hỏi đáp)",
            "4️⃣ Scales (Thang đo)",
            "5️⃣ Ranking (Xếp hạng)",
            "6️⃣ Pin on Image (Ghim ảnh)"
        ])

        st.markdown("---")
        if st.button("THOÁT"):
            st.session_state.clear()
            st.rerun()

    # --- HEADER ---
    st.markdown(f"<h2 style='color:{PRIMARY_COLOR}; border-bottom:2px solid #e2e8f0; padding-bottom:10px;'>{menu}</h2>", unsafe_allow_html=True)

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

    # (THÊM) Lấy cấu hình theo lớp cho đúng hoạt động
    cfg = get_class_cfg(st.session_state['class_id'])
    act_cfg = cfg.get(current_act_key, {})

    # ==========================================
    # DASHBOARD
    # ==========================================
    if "Dashboard" in menu:
        st.markdown(f"**Chủ đề lớp:** {cfg.get('topic','')}")
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
            st.info(f"Câu hỏi: **{act_cfg.get('question','Nhập từ khóa') }**")
            if st.session_state['role'] == 'student':
                with st.form("f_wc"):
                    n = st.text_input("Tên:")
                    txt = st.text_input("Nhập 1 từ khóa:")
                    if st.form_submit_button("GỬI TỪ KHÓA"):
                        save_data(st.session_state['class_id'], current_act_key, n, txt)
                        st.success("Đã gửi!"); time.sleep(0.5); st.rerun()
            else:
                st.warning("Giảng viên xem kết quả bên phải.")
                # (THÊM) Gợi ý đáp án/tiêu chí
                with st.expander("🧩 Gợi ý đáp án / tiêu chí (dành cho giảng viên)", expanded=True):
                    st.write("**Từ khóa gợi ý:** " + ", ".join(act_cfg.get("expected_keywords", [])))
                    st.caption(act_cfg.get("teacher_note", ""))

        with c2:
            st.markdown("##### ☁️ KẾT QUẢ HIỂN THỊ")
            df = load_data(st.session_state['class_id'], current_act_key)
            with st.container(border=True):
                if not df.empty:
                    text = " ".join(df["Nội dung"].astype(str))
                    wc = WordCloud(width=800, height=400, background_color='white', colormap='ocean').generate(text)
                    fig, ax = plt.subplots(); ax.imshow(wc, interpolation='bilinear'); ax.axis("off")
                    st.pyplot(fig)
                else:
                    st.info("Chưa có dữ liệu. Mời lớp nhập từ khóa.")

    # ==========================================
    # 2. POLL (BÌNH CHỌN)
    # ==========================================
    elif "Poll" in menu:
        c1, c2 = st.columns([1, 2])
        options = act_cfg.get("options", ["Phương án A", "Phương án B", "Phương án C", "Phương án D"])
        with c1:
            st.info(f"Câu hỏi: **{act_cfg.get('question','Theo bạn, phương án nào đúng nhất?')}**")
            if st.session_state['role'] == 'student':
                with st.form("f_poll"):
                    n = st.text_input("Tên:")
                    vote = st.radio("Lựa chọn:", options)
                    if st.form_submit_button("BÌNH CHỌN"):
                        save_data(st.session_state['class_id'], current_act_key, n, vote)
                        st.success("Đã chọn!"); time.sleep(0.5); st.rerun()
            else:
                # (THÊM) Gợi ý đáp án
                with st.expander("🧩 Đáp án gợi ý (dành cho giảng viên)", expanded=True):
                    st.write(f"**Đáp án:** {act_cfg.get('answer','(chưa đặt)')}")
                    st.caption(act_cfg.get("teacher_note",""))

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
    # 3. OPEN ENDED (CÂU HỎI MỞ)
    # ==========================================
    elif "Open Ended" in menu:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.info(f"**{act_cfg.get('question','Hãy chia sẻ ý kiến của bạn')}**")
            if st.session_state['role'] == 'student':
                with st.form("f_open"):
                    n = st.text_input("Tên:")
                    c = st.text_area("Câu trả lời của bạn:")
                    if st.form_submit_button("GỬI BÀI"):
                        save_data(st.session_state['class_id'], current_act_key, n, c)
                        st.success("Đã gửi!"); time.sleep(0.5); st.rerun()
            else:
                # (THÊM) Rubric chấm
                with st.expander("🧩 Rubric / tiêu chí chấm (dành cho giảng viên)", expanded=True):
                    for i, r in enumerate(act_cfg.get("rubric", []), start=1):
                        st.write(f"{i}. {r}")

        with c2:
            st.markdown("##### 💬 BỨC TƯỜNG Ý KIẾN")
            df = load_data(st.session_state['class_id'], current_act_key)
            with st.container(border=True, height=500):
                if not df.empty:
                    for i, r in df.iterrows():
                        st.markdown(f'<div class="note-card"><b>{r["Học viên"]}</b>: {r["Nội dung"]}</div>', unsafe_allow_html=True)
                else:
                    st.info("Sàn ý kiến trống.")

    # ==========================================
    # 4. SCALES (THANG ĐO - SPIDER WEB)
    # ==========================================
    elif "Scales" in menu:
        c1, c2 = st.columns([1, 2])
        criteria = act_cfg.get("criteria", ["Kỹ năng A", "Kỹ năng B", "Kỹ năng C", "Kỹ năng D"])
        with c1:
            st.info(f"**{act_cfg.get('question','Đánh giá mức độ đồng ý (1: Thấp - 5: Cao)')}**")
            if st.session_state['role'] == 'student':
                with st.form("f_scale"):
                    n = st.text_input("Tên:")
                    scores = []
                    for cri in criteria:
                        scores.append(st.slider(cri, 1, 5, 3))
                    if st.form_submit_button("GỬI ĐÁNH GIÁ"):
                        val = ",".join(map(str, scores))
                        save_data(st.session_state['class_id'], current_act_key, n, val)
                        st.success("Đã lưu!"); time.sleep(0.5); st.rerun()
            else:
                with st.expander("🧩 Gợi ý diễn giải (dành cho giảng viên)", expanded=True):
                    st.caption(act_cfg.get("teacher_note", "Quan sát tiêu chí thấp để điều chỉnh nhịp giảng."))

        with c2:
            st.markdown("##### 🕸️ MẠNG NHỆN NĂNG LỰC")
            df = load_data(st.session_state['class_id'], current_act_key)
            with st.container(border=True):
                if not df.empty:
                    try:
                        data_matrix = []
                        for item in df["Nội dung"]:
                            data_matrix.append([int(x) for x in item.split(',')])

                        if len(data_matrix) > 0:
                            avg_scores = np.mean(data_matrix, axis=0)
                            fig = go.Figure(data=go.Scatterpolar(
                                r=avg_scores, theta=criteria, fill='toself', name='Lớp học'
                            ))
                            fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5])), showlegend=False)
                            st.plotly_chart(fig, use_container_width=True)
                    except:
                        st.error("Dữ liệu lỗi định dạng.")
                else:
                    st.info("Chưa có dữ liệu thang đo.")

    # ==========================================
    # 5. RANKING (XẾP HẠNG)
    # ==========================================
    elif "Ranking" in menu:
        c1, c2 = st.columns([1, 2])
        items = act_cfg.get("items", ["Tiêu chí 1", "Tiêu chí 2", "Tiêu chí 3", "Tiêu chí 4"])
        with c1:
            st.info(f"**{act_cfg.get('question','Sắp xếp thứ tự ưu tiên (Quan trọng nhất lên đầu)')}**")
            if st.session_state['role'] == 'student':
                with st.form("f_rank"):
                    n = st.text_input("Tên:")
                    rank = st.multiselect("Thứ tự:", items)
                    if st.form_submit_button("NỘP BẢNG XẾP HẠNG"):
                        if len(rank) == len(items):
                            save_data(st.session_state['class_id'], current_act_key, n, "->".join(rank))
                            st.success("Đã nộp!"); time.sleep(0.5); st.rerun()
                        else:
                            st.warning(f"Vui lòng chọn đủ {len(items)} mục.")
            else:
                with st.expander("🧩 Thứ tự gợi ý (dành cho giảng viên)", expanded=True):
                    sug = act_cfg.get("suggested_order", [])
                    if sug:
                        for i, x in enumerate(sug, start=1):
                            st.write(f"{i}. {x}")
                    st.caption(act_cfg.get("teacher_note", ""))

        with c2:
            st.markdown("##### 🏆 KẾT QUẢ XẾP HẠNG")
            df = load_data(st.session_state['class_id'], current_act_key)
            with st.container(border=True):
                if not df.empty:
                    scores = {k: 0 for k in items}
                    for r in df["Nội dung"]:
                        parts = r.split("->")
                        for idx, item in enumerate(parts):
                            scores[item] += (len(items) - idx)

                    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                    labels = [x[0] for x in sorted_items]
                    vals = [x[1] for x in sorted_items]

                    fig = px.bar(x=vals, y=labels, orientation='h',
                                 labels={'x':'Tổng điểm', 'y':'Mục'}, text=vals)
                    fig.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Chưa có xếp hạng.")

    # ==========================================
    # 6. PIN ON IMAGE (GHIM ẢNH)
    # ==========================================
    elif "Pin on Image" in menu:
        c1, c2 = st.columns([1, 2])
        pin_image = act_cfg.get("image", MAP_IMAGE)
        with c1:
            st.info(f"**{act_cfg.get('question','Ghim vị trí bạn chọn trên bản đồ')}**")
            if st.session_state['role'] == 'student':
                with st.form("f_pin"):
                    n = st.text_input("Tên:")
                    x_val = st.slider("Vị trí Ngang (Trái -> Phải)", 0, 100, 50)
                    y_val = st.slider("Vị trí Dọc (Dưới -> Trên)", 0, 100, 50)
                    if st.form_submit_button("GHIM VỊ TRÍ"):
                        save_data(st.session_state['class_id'], current_act_key, n, f"{x_val},{y_val}")
                        st.success("Đã ghim!"); time.sleep(0.5); st.rerun()
            else:
                with st.expander("🧩 Mục đích hoạt động (dành cho giảng viên)", expanded=True):
                    st.caption(act_cfg.get("teacher_note", ""))

        with c2:
            st.markdown("##### 📍 BẢN ĐỒ NHIỆT (HEATMAP)")
            df = load_data(st.session_state['class_id'], current_act_key)
            with st.container(border=True):
                if not df.empty:
                    try:
                        xs, ys = [], []
                        for item in df["Nội dung"]:
                            coords = item.split(',')
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
                                source=pin_image,
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
    if st.session_state['role'] == 'teacher' and "Dashboard" not in menu:
        st.markdown("---")
        with st.expander("👮‍♂️ BẢNG ĐIỀU KHIỂN GIẢNG VIÊN (Dành riêng cho hoạt động này)", expanded=True):
            col_ai, col_reset = st.columns([3, 1])

            with col_ai:
                st.markdown("###### 🤖 AI Trợ giảng")
                prompt = st.text_input("Nhập lệnh cho AI:", placeholder=f"Ví dụ: Phân tích xu hướng của {menu}...")
                if st.button("PHÂN TÍCH NGAY") and prompt:
                    curr_df = load_data(st.session_state['class_id'], current_act_key)
                    if not curr_df.empty:
                        if model is None:
                            st.warning("Chưa cấu hình GEMINI_API_KEY trong st.secrets.")
                        else:
                            with st.spinner("AI đang suy nghĩ..."):
                                # (THÊM nhẹ) đưa thêm chủ đề lớp + đáp án gợi ý để AI phân tích đúng hướng
                                context = {
                                    "chu_de_lop": cfg.get("topic",""),
                                    "cau_hoi": act_cfg.get("question",""),
                                    "goi_y_dap_an_poll": act_cfg.get("answer",""),
                                    "rubric_openended": act_cfg.get("rubric", []),
                                    "goi_y_ranking": act_cfg.get("suggested_order", [])
                                }
                                res = model.generate_content(
                                    f"Ngữ cảnh lớp: {context}. "
                                    f"Dữ liệu {menu}: {curr_df.to_string(index=False)}. "
                                    f"Yêu cầu giảng viên: {prompt}"
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
