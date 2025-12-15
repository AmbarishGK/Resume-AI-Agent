#!/usr/bin/env python3
"""RAG backend for MaRNoW resume + JD analysis.

This server mirrors the design of rag_app/rag_server.py but instead of
indexing PDFs, it:

- Loads a resume and job description (JD) from marnow.db tables
  (resumes, job_posts) by ID.
- Chunks them into Documents with metadata indicating source ("resume" vs "jd").
- Stores them in a Chroma vector store using Ollama embeddings.
- Exposes endpoints for:
    - POST /ingest_pair  – (re)index a given (resume_id, job_id)
    - POST /query        – RAG-style QA over that resume+JD pair
    - POST /explain      – explain a specific source chunk

You can run this with uvicorn, for example:

  uv run uvicorn tools.rag_resume_server:app --reload --port 8100

and then point a Streamlit UI at http://localhost:8100.
"""

import os
import sqlite3
import io
import json
import tempfile
import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Literal, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel

from pypdf import PdfReader

from marnow.db import upsert_resume, upsert_job
from marnow.match import score_pair, _skill_index

from tools.latex_utils import render_resume_tex, pdflatex_available, build_pdf_from_tex

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.llms import Ollama

# Import copilot helpers (small+large model pipeline)
from tools.ai_copilot import (
    extract_resume_sections,
    analyze_alignment_small_model,
    generate_rewrites_large_model,
    generate_integration_report,
    generate_cover_letter_large_model,
    SMALL_MODEL_DEFAULT,
    LARGE_MODEL_DEFAULT,
)

# Where to persist the RAG vector DB for resume+JD pairs
DB_DIR = os.environ.get("RAG_RESUME_CHROMA_DIR", "./rag_resume_chroma")

# marnow SQLite DB path
MARNOW_DB = os.environ.get("MARNOW_DB", "marnow.db")

# Embedding + LLM models for Ollama
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3")


vectorstore: Optional[Chroma] = None
all_docs: List[Document] = []
current_pair: Optional[Tuple[int, int]] = None  # (resume_id, job_id)

app = FastAPI(title="MaRNoW Resume+JD RAG Server")


# ---------- Pydantic models ----------


class IngestPairRequest(BaseModel):
    resume_id: int
    job_id: int


class IngestUploadResponse(BaseModel):
    status: str
    message: str
    resume_id: int
    job_id: int
    num_documents: int


class ScoreRequest(BaseModel):
    resume_id: int
    job_id: int


class ScoreResponse(BaseModel):
    total: float
    skills_score: float
    resp_score: float
    seniority_score: float
    domain_score: float
    missing: List[str]


class ApplyRewriteRequest(BaseModel):
    resume_id: int
    job_id: int
    small_model: Optional[str] = None
    large_model: Optional[str] = None
    reindex: bool = True


class ApplyRewriteResponse(BaseModel):
    status: str
    message: str
    original_resume_id: int
    new_resume_id: int
    job_id: int
    skills_after: str
    experience_after: str
    score_before: ScoreResponse
    score_after: ScoreResponse
    delta_total: float


class IngestPairResponse(BaseModel):
    status: str
    message: str
    resume_id: int
    job_id: int
    num_documents: int


class QueryRequest(BaseModel):
    query: str
    mode: Literal["all", "resume", "jd"] = "all"


class QueryResponse(BaseModel):
    answer: str
    sources: List[dict]


class ChatRequest(BaseModel):
    resume_id: int
    job_id: int
    message: str
    mode: Literal["all", "resume", "jd"] = "all"
    small_model: Optional[str] = None
    large_model: Optional[str] = None


class ChatResponse(BaseModel):
    kind: str
    answer: str
    payload: dict
    sources: List[dict]


class ExplainRequest(BaseModel):
    content: str


class ExplainResponse(BaseModel):
    explanation: str


class CopilotRequest(BaseModel):
    resume_id: int
    job_id: int
    mode: Literal["analysis", "rewrite", "cover-letter", "full"] = "rewrite"
    small_model: Optional[str] = None
    large_model: Optional[str] = None
    context: Literal["full", "rag"] = "full"  # whether to use full texts or RAG chunks


