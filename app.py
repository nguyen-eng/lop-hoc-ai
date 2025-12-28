import streamlit as st
import google.generativeai as genai
import pandas as pd
import os

# --- 1. CẤU HÌNH & KẾT NỐI ---
st.set_page_config(page_title="Lớp học Thông minh T05", page_icon="🏫", layout="wide")

# Link để tạo QR (Thầy thay link của thầy vào đây)
LINK_APP = "https://lop-hoc-ai-6xgnjmvjouqtgmblfrernh.streamlit.app/" 

try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash') # Dùng bản 2.5 cho thông minh
except:
    st.error("⚠️ Chưa cấu hình API Key!")

# --- 2. GIAO DIỆN CHUNG (Header & QR) ---
col_logo, col_header = st.columns([1, 5])
with col_logo:
    if LINK_APP != "https://lop-hoc-ai-6xgnjmvjouqtgmblfrernh.streamlit.app/":
        st.image(f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={LINK_APP}", width=100)
with col_header:
    st.title("🏫 Hệ thống Tương tác Lớp học T05")
    st.caption("Giảng viên: Thầy Nguyên - Khoa LLCT&KHXHNV")

# --- 3. TẠO CÁC TAB CHỨC NĂNG ---
tab1, tab2, tab3 = st.tabs(["1️⃣ KHỞI ĐỘNG (Quan điểm)", "2️⃣ TRÒ CHƠI (Sắp xếp)", "3️⃣ TỔNG KẾT (Thu hoạch)"])

# ==========================================
# TAB 1: KHỞI ĐỘNG - PHÂN TÍCH QUAN ĐIỂM
# ==========================================
with tab1:
    st.header("🗣️ Hoạt động 1: Nêu quan điểm")
    st.info("Câu hỏi: Theo bạn, AI là cơ hội hay thách thức đối với công tác An ninh trật tự?")
    
    with st.form("form_quan_diem"):
        qd_ten = st.text_input("Tên của bạn (Tab 1):")
        qd_y_kien = st.text_area("Nhập ý kiến của bạn ngắn gọn:")
        qd_submit = st.form_submit_button("Gửi quan điểm")
        
        if qd_submit and qd_ten and qd_y_kien:
            with open("data_tab1.csv", "a", encoding="utf-8") as f:
                f.write(f"{qd_ten}|{qd_y_kien.replace('\n', ' ')}\n")
            st.success("Đã ghi nhận!")

    # Phần Giảng viên Tab 1
    with st.expander("🔐 Phân tích Quan điểm (Giảng viên)"):
        if st.text_input("Mật khẩu Tab 1", type="password") == "T05":
            if st.button("Phân tích Tích cực/Tiêu cực"):
                if os.path.exists("data_tab1.csv"):
                    df1 = pd.read_csv("data_tab1.csv", sep="|", names=["Tên", "Ý kiến"])
                    st.dataframe(df1.tail(5)) # Hiện 5 người mới nhất
                    
                    prompt1 = f"""
                    Phân tích danh sách ý kiến sau: {df1.to_string()}
                    Nhiệm vụ:
                    1. Đếm số lượng ý kiến Tích cực (Ủng hộ/Cơ hội) và Tiêu cực (Lo ngại/Thách thức). Tính % mỗi loại.
                    2. Tóm tắt 1 lý do chính của phe Tích cực và 1 lý do chính của phe Tiêu cực.
                    3. Liệt kê tên những bạn có quan điểm sắc sảo nhất.
                    """
                    st.write(model.generate_content(prompt1).text)
                else:
                    st.warning("Chưa có dữ liệu.")

# ==========================================
# TAB 2: TRÒ CHƠI - SẮP XẾP QUY TRÌNH
# ==========================================
with tab2:
    st.header("🧩 Hoạt động 2: Ghép nối quy trình")
    st.write("Hãy sắp xếp các bước sau theo đúng trình tự Logic:")
    
    # Định nghĩa các mảnh ghép (Thầy sửa nội dung ở đây)
    manh_ghep = ["1. Thu thập thông tin", "2. Đánh giá tình hình", "3. Lên phương án", "4. Triển khai thực hiện", "5. Rút kinh nghiệm"]
    # Đáp án đúng (để máy chấm điểm sơ bộ nếu cần, ở đây ta để AI phân tích)
    
    with st.form("form_game"):
        game_ten = st.text_input("Tên của bạn (Tab 2):")
        # Widget cho phép chọn thứ tự
        game_tra_loi = st.multiselect("Chọn lần lượt từng bước từ 1 đến 5:", options=manh_ghep)
        game_submit = st.form_submit_button("Nộp bài")
        
        if game_submit:
            if len(game_tra_loi) < len(manh_ghep):
                st.warning("Bạn chưa chọn đủ các bước!")
            else:
                # Chuyển list thành chuỗi để lưu
                ket_qua_game = " -> ".join(game_tra_loi)
                with open("data_tab2.csv", "a", encoding="utf-8") as f:
                    f.write(f"{game_ten}|{ket_qua_game}\n")
                st.success("Đã nộp bài!")

    # Phần Giảng viên Tab 2
    with st.expander("🔐 Phân tích Lỗi sai (Giảng viên)"):
        if st.text_input("Mật khẩu Tab 2", type="password") == "T05":
            dap_an_dung = " -> ".join(manh_ghep) # Giả sử thứ tự trong list trên là đúng
            st.info(f"Đáp án đúng máy đang giữ: {dap_an_dung}")
            
            if st.button("Chấm điểm & Phân tích lỗi"):
                if os.path.exists("data_tab2.csv"):
                    df2 = pd.read_csv("data_tab2.csv", sep="|", names=["Tên", "Bài làm"])
                    
                    prompt2 = f"""
                    Đáp án đúng là: {dap_an_dung}
                    Danh sách bài làm của học viên:
                    {df2.to_string()}
                    
                    Nhiệm vụ:
                    1. Đếm số lượng bạn làm Đúng hoàn toàn và Sai.
                    2. Với các bạn sai, hãy chỉ ra lỗi sai phổ biến nhất (họ hay nhầm bước nào với bước nào?).
                    3. Liệt kê tên các bạn làm đúng nhanh nhất (dựa trên danh sách).
                    """
                    st.write(model.generate_content(prompt2).text)
                else:
                    st.warning("Chưa có dữ liệu.")

# ==========================================
# TAB 3: TỔNG KẾT - BÀI THU HOẠCH (Cũ)
# ==========================================
with tab3:
    st.header("📝 Hoạt động 3: Tổng kết kiến thức")
    
    with st.form("form_thu_hoach"):
        th_ten = st.text_input("Họ và tên:")
        th_y_kien = st.text_area("Điều quan trọng nhất bạn rút ra hôm nay?")
        th_submit = st.form_submit_button("Gửi bài thu hoạch")

        if th_submit and th_ten and th_y_kien:
            with open("data_tab3.csv", "a", encoding="utf-8") as f:
                f.write(f"{th_ten}|{th_y_kien.replace('\n', ' ')}\n")
            st.success("Đã ghi nhận!")

    # Phần Giảng viên Tab 3
    with st.expander("🔐 Phân tích Tổng kết (Giảng viên)"):
        pw3 = st.text_input("Mật khẩu Tab 3", type="password")
        chu_de = st.text_input("Chủ đề bài học (để AI đối chiếu):")
        
        if pw3 == "T05" and st.button("Phân tích 3 vấn đề cốt lõi"):
            if os.path.exists("data_tab3.csv"):
                df3 = pd.read_csv("data_tab3.csv", sep="|", names=["Tên", "Ý kiến"])
                prompt3 = f"""
                Chủ đề: {chu_de}
                Dữ liệu: {df3.to_string()}
                Yêu cầu:
                1. Tổng hợp 3 vấn đề cốt lõi nhất lớp đã hiểu.
                2. Đánh giá mức độ hiểu bài so với chủ đề.
                3. Đề xuất giảng viên cần lưu ý gì.
                """
                st.write(model.generate_content(prompt3).text)
            else:
                st.warning("Chưa có dữ liệu.")
