import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import plotly.express as px
import time

# --- 1. CẤU HÌNH HỆ THỐNG ---
st.set_page_config(page_title="Hệ thống Đa lớp T05", page_icon="👮‍♂️", layout="wide")

# --- 2. CSS STYLE (GIỮ NGUYÊN) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    [data-testid="stSidebar"] { background-color: #111827; color: white; }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label { color: #e5e7eb; }
    div.stButton > button {
        background-color: #047857; color: white; border: none;
        border-radius: 6px; padding: 0.6rem 1rem; font-weight: 600; width: 100%;
    }
    div.stButton > button:hover { background-color: #065f46; }
</style>
""", unsafe_allow_html=True)

# --- KẾT NỐI AI ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
except:
    pass

# --- 3. QUẢN LÝ TRẠNG THÁI (SESSION) ---
if 'is_logged_in' not in st.session_state:
    st.session_state['is_logged_in'] = False
if 'user_role' not in st.session_state:
    st.session_state['user_role'] = ''
if 'class_id' not in st.session_state:
    st.session_state['class_id'] = ''

# DANH SÁCH 10 LỚP
LIST_CLASSES = {f"Lớp học {i}": f"lop{i}" for i in range(1, 11)}
CLASS_PASSWORDS = {f"lop{i}": f"LH{i}" for i in range(1, 11)}

# HÀM HỖ TRỢ
def get_file_path(class_id, tab_num):
    return f"data_{class_id}_tab{tab_num}.csv"

def load_data(class_id, tab_num):
    filename = get_file_path(class_id, tab_num)
    if os.path.exists(filename):
        return pd.read_csv(filename, sep="|", names=["Tên", "Nội dung"])
    return pd.DataFrame(columns=["Tên", "Nội dung"])

def clear_data(class_id):
    for i in range(1, 4):
        file = get_file_path(class_id, i)
        if os.path.exists(file): os.remove(file)

# ==========================================
# MÀN HÌNH ĐĂNG NHẬP (QUAN TRỌNG)
# ==========================================
if not st.session_state['is_logged_in']:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<h2 style='text-align: center; color: #047857;'>CỔNG ĐÀO TẠO T05</h2>", unsafe_allow_html=True)
            st.info("👋 Chào mừng! Vui lòng chọn lớp để đăng nhập.")
            
            # --- DANH MỤC 10 LỚP Ở ĐÂY ---
            chon_lop = st.selectbox("📌 Chọn Lớp học:", list(LIST_CLASSES.keys()))
            mat_khau = st.text_input("🔑 Mật khẩu:", type="password")
            
            c1, c2 = st.columns(2)
            if c1.button("Đăng nhập Học viên"):
                ma_lop = LIST_CLASSES[chon_lop]
                mk_dung = CLASS_PASSWORDS[ma_lop]
                if mat_khau == mk_dung:
                    st.session_state['is_logged_in'] = True
                    st.session_state['user_role'] = 'student'
                    st.session_state['class_id'] = ma_lop
                    st.rerun()
                else:
                    st.error(f"Sai mật khẩu! Mật khẩu lớp này là {mk_dung}")
            
            if c2.button("Giảng viên / Admin"):
                if mat_khau == "T05":
                    st.session_state['is_logged_in'] = True
                    st.session_state['user_role'] = 'teacher'
                    st.session_state['class_id'] = 'admin'
                    st.rerun()
                else:
                    st.error("Sai mật khẩu Giảng viên (T05).")

# ==========================================
# GIAO DIỆN CHÍNH (SAU KHI ĐĂNG NHẬP)
# ==========================================
else:
    # --- SIDEBAR ---
    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/Cong_an_hieu_Viet_Nam.svg/1200px-Cong_an_hieu_Viet_Nam.svg.png", width=50)
        st.markdown("### T05 LMS")
        st.divider()
        
        # XỬ LÝ HIỂN THỊ LỚP
        active_class = st.session_state['class_id']
        
        if st.session_state['user_role'] == 'teacher':
            st.success("⭐️ Chế độ Giảng viên")
            st.markdown("---")
            # --- MENU CHỌN LỚP CHO GIẢNG VIÊN (NẰM Ở SIDEBAR) ---
            st.markdown("👇 **CHỌN LỚP ĐỂ QUẢN LÝ:**")
            chon_lop_gv = st.selectbox("", list(LIST_CLASSES.keys()), index=0)
            active_class = LIST_CLASSES[chon_lop_gv] # Cập nhật lớp đang xem
            st.markdown("---")
        else:
            # Học viên thì chỉ hiện tên lớp mình
            ten_lop = [k for k, v in LIST_CLASSES.items() if v == active_class][0]
            st.info(f"👤 Học viên: {ten_lop}")

        menu = st.radio("ĐIỀU HƯỚNG:", ["🏠 Dashboard", "1️⃣ Quan điểm", "2️⃣ Quy trình", "3️⃣ Thu hoạch", "⚙️ Reset Dữ liệu"])
        
        st.markdown("---")
        # Nút đăng xuất để quay lại màn hình chọn lớp
        if st.button("🚪 Đăng xuất"):
            st.session_state.clear() # Xóa sạch trạng thái cũ
            st.rerun()

    # --- NỘI DUNG CHÍNH ---
    # Tiêu đề thay đổi theo lớp đang chọn
    ten_lop_hien_tai = [k for k, v in LIST_CLASSES.items() if v == active_class][0]
    
    if menu == "🏠 Dashboard":
        st.title(f"📊 {ten_lop_hien_tai}")
        df1 = load_data(active_class, 1); df2 = load_data(active_class, 2); df3 = load_data(active_class, 3)
        c1, c2, c3 = st.columns(3)
        c1.metric("Ý kiến", len(df1)); c2.metric("Bài tập", len(df2)); c3.metric("Thu hoạch", len(df3))
        if len(df1)+len(df2)+len(df3) > 0:
            data = pd.DataFrame({"HĐ": ["HĐ1", "HĐ2", "HĐ3"], "SL": [len(df1), len(df2), len(df3)]})
            st.plotly_chart(px.bar(data, x="HĐ", y="SL", color="HĐ"), use_container_width=True)
        else:
            st.info(f"Lớp {ten_lop_hien_tai} chưa có dữ liệu nào.")

    elif menu == "1️⃣ Quan điểm":
        st.header(f"🗣️ Thảo luận: {ten_lop_hien_tai}")
        c1, c2 = st.columns(2)
        with c1:
            if st.session_state['user_role'] == 'student':
                with st.form("f1"):
                    if st.form_submit_button("Gửi ý kiến") and (name := st.text_input("Tên")) and (txt := st.text_area("Nội dung")):
                        with open(get_file_path(active_class, 1), "a", encoding="utf-8") as f: f.write(f"{name}|{txt.replace(chr(10), ' ')}\n"); st.success("Xong!")
            else: st.info("Giảng viên chỉ xem.")
        with c2:
            df = load_data(active_class, 1)
            if not df.empty:
                st.dataframe(df, height=200)
                if st.session_state['user_role'] == 'teacher' and st.button("AI Phân tích"):
                    st.markdown(model.generate_content(f"Phân tích: {df.to_string()}").text)

    elif menu == "2️⃣ Quy trình":
        st.header(f"🧩 Bài tập: {ten_lop_hien_tai}")
        c1, c2 = st.columns(2)
        with c1:
            if st.session_state['user_role'] == 'student':
                with st.form("f2"):
                    if st.form_submit_button("Nộp bài") and (name := st.text_input("Tên")) and (ans := st.multiselect("Thứ tự", ["B1", "B2", "B3", "B4", "B5"])):
                        with open(get_file_path(active_class, 2), "a", encoding="utf-8") as f: f.write(f"{name}|{'->'.join(ans)}\n"); st.success("Xong!")
        with c2:
            df = load_data(active_class, 2)
            if not df.empty: st.dataframe(df)

    elif menu == "3️⃣ Thu hoạch":
        st.header(f"📝 Thu hoạch: {ten_lop_hien_tai}")
        c1, c2 = st.columns(2)
        with c1:
            if st.session_state['user_role'] == 'student':
                with st.form("f3"):
                    if st.form_submit_button("Nộp") and (name := st.text_input("Tên")) and (txt := st.text_area("Bài học")):
                        with open(get_file_path(active_class, 3), "a", encoding="utf-8") as f: f.write(f"{name}|{txt.replace(chr(10), ' ')}\n"); st.success("Xong!")
        with c2:
            df = load_data(active_class, 3)
            if not df.empty and st.session_state['user_role'] == 'teacher':
                if st.button("Tổng hợp") and (tp := st.text_input("Chủ đề")):
                    st.markdown(model.generate_content(f"Chủ đề {tp}. Dữ liệu {df.to_string()}. Tóm tắt 3 ý.").text)

    elif menu == "⚙️ Reset Dữ liệu":
        if st.session_state['user_role'] == 'teacher':
            st.warning(f"⚠️ Thầy đang chọn xóa dữ liệu của: **{ten_lop_hien_tai}**")
            if st.button(f"XÓA SẠCH {ten_lop_hien_tai}"):
                clear_data(active_class)
                st.toast("Đã xóa xong!", icon="🗑")
                time.sleep(1); st.rerun()
        else:
            st.error("Chỉ Giảng viên mới được vào đây!")
