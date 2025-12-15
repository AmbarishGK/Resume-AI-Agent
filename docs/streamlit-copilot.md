# Streamlit Copilot (RAG)

This is the most interactive way to use the project. It runs a local FastAPI server + Streamlit UI.

## What it does
- Upload a resume PDF and paste a job description (JD)
- Index both into a local vector store (Chroma)
- Ask questions (RAG) and run copilot-style actions:
  - score
  - rewrite (apply suggested changes and rescore)
  - export LaTeX / PDF

## Prerequisites

### 1) Install optional dependencies

```bash
uv pip install -r requirements_rag.txt
```

### 2) Start Ollama + pull models

This project uses Ollama for embeddings and generation.

```bash
ollama serve

# recommended defaults used by the server/UI
ollama pull nomic-embed-text
ollama pull llama3
ollama pull mistral:instruct
ollama pull llama2:13b
```

You can change models with env vars:

- `OLLAMA_EMBED_MODEL` (default: `nomic-embed-text`)
- `OLLAMA_LLM_MODEL` (default: `llama3`)

## Run

### 1) Start the backend

```bash
uv run uvicorn tools.rag_resume_server:app --reload --port 8100
```

### 2) Start the Streamlit UI

```bash
uv run streamlit run tools/rag_resume_app.py --server.port 8502
```

Open the UI at `http://127.0.0.1:8502`.

## Typical flow in the UI

1) **Ingest**
- Upload resume PDF
- Paste JD text
- Click **Ingest resume + JD**

The backend will create/dedupe DB rows in `marnow.db` and return `resume_id` and `job_id` automatically.

2) **Check score**
- Click **Check score** to see the baseline heuristic score and missing skills.

3) **Apply suggested changes**
- Click **Apply suggested changes** to generate a rewritten version and rescore.
- A new `resume_id` is created for the rewritten resume.

4) **Download**
- Download `.tex` or `.pdf` (PDF requires `pdflatex`).

## Notes
- Vector store directory is controlled by `RAG_RESUME_CHROMA_DIR` (default `./rag_resume_chroma`).
- SQLite DB path is controlled by `MARNOW_DB` (default `./marnow.db`).
