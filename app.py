import streamlit as st
import google.generativeai as genai
import pandas as pd
import os
import plotly.express as px
import plotly.graph_objects as go
import time
from datetime import datetime
import threading
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from PIL import Image
import numpy as np

# ==========================================
# 1. CẤU HÌNH & GIAO DIỆN (UI/UX)
# ==========================================
st.set_page_config(
    page_title="T05 Interactive Suite",
    page_icon="📶",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- LOGO & RESOURCE ---
LOGO_URL = "https://drive.google.com/thumbnail?id=1PsUr01oeleJkW2JB1gqnID9WJNsTMFGW&sz=w1000"
TARGET_IMG = "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/Blank_US_Map_(states_only).svg/1200px-Blank_US_Map_(states_only).svg.png" # Dùng tạm map hoặc ảnh đích
# Có thể thay link ảnh đích (Target) ở trên để học viên ghim vào

PRIMARY_COLOR = "#006a4e" 
BG_COLOR = "#f0f2f5"
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
    
    /* LOGIN BOX */
    .login-box {{
        background: white; padding: 40px; border-radius: 20px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.1); text-align: center;
        max-width: 600px; margin: 0 auto; border-top: 6px solid {PRIMARY_COLOR};
    }}
    
    /* VISUALIZATION CARD */
    .viz-card {{
        background: white; padding: 25px; border-radius: 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }}
    
    /* FEATURE ICONS STYLE */
    .feature-icon {{ font-size: 24px; margin-right: 10px; }}
    
    /* INPUT & BUTTONS */
    .stTextInput input, .stTextArea textarea {{
        border: 2px solid #e2e8f0; border-radius: 12px; padding: 12px;
    }}
    div.stButton > button {{
        background-color: {PRIMARY_COLOR}; color: white; border: none;
        border-radius: 50px; padding: 12px 24px; font-weight: 700;
        text-transform: uppercase; letter-spacing: 1px; width: 100%;
        box-shadow: 0 4px 15px rgba(0, 106, 78, 0.3);
    }}
    div.stButton > button:hover {{ background-color: #00503a; transform: translateY(-2px); }}
    
    /* SIDEBAR */
    [data-testid="stSidebar"] {{ background-color: #111827; }}
    [data-testid="stSidebar"] * {{ color: #ffffff; }}

    /* NOTE CARD (Open Ended) */
    .note-card {{
        background: #fff; padding: 15px; border-radius: 12px;
        border-left: 5px solid {PRIMARY_COLOR}; margin-bottom: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08); font-size: 15px;
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
# 2. XỬ LÝ DỮ LIỆU
# ==========================================
data_lock = threading.Lock()
CLASSES = {f"Lớp học {i}": f"lop{i}" for i in range(1, 11)}

# MẬT KHẨU TỰ ĐỘNG
PASSWORDS = {}
for i in range(1, 9): PASSWORDS[f"lop{i}"] = f"T05-{i}"
for i in range(9, 11): PASSWORDS[f"lop{i}"] = f"LH{i}"

if 'logged_in' not in st.session_state: st.session_state.update({'logged_in': False, 'role': '', 'class_id': ''})

def get_path(cls, act): return f"data_{cls}_{act}.csv"

def save_data(cls, act, name, content):
    # content có thể là chuỗi hoặc số liệu phức tạp
    content = str(content).replace("|", "-").replace("\n", " ")
    timestamp = datetime.now().strftime("%H:%M:%S")
    row = f"{name}|{content}|{timestamp}\n"
    with data_lock:
        with open(get_path(cls, act), "a", encoding="utf-8") as f: f.write(row)

def load_data(cls, act):
    path = get_path(cls, act)
    if os.path.exists(path):
        try:
            return pd.read_csv(path, sep="|", names=["Học viên", "Nội dung", "Thời gian"])
        except: return pd.DataFrame(columns=["Học viên", "Nội dung", "Thời gian"])
    return pd.DataFrame(columns=["Học viên", "Nội dung", "Thời gian"])

def clear_activity(cls, act):
    with data_lock:
        path = get_path(cls, act)
        if os.path.exists(path): os.remove(path)

# ==========================================
# 3. MÀN HÌNH ĐĂNG NHẬP
# ==========================================
if not st.session_state['logged_in']:
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown(f"""
        <div class="login-box">
            <img src="{LOGO_URL}" width="100">
            <h2 style="color:{PRIMARY_COLOR}; margin-top:15px;">TRƯỜNG ĐH CẢNH SÁT NHÂN DÂN</h2>
            <p style="color:#64748b; font-weight:600;">HỆ THỐNG TƯƠNG TÁC ĐA PHƯƠNG TIỆN</p>
            <div style="text-align:left; background:#f1f5f9; padding:15px; border-radius:10px; margin:20px 0; font-size:14px; color:#334155;">
                <b>Khoa:</b> LLCT & KHXHNV<br>
                <b>Giảng viên:</b> Trần Nguyễn Sĩ Nguyên
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        tab_sv, tab_gv = st.tabs(["HỌC VIÊN", "GIẢNG VIÊN"])
        
        with tab_sv:
            c_class = st.selectbox("Chọn Lớp:", list(CLASSES.keys()))
            c_pass = st.text_input("Mã lớp:", type="password", placeholder="Ví dụ: T05-1")
            if st.button("THAM GIA LỚP HỌC"):
                cid = CLASSES[c_class]
                if c_pass.strip() == PASSWORDS[cid]:
                    st.session_state.update({'logged_in': True, 'role': 'student', 'class_id': cid})
                    st.rerun()
                else: st.error("Sai mã lớp!")
        
        with tab_gv:
            t_pass = st.text_input("Mật khẩu Admin:", type="password")
            if st.button("VÀO QUẢN TRỊ"):
                if t_pass == "T05":
                    st.session_state.update({'logged_in': True, 'role': 'teacher', 'class_id': 'lop1'})
                    st.rerun()
                else: st.error("Sai mật khẩu.")

# ==========================================
# 4. GIAO DIỆN CHÍNH (MENTIMETER FULL SUITE)
# ==========================================
else:
    # --- SIDEBAR ---
    with st.sidebar:
        st.image(LOGO_URL, width=80)
        st.markdown("---")
        st.caption("🎵 NHẠC NỀN")
        st.audio("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3")
        
        cls_txt = [k for k,v in CLASSES.items() if v==st.session_state['class_id']][0]
        role = "HỌC VIÊN" if st.session_state['role'] == 'student' else "GIẢNG VIÊN"
        
        st.info(f"👤 {role}\n\n🏫 {cls_txt}")
        
        if st.session_state['role'] == 'teacher':
            st.warning("CHUYỂN LỚP QUẢN LÝ")
            s_cls = st.selectbox("", list(CLASSES.keys()), label_visibility="collapsed")
            st.session_state['class_id'] = CLASSES[s_cls]

        st.markdown("---")
        # DANH SÁCH 6 TÍNH NĂNG MENTIMETER
        menu = st.radio("CHỌN HOẠT ĐỘNG", [
            "🏠 Dashboard",
            "1️⃣ Word Cloud (Từ khóa)",
            "2️⃣ Poll (Bình chọn)",
            "3️⃣ Open Ended (Hỏi đáp)",
            "4️⃣ Scales (Thang đo)",
            "5️⃣ Ranking (Xếp hạng)",
            "6️⃣ Pin on Image (Ghim ảnh)"
        ])
        
        st.markdown("---")
        if st.button("THOÁT"): st.session_state.clear(); st.rerun()

    # --- HEADER ---
    st.markdown(f"<h2 style='color:{PRIMARY_COLOR}; border-bottom:2px solid #e2e8f0; padding-bottom:10px;'>{menu}</h2>", unsafe_allow_html=True)

    # ==========================================
    # DASHBOARD
    # ==========================================
    if "Dashboard" in menu:
        cols = st.columns(3)
        activities = ["wordcloud", "poll", "openended", "scales", "ranking", "pin"]
        names = ["Word Cloud", "Poll", "Open Ended", "Scales", "Ranking", "Pin Image"]
        
        for i, act in enumerate(activities):
            df = load_data(st.session_state['class_id'], act)
            with cols[i % 3]:
                st.markdown(f"""
                <div class="viz-card" style="text-align:center;">
                    <h1 style="color:{PRIMARY_COLOR}; margin:0;">{len(df)}</h1>
                    <p style="color:#64748b; font-weight:600;">{names[i]}</p>
                </div>
                """, unsafe_allow_html=True)

    # ==========================================
    # 1. WORD CLOUD (Đám mây từ khóa)
    # ==========================================
    elif "Word Cloud" in menu:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.info("Chủ đề: **Cảm nhận của bạn về buổi học hôm nay?** (Nhập 1-3 từ)")
            if st.session_state['role'] == 'student':
                with st.form("f_wc"):
                    n = st.text_input("Tên:")
                    txt = st.text_input("Từ khóa:")
                    if st.form_submit_button("GỬI"):
                        save_data(st.session_state['class_id'], "wordcloud", n, txt)
                        st.success("Đã gửi!"); time.sleep(0.5); st.rerun()
        with c2:
            df = load_data(st.session_state['class_id'], "wordcloud")
            with st.container(border=True):
                if not df.empty:
                    text = " ".join(df["Nội dung"].astype(str))
                    wc = WordCloud(width=800, height=400, background_color='white', colormap='viridis').generate(text)
                    fig, ax = plt.subplots(); ax.imshow(wc, interpolation='bilinear'); ax.axis("off")
                    st.pyplot(fig)
                else: st.image("https://cdn-icons-png.flaticon.com/512/7486/7486831.png", width=100); st.caption("Chờ dữ liệu...")

    # ==========================================
    # 2. POLL (Bình chọn đa lựa chọn)
    # ==========================================
    elif "Poll" in menu:
        c1, c2 = st.columns([1, 2])
        options = ["Hoàn toàn đồng ý", "Phân vân", "Không đồng ý"]
        with c1:
            st.info("Câu hỏi: **AI có thể thay thế giảng viên trong tương lai?**")
            if st.session_state['role'] == 'student':
                with st.form("f_poll"):
                    n = st.text_input("Tên:")
                    vote = st.radio("Lựa chọn:", options)
                    if st.form_submit_button("BÌNH CHỌN"):
                        save_data(st.session_state['class_id'], "poll", n, vote)
                        st.success("Đã chọn!"); time.sleep(0.5); st.rerun()
        with c2:
            df = load_data(st.session_state['class_id'], "poll")
            with st.container(border=True):
                if not df.empty:
                    cnt = df["Nội dung"].value_counts().reset_index()
                    cnt.columns = ["Lựa chọn", "Số lượng"]
                    fig = px.pie(cnt, values="Số lượng", names="Lựa chọn", hole=0.4, color_discrete_sequence=px.colors.qualitative.Set2)
                    st.plotly_chart(fig, use_container_width=True)
                else: st.caption("Chưa có bình chọn.")

    # ==========================================
    # 3. OPEN ENDED (Câu hỏi mở / Bức tường ý kiến)
    # ==========================================
    elif "Open Ended" in menu:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.info("**Những thách thức lớn nhất của Chuyển đổi số là gì?**")
            if st.session_state['role'] == 'student':
                with st.form("f_open"):
                    n = st.text_input("Tên:")
                    c = st.text_area("Câu trả lời:")
                    if st.form_submit_button("GỬI BÀI"):
                        save_data(st.session_state['class_id'], "openended", n, c)
                        st.success("Đã gửi!"); time.sleep(0.5); st.rerun()
        with c2:
            df = load_data(st.session_state['class_id'], "openended")
            with st.container(border=True, height=500):
                if not df.empty:
                    for i, r in df.iterrows():
                        st.markdown(f'<div class="note-card"><b>{r["Học viên"]}</b>: {r["Nội dung"]}</div>', unsafe_allow_html=True)
                else: st.caption("Sàn ý kiến trống.")

    # ==========================================
    # 4. SCALES (Thang đo / Spider Chart)
    # ==========================================
    elif "Scales" in menu:
        c1, c2 = st.columns([1, 2])
        criteria = ["Kỹ năng tra cứu", "Tư duy phản biện", "Làm việc nhóm"]
        with c1:
            st.info("**Tự đánh giá năng lực bản thân (Thang điểm 1-5)**")
            if st.session_state['role'] == 'student':
                with st.form("f_scale"):
                    n = st.text_input("Tên:")
                    s1 = st.slider(criteria[0], 1, 5, 3)
                    s2 = st.slider(criteria[1], 1, 5, 3)
                    s3 = st.slider(criteria[2], 1, 5, 3)
                    if st.form_submit_button("GỬI ĐÁNH GIÁ"):
                        # Lưu dạng: 3,4,5
                        val = f"{s1},{s2},{s3}"
                        save_data(st.session_state['class_id'], "scales", n, val)
                        st.success("Đã lưu!"); time.sleep(0.5); st.rerun()
        with c2:
            df = load_data(st.session_state['class_id'], "scales")
            with st.container(border=True):
                if not df.empty:
                    # Tính trung bình
                    try:
                        data_matrix = []
                        for item in df["Nội dung"]:
                            data_matrix.append([int(x) for x in item.split(',')])
                        avg = np.mean(data_matrix, axis=0)
                        
                        fig = go.Figure(data=go.Scatterpolar(
                            r=avg, theta=criteria, fill='toself', name='Lớp học'
                        ))
                        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5])), showlegend=False)
                        st.plotly_chart(fig, use_container_width=True)
                    except: st.error("Lỗi định dạng dữ liệu.")
                else: st.caption("Chưa có dữ liệu thang đo.")

    # ==========================================
    # 5. RANKING (Xếp hạng ưu tiên)
    # ==========================================
    elif "Ranking" in menu:
        c1, c2 = st.columns([1, 2])
        items = ["Nhân lực", "Công nghệ", "Chính sách", "Vốn"]
        with c1:
            st.info("**Sắp xếp mức độ ưu tiên (Quan trọng nhất lên đầu)**")
            if st.session_state['role'] == 'student':
                with st.form("f_rank"):
                    n = st.text_input("Tên:")
                    rank = st.multiselect("Thứ tự ưu tiên:", items)
                    if st.form_submit_button("NỘP BẢNG XẾP HẠNG"):
                        if len(rank) == len(items):
                            save_data(st.session_state['class_id'], "ranking", n, "->".join(rank))
                            st.success("Đã nộp!"); time.sleep(0.5); st.rerun()
                        else: st.warning(f"Vui lòng chọn đủ {len(items)} mục.")
        with c2:
            df = load_data(st.session_state['class_id'], "ranking")
            with st.container(border=True):
                if not df.empty:
                    # Tính điểm trọng số (Vị trí 1 = 4 điểm, Vị trí 4 = 1 điểm)
                    scores = {k: 0 for k in items}
                    for r in df["Nội dung"]:
                        parts = r.split("->")
                        for idx, item in enumerate(parts):
                            scores[item] += (len(items) - idx)
                    
                    sorted_scores = dict(sorted(scores.items(), key=lambda item: item[1]))
                    fig = px.bar(x=list(sorted_scores.values()), y=list(sorted_scores.keys()), orientation='h', labels={'x':'Điểm số', 'y':'Hạng mục'})
                    st.plotly_chart(fig, use_container_width=True)
                else: st.caption("Chưa có xếp hạng.")

    # ==========================================
    # 6. PIN ON IMAGE (Ghim ảnh / Heatmap)
    # ==========================================
    elif "Pin on Image" in menu:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.info("**Ghim vị trí của bạn trên bản đồ (Mô phỏng)**")
            if st.session_state['role'] == 'student':
                with st.form("f_pin"):
                    n = st.text_input("Tên:")
                    # Giả lập tọa độ bằng thanh trượt
                    x = st.slider("Tọa độ Ngang (X)", 0, 100, 50)
                    y = st.slider("Tọa độ Dọc (Y)", 0, 100, 50)
                    if st.form_submit_button("GHIM VỊ TRÍ"):
                        save_data(st.session_state['class_id'], "pin", n, f"{x},{y}")
                        st.success("Đã ghim!"); time.sleep(0.5); st.rerun()
        with c2:
            df = load_data(st.session_state['class_id'], "pin")
            with st.container(border=True):
                # Vẽ biểu đồ Scatter mô phỏng trên nền ảnh
                if not df.empty:
                    try:
                        xs, ys = [], []
                        for item in df["Nội dung"]:
                            coords = item.split(',')
                            xs.append(int(coords[0])); ys.append(int(coords[1]))
                        
                        fig = go.Figure()
                        # Thêm ảnh nền (Mô phỏng bằng Layout Image của Plotly rất phức tạp khi dùng URL, 
                        # nên ở đây ta dùng Scatter plot trên nền trắng hoặc lưới để đơn giản hóa cho Streamlit Cloud)
                        fig.add_trace(go.Scatter(x=xs, y=ys, mode='markers', marker=dict(size=15, color='red', opacity=0.6)))
                        fig.update_layout(
                            xaxis=dict(range=[0, 100], showgrid=False),
                            yaxis=dict(range=[0, 100], showgrid=False),
                            width=600, height=400, title="Bản đồ nhiệt lớp học"
                        )
                        st.plotly_chart(fig)
                    except: st.error("Lỗi dữ liệu pin.")
                else: st.caption("Chưa có ghim nào.")

    # ==========================================
    # CONTROL PANEL (CHUNG CHO MỌI TAB)
    # ==========================================
    if st.session_state['role'] == 'teacher':
        st.markdown("---")
        with st.expander("👮‍♂️ BẢNG ĐIỀU KHIỂN GIẢNG VIÊN (Dành riêng cho Tab này)", expanded=True):
            act_key = menu.split(" ")[1].lower() # Lấy từ khóa làm key (wordcloud, poll...)
            if "pin" in act_key: act_key = "pin"
            
            c_ai, c_del = st.columns([3, 1])
            with c_ai:
                prompt = st.text_input("Yêu cầu AI phân tích:", placeholder=f"Phân tích kết quả {menu}...")
                if st.button("PHÂN TÍCH NGAY") and prompt:
                    df_curr = load_data(st.session_state['class_id'], act_key)
                    if not df_curr.empty:
                        with st.spinner("AI đang xử lý..."):
                            st.info(model.generate_content(f"Dữ liệu {menu}: {df_curr.to_string()}. Yêu cầu: {prompt}").text)
                    else: st.warning("Chưa có dữ liệu để phân tích.")
            
            with c_del:
                if st.button(f"🗑 RESET {menu}", type="primary"):
                    clear_activity(st.session_state['class_id'], act_key)
                    st.toast(f"Đã xóa dữ liệu {menu}"); time.sleep(1); st.rerun()
