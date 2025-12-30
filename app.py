import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import plotly.express as px
import time
from datetime import datetime
import threading

# ==========================================
# 1. CẤU HÌNH & GIAO DIỆN (UI/UX)
# ==========================================
st.set_page_config(
    page_title="Cổng Đào tạo T05",
    page_icon="👮‍♂️",
    layout="wide",
    initial_sidebar_state="collapsed" # Ẩn sidebar lúc đăng nhập cho đẹp
)

# --- LOGO (Dùng link thumbnail của Google Drive để ổn định) ---
LOGO_URL = "https://drive.google.com/thumbnail?id=1PsUr01oeleJkW2JB1gqnID9WJNsTMFGW&sz=w1000"

# --- MÀU SẮC NGÀNH ---
PRIMARY_COLOR = "#047857" # Xanh Cảnh sát
BG_COLOR = "#f0f2f5"      # Xám nền hiện đại
TEXT_COLOR = "#1f2937"

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
        background-color: {BG_COLOR};
        color: {TEXT_COLOR};
    }}
    
    /* Ẩn Header/Footer mặc định */
    header {{visibility: hidden;}} footer {{visibility: hidden;}}
    
    /* LOGIN CARD STYLE (Giao diện đăng nhập chuyên nghiệp) */
    .login-container {{
        background-color: white;
        padding: 40px;
        border-radius: 15px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        text-align: center;
        max-width: 500px;
        margin: 0 auto;
        border-top: 5px solid {PRIMARY_COLOR};
    }}
    
    /* SIDEBAR STYLE */
    [data-testid="stSidebar"] {{ background-color: #111827; }}
    [data-testid="stSidebar"] h1, h2, h3, p, span {{ color: #e5e7eb !important; }}
    
    /* METRIC CARD (Thẻ số liệu) */
    .metric-card {{
        background: white;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        text-align: center;
        transition: transform 0.2s;
    }}
    .metric-card:hover {{ transform: translateY(-5px); }}
    .metric-value {{ font-size: 28px; font-weight: 700; color: {PRIMARY_COLOR}; }}
    .metric-label {{ font-size: 14px; color: #6b7280; margin-top: 5px; }}
    
    /* BUTTON STYLE */
    div.stButton > button {{
        background-color: {PRIMARY_COLOR};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.6rem 1.5rem;
        font-weight: 600;
        width: 100%;
    }}
    div.stButton > button:hover {{ background-color: #064e3b; }}
    
    /* TAB STYLE */
    .stTabs [data-baseweb="tab-list"] {{ justify-content: center; }}
</style>
""", unsafe_allow_html=True)

# --- KẾT NỐI AI ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
except: pass

# ==========================================
# 2. XỬ LÝ DỮ LIỆU (BACKEND)
# ==========================================
data_lock = threading.Lock()
CLASSES = {f"Lớp {i}": f"lop{i}" for i in range(1, 11)}

# Mật khẩu: T05-1 cho lớp 1, còn lại LH2...LH10
PASSWORDS = {f"lop{i}": f"LH{i}" for i in range(1, 11)}
PASSWORDS["lop1"] = "T05-1"

# Session Management
if 'logged_in' not in st.session_state: st.session_state.update({'logged_in': False, 'role': '', 'class_id': ''})

def get_path(cls, act): return f"data_{cls}_act{act}.csv"

def save_data(cls, act, name, content):
    content = content.replace("|", "-").replace("\n", " ")
    timestamp = datetime.now().strftime("%H:%M %d/%m")
    row = f"{name}|{content}|{timestamp}\n"
    file_path = get_path(cls, act)
    with data_lock:
        with open(file_path, "a", encoding="utf-8") as f: f.write(row)

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
# 3. MÀN HÌNH ĐĂNG NHẬP (PROFESSIONAL UI)
# ==========================================
if not st.session_state['logged_in']:
    # Tạo khoảng trống để đẩy form xuống giữa
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # Chia 3 cột để Form nằm giữa (Cột 2)
    c1, c2, c3 = st.columns([1, 2, 1])
    
    with c2:
        # Bắt đầu khung Login Card
        st.markdown(f"""
        <div class="login-container">
            <img src="{LOGO_URL}" width="120" style="margin-bottom: 20px;">
            <h2 style="color: {PRIMARY_COLOR}; margin: 0; font-weight: 700;">ĐẠI HỌC CẢNH SÁT NHÂN DÂN</h2>
            <p style="color: #6b7280; font-size: 16px; margin-bottom: 30px;">HỆ THỐNG HỌC TẬP TRỰC TUYẾN (T05)</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Tabs chọn vai trò nằm ngay dưới tiêu đề
        tab_sv, tab_gv = st.tabs(["👨‍🎓 CỔNG HỌC VIÊN", "👮‍♂️ CỔNG GIẢNG VIÊN"])
        
        with tab_sv:
            with st.container(border=True):
                st.info("Vui lòng chọn Lớp sinh hoạt và nhập Mã truy cập.")
                c_class = st.selectbox("Chọn Lớp:", list(CLASSES.keys()), key="s_class")
                c_pass = st.text_input("Mã truy cập:", type="password", key="s_pass")
                
                if st.button("ĐĂNG NHẬP LỚP HỌC", use_container_width=True):
                    cls_code = CLASSES[c_class]
                    if c_pass.strip() == PASSWORDS[cls_code]:
                        st.session_state.update({'logged_in': True, 'role': 'student', 'class_id': cls_code})
                        st.rerun()
                    else:
                        st.error(f"Sai mã truy cập của {c_class}.")

        with tab_gv:
            with st.container(border=True):
                st.info("Khu vực dành riêng cho Giảng viên/Quản trị.")
                t_pass = st.text_input("Mật khẩu Quản trị:", type="password", key="t_pass")
                if st.button("TRUY CẬP HỆ THỐNG", use_container_width=True):
                    if t_pass.strip() == "T05":
                        st.session_state.update({'logged_in': True, 'role': 'teacher', 'class_id': 'lop1'})
                        st.rerun()
                    else:
                        st.error("Sai mật khẩu T05.")

# ==========================================
# 4. GIAO DIỆN CHÍNH (FULL CONTENT)
# ==========================================
else:
    # --- SIDEBAR MENU ---
    with st.sidebar:
        st.image(LOGO_URL, width=80)
        
        # Thông tin người dùng
        cls_name = [k for k, v in CLASSES.items() if v == st.session_state['class_id']][0]
        role_label = "HỌC VIÊN" if st.session_state['role'] == 'student' else "GIẢNG VIÊN"
        
        st.markdown(f"""
        <div style="text-align: center; padding: 15px; background: #1f2937; border-radius: 8px; margin: 15px 0;">
            <p style="color: #9ca3af; font-size: 12px; margin:0;">Xin chào</p>
            <h3 style="color: white; margin:5px 0;">{role_label}</h3>
            <span style="background: {PRIMARY_COLOR}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px;">{cls_name}</span>
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state['role'] == 'teacher':
            st.markdown("---")
            st.caption("CHUYỂN ĐỔI LỚP QUẢN LÝ")
            sel_cls = st.selectbox("", list(CLASSES.keys()), label_visibility="collapsed")
            st.session_state['class_id'] = CLASSES[sel_cls]
        
        st.markdown("---")
        menu = st.radio("MENU ĐIỀU HƯỚNG", 
            ["📊 Dashboard Tổng quan", "1️⃣ Hoạt động: Quan điểm", "2️⃣ Hoạt động: Quy trình", "3️⃣ Hoạt động: Thu hoạch", "⚙️ Cài đặt hệ thống"])
        
        st.markdown("---")
        if st.button("Đăng xuất hệ thống"):
            st.session_state.clear()
            st.rerun()

    # --- MAIN CONTENT ---
    # Header Trang
    st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 20px;">
        <h1 style="margin:0; color: {PRIMARY_COLOR};">{menu.split(" ")[1]}</h1>
        <span style="background: #e5e7eb; color: #374151; padding: 5px 10px; border-radius: 20px; font-size: 14px;">{cls_name}</span>
    </div>
    """, unsafe_allow_html=True)

    # --- TRANG 1: DASHBOARD ---
    if "Dashboard" in menu:
        # Load dữ liệu
        df1 = load_data(st.session_state['class_id'], 1)
        df2 = load_data(st.session_state['class_id'], 2)
        df3 = load_data(st.session_state['class_id'], 3)
        total = len(df1) + len(df2) + len(df3)
        
        # 4 Thẻ số liệu đẹp
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f'<div class="metric-card"><div class="metric-value">{total}</div><div class="metric-label">Tổng tương tác</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="metric-card"><div class="metric-value">{len(df1)}</div><div class="metric-label">Ý kiến thảo luận</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="metric-card"><div class="metric-value">{len(df2)}</div><div class="metric-label">Bài tập quy trình</div></div>', unsafe_allow_html=True)
        c4.markdown(f'<div class="metric-card"><div class="metric-value">{len(df3)}</div><div class="metric-label">Bài thu hoạch</div></div>', unsafe_allow_html=True)
        
        st.write("")
        # Biểu đồ & Tiến độ
        col_chart, col_info = st.columns([2, 1])
        
        with col_chart:
            with st.container(border=True):
                st.subheader("📈 Biểu đồ tham gia lớp học")
                if total > 0:
                    chart_data = pd.DataFrame({
                        "Hoạt động": ["Quan điểm", "Quy trình", "Thu hoạch"],
                        "Số lượng": [len(df1), len(df2), len(df3)]
                    })
                    fig = px.bar(chart_data, x="Hoạt động", y="Số lượng", text_auto=True, 
                                 color="Hoạt động", color_discrete_sequence=[PRIMARY_COLOR, "#eab308", "#ef4444"])
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Chưa có dữ liệu để vẽ biểu đồ. Hãy bắt đầu các hoạt động!")
        
        with col_info:
            with st.container(border=True):
                st.subheader("Tra cứu tiến độ")
                st.caption("Nhập tên học viên để kiểm tra % hoàn thành:")
                check_name = st.text_input("Họ và tên:", placeholder="Ví dụ: Nguyễn Văn A")
                if check_name:
                    p = check_progress(st.session_state['class_id'], check_name)
                    st.progress(p)
                    if p == 100: st.success("🎉 Đã hoàn thành xuất sắc!"); st.balloons()
                    else: st.info(f"Đã hoàn thành {p}%")

    # --- TRANG 2: QUAN ĐIỂM (Khôi phục đầy đủ) ---
    elif "Quan điểm" in menu:
        st.info("💡 **Chủ đề thảo luận:** Theo đồng chí, Trí tuệ nhân tạo (AI) là CƠ HỘI hay THÁCH THỨC đối với công tác An ninh trật tự?")
        
        c_left, c_right = st.columns([1, 1], gap="medium")
        
        with c_left:
            st.subheader("✍️ Khu vực Nhập liệu")
            if st.session_state['role'] == 'student':
                with st.form("form_qd"):
                    name = st.text_input("Họ và tên học viên")
                    content = st.text_area("Quan điểm của đồng chí (Ngắn gọn)", height=150)
                    if st.form_submit_button("Gửi ý kiến"):
                        if name and content:
                            save_data(st.session_state['class_id'], 1, name, content)
                            st.success("Đã ghi nhận ý kiến!")
                            time.sleep(1); st.rerun()
                        else: st.warning("Vui lòng nhập đủ thông tin.")
            else:
                st.warning("Giảng viên vui lòng xem kết quả bên phải.")

        with c_right:
            st.subheader("gửi dữ liệu & Phân tích")
            df = load_data(st.session_state['class_id'], 1)
            
            with st.container(border=True):
                if not df.empty:
                    st.dataframe(df, use_container_width=True, height=300)
                    if st.session_state['role'] == 'teacher':
                        st.markdown("---")
                        if st.button("✨ AI Phân tích Quan điểm"):
                            with st.spinner("Đang phân tích dữ liệu..."):
                                prompt = f"Phân tích các ý kiến sau xem bao nhiêu % cho là Cơ hội, bao nhiêu % Thách thức: {df.to_string()}"
                                st.write(model.generate_content(prompt).text)
                else:
                    st.info("Chưa có ý kiến nào được gửi.")

    # --- TRANG 3: QUY TRÌNH (Khôi phục đầy đủ) ---
    elif "Quy trình" in menu:
        st.info("🧩 **Yêu cầu:** Sắp xếp các bước xử lý tình huống nghiệp vụ theo đúng trình tự.")
        
        steps = ["1. Tiếp nhận tin báo", "2. Báo cáo lãnh đạo", "3. Xuống hiện trường", "4. Xử lý ban đầu", "5. Lập hồ sơ"]
        
        c_left, c_right = st.columns([1, 1], gap="medium")
        
        with c_left:
            st.subheader("🎮 Bài tập")
            if st.session_state['role'] == 'student':
                with st.form("form_qt"):
                    name = st.text_input("Họ và tên")
                    ans = st.multiselect("Chọn thứ tự các bước:", steps)
                    if st.form_submit_button("Nộp bài"):
                        if name and ans:
                            save_data(st.session_state['class_id'], 2, name, " -> ".join(ans))
                            st.success("Đã nộp bài!")
                            time.sleep(1); st.rerun()
            else: st.warning("Giảng viên xem kết quả bên phải.")
            
        with c_right:
            st.subheader("📊 Kết quả lớp học")
            df = load_data(st.session_state['class_id'], 2)
            with st.container(border=True):
                if not df.empty:
                    st.dataframe(df, use_container_width=True)
                    if st.session_state['role'] == 'teacher':
                        if st.button("🔍 AI Chấm bài & Tìm lỗi sai"):
                            with st.spinner("Đang chấm bài..."):
                                prompt = f"Đáp án đúng là: {steps}. Dữ liệu bài làm: {df.to_string()}. Hãy chỉ ra lỗi sai phổ biến."
                                st.write(model.generate_content(prompt).text)
                else: st.info("Chưa có bài nộp.")

    # --- TRANG 4: THU HOẠCH (Khôi phục đầy đủ) ---
    elif "Thu hoạch" in menu:
        c_left, c_right = st.columns([2, 1], gap="medium")
        
        with c_left:
            st.subheader("📝 Bài thu hoạch cuối buổi")
            if st.session_state['role'] == 'student':
                with st.form("form_th"):
                    name = st.text_input("Họ và tên")
                    val = st.text_area("Điều tâm đắc nhất đồng chí rút ra được là gì?", height=150)
                    if st.form_submit_button("Gửi bài thu hoạch"):
                        if name and val:
                            save_data(st.session_state['class_id'], 3, name, val)
                            st.success("Cảm ơn đồng chí!")
                            time.sleep(1); st.rerun()
            else: st.info("Khu vực dành cho học viên nộp bài.")
            
        with c_right:
            st.image("https://cdn-icons-png.flaticon.com/512/2921/2921222.png", width=150)
            st.caption("Tổng hợp kiến thức")

        st.markdown("---")
        if st.session_state['role'] == 'teacher':
            st.subheader("🔐 Giảng viên: Tổng hợp tri thức")
            df = load_data(st.session_state['class_id'], 3)
            if not df.empty:
                st.dataframe(df, use_container_width=True)
                topic = st.text_input("Nhập chủ đề bài học để AI tổng hợp:")
                if st.button("🚀 AI Tổng hợp 3 điểm cốt lõi") and topic:
                    with st.spinner("Đang tổng hợp..."):
                        prompt = f"Chủ đề: {topic}. Dữ liệu học viên: {df.to_string()}. Tóm tắt 3 điểm chính."
                        st.write(model.generate_content(prompt).text)

    # --- TRANG 5: CÀI ĐẶT ---
    elif "Cài đặt" in menu:
        if st.session_state['role'] == 'teacher':
            st.subheader("⚙️ Quản trị Dữ liệu")
            st.warning(f"Thầy đang thao tác trên dữ liệu của: **{cls_name}**")
            
            with st.container(border=True):
                st.markdown("#### 🗑 Xóa dữ liệu lớp học")
                st.markdown("Thao tác này sẽ xóa sạch các bài làm của học viên trong lớp này để chuẩn bị cho khóa sau.")
                if st.button("XÁC NHẬN XÓA DỮ LIỆU", type="primary"):
                    clear_class_data(st.session_state['class_id'])
                    st.toast("Đã xóa sạch dữ liệu!", icon="🗑")
                    time.sleep(1); st.rerun()
        else:
            st.error("Học viên không có quyền truy cập khu vực này.")
