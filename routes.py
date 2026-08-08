# ==================== 2. routes.py ====================

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
from database import get_db, Member, Attendance, Project

router = APIRouter()


class ScanRequest(BaseModel):
    member_name: str


class ScanResponse(BaseModel):
    status: str
    member_name: str
    entry_time: Optional[str] = None
    exit_time: Optional[str] = None
    duration: Optional[str] = None


class ProjectPayload(BaseModel):
    Record_ID: Optional[int] = 0
    Member_Name: Optional[str] = ""
    In_Timing: Optional[str] = ""
    Out_Timing: Optional[str] = ""
    Duration_Hrs: Optional[str] = ""
    Project_Name: Optional[str] = ""
    Status: Optional[str] = ""
    Remarks: Optional[str] = ""
    Category: Optional[str] = ""
    Progress: Optional[int] = 0
    Camera_Verified: Optional[str] = ""
    Timestamp: Optional[str] = ""
    Image_Path: Optional[str] = ""


def auto_exit_members(db: Session):
    cutoff = datetime.utcnow() - timedelta(minutes=2)
    active_members = db.query(Member).filter(Member.is_active == True).all()
    for member in active_members:
        if member.last_seen_at and member.last_seen_at < cutoff:
            record = db.query(Attendance).filter(
                Attendance.member_id == member.id,
                Attendance.status == "active"
            ).first()
            if record:
                record.exit_time = member.last_seen_at
                delta = record.exit_time - record.entry_time
                record.duration_seconds = int(delta.total_seconds())
                record.status = "closed"
            member.is_active = False
    db.commit()


@router.post("/api/scan", response_model=ScanResponse)
def scan_member(req: ScanRequest, db: Session = Depends(get_db)):
    auto_exit_members(db)
    now = datetime.utcnow()

    member = db.query(Member).filter(Member.name == req.member_name).first()
    if not member:
        member = Member(name=req.member_name, is_active=False, last_seen_at=now)
        db.add(member)
        db.commit()
        db.refresh(member)
    else:
        member.last_seen_at = now

    active_record = db.query(Attendance).filter(
        Attendance.member_id == member.id,
        Attendance.status == "active"
    ).first()

    entry_time_str = None
    status_msg = ""

    if not active_record:
        new_record = Attendance(member_id=member.id, entry_time=now, status="active")
        db.add(new_record)
        member.is_active = True
        db.commit()
        db.refresh(new_record)
        entry_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        status_msg = "entry_marked"
    else:
        member.is_active = True
        db.commit()
        entry_time_str = active_record.entry_time.strftime("%Y-%m-%d %H:%M:%S")
        status_msg = "already_active"

    return ScanResponse(
        status=status_msg,
        member_name=member.name,
        entry_time=entry_time_str,
        exit_time=None,
        duration=None
    )


@router.get("/api/live-members")
def get_live_members(db: Session = Depends(get_db)):
    auto_exit_members(db)
    members = db.query(Member).filter(Member.is_active == True).all()
    result = []
    for m in members:
        record = db.query(Attendance).filter(
            Attendance.member_id == m.id,
            Attendance.status == "active"
        ).first()
        entry_time = record.entry_time.strftime("%Y-%m-%d %H:%M:%S") if record else None
        duration_sec = 0
        if record and record.entry_time:
            duration_sec = int((datetime.utcnow() - record.entry_time).total_seconds())
        duration_str = f"{duration_sec // 3600:02d}:{(duration_sec % 3600) // 60:02d}:{duration_sec % 60:02d}"
        result.append({
            "name": m.name,
            "entry_time": entry_time,
            "current_duration": duration_str,
            "last_seen": m.last_seen_at.strftime("%Y-%m-%d %H:%M:%S") if m.last_seen_at else None
        })
    return {"live_members": result, "count": len(result)}


