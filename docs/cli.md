# CLI (ingest + match)

The CLI lives in `marnow/cli.py`.

## Initialize DB

```bash
# creates ./marnow.db by default
python -m marnow.cli initdb

# optional: seed skills (recommended before matching)
python -m marnow.cli seed-skills app/data/skills/skills.csv
```

## Ingest job descriptions

```bash
python -m marnow.cli ingest-jd app/data/jds/company-role.txt
```

## Ingest resumes

```bash
python -m marnow.cli ingest-resume app/data/resumes/resume.pdf
```

## Find IDs (recommended)

If you are matching from the DB, you’ll need `resume_id` and `job_id`.

```bash
python tools/db_cli.py list-resumes --limit 10
python tools/db_cli.py list-jobs --limit 10

# optional filter
python tools/db_cli.py list-jobs --contains "stripe" --limit 20
```

## Match + report

```bash
python -m marnow.cli match <resume_id> <job_id>
python -m marnow.cli report <match_id>
```

## Notes

- If you need a specific DB path, set:

```bash
export MARNOW_DB=./marnow.db
```
