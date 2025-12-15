# Troubleshooting

## Playwright browser not found

```bash
python -m playwright install chromium
```

## Database path issues

```bash
export MARNOW_DB=./marnow.db
```

## Workflow debugging

Try running each step by itself:

```bash
python tools/jobscraper/main.py --config app/config/careers.yaml --out app/data/jobs/jobs.csv
python tools/make_jds_from_jobs.py --limit 2
python -m marnow.cli initdb
```
