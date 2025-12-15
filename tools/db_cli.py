#!/usr/bin/env python3

import os
import sqlite3
from typing import Optional

import typer

app = typer.Typer(help="Helper CLI to inspect marnow.db (list IDs for resumes/jobs/matches)")


def _db_path() -> str:
    return os.environ.get("MARNOW_DB", "marnow.db")


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(_db_path())
    con.execute("PRAGMA foreign_keys=ON;")
    return con


@app.command("list-resumes")
def list_resumes(limit: int = 20):
    """List ingested resumes (ids + filenames)."""
    con = _connect()
    try:
        rows = con.execute(
            "SELECT id, filename, fmt, parsed_at FROM resumes ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        con.close()

    if not rows:
        typer.echo("No resumes found. Use: python -m marnow.cli ingest-resume <file.pdf>")
        raise typer.Exit(0)

    typer.echo("id\tfilename\tfmt\tparsed_at")
    for rid, fn, fmt, ts in rows:
        typer.echo(f"{rid}\t{fn}\t{fmt}\t{ts}")


@app.command("list-jobs")
def list_jobs(limit: int = 20, contains: Optional[str] = None):
    """List ingested job descriptions (ids + company/role).

    Use --contains to filter by substring in company/role.
    """
    con = _connect()
    try:
        if contains:
            q = f"%{contains}%"
            rows = con.execute(
                "SELECT id, company, role, ingested_at FROM job_posts "
                "WHERE COALESCE(company,'') LIKE ? OR COALESCE(role,'') LIKE ? "
                "ORDER BY id DESC LIMIT ?",
                (q, q, limit),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT id, company, role, ingested_at FROM job_posts ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    finally:
        con.close()

    if not rows:
        typer.echo("No jobs found. Run: python tools/workflow.py (or ingest-jd)")
        raise typer.Exit(0)

    typer.echo("id\tcompany\trole\tingested_at")
    for jid, company, role, ts in rows:
        typer.echo(f"{jid}\t{company or ''}\t{role or ''}\t{ts}")


@app.command("list-matches")
def list_matches(limit: int = 20):
    """List match runs (ids + resume_id/job_id + total score)."""
    con = _connect()
    try:
        rows = con.execute(
            "SELECT id, resume_id, job_id, score_total, created_at FROM matches ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        con.close()

    if not rows:
        typer.echo("No matches found yet. Run: python -m marnow.cli match <resume_id> <job_id>")
        raise typer.Exit(0)

    typer.echo("id\tresume_id\tjob_id\tscore_total\tcreated_at")
    for mid, rid, jid, total, ts in rows:
        typer.echo(f"{mid}\t{rid}\t{jid}\t{total}\t{ts}")


if __name__ == "__main__":
    app()
