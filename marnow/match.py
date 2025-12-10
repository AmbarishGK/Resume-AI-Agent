import re, json, sqlite3, math, datetime, os
from collections import Counter
from typing import Dict, List, Tuple, Set

DB = os.environ.get("MARNOW_DB", "marnow.db")

_WORD = re.compile(r"[a-zA-Z0-9\+\#\.][a-zA-Z0-9\+\#\.\-]+")

def _tok(s:str)->List[str]:
    return [w.lower() for w in _WORD.findall(s or "")]

def _contains_any(text:str, keys:Set[str])->bool:
    t = " " + (text or "").lower() + " "
    return any((" " + k + " ") in t for k in keys)

def _normalize_aliases(js:str)->Set[str]:
    try:
        arr = json.loads(js or "[]")
    except Exception:
        arr = []
    out = set()
    for a in arr:
        a = a.strip().lower()
        if not a: continue
        out.add(a)
    return out

def _get(conn):
    r = conn.execute("select id, filename, fmt, text from resumes").fetchall()
    j = conn.execute("select id, company, role, text from job_posts").fetchall()
    skills = conn.execute("select id, skill, aliases_json, category from skills").fetchall()
    return r, j, skills

def _skill_index(skills_rows)->Dict[str,Dict]:
    idx = {}
    for _,skill,aliases_js,cat in skills_rows:
        key = skill.strip().lower()
        al = _normalize_aliases(aliases_js)
        al.add(key)
        idx[key] = {"aliases": al, "category": (cat or "").strip().lower()}
    return idx

def _bag_presence(text:str, patterns:Set[str])->Tuple[int,Set[str]]:
    found = set()
    t = " " + (text or "").lower() + " "
    for p in patterns:
        if (" " + p + " ") in t:
            found.add(p)
    return len(found), found

def score_pair(resume_txt:str, jd_txt:str, jd_role:str, jd_company:str, skills_idx:Dict[str,Dict])->Dict:
    # 1) Skills overlap
    all_aliases = set()
    for ent in skills_idx.values():
        all_aliases |= ent["aliases"]
    n_skills_resume, found_resume = _bag_presence(resume_txt, all_aliases)
    n_skills_jd, found_jd = _bag_presence(jd_txt, all_aliases)
    # intersection across resume & JD (skill present in both)
    overlap = found_resume & found_jd

    # Normalize by JD skill demand (avoid over-credit)
    denom = max(5, len(found_jd))  # avoid div by small
    skills_score = min(1.0, len(overlap) / denom) * 45.0

    # 2) Responsibilities/experience signals (heuristics)
    resp_keys = {
        "design","implement","deploy","scale","optimize",
        "build","lead","collaborate","maintain","own",
        "pipelines","apis","services","models","evaluation","benchmark"
    }
    r_resp = len(resp_keys & set(_tok(resume_txt)))
    j_resp = len(resp_keys & set(_tok(jd_txt)))
    resp_score = min(1.0, (r_resp / max(6, j_resp))) * 35.0

    # 3) Seniority alignment
    newgrad_keys = {"new grad","entry level","junior","resident","intern"}
    senior_keys = {"senior","staff","principal","lead"}
    resume_t = (resume_txt or "").lower()
    jd_t = (jd_txt or "").lower()
    want_new = _contains_any(jd_t, newgrad_keys)
    want_senior = _contains_any(jd_t, senior_keys)
    is_newish = _contains_any(resume_t, {"b.s.","bsc","b.e","ms","intern","new grad","junior"}) and not _contains_any(resume_t, senior_keys)
    is_seniorish = _contains_any(resume_t, senior_keys) or _contains_any(resume_t, {"7+ years","8+ years","10+ years"})
    seniority_score = 0.0
    if want_new and is_newish: seniority_score = 15.0
    elif want_senior and is_seniorish: seniority_score = 15.0
    elif not want_new and not want_senior: seniority_score = 10.0  # neutral JD

    # 4) Domain/company signals
    domain_sets = {
        "ai": {"ml","machine learning","deep learning","pytorch","tensorflow","llm","nlp","cv","computer vision"},
        "robotics": {"ros","ros2","slam","lidar","autonomy","control","pid","isaac"},
        "backend": {"api","microservices","grpc","rest","database","postgres","cassandra","redis","kafka","kubernetes"},
        "fullstack": {"react","next.js","frontend","backend","full stack","typescript"},
        "firmware": {"embedded","rtos","baremetal","stm32","fpga","uart","spi","i2c"},
        "data": {"airflow","spark","pyspark","hadoop","etl","data pipeline","bigquery","snowflake"}
    }
    dom_want = set()
    t_all = (jd_role or "") + " " + jd_t
    for k, keys in domain_sets.items():
        if _contains_any(t_all, keys):
            dom_want.add(k)
    dom_have = set()
    for k, keys in domain_sets.items():
        if _contains_any(resume_t, keys):
            dom_have.add(k)
    domain_overlap = len(dom_want & dom_have)
    domain_score = min(1.0, domain_overlap / max(1, len(dom_want))) * 5.0 if dom_want else 3.0

    total = round(skills_score + resp_score + seniority_score + domain_score, 2)
    # Missing skills (JD says, resume lacks)
    missing = list((found_jd - overlap))[:10]

    return {
        "skills_score": round(skills_score,2),
        "resp_score": round(resp_score,2),
        "seniority_score": round(seniority_score,2),
        "domain_score": round(domain_score,2),
        "total": total,
        "missing": missing
    }

def run_match(resume_id:int, job_id:int)->Dict:
    con = sqlite3.connect(DB); con.execute("PRAGMA foreign_keys=ON;")
    try:
        r = con.execute("select id, text from resumes where id=?", (resume_id,)).fetchone()
        j = con.execute("select id, company, role, text from job_posts where id=?", (job_id,)).fetchone()
        if not r or not j:
            raise ValueError("Invalid resume_id or job_id")
        skills = con.execute("select id, skill, aliases_json, category from skills").fetchall()
        idx = _skill_index(skills)
        result = score_pair(r[1], j[3], j[2] or "", j[1] or "", idx)
        # persist into matches
        now = datetime.datetime.utcnow().isoformat()
        con.execute("""INSERT INTO matches(resume_id, job_id, score_total, score_skills, score_resp,
                       score_seniority, score_domain, gaps_json, created_at)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (resume_id, job_id, result["total"], result["skills_score"], result["resp_score"],
                     result["seniority_score"], result["domain_score"], json.dumps(result["missing"]), now))
        con.commit()
        result["match_id"] = con.execute("select last_insert_rowid()").fetchone()[0]
        return result
    finally:
        con.close()

def report_match(match_id:int)->Dict:
    con = sqlite3.connect(DB)
    try:
        row = con.execute("""select m.id, m.resume_id, m.job_id, m.score_total, m.score_skills,
                             m.score_resp, m.score_seniority, m.score_domain, m.gaps_json,
                             r.filename, j.company, j.role
                             from matches m
                             join resumes r on r.id=m.resume_id
                             join job_posts j on j.id=m.job_id
                             where m.id=?""", (match_id,)).fetchone()
        if not row: raise ValueError("match_id not found")
        return {
            "match_id": row[0],
            "resume_id": row[1],
            "job_id": row[2],
            "scores": {
                "total": row[3],
                "skills": row[4],
                "responsibilities": row[5],
                "seniority": row[6],
                "domain": row[7],
            },
            "missing": json.loads(row[8] or "[]"),
            "resume": row[9],
            "company": row[10],
            "role": row[11],
        }
    finally:
        con.close()
