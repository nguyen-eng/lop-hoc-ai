import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import plotly.express as px
import time
from datetime import datetime
import threading

# ==========================================
# 1. CẤU HÌNH GIAO DIỆN (UI/UX)
# ==========================================
st.set_page_config(
    page_title="Hệ thống Đào tạo T05",
    page_icon="👮‍♂️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- LOGO ---
LOGO_URL = "https://drive.google.com/thumbnail?id=1PsUr01oeleJkW2JB1gqnID9WJNsTMFGW&sz=w1000"

# --- MÀU SẮC & FONT ---
PRIMARY_COLOR = "#006a4e" 
BG_COLOR = "#f8fafc"      
TEXT_COLOR = "#111827"    

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');
    
    html, body, [class*="css"] {{
        font-family: 'Montserrat', sans-serif;
        background-color: {BG_COLOR};
        color: {TEXT_COLOR};
    }}
    
    header {{visibility: hidden;}} footer {{visibility: hidden;}}
    
    /* LOGIN CARD */
    .login-container {{
        background-color: white;
        padding: 40px 30px;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        text-align: center;
        max-width: 650px;
        margin: 0 auto;
        border-top: 6px solid {PRIMARY_COLOR};
    }}
    
    .school-name {{
        font-family: 'Montserrat', sans-serif;
        font-size: 22px;
        font-weight: 800;
        color: #b91c1c;
        text-transform: uppercase;
        margin-top: 15px;
        letter-spacing: 0.5px;
    }}
    
    .system-name {{
        font-size: 15px;
        font-weight: 700;
        color: #374151;
        margin-top: 5px;
        text-transform: uppercase;
        margin-bottom: 20px;
    }}

    /* INFO SECTION - ĐÃ KHẮC PHỤC LỖI HIỂN THỊ */
    .info-box {{
        background-color: #f1f5f9;
        padding: 15px;
        border-radius: 8px;
        margin-top: 15px;
        text-align: left;
        font-size: 14px;
        border-left: 4px solid {PRIMARY_COLOR};
    }}
    .info-line {{
        margin-bottom: 5px;
        color: #475569;
    }}
    .info-label {{
        font-weight: 700;
        color: {PRIMARY_COLOR};
        margin-right: 5px;
    }}
    
    /* SIDEBAR */
    [data-testid="stSidebar"] {{ background-color: #0f172a; }}
    [data-testid="stSidebar"] * {{ font-family: 'Montserrat', sans-serif; }}
    
    /* BUTTON */
    div.stButton > button {{
        background-color: {PRIMARY_COLOR};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.7rem 1.5rem;
        font-weight: 700;
        width: 100%;
        text-transform: uppercase;
    }}
    div.stButton > button:hover {{ background-color: #064e3b; }}
    
    /* TABS */
    .stTabs [data-baseweb="tab-list"] {{ justify-content: center; }}
    .stTabs [data-baseweb="tab"] {{ font-weight: 600; }}
    .stTabs [data-baseweb="tab"][aria-selected="true"] {{ color: {PRIMARY_COLOR}; }}

</style>
""", unsafe_allow_html=True)

# --- KẾT NỐI AI ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
except: pass

# ==========================================
# 2. BACKEND
# ==========================================
data_lock = threading.Lock()
CLASSES = {f"Lớp {i}": f"lop{i}" for i in range(1, 11)}

PASSWORDS = {f"lop{i}": f"LH{i}" for i in range(1, 11)}
PASSWORDS["lop1"] = "T05-1"

if 'logged_in' not in st.session_state: st.session_state.update({'logged_in': False, 'role': '', 'class_id': ''})

def get_path(cls, act): return f"data_{cls}_act{act}.csv"

def save_data(cls, act, name, content):
    content = content.replace("|", "-").replace("\n", " ")
    timestamp = datetime.now().strftime("%H:%M %d/%m")
    row = f"{name}|{content}|{timestamp}\n"
    with data_lock:
        with open(get_path(cls, act), "a", encoding="utf-8") as f: f.write(row)

def load_data(cls, act):
    if os.path.exists(get_path(cls, act)):
        return pd.read_csv(get_path(cls, act), sep="|", names=["Học viên", "Nội dung", "Thời gian"])
    return pd.DataFrame(columns=["Học viên", "Nội dung", "Thời gian"])

def clear_class_data(cls):
    with data_lock:
        for i in range(1, 4):
            if os.path.exists(get_path(cls, i)): os.remove(get_path(cls, i))

def check_progress(cls, name):
    prog = 0
    for i in range(1, 4):
        df = load_data(cls, i)
        if not df.empty and name in df["Học viên"].values: prog += 33
    return min(prog, 100)

# ==========================================
# 3. MÀN HÌNH ĐĂNG NHẬP (ĐÃ SỬA LỖI CODE BLOCK)
# ==========================================
if not st.session_state['logged_in']:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    
    with c2:
        # --- HTML ĐƯỢC VIẾT SÁT LỀ TRÁI ĐỂ TRÁNH LỖI ---
        login_html = f"""
<div class="login-container">
    <img src="{LOGO_URL}" width="110" style="margin-bottom: 15px;">
    <div class="school-name">TRƯỜNG ĐẠI HỌC CẢNH SÁT NHÂN DÂN</div>
    <div class="system-name">HỆ THỐNG HỌC TẬP TRỰC TUYẾN (T05)</div>
    
    <div class="info-box">
        <div class="info-line">
            <span class="info-label">Đơn vị:</span> Khoa Lý luận chính trị và Khoa học xã hội nhân văn
        </div>
        <div class="info-line">
            <span class="info-label">Giảng viên:</span> Trần Nguyễn Sĩ Nguyên
        </div>
    </div>
</div>
"""
        st.markdown(login_html, unsafe_allow_html=True)
        # -----------------------------------------------
        
        st.write("") 
        
        tab_sv, tab_gv = st.tabs(["CỔNG HỌC VIÊN", "CỔNG GIẢNG VIÊN"])
        
        with tab_sv:
            with st.container(border=True):
                st.markdown("**Thông tin truy cập**")
                c_class = st.selectbox("Lớp sinh hoạt", list(CLASSES.keys()), key="s_class")
                c_pass = st.text_input("Mã bảo mật", type="password", key="s_pass")
                
                st.write("")
                if st.button("ĐĂNG NHẬP NGAY"):
                    cls_code = CLASSES[c_class]
                    if c_pass.strip() == PASSWORDS[cls_code]:
                        st.session_state.update({'logged_in': True, 'role': 'student', 'class_id': cls_code})
                        st.rerun()
                    else:
                        st.error("Mật khẩu không chính xác.")

        with tab_gv:
            with st.container(border=True):
                st.markdown("**Quản trị hệ thống**")
                t_pass = st.text_input("Mật khẩu Giảng viên", type="password", key="t_pass")
                st.write("")
                if st.button("TRUY CẬP QUẢN TRỊ"):
                    if t_pass.strip() == "T05":
                        st.session_state.update({'logged_in': True, 'role': 'teacher', 'class_id': 'lop1'})
                        st.rerun()
                    else:
                        st.error("Sai mật khẩu T05.")

# ==========================================
# 4. GIAO DIỆN CHÍNH
# ==========================================
else:
    with st.sidebar:
        st.image(LOGO_URL, width=90)
        
        cls_name = [k for k, v in CLASSES.items() if v == st.session_state['class_id']][0]
        role_label = "HỌC VIÊN" if st.session_state['role'] == 'student' else "GIẢNG VIÊN"
        
        st.markdown(f"""
        <div style="text-align: center; padding: 20px 10px; background: #1e293b; border-radius: 8px; margin: 20px 0;">
            <p style="color: #94a3b8; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; margin:0;">Tài khoản</p>
            <h3 style="color: white; margin: 5px 0; font-weight: 700;">{role_label}</h3>
            <div style="background: {PRIMARY_COLOR}; color: white; padding: 4px 10px; border-radius: 4px; font-size: 12px; display: inline-block; margin-top: 5px;">{cls_name}</div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state['role'] == 'teacher':
            st.caption("CHUYỂN LỚP QUẢN LÝ")
            sel_cls = st.selectbox("", list(CLASSES.keys()), label_visibility="collapsed")
            st.session_state['class_id'] = CLASSES[sel_cls]
        
        st.markdown("---")
        menu = st.radio("MENU CHỨC NĂNG", 
            ["📊 Dashboard", "1️⃣ Thảo luận: Quan điểm", "2️⃣ Bài tập: Quy trình", "3️⃣ Tổng kết: Thu hoạch", "⚙️ Cài đặt"])
        
        st.markdown("---")
        if st.button("ĐĂNG XUẤT"):
            st.session_state.clear()
            st.rerun()

    st.markdown(f"""
    <h2 style="color: {PRIMARY_COLOR}; font-weight: 800; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px;">
        {menu.split(" ")[1]} <span style="font-weight: 400; color: #6b7280; font-size: 20px;">/ {cls_name}</span>
    </h2>
    """, unsafe_allow_html=True)

    if "Dashboard" in menu:
        df1 = load_data(st.session_state['class_id'], 1)
        df2 = load_data(st.session_state['class_id'], 2)
        df3 = load_data(st.session_state['class_id'], 3)
        total = len(df1) + len(df2) + len(df3)
        
        c1, c2, c3, c4 = st.columns(4)
        
        st.markdown("""
        <style>
        .metric-card { background: white; padding: 20px; border-radius: 8px; border: 1px solid #e2e8f0; text-align: center; }
        .metric-num { font-size: 32px; font-weight: 800; color: #0f172a; }
        .metric-lbl { font-size: 13px; font-weight: 600; color: #64748b; text-transform: uppercase; }
        </style>
        """, unsafe_allow_html=True)
        
        c1.markdown(f'<div class="metric-card"><div class="metric-num">{total}</div><div class="metric-lbl">Tổng bài nộp</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="metric-card"><div class="metric-num">{len(df1)}</div><div class="metric-lbl">Thảo luận</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="metric-card"><div class="metric-num">{len(df2)}</div><div class="metric-lbl">Bài tập</div></div>', unsafe_allow_html=True)
        c4.markdown(f'<div class="metric-card"><div class="metric-num">{len(df3)}</div><div class="metric-lbl">Thu hoạch</div></div>', unsafe_allow_html=True)
        
        st.write("")
        col_chart, col_info = st.columns([2, 1])
        with col_chart:
            with st.container(border=True):
                st.markdown("**Biểu đồ tham gia**")
                if total > 0:
                    d = pd.DataFrame({"HĐ": ["HĐ1", "HĐ2", "HĐ3"], "SL": [len(df1), len(df2), len(df3)]})
                    fig = px.bar(d, x="HĐ", y="SL", text_auto=True, color="HĐ", color_discrete_sequence=[PRIMARY_COLOR, "#f59e0b", "#ef4444"])
                    st.plotly_chart(fig, use_container_width=True)
                else: st.info("Chưa có dữ liệu.")
        with col_info:
            with st.container(border=True):
                st.markdown("**Tra cứu tiến độ**")
                check_name = st.text_input("Nhập họ tên học viên:")
                if check_name:
                    p = check_progress(st.session_state['class_id'], check_name)
                    st.progress(p)
                    st.caption(f"Đã hoàn thành {p}%")

    elif "Quan điểm" in menu:
        st.info("💡 **CHỦ ĐỀ:** Theo đồng chí, AI là CƠ HỘI hay THÁCH THỨC đối với công tác An ninh trật tự?")
        c1, c2 = st.columns([1, 1], gap="medium")
        with c1:
            st.markdown("##### ✍️ Cổng nhập liệu")
            if st.session_state['role'] == 'student':
                with st.form("f1"):
                    n = st.text_input("Họ tên")
                    c = st.text_area("Ý kiến ngắn gọn", height=150)
                    if st.form_submit_button("GỬI Ý KIẾN") and n and c:
                        save_data(st.session_state['class_id'], 1, n, c)
                        st.success("Đã gửi!"); time.sleep(1); st.rerun()
            else: st.warning("Giảng viên vui lòng xem kết quả.")
        with c2:
            st.markdown("##### 📋 Dữ liệu lớp")
            df = load_data(st.session_state['class_id'], 1)
            if not df.empty:
                st.dataframe(df, use_container_width=True)
                if st.session_state['role'] == 'teacher' and st.button("AI PHÂN TÍCH"):
                    st.markdown(model.generate_content(f"Phân tích: {df.to_string()}").text)

    elif "Quy trình" in menu:
        c1, c2 = st.columns([1, 1], gap="medium")
        with c1:
            st.markdown("##### 🧩 Bài tập sắp xếp")
            steps = ["1. Tiếp nhận", "2. Báo cáo", "3. Hiện trường", "4. Xử lý", "5. Hồ sơ"]
            if st.session_state['role'] == 'student':
                with st.form("f2"):
                    n = st.text_input("Họ tên")
                    ans = st.multiselect("Thứ tự đúng:", steps)
                    if st.form_submit_button("NỘP BÀI") and n and ans:
                        save_data(st.session_state['class_id'], 2, n, " -> ".join(ans))
                        st.success("Đã nộp!"); time.sleep(1); st.rerun()
        with c2:
            st.markdown("##### 📊 Kết quả")
            df = load_data(st.session_state['class_id'], 2)
            if not df.empty: st.dataframe(df, use_container_width=True)

    elif "Thu hoạch" in menu:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown("##### 📝 Bài thu hoạch")
            if st.session_state['role'] == 'student':
                with st.form("f3"):
                    n = st.text_input("Họ tên")
                    v = st.text_area("Điều tâm đắc nhất", height=150)
                    if st.form_submit_button("GỬI BÀI") and n and v:
                        save_data(st.session_state['class_id'], 3, n, v)
                        st.success("Đã gửi!"); time.sleep(1); st.rerun()
        with c2:
            st.image("https://cdn-icons-png.flaticon.com/512/2921/2921222.png", width=120)
        
        if st.session_state['role'] == 'teacher':
            st.markdown("---")
            df = load_data(st.session_state['class_id'], 3)
            if not df.empty:
                st.dataframe(df)
                t = st.text_input("Chủ đề bài học:")
                if st.button("TỔNG HỢP KIẾN THỨC") and t:
                    st.markdown(model.generate_content(f"Chủ đề {t}. Dữ liệu: {df.to_string()}. Tóm tắt 3 ý.").text)

    elif "Cài đặt" in menu:
        if st.session_state['role'] == 'teacher':
            st.warning(f"Đang thao tác lớp: **{cls_name}**")
            if st.button("XÓA DỮ LIỆU LỚP NÀY", type="primary"):
                clear_class_data(st.session_state['class_id'])
                st.toast("Đã xóa xong!", icon="🗑"); time.sleep(1); st.rerun()
        else: st.error("Không có quyền truy cập.")
