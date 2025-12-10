import os, sqlite3, json, hashlib, datetime
from typing import Iterable, Optional, Tuple

DB_PATH = os.environ.get("MARNOW_DB", "marnow.db")

SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS resumes(
  id INTEGER PRIMARY KEY,
  filename TEXT, fmt TEXT, text TEXT,
  parsed_at TEXT, hash TEXT UNIQUE, notes TEXT
);
CREATE TABLE IF NOT EXISTS job_posts(
  id INTEGER PRIMARY KEY,
  filename TEXT, company TEXT, role TEXT,
  source_url TEXT, text TEXT, ingested_at TEXT, hash TEXT UNIQUE
);
CREATE TABLE IF NOT EXISTS skills(
  id INTEGER PRIMARY KEY,
  skill TEXT UNIQUE, aliases_json TEXT, category TEXT, added_at TEXT
);
CREATE TABLE IF NOT EXISTS matches(
  id INTEGER PRIMARY KEY,
  resume_id INTEGER, job_id INTEGER,
  score_total REAL, score_skills REAL, score_resp REAL,
  score_seniority REAL, score_domain REAL,
  gaps_json TEXT, created_at TEXT,
  FOREIGN KEY(resume_id) REFERENCES resumes(id) ON DELETE CASCADE,
  FOREIGN KEY(job_id) REFERENCES job_posts(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS artifacts(
  id INTEGER PRIMARY KEY,
  match_id INTEGER, resume_tex TEXT, cover_tex TEXT,
  email_md TEXT, export_dir TEXT, created_at TEXT,
  FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE
);
"""

def connect():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:  # Only create directory if path has a directory component
        os.makedirs(db_dir, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys=ON;")
    return con

def init_db():
    con = connect(); con.executescript(SCHEMA_SQL); con.commit(); con.close()

def sha256_text(t:str)->str:
    return hashlib.sha256(t.encode("utf-8",errors="ignore")).hexdigest()

def upsert_resume(filename, fmt, text, notes=None):
    con = connect()
    h = sha256_text(text); now = datetime.datetime.utcnow().isoformat()
    cur = con.cursor()
    cur.execute("SELECT id FROM resumes WHERE hash=?", (h,))
    row = cur.fetchone()
    if row: con.close(); return row[0], False
    cur.execute("INSERT INTO resumes VALUES(NULL,?,?,?,?,?,?)",
                (filename, fmt, text, now, h, notes))
    con.commit(); rid = cur.lastrowid; con.close(); return rid, True

def upsert_job(filename, company, role, text, source_url=None):
    con = connect()
    h = sha256_text(text); now = datetime.datetime.utcnow().isoformat()
    cur = con.cursor()
    cur.execute("SELECT id FROM job_posts WHERE hash=?", (h,))
    row = cur.fetchone()
    if row: con.close(); return row[0], False
    cur.execute("INSERT INTO job_posts VALUES(NULL,?,?,?,?,?,?,?)",
                (filename, company, role, source_url, text, now, h))
    con.commit(); jid = cur.lastrowid; con.close(); return jid, True

def seed_skills(rows:Iterable[Tuple[str,str,str]])->int:
    con = connect(); cur = con.cursor(); now = datetime.datetime.utcnow().isoformat(); n=0
    for skill, aliases, cat in rows:
        aliases_list=[a.strip() for a in (aliases or "").split(",") if a.strip()]
        cur.execute("INSERT OR IGNORE INTO skills VALUES(NULL,?,?,?,?)",
                    (skill.strip(), json.dumps(aliases_list), cat, now))
        n+=cur.rowcount
    con.commit(); con.close(); return n
