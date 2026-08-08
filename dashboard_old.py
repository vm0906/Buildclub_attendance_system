import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import datetime
from PIL import Image

# ---------------------------------------------------------
# Helper API Mock Functions (Ensure API calls won't crash if un-imported)
# ---------------------------------------------------------
def api_post(endpoint, payload=None):
    return {"status": "success", "username": payload.get("username") if payload else "", "success": True}

def api_get(endpoint):
    if "live-members" in endpoint:
        return []
    if "projects" in endpoint:
        return []
    if "member" in endpoint:
        return {"today_duration": "00:00:00", "weekly_duration": "00:00:00", "monthly_duration": "00:00:00", "total_visits": 0}
    if "attendance" in endpoint:
        return []
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
    /* Main Background */
    .stApp {
        background-color: #eaece4 !important;
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
        color: #1a1c18;
    }
    
    /* Top Header Styling */
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

    /* System Standby Blue Alert Box */
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

    /* Dark Lock Console Button */
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

    /* Cards & Containers */
    .bento-card {
        background-color: #ffffff;
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.02);
        border: 1px solid #e1e4da;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 3. Data Storage & Safe Auto-Repair Logic
# ---------------------------------------------------------
UPLOADS_DIR = "uploaded_proofs"
DATA_FILE = "project_records.csv"
ATTENDANCE_FILE = "attendance_records.csv"

os.makedirs(UPLOADS_DIR, exist_ok=True)

EXPECTED_PROJECT_COLS = ["Record ID", "Member Name", "In-Timing", "Out-Timing", "Duration (Hrs)", "Project Name", "Status", "Remarks", "Category", "Progress", "Camera Verified", "Timestamp", "Image Path"]

def load_and_fix_projects():
    if not os.path.exists(DATA_FILE):
        initial_projects = [
            {"Record ID": 3, "Member Name": "Ankur", "In-Timing": "2026-07-27 14:25:04", "Out-Timing": "🟢 Active On-Site", "Duration (Hrs)": "None", "Project Name": "Vision AI Portal", "Status": "In Progress", "Remarks": "Camera Auto-Scan", "Category": "Computer Vision", "Progress": 85, "Camera Verified": "Verified (OpenCV) ✅", "Timestamp": "2026-07-27 02:25 PM", "Image Path": ""},
            {"Record ID": 2, "Member Name": "Ankur", "In-Timing": "2026-07-27 14:25:04", "Out-Timing": "2026-07-27 14:25:04", "Duration (Hrs)": 0, "Project Name": "Vision AI Portal", "Status": "In Progress", "Remarks": "Camera Auto-Scan", "Category": "Computer Vision", "Progress": 85, "Camera Verified": "Verified (OpenCV) ✅", "Timestamp": "2026-07-27 02:25 PM", "Image Path": ""},
            {"Record ID": 1, "Member Name": "Ankur", "In-Timing": "2026-07-27 14:24:59", "Out-Timing": "2026-07-27 14:25:01", "Duration (Hrs)": 0, "Project Name": "Vision AI Portal", "Status": "In Progress", "Remarks": "Camera Auto-Scan", "Category": "Computer Vision", "Progress": 85, "Camera Verified": "Verified (OpenCV) ✅", "Timestamp": "2026-07-27 02:24 PM", "Image Path": ""}
        ]
        df = pd.DataFrame(initial_projects)
        df.to_csv(DATA_FILE, index=False)
        return df
    else:
        df = pd.read_csv(DATA_FILE)
        changed = False
        for col in EXPECTED_PROJECT_COLS:
            if col not in df.columns:
                if col == "Category": df[col] = "General"
                elif col == "Camera Verified": df[col] = "Pending ⏳"
                elif col == "Progress": df[col] = 50
                elif col == "Member Name": df[col] = "Member"
                elif col == "Status": df[col] = "In Progress"
                elif col == "Remarks": df[col] = "Manual Entry"
                else: df[col] = ""
                changed = True
        if changed:
            df.to_csv(DATA_FILE, index=False)
        return df

df_projects = load_and_fix_projects()

# ---------------------------------------------------------
# 4. Authentication Session State
# ---------------------------------------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    col_a, col_b, col_c = st.columns([1, 1.5, 1])
    with col_b:
        st.markdown("""
        <div class="bento-card" style="text-align: center; margin-top: 50px;">
            <h2>⚡ Build Club Portal</h2>
            <p style="color: #6b7280;">Log in to access your makerspace hub</p>
        </div>
        """, unsafe_allow_html=True)
        user_input = st.text_input(
            "Username or Email",
            value="admin@buildclub"
        )
        pass_input = st.text_input(
            "Password",
            type="password",
            value="srm123"
        )
        if st.button("Access Portal", type="primary", use_container_width=True):
            result = api_post("/api/login", {
                "username": user_input,
                "password": pass_input
            })
            if result.get("status") == "success":
                st.session_state.logged_in = True
                st.session_state.username = result.get("username", user_input)
                st.rerun()
            else:
                st.error("Invalid Username or Password")
                st.stop()
    st.stop()

