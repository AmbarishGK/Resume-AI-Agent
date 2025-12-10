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
from typing import List, Optional, Tuple, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_community.llms import Ollama

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


class ExplainRequest(BaseModel):
    content: str


class ExplainResponse(BaseModel):
    explanation: str


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
