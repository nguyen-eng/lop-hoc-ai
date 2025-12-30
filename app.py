import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
import time
from datetime import datetime

# ==========================================
# 1. CẤU HÌNH & CSS "EDX STYLE"
# ==========================================
st.set_page_config(
    page_title="T05 Academy - Learning Platform",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# COLOR PALETTE (CAND STYLE + EDX MODERN)
PRIMARY_COLOR = "#047857"   # Xanh lục bảo đậm (Màu ngành)
ACCENT_COLOR = "#fbbf24"    # Vàng kim (Điểm nhấn)
BG_COLOR = "#f3f4f6"        # Xám rất nhạt (Nền app)
CARD_BG = "#ffffff"         # Trắng (Nền thẻ)
TEXT_COLOR = "#1f2937"      # Xám đen (Chữ)

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    /* RESET MẶC ĐỊNH */
    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
        background-color: {BG_COLOR};
        color: {TEXT_COLOR};
    }}
    
    /* ẨN HEADER/FOOTER CỦA STREAMLIT */
    header {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    
    /* SIDEBAR CAO CẤP */
    [data-testid="stSidebar"] {{
        background-color: #0f172a; /* Màu xanh đen EdX */
        border-right: 1px solid #1e293b;
    }}
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
        color: white !important;
    }}
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span {{
        color: #94a3b8 !important;
    }}
    
    /* CARD DESIGN (KHUNG NỘI DUNG) */
    div.block-container {{
        padding-top: 2rem;
        max-width: 1200px;
    }}
    div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column;"] > div[data-testid="stVerticalBlock"] {{
        /* CSS cho các container chính */
    }}
    
    /* CUSTOM METRIC BOX */
    .metric-box {{
        background: white;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border-left: 5px solid {PRIMARY_COLOR};
        text-align: center;
    }}
    
    /* PROGRESS BAR */
    .stProgress > div > div > div > div {{
        background-color: {PRIMARY_COLOR};
    }}
    
    /* BUTTON HIỆN ĐẠI */
    div.stButton > button {{
        background-color: {PRIMARY_COLOR};
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.5rem 1.5rem;
        font-weight: 600;
        transition: all 0.2s;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }}
    div.stButton > button:hover {{
        background-color: #065f46;
        transform: translateY(-2px);
    }}
    
    /* TAB DESIGN */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 10px;
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: white;
        border-radius: 6px;
        padding: 10px 20px;
        border: 1px solid #e5e7eb;
    }}
    .stTabs [data-baseweb="tab"][aria-selected="true"] {{
        background-color: {PRIMARY_COLOR};
        color: white;
    }}
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
# 2. LOGIC HỆ THỐNG (DATA ENGINE)
# ==========================================

# Danh sách 10 lớp
CLASSES = {f"Lớp {i}": f"lop{i}" for i in range(1, 11)}
PASSWORDS = {f"lop{i}": f"LH{i}" for i in range(1, 11)}

# Quản lý Session
if 'logged_in' not in st.session_state: st.session_state.update({'logged_in': False, 'role': '', 'class_id': '', 'user_name': ''})

# Hàm xử lý file
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

# Hàm kiểm tra tiến độ (Giả lập)
def check_progress(cls, name):
    progress = 0
    # Kiểm tra xem tên học viên có trong các file dữ liệu không
    for i in range(1, 4):
        df = load_data(cls, i)
        if not df.empty and name in df["Học viên"].values:
            progress += 33
    return min(progress, 100)

