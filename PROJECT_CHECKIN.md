# Project Check-in

**Project Info:** MaRNoW - Resume & Cover Letter Copilot  
**Team:** Individual Project (coordinated group with Deeksha and Paul, but separate implementation)

---

## Project Activities Completed Since Last Check-in

### 1. MaRNoW AI Copilot (Small + Large Local Models)

I implemented a new AI copilot script that uses local open-source LLMs (Mistral-7B as the "small" model, LLaMA 2-13B as the "large" model) to analyze a resume against a specific JD and generate concrete outputs suitable for ATS and recruiters.

**Key components:**
- **File:** `tools/ai_copilot.py`
- **Inputs:**
  - `--resume-id` from `marnow.db` (resumes table), or `--resume-file` (PDF/DOCX/TXT)
  - `--job-id` from `marnow.db` (job_posts table), or `--jd-file` (JD text/PDF/DOCX)

**Small model (Mistral-7B) responsibilities:**
- Parse the full resume text and extract three logical sections:
  - Skills / Technical Skills
  - Experience / Work Experience
  - Projects
- Analyze a pair (resume, JD) and output structured JSON:
  - `jd_key_skills` - skills/requirements inferred from JD
  - `resume_present_skills` - skills clearly present in resume
  - `missing_skills` - JD skills underrepresented or absent in resume
  - `notes` - short summary of alignment/gaps

**Large model (LLaMA 2-13B) responsibilities:**
- Rewrite the **Skills** section as a flat list of 1-2 word tokens (e.g., `Python`, `Robotics`, `LLMs`), suitable for ATS keyword matching.
- Rewrite **Experience** bullets while:
  - Preserving roughly one-to-one mapping between original and new bullets (no merging multiple bullets into one).
  - Integrating JD-relevant skills (robotics, ML, LLMs, etc.) only when supported by existing resume content.
  - Keeping bullets impact-focused and metric-friendly.
- Generate a **JD Skills Coverage Report** explaining:
  - Which JD skills were missing or weak.
  - How the suggested bullets now surface those skills.
- Generate a **tailored cover letter** draft that:
  - Uses resume evidence + JD text.
  - Stays truthful (no invented companies, degrees, or tools).
  - Is formatted as a short, recruiter-friendly letter (3-6 paragraphs).

**Modes implemented in `ai_copilot.py`:**
- `--mode analysis` - only print the JSON skill alignment (no rewrites or cover letter).
- `--mode rewrite` - skill alignment + Skills/Experience before/after + coverage report.
- `--mode cover-letter` - skill alignment + cover letter draft only.
- `--mode full` - alignment + rewrites + coverage + cover letter (full copilot pass).

This directly supports many of the proposal prompts:
- Check my resume vs a JD and surface gaps.
- List JD skills and which ones I lack.
- Rewrite bullets for specific skills (Python/Kubernetes, ML/robotics, etc.).
- Suggest stronger, metric-driven bullets.
- Generate a role-specific cover letter grounded in resume content.


### 2. Resume+JD RAG Backend (Vector Store over marnow.db)

I added a separate RAG (Retrieval-Augmented Generation) backend dedicated to resume+JD analysis, mirroring the earlier financial RAG app but plugged into the MaRNoW SQLite database instead of PDFs.

**File:** `tools/rag_resume_server.py`

**Functionality:**
- **/ingest_pair** (`POST`):
  - Inputs: `resume_id` and `job_id` (foreign keys into `resumes` and `job_posts`).
  - Loads full text fields from `marnow.db`.
  - Splits each into overlapping text chunks using `RecursiveCharacterTextSplitter`.
  - Builds LangChain `Document`s with metadata (source = `"resume"` or `"jd"`, chunk index, company/role, etc.).
  - Indexes all chunks in a **Chroma** vector store using **OllamaEmbeddings** (default `nomic-embed-text`).

- **/query** (`POST`):
  - Inputs: `query` string and `mode` (`"all" | "resume" | "jd"`).
  - Retrieves top-k chunks from the vector store filtered by `source` (JD-only, resume-only, or both).
  - Builds a labeled `Context:` string combining retrieved JD and resume chunks.
  - Calls a single Ollama LLM model (default `llama3`, configurable via `OLLAMA_LLM_MODEL`) to answer based solely on that context.
  - Returns the answer plus a list of source chunks with metadata.