# ---------------------------------------------------------
# 5. Sidebar Navigation
# ---------------------------------------------------------
st.sidebar.markdown(f"### 👤 {st.session_state.username}")
st.sidebar.caption("Portal Manager")
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
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

# Blue Alert Banner
st.markdown("""
<div class="standby-box">
    📌 <b>System Standby:</b> Awaiting camera feed check-in signals.
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# TAB 1: Today's Overview (Live Session Logs)
# ---------------------------------------------------------
if nav == "📊 Today's Overview":

    tab1, tab2, tab3 = st.tabs(["📜 Live Member Session Logs", "🛠️ Admin Remarks & Status Editor", "🧵 Audit Export"])

    with tab1:
        st.markdown("### Real-Time In/Out & Project Milestones")
        
        live_data = api_get("/api/live-members")
        if isinstance(live_data, list):
            live_members = live_data
        else:
            live_members = live_data.get("live_members", [])

        display_cols = ["Record ID", "Member Name", "In-Timing", "Out-Timing", "Duration (Hrs)", "Project Name", "Status", "Remarks"]
        available_cols = [c for c in display_cols if c in df_projects.columns]
        projects = api_get("/api/projects")

        if isinstance(projects, list) and len(projects) > 0:
            st.dataframe(
                pd.DataFrame(projects),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("No projects found.")

    with tab2:
        st.markdown("### 🛠️ Admin Status Editor")
        st.info("Edit session remarks or override project status here.")

    with tab3:
        st.markdown("### 🧵 Audit Export")
        st.download_button("📥 Export CSV Audit Log", data=df_projects.to_csv(index=False), file_name="makerspace_audit_log.csv")

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
                
                image = Image.open(uploaded_file)
                image = image.convert("RGB")
                image.save(img_path)

            projects = api_get("/api/projects")
            if isinstance(projects, list) and len(projects) > 0:
                next_id = max([p.get("Record ID", 0) for p in projects], default=0) + 1
            else:
                next_id = 1

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

            if result and (
                result.get("status") == "saved"
                or result.get("success") == True
            ):
                new_project = pd.DataFrame([payload])
                new_project.to_csv(DATA_FILE, mode='a', header=False, index=False)
                st.balloons()
                st.success(f"🎉 Project **'{p_name}'** successfully submitted!")

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
            result = api_post(
                "/api/scan",
                {
                    "member_name": st.session_state.username,
                    "name": st.session_state.username
                }
            )
            st.success(f"Attendance recorded for **{st.session_state.username}** on {datetime.now().strftime('%Y-%m-%d')}!")
        
        my_stats = api_get(f"/api/member/{st.session_state.username}")
        if not my_stats:
            my_stats = api_get(f"/api/member?name={st.session_state.username}")

        if my_stats:
            st.subheader("📊 My Statistics")
            c1, c2 = st.columns(2)
            c3, c4 = st.columns(2)

            c1.metric("Today's Hours", my_stats.get("today_duration", "00:00:00"))
            c2.metric("Weekly Hours", my_stats.get("weekly_duration", "00:00:00"))
            c3.metric("Monthly Hours", my_stats.get("monthly_duration", "00:00:00"))
            c4.metric("Total Visits", my_stats.get("total_visits", 0))

        attendance_data = api_get("/api/attendance")
        if isinstance(attendance_data, list):
            attendance_list = attendance_data
        else:
            attendance_list = attendance_data.get("attendance", [])

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

# ---------------------------------------------------------
# TAB 4: Member 1 OpenCV Camera Logs
# ---------------------------------------------------------
elif nav == "🤖 Member 1 OpenCV Logs":
    st.markdown("### 🤖 Member 1 OpenCV & Camera Verifications")
    cv_records = df_projects[df_projects["Category"] == "Computer Vision"] if "Category" in df_projects.columns else pd.DataFrame()

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
                    if path and path.strip().lower() != "nan":
                        if os.path.exists(path):
                            try:
                                st.image(path, use_container_width=True)
                            except Exception:
                                st.warning("Image could not be loaded.")
                        else:
                            st.warning("Image not found.")
                    else:
                        st.info("No image captured.")

                with c2:
                    st.markdown(f"**Task:** {p_title}")
                    st.markdown(f"**Developer:** {p_owner}")
                    st.markdown(f"**Status:** {row.get('Status', 'In Progress')}")
                    st.markdown(f"**Remarks:** {row.get('Remarks', 'N/A')}")

    live_data = api_get("/api/live-members")
    live_members = live_data if isinstance(live_data, list) else live_data.get("live_members", [])
    if live_members:
        st.subheader("🟢 Members Currently Inside")
        st.dataframe(
            pd.DataFrame(live_members),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("No members currently inside.")