@router.get("/api/attendance")
def get_attendance_history(limit: int = 200, db: Session = Depends(get_db)):
    records = db.query(Attendance).order_by(Attendance.entry_time.desc()).limit(limit).all()
    result = []
    for r in records:
        member = db.query(Member).filter(Member.id == r.member_id).first()
        duration_str = "00:00:00"
        if r.duration_seconds and r.duration_seconds > 0:
            ds = r.duration_seconds
            duration_str = f"{ds // 3600:02d}:{(ds % 3600) // 60:02d}:{ds % 60:02d}"
        elif r.status == "active" and r.entry_time:
            ds = int((datetime.utcnow() - r.entry_time).total_seconds())
            duration_str = f"{ds // 3600:02d}:{(ds % 3600) // 60:02d}:{ds % 60:02d}"
        result.append({
            "id": r.id,
            "member_name": member.name if member else "Unknown",
            "entry_time": r.entry_time.strftime("%Y-%m-%d %H:%M:%S") if r.entry_time else None,
            "exit_time": r.exit_time.strftime("%Y-%m-%d %H:%M:%S") if r.exit_time else None,
            "duration": duration_str,
            "status": r.status
        })
    return {"attendance": result}


@router.get("/api/member/{name}")
def get_member_stats(name: str, db: Session = Depends(get_db)):
    member = db.query(Member).filter(Member.name == name).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    today = datetime.utcnow().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    records = db.query(Attendance).filter(Attendance.member_id == member.id).all()

    today_duration = 0
    week_duration = 0
    month_duration = 0
    total_visits = len(records)

    for r in records:
        dur = r.duration_seconds or 0
        if r.status == "active" and r.entry_time:
            dur += int((datetime.utcnow() - r.entry_time).total_seconds())

        entry_date = r.entry_time.date() if r.entry_time else None
        if entry_date == today:
            today_duration += dur
        if entry_date and entry_date >= week_start:
            week_duration += dur
        if entry_date and entry_date >= month_start:
            month_duration += dur

    def fmt(sec):
        return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}:{sec % 60:02d}"

    return {
        "member_name": member.name,
        "today_duration": fmt(today_duration),
        "weekly_duration": fmt(week_duration),
        "monthly_duration": fmt(month_duration),
        "total_visits": total_visits,
        "is_active": member.is_active
    }


@router.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    auto_exit_members(db)
    total_members = db.query(Member).count()
    live = db.query(Member).filter(Member.is_active == True).count()
    today = datetime.utcnow().date()
    present_today = db.query(Attendance).filter(
        func.date(Attendance.entry_time) == today
    ).count()
    absent = total_members - live
    return {
        "total_members": total_members,
        "live_members": live,
        "present_today": present_today,
        "absent": absent if absent >= 0 else 0,
        "unknown_faces": 0
    }


@router.post("/api/projects")
def create_project(payload: dict, db: Session = Depends(get_db)):
    db_project = Project(
        record_id=payload.get("Record ID", 0),
        member_name=payload.get("Member Name", ""),
        in_timing=payload.get("In-Timing", ""),
        out_timing=payload.get("Out-Timing", ""),
        duration=payload.get("Duration (Hrs)", ""),
        project_name=payload.get("Project Name", ""),
        status=payload.get("Status", ""),
        remarks=payload.get("Remarks", ""),
        category=payload.get("Category", ""),
        progress=payload.get("Progress", 0),
        camera_verified=payload.get("Camera Verified", ""),
        timestamp=payload.get("Timestamp", ""),
        image_path=payload.get("Image Path", "")
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return {"id": db_project.id, "status": "saved"}


@router.get("/api/projects")
def get_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.id.desc()).all()
    result = []
    for p in projects:
        result.append({
            "Record ID": p.record_id,
            "Member Name": p.member_name,
            "In-Timing": p.in_timing,
            "Out-Timing": p.out_timing,
            "Duration (Hrs)": p.duration,
            "Project Name": p.project_name,
            "Status": p.status,
            "Remarks": p.remarks,
            "Category": p.category,
            "Progress": p.progress,
            "Camera Verified": p.camera_verified,
            "Timestamp": p.timestamp,
            "Image Path": p.image_path
        })
    return result

class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/api/login")
def login(req: LoginRequest):

    if req.username == "admin@buildclub" and req.password == "srm123":
        return {
            "status":"success",
            "username":"Admin"
        }

    raise HTTPException(
        status_code=401,
        detail="Invalid username or password"
    )