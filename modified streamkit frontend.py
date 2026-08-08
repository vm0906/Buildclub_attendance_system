import streamlit as st
import pandas as pd
import numpy as np
import os
import requests
import subprocess
import sys
from datetime import datetime
from PIL import Image

# ---------------------------------------------------------
# API Configuration
# ---------------------------------------------------------
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8000")

def api_get(endpoint):
    try:
        r = requests.get(f"{API_BASE}{endpoint}", timeout=3)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        return {}

def api_post(endpoint, json_data=None):
    try:
        r = requests.post(f"{API_BASE}{endpoint}", json=json_data, timeout=3)
        return r.json() if r.status_code in [200, 201] else {}
    except Exception:
        return {}

# ---------------------------------------------------------
# 1. Page Configuration
# ---------------------------------------------------------
st.set_page_config(
    page_title="Build Club - Makerspace Hub",
    page_icon="⚡",
    layout="wide"
)

# ---------------------------------------------------------
# 2. Custom CSS
# ---------------------------------------------------------
st.markdown("""
<style>
    .stApp {
        background-color: #eaece4 !important;
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
        color: #1a1c18;
    }
    .header-title {
        font-size: 2.3rem;
        font-weight: 800;
        color: #11130f;
        margin-bottom: 2px;
    }
    .header-subtitle {
        color: #63685e;
        font-size: 0.95rem;
        font-weight: 500;
        margin-bottom: 20px;
    }
    .standby-box {
        background-color: #dbe5ed;
        color: #1d4ed8;
        padding: 16px 20px;
        border-radius: 12px;
        font-size: 0.95rem;
        font-weight: 500;
        margin-bottom: 25px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    div.stButton > button[kind="secondary"] {
        background-color: #1c2b1e !important;
        color: #86efac !important;
        border: none !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        padding: 10px 20px !important;
    }
    div.stButton > button[kind="secondary"]:hover {
        background-color: #273d2a !important;
        color: #bbf7d0 !important;
    }
    .bento-card {
        background-color: #ffffff;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.02);
        border: 1px solid #e1e4da;
        margin-bottom: 20px;
    }
    .status-active {
        background-color: #dcfce7;
        color: #15803d;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.82rem;
        font-weight: 600;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 800;
        color: #11130f;
        margin-bottom: 4px;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #63685e;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 3. Data Storage & Initialization
# ---------------------------------------------------------
UPLOADS_DIR = "uploaded_proofs"
CSV_FILE = "attendance_records.csv"
os.makedirs(UPLOADS_DIR, exist_ok=True)

EXPECTED_PROJECT_COLS = ["Record ID", "Member Name", "In-Timing", "Out-Timing", "Duration (Hrs)", "Project Name", "Status", "Remarks", "Category", "Progress", "Camera Verified", "Timestamp", "Image Path"]

def load_and_fix_projects():
    data = api_get("/api/projects")
    if isinstance(data, list) and len(data) > 0:
        df = pd.DataFrame(data)
        for col in EXPECTED_PROJECT_COLS:
            if col not in df.columns:
                df[col] = ""
        return df
    return pd.DataFrame(columns=EXPECTED_PROJECT_COLS)

def get_attendance_data():
    """Reads attendance via API with direct local CSV fallback."""
    res = api_get("/api/attendance")
    records = res.get("attendance", []) if isinstance(res, dict) else []
    
    if not records and os.path.exists(CSV_FILE):
        try:
            df = pd.read_csv(CSV_FILE)
            records = df.to_dict(orient="records")
        except Exception:
            records = []
    return records

df_projects = load_and_fix_projects()

# ---------------------------------------------------------
# 4. Session State Management (Fixes Auto-Logout Bug)
# ---------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "camera_process" not in st.session_state:
    st.session_state.camera_process = None

if not st.session_state.logged_in:
    col_a, col_b, col_c = st.columns([1, 1.5, 1])
    with col_b:
        st.markdown("""
        <div class="bento-card" style="text-align: center; margin-top: 50px;">
            <h2>⚡ Build Club Portal</h2>
            <p style="color: #6b7280;">Log in to access your makerspace hub</p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form"):
            user_input = st.text_input("Username or Email", value="Lakshmi")
            pass_input = st.text_input("Password", type="password", value="123")
            submit_login = st.form_submit_button("Access Portal", type="primary", use_container_width=True)
            
            if submit_login:
                if user_input and pass_input:
                    st.session_state.logged_in = True
                    st.session_state.username = user_input
                    st.rerun()
                else:
                    st.error("Please enter both fields.")
    st.stop()

# ---------------------------------------------------------
# 5. Sidebar Navigation & Camera Process Manager
# ---------------------------------------------------------
st.sidebar.markdown(f"### 👤 {st.session_state.username}")
st.sidebar.caption("Portal Manager")
st.sidebar.divider()

# OpenCV Camera Process Control
st.sidebar.markdown("### 🎥 Camera System Control")

camera_running = st.session_state.camera_process is not None and st.session_state.camera_process.poll() is None

if camera_running:
    st.sidebar.success("🟢 Camera Active")
    if st.sidebar.button("🛑 Stop Camera Pipeline", type="secondary", use_container_width=True):
        st.session_state.camera_process.terminate()
        st.session_state.camera_process = None
        st.sidebar.info("Camera stopped.")
        st.rerun()
else:
    st.sidebar.warning("⚪ Camera Offline")
    if st.sidebar.button("🚀 Start Camera Pipeline", type="primary", use_container_width=True):
        camera_script = "Main.py" if os.path.exists("Main.py") else "main.py"
        if os.path.exists(camera_script):
            st.session_state.camera_process = subprocess.Popen([sys.executable, camera_script])
            st.sidebar.success("Camera started!")
            st.rerun()
        else:
            st.sidebar.error("Neither `Main.py` nor `main.py` was found.")

st.sidebar.divider()

nav = st.sidebar.radio(
    "Menu Navigation", 
    [
        "📊 Today's Overview", 
        "📤 Submit & Upload Project", 
        "📅 Timetable & Attendance", 
        "🤖 Member 1 OpenCV Logs"
    ]
)

# ---------------------------------------------------------
# HEADER SECTION
# ---------------------------------------------------------
head_col1, head_col2 = st.columns([3.5, 1])

with head_col1:
    st.markdown('<div class="header-title">Today\'s Overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="header-subtitle">Live Makerspace Attendance, Member Timings & Project Milestones</div>', unsafe_allow_html=True)

with head_col2:
    st.write("")
    if st.button("🔒 Lock Console", type="secondary", use_container_width=True):
        if st.session_state.camera_process and st.session_state.camera_process.poll() is None:
            st.session_state.camera_process.terminate()
            st.session_state.camera_process = None
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

status_str = "🟢 **Camera Active:** Process running and updating records." if camera_running else "📌 **System Standby:** Awaiting camera launch or check-in signals."
st.markdown(f"""
<div class="standby-box">
    {status_str}
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# TAB 1: Today's Overview
# ---------------------------------------------------------
if nav == "📊 Today's Overview":
    stats = api_get("/api/stats")
    live_data = api_get("/api/live-members")
    attendance_list = get_attendance_data()

    # Dynamic fallback: Calculate metrics directly from camera records CSV if API metrics are missing or zero
    if attendance_list:
        df_att = pd.DataFrame(attendance_list)
        name_col = "Member Name" if "Member Name" in df_att.columns else ("member_name" if "member_name" in df_att.columns else None)
        total_members = len(df_att[name_col].unique()) if name_col else len(df_att)
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        time_col = "Last Active" if "Last Active" in df_att.columns else ("entry_time" if "entry_time" in df_att.columns else None)
        
        if time_col:
            present_today = len(df_att[df_att[time_col].astype(str).str.startswith(today_str)])
            if present_today == 0:  # Fallback if dates in CSV are slightly formatted differently
                present_today = len(df_att)
        else:
            present_today = len(df_att)
            
        live_count = stats.get("live_members", present_today)
    else:
        live_count = stats.get("live_members", 0)
        total_members = stats.get("total_members", 0)
        present_today = stats.get("present_today", 0)

    absent_count = max(0, total_members - present_today)
    unknown_faces = stats.get("unknown_faces", 0)

    st.markdown("### 📊 Live Dashboard")
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    
    with m1:
        st.markdown(f'<div class="metric-value">{live_count}</div><div class="metric-label">🟢 Live Members</div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="metric-value">{present_today}</div><div class="metric-label">📅 Present Today</div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="metric-value">{absent_count}</div><div class="metric-label">⚪ Absent</div>', unsafe_allow_html=True)
    with m4:
        st.markdown(f'<div class="metric-value">{total_members}</div><div class="metric-label">👥 Total Members</div>', unsafe_allow_html=True)
    with m5:
        st.markdown(f'<div class="metric-value">{unknown_faces}</div><div class="metric-label">❓ Unknown Faces</div>', unsafe_allow_html=True)
    with m6:
        st.markdown(f'<div class="metric-value">{len(df_projects)}</div><div class="metric-label">🛠️ Projects</div>', unsafe_allow_html=True)

    st.divider()

    tab1, tab2, tab3 = st.tabs(["📜 Live Member Session Logs", "🛠️ Admin Remarks & Status Editor", "🧵 Audit Export"])

    with tab1:
        st.markdown("### Real-Time In/Out & Project Milestones")
        
        live_members = live_data.get("live_members", [])
        if live_members:
            live_df = pd.DataFrame(live_members)
            st.dataframe(live_df, use_container_width=True, hide_index=True)
        else:
            st.info("No active members currently on-site.")

        st.markdown("#### 📋 Recent Attendance & Camera Logs")
        if attendance_list:
            recent_df = pd.DataFrame(attendance_list)
            st.dataframe(recent_df, use_container_width=True, hide_index=True)
        else:
            st.info("No attendance records registered yet.")

    with tab2:
        st.markdown("### 🛠️ Admin Status Editor")
        st.info("Edit session remarks or override project status here.")

    with tab3:
        st.markdown("### 🧵 Audit Export")
        if attendance_list:
            audit_df = pd.DataFrame(attendance_list)
            st.download_button("📥 Export CSV Audit Log", data=audit_df.to_csv(index=False), file_name="makerspace_audit_log.csv")
        else:
            st.info("No data to export.")

# ---------------------------------------------------------
# TAB 2: Upload Projects & Mark Completion
# ---------------------------------------------------------
elif nav == "📤 Submit & Upload Project":
    st.markdown("### 📤 Submit & Update Project Record")

    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.markdown('<div class="bento-card">', unsafe_allow_html=True)
        p_name = st.text_input("Project Name *", placeholder="e.g., Vision AI Portal")
        p_owner = st.text_input("Project Owner / Team", value=st.session_state.username)
        p_cat = st.selectbox("Category", ["Computer Vision", "Web Development", "Hardware / IoT", "Artificial Intelligence"])
        p_prog = st.slider("Completion Progress (%)", 0, 100, 50)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="bento-card">', unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Upload Completion Screenshot/Picture", type=["jpg", "png", "jpeg"])
        if uploaded_file is not None:
            st.image(Image.open(uploaded_file), caption="Upload Preview", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    if st.button("🚀 Save & Submit Project", type="primary", use_container_width=True):
        if not p_name.strip():
            st.error("⚠️ Please enter a Project Name.")
        else:
            img_path = ""
            if uploaded_file is not None:
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_name = "".join([c if c.isalnum() else "_" for c in p_name])
                img_path = os.path.join(UPLOADS_DIR, f"{safe_name}_{timestamp_str}.png")
                Image.open(uploaded_file).save(img_path)

            next_id = len(df_projects) + 1
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            payload = {
                "Record ID": next_id,
                "Member Name": p_owner.strip(),
                "In-Timing": now_str,
                "Out-Timing": "🟢 Active On-Site",
                "Duration (Hrs)": "None",
                "Project Name": p_name.strip(),
                "Status": "In Progress" if p_prog < 100 else "Completed",
                "Remarks": "Manual Upload",
                "Category": p_cat,
                "Progress": p_prog,
                "Camera Verified": "Verified ✅" if uploaded_file else "Pending ⏳",
                "Timestamp": datetime.now().strftime("%Y-%m-%d %I:%M %p"),
                "Image Path": img_path
            }

            result = api_post("/api/projects", payload)
            if result.get("status") == "saved":
                st.balloons()
                st.success(f"🎉 Project **'{p_name}'** successfully submitted!")
                st.rerun()
            else:
                st.error("Failed to save project to backend.")

    st.divider()
    st.markdown("### 📁 Existing Projects")
    projects_data = api_get("/api/projects")
    if isinstance(projects_data, list) and len(projects_data) > 0:
        proj_df = pd.DataFrame(projects_data)
        display_cols = ["Record ID", "Member Name", "Project Name", "Status", "Category", "Progress", "Timestamp"]
        available_cols = [c for c in display_cols if c in proj_df.columns]
        st.dataframe(proj_df[available_cols], use_container_width=True, hide_index=True)
    else:
        st.info("No projects submitted yet.")

# ---------------------------------------------------------
# TAB 3: Timetable & Attendance
# ---------------------------------------------------------
elif nav == "📅 Timetable & Attendance":
    st.markdown("### 📅 Build Club Timetable & Attendance Log")

    col_att, col_time = st.columns([1.2, 1], gap="large")

    with col_att:
        st.markdown('<div class="bento-card">', unsafe_allow_html=True)
        st.markdown("#### ⏱️ Quick Check-in")
        if st.button("✅ Mark My Attendance for Today"):
            result = api_post("/api/scan", {"member_name": st.session_state.username})
            if result:
                st.success(f"Attendance recorded for **{st.session_state.username}** on {datetime.now().strftime('%Y-%m-%d')}!")
            else:
                st.error("Backend connection failed.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="bento-card">', unsafe_allow_html=True)
        st.markdown("#### 📊 My Stats")
        my_stats = api_get(f"/api/member/{st.session_state.username}")
        if my_stats and "member_name" in my_stats:
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Today's Duration", my_stats.get("today_duration", "00:00:00"))
                st.metric("Weekly Duration", my_stats.get("weekly_duration", "00:00:00"))
            with c2:
                st.metric("Monthly Duration", my_stats.get("monthly_duration", "00:00:00"))
                st.metric("Total Visits", my_stats.get("total_visits", 0))
            if my_stats.get("is_active"):
                st.success("🟢 You are currently checked in.")
            else:
                st.info("⚪ You are not currently checked in.")
        else:
            st.info("No stats available for your account yet.")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_time:
        st.markdown('<div class="bento-card">', unsafe_allow_html=True)
        st.markdown("#### 🗓️ Weekly Schedule")
        timetable_data = [
            {"Day": "Monday", "Time": "04:00 PM", "Session": "Member 1 OpenCV Camera Testing"},
            {"Day": "Wednesday", "Time": "03:00 PM", "Session": "Dashboard & Web Portal Review"},
            {"Day": "Friday", "Time": "05:00 PM", "Session": "Build Club Weekly Project Submissions"}
        ]
        st.table(pd.DataFrame(timetable_data))
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="bento-card">', unsafe_allow_html=True)
        st.markdown("#### 📋 Today's Attendance")
        att_list = get_attendance_data()
        if att_list:
            today_str = datetime.now().strftime("%Y-%m-%d")
            today_records = [
                r for r in att_list 
                if str(r.get("entry_time") or r.get("Last Active") or r.get("Timestamp") or "").startswith(today_str)
            ]
            st.write(f"**Total check-ins today:** {len(today_records) if today_records else len(att_list)}")
            display_items = today_records if today_records else att_list
            for r in display_items[:5]:
                name = r.get("member_name") or r.get("Member Name") or "Unknown"
                entry = r.get("entry_time") or r.get("Last Active") or r.get("Timestamp") or "N/A"
                dur = r.get("duration", "Active")
                st.markdown(f"- **{name}** — {entry} — ⏱️ {dur}")
        else:
            st.info("No attendance records found.")
        st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------
# TAB 4: Member 1 OpenCV Camera Logs
# ---------------------------------------------------------
elif nav == "🤖 Member 1 OpenCV Logs":
    st.markdown("### 🤖 Member 1 OpenCV & Camera Verifications")

    projects_data = api_get("/api/projects")
    if isinstance(projects_data, list) and len(projects_data) > 0:
        proj_df = pd.DataFrame(projects_data)
        cv_records = proj_df[proj_df["Category"] == "Computer Vision"] if "Category" in proj_df.columns else pd.DataFrame()
    else:
        cv_records = pd.DataFrame()

    if cv_records.empty:
        st.info("No OpenCV camera logs recorded yet.")
    else:
        for idx, row in cv_records.iterrows():
            p_title = row.get("Project Name", "Project")
            p_owner = row.get("Member Name", "Member 1")
            p_time = row.get("In-Timing", "N/A")
            
            with st.expander(f"📷 {p_title} — {p_owner} ({p_time})"):
                c1, c2 = st.columns([1, 2])
                with c1:
                    path = str(row.get("Image Path", ""))
                    if path and os.path.exists(path):
                        st.image(path, use_container_width=True)
                    else:
                        st.info("No image captured.")
                with c2:
                    st.markdown(f"**Task:** {p_title}")
                    st.markdown(f"**Developer:** {p_owner}")
                    st.markdown(f"**Status:** {row.get('Status', 'In Progress')}")
                    st.markdown(f"**Remarks:** {row.get('Remarks', 'N/A')}")
                    st.markdown(f"**Progress:** {row.get('Progress', 0)}%")
                    st.markdown(f"**Camera Verified:** {row.get('Camera Verified', 'Pending ⏳')}")

                    image_path = row.get("Image Path", "")
                    if image_path and os.path.exists(image_path):
                        st.image(image_path, caption="Project Evidence", use_container_width=True)

                    st.markdown("---")
                    st.markdown("### 👤 Attendance Information")

                    if row.get("Out-Timing") == "🟢 Active On-Site":
                        st.success("Currently Present in Makerspace")
                    else:
                        st.info(f"Checked Out : {row.get('Out-Timing', 'N/A')}")

                    st.write(f"**In Time:** {row.get('In-Timing', 'N/A')}")
                    st.write(f"**Duration:** {row.get('Duration (Hrs)', 'N/A')}")

st.sidebar.markdown("---")
st.sidebar.success("✅ Build Club Smart Attendance System")
st.sidebar.caption("Powered by Face Recognition + FastAPI + Streamlit")