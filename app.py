import streamlit as st
import google.generativeai as genai

st.title("🛠 Công cụ khám bệnh lỗi 404")

# 1. Kiểm tra phiên bản thư viện đang chạy
import google.generativeai
st.write(f"📌 Phiên bản thư viện Google đang cài: **{google.generativeai.__version__}**")
st.info("Phiên bản chuẩn cần thiết phải là từ **0.5.0** trở lên (tốt nhất là **0.8.3**).")

# 2. Kiểm tra kết nối API
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    st.success("✅ Đã nhận được chìa khóa API Key.")
except:
    st.error("❌ Chưa nhập API Key trong Secrets.")

# 3. Quét danh sách Model khả dụng
if st.button("🔍 Quét danh sách Model"):
    try:
        st.write("Đang hỏi Google xem có những model nào...")
        models = genai.list_models()
        found_any = False
        
        st.write("### Danh sách Model tìm thấy:")
        for m in models:
            if 'generateContent' in m.supported_generation_methods:
                st.code(m.name) # In ra tên chính xác
                found_any = True
        
        if not found_any:
            st.warning("⚠️ Không tìm thấy model nào hỗ trợ viết văn bản. Có thể do API Key hoặc Lỗi vùng.")
        else:
            st.success("Kết nối tốt! Hãy copy tên model ở trên vào code.")
            
    except Exception as e:
        st.error(f"Lỗi khi kết nối Google: {e}")
