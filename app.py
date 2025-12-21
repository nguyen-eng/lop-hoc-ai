import streamlit as st
import google.generativeai as genai
import pandas as pd
import os

# 1. Cấu hình trang
st.set_page_config(page_title="Thu hoạch bài học - T05", page_icon="📝")

# 2. Kết nối AI (Lấy chìa khóa từ két sắt bí mật của Streamlit)
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except:
    st.error("Chưa cấu hình API Key. Hãy báo cho Giảng viên.")

# 3. Tiêu đề
st.title("📝 Thu hoạch nhanh sau bài học")
st.caption("Dành cho học viên lớp T05 - Khoa LLCT&KHXHNV")

# 4. Giao diện Học viên
with st.form("form_hoc_vien"):
    st.write("### Phần dành cho Học viên")
    ten = st.text_input("Họ và tên:")
    cau_tra_loi = st.text_area("Điều quan trọng nhất bạn rút ra được hôm nay là gì?")
    submit = st.form_submit_button("Gửi bài")

    if submit:
        if not ten or not cau_tra_loi:
            st.warning("Vui lòng nhập đủ Tên và Nội dung.")
        else:
            # Lưu tạm vào file CSV
            with open("data.csv", "a", encoding="utf-8") as f:
                # Xử lý xuống dòng để không lỗi file
                clean_loi = cau_tra_loi.replace("\n", " ")
                f.write(f"{ten}|{clean_loi}\n")
            st.success(f"Cảm ơn {ten}, đã ghi nhận ý kiến!")

# 5. Giao diện Giảng viên (Phân tích)
st.divider()
with st.expander("🔐 Khu vực Giảng viên (Phân tích dữ liệu)"):
    password = st.text_input("Nhập mật khẩu quản trị", type="password")
    
    if password == "T05": # Mật khẩu mặc định là T05
        if st.button("🚀 Bắt đầu phân tích ngay"):
            try:
                # Đọc dữ liệu từ file
                if not os.path.exists("data.csv"):
                    st.info("Chưa có dữ liệu nào được gửi.")
                else:
                    df = pd.read_csv("data.csv", sep="|", names=["Học viên", "Ý kiến"])
                    
                    # Hiển thị bảng dữ liệu thô
                    st.write("### Dữ liệu thu được:")
                    st.dataframe(df)
                    
                    # Gửi cho AI xử lý
                    with st.spinner('Đang đọc suy nghĩ của cả lớp...'):
                        data_text = df.to_string()
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        prompt = f"""
                        Đóng vai trợ lý giáo dục. Phân tích danh sách ý kiến học viên sau:
                        {data_text}
                        
                        Nhiệm vụ:
                        1. Tổng hợp thành 3 vấn đề/luận điểm cốt lõi nhất mà lớp học đã nắm bắt được.
                        2. Dưới mỗi luận điểm, liệt kê tên các học viên đã đóng góp ý đó.
                        3. Nhận xét ngắn gọn về chất lượng hiểu bài chung của lớp.
                        
                        Trình bày định dạng Markdown đẹp mắt, dùng tiếng Việt.
                        """
                        response = model.generate_content(prompt)
                        
                    st.success("Đã phân tích xong!")
                    st.markdown(response.text)
            except Exception as e:
                st.error(f"Có lỗi xảy ra: {e}")
