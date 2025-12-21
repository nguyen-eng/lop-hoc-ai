import streamlit as st
import google.generativeai as genai
import pandas as pd
import os

# 1. Cấu hình trang
st.set_page_config(page_title="Thu hoạch bài học - T05", page_icon="📝")

# 2. Kết nối AI
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    # Sử dụng model 2.5 flash như đã chốt
    model = genai.GenerativeModel('gemini-2.5-flash')
except:
    st.error("Lỗi: Chưa cấu hình API Key.")

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
            with open("data.csv", "a", encoding="utf-8") as f:
                clean_loi = cau_tra_loi.replace("\n", " ")
                f.write(f"{ten}|{clean_loi}\n")
            st.success(f"Cảm ơn {ten}, đã ghi nhận ý kiến!")

# 5. Giao diện Giảng viên (Đã nâng cấp)
st.divider()
with st.expander("🔐 Khu vực Giảng viên (Phân tích dữ liệu)"):
    password = st.text_input("Nhập mật khẩu quản trị", type="password")
    
    if password == "T05":
        st.info("👋 Chào Giảng viên, hãy nhập chủ đề để AI phân tích sát thực tế hơn.")
        
        # --- PHẦN MỚI THÊM VÀO ---
        chu_de = st.text_input("Chủ đề bài học hôm nay là gì?", 
                              placeholder="Ví dụ: Quan điểm toàn diện trong Triết học Mác - Lênin")
        # -------------------------

        if st.button("🚀 Bắt đầu phân tích ngay"):
            if not chu_de:
                st.error("⚠️ Vui lòng nhập 'Chủ đề bài học' trước khi phân tích!")
            elif not os.path.exists("data.csv"):
                st.info("Chưa có dữ liệu học viên nào được gửi.")
            else:
                try:
                    # Đọc dữ liệu
                    df = pd.read_csv("data.csv", sep="|", names=["Học viên", "Ý kiến"])
                    st.write("### Dữ liệu thu được:")
                    st.dataframe(df)
                    
                    # Gửi cho AI xử lý với Prompt mới
                    with st.spinner(f'Đang đối chiếu ý kiến với chủ đề "{chu_de}"...'):
                        data_text = df.to_string()
                        
                        prompt = f"""
                        Đóng vai trợ lý giảng dạy tại trường Đại học Cảnh sát nhân dân (T05).
                        
                        THÔNG TIN ĐẦU VÀO:
                        1. Chủ đề bài giảng hôm nay: "{chu_de}"
                        2. Danh sách phản hồi của học viên:
                        {data_text}
                        
                        NHIỆM VỤ:
                        Hãy phân tích danh sách trên dựa vào Chủ đề bài giảng.
                        1. Tổng hợp 3 vấn đề/khía cạnh chính mà lớp học tâm đắc nhất (kèm tên học viên).
                        2. Đánh giá chất lượng: Các ý kiến này có bám sát chủ đề "{chu_de}" không? Có ai hiểu sai lệch không?
                        3. Đề xuất: Giảng viên cần nhấn mạnh lại điều gì trong buổi sau?
                        
                        Trình bày định dạng Markdown rõ ràng, ngôn phong sư phạm, nghiêm túc.
                        """
                        
                        response = model.generate_content(prompt)
                        
                    st.success("Đã phân tích xong!")
                    st.markdown(response.text)
                    
                except Exception as e:
                    st.error(f"Có lỗi xảy ra: {e}")
