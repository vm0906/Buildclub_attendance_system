<div align="center">

# 🎯 Build Club Smart Attendance System

### AI-powered presence & session tracking for modern makerspaces

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org/)
[![face_recognition](https://img.shields.io/badge/face__recognition-dlib-FF6F61?style=for-the-badge)](https://github.com/ageitgey/face_recognition)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)

[![Status](https://img.shields.io/badge/status-working%20prototype-yellow?style=flat-square)](#current-status)
[![License](https://img.shields.io/badge/license-not%20yet%20specified-lightgrey?style=flat-square)](#license)

**A camera watches the door. A face gets recognized. A session gets tracked — start to finish.**

</div>

---

Traditional makerspace attendance means sign-in sheets nobody fills out honestly, no idea how long people actually stayed, and zero real analytics. This system replaces that with webcam-based face recognition that detects **when a member arrives, tracks their presence while they're there, and logs when they actually leave** — session duration included.

```
   📷 Webcam  →  🔍 Detection  →  🧠 Recognition  →  🪪 Identity
        ↓
   🟢 ENTRY  →  ⏱️ Session Tracking  →  🚪 EXIT  →  🗄️ Database  →  📊 Dashboard
```

> **Status:** 🟡 Working prototype. Webcam recognition and attendance-event generation have been tested successfully — see [Current Status](#-current-status).

---

## 📑 Contents

<table>
<tr>
<td valign="top" width="33%">

- [Problem & Solution](#-problem--solution)
- [Key Features](#-key-features)
- [System Architecture](#️-system-architecture)
- [AI / CV Pipeline](#-ai--computer-vision-pipeline)
- [Presence Tracking](#-presence--session-tracking)

</td>
<td valign="top" width="33%">

- [Backend & Database](#-backend--database)
- [Project Structure](#-project-structure)
- [Installation](#-installation)
- [Dataset Setup](#-dataset-setup)
- [Configuration](#️-configuration)

</td>
<td valign="top" width="33%">

- [Tech Stack](#-tech-stack)
- [Privacy & Security](#-privacy--security)
- [Limitations & Roadmap](#-known-limitations)
- [Testing](#-testing)
- [License & Author](#-license)

</td>
</tr>
</table>

---

## 💡 Problem & Solution

| ❌ The Problem | ✅ The Solution |
|---|---|
| Manual sign-in sheets, easy to skip | Automatic recognition — no action needed from members |
| No real session-duration data | Continuous presence tracking, not just a check-in |
| Inaccurate, unauditable records | Every ENTRY/EXIT is a logged, timestamped event |
| Doesn't scale with membership | Same pipeline works whether it's 10 members or 200 |

---

## ✨ Key Features

- 🎥 **Real-time webcam** face detection and recognition
- 🪪 **Registered-member matching** against a face-encoding dataset
- 🟢 **Automatic ENTRY** detection when a known member appears
- 🔴 **Automatic EXIT** detection after a configurable grace period
- ⏱️ **Session-duration tracking** — not just present/absent
- 🗄️ **Attendance persistence** to a database
- 🔌 **Backend/API layer** connecting recognition → storage → dashboard
- 📊 **Dashboard/analytics** for reviewing attendance history
- ❓ **Unknown-face handling** for unrecognized visitors
- 📝 **Event logging** across recognition and attendance actions

---

## 🏗️ System Architecture

```
┌───────────────────────────────────────────────────────┐
│  📷 CAMERA LAYER            Webcam capture (OpenCV)     │
└───────────────────────────┬─────────────────────────┘
                              ▼
┌───────────────────────────────────────────────────────┐
│  🔍 COMPUTER VISION LAYER   Face detection per frame     │
└───────────────────────────┬─────────────────────────┘
                              ▼
┌───────────────────────────────────────────────────────┐
│  🧠 RECOGNITION LAYER       Encoding + match vs. dataset │
└───────────────────────────┬─────────────────────────┘
                              ▼
┌───────────────────────────────────────────────────────┐
│  ⏱️  PRESENCE / SESSION LAYER ENTRY → grace period → EXIT │
└───────────────────────────┬─────────────────────────┘
                              ▼
┌───────────────────────────────────────────────────────┐
│  🗄️  PERSISTENCE / API LAYER  Backend stores the event   │
└───────────────────────────┬─────────────────────────┘
                              ▼
┌───────────────────────────────────────────────────────┐
│  📊 DASHBOARD / ANALYTICS   Attendance & session review  │
└───────────────────────────────────────────────────────┘
```

> 🟡 **Honesty check:** this is a prototype, not a single unified production stack. Your checkout may contain more than one implementation of a layer (e.g. an older API module next to a newer one). Treat the actively-used module as current and the rest as legacy until consolidated.

---

## 🧠 AI / Computer Vision Pipeline

```
Dataset (member photos) → Face Detection → Face Encoding → Cached Encodings
                                                                    ↓
                          Live Webcam Frame → Face Matching (distance) → Identity → Attendance Event
```

| Library | Role |
|---|---|
| **OpenCV** | Webcam capture, frame-level image ops |
| **face_recognition** (`dlib`) | Face detection + 128-d face encoding, for both dataset and live frames |
| **Encoding cache** | Member encodings computed once, reused every frame — no re-encoding reference images live |

> ⚠️ Any "confidence %" shown in the UI is a **derived display value from match distance**, not a calibrated classifier probability. Read it as "how close the match was," not a statistical guarantee.

---

## ⏱️ Presence & Session Tracking

The core technical idea: **attendance** ≠ **presence**.

| | |
|---|---|
| **Attendance** | The fact a member was recognized during a visit |
| **Presence tracking** | Continuously watching whether they're *still* there |

```
Member recognized  →  🟢 ENTRY, session starts
Still detected      →  session stays active
Leaves camera view  →  ⏳ grace period starts
Reappears in time    →  session continues (no false EXIT)
Doesn't reappear      →  🔴 EXIT logged, duration calculated & saved
```

This avoids the classic false-EXIT problem where briefly stepping out of frame gets logged as leaving-and-returning repeatedly.

---

## 🔌 Backend & Database

**Flow:** recognition process → attendance events (ENTRY/EXIT/duration) → **API/backend** validates → **database** persists → **dashboard** reads and displays.

- **SQLite** via **SQLAlchemy** — core entities:
  - `Member` — identity + face-encoding reference
  - `Attendance` — entry time, exit time, session duration

> 🟡 Backend/DB/dashboard components are development-stage and may include more than one competing implementation. Check `database.py` in your checkout for the authoritative schema.

---

## 📁 Project Structure

```
build-club-smart-attendance/
├── camera.py         # Webcam capture
├── recognizer.py       # Detection + encoding + matching
├── tracker.py            # ENTRY/EXIT + grace period logic
├── attendance.py          # Attendance event handling
├── api_client.py            # Sends events to backend
├── backend.py                 # API service
├── database.py                  # SQLAlchemy models
├── config.py                      # Thresholds, timing, paths
├── dashboard/                        # Streamlit analytics app
├── dataset/                             # Registered member photos
├── requirements.txt
└── README.md
```

> Adapt to your actual repo — this reflects the components described for the project, not a guaranteed exact listing.

---

## 🚀 Installation

**Terminal 1 · Environment**
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
> `dlib` needs a C++ build toolchain + CMake on some systems if the wheel isn't prebuilt.

**Terminal 2 · Backend/API**
```powershell
.venv\Scripts\activate
python backend.py
```

**Terminal 3 · Camera / recognition**
```powershell
.venv\Scripts\activate
python Main.py
```

**Terminal 4 · Dashboard**
```powershell
.venv\Scripts\activate
streamlit run dashboard/app.py
```
> Exact filenames depend on your repo — adjust to match what's actually there.

---

## 🗂️ Dataset Setup

```
dataset/
├── MemberName1/
│   ├── image1.jpg
│   ├── image2.jpg
│   └── image3.jpg
├── MemberName2/
│   ├── image1.jpg
│   └── image2.jpg
```

- One folder per member · several varied photos each (lighting/angle/expression)
- Clear, well-lit, front-facing shots encode best
- Re-generate encodings after adding/updating photos

---

## ⚙️ Configuration

| Setting | Purpose |
|---|---|
| Recognition/match threshold | Distance cutoff for accepting a match |
| Camera source/index | Which webcam device to use |
| Frame resize factor | Downscale frames to cut compute cost |
| Frame skip interval | Process every Nth frame |
| Grace period duration | Wait time before logging EXIT |
| Database path | Where attendance data is stored |
| API base URL | Where events get sent |
| Logging level | Verbosity/output |

> Check `config.py` for actual variable names/defaults — table above reflects the kinds of settings this system needs.

---

## 🎬 Example Attendance Flow

*Illustrative — actual timings depend on your configured grace period.*

```
10:00  →  Member detected  →  🟢 ENTRY, session starts
10:30  →  Still visible     →  session continues
10:45  →  Disappears          →  ⏳ grace period begins
10:4X  →  No reappearance      →  🔴 EXIT
       →  Duration calculated (10:00–10:4X) & saved
```

---

## 🧰 Tech Stack

| Category | Technology |
|---|---|
| Language | Python |
| Computer Vision | OpenCV |
| Face Recognition | face_recognition, dlib |
| Numerical Computing | NumPy |
| Backend / API | FastAPI |
| ORM | SQLAlchemy |
| Database | SQLite |
| Dashboard | Streamlit |
| Data Handling | Pandas |
| HTTP Client | Requests |

---

## ⚡ Performance Considerations

- **Frame resizing** + **frame skipping** cut compute cost
- **Encoding cache** avoids re-encoding reference photos every frame
- **Threshold tuning** trades false positives vs. false negatives
- **Lighting & camera quality** directly affect reliability

> 🟡 **Benchmarking has not yet been formally performed.** Future methodology: FPS, end-to-end latency, and match accuracy on a labeled known/unknown test set.

---

## 🔒 Privacy & Security

This system handles **biometric data** (face images + encodings) — treat it carefully.

| Now | Recommended for production |
|---|---|
| Member photos stored locally in `dataset/` | Restrict filesystem access to authorized users |
| Encodings cached locally | Add authentication/authorization before any remote exposure |
| No auth layer in the prototype | Use HTTPS for any networked API traffic |
| — | Define a data-retention policy for images/encodings/records |
| — | Consider member consent per your institution's policy |

*Not legal advice — consult your institution's policies before deploying beyond a local prototype.*

---

## ✅ Current Status

**Working prototype**, not production-finished.

- ✔️ Webcam recognition tested — successfully recognized a registered member
- ✔️ Real attendance events generated (ENTRY detection + "marked present")
- 🟡 Backend/API/database exist but should be considered development-stage

---

## ⚠️ Known Limitations

- Sensitive to lighting conditions and face pose/angle
- No formal accuracy benchmark yet
- Webcam-dependent, not evaluated across camera types
- No liveness/anti-spoofing detection
- No production-grade authentication
- Backend/DB may have more than one implementation path to consolidate

---

## 🗺️ Future Roadmap

| Phase | Focus |
|---|---|
| **1** | Architecture cleanup — consolidate duplicate backend/DB paths |
| **2** | Production-hardened backend (error handling, structured logging) |
| **3** | Authentication & role-based access control |
| **4** | Liveness / anti-spoofing detection |
| **5** | Multi-camera support |
| **6** | Advanced makerspace analytics |
| **7** | Cloud deployment |
| **8** | Equipment / lab utilization analytics |

> None of the above exists yet — this is a direction, not a feature list.

---

## 🌱 Why This Project Matters

This isn't just a digital sign-in sheet. Session-level presence tracking is a foundation for understanding how people actually use a shared physical space. Extended further, it could inform:

`occupancy` · `member utilization` · `project participation` · `equipment usage`

All future possibilities — not current features.

---

## 🧪 Testing

**Validated so far:** live webcam recognition · ENTRY event generation · "marked present" event generation.

No automated test suite exists yet.

**Recommended future suite:** unit tests for match/threshold logic · state-transition tests for ENTRY→grace→EXIT · integration tests for API/DB persistence · a labeled known/unknown face set for accuracy eval.

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch
3. Keep changes scoped and well-described
4. Open a PR describing what and why
5. File issues with enough detail to reproduce

---

## 📄 License

**Not yet specified.** *(Consider MIT or Apache-2.0 once ready to formalize.)*

## 👥 Author / Team

Built by the Build Club project team.
