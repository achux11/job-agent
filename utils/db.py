import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "jobs.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_title TEXT NOT NULL,
            company TEXT NOT NULL,
            location TEXT,
            job_url TEXT,
            job_description TEXT,
            status TEXT DEFAULT 'applied',
            notes TEXT,
            salary_min INTEGER,
            salary_max INTEGER,
            applied_date TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            application_id INTEGER,
            type TEXT,
            content TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (application_id) REFERENCES applications(id)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS resume_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            section TEXT,
            content TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            message TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()


# ─── Applications ──────────────────────────────────────────────────────────────

def add_application(job_title, company, location="", job_url="", job_description="",
                    status="applied", notes="", salary_min=None, salary_max=None, applied_date=None):
    conn = get_conn()
    c = conn.cursor()
    applied_date = applied_date or datetime.now().strftime("%Y-%m-%d")
    c.execute("""
        INSERT INTO applications (job_title, company, location, job_url, job_description,
                                  status, notes, salary_min, salary_max, applied_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (job_title, company, location, job_url, job_description,
          status, notes, salary_min, salary_max, applied_date))
    conn.commit()
    app_id = c.lastrowid
    conn.close()
    return app_id


def get_applications(status=None):
    conn = get_conn()
    c = conn.cursor()
    if status and status != "All":
        c.execute("SELECT * FROM applications WHERE status=? ORDER BY created_at DESC", (status,))
    else:
        c.execute("SELECT * FROM applications ORDER BY created_at DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def update_application(app_id, **kwargs):
    conn = get_conn()
    c = conn.cursor()
    kwargs["updated_at"] = datetime.now().isoformat()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [app_id]
    c.execute(f"UPDATE applications SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


def delete_application(app_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM materials WHERE application_id=?", (app_id,))
    c.execute("DELETE FROM applications WHERE id=?", (app_id,))
    conn.commit()
    conn.close()


def get_application(app_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM applications WHERE id=?", (app_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_stats():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM applications")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM applications WHERE status IN ('applied','screening')")
    active = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM applications WHERE status='interview'")
    interviews = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM applications WHERE status='offer'")
    offers = c.fetchone()[0]
    conn.close()
    return {"total": total, "active": active, "interviews": interviews, "offers": offers}


# ─── Materials ─────────────────────────────────────────────────────────────────

def save_material(application_id, material_type, content):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO materials (application_id, type, content)
        VALUES (?, ?, ?)
    """, (application_id, material_type, content))
    conn.commit()
    conn.close()


def get_materials(application_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM materials WHERE application_id=? ORDER BY created_at DESC", (application_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


# ─── Resume Vault ──────────────────────────────────────────────────────────────

def save_resume_chunk(section, content):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM resume_chunks WHERE section=?", (section,))
    c.execute("INSERT INTO resume_chunks (section, content) VALUES (?, ?)", (section, content))
    conn.commit()
    conn.close()


def get_resume_chunks():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM resume_chunks ORDER BY section")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_resume_text():
    chunks = get_resume_chunks()
    return "\n\n".join(f"## {c['section']}\n{c['content']}" for c in chunks)


# ─── Chat History ──────────────────────────────────────────────────────────────

def save_chat(session_id, role, message):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO chat_history (session_id, role, message) VALUES (?, ?, ?)",
              (session_id, role, message))
    conn.commit()
    conn.close()


def get_chat_history(session_id, limit=20):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT role, message FROM chat_history
        WHERE session_id=?
        ORDER BY created_at DESC LIMIT ?
    """, (session_id, limit))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return list(reversed(rows))
