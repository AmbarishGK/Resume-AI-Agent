# WRAP.md

Session wrap-up for ongoing MaRNoW (Resume-AI-Agent) work. This file captures what was added/changed so future sessions can resume quickly.

## 1. New AI Copilot Script (non-RAG, direct JD+resume)

### File
- `tools/ai_copilot.py`

### Purpose
Command-line tool that:
- Loads a **resume** and **job description (JD)** either from:
  - `marnow.db` (`resumes.id`, `job_posts.id`), or
  - direct files (`--resume-file`, `--jd-file`).
- Uses local open-source models via **Ollama** to:
  - Extract Skills / Experience / Projects sections from the resume.
  - Analyze overlap between JD skills and resume skills.
  - Propose **section-wise rewrites** for `SKILLS` and `EXPERIENCE`.
  - Produce a comparison: **BEFORE vs AFTER** for both sections.
  - Generate a markdown report explaining how JD skills are integrated.

### Models
- Small model (analysis + section extraction): configurable via `--small-model`, default `mistral:instruct`.
- Large model (rewrites + coverage report): configurable via `--large-model`, default `llama2:13b`.

### Key Behavior
- **Section extraction**: small model parses the full resume text and returns JSON with:
  - `skills`, `experience`, `projects` (raw text for each section).
- **Skill alignment**: small model sees full JD text + full resume text and returns JSON:
  - `jd_key_skills` – list of skills/requirements from JD.
  - `resume_present_skills` – skills clearly present in resume.
  - `missing_skills` – JD skills weak/absent in resume.
  - `notes` – short summary.
- **Rewrites** (large model):
  - Input: JD text, extracted sections, and skill-alignment JSON.
  - Output markdown with exactly two headings:
    - `### SKILLS (suggested rewrite)` – **1–2 word tokens only** (e.g., `Python`, `Robotics`, `Machine Learning`, `LLMs`).
    - `### EXPERIENCE (suggested rewrite)` – per-bullet rewrites.
  - Prompt explicitly enforces:
    - No fabrication of new tools/companies/roles.
    - Preserve roughly one rewritten bullet per original bullet (no merging).
    - Integrate JD skill tokens into bullets **only where consistent** with original content.

### CLI Usage Examples

Using existing DB entries (recommended):

```bash
# Everything with small model (Mistral only)
python tools/ai_copilot.py \
  --resume-id 5 \
  --job-id 1 \
  --small-model mistral:instruct \
  --large-model mistral:instruct \
  > out_small_only.md 2>&1

# Hybrid: small for analysis, large for rewrites (typical)
python tools/ai_copilot.py \
  --resume-id 5 \
  --job-id 1 \
  --small-model mistral:instruct \
  --large-model llama2:13b \
  > out_hybrid.md 2>&1

# Everything with large model (LLaMA 2 only)
python tools/ai_copilot.py \
  --resume-id 5 \
  --job-id 1 \
  --small-model llama2:13b \
  --large-model llama2:13b \
  > out_large_only.md 2>&1
```

Key sections in the output files:
- `=== SKILL ALIGNMENT (JSON) ===` – JD vs resume skills.
- `=== COMPARISON: SKILLS SECTION ===` – Skills BEFORE vs AFTER.
- `=== COMPARISON: EXPERIENCE SECTION ===` – Experience BEFORE vs AFTER.
- `=== JD SKILLS COVERAGE REPORT ===` – textual explanation of how JD skills are integrated into new bullets.


## 2. New RAG Backend for Resume + JD

### File
- `tools/rag_resume_server.py`

### Purpose
RAG-style backend (FastAPI + Chroma + Ollama), analogous to `rag_app/rag_server.py`, but:
- Ingests **one resume + one JD pair** from `marnow.db` by ID.
- Builds a vector store over chunks of resume + JD.
- Answers arbitrary questions using retrieved chunks as context.

### How It Works

1. **Ingest pair** (`POST /ingest_pair`):
   - Input JSON:
     - `resume_id` – `resumes.id` in `marnow.db`.
     - `job_id` – `job_posts.id` in `marnow.db`.
   - Loads full `resumes.text` and `job_posts.text`.
   - Splits each into chunks with `RecursiveCharacterTextSplitter`.
   - Wraps as LangChain `Document`s with metadata:
     - JD chunks: `{source: "jd", job_id, company, role, chunk_index}`.
     - Resume chunks: `{source: "resume", resume_id, filename, fmt, chunk_index}`.
   - Stores all docs in **Chroma** at `./rag_resume_chroma` using `OllamaEmbeddings` (default `nomic-embed-text`).

