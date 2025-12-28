import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import plotly.express as px
import time

# --- 1. CẤU HÌNH HỆ THỐNG ---
st.set_page_config(
    page_title="Hệ thống Đào tạo Đa lớp T05",
    page_icon="👮‍♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CSS CHUYÊN NGHIỆP (GIỮ NGUYÊN STYLE CAND) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    
    /* Giao diện Login */
    .login-container {
        max-width: 400px;
        margin: auto;
        padding: 30px;
        background: white;
        border-radius: 10px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        text-align: center;
    }
    
    /* Sidebar & Button */
    [data-testid="stSidebar"] { background-color: #111827; color: white; }
    [data-testid="stSidebar"] p { color: #e5e7eb; }
    div.stButton > button {
        background-color: #047857; color: white; border: none;
        border-radius: 6px; padding: 0.6rem 1rem; font-weight: 600; width: 100%;
    }
    div.stButton > button:hover { background-color: #065f46; }
    
    /* Nút Reset dữ liệu (Màu đỏ) */
    .reset-btn > button {
        background-color: #dc2626 !important;
    }
    .reset-btn > button:hover {
        background-color: #b91c1c !important;
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

# --- 3. QUẢN LÝ SESSION (TRẠNG THÁI ĐĂNG NHẬP) ---
if 'is_logged_in' not in st.session_state:
    st.session_state['is_logged_in'] = False
if 'user_role' not in st.session_state:
    st.session_state['user_role'] = '' # 'student' or 'teacher'
if 'class_id' not in st.session_state:
    st.session_state['class_id'] = '' # 'lop1', 'lop2'...

# Danh sách 10 lớp
LIST_CLASSES = {f"Lớp học {i}": f"lop{i}" for i in range(1, 11)}
# Mật khẩu tương ứng: LH1, LH2...
CLASS_PASSWORDS = {f"lop{i}": f"LH{i}" for i in range(1, 11)}

# --- HÀM HỖ TRỢ FILE ---
def get_file_path(class_id, tab_num):
    """Tạo tên file riêng cho từng lớp (Ví dụ: data_lop1_tab1.csv)"""
    return f"data_{class_id}_tab{tab_num}.csv"

def load_data(class_id, tab_num):
    filename = get_file_path(class_id, tab_num)
    if os.path.exists(filename):
        return pd.read_csv(filename, sep="|", names=["Tên", "Nội dung"])
    return pd.DataFrame(columns=["Tên", "Nội dung"])

def clear_data(class_id):
    """Hàm xóa sạch dữ liệu của một lớp"""
    for i in range(1, 4):
        file = get_file_path(class_id, i)
        if os.path.exists(file):
            os.remove(file)
            
# ==========================================
# PHẦN 1: MÀN HÌNH ĐĂNG NHẬP (LOGIN SCREEN)
# ==========================================
if not st.session_state['is_logged_in']:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("""
            <div style="text-align: center;">
                <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/Cong_an_hieu_Viet_Nam.svg/1200px-Cong_an_hieu_Viet_Nam.svg.png" width="100">
                <h2 style="color: #047857; margin-top: 10px;">CỔNG ĐÀO TẠO T05</h2>
                <p>Vui lòng đăng nhập để vào lớp học</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Form đăng nhập
            chon_lop = st.selectbox("Chọn Lớp học:", list(LIST_CLASSES.keys()))
            mat_khau = st.text_input("Mật khẩu truy cập:", type="password")
            
            col_login, col_teacher = st.columns(2)
            
            # Nút Đăng nhập Học viên
            if col_login.button("Đăng nhập Học viên"):
                ma_lop = LIST_CLASSES[chon_lop] # Lấy mã 'lop1'
                mk_dung = CLASS_PASSWORDS[ma_lop] # Lấy mk 'LH1'
                
                if mat_khau == mk_dung:
                    st.session_state['is_logged_in'] = True
                    st.session_state['user_role'] = 'student'
                    st.session_state['class_id'] = ma_lop
                    st.rerun()
                else:
                    st.error("Mật khẩu sai! (Gợi ý: LH + số lớp)")
            
            # Nút Đăng nhập Giảng viên
            if col_teacher.button("Giảng viên / Admin"):
                if mat_khau == "T05": # Mật khẩu Giảng viên
                    st.session_state['is_logged_in'] = True
                    st.session_state['user_role'] = 'teacher'
                    st.session_state['class_id'] = 'admin' # Admin xem được tất cả
                    st.rerun()
                else:
                    st.error("Sai mật khẩu Giảng viên.")

# ==========================================
# PHẦN 2: GIAO DIỆN CHÍNH (SAU KHI LOGIN)
# ==========================================
else:
    # --- SIDEBAR CHUNG ---
    with st.sidebar:
        st.markdown("""
            <div style="text-align: center; margin-bottom: 20px;">
                <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/Cong_an_hieu_Viet_Nam.svg/1200px-Cong_an_hieu_Viet_Nam.svg.png" width="60">
                <h3 style="color: #fbbf24; margin:0;">T05 LMS</h3>
            </div>
        """, unsafe_allow_html=True)
        
        # Hiển thị thông tin người dùng
        if st.session_state['user_role'] == 'student':
            # Lấy tên lớp đẹp để hiển thị (VD: lop1 -> Lớp học 1)
            ten_lop_hien_thi = [k for k, v in LIST_CLASSES.items() if v == st.session_state['class_id']][0]
            st.info(f"👤 Học viên: **{ten_lop_hien_thi}**")
        else:
            st.error("⭐️ **Quyền Giảng viên**")
        
        st.divider()
        
        # Menu điều hướng
        menu_options = ["🏠 Dashboard", "1️⃣ Quan điểm", "2️⃣ Quy trình", "3️⃣ Thu hoạch"]
        if st.session_state['user_role'] == 'teacher':
             menu_options.append("⚙️ Quản trị & Reset") # Menu riêng cho GV
             
        menu = st.radio("ĐIỀU HƯỚNG:", menu_options, label_visibility="collapsed")
        
        st.divider()
        if st.button("Đăng xuất"):
            st.session_state['is_logged_in'] = False
            st.rerun()

    # XÁC ĐỊNH CLASS ID ĐỂ LÀM VIỆC
    # Nếu là SV: dùng class_id của SV. Nếu là GV: Mặc định chọn Lớp 1 hoặc cho chọn.
    active_class = st.session_state['class_id']
    
    if st.session_state['user_role'] == 'teacher' and menu != "⚙️ Quản trị & Reset":
        # Giảng viên có quyền chọn lớp để xem dữ liệu ở các Tab hoạt động
        st.markdown("### 👁️ Chế độ Xem của Giảng viên")
        chon_lop_gv = st.selectbox("Thầy muốn xem dữ liệu lớp nào?", list(LIST_CLASSES.keys()))
        active_class = LIST_CLASSES[chon_lop_gv]
        st.divider()

    # --- NỘI DUNG TỪNG TRANG ---
    
    # 1. DASHBOARD
    if "Dashboard" in menu:
        st.title(f"📊 Dashboard - {active_class.upper()}")
        df1 = load_data(active_class, 1)
        df2 = load_data(active_class, 2)
        df3 = load_data(active_class, 3)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Ý kiến", len(df1))
        col2.metric("Bài tập", len(df2))
        col3.metric("Thu hoạch", len(df3))
        
        if len(df1)>0 or len(df2)>0 or len(df3)>0:
            data = pd.DataFrame({"HĐ": ["HĐ1", "HĐ2", "HĐ3"], "SL": [len(df1), len(df2), len(df3)]})
            fig = px.bar(data, x="HĐ", y="SL", color="HĐ", color_discrete_sequence=['#047857', '#d97706', '#b91c1c'])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Lớp này chưa có dữ liệu nào.")

    # 2. QUAN ĐIỂM
    elif "1️⃣" in menu:
        st.title("🗣️ Hoạt động 1: Quan điểm")
        col_sv, col_gv = st.columns(2)
        
        with col_sv:
            if st.session_state['user_role'] == 'student':
                with st.form("f1"):
                    name = st.text_input("Họ tên")
                    txt = st.text_area("Ý kiến của bạn")
                    if st.form_submit_button("Gửi") and name:
                        with open(get_file_path(active_class, 1), "a", encoding="utf-8") as f:
                            f.write(f"{name}|{txt.replace(chr(10), ' ')}\n")
                        st.success("Đã gửi!")
            else:
                st.info("Giảng viên chỉ xem, không nhập liệu.")

        with col_gv:
            st.subheader("Phân tích")
            df = load_data(active_class, 1)
            if not df.empty:
                st.dataframe(df, height=200)
                if st.session_state['user_role'] == 'teacher':
                    if st.button("AI Phân tích"):
                        prompt = f"Phân tích ý kiến lớp {active_class}: {df.to_string()}"
                        st.write(model.generate_content(prompt).text)
            else:
                st.warning("Chưa có dữ liệu.")

    # 3. QUY TRÌNH
    elif "2️⃣" in menu:
        st.title("🧩 Hoạt động 2: Quy trình")
        steps = ["1. Tiếp nhận", "2. Báo cáo", "3. Xuống hiện trường", "4. Xử lý", "5. Lập biên bản"]
        
        col_sv, col_gv = st.columns(2)
        with col_sv:
            if st.session_state['user_role'] == 'student':
                with st.form("f2"):
                    name = st.text_input("Họ tên")
                    ans = st.multiselect("Thứ tự:", steps)
                    if st.form_submit_button("Nộp") and name:
                        with open(get_file_path(active_class, 2), "a", encoding="utf-8") as f:
                            f.write(f"{name}|{'->'.join(ans)}\n")
                        st.success("Đã nộp!")
        
        with col_gv:
            st.subheader("Kết quả")
            df = load_data(active_class, 2)
            if not df.empty:
                st.dataframe(df)
                if st.session_state['user_role'] == 'teacher' and st.button("AI Chấm bài"):
                     st.write(model.generate_content(f"Chấm bài quy trình: {df.to_string()}").text)

    # 4. THU HOẠCH
    elif "3️⃣" in menu:
        st.title("📝 Hoạt động 3: Thu hoạch")
        col_sv, col_gv = st.columns(2)
        with col_sv:
             if st.session_state['user_role'] == 'student':
                with st.form("f3"):
                    name = st.text_input("Họ tên")
                    txt = st.text_area("Bài học tâm đắc")
                    if st.form_submit_button("Gửi") and name:
                        with open(get_file_path(active_class, 3), "a", encoding="utf-8") as f:
                             f.write(f"{name}|{txt.replace(chr(10), ' ')}\n")
                        st.success("Ghi nhận!")
        with col_gv:
             df = load_data(active_class, 3)
             if not df.empty:
                 st.dataframe(df)
                 if st.session_state['user_role'] == 'teacher':
                     topic = st.text_input("Chủ đề:")
                     if st.button("Tổng hợp") and topic:
                         st.write(model.generate_content(f"Chủ đề {topic}. Tóm tắt: {df.to_string()}").text)

    # 5. TRANG QUẢN TRỊ (CHỈ GIẢNG VIÊN MỚI THẤY)
    elif menu == "⚙️ Quản trị & Reset":
        st.title("⚙️ Quản trị Hệ thống Đa lớp")
        st.markdown("---")
        
        st.warning("⚠️ Vùng nguy hiểm: Xóa dữ liệu sẽ không thể khôi phục.")
        
        col_chon, col_hanh_dong = st.columns([1, 2])
        
        with col_chon:
            lop_can_xoa = st.selectbox("Chọn lớp cần Reset dữ liệu:", list(LIST_CLASSES.keys()))
            ma_lop_xoa = LIST_CLASSES[lop_can_xoa]
        
        with col_hanh_dong:
            st.markdown(f"**Trạng thái lớp {lop_can_xoa}:**")
            # Kiểm tra xem có file dữ liệu không
            files_exist = any([os.path.exists(get_file_path(ma_lop_xoa, i)) for i in range(1,4)])
            
            if files_exist:
                st.info(f"Đang chứa dữ liệu.")
                # Sử dụng container để css nút màu đỏ
                with st.container():
                    st.markdown('<div class="reset-btn">', unsafe_allow_html=True)
                    if st.button(f"🗑 XÓA SẠCH DỮ LIỆU {lop_can_xoa.upper()}"):
                        clear_data(ma_lop_xoa)
                        st.toast(f"Đã xóa toàn bộ dữ liệu của {lop_can_xoa}!", icon="🗑")
                        time.sleep(1)
                        st.rerun()
                    st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.success("Dữ liệu trống/sạch sẽ.")
