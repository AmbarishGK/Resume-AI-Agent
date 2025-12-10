# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Setup & Environment

- Python project managed via `uv` with a local virtual environment at `.venv/`.
- Primary dependencies are in `requirements.txt`; Playwright’s Chromium browser must also be installed.
- The MaRNoW SQLite database defaults to `marnow.db` in the project root, overridable via `MARNOW_DB`.
- For GPU + Ollama-based workflows, a CUDA-enabled Docker environment is provided.

### Local setup

```bash
# From project root
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
python -m playwright install chromium

# Or use the quick script (does all of the above)
./activate.sh
```

### Docker / docker-compose (GPU + Ollama)

- Image is built from `Dockerfile` and wired up via `docker-compose.yml` as the `marnow` service.
- The container:
  - Mounts the repo at `/app` and `~/.ollama` into `/root/.ollama`.
  - Starts `ollama serve` via `entrypoint.sh`, health-checks the Ollama API, optionally pre-pulls models from `OLLAMA_MODELS`, and then hands off to the container `CMD`.
  - Exposes Ollama on port `11500` (host) → `11434` (container).

Typical flow:

```bash
# Build + run GPU dev container
docker compose up --build

# Exec into the container (project mounted at /app)
docker exec -it marnow bash
cd /app
source .venv/bin/activate  # if you create one inside the container
```

## Common Commands

### End-to-end job → JD → DB workflow

Entry point orchestrator: `tools/workflow.py`.

```bash
# Default: scrape jobs, fetch first 10 JDs, ingest those JDs into marnow.db
python tools/workflow.py

# Fetch and ingest all available JDs
python tools/workflow.py --all-jds --all-ingest

# Filter jobs during scraping
python tools/workflow.py \
  --include "software,engineer" \
  --exclude "senior,staff" \
  --locations "remote,sf"

# Use existing jobs.csv and/or JD files
python tools/workflow.py --skip-scrape --skip-fetch   # only ingest
```

### Manual step execution

```bash
# 1) Scrape jobs from configured career pages
python tools/jobscraper/main.py \
  --config app/config/careers.yaml \
  --out app/data/jobs/jobs.csv \
  --include "software,engineer" \
  --locations "remote"

# 2) Fetch job descriptions from jobs.csv into app/data/jds/
python tools/make_jds_from_jobs.py --limit 10   # or --all

# 3) Initialize DB and ingest a specific JD
python -m marnow.cli initdb
python -m marnow.cli ingest-jd app/data/jds/company-role.txt
```

### Resume ingestion and matching

```bash
# Ingest a resume (PDF or DOCX)
python -m marnow.cli ingest-resume app/data/resumes/resume.pdf

# Match a resume (id=R) to a job (id=J)
python -m marnow.cli match R J

# View a stored match report
python -m marnow.cli report <match_id>
```

### Notes on tests and linting

- There are currently no automated tests or linting/tooling scripts defined in this repo (no `pytest` config, `Makefile`, or `pyproject.toml`).
- If you add tests or linting, prefer project-root entrypoints (e.g., `python -m pytest`) and update this WARP.md with the relevant commands, including how to run a single test.

## High-Level Architecture

At a high level, this repo wires together three main layers:

1. **Data collection (scraping + fetching)** in `tools/` and `app/`.
2. **Persistence and ingestion** in `marnow/`.
3. **Matching and CLI orchestration** in `marnow/cli.py` and `tools/workflow.py`.

### Data collection layer

- **Config-driven job scraping** (`tools/jobscraper/main.py`)
  - Treats the project root (`Resume-AI-Agent/`) as `BASE_DIR` and uses `app/config/careers.yaml` to describe each target careers site.
  - Uses Playwright synchronously (`sync_playwright`) to:
    - Handle cookie/consent banners.
    - Optionally paginate via scroll or "load more" buttons per-site.
    - Extract job cards using `list_selector`, then fields via `title_selector`, `link_selector`, `location_selector`, and `date_selector`.
  - Normalizes and filters jobs via `matches_filters`, supporting include/exclude keyword lists and location filters.
  - Deduplicates by `link` and writes a canonical `app/data/jobs/jobs.csv` with columns:
    - `role`, `date`, `location`, `link`, `source`, `keywords_matched`.
  - New companies are added purely by editing `app/config/careers.yaml`; scraper logic stays generic.

- **JD fetching** (`tools/make_jds_from_jobs.py`)
  - Reads `app/data/jobs/jobs.csv`, then for each row:
    - Fetches `link` via `requests`.
    - Uses `BeautifulSoup` to strip scripts/styles and heuristically select the main content (prefers large blocks under selectors like `main`, `[role=main]`, `.job-description`, etc.).
  - Writes each JD as a plain text file under `app/data/jds/` named `{source}-{role}.txt` (slugified).
  - Skips existing files to make repeated runs idempotent.

- **Data directories under `app/data/`**
  - `jobs/` – latest scraped job listings (CSV).
  - `jds/` – text JDs ready for ingestion.
  - `resumes/` – user-provided resume files (PDF/DOCX).
  - `skills/skills.csv` – skills and aliases used by the matching engine.

### Ingestion and persistence layer (`marnow/`)

