import streamlit as st
import google.generativeai as genai
import pandas as pd
import os

# 1. Cấu hình trang
st.set_page_config(page_title="Thu hoạch bài học - T05", page_icon="📝")

# --- PHẦN CẤU HÌNH ĐƯỜNG LINK CỦA THẦY (SỬA Ở ĐÂY) ---
# Thầy hãy dán đường link trang web của Thầy vào giữa hai dấu ngoặc kép dưới đây
LINK_APP_CUA_THAY = "https://lop-hoc-ai-6xgnjmvjouqtgmblfrernh.streamlit.app/" 
# Ví dụ: "https://lop-hoc-ai.streamlit.app"
# -----------------------------------------------------

# 2. Kết nối AI
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
except:
    st.error("Lỗi: Chưa cấu hình API Key.")

# 3. Giao diện Tiêu đề & QR Code (MỚI)
# Chia làm 2 cột: Cột 1 nhỏ (chứa QR), Cột 2 to (chứa Tiêu đề)
col1, col2 = st.columns([1, 4]) 

with col1:
    # Tự động tạo mã QR từ đường link
    if LINK_APP_CUA_THAY != "https://share.streamlit.io/...":
        qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={LINK_APP_CUA_THAY}"
        st.image(qr_url, caption="Quét để vào lớp", width=120)
    else:
        st.warning("Chưa nhập Link")

with col2:
    st.title("📝 Thu hoạch nhanh")
    st.caption("Khoa LLCT&KHXHNV - T05")
    st.info("Học viên quét mã QR bên cạnh để nộp bài nhanh.")

# 4. Giao diện Học viên
st.divider()
with st.form("form_hoc_vien"):
    st.write("### ✍️ Phần dành cho Học viên")
    ten = st.text_input("Họ và tên:")
    cau_tra_loi = st.text_area("Điều quan trọng nhất bạn rút ra được hôm nay là gì?")
    submit = st.form_submit_button("Gửi bài")

    if submit:
        if not ten or not cau_tra_loi:
            st.warning("Vui lòng nhập đủ Tên và Nội dung.")
        else:
            with open("data.csv", "a", encoding="utf-8") as f:
                clean_loi = cau_tra_loi.replace("\n", " ")
                f.write(f"{ten}|{clean_loi}\n")
            st.success(f"Cảm ơn {ten}, đã ghi nhận ý kiến!")

# 5. Giao diện Giảng viên (Có mật khẩu & Nhập chủ đề)
st.divider()
with st.expander("🔐 Khu vực Giảng viên (Phân tích dữ liệu)"):
    password = st.text_input("Nhập mật khẩu quản trị", type="password")
    
    if password == "T05":
        st.success("Đã đăng nhập quyền Giảng viên.")
        
        # Nhập chủ đề để AI đối chiếu
        chu_de = st.text_input("Chủ đề bài học hôm nay là gì?", 
                              placeholder="Ví dụ: Quan điểm toàn diện...")
        
        if st.button("🚀 Bắt đầu phân tích ngay"):
            if not chu_de:
                st.error("⚠️ Thầy chưa nhập 'Chủ đề bài học'.")
            elif not os.path.exists("data.csv"):
                st.info("Chưa có dữ liệu học viên nào.")
            else:
                try:
                    df = pd.read_csv("data.csv", sep="|", names=["Học viên", "Ý kiến"])
                    st.write("### Dữ liệu thô:")
                    st.dataframe(df)
                    
                    with st.spinner(f'Đang phân tích dựa trên chủ đề "{chu_de}"...'):
                        data_text = df.to_string()
                        prompt = f"""
                        Đóng vai trợ lý giảng dạy tại trường T05.
                        THÔNG TIN:
                        - Chủ đề: "{chu_de}"
                        - Dữ liệu: {data_text}
                        
                        YÊU CẦU:
                        1. Tổng hợp 3 vấn đề cốt lõi lớp đã hiểu (kèm tên).
                        2. Đánh giá mức độ hiểu bài so với chủ đề "{chu_de}".
                        3. Đề xuất giảng viên cần lưu ý gì.
                        Dùng định dạng Markdown.
                        """
                        response = model.generate_content(prompt)
                        
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"Lỗi: {e}")
