import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import plotly.express as px

# --- 1. CẤU HÌNH TRANG (Full màn hình) ---
st.set_page_config(
    page_title="LMS T05 - Hệ thống Lớp học",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS TÙY CHỈNH (Để giao diện đẹp như App xịn) ---
st.markdown("""
<style>
    /* Chỉnh màu nền Sidebar cho giống Gradescope */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #dee2e6;
    }
    /* Chỉnh nút bấm màu xanh chuyên nghiệp */
    div.stButton > button:first-child {
        background-color: #007bff;
        color: white;
        border-radius: 6px;
        border: none;
        padding: 0.5rem 1rem;
    }
    div.stButton > button:hover {
        background-color: #0056b3;
    }
    /* Tạo hiệu ứng thẻ (Card) */
    .metric-card {
        background-color: white;
        border: 1px solid #e9ecef;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# --- KẾT NỐI AI ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
except:
    st.error("⚠️ Chưa cấu hình API Key!")

# --- THANH ĐIỀU HƯỚNG BÊN TRÁI (SIDEBAR) ---
with st.sidebar:
    # Logo giả lập (Thầy có thể thay bằng link ảnh logo T05)
    st.image("https://cdn-icons-png.flaticon.com/512/2995/2995459.png", width=60) 
    st.title("LMS T05")
    st.caption("Khoa LLCT&KHXHNV")
    
    st.divider()
    
    # Menu điều hướng kiểu dọc (Giống Gradescope)
    menu = st.radio(
        "DI CHUYỂN ĐẾN:",
        ["🏠 Dashboard (Tổng quan)", "1️⃣ Quan điểm (Thảo luận)", "2️⃣ Quy trình (Bài tập)", "3️⃣ Thu hoạch (Tổng kết)"],
    )
    
    st.divider()
    
    # QR Code nhỏ gọn ở góc dưới
    LINK_APP = "https://share.streamlit.io/..." # Thay link của Thầy vào đây
    if LINK_APP != "https://share.streamlit.io/...":
        st.caption("Quét để vào lớp:")
        st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={LINK_APP}", width=120)

# --- HÀM HỖ TRỢ ĐỌC DỮ LIỆU ---
def load_data(filename):
    if os.path.exists(filename):
        return pd.read_csv(filename, sep="|", names=["Tên", "Nội dung"])
    return pd.DataFrame(columns=["Tên", "Nội dung"])

# ==========================================
# TRANG 1: DASHBOARD (TỔNG QUAN)
# ==========================================
if "Dashboard" in menu:
    st.title("🏠 Bảng điều khiển Lớp học")
    st.markdown("---")
    
    # Load dữ liệu thống kê
    df1 = load_data("data_tab1.csv")
    df2 = load_data("data_tab2.csv")
    df3 = load_data("data_tab3.csv")
    
    # Hiển thị 3 thẻ số liệu (Metrics)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Lượt thảo luận", f"{len(df1)}", delta="Hoạt động 1")
    with col2:
        st.metric("Bài nộp quy trình", f"{len(df2)}", delta="Hoạt động 2")
    with col3:
        st.metric("Bài thu hoạch", f"{len(df3)}", delta="Hoạt động 3")
        
    st.write("") # Khoảng cách
    
    # Biểu đồ hoạt động (Demo)
    with st.container(border=True):
        st.subheader("📊 Biểu đồ tham gia thực tế")
        if len(df1) > 0 or len(df2) > 0 or len(df3) > 0:
            chart_data = pd.DataFrame({
                "Hoạt động": ["Quan điểm", "Quy trình", "Thu hoạch"],
                "Số lượng": [len(df1), len(df2), len(df3)]
            })
            # Vẽ biểu đồ cột màu xanh chuyên nghiệp
            fig = px.bar(chart_data, x="Hoạt động", y="Số lượng", text_auto=True, 
                         color_discrete_sequence=['#007bff']) 
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Chưa có dữ liệu để vẽ biểu đồ.")

# ==========================================
# TRANG 2: HOẠT ĐỘNG 1 - QUAN ĐIỂM
# ==========================================
elif "1️⃣" in menu:
    st.title("🗣️ Thảo luận: Quan điểm Cá nhân")
    st.caption("Chủ đề: Cơ hội và Thách thức của AI")
    st.markdown("---")
    
    # Chia 2 cột: Sinh viên (Trái) - Giảng viên (Phải)
    col_student, col_teacher = st.columns([1, 1], gap="large")
    
    # Cột trái: Form nhập liệu
    with col_student:
        st.subheader("✍️ Dành cho Học viên")
        with st.container(border=True): # Tạo khung viền (Card)
            with st.form("form_qd"):
                ten = st.text_input("Họ tên:")
                y_kien = st.text_area("Theo bạn, AI là cơ hội hay thách thức?")
                if st.form_submit_button("Gửi ý kiến") and ten and y_kien:
                    with open("data_tab1.csv", "a", encoding="utf-8") as f:
                        f.write(f"{ten}|{y_kien.replace(chr(10), ' ')}\n")
                    st.success("Đã gửi thành công!")

    # Cột phải: Phân tích AI
    with col_teacher:
        st.subheader("🔐 Dành cho Giảng viên")
        
        # Khu vực nhập mật khẩu gọn gàng
        with st.expander("Mở bảng phân tích", expanded=True):
            password = st.text_input("Mật khẩu:", type="password", key="pass1")
            
            if password == "T05":
                df = load_data("data_tab1.csv")
                if not df.empty:
                    st.write(f"**Số lượng bài nộp:** {len(df)}")
                    st.dataframe(df.tail(3), height=150) # Xem trước 3 dòng
                    
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        analyze_btn = st.button("✨ Phân tích Cảm xúc")
                    with col_btn2:
                        wc_btn = st.button("☁️ Vẽ Word Cloud")

                    # Xử lý nút bấm
                    if analyze_btn:
                        with st.spinner("AI đang đọc bài..."):
                            prompt = f"Phân tích cảm xúc (Tích cực/Tiêu cực) từ dữ liệu: {df.to_string()}. Trả về % và lý do chính. Định dạng Markdown đẹp."
                            st.markdown(model.generate_content(prompt).text)
                            
                    if wc_btn:
                        st.write("#### ☁️ Từ khóa nổi bật")
                        text = " ".join(df["Nội dung"].astype(str))
                        wc = WordCloud(width=800, height=400, background_color='white', colormap='Blues').generate(text)
                        fig, ax = plt.subplots()
                        ax.imshow(wc, interpolation='bilinear')
                        ax.axis("off")
                        st.pyplot(fig)
                else:
                    st.info("Chưa có dữ liệu.")
            else:
                st.info("Nhập mật khẩu để xem phân tích.")

# ==========================================
# TRANG 3: HOẠT ĐỘNG 2 - QUY TRÌNH
# ==========================================
elif "2️⃣" in menu:
    st.title("🧩 Bài tập: Sắp xếp Quy trình")
    st.markdown("---")
    
    manh_ghep = ["1. Thu thập", "2. Đánh giá", "3. Lên phương án", "4. Thực hiện", "5. Rút kinh nghiệm"]
    
    col_game, col_result = st.columns([1, 1], gap="large")

    with col_game:
        st.subheader("🎮 Phần thi Học viên")
        with st.container(border=True):
            with st.form("form_game"):
                ten = st.text_input("Họ tên:", key="name2")
                st.write("Sắp xếp các bước sau:")
                tra_loi = st.multiselect("Chọn thứ tự đúng:", options=manh_ghep)
                if st.form_submit_button("Nộp bài") and ten:
                    ket_qua = " -> ".join(tra_loi)
                    with open("data_tab2.csv", "a", encoding="utf-8") as f:
                        f.write(f"{ten}|{ket_qua}\n")
                    st.success("Đã nộp!")
    
    with col_result:
        st.subheader("🔐 Phân tích Lỗi sai")
        password = st.text_input("Mật khẩu GV:", type="password", key="pass2")
        if password == "T05":
            df = load_data("data_tab2.csv")
            if not df.empty:
                st.dataframe(df.tail(5))
                if st.button("🔍 Tìm lỗi sai phổ biến"):
                    prompt = f"Đáp án đúng là 1->2->3->4->5. Phân tích lỗi sai từ: {df.to_string()}"
                    st.markdown(model.generate_content(prompt).text)

# ==========================================
# TRANG 4: TỔNG KẾT
# ==========================================
elif "3️⃣" in menu:
    st.title("📝 Tổng kết & Thu hoạch")
    st.markdown("---")
    
    with st.container(border=True):
        col_input, col_image = st.columns([2, 1])
        with col_input:
            with st.form("form_th"):
                ten = st.text_input("Họ tên:", key="name3")
                bai_hoc = st.text_area("Bài học tâm đắc nhất:", height=150)
                if st.form_submit_button("Gửi bài thu hoạch") and ten:
                    with open("data_tab3.csv", "a", encoding="utf-8") as f:
                        f.write(f"{ten}|{bai_hoc.replace(chr(10), ' ')}\n")
                    st.success("Đã ghi nhận!")
        with col_image:
            st.info("Hãy viết ngắn gọn, súc tích những gì bạn tâm đắc nhất.")

    st.divider()
    
    with st.expander("🔐 Tổng hợp Kiến thức (Giảng viên)", expanded=False):
        password = st.text_input("Mật khẩu GV:", type="password", key="pass3")
        chu_de = st.text_input("Chủ đề bài giảng:")
        if password == "T05" and st.button("🚀 Tổng hợp 3 điểm cốt lõi"):
            df = load_data("data_tab3.csv")
            if not df.empty:
                prompt = f"Chủ đề: {chu_de}. Dữ liệu: {df.to_string()}. Tổng hợp 3 vấn đề cốt lõi."
                st.markdown(model.generate_content(prompt).text)
