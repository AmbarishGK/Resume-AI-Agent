# Flow summary (archived)

This used to be a very detailed, step-by-step writeup of the pipeline.
It’s kept around as a reference, but the up-to-date docs are:

- `README.md` (how to run the repo)
- `WORKFLOW.md` (pipeline steps + flags)

## TL;DR

- `tools/workflow.py` orchestrates everything.
- outputs:
  - scraped listings: `app/data/jobs/jobs.csv`
  - fetched JDs: `app/data/jds/*.txt`
  - DB: `marnow.db` (or whatever `MARNOW_DB` points to)
