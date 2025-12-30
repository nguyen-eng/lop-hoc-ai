import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import plotly.express as px
import time
from datetime import datetime

# ==========================================
# 1. CẤU HÌNH HỆ THỐNG
# ==========================================
st.set_page_config(
    page_title="T05 Academy - Learning Platform",
    page_icon="👮‍♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 🖼️ KHU VỰC THAY LOGO NHÀ TRƯỜNG ---
# Thầy dán link ảnh logo của Thầy vào giữa hai dấu ngoặc kép dưới đây
# Nếu chưa có, cứ để nguyên link mặc định này (Công an hiệu)
LOGO_URL = "https://drive.google.com/uc?export=view&id=1PsUr01oeleJkW2JB1gqnID9WJNsTMFGW" 
# ----------------------------------------

# MÀU SẮC CHỦ ĐẠO (Xanh Cảnh sát)
PRIMARY_COLOR = "#047857"
BG_COLOR = "#f3f4f6"

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; background-color: {BG_COLOR}; }}
    
    /* Ẩn Header mặc định */
    header {{visibility: hidden;}} footer {{visibility: hidden;}}
    
    /* Sidebar màu tối */
    [data-testid="stSidebar"] {{ background-color: #0f172a; border-right: 1px solid #1e293b; }}
    [data-testid="stSidebar"] h1, h2, h3 {{ color: white !important; }}
    [data-testid="stSidebar"] p, span, label {{ color: #94a3b8 !important; }}
    
    /* Card design */
    .metric-box {{ background: white; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border-left: 5px solid {PRIMARY_COLOR}; text-align: center; }}
    
    /* Button */
    div.stButton > button {{ background-color: {PRIMARY_COLOR}; color: white; border: none; border-radius: 6px; padding: 0.5rem 1.5rem; font-weight: 600; width: 100%; transition: all 0.2s; }}
    div.stButton > button:hover {{ background-color: #065f46; transform: translateY(-2px); }}
</style>
""", unsafe_allow_html=True)

# --- KẾT NỐI AI ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
except:
    pass

# ==========================================
# 2. XỬ LÝ DỮ LIỆU & MẬT KHẨU
# ==========================================

# --- CẤU HÌNH MẬT KHẨU (BẢO MẬT) ---
CLASSES = {f"Lớp {i}": f"lop{i}" for i in range(1, 11)}

# Tạo mật khẩu mặc định (LH2 -> LH10)
PASSWORDS = {f"lop{i}": f"LH{i}" for i in range(1, 11)}
# Cập nhật riêng Lớp 1 theo ý Thầy
PASSWORDS["lop1"] = "T05-1" 

# Quản lý Session
if 'logged_in' not in st.session_state: st.session_state.update({'logged_in': False, 'role': '', 'class_id': ''})

# Hàm file
def get_path(cls, act): return f"data_{cls}_act{act}.csv"

def save_data(cls, act, name, content):
    with open(get_path(cls, act), "a", encoding="utf-8") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        f.write(f"{name}|{content}|{timestamp}\n")

def load_data(cls, act):
    if os.path.exists(get_path(cls, act)):
        return pd.read_csv(get_path(cls, act), sep="|", names=["Học viên", "Nội dung", "Thời gian"])
    return pd.DataFrame(columns=["Học viên", "Nội dung", "Thời gian"])

def clear_class_data(cls):
    for i in range(1, 4):
        p = get_path(cls, i)
        if os.path.exists(p): os.remove(p)

def check_progress(cls, name):
    progress = 0
    for i in range(1, 4):
        df = load_data(cls, i)
        if not df.empty and name in df["Học viên"].values: progress += 33
    return min(progress, 100)

# ==========================================
# 3. GIAO DIỆN ĐĂNG NHẬP (KHÔNG GỢI Ý PASS)
# ==========================================
if not st.session_state['logged_in']:
    col_spacer1, col_main, col_spacer2 = st.columns([1, 1.5, 1])
    with col_main:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            # Hiển thị Logo từ link Thầy dán
            st.markdown(f"""
                <div style="text-align: center;">
                    <img src="{LOGO_URL}" width="120" style="margin-bottom: 15px;">
                    <h2 style="color: {PRIMARY_COLOR}; margin: 0;">CỔNG ĐÀO TẠO T05</h2>
                    <p style="color: gray; font-size: 14px;">Hệ thống học tập trực tuyến</p>
                </div>
            """, unsafe_allow_html=True)
            
            st.divider()
            
            tab_sv, tab_gv = st.tabs(["👨‍🎓 Học viên", "👮‍♂️ Giảng viên"])
            
            with tab_sv:
                # Chỉ hiện danh sách lớp, KHÔNG hiện gợi ý mật khẩu
                c_class = st.selectbox("Chọn Lớp sinh hoạt", list(CLASSES.keys()), key="s_class")
                c_pass = st.text_input("Nhập mật khẩu lớp", type="password", key="s_pass")
                
                if st.button("Truy cập Lớp học", use_container_width=True):
                    cls_code = CLASSES[c_class]
                    # Kiểm tra mật khẩu âm thầm
                    if c_pass == PASSWORDS[cls_code]:
                        st.session_state.update({'logged_in': True, 'role': 'student', 'class_id': cls_code})
                        st.rerun()
                    else:
                        # Thông báo lỗi chung chung, không gợi ý
                        st.error("Sai mật khẩu. Vui lòng kiểm tra lại.")

            with tab_gv:
                t_pass = st.text_input("Mật khẩu Giảng viên", type="password", key="t_pass")
                if st.button("Đăng nhập Quản trị", use_container_width=True):
                    if t_pass == "T05":
                        st.session_state.update({'logged_in': True, 'role': 'teacher', 'class_id': 'lop1'})
                        st.rerun()
                    else:
                        st.error("Sai mật khẩu quản trị.")

# ==========================================
# 4. GIAO DIỆN CHÍNH (LMS)
# ==========================================
else:
    # --- SIDEBAR ---
    with st.sidebar:
        # Logo Sidebar
        st.image(LOGO_URL, width=70)
        
        # Profile Card
        cls_name = [k for k, v in CLASSES.items() if v == st.session_state['class_id']][0]
        role_title = "Học viên" if st.session_state['role'] == 'student' else "Giảng viên"
        
        st.markdown(f"""
        <div style="background: #1e293b; padding: 15px; border-radius: 8px; margin: 10px 0;">
            <p style="color: #94a3b8; margin:0; font-size: 12px;">Xin chào,</p>
            <h4 style="color: white; margin:0;">{role_title}</h4>
            <p style="color: #fbbf24; margin:0; font-size: 13px;">{cls_name}</p>
        </div>
        """, unsafe_allow_html=True)

        if st.session_state['role'] == 'teacher':
             st.markdown("👇 **CHUYỂN LỚP:**")
             sel = st.selectbox("", list(CLASSES.keys()), label_visibility="collapsed")
             st.session_state['class_id'] = CLASSES[sel]
             st.divider()

        menu = st.radio("MENU", ["📊 Tổng quan", "Module 1: Quan điểm", "Module 2: Quy trình", "Module 3: Thu hoạch", "⚙️ Cài đặt"])
        
        st.divider()
        if st.button("Đăng xuất"):
            st.session_state.clear()
            st.rerun()

    # --- MAIN CONTENT ---
    st.markdown(f"### 🚩 {cls_name} / {menu}")
    
    # 1. DASHBOARD
    if "Tổng quan" in menu:
        df1 = load_data(st.session_state['class_id'], 1)
        df2 = load_data(st.session_state['class_id'], 2)
        df3 = load_data(st.session_state['class_id'], 3)
        total = len(df1) + len(df2) + len(df3)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f'<div class="metric-box"><h3>{total}</h3><p>Tổng bài nộp</p></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="metric-box"><h3>{len(df1)}</h3><p>Thảo luận</p></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="metric-box"><h3>{len(df2)}</h3><p>Bài tập</p></div>', unsafe_allow_html=True)
        c4.markdown(f'<div class="metric-box"><h3>{len(df3)}</h3><p>Thu hoạch</p></div>', unsafe_allow_html=True)
        
        st.write("")
        c_chart, c_info = st.columns([2, 1])
        with c_chart:
            with st.container(border=True):
                st.markdown("#### 📈 Tiến độ lớp học")
                if total > 0:
                    d = pd.DataFrame({"M": ["M1", "M2", "M3"], "V": [len(df1), len(df2), len(df3)]})
                    fig = px.bar(d, x="M", y="V", color="M", color_discrete_sequence=[PRIMARY_COLOR, "#fbbf24", "#ef4444"])
                    st.plotly_chart(fig, use_container_width=True)
                else: st.info("Chưa có dữ liệu.")
        with c_info:
            with st.container(border=True):
                st.info("Hệ thống hoạt động tốt.")
                if st.session_state['role'] == 'student':
                    st.markdown("---")
                    ck = st.text_input("Tra cứu tiến độ (Nhập tên):")
                    if ck:
                        p = check_progress(st.session_state['class_id'], ck)
                        st.progress(p)
                        st.caption(f"Hoàn thành {p}%")

    # 2. MODULE 1
    elif "Module 1" in menu:
        st.info("Chủ đề: **AI là CƠ HỘI hay THÁCH THỨC đối với An ninh trật tự?**")
        c1, c2 = st.columns(2)
        with c1:
            if st.session_state['role'] == 'student':
                with st.form("f1"):
                    if st.form_submit_button("Gửi ý kiến") and (n:=st.text_input("Tên")) and (c:=st.text_area("Nội dung")):
                        save_data(st.session_state['class_id'], 1, n, c)
                        st.toast("Đã gửi!", icon="✅"); time.sleep(1); st.rerun()
            else: st.info("Giảng viên xem kết quả bên phải.")
        with c2:
            df = load_data(st.session_state['class_id'], 1)
            if not df.empty:
                st.dataframe(df, use_container_width=True)
                if st.session_state['role'] == 'teacher' and st.button("AI Phân tích"):
                    st.markdown(model.generate_content(f"Phân tích cảm xúc: {df.to_string()}").text)

    # 3. MODULE 2
    elif "Module 2" in menu:
        c1, c2 = st.columns(2)
        with c1:
            if st.session_state['role'] == 'student':
                with st.form("f2"):
                    steps = ["1. Tiếp nhận", "2. Báo cáo", "3. Hiện trường", "4. Xử lý", "5. Hồ sơ"]
                    if st.form_submit_button("Nộp bài") and (n:=st.text_input("Tên")) and (ans:=st.multiselect("Thứ tự", steps)):
                        save_data(st.session_state['class_id'], 2, n, " -> ".join(ans))
                        st.toast("Đã nộp!", icon="✅"); time.sleep(1); st.rerun()
        with c2:
            df = load_data(st.session_state['class_id'], 2)
            if not df.empty: st.dataframe(df, use_container_width=True)

    # 4. MODULE 3
    elif "Module 3" in menu:
        c1, c2 = st.columns([2, 1])
        with c1:
            if st.session_state['role'] == 'student':
                with st.form("f3"):
                    if st.form_submit_button("Gửi thu hoạch") and (n:=st.text_input("Tên")) and (v:=st.text_area("Nội dung")):
                        save_data(st.session_state['class_id'], 3, n, v)
                        st.toast("Đã gửi!", icon="✅"); time.sleep(1); st.rerun()
        
        st.markdown("---")
        if st.session_state['role'] == 'teacher':
            df = load_data(st.session_state['class_id'], 3)
            if not df.empty:
                st.dataframe(df)
                if st.button("Tổng hợp kiến thức") and (t:=st.text_input("Chủ đề:")):
                    st.markdown(model.generate_content(f"Chủ đề {t}. Dữ liệu {df.to_string()}. Tóm tắt 3 ý.").text)

    # 5. SETTINGS
    elif "Cài đặt" in menu:
        if st.session_state['role'] == 'teacher':
            st.warning(f"Đang quản lý: **{cls_name}**")
            if st.button("XÓA DỮ LIỆU LỚP NÀY", type="primary"):
                clear_class_data(st.session_state['class_id'])
                st.toast("Đã xóa xong!", icon="🗑"); time.sleep(1); st.rerun()
        else: st.error("Không có quyền truy cập.")