class CopilotResponse(BaseModel):
    analysis: dict
    resume_sections: dict
    skills_before: Optional[str] = None
    skills_after: Optional[str] = None
    experience_before: Optional[str] = None
    experience_after: Optional[str] = None
    coverage_report_md: Optional[str] = None
    rewrites_md_raw: Optional[str] = None
    cover_letter: Optional[str] = None


# ---------- DB helpers ----------


def _connect_marnow() -> sqlite3.Connection:
    if not os.path.exists(MARNOW_DB):
        raise RuntimeError(f"MARNOW_DB not found at {MARNOW_DB}")
    con = sqlite3.connect(MARNOW_DB)
    con.execute("PRAGMA foreign_keys=ON;")
    return con


def load_resume_and_jd(resume_id: int, job_id: int) -> Tuple[dict, dict]:
    """Load resume and JD rows from marnow.db.

    Returns (resume_row, jd_row) where each is a dict with keys:
      - id, filename, text, ...
    for resumes; and
      - id, company, role, text, ...
    for job_posts.
    """

    con = _connect_marnow()
    try:
        r = con.execute(
            "SELECT id, filename, fmt, text, parsed_at, hash, notes FROM resumes WHERE id=?",
            (resume_id,),
        ).fetchone()
        if not r:
            raise RuntimeError(f"resume_id {resume_id} not found in resumes table")
        resume = {
            "id": r[0],
            "filename": r[1],
            "fmt": r[2],
            "text": r[3] or "",
            "parsed_at": r[4],
            "hash": r[5],
            "notes": r[6],
        }

        j = con.execute(
            "SELECT id, filename, company, role, source_url, text, ingested_at, hash "
            "FROM job_posts WHERE id=?",
            (job_id,),
        ).fetchone()
        if not j:
            raise RuntimeError(f"job_id {job_id} not found in job_posts table")
        jd = {
            "id": j[0],
            "filename": j[1],
            "company": j[2],
            "role": j[3],
            "source_url": j[4],
            "text": j[5] or "",
            "ingested_at": j[6],
            "hash": j[7],
        }
        return resume, jd
    finally:
        con.close()


# ---------- Scoring helpers ----------


def _load_skills_index() -> dict:
    con = _connect_marnow()
    try:
        rows = con.execute("select id, skill, aliases_json, category from skills").fetchall()
    finally:
        con.close()
    return _skill_index(rows)


def compute_score(resume_id: int, job_id: int) -> ScoreResponse:
    resume, jd = load_resume_and_jd(resume_id, job_id)
    idx = _load_skills_index()
    res = score_pair(
        resume_txt=resume.get("text", "") or "",
        jd_txt=jd.get("text", "") or "",
        jd_role=jd.get("role") or "",
        jd_company=jd.get("company") or "",
        skills_idx=idx,
    )
    return ScoreResponse(**res)


def _split_rewrites(rewrites_md: str) -> tuple[str, str]:
    skills_after = ""
    experience_after = ""
    marker_skills = "### SKILLS (suggested rewrite)"
    marker_exp = "### EXPERIENCE (suggested rewrite)"
    if marker_skills in rewrites_md:
        _, rest = rewrites_md.split(marker_skills, 1)
        if marker_exp in rest:
            skills_after, exp_rest = rest.split(marker_exp, 1)
            skills_after = skills_after.strip()
            experience_after = (marker_exp + "\n" + exp_rest.strip()).strip()
        else:
            skills_after = rest.strip()
    else:
        skills_after = rewrites_md.strip()
    return skills_after, experience_after


