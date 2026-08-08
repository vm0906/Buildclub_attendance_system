# ==================== 1. database.py ====================

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, ForeignKey, Boolean, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./buildclub.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Member(Base):
    __tablename__ = "members"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=False)
    last_seen_at = Column(DateTime, nullable=True)
    attendance_records = relationship("Attendance", back_populates="member")


class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, default=0)
    status = Column(String, default="active")
    member = relationship("Member", back_populates="attendance_records")


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True, index=True)
    record_id = Column(Integer, default=0)
    member_name = Column(String)
    in_timing = Column(String)
    out_timing = Column(String)
    duration = Column(String)
    project_name = Column(String)
    status = Column(String)
    remarks = Column(String)
    category = Column(String)
    progress = Column(Integer, default=0)
    camera_verified = Column(String)
    timestamp = Column(String)
    image_path = Column(String, default="")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)