2. **Query** (`POST /query`):
   - Input JSON:
     - `query`: user question (e.g., "List JD skills I lack", "Rewrite bullets for robotics").
     - `mode`: `"all" | "resume" | "jd"` (retrieval filter on `source`).
   - Uses `vectorstore.as_retriever(search_kwargs={"k": 12, filter: ...})` to fetch relevant chunks.
   - De-duplicates near-identical docs.
   - Builds a `Context:` string with labeled chunks:
     - `[JD CHUNK]` versus `[RESUME CHUNK]`.
   - Calls `Ollama(model=LLM_MODEL)` (default `llama3`) to answer *only using that context*.
   - Returns JSON:
     - `answer` – grounded answer.
     - `sources` – list of retrieved chunks + metadata.

3. **Explain** (`POST /explain`):
   - Input: `{content}` – raw text from a retrieved chunk.
   - LLM explains that chunk in plain language; helpful for understanding a specific JD or resume segment.

### Running the Backend

From project root (with `.venv` active and Ollama running):

```bash
# Ensure dependencies are installed (once)
uv pip install fastapi uvicorn chromadb \
  langchain-core langchain-community langchain-text-splitters \
  streamlit requests

# Start RAG backend
uv run uvicorn tools.rag_resume_server:app --reload --port 8100
```

Server base URL: `http://127.0.0.1:8100`

Example manual `curl` to ingest a pair:

```bash
curl -X POST http://127.0.0.1:8100/ingest_pair \
  -H 'Content-Type: application/json' \
  -d '{"resume_id": 5, "job_id": 1}'
```


## 3. New Streamlit UI for Resume + JD RAG

### File
- `tools/rag_resume_app.py`

### Purpose
Interactive UI (similar to `rag_app/streamlit_app.py`) for exploring the resume+JD RAG server.

### Features
- Sidebar: choose `resume_id` and `job_id` from `marnow.db` and ingest that pair.
- Main panel:
  - Ask questions about that pair with retrieval modes:
    - **All (JD + resume)**
    - **JD only**
    - **Resume only**
  - Display model answer.
  - Show retrieved source chunks with:
    - `source` (`jd` / `resume`)
    - `company` / `role` for JD
    - `resume_id` for resume
    - underlying text
  - Per-source **Explain** button that calls `/explain` on the backend.

### Running the UI

After backend is running on port 8100:

```bash
uv run streamlit run tools/rag_resume_app.py --server.port 8502
```

UI URL: `http://127.0.0.1:8502`

### Typical Workflow in the UI

1. **Ingest**:
   - In sidebar, set `Resume ID` and `Job ID` (e.g., `5` and `1`).
   - Click **"Ingest this pair"**.

2. **Ask**:
   - In main panel, enter a question, for example:
     - "List the skills in the JD and show which ones my resume lacks."
     - "Rewrite my experience bullets to emphasize robotics and ML."
     - "Suggest 3 bullets that better highlight LLM experience while staying truthful."
   - Choose retrieval mode: All / JD only / Resume only.
   - Click **"Ask"**.

3. **Inspect sources and explanations**:
   - Expand each retrieved source to see exactly which JD/resume text was used.
   - Optionally click **"Explain Source N"** to have the LLM summarize that chunk.


## 4. How This Fits Together & Next Steps

- **Existing MaRNoW pipeline** (`tools/workflow.py`, `marnow/` modules) still handles:
  - Scraping jobs → fetching JDs → ingesting into `marnow.db`.
  - Resume ingestion and scoring via `marnow.cli match`.
- **New pieces** built in this session:
  1. `tools/ai_copilot.py`: prompt-based analyzer/rewriter (no vector DB) for a single resume+JD pair.
  2. `tools/rag_resume_server.py`: RAG backend that turns a resume+JD pair from `marnow.db` into a vector store and answers questions with retrieved chunks.
  3. `tools/rag_resume_app.py`: Streamlit frontend to interactively query and inspect that RAG backend.

### Good follow-up tasks
- Tighten the skill-token normalization (e.g., canonicalizing JD skills to a controlled vocabulary).
- Add preset question templates to `rag_resume_app.py` (dropdowns for "check match", "rewrite bullets", etc.).
- Optionally integrate RAG server calls back into `ai_copilot.py` so CLI can switch between "direct" mode and "RAG" mode.
- Persist user-selected rewrites back into new resume files (LaTeX/Markdown templates) for end-to-end automation.