# ==========================================
# 3. GIAO DIỆN: LOGIN (PORTAL STYLE)
# ==========================================
if not st.session_state['logged_in']:
    col_spacer1, col_main, col_spacer2 = st.columns([1, 1.5, 1])
    with col_main:
        st.markdown("<br><br>", unsafe_allow_html=True)
        with st.container(border=True):
            st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/Cong_an_hieu_Viet_Nam.svg/1200px-Cong_an_hieu_Viet_Nam.svg.png", width=100)
            st.markdown("<h1 style='text-align: center; font-size: 24px;'>CỔNG ĐÀO TẠO TRỰC TUYẾN T05</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: gray;'>Đăng nhập để truy cập khoá học</p>", unsafe_allow_html=True)
            
            tab_sv, tab_gv = st.tabs(["👨‍🎓 Học viên", "👮‍♂️ Giảng viên"])
            
            with tab_sv:
                c_class = st.selectbox("Chọn Lớp học", list(CLASSES.keys()), key="s_class")
                c_pass = st.text_input("Mật khẩu lớp (Ví dụ: LH1)", type="password", key="s_pass")
                if st.button("Truy cập Lớp học", use_container_width=True):
                    cls_code = CLASSES[c_class]
                    if c_pass == PASSWORDS[cls_code]:
                        st.session_state.update({'logged_in': True, 'role': 'student', 'class_id': cls_code})
                        st.rerun()
                    else:
                        st.error("Mật khẩu không đúng.")

            with tab_gv:
                t_pass = st.text_input("Mật khẩu Giảng viên", type="password", key="t_pass")
                if st.button("Đăng nhập Quản trị", use_container_width=True):
                    if t_pass == "T05":
                        st.session_state.update({'logged_in': True, 'role': 'teacher', 'class_id': 'lop1'}) # Mặc định xem lớp 1
                        st.rerun()
                    else:
                        st.error("Sai mật khẩu T05.")

