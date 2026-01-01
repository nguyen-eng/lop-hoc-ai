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
import numpy as np

# ==========================================
# 1. CẤU HÌNH & GIAO DIỆN (UI/UX)
# ==========================================
st.set_page_config(
    page_title="T05 Interactive Class",
    page_icon="📶",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- TÀI NGUYÊN ---
LOGO_URL = "https://drive.google.com/thumbnail?id=1PsUr01oeleJkW2JB1gqnID9WJNsTMFGW&sz=w1000"
# Ảnh nền cho hoạt động Pin (Thầy có thể thay link ảnh bản đồ VN hoặc sơ đồ chiến thuật vào đây)
MAP_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/Blank_map_of_Vietnam.svg/858px-Blank_map_of_Vietnam.svg.png"

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
    
    /* VIZ CARD (Khung hiển thị biểu đồ) */
    .viz-card {{
        background: white; padding: 25px; border-radius: 16px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        margin-bottom: 20px; border: 1px solid #e2e8f0;
    }}
    
    /* INPUT FORM */
    .stTextInput input, .stTextArea textarea {{
        border: 2px solid #e2e8f0; border-radius: 12px; padding: 12px;
    }}
    
    /* BUTTONS */
    div.stButton > button {{
        background-color: {PRIMARY_COLOR}; color: white; border: none;
        border-radius: 50px; padding: 12px 24px; font-weight: 700;
        text-transform: uppercase; letter-spacing: 1px; width: 100%;
        box-shadow: 0 4px 15px rgba(0, 106, 78, 0.3);
    }}
    div.stButton > button:hover {{ background-color: #00503a; transform: translateY(-2px); }}
    
    /* NOTE CARD (Open Ended) */
    .note-card {{
        background: #fff; padding: 15px; border-radius: 12px;
        border-left: 5px solid {PRIMARY_COLOR}; margin-bottom: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08); font-size: 15px;
    }}
    
    /* SIDEBAR */
    [data-testid="stSidebar"] {{ background-color: #111827; }}
    [data-testid="stSidebar"] * {{ color: #ffffff; }}
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
CLASSES = {f"Lớp học {i}": f"lop{i}" for i in range(1, 11)}

PASSWORDS = {}
for i in range(1, 9): PASSWORDS[f"lop{i}"] = f"T05-{i}"
for i in range(9, 11): PASSWORDS[f"lop{i}"] = f"LH{i}"

if 'logged_in' not in st.session_state: st.session_state.update({'logged_in': False, 'role': '', 'class_id': ''})

def get_path(cls, act): return f"data_{cls}_{act}.csv"

def save_data(cls, act, name, content):
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
            <p style="color:#64748b; font-weight:600;">HỆ THỐNG TƯƠNG TÁC LỚP HỌC</p>
            <div style="text-align:left; background:#f1f5f9; padding:15px; border-radius:10px; margin:20px 0; font-size:14px; color:#334155;">
                <b>Khoa:</b> LLCT & KHXHNV<br>
                <b>Giảng viên:</b> Trần Nguyễn Sĩ Nguyên
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        tab_sv, tab_gv = st.tabs(["CỔNG HỌC VIÊN", "CỔNG GIẢNG VIÊN"])
        
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
# 4. GIAO DIỆN CHÍNH (FULL INTERACTIVE)
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
        # DANH SÁCH HOẠT ĐỘNG
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

    # Lấy key hoạt động để lưu file
    act_map = {
        "1️⃣ Word Cloud (Từ khóa)": "wordcloud",
        "2️⃣ Poll (Bình chọn)": "poll",
        "3️⃣ Open Ended (Hỏi đáp)": "openended",
        "4️⃣ Scales (Thang đo)": "scales",
        "5️⃣ Ranking (Xếp hạng)": "ranking",
        "6️⃣ Pin on Image (Ghim ảnh)": "pin"
    }
    current_act_key = act_map.get(menu, "dashboard")

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
                    <h1 style="color:{PRIMARY_COLOR}; margin:0; font-size:40px;">{len(df)}</h1>
                    <p style="color:#64748b; font-weight:600; text-transform:uppercase;">{names[i]}</p>
                </div>
                """, unsafe_allow_html=True)

    # ==========================================
    # 1. WORD CLOUD
    # ==========================================
    elif "Word Cloud" in menu:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.info("Câu hỏi: **Từ khóa nào mô tả đúng nhất về Chuyển đổi số?**")
            # FORM NHẬP CHO HỌC VIÊN
            if st.session_state['role'] == 'student':
                with st.form("f_wc"):
                    n = st.text_input("Tên:")
                    txt = st.text_input("Nhập 1 từ khóa:")
                    if st.form_submit_button("GỬI TỪ KHÓA"):
                        save_data(st.session_state['class_id'], current_act_key, n, txt)
                        st.success("Đã gửi!"); time.sleep(0.5); st.rerun()
            else: st.warning("Giảng viên xem kết quả bên phải.")
            
        with c2:
            st.markdown("##### ☁️ KẾT QUẢ HIỂN THỊ")
            df = load_data(st.session_state['class_id'], current_act_key)
            with st.container(border=True):
                if not df.empty:
                    text = " ".join(df["Nội dung"].astype(str))
                    # Tạo Wordcloud
                    wc = WordCloud(width=800, height=400, background_color='white', colormap='ocean').generate(text)
                    fig, ax = plt.subplots(); ax.imshow(wc, interpolation='bilinear'); ax.axis("off")
                    st.pyplot(fig)
                else: st.info("Chưa có dữ liệu. Mời lớp nhập từ khóa.")

    # ==========================================
    # 2. POLL (BÌNH CHỌN)
    # ==========================================
    elif "Poll" in menu:
        c1, c2 = st.columns([1, 2])
        options = ["Phương án A", "Phương án B", "Phương án C", "Phương án D"]
        with c1:
            st.info("Câu hỏi: **Theo bạn, giải pháp nào là tối ưu nhất?**")
            if st.session_state['role'] == 'student':
                with st.form("f_poll"):
                    n = st.text_input("Tên:")
                    vote = st.radio("Lựa chọn:", options)
                    if st.form_submit_button("BÌNH CHỌN"):
                        save_data(st.session_state['class_id'], current_act_key, n, vote)
                        st.success("Đã chọn!"); time.sleep(0.5); st.rerun()
        with c2:
            st.markdown("##### 📊 THỐNG KÊ LỰA CHỌN")
            df = load_data(st.session_state['class_id'], current_act_key)
            with st.container(border=True):
                if not df.empty:
                    cnt = df["Nội dung"].value_counts().reset_index()
                    cnt.columns = ["Lựa chọn", "Số lượng"]
                    fig = px.bar(cnt, x="Lựa chọn", y="Số lượng", color="Lựa chọn", text_auto=True)
                    st.plotly_chart(fig, use_container_width=True)
                else: st.info("Chưa có bình chọn nào.")

    # ==========================================
    # 3. OPEN ENDED (CÂU HỎI MỞ)
    # ==========================================
    elif "Open Ended" in menu:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.info("**Hãy chia sẻ một khó khăn bạn đang gặp phải?**")
            if st.session_state['role'] == 'student':
                with st.form("f_open"):
                    n = st.text_input("Tên:")
                    c = st.text_area("Câu trả lời của bạn:")
                    if st.form_submit_button("GỬI BÀI"):
                        save_data(st.session_state['class_id'], current_act_key, n, c)
                        st.success("Đã gửi!"); time.sleep(0.5); st.rerun()
        with c2:
            st.markdown("##### 💬 BỨC TƯỜNG Ý KIẾN")
            df = load_data(st.session_state['class_id'], current_act_key)
            with st.container(border=True, height=500): # Cho phép cuộn
                if not df.empty:
                    for i, r in df.iterrows():
                        st.markdown(f'<div class="note-card"><b>{r["Học viên"]}</b>: {r["Nội dung"]}</div>', unsafe_allow_html=True)
                else: st.info("Sàn ý kiến trống.")

    # ==========================================
    # 4. SCALES (THANG ĐO - SPIDER WEB)
    # ==========================================
    elif "Scales" in menu:
        c1, c2 = st.columns([1, 2])
        criteria = ["Kỹ năng A", "Kỹ năng B", "Kỹ năng C", "Kỹ năng D"]
        with c1:
            st.info("**Đánh giá mức độ đồng ý (1: Thấp - 5: Cao)**")
            if st.session_state['role'] == 'student':
                with st.form("f_scale"):
                    n = st.text_input("Tên:")
                    scores = []
                    for cri in criteria:
                        scores.append(st.slider(cri, 1, 5, 3))
                    if st.form_submit_button("GỬI ĐÁNH GIÁ"):
                        # Lưu dạng chuỗi: "3,4,5,2"
                        val = ",".join(map(str, scores))
                        save_data(st.session_state['class_id'], current_act_key, n, val)
                        st.success("Đã lưu!"); time.sleep(0.5); st.rerun()
        with c2:
            st.markdown("##### 🕸️ MẠNG NHỆN NĂNG LỰC")
            df = load_data(st.session_state['class_id'], current_act_key)
            with st.container(border=True):
                if not df.empty:
                    try:
                        # Tính trung bình các cột
                        data_matrix = []
                        for item in df["Nội dung"]:
                            data_matrix.append([int(x) for x in item.split(',')])
                        
                        # Tính trung bình dọc
                        if len(data_matrix) > 0:
                            avg_scores = np.mean(data_matrix, axis=0)
                            
                            # Vẽ Radar Chart
                            fig = go.Figure(data=go.Scatterpolar(
                                r=avg_scores, theta=criteria, fill='toself', name='Lớp học'
                            ))
                            fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 5])), showlegend=False)
                            st.plotly_chart(fig, use_container_width=True)
                    except: st.error("Dữ liệu lỗi định dạng.")
                else: st.info("Chưa có dữ liệu thang đo.")

    # ==========================================
    # 5. RANKING (XẾP HẠNG)
    # ==========================================
    elif "Ranking" in menu:
        c1, c2 = st.columns([1, 2])
        items = ["Tiêu chí 1", "Tiêu chí 2", "Tiêu chí 3", "Tiêu chí 4"]
        with c1:
            st.info("**Sắp xếp thứ tự ưu tiên (Quan trọng nhất lên đầu)**")
            if st.session_state['role'] == 'student':
                with st.form("f_rank"):
                    n = st.text_input("Tên:")
                    rank = st.multiselect("Thứ tự:", items)
                    if st.form_submit_button("NỘP BẢNG XẾP HẠNG"):
                        if len(rank) == len(items):
                            save_data(st.session_state['class_id'], current_act_key, n, "->".join(rank))
                            st.success("Đã nộp!"); time.sleep(0.5); st.rerun()
                        else: st.warning(f"Vui lòng chọn đủ {len(items)} mục.")
        with c2:
            st.markdown("##### 🏆 KẾT QUẢ XẾP HẠNG")
            df = load_data(st.session_state['class_id'], current_act_key)
            with st.container(border=True):
                if not df.empty:
                    # Tính điểm trọng số: Vị trí 1 = 4đ, Vị trí 4 = 1đ
                    scores = {k: 0 for k in items}
                    for r in df["Nội dung"]:
                        parts = r.split("->")
                        for idx, item in enumerate(parts):
                            scores[item] += (len(items) - idx) # Công thức điểm
                    
                    # Sắp xếp để vẽ
                    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
                    labels = [x[0] for x in sorted_items]
                    vals = [x[1] for x in sorted_items]
                    
                    fig = px.bar(x=vals, y=labels, orientation='h', labels={'x':'Tổng điểm', 'y':'Mục'}, text=vals)
                    fig.update_layout(yaxis={'categoryorder':'total ascending'})
                    st.plotly_chart(fig, use_container_width=True)
                else: st.info("Chưa có xếp hạng.")

    # ==========================================
    # 6. PIN ON IMAGE (GHIM ẢNH)
    # ==========================================
    elif "Pin on Image" in menu:
        c1, c2 = st.columns([1, 2])
        with c1:
            st.info("**Ghim vị trí bạn chọn trên bản đồ**")
            if st.session_state['role'] == 'student':
                with st.form("f_pin"):
                    n = st.text_input("Tên:")
                    # Dùng Slider để giả lập tọa độ X, Y (0-100%)
                    x_val = st.slider("Vị trí Ngang (Trái -> Phải)", 0, 100, 50)
                    y_val = st.slider("Vị trí Dọc (Dưới -> Trên)", 0, 100, 50)
                    if st.form_submit_button("GHIM VỊ TRÍ"):
                        save_data(st.session_state['class_id'], current_act_key, n, f"{x_val},{y_val}")
                        st.success("Đã ghim!"); time.sleep(0.5); st.rerun()
        with c2:
            st.markdown("##### 📍 BẢN ĐỒ NHIỆT (HEATMAP)")
            df = load_data(st.session_state['class_id'], current_act_key)
            with st.container(border=True):
                if not df.empty:
                    try:
                        xs = []
                        ys = []
                        for item in df["Nội dung"]:
                            coords = item.split(',')
                            xs.append(int(coords[0]))
                            ys.append(int(coords[1]))
                        
                        fig = go.Figure()
                        # Vẽ các điểm ghim
                        fig.add_trace(go.Scatter(
                            x=xs, y=ys, mode='markers',
                            marker=dict(size=12, color='red', opacity=0.7, line=dict(width=1, color='white')),
                            name='Vị trí ghim'
                        ))
                        
                        # Cấu hình trục để giống khung ảnh (0-100)
                        fig.update_layout(
                            xaxis=dict(range=[0, 100], showgrid=False, zeroline=False, visible=False),
                            yaxis=dict(range=[0, 100], showgrid=False, zeroline=False, visible=False),
                            images=[dict(
                                source=MAP_IMAGE, # Link ảnh nền
                                xref="x", yref="y",
                                x=0, y=100, sizex=100, sizey=100,
                                sizing="stretch", layer="below"
                            )],
                            width=600, height=400, margin=dict(l=0, r=0, t=0, b=0)
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    except: st.error("Lỗi dữ liệu ghim.")
                else: st.info("Chưa có ghim nào.")

    # ==========================================
    # CONTROL PANEL CHO GIẢNG VIÊN (CHUNG CHO MỌI TAB)
    # ==========================================
    if st.session_state['role'] == 'teacher' and "Dashboard" not in menu:
        st.markdown("---")
        with st.expander("👮‍♂️ BẢNG ĐIỀU KHIỂN GIẢNG VIÊN (Dành riêng cho hoạt động này)", expanded=True):
            col_ai, col_reset = st.columns([3, 1])
            
            with col_ai:
                st.markdown("###### 🤖 AI Trợ giảng")
                prompt = st.text_input("Nhập lệnh cho AI:", placeholder=f"Ví dụ: Phân tích xu hướng của {menu}...")
                if st.button("PHÂN TÍCH NGAY") and prompt:
                    curr_df = load_data(st.session_state['class_id'], current_act_key)
                    if not curr_df.empty:
                        with st.spinner("AI đang suy nghĩ..."):
                            res = model.generate_content(f"Dữ liệu {menu}: {curr_df.to_string()}. Yêu cầu: {prompt}")
                            st.info(res.text)
                    else: st.warning("Chưa có dữ liệu để phân tích.")
            
            with col_reset:
                st.markdown("###### 🗑 Xóa dữ liệu")
                if st.button(f"RESET {menu}", type="secondary"):
                    clear_activity(st.session_state['class_id'], current_act_key)
                    st.toast(f"Đã xóa sạch dữ liệu {menu}"); time.sleep(1); st.rerun()
