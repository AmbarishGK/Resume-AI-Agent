# Resume-AI-Agent

This repo is a small end-to-end pipeline for:

- scraping job postings from company career pages
- fetching the full job descriptions (JDs)
- ingesting resumes + JDs into a local SQLite DB
- scoring a resume <-> JD pair and reporting gaps

The core project works without any external services. There are also optional "copilot" scripts (RAG + local LLM workflows) under `tools/`.

## Quick start

```bash
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
python -m playwright install chromium

python tools/workflow.py
```

That runs:
1) scrape jobs → `app/data/jobs/jobs.csv`
2) fetch JDs → `app/data/jds/*.txt`
3) ingest JDs into SQLite → `marnow.db`

## Common commands

Scrape/fetch/ingest (manual):

```bash
python tools/jobscraper/main.py --config app/config/careers.yaml --out app/data/jobs/jobs.csv
python tools/make_jds_from_jobs.py --limit 10   # or --all

python -m marnow.cli initdb
python -m marnow.cli ingest-jd app/data/jds/company-role.txt
```

Resume ingestion + matching:

```bash
python -m marnow.cli ingest-resume app/data/resumes/resume.pdf
python -m marnow.cli match <resume_id> <job_id>
python -m marnow.cli report <match_id>
```

## Config

Scraper targets live in `app/config/careers.yaml`.

## Development hygiene (optional)

Ruff is included as a lightweight linter/formatter.

```bash
python -m ruff check .
python -m ruff format .
```

## Docs (MkDocs)

Local preview:

```bash
mkdocs serve
```

GitHub Pages:

- This repo includes a GitHub Actions workflow that deploys MkDocs to the `gh-pages` branch on every push to `main`.
- After the first run, enable Pages in GitHub repo settings and point it at `gh-pages`.

## Docs

- `SETUP.md` – setup notes
- `WORKFLOW.md` – pipeline details + flags
- `TROUBLESHOOTING.md` – common failures