# ==========================================
# 4. GIAO DIỆN CHÍNH (LMS DASHBOARD)
# ==========================================
else:
    # --- SIDEBAR (MENU KHÓA HỌC) ---
    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/a/a1/Cong_an_hieu_Viet_Nam.svg/1200px-Cong_an_hieu_Viet_Nam.svg.png", width=60)
        
        # Profile Card
        if st.session_state['role'] == 'student':
            user_display = [k for k, v in CLASSES.items() if v == st.session_state['class_id']][0]
            st.markdown(f"""
            <div style="background: #1e293b; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                <h4 style="color: white; margin:0;">Học viên</h4>
                <p style="color: #fbbf24; margin:0; font-size: 14px;">{user_display}</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background: #1e293b; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                <h4 style="color: white; margin:0;">Giảng viên</h4>
                <p style="color: #fbbf24; margin:0; font-size: 14px;">Admin Access</p>
            </div>
            """, unsafe_allow_html=True)
            
            # GV chọn lớp để xem
            st.markdown("**📂 CHỌN LỚP QUẢN LÝ**")
            select_cls = st.selectbox("", list(CLASSES.keys()), label_visibility="collapsed")
            st.session_state['class_id'] = CLASSES[select_cls]
            st.divider()

        # Menu Navigation
        menu = st.radio(
            "NỘI DUNG KHÓA HỌC",
            ["📊 Tổng quan", "Module 1: Quan điểm", "Module 2: Quy trình", "Module 3: Thu hoạch", "⚙️ Cài đặt lớp"],
        )
        
        st.divider()
        if st.button("Đăng xuất", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    # --- MAIN CONTENT AREA ---
    
    # Header động
    cls_name = [k for k, v in CLASSES.items() if v == st.session_state['class_id']][0]
    st.markdown(f"### 🚩 {cls_name} / {menu}")
    
    # === 1. DASHBOARD (TỔNG QUAN) ===
    if "Tổng quan" in menu:
        # Load data
        df1 = load_data(st.session_state['class_id'], 1)
        df2 = load_data(st.session_state['class_id'], 2)
        df3 = load_data(st.session_state['class_id'], 3)
        total_sub = len(df1) + len(df2) + len(df3)
        
        # Display EdX style Metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f'<div class="metric-box"><h3>{total_sub}</h3><p>Tổng lượt nộp</p></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="metric-box"><h3>{len(df1)}</h3><p>Thảo luận</p></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="metric-box"><h3>{len(df2)}</h3><p>Bài tập</p></div>', unsafe_allow_html=True)
        c4.markdown(f'<div class="metric-box"><h3>{len(df3)}</h3><p>Thu hoạch</p></div>', unsafe_allow_html=True)
        
        st.write("") # Spacer
        
        # Biểu đồ và Tiến độ
        c_chart, c_prog = st.columns([2, 1])
        
        with c_chart:
            with st.container(border=True):
                st.markdown("#### 📈 Biểu đồ tham gia")
                if total_sub > 0:
                    data = pd.DataFrame({"Module": ["M1: Quan điểm", "M2: Quy trình", "M3: Thu hoạch"], "Số lượng": [len(df1), len(df2), len(df3)]})
                    fig = px.bar(data, x="Module", y="Số lượng", text_auto=True, color="Module", color_discrete_sequence=[PRIMARY_COLOR, ACCENT_COLOR, "#ef4444"])
                    fig.update_layout(plot_bgcolor="white", height=300)
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Chưa có dữ liệu để hiển thị.")
        
        with c_prog:
            with st.container(border=True):
                st.markdown("#### 🔔 Thông báo lớp học")
                st.success("Hệ thống hoạt động bình thường.")
                st.info(f"Chào mừng đến với {cls_name}. Vui lòng hoàn thành các Module bên dưới.")
                if st.session_state['role'] == 'student':
                    # Tính tiến độ cá nhân (Demo - cần nhập tên để check)
                    st.markdown("---")
                    my_name_check = st.text_input("Nhập tên để xem tiến độ:", placeholder="Ví dụ: Nguyễn Văn A")
                    if my_name_check:
                        prog = check_progress(st.session_state['class_id'], my_name_check)
                        st.write(f"Tiến độ của **{my_name_check}**:")
                        st.progress(prog)
                        st.caption(f"Đã hoàn thành {prog}% khoá học")

    # === 2. MODULE 1: QUAN ĐIỂM ===
    elif "Module 1" in menu:
        st.markdown("## 🗣️ Module 1: Thảo luận Chuyên đề")
        st.info("Câu hỏi thảo luận: **Theo đồng chí, AI là CƠ HỘI hay THÁCH THỨC đối với công tác An ninh?**")
        
        c_left, c_right = st.columns([1, 1], gap="large")
        
        with c_left:
            if st.session_state['role'] == 'student':
                with st.container(border=True):
                    st.markdown("#### ✍️ Nộp ý kiến")
                    with st.form("f1"):
                        name = st.text_input("Họ và tên")
                        content = st.text_area("Ý kiến của đồng chí", height=150)
                        if st.form_submit_button("Gửi bài") and name:
                            save_data(st.session_state['class_id'], 1, name, content)
                            st.toast("Đã gửi thành công!", icon="✅")
                            time.sleep(1); st.rerun()
            else:
                st.info("Chế độ Giảng viên: Xem kết quả bên phải.")

        with c_right:
            df = load_data(st.session_state['class_id'], 1)
            with st.container(border=True):
                st.markdown(f"#### 💬 Thảo luận lớp ({len(df)})")
                if not df.empty:
                    st.dataframe(df, use_container_width=True, height=300)
                    if st.session_state['role'] == 'teacher' and st.button("✨ AI Phân tích Cảm xúc"):
                        with st.spinner("AI đang đọc dữ liệu..."):
                            prompt = f"Phân tích sắc thái (Tích cực/Tiêu cực/Trung lập) từ các ý kiến sau: {df.to_string()}. Trả về Markdown ngắn gọn."
                            st.markdown(model.generate_content(prompt).text)

    # === 3. MODULE 2: QUY TRÌNH ===
    elif "Module 2" in menu:
        st.markdown("## 🧩 Module 2: Bài tập Quy trình")
        
        c_left, c_right = st.columns([1, 1], gap="large")
        steps = ["1. Tiếp nhận tin", "2. Báo cáo lãnh đạo", "3. Xuống hiện trường", "4. Xử lý ban đầu", "5. Lập hồ sơ"]
        
        with c_left:
            if st.session_state['role'] == 'student':
                with st.container(border=True):
                    st.markdown("#### 🎮 Sắp xếp quy trình")
                    with st.form("f2"):
                        name = st.text_input("Họ và tên")
                        ans = st.multiselect("Chọn thứ tự đúng:", steps)
                        if st.form_submit_button("Nộp bài") and name:
                            save_data(st.session_state['class_id'], 2, name, " -> ".join(ans))
                            st.toast("Đã nộp bài!", icon="✅")
                            time.sleep(1); st.rerun()
        
        with c_right:
            df = load_data(st.session_state['class_id'], 2)
            with st.container(border=True):
                st.markdown("#### 📊 Kết quả bài tập")
                if not df.empty:
                    st.dataframe(df, use_container_width=True)
                    if st.session_state['role'] == 'teacher' and st.button("🤖 AI Chấm & Phân tích lỗi"):
                         with st.spinner("AI đang chấm bài..."):
                            st.write(model.generate_content(f"Quy trình đúng: {steps}. Bài làm: {df.to_string()}. Phân tích lỗi sai.").text)

    # === 4. MODULE 3: THU HOẠCH ===
    elif "Module 3" in menu:
        st.markdown("## 📝 Module 3: Tổng kết & Thu hoạch")
        
        with st.container(border=True):
            col_inp, col_img = st.columns([2, 1])
            with col_inp:
                if st.session_state['role'] == 'student':
                    st.markdown("#### Bài học tâm đắc nhất hôm nay")
                    with st.form("f3"):
                        name = st.text_input("Họ và tên")
                        val = st.text_area("Nội dung thu hoạch", height=100)
                        if st.form_submit_button("Gửi thu hoạch") and name:
                            save_data(st.session_state['class_id'], 3, name, val)
                            st.toast("Cảm ơn đồng chí!", icon="🎉")
                            time.sleep(1); st.rerun()
                else:
                    st.info("Khu vực học viên nộp bài.")
            with col_img:
                st.image("https://cdn-icons-png.flaticon.com/512/3135/3135810.png", width=150, caption="Knowledge Base")

        st.markdown("---")
        if st.session_state['role'] == 'teacher':
             df = load_data(st.session_state['class_id'], 3)
             st.markdown("#### 🔐 Giảng viên: Tổng hợp Tri thức")
             if not df.empty:
                 st.dataframe(df)
                 topic = st.text_input("Chủ đề bài giảng hôm nay:")
                 if st.button("🚀 Tổng hợp 3 điểm cốt lõi") and topic:
                     st.markdown(model.generate_content(f"Chủ đề: {topic}. Dữ liệu: {df.to_string()}. Tóm tắt 3 điểm chính.").text)

    # === 5. SETTINGS ===
    elif "Cài đặt" in menu:
        if st.session_state['role'] == 'teacher':
            st.markdown("## ⚙️ Quản trị Lớp học")
            st.warning(f"Thầy đang thao tác trên: **{cls_name}**")
            
            with st.container(border=True):
                st.markdown("#### 🗑 Reset Dữ liệu Lớp học")
                st.markdown("Thao tác này sẽ xóa toàn bộ bài làm của học viên trong lớp này. Không thể khôi phục.")
                if st.button(f"Xác nhận Xóa dữ liệu {cls_name}", type="primary"):
                    clear_class_data(st.session_state['class_id'])
                    st.toast("Đã xóa sạch dữ liệu!", icon="🗑")
                    time.sleep(1); st.rerun()
        else:
            st.error("Bạn không có quyền truy cập trang này.")
