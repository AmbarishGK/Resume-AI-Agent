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

st.set_page_config(page_title="MaRNoW Resume+JD Copilot", layout="centered")

st.title("MaRNoW: Resume + JD Copilot")
st.write("Backend: FastAPI + Chroma + Ollama (upload resume PDF + paste JD text)")

main_tab, sources_tab = st.tabs(["Copilot Chat", "Sources / Debug"])


if "resume_id" not in st.session_state:
    st.session_state["resume_id"] = None
if "job_id" not in st.session_state:
    st.session_state["job_id"] = None
if "latest_resume_id" not in st.session_state:
    st.session_state["latest_resume_id"] = None
if "last_sources" not in st.session_state:
    st.session_state["last_sources"] = []

st.sidebar.header("1) Ingest")
resume_file = st.sidebar.file_uploader("Upload resume (.pdf)", type=["pdf"])
jd_text = st.sidebar.text_area("Paste job description (JD)", height=200)
company = st.sidebar.text_input("Company (optional)")
role = st.sidebar.text_input("Role (optional)")

if st.sidebar.button("Ingest resume + JD"):
    if resume_file is None:
        st.sidebar.error("Please upload a resume PDF")
    elif not (jd_text or "").strip():
        st.sidebar.error("Please paste the JD text")
    else:
        with st.spinner("Uploading + indexing into vector store..."):
            try:
                files = {
                    "resume_file": (resume_file.name, resume_file.getvalue(), "application/pdf")
                }
                data = {
                    "jd_text": jd_text,
                    "company": company,
                    "role": role,
                    "source_url": "",
                }
                resp = requests.post(
                    f"{API_BASE}/ingest_upload",
                    files=files,
                    data=data,
                    timeout=180,
                )
            except Exception as e:
                st.sidebar.error(f"Request failed: {e}")
                resp = None

        if resp is not None:
            if resp.ok:
                out = resp.json()
                st.session_state["resume_id"] = out["resume_id"]
                st.session_state["job_id"] = out["job_id"]
                st.session_state["latest_resume_id"] = out["resume_id"]
                st.sidebar.success(
                    f"Ingested (resume_id={out['resume_id']}, job_id={out['job_id']}) with {out['num_documents']} chunks."
                )
            else:
                st.sidebar.error(f"Ingest failed: {resp.text}")

st.sidebar.divider()
st.sidebar.header("2) Models")
small_model = st.sidebar.text_input("Small model (analysis)", value="mistral:instruct")
large_model = st.sidebar.text_input("Large model (rewrite/cover letter)", value="llama2:13b")

st.sidebar.divider()
st.sidebar.header("3) Actions")

ids_ready = st.session_state.get("resume_id") and st.session_state.get("job_id")

if st.sidebar.button("Check score"):
    if not ids_ready:
        st.sidebar.error("Ingest first")
    else:
        with st.spinner("Scoring..."):
            try:
                resp = requests.post(
                    f"{API_BASE}/score",
                    json={"resume_id": int(st.session_state["latest_resume_id"]), "job_id": int(st.session_state["job_id"])},
                    timeout=60,
                )
                if resp.ok:
                    st.session_state["last_score"] = resp.json()
                else:
                    st.sidebar.error(resp.text)
            except Exception as e:
                st.sidebar.error(f"Request failed: {e}")

if st.sidebar.button("Apply suggested changes"):
    if not ids_ready:
        st.sidebar.error("Ingest first")
    else:
        with st.spinner("Running copilot rewrite + rescoring..."):
            try:
                resp = requests.post(
                    f"{API_BASE}/apply_copilot_rewrite",
                    json={
                        "resume_id": int(st.session_state["latest_resume_id"]),
                        "job_id": int(st.session_state["job_id"]),
                        "small_model": small_model,
                        "large_model": large_model,
                        "reindex": True,
                    },
                    timeout=600,
                )
            except Exception as e:
                st.sidebar.error(f"Request failed: {e}")
                resp = None

        if resp is not None:
            if resp.ok:
                out = resp.json()
                st.session_state["latest_resume_id"] = out["new_resume_id"]
                st.session_state["last_apply"] = out
                st.sidebar.success(
                    f"Applied. New resume_id={out['new_resume_id']} (Δ total = {out['delta_total']})."
                )
            else:
                st.sidebar.error(f"Apply failed: {resp.text}")

