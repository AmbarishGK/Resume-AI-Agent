# Getting Started

## 1) Clone

```bash
git clone <YOUR_REPO_URL>
cd Resume-AI-Agent
```

## 2) Create a virtual environment + install dependencies

Assumptions: Linux, Python 3.10+.

This repo uses `uv` (recommended), but regular `venv` works too.

### Option A: uv (recommended)

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
python -m playwright install chromium
```

### Option B: standard venv

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## 3) Create the database

The DB is SQLite. By default it’s created at `./marnow.db`.

```bash
python -m marnow.cli initdb

# optional: seed the skills table (used by the matcher)
python -m marnow.cli seed-skills app/data/skills/skills.csv
```

If you want the DB somewhere else:

```bash
export MARNOW_DB=/path/to/marnow.db
python -m marnow.cli initdb
```

## 4) Run the pipeline

```bash
python tools/workflow.py
```

Outputs:

- scraped listings: `app/data/jobs/jobs.csv`
- fetched JDs: `app/data/jds/*.txt`
- SQLite DB: `marnow.db` (or whatever `MARNOW_DB` points to)

## 5) Ingest a resume + run a match

```bash
python -m marnow.cli ingest-resume app/data/resumes/resume.pdf

# pick a job_id from the DB, then:
python -m marnow.cli match <resume_id> <job_id>
python -m marnow.cli report <match_id>
```

## Optional: run the Streamlit copilot

See `streamlit-copilot.md` for the full setup (requires Ollama + `requirements_rag.txt`).

## Optional: build the docs site

```bash
mkdocs serve
```
