import sqlite3
import pandas as pd
from datetime import datetime

DB_NAME = "buildclub.db"


def init_db():
    """Initializes SQLite database and creates table if it doesn't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            member_name TEXT NOT NULL,
            entry_time TEXT NOT NULL,
            exit_time TEXT,
            duration_hours REAL,
            project_name TEXT DEFAULT 'Unassigned Project',
            status TEXT DEFAULT 'In Progress',
            remarks TEXT DEFAULT ''
        )
    """
    )
    conn.commit()
    conn.close()


# Auto-initialize DB on import
init_db()


def get_db_connection():
    """Returns a new connection to the database."""
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def verify_admin(username, password):
    """Verifies administrator credentials."""
    return username == "admin@buildclub.org" and password == "BuildClub#2026"


def get_attendance_df():
    """Retrieves all attendance and project records into a pandas DataFrame."""
    conn = get_db_connection()
    try:
        df = pd.read_sql_query("SELECT * FROM attendance_logs ORDER BY id DESC", conn)
    except Exception:
        df = pd.DataFrame(
            columns=[
                "id",
                "member_name",
                "entry_time",
                "exit_time",
                "duration_hours",
                "project_name",
                "status",
                "remarks",
            ]
        )
    finally:
        conn.close()
    return df


def update_project_details(record_id, project_name, status, remarks):
    """Updates project metadata and remarks for a given session ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE attendance_logs 
        SET project_name = ?, status = ?, remarks = ?
        WHERE id = ?
    """,
        (project_name, status, remarks, record_id),
    )
    conn.commit()
    conn.close()


def record_scan(member_name, project_name="Unassigned Project"):
    """Records camera check-in or check-out automatically."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Check for active check-in without check-out timestamp
    cursor.execute(
        """
        SELECT id, entry_time FROM attendance_logs 
        WHERE member_name = ? AND exit_time IS NULL
        ORDER BY id DESC LIMIT 1
    """,
        (member_name,),
    )
    active_session = cursor.fetchone()

    if active_session:
        session_id, entry_str = active_session
        entry_dt = datetime.strptime(entry_str, "%Y-%m-%d %H:%M:%S")
        exit_dt = datetime.now()
        duration = round((exit_dt - entry_dt).total_seconds() / 3600.0, 2)

        cursor.execute(
            """
            UPDATE attendance_logs
            SET exit_time = ?, duration_hours = ?
            WHERE id = ?
        """,
            (now_str, duration, session_id),
        )
        action = "checkout"
    else:
        cursor.execute(
            """
            INSERT INTO attendance_logs (member_name, entry_time, project_name, status, remarks)
            VALUES (?, ?, ?, 'In Progress', 'Camera Auto-Scan')
        """,
            (member_name, now_str, project_name),
        )
        action = "checkin"

    conn.commit()
    conn.close()
    return action, now_str