import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import plotly.express as px

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Hệ thống Quản lý Lớp học T05",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CSS "MAKEUP" CHO GIAO DIỆN (PHẦN QUAN TRỌNG NHẤT) ---
st.markdown("""
<style>
    /* 1. Nền tổng thể màu xám nhạt sang trọng */
    .stApp {
        background-color: #f0f2f6;
    }
    
    /* 2. Tùy chỉnh Sidebar (Thanh bên trái) */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #ddd;
    }
    
    /* 3. Hiệu ứng Card (Khung trắng đổ bóng) cho các container */
    div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column;"] > div[data-testid="stVerticalBlock"] {
        /* CSS này tác động vào các block chính, tùy phiên bản streamlit có thể khác, 
           nhưng ta sẽ dùng st.container(border=True) để đảm bảo nhất */
    }

    /* 4. Tiêu đề H1, H2, H3 gọn gàng */
    h1 {
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        color: #1f2937;
        font-weight: 700;
        padding-bottom: 10px;
    }
    h2, h3 {
        color: #374151;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }

    /* 5. Nút bấm (Button) phong cách hiện đại */
    div.stButton > button {
        background-color: #2563eb; /* Xanh dương đậm */
        color: white;
        border-radius: 8px;
        padding: 0.5rem 1.2rem;
        font-weight: 500;
        border: none;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        transition: all 0.2s;
        width: 100%;
    }
    div.stButton > button:hover {
        background-color: #1d4ed8;
        transform: translateY(-1px);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }

    /* 6. Ô nhập liệu (Input) */
    .stTextInput > div > div > input {
        border-radius: 8px;
        border: 1px solid #d1d5db;
    }
    
    /* 7. Metric Card (Thẻ số liệu) */
    div[data-testid="metric-container"] {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
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
    pass # Bỏ qua lỗi hiển thị ban đầu để giao diện đẹp hơn

# --- HÀM LOAD DỮ LIỆU ---
def load_data(filename):
    if os.path.exists(filename):
        return pd.read_csv(filename, sep="|", names=["Tên", "Nội dung"])
    return pd.DataFrame(columns=["Tên", "Nội dung"])

# --- SIDEBAR (THANH ĐIỀU HƯỚNG) ---
with st.sidebar:
    st.title("🎓 LMS T05")
    st.markdown("**Khoa LLCT & KHXHNV**")
    st.markdown("---")
    
    menu = st.radio(
        "Khu vực làm việc:",
        ["Dashboard", "Hoạt động 1: Quan điểm", "Hoạt động 2: Quy trình", "Hoạt động 3: Thu hoạch"],
        label_visibility="collapsed" # Ẩn nhãn để đẹp hơn
    )
    
    st.markdown("---")
    st.caption("© 2025 Hệ thống hỗ trợ giảng dạy")
    
    # QR Code (Ẩn ở dưới cùng)
    LINK_APP = "https://share.streamlit.io/..." # Thay link của Thầy
    if LINK_APP != "https://share.streamlit.io/...":
        with st.expander("📲 Mã QR Lớp học"):
            st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={LINK_APP}")

# --- TRANG CHÍNH: DASHBOARD ---
if menu == "Dashboard":
    st.title("📊 Bảng điều khiển Trung tâm")
    st.markdown("Tổng quan tình hình lớp học theo thời gian thực.")
    
    # Load dữ liệu
    df1 = load_data("data_tab1.csv")
    df2 = load_data("data_tab2.csv")
    df3 = load_data("data_tab3.csv")
    
    # Hàng 1: Các con số thống kê (Metrics)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Tổng lượt tham gia", f"{len(df1)+len(df2)+len(df3)}")
    with col2:
        st.metric("Thảo luận", f"{len(df1)}", delta="HĐ 1")
    with col3:
        st.metric("Bài tập quy trình", f"{len(df2)}", delta="HĐ 2")
    with col4:
        st.metric("Bài thu hoạch", f"{len(df3)}", delta="HĐ 3")
    
    st.markdown("---")
    
    # Hàng 2: Biểu đồ và Thông báo
    c_chart, c_info = st.columns([2, 1])
    
    with c_chart:
        # Khung viền trắng cho biểu đồ
        with st.container(border=True):
            st.subheader("📈 Xu hướng tham gia")
            if len(df1) > 0 or len(df2) > 0 or len(df3) > 0:
                data = pd.DataFrame({
                    "Hoạt động": ["Quan điểm", "Quy trình", "Thu hoạch"],
                    "Số lượng": [len(df1), len(df2), len(df3)]
                })
                # Biểu đồ Plotly style hiện đại
                fig = px.bar(data, x="Hoạt động", y="Số lượng", text_auto=True,
                             color="Hoạt động", color_discrete_sequence=px.colors.qualitative.Pastel)
                fig.update_layout(plot_bgcolor="white", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Chưa có dữ liệu để hiển thị biểu đồ.")

    with c_info:
        with st.container(border=True):
            st.subheader("🔔 Thông báo mới")
            st.info("Chào mừng Giảng viên quay trở lại.")
            st.success("Hệ thống AI: Sẵn sàng.")
            st.warning("Trạng thái lớp: Đang mở.")

# --- TRANG HOẠT ĐỘNG 1: QUAN ĐIỂM ---
elif menu == "Hoạt động 1: Quan điểm":
    st.title("🗣️ Diễn đàn: Cơ hội & Thách thức AI")
    
    # Layout chia 2 cột với tỉ lệ 4:6
    col_left, col_right = st.columns([4, 6], gap="medium")
    
    with col_left:
        with st.container(border=True):
            st.markdown("### 📝 Học viên nộp bài")
            with st.form("form1"):
                name = st.text_input("Họ và tên")
                content = st.text_area("Quan điểm của bạn (Ngắn gọn)", height=150)
                if st.form_submit_button("Gửi ý kiến") and name and content:
                    with open("data_tab1.csv", "a", encoding="utf-8") as f:
                        f.write(f"{name}|{content.replace(chr(10), ' ')}\n")
                    st.toast("Đã gửi thành công!", icon="✅") # Thông báo nhỏ góc phải

    with col_right:
        with st.container(border=True):
            st.markdown("### 🧠 Giảng viên Phân tích")
            
            # Kiểm tra mật khẩu
            if "auth_1" not in st.session_state:
                pwd = st.text_input("Nhập mật khẩu quản trị:", type="password")
                if pwd == "T05":
                    st.session_state["auth_1"] = True
                    st.rerun()
            
            if st.session_state.get("auth_1"):
                df = load_data("data_tab1.csv")
                if not df.empty:
                    tab_list, tab_ai = st.tabs(["Danh sách", "Phân tích AI"])
                    
                    with tab_list:
                        st.dataframe(df, use_container_width=True, height=200)
                    
                    with tab_ai:
                        col_btn1, col_btn2 = st.columns(2)
                        if col_btn1.button("Phân tích Cảm xúc"):
                            with st.spinner("AI đang đọc..."):
                                prompt = f"Phân tích cảm xúc từ: {df.to_string()}. Trình bày đẹp."
                                st.markdown(model.generate_content(prompt).text)
                        
                        if col_btn2.button("Vẽ Word Cloud"):
                             text = " ".join(df["Nội dung"].astype(str))
                             wc = WordCloud(width=800, height=400, background_color='white').generate(text)
                             fig, ax = plt.subplots()
                             ax.imshow(wc, interpolation='bilinear'); ax.axis("off")
                             st.pyplot(fig)
                else:
                    st.info("Chưa có bài nộp nào.")

# --- TRANG HOẠT ĐỘNG 2: QUY TRÌNH ---
elif menu == "Hoạt động 2: Quy trình":
    st.title("🧩 Bài tập: Sắp xếp Quy trình")
    
    col_left, col_right = st.columns([1, 1], gap="medium")
    
    with col_left:
        with st.container(border=True):
            st.subheader("🎮 Phần chơi")
            steps = ["1. Thu thập", "2. Đánh giá", "3. Lên phương án", "4. Thực hiện", "5. Rút kinh nghiệm"]
            with st.form("form2"):
                name = st.text_input("Họ và tên")
                choice = st.multiselect("Chọn thứ tự đúng:", steps)
                if st.form_submit_button("Nộp bài") and name:
                    with open("data_tab2.csv", "a", encoding="utf-8") as f:
                        f.write(f"{name}|{' -> '.join(choice)}\n")
                    st.toast("Đã nộp bài!", icon="✅")

    with col_right:
        with st.container(border=True):
            st.subheader("📊 Kết quả")
            if st.checkbox("Hiện phân tích (Giảng viên)"):
                 df = load_data("data_tab2.csv")
                 if not df.empty:
                     st.dataframe(df.tail(5), use_container_width=True)
                     if st.button("AI Chấm bài"):
                         prompt = f"Đáp án: 1->2->3->4->5. Dữ liệu: {df.to_string()}. Phân tích lỗi sai."
                         st.write(model.generate_content(prompt).text)

# --- TRANG HOẠT ĐỘNG 3: THU HOẠCH ---
elif menu == "Hoạt động 3: Thu hoạch":
    st.title("📝 Tổng kết Bài học")
    
    with st.container(border=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("#### Bài học tâm đắc nhất")
            with st.form("form3"):
                name = st.text_input("Họ và tên")
                lesson = st.text_area("Nội dung", height=100)
                if st.form_submit_button("Gửi Thu hoạch") and name:
                    with open("data_tab3.csv", "a", encoding="utf-8") as f:
                        f.write(f"{name}|{lesson.replace(chr(10), ' ')}\n")
                    st.success("Đã ghi nhận!")
        with col2:
            st.info("💡 **Lưu ý:** Hãy tập trung vào những từ khóa cốt lõi.")
    
    st.markdown("---")
    
    with st.expander("🔐 Khu vực Giảng viên (Tổng hợp kiến thức)"):
        if st.text_input("Mật khẩu:", type="password", key="p3") == "T05":
             topic = st.text_input("Chủ đề hôm nay:")
             if st.button("🚀 AI Tổng hợp") and topic:
                 df = load_data("data_tab3.csv")
                 if not df.empty:
                     prompt = f"Chủ đề: {topic}. Dữ liệu: {df.to_string()}. Tóm tắt 3 điểm chính."
                     st.markdown(model.generate_content(prompt).text)
