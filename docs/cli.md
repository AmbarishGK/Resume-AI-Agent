# CLI (ingest + match)

The CLI lives in `marnow/cli.py`.

## Initialize DB

```bash
python -m marnow.cli initdb
```

## Ingest job descriptions

```bash
python -m marnow.cli ingest-jd app/data/jds/company-role.txt
```

## Ingest resumes

```bash
python -m marnow.cli ingest-resume app/data/resumes/resume.pdf
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
