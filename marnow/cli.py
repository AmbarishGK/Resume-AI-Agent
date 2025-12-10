import typer
from pathlib import Path
from marnow.ingest import ensure_db, seed_skills_csv, ingest_jd, ingest_resume_pdf, ingest_resume_docx
from marnow.match import run_match, report_match

app = typer.Typer(help="MaRNoW ingestion & matching CLI")

@app.command()
def initdb():
    ensure_db(); typer.echo("DB initialized.")

@app.command("seed-skills")
def seed(csv_path: str = "/app/data/skills/skills.csv"):
    ensure_db(); n = seed_skills_csv(csv_path); typer.echo(f"Inserted {n} skills")

@app.command("ingest-jd")
def jd(path: str):
    ensure_db(); jid, created = ingest_jd(path)
    typer.echo(f"JD {'created' if created else 'exists'} id={jid}")

@app.command("ingest-resume")
def resume(path: str):
    ensure_db(); p = Path(path)
    if p.suffix.lower()==".pdf": rid, created = ingest_resume_pdf(path)
    elif p.suffix.lower()==".docx": rid, created = ingest_resume_docx(path)
    else:
        typer.echo("Unsupported format (.pdf or .docx)"); raise typer.Exit(1)
    typer.echo(f"Resume {'created' if created else 'exists'} id={rid}")

@app.command("match")
def match(resume_id: int, job_id: int):
    ensure_db()
    res = run_match(resume_id, job_id)
    typer.echo(f"match_id={res['match_id']} total={res['total']} "
               f"(skills={res['skills_score']}, resp={res['resp_score']}, "
               f"seniority={res['seniority_score']}, domain={res['domain_score']})")
    if res["missing"]:
        typer.echo("Top missing skills: " + ", ".join(res["missing"][:10]))

@app.command("report")
def report(match_id: int):
    ensure_db()
    rep = report_match(match_id)
    s = rep["scores"]
    typer.echo(f"Match {rep['match_id']} | Resume {rep['resume']} -> {rep['company']} / {rep['role']}")
    typer.echo(f"Total: {s['total']}  [skills {s['skills']} | resp {s['responsibilities']} | "
               f"seniority {s['seniority']} | domain {s['domain']}]")
    if rep["missing"]:
        typer.echo("Missing skills: " + ", ".join(rep["missing"]))

if __name__=="__main__":
    app()
