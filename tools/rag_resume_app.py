#!/usr/bin/env python3
"""Streamlit UI for MaRNoW Resume+JD RAG server.

This UI is analogous to rag_app/streamlit_app.py, but it talks to
`tools.rag_resume_server` instead of the financial PDF server.

Features:
- Input a resume_id and job_id (from marnow.db).
- Ingest that pair into the RAG backend via /ingest_pair.
- Ask questions about the pair using /query with retrieval modes:
    - all (JD + resume)
    - jd-only
    - resume-only
- Inspect retrieved source chunks and optionally request an explanation
  for a specific chunk via /explain.

Run (from project root, after starting rag_resume_server):

  uv run streamlit run tools/rag_resume_app.py --server.port 8502
"""

import requests
import streamlit as st

API_BASE = "http://127.0.0.1:8100"

st.set_page_config(page_title="MaRNoW Resume+JD RAG", layout="centered")

st.title("📄 MaRNoW: Resume + JD RAG Copilot")
st.write("Backend: FastAPI + Chroma + Ollama (resume + JD from marnow.db)")


# Persist last QA result across reruns
if "qa_result" not in st.session_state:
    st.session_state["qa_result"] = None


st.sidebar.header("1. Ingest Resume + JD from marnow.db")
resume_id = st.sidebar.number_input("Resume ID (resumes.id)", min_value=1, step=1, value=1)
job_id = st.sidebar.number_input("Job ID (job_posts.id)", min_value=1, step=1, value=1)

if st.sidebar.button("Ingest this pair"):
    with st.spinner("Loading resume+JD and indexing into vector store..."):
        try:
            resp = requests.post(
                f"{API_BASE}/ingest_pair",
                json={"resume_id": int(resume_id), "job_id": int(job_id)},
                timeout=120,
            )
        except Exception as e:
            st.sidebar.error(f"Request failed: {e}")
            resp = None
    if resp is not None:
        if resp.ok:
            data = resp.json()
            st.sidebar.success(
                f"Ingested pair (resume_id={data['resume_id']}, job_id={data['job_id']}). "
                f"Indexed {data['num_documents']} chunks."
            )
        else:
            st.sidebar.error(f"Ingest failed: {resp.text}")


st.header("2. Ask Questions (RAG over Resume + JD)")

query = st.text_input(
    "Enter your question (e.g., 'List JD skills I lack', 'Rewrite my bullets for robotics'):"
)
mode_label = st.selectbox(
    "Restrict retrieval to:",
    ["All (JD + resume)", "JD only", "Resume only"],
    index=0,
)

mode_map = {
    "All (JD + resume)": "all",
    "JD only": "jd",
    "Resume only": "resume",
}
mode = mode_map[mode_label]


if st.button("Ask"):
    if not query.strip():
        st.warning("Please enter a question.")
    else:
        with st.spinner("Querying RAG backend..."):
            payload = {"query": query, "mode": mode}
            try:
                resp = requests.post(f"{API_BASE}/query", json=payload, timeout=180)
            except Exception as e:
                st.error(f"Request failed: {e}")
                resp = None

        if resp is not None:
            if resp.ok:
                st.session_state["qa_result"] = resp.json()
            else:
                st.error(f"Query failed: {resp.text}")
                st.session_state["qa_result"] = None


result = st.session_state.get("qa_result")
if result:
    st.subheader("Answer")
    st.write(result["answer"])

    st.subheader("Sources (retrieved context)")
    seen_keys = set()
    for i, src in enumerate(result["sources"]):
        source_type = src.get("source") or "?"
        resume_id_src = src.get("resume_id")
        job_id_src = src.get("job_id")
        company = src.get("company") or ""
        role = src.get("role") or ""
        content = src.get("content") or src.get("preview") or ""

        key = (source_type, resume_id_src, job_id_src, content[:50])
        if key in seen_keys:
            continue
        seen_keys.add(key)

        label = f"Source {i+1} – {source_type.upper()}"
        if source_type == "jd" and company or role:
            label += f" ({company} / {role})"
        elif source_type == "resume" and resume_id_src:
            label += f" (resume_id={resume_id_src})"

        with st.expander(label):
            if company or role:
                st.write(f"**JD company/role:** {company} / {role}")
            if resume_id_src:
                st.write(f"**Resume ID:** {resume_id_src}")

            st.write("---")
            st.write(content)

            if st.button(f"Explain Source {i+1}", key=f"explain_{i}"):
                with st.spinner("Generating explanation..."):
                    try:
                        exp_resp = requests.post(
                            f"{API_BASE}/explain",
                            json={"content": content},
                            timeout=180,
                        )
                        if exp_resp.ok:
                            exp = exp_resp.json().get("explanation", "")
                            st.markdown("### Explanation")
                            st.write(exp)
                        else:
                            st.error(f"Explain failed: {exp_resp.text}")
                    except Exception as e:
                        st.error(f"Request failed: {e}")


st.info(
    "Tip: try prompts like 'List JD skills and show which ones I lack', "
    "'Rewrite my projects bullets to emphasize robotics and ML', or "
    "'Suggest 3 bullets that better highlight LLM experience while staying truthful.'"
)
