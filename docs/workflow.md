# Pipeline (workflow)

The entry point is `tools/workflow.py`. It orchestrates:

1. scrape jobs -> `app/data/jobs/jobs.csv`
2. fetch job descriptions -> `app/data/jds/*.txt`
3. ingest JDs into SQLite -> `marnow.db` (or `MARNOW_DB`)

Note: `workflow.py` will create the DB if needed, but for manual usage you can run `python -m marnow.cli initdb`.

## Basic run

```bash
python tools/workflow.py
```

## Useful flags

```bash
# fetch all JDs and ingest all
python tools/workflow.py --all-jds --all-ingest

# filter during scraping
python tools/workflow.py --include "software,engineer" --exclude "senior,staff" --locations "remote,sf"

# reuse existing artifacts
python tools/workflow.py --skip-scrape --skip-fetch
```

## Related docs

- See `setup.md` for dependency install
- See `troubleshooting.md` if scraping/fetching fails
