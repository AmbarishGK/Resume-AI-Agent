import re, csv
from pathlib import Path
from typing import Optional, Tuple
from marnow.db import init_db, upsert_resume, upsert_job, seed_skills

def _read_text(p:Path)->str:
    return p.read_text(encoding="utf-8",errors="ignore")

def _parse_meta(text, fname)->Tuple[Optional[str],Optional[str]]:
    company=role=None
    for line in text.splitlines()[:5]:
        if line.lower().startswith("# company:"): company=line.split(":",1)[1].strip()
        if line.lower().startswith("# role:"): role=line.split(":",1)[1].strip()
    if not company or not role:
        parts=re.split(r"[_\-]+", Path(fname).stem)
        if not company and parts: company=parts[0]
        if not role and len(parts)>1: role=" ".join(parts[1:])
    return company,role

def ingest_jd(path):
    p=Path(path); text=_read_text(p)
    comp,role=_parse_meta(text,p.name)
    jid,created=upsert_job(p.name,comp,role,text,None)
    return jid,created

def ingest_resume_pdf(path):
    from pypdf import PdfReader
    p=Path(path); reader=PdfReader(str(p))
    text="\n".join(pg.extract_text() or "" for pg in reader.pages)
    rid,created=upsert_resume(p.name,"pdf",text)
    return rid,created

def ingest_resume_docx(path):
    import docx
    p=Path(path); doc=docx.Document(str(p))
    text="\n".join(par.text for par in doc.paragraphs)
    rid,created=upsert_resume(p.name,"docx",text)
    return rid,created

def seed_skills_csv(csv_path):
    rows=[]
    with open(csv_path,encoding="utf-8") as f:
        r=csv.DictReader(f)
        for row in r:
            rows.append((row.get("skill",""),row.get("aliases",""),row.get("category","")))
    return seed_skills(rows)

def ensure_db(): init_db()