st.sidebar.divider()
st.sidebar.header("4) Download")
if ids_ready:
    rid = int(st.session_state["latest_resume_id"])
    if st.sidebar.button("Fetch LaTeX (.tex)"):
        try:
            r = requests.get(f"{API_BASE}/export/resume/{rid}?format=tex", timeout=60)
            if r.ok:
                st.session_state["download_tex"] = r.text
            else:
                st.sidebar.error(r.text)
        except Exception as e:
            st.sidebar.error(f"Request failed: {e}")

    if st.sidebar.button("Fetch PDF (.pdf)"):
        try:
            r = requests.get(f"{API_BASE}/export/resume/{rid}?format=pdf", timeout=120)
            if r.ok:
                st.session_state["download_pdf"] = r.content
            else:
                st.sidebar.error(r.text)
        except Exception as e:
            st.sidebar.error(f"Request failed: {e}")

    if st.session_state.get("download_tex"):
        st.sidebar.download_button(
            "Download LaTeX",
            data=st.session_state["download_tex"],
            file_name=f"resume_{rid}.tex",
            mime="application/x-tex",
        )

    if st.session_state.get("download_pdf"):
        st.sidebar.download_button(
            "Download PDF",
            data=st.session_state["download_pdf"],
            file_name=f"resume_{rid}.pdf",
            mime="application/pdf",
        )


with main_tab:
    st.header("Chat")

    ids_ready = st.session_state.get("resume_id") and st.session_state.get("job_id")
    if not ids_ready:
        st.info("Upload a resume PDF and paste a JD in the sidebar, then click 'Ingest resume + JD'.")

    # Show score panel if we have it
    if st.session_state.get("last_score"):
        s = st.session_state["last_score"]
        st.subheader("Current score")
        st.json(s)

    if st.session_state.get("last_apply"):
        a = st.session_state["last_apply"]
        st.subheader("After applying changes")
        st.write(f"New resume_id: {a['new_resume_id']} | Δ total: {a['delta_total']}")
        st.json({"before": a["score_before"], "after": a["score_after"]})
        with st.expander("Skills rewrite (after)"):
            st.code(a.get("skills_after") or "")
        with st.expander("Experience rewrite (after)"):
            st.code(a.get("experience_after") or "")

    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    for m in st.session_state["messages"]:
        with st.chat_message(m["role"]):
            st.write(m["content"])

    user_msg = st.chat_input("Ask anything (your 20 prompts or custom).")
    if user_msg:
        st.session_state["messages"].append({"role": "user", "content": user_msg})
        with st.chat_message("user"):
            st.write(user_msg)

        if not ids_ready:
            with st.chat_message("assistant"):
                st.write("Ingest a resume+JD first.")
        else:
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        resp = requests.post(
                            f"{API_BASE}/chat",
                            json={
                                "resume_id": int(st.session_state["latest_resume_id"]),
                                "job_id": int(st.session_state["job_id"]),
                                "message": user_msg,
                                "mode": "all",
                                "small_model": small_model,
                                "large_model": large_model,
                            },
                            timeout=600,
                        )
                    except Exception as e:
                        st.error(f"Request failed: {e}")
                        resp = None

                    if resp is not None and resp.ok:
                        data = resp.json()
                        st.session_state["last_sources"] = data.get("sources") or []
                        answer = data.get("answer") or ""
                        st.write(answer)
                        st.session_state["messages"].append({"role": "assistant", "content": answer})
                    elif resp is not None:
                        st.error(resp.text)

with sources_tab:
    st.header("Retrieved sources")
    srcs = st.session_state.get("last_sources") or []
    if not srcs:
        st.info("No sources yet. Ask a question in Chat after ingesting.")
    else:
        for i, src in enumerate(srcs):
            label = f"Source {i+1}: {src.get('source')}"
            if src.get("company") or src.get("role"):
                label += f" ({src.get('company') or ''} / {src.get('role') or ''})"
            with st.expander(label):
                st.code(src.get("content") or src.get("preview") or "")
