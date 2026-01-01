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

    .login-box {{
        background: white; padding: 40px; border-radius: 20px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.1); text-align: center;
        max-width: 600px; margin: 0 auto; border-top: 6px solid {PRIMARY_COLOR};
    }}

    .viz-card {{
        background: white; padding: 25px; border-radius: 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        margin-bottom: 20px; border: 1px solid #e2e8f0;
    }}

    .stTextInput input, .stTextArea textarea {{
        border: 2px solid #e2e8f0; border-radius: 12px; padding: 12px;
    }}

    div.stButton > button {{
        background-color: {PRIMARY_COLOR}; color: white; border: none;
        border-radius: 12px; padding: 12px 16px; font-weight: 700;
        width: 100%;
        box-shadow: 0 4px 15px rgba(0, 106, 78, 0.25);
    }}
    div.stButton > button:hover {{ background-color: #00503a; transform: translateY(-1px); }}

    .note-card {{
        background: #fff; padding: 15px; border-radius: 12px;
        border-left: 5px solid {PRIMARY_COLOR}; margin-bottom: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08); font-size: 15px;
    }}

    /* Gradescope-like list row */
    .gs-row {{
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 14px 16px;
        margin-bottom: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.04);
    }}
    .gs-title {{
        font-weight: 800;
        color: #0f172a;
        font-size: 16px;
        margin: 0;
        padding: 0;
    }}
    .gs-sub {{
        color: #64748b;
        font-weight: 600;
        font-size: 13px;
        margin-top: 6px;
    }}

    [data-testid="stSidebar"] {{ background-color: #111827; }}
    [data-testid="stSidebar"] * {{ color: #ffffff; }}
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
# 1.5. “NGÂN HÀNG HOẠT ĐỘNG” THEO TỪNG LỚP (Mentimeter-like)
# - Giữ nguyên 6 loại hoạt động có sẵn
# - Chỉ thay “câu hỏi/đáp án/tiêu chí/options/items” theo lớp
# ==========================================
CLASS_BANK = {
    # LỚP 1-2: Nguyên nhân – Kết quả (phân biệt nguyên cớ, điều kiện)
    "lop1": {
        "topic": "Cặp phạm trù Nguyên nhân – Kết quả (phân biệt nguyên cớ, điều kiện)",
        "wordcloud": {"title": "Word Cloud: Từ khóa phân biệt", "q": "Nhập 1 từ khóa giúp phân biệt *nguyên nhân* với *nguyên cớ/điều kiện*."},
        "poll": {"title": "Poll: Chọn đúng bản chất", "q": "Trong các phát biểu sau, đâu là mô tả đúng nhất về *nguyên nhân*?", "options": [
            "A. Hiện tượng có trước kết quả và có liên hệ ngẫu nhiên bên ngoài",
            "B. Nhân tố sinh ra kết quả, quyết định sự xuất hiện của kết quả",
            "C. Hoàn cảnh đi kèm, tạo môi trường cho kết quả nhưng không sinh ra kết quả",
            "D. Lý do được nêu ra để biện minh hành vi sau khi kết quả đã xảy ra"
        ], "answer_key": "B"},
        "openended": {"title": "Open Ended: Tình huống vụ việc", "q": "Hãy nêu *một tình huống* trong công tác/đời sống và chỉ rõ: đâu là **nguyên nhân**, đâu là **nguyên cớ**, đâu là **điều kiện**."},
        "scales": {"title": "Scales: Tự đánh giá năng lực phân biệt", "q": "Tự đánh giá mức độ vững chắc (1 thấp – 5 cao).", "criteria": [
            "Nhận diện nguyên nhân", "Phân biệt nguyên cớ", "Phân biệt điều kiện", "Lập luận chứng minh"
        ]},
        "ranking": {"title": "Ranking: Ưu tiên khi phân tích vụ việc", "q": "Sắp xếp thứ tự ưu tiên khi phân tích một vụ việc.", "items": [
            "Xác định kết quả/hậu quả", "Truy nguyên nguyên nhân quyết định", "Tách nguyên cớ ngẫu nhiên", "Kiểm tra điều kiện đi kèm"
        ]},
        "pin": {"title": "Pin: Điểm nóng tình huống", "q": "Ghim vị trí minh họa nơi *dễ phát sinh nguyên cớ (xung đột)* trong tình huống thầy đang giảng.", "image": MAP_IMAGE},
    },
    "lop2": {
        "topic": "Cặp phạm trù Nguyên nhân – Kết quả (kỹ năng lập luận & phản biện)",
        "wordcloud": {"title": "Word Cloud: Từ khóa ‘động lực’", "q": "Nhập 1 từ khóa mô tả ‘động lực bên trong’ của sự việc (nguyên nhân)."},
        "poll": {"title": "Poll: Nhận diện nguyên cớ", "q": "Sự kiện Vịnh Bắc Bộ (1964) trong lập luận lịch sử thường được xem là gì?", "options": [
            "A. Nguyên nhân trực tiếp tất yếu", "B. Nguyên nhân sâu xa quyết định",
            "C. Nguyên cớ để hợp thức hóa hành động", "D. Điều kiện đủ duy nhất"
        ], "answer_key": "C"},
        "openended": {"title": "Open Ended: Phản bác ngộ nhận", "q": "Nêu một *ngộ nhận phổ biến* khi phân tích nguyên nhân–kết quả và cách thầy/cô sẽ phản bác."},
        "scales": {"title": "Scales: Chuẩn hóa tư duy điều tra", "q": "Tự đánh giá mức độ vận dụng được vào tư duy điều tra/nhận định vụ việc.", "criteria": [
            "Bám chứng cứ", "Tránh võ đoán", "Chuỗi nhân quả", "Loại nhiễu nguyên cớ"
        ]},
        "ranking": {"title": "Ranking: 4 bước lập luận", "q": "Xếp hạng 4 bước lập luận nhân quả.", "items": [
            "Mô tả kết quả", "Liệt kê yếu tố liên quan", "Chứng minh yếu tố sinh ra kết quả", "Kết luận nguyên nhân quyết định"
        ]},
        "pin": {"title": "Pin: Bản đồ nhân quả", "q": "Ghim nơi *bắt đầu* của chuỗi sự kiện theo phân tích của bạn.", "image": MAP_IMAGE},
    },

    # LỚP 3-4: Quy luật phủ định của phủ định
    "lop3": {
        "topic": "Quy luật Phủ định của phủ định (đường xoáy ốc, tính kế thừa)",
        "wordcloud": {"title": "Word Cloud: Từ khóa ‘kế thừa’", "q": "Nhập 1 từ khóa thể hiện đúng tinh thần *kế thừa biện chứng*."},
        "poll": {"title": "Poll: Hiểu đúng ‘hai lần phủ định’", "q": "Vì sao thường nói phát triển cần *ít nhất hai lần phủ định*?", "options": [
            "A. Vì phải quay lại y nguyên cái cũ",
            "B. Vì một lần phủ định chưa đủ hình thành chất mới ổn định",
            "C. Vì phủ định luôn do ý chí chủ quan áp đặt",
            "D. Vì mọi sự vật đều phát triển theo đường thẳng"
        ], "answer_key": "B"},
        "openended": {"title": "Open Ended: Ví dụ thực tiễn", "q": "Hãy đưa 1 ví dụ trong học tập/công tác thể hiện ‘phủ định của phủ định’ theo đường xoáy ốc."},
        "scales": {"title": "Scales: Năng lực giải thích quy luật", "q": "Tự đánh giá mức độ nắm vững.", "criteria": [
            "Phủ định biện chứng", "Tính kế thừa", "Đường xoáy ốc", "Tránh ‘a→-a→a’ máy móc"
        ]},
        "ranking": {"title": "Ranking: Trụ cột lập luận", "q": "Sắp xếp trụ cột lập luận khi giảng quy luật.", "items": [
            "Mâu thuẫn nội tại", "Phủ định biện chứng", "Kế thừa", "Trình độ phát triển cao hơn"
        ]},
        "pin": {"title": "Pin: Điểm ‘bẻ gãy’ tư duy", "q": "Ghim vị trí tượng trưng ‘điểm bẻ gãy’ nơi cái cũ bị phủ định trong ví dụ của bạn.", "image": MAP_IMAGE},
    },
    "lop4": {
        "topic": "Quy luật Phủ định của phủ định (phản biện Popper & tính kiểm chứng)",
        "wordcloud": {"title": "Word Cloud: Từ khóa ‘khả kiểm’", "q": "Nhập 1 từ khóa về *chuẩn mực lập luận* khi phản biện ‘phi khả kiểm’."},
        "poll": {"title": "Poll: Phản biện lập luận ‘mơ hồ’", "q": "Cách phản biện mạnh nhất trước phê phán ‘quy luật mơ hồ’ là gì?", "options": [
            "A. Kể thật nhiều ví dụ",
            "B. Chỉ dựa vào uy tín kinh điển",
            "C. Nêu điều kiện áp dụng + tiêu chí nhận diện phủ định biện chứng",
            "D. Bỏ qua phê phán vì ‘thù địch’"
        ], "answer_key": "C"},
        "openended": {"title": "Open Ended: Một tiêu chí nhận diện", "q": "Hãy đề xuất 1–2 **tiêu chí** giúp phân biệt ‘phủ định biện chứng’ với ‘phủ định siêu hình’."},
        "scales": {"title": "Scales: Mức độ lập luận", "q": "Tự đánh giá khả năng lập luận trước phản biện.", "criteria": [
            "Đặt điều kiện áp dụng", "Chỉ ra cơ chế nội tại", "Phân biệt ví dụ minh họa", "Kết luận có giới hạn"
        ]},
        "ranking": {"title": "Ranking: Cấu trúc trả lời phản biện", "q": "Sắp xếp cấu trúc trả lời phản biện.", "items": [
            "Làm rõ phạm vi", "Nêu tiêu chí", "Áp vào ví dụ", "Kết luận & giới hạn"
        ]},
        "pin": {"title": "Pin: Điểm tranh luận", "q": "Ghim vị trí tượng trưng ‘điểm bị hiểu sai’ mà bạn muốn giải thích.", "image": MAP_IMAGE},
    },

    # LỚP 5-6: Triết học về con người (bản chất, tha hóa, giải phóng)
    "lop5": {
        "topic": "Triết học về con người: Quan niệm & bản chất con người (Mác)",
        "wordcloud": {"title": "Word Cloud: ‘Bản chất’ là gì?", "q": "Nhập 1 từ khóa mô tả ‘bản chất con người’ theo Mác."},
        "poll": {"title": "Poll: Luận điểm trung tâm", "q": "Theo Mác, bản chất con người trước hết là gì?", "options": [
            "A. Một thuộc tính sinh học bất biến",
            "B. Một tinh thần siêu nghiệm có sẵn",
            "C. Tổng hòa những quan hệ xã hội",
            "D. Một ‘bản tính thiện/ác’ cố định"
        ], "answer_key": "C"},
        "openended": {"title": "Open Ended: Vận dụng vào môi trường CAND", "q": "Theo bạn, ‘tổng hòa quan hệ xã hội’ gợi ra điều gì khi rèn luyện phẩm chất người cán bộ?" },
        "scales": {"title": "Scales: Hiểu 4 tầng bản chất", "q": "Tự đánh giá mức độ hiểu.", "criteria": [
            "Sinh học–tự nhiên", "Xã hội–lịch sử", "Thực tiễn–lao động", "Tự ý thức–giá trị"
        ]},
        "ranking": {"title": "Ranking: Cái gì quyết định ‘tính người’?", "q": "Xếp hạng yếu tố quyết định ‘tính người’ trong phân tích của bạn.", "items": [
            "Quan hệ xã hội", "Hoạt động thực tiễn", "Giá trị–đạo đức", "Năng lực nhận thức"
        ]},
        "pin": {"title": "Pin: Không gian ‘quan hệ xã hội’", "q": "Ghim nơi biểu tượng cho ‘mạng lưới quan hệ’ chi phối sự hình thành nhân cách.", "image": MAP_IMAGE},
    },
    "lop6": {
        "topic": "Triết học về con người: Tha hóa trong lao động & giải phóng con người",
        "wordcloud": {"title": "Word Cloud: Từ khóa ‘tha hóa’", "q": "Nhập 1 từ khóa mô tả hiện tượng tha hóa."},
        "poll": {"title": "Poll: Dấu hiệu tha hóa", "q": "Dấu hiệu cốt lõi của lao động bị tha hóa là gì?", "options": [
            "A. Người lao động làm việc ít đi",
            "B. Sản phẩm/quá trình lao động quay lại thống trị người lao động",
            "C. Lao động luôn tạo hạnh phúc trực tiếp",
            "D. Lao động chỉ là hoạt động bản năng"
        ], "answer_key": "B"},
        "openended": {"title": "Open Ended: Một cơ chế giải phóng", "q": "Theo bạn, điều kiện/cơ chế nào giúp ‘giải phóng con người’ theo tinh thần Mác?" },
        "scales": {"title": "Scales: Nhận diện 4 dạng tha hóa", "q": "Tự đánh giá mức độ phân biệt.", "criteria": [
            "Tha hóa khỏi sản phẩm", "Tha hóa khỏi hoạt động", "Tha hóa khỏi ‘loài tính’", "Tha hóa khỏi người khác"
        ]},
        "ranking": {"title": "Ranking: Ưu tiên can thiệp", "q": "Xếp hạng ưu tiên can thiệp để giảm ‘tha hóa’ trong tổ chức.", "items": [
            "Mục tiêu/ý nghĩa công việc", "Cơ chế ghi nhận–đãi ngộ", "Tổ chức lao động hợp lý", "Văn hóa tổ chức"
        ]},
        "pin": {"title": "Pin: Điểm ‘đứt gãy ý nghĩa’", "q": "Ghim điểm minh họa nơi ‘ý nghĩa công việc’ bị đứt gãy dẫn tới tha hóa.", "image": MAP_IMAGE},
    },

    # LỚP 7-8: Cá nhân – xã hội, vấn đề con người ở Việt Nam
    "lop7": {
        "topic": "Triết học về con người: Quan hệ cá nhân – xã hội",
        "wordcloud": {"title": "Word Cloud: Từ khóa ‘cộng đồng’", "q": "Nhập 1 từ khóa mô tả quan hệ cá nhân–xã hội."},
        "poll": {"title": "Poll: Quan điểm đúng", "q": "Quan điểm nào đúng nhất theo duy vật lịch sử?", "options": [
            "A. Xã hội chỉ là tổng cộng cơ học các cá nhân",
            "B. Cá nhân chỉ là ‘hạt bụi’ không vai trò",
            "C. Cá nhân là chủ thể lịch sử trong những điều kiện xã hội nhất định",
            "D. Cá nhân tách khỏi xã hội vẫn phát triển đầy đủ"
        ], "answer_key": "C"},
        "openended": {"title": "Open Ended: Xung đột cá nhân–tập thể", "q": "Nêu 1 xung đột cá nhân–tập thể trong học tập/tổ chức và cách giải theo tinh thần biện chứng."},
        "scales": {"title": "Scales: Năng lực hài hòa", "q": "Tự đánh giá năng lực hài hòa cá nhân–tập thể.", "criteria": [
            "Tự chủ", "Kỷ luật", "Tinh thần cộng đồng", "Trách nhiệm xã hội"
        ]},
        "ranking": {"title": "Ranking: Trật tự ưu tiên", "q": "Xếp hạng các nguyên tắc khi xử lý mối quan hệ cá nhân–tập thể.", "items": [
            "Mục tiêu chung", "Quy chế–kỷ luật", "Tôn trọng cá nhân", "Đối thoại–phản hồi"
        ]},
        "pin": {"title": "Pin: Nút thắt tổ chức", "q": "Ghim điểm tượng trưng ‘nút thắt’ trong quan hệ cá nhân–tập thể.", "image": MAP_IMAGE},
    },
    "lop8": {
        "topic": "Triết học về con người: Vấn đề con người ở Việt Nam (bối cảnh mới)",
        "wordcloud": {"title": "Word Cloud: Thách thức con người VN", "q": "Nhập 1 từ khóa về thách thức/phẩm chất con người Việt Nam hiện nay."},
        "poll": {"title": "Poll: Ưu tiên phát triển", "q": "Ưu tiên nào là ‘đòn bẩy’ để phát triển con người ở Việt Nam?", "options": [
            "A. Chỉ tăng trưởng kinh tế, không cần văn hóa",
            "B. Phát triển toàn diện: trí tuệ–đạo đức–thể chất–thẩm mỹ",
            "C. Chỉ kỷ luật, không cần sáng tạo",
            "D. Chỉ công nghệ, không cần con người"
        ], "answer_key": "B"},
        "openended": {"title": "Open Ended: Một giải pháp cụ thể", "q": "Đề xuất 1 giải pháp cụ thể (cấp lớp/đơn vị/địa phương) để phát triển con người theo định hướng nhân văn."},
        "scales": {"title": "Scales: ‘Phẩm chất công dân’", "q": "Tự đánh giá.", "criteria": [
            "Tôn trọng pháp luật", "Tinh thần trách nhiệm", "Năng lực số", "Nhân ái–hợp tác"
        ]},
        "ranking": {"title": "Ranking: Hệ giá trị", "q": "Xếp hạng hệ giá trị ưu tiên của bạn.", "items": [
            "Trung thực", "Kỷ luật", "Sáng tạo", "Phụng sự cộng đồng"
        ]},
        "pin": {"title": "Pin: Vấn đề theo vùng", "q": "Ghim khu vực bạn cho là cần ưu tiên chính sách ‘phát triển con người’ (minh họa).", "image": MAP_IMAGE},
    },

    # LỚP 9-10: Triết học Mác-xít nói chung
    "lop9": {
        "topic": "Triết học Mác-xít: Vật chất – Ý thức, phương pháp luận",
        "wordcloud": {"title": "Word Cloud: Từ khóa ‘duy vật’", "q": "Nhập 1 từ khóa thể hiện lập trường duy vật biện chứng."},
        "poll": {"title": "Poll: Nguyên tắc nghề ĐTV", "q": "Liên hệ nghề ĐTV: phát biểu nào đúng nhất?", "options": [
            "A. Cảm nhận chủ quan quan trọng hơn chứng cứ",
            "B. Ý thức có thể ‘tạo ra’ vật chất trực tiếp",
            "C. Chứng cứ vật chất là nền tảng; ý thức định hướng cách thu thập–đánh giá",
            "D. Không cần kiểm tra chéo vì đã ‘tin chắc’"
        ], "answer_key": "C"},
        "openended": {"title": "Open Ended: Một sai lầm duy tâm", "q": "Nêu 1 sai lầm duy tâm/siêu hình trong nhận định vụ việc và cách sửa."},
        "scales": {"title": "Scales: Kỹ năng phương pháp luận", "q": "Tự đánh giá.", "criteria": [
            "Tôn trọng khách quan", "Phân tích mâu thuẫn", "Tổng hợp hệ thống", "Kiểm chứng thực tiễn"
        ]},
        "ranking": {"title": "Ranking: Ưu tiên khi lập luận", "q": "Xếp hạng ưu tiên khi lập luận khoa học.", "items": [
            "Dữ kiện–chứng cứ", "Khung lý luận", "Giả thuyết thay thế", "Kết luận có điều kiện"
        ]},
        "pin": {"title": "Pin: Điểm nóng ‘thông tin nhiễu’", "q": "Ghim điểm tượng trưng nơi dễ bị ‘thông tin nhiễu’ dẫn dắt nhận thức.", "image": MAP_IMAGE},
    },
    "lop10": {
        "topic": "Triết học Mác-xít: Phép biện chứng (toàn diện, lịch sử–cụ thể)",
        "wordcloud": {"title": "Word Cloud: Từ khóa ‘toàn diện’", "q": "Nhập 1 từ khóa về nguyên tắc toàn diện."},
        "poll": {"title": "Poll: Lịch sử–cụ thể", "q": "Nguyên tắc lịch sử–cụ thể yêu cầu điều gì?", "options": [
            "A. Dùng một công thức cho mọi tình huống",
            "B. Xem xét đối tượng trong điều kiện lịch sử cụ thể của nó",
            "C. Chỉ cần ý chí chính trị",
            "D. Chỉ cần số liệu, không cần bối cảnh"
        ], "answer_key": "B"},
        "openended": {"title": "Open Ended: Một case áp dụng", "q": "Nêu 1 case trong quản lý/lãnh đạo mà nếu bỏ bối cảnh sẽ dẫn đến quyết định sai."},
        "scales": {"title": "Scales: Năng lực biện chứng", "q": "Tự đánh giá.", "criteria": [
            "Toàn diện", "Phát triển", "Lịch sử–cụ thể", "Thực tiễn"
        ]},
        "ranking": {"title": "Ranking: Chống ‘một chiều’", "q": "Xếp hạng cách chống tư duy một chiều.", "items": [
            "Thu thập góc nhìn đối lập", "Kiểm chứng dữ liệu", "Xem điều kiện–bối cảnh", "Đặt giả thuyết thay thế"
        ]},
        "pin": {"title": "Pin: Điểm rủi ro quyết định", "q": "Ghim điểm tượng trưng ‘điểm rủi ro’ trong ra quyết định.", "image": MAP_IMAGE},
    },
}

def get_class_cfg(class_id: str):
    # fallback an toàn
    return CLASS_BANK.get(class_id, CLASS_BANK["lop1"])

# ==========================================
# 2. XỬ LÝ DỮ LIỆU (BACKEND) - GIỮ NGUYÊN
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
# 3. MÀN HÌNH ĐĂNG NHẬP - GIỮ NGUYÊN
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
# - CHỈ THÊM: danh mục hoạt động theo lớp (Gradescope-like)
# ==========================================
else:
    class_cfg = get_class_cfg(st.session_state['class_id'])

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
            class_cfg = get_class_cfg(st.session_state['class_id'])

        st.markdown("---")
        st.caption("📌 CHỦ ĐỀ LỚP")
        st.write(f"**{class_cfg['topic']}**")

        st.markdown("---")
        # DANH SÁCH HOẠT ĐỘNG - THEO LỚP (Mentimeter-like)
        menu_labels = {
            "🏠 Dashboard": "🏠 Dashboard",
            "1️⃣ Word Cloud (Từ khóa)": f"1️⃣ {class_cfg['wordcloud']['title']}",
            "2️⃣ Poll (Bình chọn)": f"2️⃣ {class_cfg['poll']['title']}",
            "3️⃣ Open Ended (Hỏi đáp)": f"3️⃣ {class_cfg['openended']['title']}",
            "4️⃣ Scales (Thang đo)": f"4️⃣ {class_cfg['scales']['title']}",
            "5️⃣ Ranking (Xếp hạng)": f"5️⃣ {class_cfg['ranking']['title']}",
            "6️⃣ Pin on Image (Ghim ảnh)": f"6️⃣ {class_cfg['pin']['title']}",
        }

        menu = st.radio("DANH MỤC HOẠT ĐỘNG", list(menu_labels.values()))

        # reverse map to canonical key
        reverse_menu = {v: k for k, v in menu_labels.items()}
        canonical_menu = reverse_menu[menu]

        st.markdown("---")
        if st.button("THOÁT"):
            st.session_state.clear()
            st.rerun()

    # --- HEADER ---
    st.markdown(
        f"<h2 style='color:{PRIMARY_COLOR}; border-bottom:2px solid #e2e8f0; padding-bottom:10px;'>{menu}</h2>",
        unsafe_allow_html=True
    )
    st.caption(f"Chủ đề lớp: **{class_cfg['topic']}**")

    # Lấy key hoạt động để lưu file (GIỮ NGUYÊN)
    act_map = {
        "1️⃣ Word Cloud (Từ khóa)": "wordcloud",
        "2️⃣ Poll (Bình chọn)": "poll",
        "3️⃣ Open Ended (Hỏi đáp)": "openended",
        "4️⃣ Scales (Thang đo)": "scales",
        "5️⃣ Ranking (Xếp hạng)": "ranking",
        "6️⃣ Pin on Image (Ghim ảnh)": "pin"
    }
    current_act_key = act_map.get(canonical_menu, "dashboard")

    # ==========================================
    # DASHBOARD (Gradescope-like: danh sách hoạt động + số lượt)
    # ==========================================
    if "Dashboard" in canonical_menu:
        st.markdown("### 📚 Danh mục hoạt động của lớp")

        activities = [
            ("wordcloud", class_cfg["wordcloud"]["title"], "Từ khóa / Word Cloud"),
            ("poll", class_cfg["poll"]["title"], "Bình chọn / Poll"),
            ("openended", class_cfg["openended"]["title"], "Trả lời mở / Open Ended"),
            ("scales", class_cfg["scales"]["title"], "Thang đo / Scales"),
            ("ranking", class_cfg["ranking"]["title"], "Xếp hạng / Ranking"),
            ("pin", class_cfg["pin"]["title"], "Ghim trên ảnh / Pin"),
        ]

        for act_key, title, typ in activities:
            df = load_data(st.session_state['class_id'], act_key)
            left, right = st.columns([5, 1])
            with left:
                st.markdown(f"""
                <div class="gs-row">
                    <div class="gs-title">{title}</div>
                    <div class="gs-sub">Loại hoạt động: {typ} • Số lượt trả lời: <b>{len(df)}</b></div>
                </div>
                """, unsafe_allow_html=True)
            with right:
                # nút mở nhanh giống “Open Assignment”
                if st.button("MỞ", key=f"open_{act_key}"):
                    # set menu bằng cách lưu session_state và rerun
                    st.session_state["__jump_to__"] = act_key
                    st.rerun()

        # nếu có jump
        if "__jump_to__" in st.session_state:
            jump = st.session_state.pop("__jump_to__")
            # chuyển sang canonical_menu tương ứng (giữ logic đơn giản)
            if jump == "wordcloud":
                st.info("Đang chuyển sang Word Cloud...")
            elif jump == "poll":
                st.info("Đang chuyển sang Poll...")
            elif jump == "openended":
                st.info("Đang chuyển sang Open Ended...")
            elif jump == "scales":
                st.info("Đang chuyển sang Scales...")
            elif jump == "ranking":
                st.info("Đang chuyển sang Ranking...")
            elif jump == "pin":
                st.info("Đang chuyển sang Pin...")

    # ==========================================
    # 1. WORD CLOUD
    # ==========================================
    elif current_act_key == "wordcloud":
        c1, c2 = st.columns([1, 2])
        with c1:
            st.info(f"Câu hỏi: **{class_cfg['wordcloud']['q']}**")
            if st.session_state['role'] == 'student':
                with st.form("f_wc"):
                    n = st.text_input("Tên:")
                    txt = st.text_input("Nhập 1 từ khóa:")
                    if st.form_submit_button("GỬI TỪ KHÓA"):
                        save_data(st.session_state['class_id'], current_act_key, n, txt)
                        st.success("Đã gửi!")
                        time.sleep(0.3)
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
    elif current_act_key == "poll":
        c1, c2 = st.columns([1, 2])
        options = class_cfg["poll"]["options"]
        with c1:
            st.info(f"Câu hỏi: **{class_cfg['poll']['q']}**")
            if st.session_state['role'] == 'student':
                with st.form("f_poll"):
                    n = st.text_input("Tên:")
                    vote = st.radio("Lựa chọn:", options)
                    if st.form_submit_button("BÌNH CHỌN"):
                        save_data(st.session_state['class_id'], current_act_key, n, vote)
                        st.success("Đã chọn!")
                        time.sleep(0.3)
                        st.rerun()

            # Gợi ý “đáp án” chỉ hiện cho GIẢNG VIÊN
            if st.session_state['role'] == 'teacher':
                st.caption(f"🔑 Đáp án dự kiến: **{class_cfg['poll'].get('answer_key','')}**")

        with c2:
            st.markdown("##### 📊 THỐNG KÊ LỰA CHỌN")
            df = load_data(st.session_state['class_id'], current_act_key)
            with st.container(border=True):
                if not df.empty:
                    cnt = df["Nội dung"].value_counts().reset_index()
                    cnt.columns = ["Lựa chọn", "Số lượng"]
                    fig = px.bar(cnt, x="Lựa chọn", y="Số lượng", text_auto=True)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Chưa có bình chọn nào.")

    # ==========================================
    # 3. OPEN ENDED
    # ==========================================
    elif current_act_key == "openended":
        c1, c2 = st.columns([1, 2])
        with c1:
            st.info(f"**{class_cfg['openended']['q']}**")
            if st.session_state['role'] == 'student':
                with st.form("f_open"):
                    n = st.text_input("Tên:")
                    c = st.text_area("Câu trả lời của bạn:")
                    if st.form_submit_button("GỬI BÀI"):
                        save_data(st.session_state['class_id'], current_act_key, n, c)
                        st.success("Đã gửi!")
                        time.sleep(0.3)
                        st.rerun()
        with c2:
            st.markdown("##### 💬 BỨC TƯỜNG Ý KIẾN")
            df = load_data(st.session_state['class_id'], current_act_key)
            with st.container(border=True, height=500):
                if not df.empty:
                    for _, r in df.iterrows():
                        st.markdown(f'<div class="note-card"><b>{r["Học viên"]}</b>: {r["Nội dung"]}</div>',
                                    unsafe_allow_html=True)
                else:
                    st.info("Sàn ý kiến trống.")

    # ==========================================
    # 4. SCALES
    # ==========================================
    elif current_act_key == "scales":
        c1, c2 = st.columns([1, 2])
        criteria = class_cfg["scales"]["criteria"]
        with c1:
            st.info(f"**{class_cfg['scales']['q']}**")
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
                        time.sleep(0.3)
                        st.rerun()
        with c2:
            st.markdown("##### 🕸️ MẠNG NHỆN NĂNG LỰC")
            df = load_data(st.session_state['class_id'], current_act_key)
            with st.container(border=True):
                if not df.empty:
                    try:
                        data_matrix = []
                        for item in df["Nội dung"]:
                            data_matrix.append([int(x) for x in str(item).split(',') if str(x).strip() != ""])
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
    elif current_act_key == "ranking":
        c1, c2 = st.columns([1, 2])
        items = class_cfg["ranking"]["items"]
        with c1:
            st.info(f"**{class_cfg['ranking']['q']}**")
            if st.session_state['role'] == 'student':
                with st.form("f_rank"):
                    n = st.text_input("Tên:")
                    rank = st.multiselect("Thứ tự (chọn đủ tất cả mục):", items)
                    if st.form_submit_button("NỘP BẢNG XẾP HẠNG"):
                        if len(rank) == len(items):
                            save_data(st.session_state['class_id'], current_act_key, n, "->".join(rank))
                            st.success("Đã nộp!")
                            time.sleep(0.3)
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
    elif current_act_key == "pin":
        c1, c2 = st.columns([1, 2])
        pin_img = class_cfg["pin"].get("image", MAP_IMAGE)
        with c1:
            st.info(f"**{class_cfg['pin']['q']}**")
            if st.session_state['role'] == 'student':
                with st.form("f_pin"):
                    n = st.text_input("Tên:")
                    x_val = st.slider("Vị trí Ngang (Trái -> Phải)", 0, 100, 50)
                    y_val = st.slider("Vị trí Dọc (Dưới -> Trên)", 0, 100, 50)
                    if st.form_submit_button("GHIM VỊ TRÍ"):
                        save_data(st.session_state['class_id'], current_act_key, n, f"{x_val},{y_val}")
                        st.success("Đã ghim!")
                        time.sleep(0.3)
                        st.rerun()
        with c2:
            st.markdown("##### 📍 BẢN ĐỒ (PIN)")
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
                            marker=dict(size=12, color='red', opacity=0.7, line=dict(width=1, color='white')),
                            name='Vị trí ghim'
                        ))
                        fig.update_layout(
                            xaxis=dict(range=[0, 100], showgrid=False, zeroline=False, visible=False),
                            yaxis=dict(range=[0, 100], showgrid=False, zeroline=False, visible=False),
                            images=[dict(
                                source=pin_img,
                                xref="x", yref="y",
                                x=0, y=100, sizex=100, sizey=100,
                                sizing="stretch", layer="below"
                            )],
                            width=700, height=420, margin=dict(l=0, r=0, t=0, b=0)
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    except:
                        st.error("Lỗi dữ liệu ghim.")
                else:
                    st.info("Chưa có ghim nào.")

    # ==========================================
    # CONTROL PANEL CHO GIẢNG VIÊN (CHUNG CHO MỌI TAB) - GIỮ NGUYÊN, CHỈ BỔ SUNG “gợi ý prompt”
    # ==========================================
    if st.session_state['role'] == 'teacher' and "Dashboard" not in canonical_menu:
        st.markdown("---")
        with st.expander("👮‍♂️ BẢNG ĐIỀU KHIỂN GIẢNG VIÊN (Dành riêng cho hoạt động này)", expanded=True):
            col_ai, col_reset = st.columns([3, 1])

            with col_ai:
                st.markdown("###### 🤖 AI Trợ giảng")
                default_hint = f"Phân tích xu hướng trả lời của lớp về: {menu}. Nêu 3 điểm mạnh, 3 ngộ nhận, và 3 gợi ý giảng tiếp."
                prompt = st.text_input("Nhập lệnh cho AI:", value=default_hint)

                if st.button("PHÂN TÍCH NGAY") and prompt:
                    curr_df = load_data(st.session_state['class_id'], current_act_key)
                    if curr_df.empty:
                        st.warning("Chưa có dữ liệu để phân tích.")
                    else:
                        if model is None:
                            st.error("Chưa cấu hình GEMINI_API_KEY trong secrets.")
                        else:
                            with st.spinner("AI đang suy nghĩ..."):
                                res = model.generate_content(
                                    f"Chủ đề lớp: {class_cfg['topic']}.\n"
                                    f"Hoạt động: {menu}.\n"
                                    f"Dữ liệu (bảng):\n{curr_df.to_string(index=False)}\n\n"
                                    f"Yêu cầu giảng viên: {prompt}\n"
                                    f"Yêu cầu trình bày: ngắn gọn, gạch đầu dòng, chỉ ra mô thức sai lầm và đề xuất câu hỏi gợi mở tiếp theo."
                                )
                                st.info(res.text)

            with col_reset:
                st.markdown("###### 🗑 Xóa dữ liệu")
                if st.button(f"RESET {menu}", type="secondary"):
                    clear_activity(st.session_state['class_id'], current_act_key)
                    st.toast(f"Đã xóa sạch dữ liệu {menu}")
                    time.sleep(0.6)
                    st.rerun()
