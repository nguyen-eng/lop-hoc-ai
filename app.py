import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import plotly.express as px
import plotly.graph_objects as go

# --- 1. CẤU HÌNH TRANG (Full màn hình & Title) ---
st.set_page_config(
    page_title="Hệ thống Quản lý Đào tạo T05",
    page_icon="👮‍♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CSS "MAKEUP" CHUYÊN NGHIỆP (STYLE GUIDE CAND) ---
st.markdown("""
<style>
    /* NHÚNG FONT CHỮ HIỆN ĐẠI */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* TÙY BIẾN THANH SIDEBAR (MÀU XANH ĐẬM NGÀNH) */
    [data-testid="stSidebar"] {
        background-color: #111827; /* Màu đen xanh đậm */
        color: white;
    }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {
        color: #e5e7eb; /* Chữ xám trắng */
    }
    
    /* NỀN TỔNG THỂ */
    .stApp {
        background-color: #f3f4f6; /* Xám rất nhạt */
    }

    /* TIÊU ĐỀ TRANG */
    h1, h2, h3 {
        color: #1f2937;
        font-weight: 700;
    }
    
    /* CARD (KHUNG CHỨA NỘI DUNG) - GIỐNG GRADESCOPE */
    div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column;"] > div[data-testid="stVerticalBlock"] {
        background-color: white;
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }

    /* NÚT BẤM (BUTTON) - MÀU XANH CÔNG AN */
    div.stButton > button {
        background-color: #047857; /* Xanh lá đậm */
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        width: 100%;
        transition: all 0.2s;
    }
    div.stButton > button:hover {
        background-color: #065f46;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }

    /* INPUT FIELD */
    .stTextInput input, .stTextArea textarea {
        background-color: #f9fafb;
        border: 1px solid #d1d5db;
        border-radius: 6px;
    }

    /* LOGO BO TRÒN */
    .profile-img {
        width: 80px;
        height: 80px;
        border-radius: 50%;
        border: 2px solid #fbbf24; /* Viền vàng */
        margin-bottom: 10px;
        display: block;
        margin-left: auto;
        margin-right: auto;
    }
</style>
""", unsafe_allow_html=True)

# --- KẾT NỐI AI ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
except:
    pass

# --- HÀM LOAD DỮ LIỆU ---
def load_data(filename):
    if os.path.exists(filename):
        return pd.read_csv(filename, sep="|", names=["Tên", "Nội dung"])
    return pd.DataFrame(columns=["Tên", "Nội dung"])

# --- SIDEBAR: TRUNG TÂM ĐIỀU KHIỂN ---
with st.sidebar:
    # Logo Ngành (Link tượng trưng, Thầy có thể thay link ảnh T05 thật)
    st.markdown("""
        <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/Cong_an_hieu_Viet_Nam.svg/1200px-Cong_an_hieu_Viet_Nam.svg.png" class="profile-img">
        <div style="text-align: center; margin-bottom: 20px;">
            <h3 style="color: #fbbf24; margin:0;">T05 - PPU</h3>
            <p style="font-size: 12px; opacity: 0.8;">ĐẠI HỌC CẢNH SÁT NHÂN DÂN</p>
        </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    menu = st.radio(
        "ĐIỀU HƯỚNG",
        ["📊 Tổng quan (Dashboard)", "🗣️ Diễn đàn Quan điểm", "🧩 Bài tập Quy trình", "📝 Tổng kết Thu hoạch"],
        label_visibility="collapsed"
    )
    
    st.markdown("---")
    st.info("Hệ thống: **Online** 🟢")
    
    # QR Code
    LINK_APP = "https://share.streamlit.io/..." # THAY LINK CỦA THẦY VÀO ĐÂY
    if LINK_APP != "https://share.streamlit.io/...":
        with st.expander("📲 Mã QR Lớp học"):
            st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={LINK_APP}")

# --- TRANG 1: DASHBOARD (TỔNG QUAN) ---
if "Tổng quan" in menu:
    st.title("📊 Trung tâm Chỉ huy Lớp học")
    st.markdown("Báo cáo tình hình học tập và tương tác thời gian thực.")
    st.markdown("---")
    
    df1 = load_data("data_tab1.csv")
    df2 = load_data("data_tab2.csv")
    df3 = load_data("data_tab3.csv")
    
    # Hàng 1: Thẻ số liệu (Metrics)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Tổng sỹ số", "85", delta="Đang online") # Giả lập
    with col2:
        st.metric("Ý kiến tham gia", f"{len(df1)}", delta="HĐ 1")
    with col3:
        st.metric("Bài tập đã nộp", f"{len(df2)}", delta="HĐ 2")
    with col4:
        st.metric("Bài thu hoạch", f"{len(df3)}", delta="HĐ 3")
        
    st.markdown("---")
    
    # Hàng 2: Biểu đồ
    c_left, c_right = st.columns([2, 1])
    
    with c_left:
        with st.container(border=True):
            st.subheader("Tiến độ tham gia các hoạt động")
            if len(df1) > 0 or len(df2) > 0 or len(df3) > 0:
                data = pd.DataFrame({
                    "Hoạt động": ["Quan điểm", "Quy trình", "Thu hoạch"],
                    "Số lượng": [len(df1), len(df2), len(df3)]
                })
                # Biểu đồ Plotly với màu sắc ngành (Xanh rêu, Vàng, Đỏ)
                fig = px.bar(data, x="Hoạt động", y="Số lượng", text_auto=True,
                             color="Hoạt động", 
                             color_discrete_sequence=['#047857', '#d97706', '#b91c1c']) 
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Chưa có dữ liệu để vẽ biểu đồ.")
                
    with c_right:
        with st.container(border=True):
            st.subheader("Thông báo nhanh")
            st.success("✅ Hệ thống AI đang hoạt động tốt.")
            st.warning("⚠️ Nhắc nhở: Lớp nộp bài HĐ2 trước 10:00.")
            st.info("ℹ️ Chuyên đề hôm nay: Chuyển đổi số trong CAND.")

# --- TRANG 2: QUAN ĐIỂM (DIỄN ĐÀN) ---
elif "Diễn đàn" in menu:
    st.title("🗣️ Diễn đàn thảo luận")
    st.caption("Chủ đề: Cơ hội và Thách thức của Trí tuệ nhân tạo (AI) đối với An ninh trật tự.")
    st.markdown("---")
    
    col_sv, col_gv = st.columns([1, 1], gap="medium")
    
    # Cột Học viên
    with col_sv:
        st.subheader("Khu vực Học viên")
        with st.container(border=True):
            with st.form("f1"):
                name = st.text_input("Họ và tên học viên")
                text = st.text_area("Quan điểm của đồng chí (Ngắn gọn)", height=150)
                if st.form_submit_button("Gửi ý kiến") and name and text:
                    with open("data_tab1.csv", "a", encoding="utf-8") as f:
                        f.write(f"{name}|{text.replace(chr(10), ' ')}\n")
                    st.toast("Đã ghi nhận ý kiến!", icon="✅")

    # Cột Giảng viên
    with col_gv:
        st.subheader("Khu vực Giảng viên")
        with st.container(border=True):
            if "auth1" not in st.session_state:
                pwd = st.text_input("Mật khẩu quản trị:", type="password")
                if pwd == "T05": st.session_state["auth1"] = True; st.rerun()
            
            if st.session_state.get("auth1"):
                df = load_data("data_tab1.csv")
                if not df.empty:
                    tab_a, tab_b = st.tabs(["Danh sách", "Phân tích chuyên sâu"])
                    with tab_a:
                        st.dataframe(df, height=200, use_container_width=True)
                    with tab_b:
                        if st.button("✨ Phân tích Tích cực/Tiêu cực"):
                            with st.spinner("AI đang xử lý..."):
                                prompt = f"Phân tích quan điểm (Tích cực/Tiêu cực) từ dữ liệu: {df.to_string()}. Trả về Markdown."
                                st.markdown(model.generate_content(prompt).text)
                        if st.button("☁️ Vẽ Word Cloud"):
                            text_wc = " ".join(df["Nội dung"].astype(str))
                            wc = WordCloud(width=800, height=400, background_color='white').generate(text_wc)
                            fig, ax = plt.subplots()
                            ax.imshow(wc, interpolation='bilinear'); ax.axis("off")
                            st.pyplot(fig)

# --- TRANG 3: QUY TRÌNH (BÀI TẬP) ---
elif "Quy trình" in menu:
    st.title("🧩 Bài tập Nghiệp vụ")
    st.caption("Yêu cầu: Sắp xếp các bước xử lý tình huống theo đúng quy trình.")
    st.markdown("---")
    
    col_left, col_right = st.columns([1, 1], gap="medium")
    
    with col_left:
        with st.container(border=True):
            st.markdown("#### 📝 Phiếu trả lời")
            steps = ["1. Tiếp nhận tin báo", "2. Báo cáo lãnh đạo", "3. Cử lực lượng xuống hiện trường", "4. Xử lý ban đầu & Bảo vệ hiện trường", "5. Lập biên bản"]
            with st.form("f2"):
                name = st.text_input("Họ và tên")
                ans = st.multiselect("Chọn thứ tự đúng:", steps)
                if st.form_submit_button("Nộp bài") and name:
                    with open("data_tab2.csv", "a", encoding="utf-8") as f:
                        f.write(f"{name}|{' -> '.join(ans)}\n")
                    st.success("Đã nộp bài thành công.")
    
    with col_right:
        with st.container(border=True):
            st.markdown("#### 🔐 Kết quả & Đánh giá")
            if st.checkbox("Hiển thị dữ liệu (Giảng viên)"):
                 df = load_data("data_tab2.csv")
                 if not df.empty:
                     st.dataframe(df.tail(10), use_container_width=True)
                     if st.button("🔍 AI Phân tích Lỗi sai"):
                         prompt = f"Đáp án đúng: 1->2->3->4->5. Dữ liệu: {df.to_string()}. Phân tích các lỗi sai phổ biến của học viên."
                         st.write(model.generate_content(prompt).text)

# --- TRANG 4: TỔNG KẾT ---
elif "Tổng kết" in menu:
    st.title("📝 Tổng kết & Thu hoạch")
    st.markdown("---")
    
    with st.container(border=True):
        col1, col2 = st.columns([2, 1])
        with col1:
            st.markdown("#### Bài học tâm đắc nhất")
            with st.form("f3"):
                name = st.text_input("Họ tên")
                val = st.text_area("Nội dung thu hoạch", height=100)
                if st.form_submit_button("Gửi Thu hoạch") and name:
                    with open("data_tab3.csv", "a", encoding="utf-8") as f:
                        f.write(f"{name}|{val.replace(chr(10), ' ')}\n")
                    st.success("Đã ghi nhận.")
        with col2:
            st.info("💡 **Lưu ý:** Nêu ngắn gọn 3 điểm cốt lõi đồng chí rút ra được sau bài học hôm nay.")

    st.markdown("---")
    with st.expander("🔐 Giảng viên: Tổng hợp kiến thức toàn lớp"):
        if st.text_input("Mật khẩu:", type="password", key="p3") == "T05":
             topic = st.text_input("Chủ đề bài giảng:")
             if st.button("🚀 Tổng hợp Kiến thức") and topic:
                 df = load_data("data_tab3.csv")
                 if not df.empty:
                     prompt = f"Chủ đề: {topic}. Dữ liệu: {df.to_string()}. Tóm tắt 3 điểm chính cả lớp đã học được."
                     st.markdown(model.generate_content(prompt).text)