- **/explain** (`POST`):
  - Input: `content` (a raw text chunk).
  - LLM explains the chunk in plain language without fabricating missing details.

This backend is useful for:
- Interactive questions like “show me the parts of the JD that mention robotics/LLMs”.
- Validating that suggested bullets are anchored in actual resume text.
- Future extensions such as RAG over multiple JDs or over scraped company pages.


### 3. Streamlit UI for Resume+JD RAG Exploration

**File:** `tools/rag_resume_app.py`

I built a small Streamlit app that connects to `rag_resume_server.py`, analogous to the earlier financial PDF RAG UI.

**Features:**
- Sidebar:
  - Enter `Resume ID` (`resumes.id`) and `Job ID` (`job_posts.id`).
  - Button to ingest that pair via `/ingest_pair`.
- Main panel:
  - Free-form question box to ask about the resume+JD pair.
  - Retrieval mode selector:
    - All (JD + resume)
    - JD only
    - Resume only
  - Display of the LLM’s answer.
  - Expandable list of retrieved sources, each showing:
    - Whether it’s a JD or resume chunk.
    - JD company/role or resume_id.
    - Raw text content.
  - `Explain Source N` button to call `/explain` for a particular chunk.

This gives an interactive way to debug and understand what context the LLM is using, complementing the more structured CLI copilot.


## Project Activities In Progress

- **Refining prompt design** for:
  - JD keyword extraction and canonicalization into short skill tokens.
  - Resume-JD alignment explanations targeted at ATS-style criteria.
  - Gap identification and prioritization by impact.
  - Stable bullet rewrites that never merge or drop important experiences.
- **Connecting RAG + Copilot:**
  - Designing how `ai_copilot.py` could optionally use retrieved chunks (from the RAG server) instead of full texts, to scale to longer resumes/JDs and multi-JD comparisons.
- **Testing local models and performance trade-offs:**
  - Measuring latency and stability of Mistral-7B vs LLaMA 2-13B vs llama3 for different tasks (analysis vs generation vs RAG QA).
- **Validation logic:**
  - Prototyping flows to detect and avoid hallucinated technologies/employers in rewrites and cover letters by cross-checking against resume text.


## Project Activities Planned

- **End-to-end Copilot Modes:**
  - Implement named modes (or presets) for the proposal’s prompts, for example:
    - "Score match + gaps" (prompts 1-2, 6, 14, 19-20).
    - "Rewrite Projects for specific skills" (prompt 3).
    - "High-impact bullet suggestions" (prompts 5, 8, 9, 15).
    - "Cover letter generator" (prompts 4, 13, 16-18).

- **LaTeX Resume & Cover Letter Generator:**
  - Use bullet rewrites and skill tokens from `ai_copilot.py` to:
    - Populate LaTeX templates for a one-page ATS-safe resume.
    - Populate a LaTeX or Markdown cover letter template.

- **SQLite Schema Extensions:**
  - Extend `marnow.db` schema to store:
    - Extracted JD and resume skills/keywords as a separate table.
    - Versioned rewritten bullets and cover-letter drafts as artifacts.

- **Tighter ATS Keyword Extractor:**
  - Use spaCy or a simple phrase matcher over JD and rewrites to:
    - Normalize skills (e.g., `Machine Learning`, `ML`, `Deep Learning`).
    - Surface a minimal, non-redundant skill set for the Skills section.

- **RAG over Company Sites and Multiple JDs:**
  - Extend the RAG backend to:
    - Ingest and index multiple JDs per company.
    - Ingest company careers/mission/culture pages.
    - Support prompts like:
      - "Find the best-fit JD among these postings for my resume."
      - "Summarize this company’s mission/culture from their site." (prompts 11-12).

- **Voice Interface (future extension):**
  - Explore Whisper or local voice agents to:
    - Accept spoken prompts (e.g., "Check my resume for this JD and rewrite bullets for ML").
    - Read back summaries or gap analyses.

- **Final integration & evaluation:**
  - Wire together:
    - scraping → JDs → `marnow.db` → AI copilot **and/or** RAG server → LaTeX/Markdown export.
  - Create a small set of test JDs and resumes to benchmark:
    - Match scores
    - Gap detection quality
    - Bullet/cover-letter quality (human evaluation)
    - ATS keyword coverage.