def _build_revised_resume_text(
    skills_after: str,
    experience_after: str,
    projects_before: str,
    original_resume_text: str,
) -> str:
    # Pragmatic plain-text draft: keep it readable + easy for matcher and LaTeX export.
    parts = [
        "RESUME (AUTO-GENERATED DRAFT)",
        "", 
        "SKILLS (rewritten)",
        (skills_after or "(no skills rewrite produced)"),
        "",
        "EXPERIENCE (rewritten)",
        (experience_after or "(no experience rewrite produced)"),
    ]
    if projects_before:
        parts += ["", "PROJECTS (original)", projects_before]

    # Keep the original extraction for traceability.
    parts += ["", "---", "ORIGINAL RESUME (PDF extracted text)", original_resume_text or ""]
    return "\n".join(parts).strip() + "\n"


def _slug(s: str) -> str:
    s = (s or "").strip().lower()
    s = "-".join(s.split())
    s = "".join(ch for ch in s if ch.isalnum() or ch in {"-", "_"})
    return s or "doc"


def _extract_pdf_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((pg.extract_text() or "") for pg in reader.pages)


# ---------- Document building & vectorstore ----------


def build_documents_for_pair(resume: dict, jd: dict) -> List[Document]:
    """Chunk resume + JD text into Documents with metadata.

    For now we use a simple character splitter for both.
    """

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=900,
        chunk_overlap=150,
        separators=["\n\n", "\n", " ", ""],
    )

    docs: List[Document] = []

    # JD chunks
    jd_text = jd.get("text", "") or ""
    jd_chunks = splitter.split_text(jd_text)
    for i, chunk in enumerate(jd_chunks):
        docs.append(
            Document(
                page_content=chunk,
                metadata={
                    "source": "jd",
                    "job_id": jd["id"],
                    "company": jd.get("company"),
                    "role": jd.get("role"),
                    "chunk_index": i,
                },
            )
        )

    # Resume chunks
    resume_text = resume.get("text", "") or ""
    r_chunks = splitter.split_text(resume_text)
    for i, chunk in enumerate(r_chunks):
        docs.append(
            Document(
                page_content=chunk,
                metadata={
                    "source": "resume",
                    "resume_id": resume["id"],
                    "filename": resume.get("filename"),
                    "fmt": resume.get("fmt"),
                    "chunk_index": i,
                },
            )
        )

    return docs


def build_vectorstore(docs: List[Document]) -> None:
    global vectorstore, all_docs

    all_docs = docs
    embeddings = OllamaEmbeddings(model=EMBED_MODEL)

    vectorstore = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=DB_DIR,
    )
    vectorstore.persist()


def run_query(query: str, mode: str = "all") -> Optional[Tuple[str, List[dict]]]:
    global vectorstore

    if vectorstore is None:
        return None

    search_kwargs: dict = {"k": 12}
    if mode == "resume":
        search_kwargs["filter"] = {"source": "resume"}
    elif mode == "jd":
        search_kwargs["filter"] = {"source": "jd"}

    retriever = vectorstore.as_retriever(search_kwargs=search_kwargs)
    docs: List[Document] = retriever.invoke(query)

    # Deduplicate near-identical docs
    unique_docs: List[Document] = []
    seen = set()
    for d in docs:
        meta = d.metadata or {}
        key = (
            meta.get("source"),
            meta.get("resume_id"),
            meta.get("job_id"),
            meta.get("chunk_index"),
            (d.page_content or "")[:80],
        )
        if key not in seen:
            seen.add(key)
            unique_docs.append(d)
    docs = unique_docs

    # Build context string
    context_chunks = []
    for d in docs:
        meta = d.metadata or {}
        label = meta.get("source", "?")
        ctx = f"[{label.upper()} CHUNK]\n" + (d.page_content or "")
        context_chunks.append(ctx)

    context = "\n\n---\n\n".join(context_chunks)[:6000]

    prompt = (
        "You are a resume & JD analysis assistant. "
        "Use ONLY the provided context, which contains chunks from a job description (JD) "
        "and a candidate's resume. If the answer is not supported by the context, say you don't know.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Answer:"
    )

    llm = Ollama(model=LLM_MODEL)
    answer = llm.invoke(prompt)

    sources = []
    for d in docs:
        meta = d.metadata or {}
        sources.append(
            {
                "source": meta.get("source"),
                "resume_id": meta.get("resume_id"),
                "job_id": meta.get("job_id"),
                "company": meta.get("company"),
                "role": meta.get("role"),
                "chunk_index": meta.get("chunk_index"),
                "preview": (d.page_content or "")[:200],
                "content": d.page_content,
            }
        )

    return answer, sources


