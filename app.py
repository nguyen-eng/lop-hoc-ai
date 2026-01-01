import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
import time
from datetime import datetime
import threading

# ==========================================
# 1. CẤU HÌNH & GIAO DIỆN (UI/UX)
# ==========================================
st.set_page_config(
    page_title="T05 Interactive Class",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- LOGO & MÀU SẮC ---
LOGO_URL = "https://drive.google.com/thumbnail?id=1PsUr01oeleJkW2JB1gqnID9WJNsTMFGW&sz=w1000"
PRIMARY_COLOR = "#006a4e" # Xanh lục bảo
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
    
    /* CARD LOGIN */
    .login-container {{
        background-color: white;
        padding: 40px;
        border-radius: 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.08);
        text-align: center;
        max-width: 600px;
        margin: 0 auto;
        border-top: 6px solid {PRIMARY_COLOR};
    }}
    
    /* MENTIMETER STYLE CONTAINERS */
    .menti-card {{
        background: white;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }}
    
    /* TEXT STYLES */
    .school-name {{ font-size: 22px; font-weight: 800; color: #b91c1c; text-transform: uppercase; margin-top: 15px; }}
    .system-name {{ font-size: 15px; font-weight: 700; color: #374151; margin-top: 5px; text-transform: uppercase; margin-bottom: 20px; }}
    
    /* INFO BOX */
    .info-box {{ background-color: #f1f5f9; padding: 15px; border-radius: 8px; margin-top: 15px; text-align: left; font-size: 14px; border-left: 4px solid {PRIMARY_COLOR}; }}
    .info-line {{ margin-bottom: 5px; display: block; }}
    .info-label {{ font-weight: 700; color: {PRIMARY_COLOR}; margin-right: 5px; }}
    
    /* SIDEBAR */
    [data-testid="stSidebar"] {{ background-color: #0f172a; }}
    [data-testid="stSidebar"] * {{ color: #cbd5e1; }}
    
    /* BUTTONS */
    div.stButton > button {{
        background-color: {PRIMARY_COLOR}; color: white; border: none; border-radius: 8px;
        padding: 0.6rem 1.2rem; font-weight: 700; width: 100%; text-transform: uppercase;
        transition: all 0.2s;
    }}
    div.stButton > button:hover {{ background-color: #047857; transform: translateY(-2px); }}
    
    /* BUTTON DANGER (Nút Reset màu đỏ) */
    .stButton button[kind="secondary"] {{
        background-color: white; color: #ef4444; border: 1px solid #ef4444;
    }}
    .stButton button[kind="secondary"]:hover {{
        background-color: #fef2f2; color: #dc2626; border-color: #dc2626;
    }}

</style>
""", unsafe_allow_html=True)

# --- KẾT NỐI AI ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
except: pass

# ==========================================
# 2. XỬ LÝ DỮ LIỆU & MẬT KHẨU
# ==========================================
data_lock = threading.Lock()
CLASSES = {f"Lớp học {i}": f"lop{i}" for i in range(1, 11)}

# --- CẤU HÌNH MẬT KHẨU MỚI (YÊU CẦU 1) ---
PASSWORDS = {}
# Lớp 1 đến 8: T05-1 ... T05-8
for i in range(1, 9):
    PASSWORDS[f"lop{i}"] = f"T05-{i}"
# Lớp 9, 10: LH9, LH10
for i in range(9, 11):
    PASSWORDS[f"lop{i}"] = f"LH{i}"

# Session Management
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
        try:
            return pd.read_csv(get_path(cls, act), sep="|", names=["Học viên", "Nội dung", "Thời gian"])
        except: return pd.DataFrame(columns=["Học viên", "Nội dung", "Thời gian"])
    return pd.DataFrame(columns=["Học viên", "Nội dung", "Thời gian"])

# --- HÀM XÓA DỮ LIỆU TỪNG HOẠT ĐỘNG (YÊU CẦU 3) ---
def clear_activity_data(cls, act):
    with data_lock:
        p = get_path(cls, act)
        if os.path.exists(p): os.remove(p)

# ==========================================
# 3. MÀN HÌNH ĐĂNG NHẬP
# ==========================================
if not st.session_state['logged_in']:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(f"""
<div class="login-container">
    <img src="{LOGO_URL}" width="110" style="margin-bottom: 15px;">
    <div class="school-name">TRƯỜNG ĐẠI HỌC CẢNH SÁT NHÂN DÂN</div>
    <div class="system-name">HỆ THỐNG TƯƠNG TÁC LỚP HỌC (T05)</div>
    <div class="info-box">
        <div class="info-line"><span class="info-label">Đơn vị:</span> Khoa LLCT & KHXHNV</div>
        <div class="info-line"><span class="info-label">Giảng viên:</span> Trần Nguyễn Sĩ Nguyên</div>
    </div>
</div>
""", unsafe_allow_html=True)
        
        st.write("")
        tab_sv, tab_gv = st.tabs(["CỔNG HỌC VIÊN", "CỔNG GIẢNG VIÊN"])
        
        with tab_sv:
            with st.container(border=True):
                c_class = st.selectbox("Chọn Lớp học", list(CLASSES.keys()))
                c_pass = st.text_input("Mã đăng nhập", type="password")
                if st.button("VÀO LỚP"):
                    cls_code = CLASSES[c_class]
                    if c_pass.strip() == PASSWORDS[cls_code]:
                        st.session_state.update({'logged_in': True, 'role': 'student', 'class_id': cls_code})
                        st.rerun()
                    else: st.error("Sai mã đăng nhập!")

        with tab_gv:
            with st.container(border=True):
                t_pass = st.text_input("Mật khẩu Quản trị", type="password")
                if st.button("ĐĂNG NHẬP ADMIN"):
                    if t_pass.strip() == "T05":
                        st.session_state.update({'logged_in': True, 'role': 'teacher', 'class_id': 'lop1'})
                        st.rerun()
                    else: st.error("Sai mật khẩu T05")

# ==========================================
# 4. GIAO DIỆN CHÍNH (MENTIMETER STYLE)
# ==========================================
else:
    # --- SIDEBAR ---
    with st.sidebar:
        st.image(LOGO_URL, width=80)
        
        # Nhạc nền (Mini Player)
        st.markdown("---")
        st.caption("🎵 NHẠC NỀN")
        st.audio("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3", start_time=0)

        # Info User
        cls_name = [k for k, v in CLASSES.items() if v == st.session_state['class_id']][0]
        role_label = "HỌC VIÊN" if st.session_state['role'] == 'student' else "GIẢNG VIÊN"
        
        st.markdown(f"""
        <div style="text-align: center; padding: 15px; background: #1e293b; border-radius: 8px; margin: 20px 0;">
            <h3 style="color: white; margin:0;">{role_label}</h3>
            <div style="color:#fbbf24; font-size:13px; margin-top:5px;">{cls_name}</div>
        </div>
        """, unsafe_allow_html=True)
        
        if st.session_state['role'] == 'teacher':
            st.caption("CHUYỂN LỚP:")
            sel_cls = st.selectbox("", list(CLASSES.keys()), label_visibility="collapsed")
            st.session_state['class_id'] = CLASSES[sel_cls]
        
        st.markdown("---")
        menu = st.radio("MENU", ["📊 Dashboard", "1️⃣ Quan điểm", "2️⃣ Quy trình", "3️⃣ Thu hoạch"])
        st.markdown("---")
        if st.button("ĐĂNG XUẤT"): st.session_state.clear(); st.rerun()

    # --- HEADER ---
    st.markdown(f"<h2 style='color:{PRIMARY_COLOR}; border-bottom:2px solid #e2e8f0; padding-bottom:10px;'>{menu} / {cls_name}</h2>", unsafe_allow_html=True)

    # ==========================================
    # TRANG 1: DASHBOARD
    # ==========================================
    if "Dashboard" in menu:
        df1 = load_data(st.session_state['class_id'], 1)
        df2 = load_data(st.session_state['class_id'], 2)
        df3 = load_data(st.session_state['class_id'], 3)
        
        # Metrics Mentimeter Style
        c1, c2, c3 = st.columns(3)
        st.markdown("""<style>.metric-box{background:white;padding:20px;border-radius:10px;box-shadow:0 2px 5px rgba(0,0,0,0.05);text-align:center;border-top:4px solid #006a4e;}.num{font-size:36px;font-weight:800;color:#1e293b;}.lbl{color:#64748b;font-weight:600;text-transform:uppercase;font-size:12px;}</style>""", unsafe_allow_html=True)
        
        c1.markdown(f'<div class="metric-box"><div class="num">{len(df1)}</div><div class="lbl">Ý kiến thảo luận</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="metric-box"><div class="num">{len(df2)}</div><div class="lbl">Bài tập nộp</div></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="metric-box"><div class="num">{len(df3)}</div><div class="lbl">Bài thu hoạch</div></div>', unsafe_allow_html=True)
        
        st.write("")
        # Biểu đồ tổng quan
        if len(df1)+len(df2)+len(df3) > 0:
            d = pd.DataFrame({"Hoạt động": ["HĐ1", "HĐ2", "HĐ3"], "Số lượng": [len(df1), len(df2), len(df3)]})
            fig = px.bar(d, x="Hoạt động", y="Số lượng", text_auto=True, color="Hoạt động", color_discrete_sequence=[PRIMARY_COLOR, "#eab308", "#ef4444"])
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Chưa có dữ liệu. Lớp học đang chờ kích hoạt.")

    # ==========================================
    # CÁC TRANG HOẠT ĐỘNG (CÓ NÚT RESET & AI CUSTOM)
    # ==========================================
    else:
        # Xác định ID hoạt động (1, 2, hoặc 3)
        act_id = 1 if "Quan điểm" in menu else 2 if "Quy trình" in menu else 3
        
        # --- PHẦN 1: GIAO DIỆN HỌC VIÊN & KẾT QUẢ ---
        c_left, c_right = st.columns([1, 1.5], gap="large")
        
        with c_left:
            st.markdown("##### ✍️ NHẬP LIỆU")
            # --- FORM NHẬP THEO TỪNG LOẠI ---
            if act_id == 1:
                st.info("Chủ đề: **AI là CƠ HỘI hay THÁCH THỨC?**")
                with st.form("f1"):
                    n = st.text_input("Họ tên")
                    c = st.text_area("Ý kiến của bạn")
                    if st.form_submit_button("GỬI Ý KIẾN") and n and c:
                        save_data(st.session_state['class_id'], 1, n, c)
                        st.success("Đã gửi!"); time.sleep(1); st.rerun()
            
            elif act_id == 2:
                st.info("Sắp xếp quy trình xử lý:")
                steps = ["1. Tiếp nhận", "2. Báo cáo", "3. Hiện trường", "4. Xử lý", "5. Hồ sơ"]
                with st.form("f2"):
                    n = st.text_input("Họ tên")
                    ans = st.multiselect("Thứ tự:", steps)
                    if st.form_submit_button("NỘP BÀI") and n and ans:
                        save_data(st.session_state['class_id'], 2, n, " -> ".join(ans))
                        st.success("Đã nộp!"); time.sleep(1); st.rerun()
                        
            elif act_id == 3:
                st.info("Tổng kết bài học hôm nay")
                with st.form("f3"):
                    n = st.text_input("Họ tên")
                    c = st.text_area("Điều tâm đắc nhất")
                    if st.form_submit_button("GỬI BÀI") and n and c:
                        save_data(st.session_state['class_id'], 3, n, c)
                        st.success("Đã gửi!"); time.sleep(1); st.rerun()

        with c_right:
            st.markdown("##### 📊 KẾT QUẢ TRỰC TUYẾN")
            df = load_data(st.session_state['class_id'], act_id)
            
            # Hiển thị kiểu Mentimeter (Biểu đồ hoặc List đẹp)
            if not df.empty:
                with st.container(border=True):
                    # Nếu là HĐ1 (Quan điểm) -> Vẽ Wordcloud hoặc List
                    if act_id == 1:
                        st.dataframe(df[["Học viên", "Nội dung"]], use_container_width=True, height=250)
                    # Nếu là HĐ2 (Quy trình) -> Chỉ hiện ds
                    elif act_id == 2:
                        st.dataframe(df, use_container_width=True, height=250)
                    # Nếu là HĐ3 (Thu hoạch)
                    else:
                        st.dataframe(df, use_container_width=True, height=250)
            else:
                st.info("Chưa có dữ liệu nào. Mời các đồng chí nhập liệu.")

        # --- PHẦN 2: KHU VỰC QUẢN TRỊ VIÊN (CHỈ GV THẤY) ---
        if st.session_state['role'] == 'teacher':
            st.markdown("---")
            with st.expander("⚙️ BẢNG ĐIỀU KHIỂN HOẠT ĐỘNG (GIẢNG VIÊN)", expanded=True):
                c_ai, c_reset = st.columns([2, 1])
                
                # 1. AI CUSTOM PROMPT
                with c_ai:
                    st.markdown("**🤖 AI Phân tích Tùy chỉnh**")
                    custom_prompt = st.text_area("Nhập yêu cầu cho AI (Ví dụ: Tìm lỗi sai, Phân tích cảm xúc...):", height=80)
                    if st.button("✨ PHÂN TÍCH NGAY", key=f"ai_btn_{act_id}"):
                        if not df.empty and custom_prompt:
                            with st.spinner("AI đang suy nghĩ..."):
                                full_prompt = f"Dữ liệu lớp học: {df.to_string()}. Yêu cầu của giảng viên: {custom_prompt}"
                                st.markdown(model.generate_content(full_prompt).text)
                        else:
                            st.warning("Cần có dữ liệu lớp học và câu lệnh nhập vào.")
                
                # 2. RESET DỮ LIỆU RIÊNG HOẠT ĐỘNG NÀY
                with c_reset:
                    st.markdown("**🗑 Quản lý Dữ liệu**")
                    st.warning("Lưu ý: Chỉ xóa dữ liệu của hoạt động này.")
                    if st.button(f"XÓA DỮ LIỆU HĐ {act_id}", type="primary", key=f"del_btn_{act_id}"):
                        clear_activity_data(st.session_state['class_id'], act_id)
                        st.toast(f"Đã xóa sạch dữ liệu Hoạt động {act_id}!", icon="🗑")
                        time.sleep(1)
                        st.rerun()