- **Database module (`marnow/db.py`)**
  - Centralizes SQLite access with `DB_PATH = os.environ.get("MARNOW_DB", "marnow.db")`.
  - On connect, ensures the DB directory exists and enables foreign keys.
  - Defines schema via `SCHEMA_SQL` and `init_db()` for:
    - `resumes` – parsed resume text and metadata.
    - `job_posts` – ingested JDs (company, role, text, source URL).
    - `skills` – normalized skills, aliases, and categories.
    - `matches` – per resume/job pair scores and gaps.
    - `artifacts` – generated LaTeX/Markdown artifacts (not yet wired from this repo’s entrypoints).
  - Provides `upsert_resume` and `upsert_job` which dedupe by SHA-256 content hash, returning `(id, created_bool)`.

- **Ingestion utilities (`marnow/ingest.py`)**
  - `ingest_jd(path)`
    - Reads JD text, parses metadata via `_parse_meta`:
      - First 5 lines may contain `# company:` and `# role:` hints.
      - Otherwise, infers from filename stem, splitting on `-`/`_` (e.g., `stripe-backend-engineer` → company `stripe`, role `backend engineer`).
    - Inserts into `job_posts` via `upsert_job`.
  - `ingest_resume_pdf` / `ingest_resume_docx`
    - Extract text from PDFs via `pypdf` and DOCX via `python-docx` and upsert into `resumes`.
  - `seed_skills_csv(csv_path)`
    - Reads `skills.csv` and forwards rows to `seed_skills` in `db.py` for population of the `skills` table.
  - `ensure_db()` wraps `init_db()` to make one-shot CLI usage simple.

### Matching and CLI layer

- **Matching engine (`marnow/match.py`)**
  - Uses `MARNOW_DB` (same env var convention) to connect to SQLite directly via `sqlite3`.
  - Builds an in-memory skills index from the `skills` table (`_skill_index`) using canonical skills plus aliases.
  - `score_pair(resume_txt, jd_txt, jd_role, jd_company, skills_idx)` computes a composite score:
    - **Skills overlap**: bag-of-words presence across resume and JD, normalized by JD skill demand.
    - **Responsibilities**: counts occurrences of verbs/phrases like `design`, `deploy`, `pipelines`, etc.
    - **Seniority alignment**: heuristics over textual cues for new-grad vs senior postings.
    - **Domain alignment**: coarse domain buckets (AI, robotics, backend, fullstack, firmware, data) driven by keyword sets.
    - Returns `total` and component scores plus a list of `missing` skills.
  - `run_match(resume_id, job_id)`
    - Loads the given resume and JD from the DB, builds the skills index, and calls `score_pair`.
    - Persists results into the `matches` table (including gaps JSON and timestamp) and returns the score dict plus the new `match_id`.
  - `report_match(match_id)`
    - Joins `matches`, `resumes`, and `job_posts` to return a structured summary (scores, missing skills, filenames, company/role) for display.

- **CLI façade (`marnow/cli.py`)**
  - Typer-based CLI exposing high-level commands:
    - `initdb` – initializes schema.
    - `seed-skills` – seeds the `skills` table from a CSV (default `/app/data/skills/skills.csv` in container contexts).
    - `ingest-jd PATH` – ingests a single JD text file.
    - `ingest-resume PATH` – ingests a single resume (`.pdf` or `.docx`).
    - `match RESUME_ID JOB_ID` – runs the matcher and prints a short summary plus top missing skills.
    - `report MATCH_ID` – pretty-prints detailed scores for an existing match.
  - All commands call `ensure_db()` first, so they are safe on a fresh project.

### Orchestrator (`tools/workflow.py`)

- Acts as the main entrypoint tying the scraper, JD fetcher, and ingestion together:
  - Sets `BASE_DIR` to the project root and ensures it is on `sys.path` so `marnow` is importable.
  - If `MARNOW_DB` is unset, sets it to `<BASE_DIR>/marnow.db` so local runs default to a project-root DB.
  - Defines three internal steps:
    - `run_scraper(...)` – calls `tools/jobscraper/main.py` via `subprocess.run`, verifies that `jobs.csv` exists.
    - `run_fetch_jds(...)` – calls `tools/make_jds_from_jobs.py` via `subprocess.run` and checks exit code.
    - `run_ingest_jds(...)` – directly imports `marnow.ingest`, enumerates JD files in `app/data/jds/`, and ingests them with per-file error handling and summary counts.
  - Supports granular control via flags:
    - `--jd-limit` / `--all-jds` for fetching.
    - `--ingest-limit` / `--all-ingest` for ingestion.
    - `--skip-scrape`, `--skip-fetch`, `--skip-ingest` to reuse existing artifacts.
    - `--include`, `--exclude`, `--locations`, `--no-headless`, `--dump-html` for controlling scraping behavior.

## Key Operational Considerations for Future Warp Agents

- Always run project commands from the repository root so relative paths in `tools/` and `marnow/` resolve correctly.
- Ensure `MARNOW_DB` is set consistently if you need a non-default DB path (e.g., inside Docker vs local dev); `tools/workflow.py` will set it to a local file when unset.
- When adding new scraping targets, prefer editing `app/config/careers.yaml` instead of touching the scraper code; the scraper is deliberately config-driven.
- If you modify JD filename conventions or add metadata headers, keep `_parse_meta` in `marnow/ingest.py` and the slugging logic in `tools/make_jds_from_jobs.py` in sync so ingestion continues to infer company/role correctly.