# ---------- FastAPI endpoints ----------


@app.get("/")
def root():
    return {
        "message": "MaRNoW Resume+JD RAG server is running",
        "endpoints": {
            "POST /ingest_pair": "Load resume+JD by ID from marnow.db and index into Chroma",
            "POST /query": "Ask RAG-style questions over the last ingested pair",
            "POST /explain": "Explain a specific source chunk",
        },
        "models": {
            "embedding": EMBED_MODEL,
            "llm": LLM_MODEL,
        },
    }


@app.post("/ingest_pair", response_model=IngestPairResponse)
async def ingest_pair(req: IngestPairRequest):
    global current_pair

    try:
        resume, jd = load_resume_and_jd(req.resume_id, req.job_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    docs = build_documents_for_pair(resume, jd)
    if not docs:
        raise HTTPException(status_code=400, detail="No text found in resume or JD")

    build_vectorstore(docs)
    current_pair = (req.resume_id, req.job_id)

    return IngestPairResponse(
        status="success",
        message="Resume+JD pair ingested and indexed",
        resume_id=req.resume_id,
        job_id=req.job_id,
        num_documents=len(docs),
    )


@app.post("/ingest_upload", response_model=IngestUploadResponse)
async def ingest_upload(
    resume_file: UploadFile = File(...),
    jd_text: str = Form(...),
    company: str = Form(""),
    role: str = Form(""),
    source_url: str = Form(""),
):
    """Ingest resume PDF upload + pasted JD text.

    Creates (or dedupes) rows in `resumes` and `job_posts`, then builds the vectorstore
    for this pair.
    """

    if not resume_file.filename or not resume_file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="resume_file must be a .pdf")

    data = await resume_file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty resume_file")

    try:
        resume_text = _extract_pdf_text(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {e}")

    if not (jd_text or "").strip():
        raise HTTPException(status_code=400, detail="jd_text is required")

    # Upsert into SQLite
    rid, _ = upsert_resume(resume_file.filename, "pdf", resume_text)

    job_filename = "-".join(
        [p for p in [_slug(company), _slug(role)] if p and p != "doc"]
    ) or "pasted-jd"
    job_filename += ".txt"

    jid, _ = upsert_job(
        job_filename,
        (company or "").strip() or None,
        (role or "").strip() or None,
        jd_text,
        (source_url or "").strip() or None,
    )

    # Build RAG index for the pair
    try:
        resume, jd = load_resume_and_jd(rid, jid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    docs = build_documents_for_pair(resume, jd)
    if not docs:
        raise HTTPException(status_code=400, detail="No text found in resume or JD")

    build_vectorstore(docs)
    global current_pair
    current_pair = (rid, jid)

    return IngestUploadResponse(
        status="success",
        message="Uploaded resume + pasted JD ingested and indexed",
        resume_id=rid,
        job_id=jid,
        num_documents=len(docs),
    )


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    if vectorstore is None:
        raise HTTPException(
            status_code=400,
            detail="No resume+JD pair indexed yet. Call /ingest_pair first.",
        )

    res = run_query(req.query, req.mode)
    if res is None:
        raise HTTPException(
            status_code=400,
            detail="Vectorstore is not initialized.",
        )

    answer, sources = res
    return QueryResponse(answer=answer, sources=sources)


@app.post("/explain", response_model=ExplainResponse)
async def explain(req: ExplainRequest):
    content = (req.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="No content provided for explanation.")

    prompt = (
        "Explain the following job/resume chunk in clear, concise terms. "
        "Do not guess missing information or fabricate details.\n\n"
        f"Content:\n{content}\n\nExplanation:"
    )

    llm = Ollama(model=LLM_MODEL)
    explanation = llm.invoke(prompt)

    return ExplainResponse(explanation=explanation)


@app.post("/score", response_model=ScoreResponse)
async def score(req: ScoreRequest):
    try:
        return compute_score(req.resume_id, req.job_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/apply_copilot_rewrite", response_model=ApplyRewriteResponse)
async def apply_copilot_rewrite(req: ApplyRewriteRequest):
    """Run copilot rewrite, save a new resume (plain text), optionally reindex, and return score delta."""

    # Ensure we have the pair
    try:
        resume_row, jd_row = load_resume_and_jd(req.resume_id, req.job_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Force using the RAG chunks if available; fallback to full text if not ingested.
    use_rag = bool(all_docs)
    small_model = req.small_model or SMALL_MODEL_DEFAULT
    large_model = req.large_model or LARGE_MODEL_DEFAULT

    if use_rag:
        jd_chunks = [d.page_content for d in all_docs if (d.metadata or {}).get("source") == "jd"]
        resume_chunks = [d.page_content for d in all_docs if (d.metadata or {}).get("source") == "resume"]
        jd_text = "\n\n".join(jd_chunks)
        resume_text = "\n\n".join(resume_chunks)
    else:
        jd_text = jd_row.get("text", "") or ""
        resume_text = resume_row.get("text", "") or ""

    jd_title = f"{jd_row.get('company') or ''} / {jd_row.get('role') or ''}".strip(" /")

    # Section extraction is best-effort: some models respond with non-JSON or structured objects.
    # Do not fail the whole pipeline if this step is messy.
    try:
        resume_sections = extract_resume_sections(resume_text, small_model)
    except Exception:
        resume_sections = {"skills": "", "experience": "", "projects": ""}

    try:
        analysis = analyze_alignment_small_model(resume_text, jd_text, small_model)
        rewrites_md = generate_rewrites_large_model(
            resume_text=resume_text,
            jd_title=jd_title,
            jd_text=jd_text,
            analysis=analysis,
            large_model=large_model,
            resume_sections=resume_sections,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Copilot rewrite failed: {e}")

    skills_after, experience_after = _split_rewrites(rewrites_md)

    revised_text = _build_revised_resume_text(
        skills_after=skills_after,
        experience_after=experience_after,
        projects_before=resume_sections.get("projects", "") or "",
        original_resume_text=resume_text,
    )

    # Store as a new resume row
    base = (resume_row.get("filename") or "resume").rsplit(".", 1)[0]
    new_filename = f"{base}_rewritten.txt"
    notes = json.dumps(
        {
            "parent_resume_id": req.resume_id,
            "job_id": req.job_id,
            "created_at": datetime.datetime.utcnow().isoformat(),
            "source": "apply_copilot_rewrite",
        }
    )
    new_rid, _ = upsert_resume(new_filename, "txt", revised_text, notes=notes)

    # Compute score before/after
    try:
        score_before = compute_score(req.resume_id, req.job_id)
        score_after = compute_score(new_rid, req.job_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scoring failed: {e}")

    # Optionally reindex to the new resume
    if req.reindex:
        try:
            resume2, jd2 = load_resume_and_jd(new_rid, req.job_id)
            docs = build_documents_for_pair(resume2, jd2)
            build_vectorstore(docs)
            global current_pair
            current_pair = (new_rid, req.job_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Reindex failed: {e}")

    delta_total = round(float(score_after.total) - float(score_before.total), 2)

    return ApplyRewriteResponse(
        status="success",
        message="Rewrite applied and saved as a new resume",
        original_resume_id=req.resume_id,
        new_resume_id=new_rid,
        job_id=req.job_id,
        skills_after=skills_after,
        experience_after=experience_after,
        score_before=score_before,
        score_after=score_after,
        delta_total=delta_total,
    )


def _retrieve_sources(query: str, mode: str) -> List[Document]:
    if vectorstore is None:
        raise RuntimeError("No resume+JD pair indexed yet. Call /ingest_pair or /ingest_upload first.")

    search_kwargs: dict = {"k": 12}
    if mode == "resume":
        search_kwargs["filter"] = {"source": "resume"}
    elif mode == "jd":
        search_kwargs["filter"] = {"source": "jd"}

    retriever = vectorstore.as_retriever(search_kwargs=search_kwargs)
    docs: List[Document] = retriever.invoke(query)

    # Deduplicate near-identical docs
    unique_docs: List[Document] = []
    seen = set()
    for d in docs:
        meta = d.metadata or {}
        key = (
            meta.get("source"),
            meta.get("resume_id"),
            meta.get("job_id"),
            meta.get("chunk_index"),
            (d.page_content or "")[:80],
        )
        if key not in seen:
            seen.add(key)
            unique_docs.append(d)
    return unique_docs


def _docs_to_sources(docs: List[Document]) -> List[dict]:
    sources: List[dict] = []
    for d in docs:
        meta = d.metadata or {}
        sources.append(
            {
                "source": meta.get("source"),
                "resume_id": meta.get("resume_id"),
                "job_id": meta.get("job_id"),
                "company": meta.get("company"),
                "role": meta.get("role"),
                "chunk_index": meta.get("chunk_index"),
                "preview": (d.page_content or "")[:200],
                "content": d.page_content,
            }
        )
    return sources


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Chat-style endpoint that uses RAG chunks and routes common intents.

    This is intentionally heuristic: it aims to cover your proposal prompts partially
    even when an exact dedicated handler is not implemented.
    """

    msg = (req.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message is required")

    # Ensure DB rows exist
    try:
        resume_row, jd_row = load_resume_and_jd(req.resume_id, req.job_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Retrieve sources for transparency
    try:
        docs = _retrieve_sources(msg, req.mode)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    sources = _docs_to_sources(docs)

    # Assemble context string for the LLM
    context_chunks = []
    for d in docs:
        label = (d.metadata or {}).get("source", "?")
        context_chunks.append(f"[{label.upper()} CHUNK]\n" + (d.page_content or ""))
    context = "\n\n---\n\n".join(context_chunks)[:6000]

    # Basic intent routing
    msg_l = msg.lower()
    small_model = req.small_model or SMALL_MODEL_DEFAULT
    large_model = req.large_model or LARGE_MODEL_DEFAULT

    # 1) Score/match
    if "score" in msg_l or ("match" in msg_l and "score" in msg_l):
        s = compute_score(req.resume_id, req.job_id)
        answer = (
            f"Heuristic MaRNoW score: total={s.total} "
            f"(skills={s.skills_score}, resp={s.resp_score}, seniority={s.seniority_score}, domain={s.domain_score}).\n"
        )
        if s.missing:
            answer += "Top missing skills: " + ", ".join(s.missing[:10])
        return ChatResponse(kind="score", answer=answer, payload={"score": s.model_dump()}, sources=sources)

    # Use aggregated RAG texts for copilot-style generators
    jd_chunks = [d.page_content for d in all_docs if (d.metadata or {}).get("source") == "jd"]
    resume_chunks = [d.page_content for d in all_docs if (d.metadata or {}).get("source") == "resume"]
    jd_text = "\n\n".join(jd_chunks) if jd_chunks else (jd_row.get("text", "") or "")
    resume_text = "\n\n".join(resume_chunks) if resume_chunks else (resume_row.get("text", "") or "")
    jd_title = f"{jd_row.get('company') or ''} / {jd_row.get('role') or ''}".strip(" /")

    # 2) Skills gaps
    if ("skills" in msg_l and ("lack" in msg_l or "missing" in msg_l)) or "keywords" in msg_l:
        try:
            analysis = analyze_alignment_small_model(resume_text, jd_text, small_model)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Skill analysis failed: {e}")

        missing = analysis.get("missing_skills") or []
        present = analysis.get("resume_present_skills") or []
        jd_skills = analysis.get("jd_key_skills") or []
        notes = (analysis.get("notes") or "").strip()

        lines = []
        if missing:
            lines.append("Missing or weak match (from the JD):")
            for s in missing:
                lines.append(f"- {s}")
        else:
            lines.append("No obvious missing skills detected (based on the extracted JD skills).")

        if jd_skills:
            lines.append("")
            lines.append("JD key skills detected:")
            lines.append("- " + ", ".join(jd_skills))

        if present:
            lines.append("")
            lines.append("Skills clearly present in your resume:")
            lines.append("- " + ", ".join(present))

        if notes:
            lines.append("")
            lines.append("Summary:")
            lines.append(notes)

        answer = "\n".join(lines).strip()
        return ChatResponse(kind="analysis", answer=answer, payload={"analysis": analysis}, sources=sources)

    # 3) Cover letter
    if "cover letter" in msg_l:
        try:
            try:
                resume_sections = extract_resume_sections(resume_text, small_model)
            except Exception:
                resume_sections = {"skills": "", "experience": "", "projects": ""}
            analysis = analyze_alignment_small_model(resume_text, jd_text, small_model)
            letter = generate_cover_letter_large_model(
                jd_title=jd_title,
                jd_text=jd_text,
                analysis=analysis,
                resume_sections=resume_sections,
                large_model=large_model,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Cover letter generation failed: {e}")
        return ChatResponse(kind="cover-letter", answer=letter, payload={"cover_letter": letter}, sources=sources)

    # 4) Rewrite
    if "rewrite" in msg_l or "bullets" in msg_l or "projects" in msg_l:
        try:
            try:
                resume_sections = extract_resume_sections(resume_text, small_model)
            except Exception:
                resume_sections = {"skills": "", "experience": "", "projects": ""}
            analysis = analyze_alignment_small_model(resume_text, jd_text, small_model)
            rewrites_md = generate_rewrites_large_model(
                resume_text=resume_text,
                jd_title=jd_title,
                jd_text=jd_text,
                analysis=analysis,
                large_model=large_model,
                resume_sections=resume_sections,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Rewrite generation failed: {e}")
        return ChatResponse(kind="rewrite", answer=rewrites_md, payload={"rewrites_md": rewrites_md}, sources=sources)

    # 5) Default: grounded RAG QA
    prompt = (
        "You are a resume & JD analysis assistant. "
        "Use ONLY the provided context, which contains chunks from a job description (JD) "
        "and a candidate's resume. If the answer is not supported by the context, say you don't know.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {msg}\n\n"
        "Answer:"
    )

    llm = Ollama(model=LLM_MODEL)
    answer = llm.invoke(prompt)
    return ChatResponse(kind="rag", answer=str(answer), payload={}, sources=sources)


@app.get("/export/resume/{resume_id}")
async def export_resume(resume_id: int, format: Literal["tex", "pdf"] = "pdf"):
    """Download a resume draft as .tex or .pdf.

    PDF export requires pdflatex to be installed.
    """

    con = _connect_marnow()
    try:
        row = con.execute("SELECT filename, text FROM resumes WHERE id=?", (resume_id,)).fetchone()
    finally:
        con.close()

    if not row:
        raise HTTPException(status_code=404, detail="resume_id not found")

    filename, text = row
    title = (filename or f"resume_{resume_id}").rsplit(".", 1)[0]
    tex = render_resume_tex(text or "", title=title)

    if format == "tex":
        out_name = f"{title}.tex"
        return Response(
            content=tex,
            media_type="application/x-tex",
            headers={"Content-Disposition": f"attachment; filename={out_name}"},
        )

    if not pdflatex_available():
        raise HTTPException(
            status_code=400,
            detail="pdflatex is not installed. Install TeX Live (or provide .tex export).",
        )

    try:
        with tempfile.TemporaryDirectory(prefix="marnow_export_") as td:
            pdf_path = build_pdf_from_tex(tex, Path(td), jobname="resume")
            pdf_bytes = pdf_path.read_bytes()
    except Exception as e:
        # Treat LaTeX compilation errors as a client error (template/data issue).
        raise HTTPException(status_code=400, detail=str(e))

    out_name = f"{title}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={out_name}"},
    )


@app.post("/copilot", response_model=CopilotResponse)
async def copilot(req: CopilotRequest):
    """Run the MaRNoW AI copilot pipeline for a given (resume_id, job_id).

    This reuses the same small+large model helpers as tools/ai_copilot.py but
    returns structured JSON suitable for visual rendering in the Streamlit UI.
    """

    # Decide which models to use
    small_model = req.small_model or SMALL_MODEL_DEFAULT
    large_model = req.large_model or LARGE_MODEL_DEFAULT

    # Get resume & JD metadata (for company/role title)
    try:
        resume_row, jd_row = load_resume_and_jd(req.resume_id, req.job_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    jd_title = f"{jd_row.get('company') or ''} / {jd_row.get('role') or ''}".strip(" /")

    # Choose context: full text vs aggregated RAG chunks
    if req.context == "rag":
        if not all_docs:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No RAG documents loaded. Call /ingest_pair first or use "
                    "context='full'."
                ),
            )
        jd_chunks = [d.page_content for d in all_docs if (d.metadata or {}).get("source") == "jd"]
        resume_chunks = [d.page_content for d in all_docs if (d.metadata or {}).get("source") == "resume"]
        jd_text = "\n\n".join(jd_chunks)
        resume_text = "\n\n".join(resume_chunks)
    else:
        jd_text = jd_row.get("text", "") or ""
        resume_text = resume_row.get("text", "") or ""

    # 1) Extract sections from resume using small model (best-effort)
    try:
        resume_sections = extract_resume_sections(resume_text, small_model)
    except Exception:
        resume_sections = {"skills": "", "experience": "", "projects": ""}

    # 2) Analyze skills & gaps (JSON)
    try:
        analysis = analyze_alignment_small_model(resume_text, jd_text, small_model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Skill alignment failed: {e}")

    # Prepare base response
    resp = CopilotResponse(analysis=analysis, resume_sections=resume_sections)

    # Early exit for analysis-only mode
    if req.mode == "analysis":
        return resp

    # 3) Rewrites (skills + experience) if requested
    rewrites_md = None
    if req.mode in {"rewrite", "full"}:
        try:
            rewrites_md = generate_rewrites_large_model(
                resume_text=resume_text,
                jd_title=jd_title,
                jd_text=jd_text,
                analysis=analysis,
                large_model=large_model,
                resume_sections=resume_sections,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Rewrite generation failed: {e}")

        # Split rewrites into skills vs experience blocks
        skills_after = ""
        experience_after = ""
        marker_skills = "### SKILLS (suggested rewrite)"
        marker_exp = "### EXPERIENCE (suggested rewrite)"
        if marker_skills in rewrites_md:
            _, rest = rewrites_md.split(marker_skills, 1)
            if marker_exp in rest:
                skills_after, exp_rest = rest.split(marker_exp, 1)
                skills_after = skills_after.strip()
                experience_after = (marker_exp + "\n" + exp_rest.strip()).strip()
            else:
                skills_after = rest.strip()
        else:
            skills_after = rewrites_md.strip()

        resp.skills_before = resume_sections.get("skills") or ""
        resp.skills_after = skills_after or ""
        resp.experience_before = resume_sections.get("experience") or ""
        resp.experience_after = experience_after or ""
        resp.rewrites_md_raw = rewrites_md

        # Coverage report
        try:
            coverage_md = generate_integration_report(
                jd_title=jd_title,
                analysis=analysis,
                resume_sections=resume_sections,
                rewrites_md=rewrites_md,
                model=large_model,
            )
            resp.coverage_report_md = coverage_md
        except Exception:
            # Non-fatal: keep resp without coverage
            resp.coverage_report_md = None

    # 4) Cover letter if requested
    if req.mode in {"cover-letter", "full"}:
        try:
            cover_letter = generate_cover_letter_large_model(
                jd_title=jd_title,
                jd_text=jd_text,
                analysis=analysis,
                resume_sections=resume_sections,
                large_model=large_model,
            )
            resp.cover_letter = cover_letter
        except Exception:
            resp.cover_letter = None

    return resp
