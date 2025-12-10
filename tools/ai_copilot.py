#!/usr/bin/env python3
"""AI-powered Resume & JD Copilot (MaRNoW-style).

This script:
  - Parses a resume file (PDF/DOCX/TXT).
  - Loads a job description (JD) from a text file or from the marnow DB by job_id.
  - Uses local open-source LLMs (via Ollama) to:
      * Extract / compare skills & keywords between resume and JD.
      * Propose section-wise tweaks for the resume (Skills + Experience/Projects).

Models (as suggested in the project proposal):
  - Small model: Mistral-7B (e.g. "mistral:instruct" in Ollama).
  - Large model: LLaMA 2-13B (e.g. "llama2:13b" in Ollama).

Usage examples (from project root):

  python tools/ai_copilot.py \
      --resume-file /path/to/resume.pdf \
      --jd-file app/data/jds/apple-ml-resident.txt

  # Or use an existing job_posts row by id
  python tools/ai_copilot.py \
      --resume-file /path/to/resume.pdf \
      --job-id 1

The script prints:
  - A JSON summary of skill alignment.
  - A human-readable section with suggested SKILLS and EXPERIENCE rewrites.

This script does NOT modify your resume or database; it only reads and prints suggestions.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

import requests

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    PdfReader = None  # type: ignore

try:
    import docx  # python-docx
except ImportError:  # pragma: no cover
    docx = None  # type: ignore

try:
    import sqlite3
except ImportError:  # pragma: no cover
    sqlite3 = None  # type: ignore


# -------- Ollama client helpers --------

SMALL_MODEL_DEFAULT = os.environ.get("MARNOW_SMALL_MODEL", "mistral:instruct")
LARGE_MODEL_DEFAULT = os.environ.get("MARNOW_LARGE_MODEL", "llama2:13b")


def _ollama_base_url() -> str:
    """Resolve Ollama base URL from OLLAMA_HOST or default.

    entrypoint.sh typically sets OLLAMA_HOST="0.0.0.0:11434"; we normalize that
    into a full http URL.
    """

    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    if not host.startswith("http://") and not host.startswith("https://"):
        host = "http://" + host
    return host.rstrip("/")


def ollama_chat(model: str, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
    """Call Ollama /api/chat with the given model and prompts.

    Returns the assistant's message content as a string.
    Raises RuntimeError on non-200 responses.
    """

    url = _ollama_base_url() + "/api/chat"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": temperature},
    }
    try:
        resp = requests.post(url, json=payload, timeout=300)
    except Exception as e:  # pragma: no cover - network failure path
        raise RuntimeError(f"Failed to call Ollama at {url}: {e}") from e

    if resp.status_code != 200:
        raise RuntimeError(f"Ollama error {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    # Newer Ollama chat API returns {message: {role, content}, ...}
    msg = data.get("message") or {}
    content = msg.get("content") or ""
    return content.strip()


# -------- Resume & JD loading --------


def load_file_text(path: Path) -> str:
    """Load text from .txt, .pdf or .docx.

    - .txt: UTF-8 text.
    - .pdf: combine pages via pypdf.
    - .docx: combine paragraphs via python-docx.
    """

    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".pdf":
        if PdfReader is None:
            raise RuntimeError("pypdf is not installed; cannot parse PDF.")
        reader = PdfReader(str(path))
        pages = [pg.extract_text() or "" for pg in reader.pages]
        return "\n".join(pages)

    if suffix in {".docx"}:
        if docx is None:
            raise RuntimeError("python-docx is not installed; cannot parse DOCX.")
        doc = docx.Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)

    raise RuntimeError(f"Unsupported file type for {path}")


def load_jd_from_db(job_id: int, db_path: Optional[str] = None) -> Tuple[str, str]:
    """Load (company, JD text) for a given job_id from marnow.db.

    db_path defaults to the same logic as marnow.db: MARNOW_DB or ./marnow.db.
    Returns (title_string, jd_text), where title_string combines company + role.
    """

    if sqlite3 is None:
        raise RuntimeError("sqlite3 not available in this environment.")

    db_path = db_path or os.environ.get("MARNOW_DB", "marnow.db")
    con = sqlite3.connect(db_path)
    try:
        row = con.execute(
            "SELECT company, role, text FROM job_posts WHERE id = ?",
            (job_id,),
        ).fetchone()
        if not row:
            raise RuntimeError(f"job_id {job_id} not found in job_posts.")
        company, role, text = row
        title = f"{company or ''} / {role or ''}".strip(" /")
        return title, text or ""
    finally:
        con.close()


def load_resume_from_db(resume_id: int, db_path: Optional[str] = None) -> Tuple[str, str]:
    """Load (filename, resume text) for a given resume_id from marnow.db.

    db_path defaults to MARNOW_DB or ./marnow.db.
    Returns (filename, text).
    """

    if sqlite3 is None:
        raise RuntimeError("sqlite3 not available in this environment.")

    db_path = db_path or os.environ.get("MARNOW_DB", "marnow.db")
    con = sqlite3.connect(db_path)
    try:
        row = con.execute(
            "SELECT filename, text FROM resumes WHERE id = ?",
            (resume_id,),
        ).fetchone()
        if not row:
            raise RuntimeError(f"resume_id {resume_id} not found in resumes.")
        filename, text = row
        return filename or f"resume_{resume_id}", text or ""
    finally:
        con.close()


# -------- LLM prompts --------


def extract_resume_sections(resume_text: str, model: str) -> dict:
    """Use an LLM to extract key sections from the resume text.

    We assume the resume may contain headings like "SKILLS", "TECHNICAL SKILLS",
    "EXPERIENCE", "WORK EXPERIENCE", "PROJECTS".

    The model is instructed to output STRICT JSON with keys:
      - skills: string (raw text of skills/technical skills section)
      - experience: string (raw text of experience/work experience section)
      - projects: string (raw text of projects section)
    """

    system = (
        "You are a resume parser. "
        "Given the full plaintext of a resume, you must extract three sections: "
        "Skills, Experience, and Projects. "
        "Respond ONLY with valid JSON that can be parsed by Python's json.loads."
    )

    user = f"""
Resume plaintext:
<<<RESUME>>>
{resume_text}
<<<END RESUME>>>

Instructions:
1. Look for headings such as SKILLS, TECHNICAL SKILLS, EXPERIENCE, WORK EXPERIENCE, PROJECTS.
2. For each of these, capture the section body (all bullets/lines) until the next heading.
3. Return a JSON object with keys:
   - "skills": string (empty string if not found)
   - "experience": string (empty string if not found)
   - "projects": string (empty string if not found)
"""

    raw = ollama_chat(model, system, user, temperature=0.0)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to salvage JSON if the model wrapped it in prose
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                raise RuntimeError("Section-extraction response was not valid JSON:\n" + raw)
        else:
            raise RuntimeError("Section-extraction response was not valid JSON:\n" + raw)
    # Normalize keys to always exist
    return {
        "skills": data.get("skills", "") or "",
        "experience": data.get("experience", "") or "",
        "projects": data.get("projects", "") or "",
    }


def analyze_alignment_small_model(resume_text: str, jd_text: str, small_model: str) -> dict:
    """Use the small model (Mistral-7B) to extract skills/gaps as JSON.

    The model is instructed to output STRICT JSON with keys:
      - jd_key_skills: list[str]
      - resume_present_skills: list[str]
      - missing_skills: list[str]
      - notes: str
    """

    system = (
        "You are an ATS-style resume analyzer. "
        "Given a job description and a resume, you extract structured skills and highlight gaps. "
        "Respond ONLY with valid JSON that can be parsed by Python's json.loads."
    )

    user = f"""
Job Description (JD):
<<<JD>>>
{jd_text}
<<<END JD>>>

Resume:
<<<RESUME>>>
{resume_text}
<<<END RESUME>>>

Instructions:
1. Extract a concise list of key hard and soft skills explicitly or implicitly required by the JD.
2. Determine which of those skills are clearly present in the resume.
3. List the JD skills that are missing or only weakly implied.
4. Return a JSON object with keys:
   - "jd_key_skills": list of strings
   - "resume_present_skills": list of strings
   - "missing_skills": list of strings
   - "notes": short one-paragraph textual summary
"""

    raw = ollama_chat(small_model, system, user, temperature=0.1)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Try to salvage JSON if the model wrapped it in prose
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                raise RuntimeError("Small-model response was not valid JSON:\n" + raw)
        else:
            raise RuntimeError("Small-model response was not valid JSON:\n" + raw)
    return data


def generate_rewrites_large_model(
    resume_text: str,
    jd_title: str,
    jd_text: str,
    analysis: dict,
    large_model: str,
    resume_sections: Optional[dict] = None,
) -> str:
    """Use a model to propose section-wise rewrites that preserve bullet structure.

    The output is human-readable markdown with two sections:
      - SKILLS (suggested rewrite)
      - EXPERIENCE (suggested rewrite)

    Requirements encoded in the prompt:
      - Skills section should be a flat list of 1–2 word tokens (e.g., "Python", "Robotics").
      - Experience/Projects bullets should NOT be merged; keep roughly one
        rewritten bullet per original bullet.
      - New skill tokens should only be integrated into bullets where they
        are consistent with the original content (no fabrication).
    """

    jd_skills = analysis.get("jd_key_skills", [])
    missing = analysis.get("missing_skills", [])
    present = analysis.get("resume_present_skills", [])

    sections = resume_sections or {}
    skills_before = sections.get("skills", "") or ""
    exp_before = sections.get("experience", "") or ""
    projects_before = sections.get("projects", "") or ""

    system = (
        "You are a precise resume rewriting assistant for software/ML/robotics roles. "
        "You ONLY rewrite Skills and Experience/Projects, and you must preserve the "
        "granularity of the candidate's bullets (no merging separate bullets into one). "
        "You must stay truthful to the resume: do not invent technologies, companies, "
        "or responsibilities that are not supported by the original text. "
        "Prefer concrete, impact-focused bullets (metrics, scale, improvements)."
    )

    user = f"""
Job Title & Company (from JD): {jd_title}

Job Description (JD):
<<<JD>>>
{jd_text}
<<<END JD>>>

Structured skill analysis (from model):
{json.dumps(analysis, indent=2)}

[SKILLS BEFORE]
{skills_before}

[EXPERIENCE BEFORE]
{exp_before}

[PROJECTS BEFORE]
{projects_before}

Your tasks:
1. Normalize the JD key skills into short skill tokens (1–2 words each), for example:
   "Machine Learning", "Robotics", "Python", "C++", "LLMs", "Generative AI".
2. For the SKILLS section, produce a flat bullet list of such short tokens that:
   - Are directly supported by the original resume, OR
   - Are extremely safe, high-level synonyms of what is already in the resume.
   Do NOT include long phrases like "Proficiency in a programming language".
3. For the EXPERIENCE section, rewrite the bullets from [EXPERIENCE BEFORE] (and
   relevant bullets from [PROJECTS BEFORE]) so that:
   - You keep roughly one rewritten bullet for each original bullet (no merging).
   - You gently integrate important JD skill tokens where they make sense and are
     supported by the content (e.g., if a project uses computer vision on robots,
     it is valid to mention "Robotics" and "Computer Vision").
   - You keep each bullet focused on one main idea.

Output format (strict):
- Write markdown with exactly these two top-level headings and nothing else at top level:

### SKILLS (suggested rewrite)
- token1
- token2
- token3
...

### EXPERIENCE (suggested rewrite)
- rewritten bullet corresponding to first relevant original bullet
- rewritten bullet corresponding to next relevant original bullet
...

Guidelines:
- Do NOT fabricate new tools, languages, companies or roles that do not appear
  or are not clearly implied in the original resume.
- You may add JD skill tokens only when they are believable given the original
  text (e.g., the work clearly uses ML/vision/robotics/LLMs).
- Do not merge multiple old bullets into one new bullet; preserve the number of
  bullets as much as is reasonable.
- Skills tokens must be 1–2 words each.
"""

    text = ollama_chat(large_model, system, user, temperature=0.3)
    return text.strip()


def generate_cover_letter_large_model(
    jd_title: str,
    jd_text: str,
    analysis: dict,
    resume_sections: dict,
    large_model: str,
) -> str:
    """Generate a one-page cover letter tailored to the JD.

    Uses the large model and is grounded in:
      - JD title + text
      - Extracted resume sections (skills, experience, projects)
      - Skill alignment JSON
    """

    system = (
        "You are an expert cover letter writer for software/ML/robotics roles. "
        "You write concise, recruiter-friendly cover letters that stay truthful "
        "to the candidate's resume while aligning to the job description."
    )

    user = f"""
Job Title & Company (from JD): {jd_title}

Job Description (JD):
<<<JD>>>
{jd_text}
<<<END JD>>>

Skill analysis:
{json.dumps(analysis, indent=2)}

[RESUME SKILLS]
{resume_sections.get("skills", "(none)")}

[RESUME EXPERIENCE]
{resume_sections.get("experience", "(none)")}

[RESUME PROJECTS]
{resume_sections.get("projects", "(none)")}

Write a one-page cover letter (3–6 short paragraphs) that:
- Clearly states interest in this specific role and company.
- Highlights the most relevant experiences and projects for this JD.
- Weaves in key JD skills (especially missing/weak ones) ONLY where honest.
- Uses concrete impact and metrics where available.
- Avoids generic fluff and repetition.
- Stays consistent with the resume; do NOT invent technologies, employers, or degrees.

Use plain text with standard cover-letter formatting (no markdown headings).
Include:
- A brief opening
- 1–3 body paragraphs connecting experience to JD
- A short closing paragraph.
"""

    text = ollama_chat(large_model, system, user, temperature=0.4)
    return text.strip()


def generate_integration_report(
    jd_title: str,
    analysis: dict,
    resume_sections: dict,
    rewrites_md: str,
    model: str,
) -> str:
    """Ask an LLM to explain how JD skills map to before/after resume text.

    This produces a human-readable markdown report that covers:
      - JD key skills
      - Which were missing in the original resume
      - How (if at all) they appear in the suggested rewrites.
    """

    system = (
        "You are a careful resume analyst. "
        "You compare job description skills with a candidate's resume BEFORE and AFTER rewrites."
    )

    user = f"""
Job Title & Company: {jd_title}

JD and resume analysis (JSON):
{json.dumps(analysis, indent=2)}

Original resume sections:
[SKILLS BEFORE]
{resume_sections.get("skills", "(none)")}

[EXPERIENCE BEFORE]
{resume_sections.get("experience", "(none)")}

[PROJECTS BEFORE]
{resume_sections.get("projects", "(none)")}

Suggested rewrites (markdown):
<<<REWRITES>>>
{rewrites_md}
<<<END REWRITES>>>

Instructions:
1. Briefly list the JD key skills.
2. For each JD key skill, indicate whether it was clearly present in the original resume.
3. Highlight any JD skills that were weak or missing before but are now better covered by the suggested bullets.
4. Where possible, quote or summarize specific AFTER bullets that integrate those JD skills.
5. Output clear markdown with these headings:

### JD SKILLS
- ...

### MISSING OR WEAK IN ORIGINAL RESUME
- skill: short note

### HOW SUGGESTED BULLETS INTEGRATE JD SKILLS
- skill: BEFORE vs AFTER explanation
"""

    text = ollama_chat(model, system, user, temperature=0.25)
    return text.strip()


# -------- CLI --------


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "MaRNoW AI Copilot: compare a resume to a JD using local open-source LLMs "
            "(Mistral-7B + LLaMA 2-13B via Ollama) and propose section-wise tweaks, "
            "coverage reports, and cover-letter drafts."
        )
    )

    # High-level mode controls how much is generated
    p.add_argument(
        "--mode",
        choices=["analysis", "rewrite", "cover-letter", "full"],
        default="rewrite",
        help=(
            "What to generate: 'analysis' = JSON only; 'rewrite' = skills/experience "
            "rewrites and coverage report; 'cover-letter' = cover letter only; "
            "'full' = rewrites + coverage + cover letter."
        ),
    )

    # Resume source: either a file path or an existing resumes.id in marnow.db
    resume_group = p.add_mutually_exclusive_group(required=True)
    resume_group.add_argument("--resume-file", help="Path to resume file (.pdf, .docx, .txt)")
    resume_group.add_argument("--resume-id", type=int, help="resumes.id to load from marnow.db")

    # JD source: either a JD file or an existing job_posts.id
    jd_group = p.add_mutually_exclusive_group(required=True)
    jd_group.add_argument("--jd-file", help="Path to JD text file (.txt/.md/.pdf/.docx)")
    jd_group.add_argument("--job-id", type=int, help="job_posts.id to load JD from marnow.db")

    p.add_argument(
        "--small-model",
        default=SMALL_MODEL_DEFAULT,
        help=f"Ollama model name for analysis (default: {SMALL_MODEL_DEFAULT})",
    )
    p.add_argument(
        "--large-model",
        default=LARGE_MODEL_DEFAULT,
        help=f"Ollama model name for rewrites (default: {LARGE_MODEL_DEFAULT})",
    )
    p.add_argument(
        "--db-path",
        default=None,
        help="Optional path to marnow.db (defaults to MARNOW_DB or ./marnow.db)",
    )
    p.add_argument(
        "--no-human",
        action="store_true",
        help="If set, only print JSON analysis (omit markdown rewrite output)",
    )

    return p.parse_args(argv)


def main(argv: Optional[list] = None) -> int:
    args = parse_args(argv)

    # Load resume text from file or DB
    if args.resume_file:
        resume_path = Path(args.resume_file).expanduser().resolve()
        if not resume_path.exists():
            print(f"[error] Resume file not found: {resume_path}", file=sys.stderr)
            return 1
        try:
            resume_text = load_file_text(resume_path)
            resume_label = resume_path.name
        except Exception as e:
            print(f"[error] Failed to load resume text: {e}", file=sys.stderr)
            return 1
    else:
        try:
            resume_label, resume_text = load_resume_from_db(args.resume_id, db_path=args.db_path)
        except Exception as e:
            print(f"[error] Failed to load resume from DB: {e}", file=sys.stderr)
            return 1

    # Load JD text from file or DB
    if args.jd_file:
        jd_path = Path(args.jd_file).expanduser().resolve()
        if not jd_path.exists():
            print(f"[error] JD file not found: {jd_path}", file=sys.stderr)
            return 1
        jd_title = jd_path.stem
        jd_text = load_file_text(jd_path)
    else:
        try:
            jd_title, jd_text = load_jd_from_db(args.job_id, db_path=args.db_path)
        except Exception as e:
            print(f"[error] Failed to load JD from DB: {e}", file=sys.stderr)
            return 1

    print(f"[info] Using resume: {resume_label}", file=sys.stderr)
    print(f"[info] Using JD: {jd_title}", file=sys.stderr)

    # Extract BEFORE sections from the resume using the small model
    print("[info] Extracting resume sections (skills/experience/projects) with model:", args.small_model, file=sys.stderr)
    try:
        resume_sections = extract_resume_sections(resume_text, args.small_model)
    except Exception as e:
        print(f"[warn] Failed to extract resume sections: {e}", file=sys.stderr)
        resume_sections = {"skills": "", "experience": "", "projects": ""}

    print("[info] Analyzing skills & gaps with small model:", args.small_model, file=sys.stderr)
    analysis = analyze_alignment_small_model(resume_text, jd_text, args.small_model)

    # Always print the JSON analysis to stdout first (machine-consumable)
    print("=== SKILL ALIGNMENT (JSON) ===")
    print(json.dumps(analysis, indent=2, ensure_ascii=False))

    # If analysis-only mode or JSON-only flag, stop here
    if args.no_human or args.mode == "analysis":
        return 0

    # -------- Rewrites (skills + experience) --------
    if args.mode in {"rewrite", "full"}:
        print("\n[info] Generating section-wise rewrites with large model:", args.large_model, file=sys.stderr)
        rewrites_md = generate_rewrites_large_model(
            resume_text=resume_text,
            jd_title=jd_title,
            jd_text=jd_text,
            analysis=analysis,
            large_model=args.large_model,
            resume_sections=resume_sections,
        )

        # Best-effort split of the rewrites into skills and experience parts
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
            # Fallback: treat entire output as a generic AFTER block
            skills_after = rewrites_md.strip()

        print("\n=== COMPARISON: SKILLS SECTION ===")
        print("[BEFORE]\n" + (resume_sections.get("skills") or "(no explicit skills section detected)"))
        print("\n[AFTER]\n" + (skills_after or "(no skills rewrite produced)"))

        print("\n=== COMPARISON: EXPERIENCE SECTION ===")
        print("[BEFORE]\n" + (resume_sections.get("experience") or "(no explicit experience section detected)"))
        print("\n[AFTER]\n" + (experience_after or "(no experience rewrite produced)"))

        print("\n=== ORIGINAL PROJECTS SECTION (BEFORE) ===")
        print(resume_sections.get("projects") or "(no explicit projects section detected)")

        print("\n=== SECTION-WISE SUGGESTED REWRITES (RAW) ===")
        print(rewrites_md)

        # Generate a coverage/explanation report for how JD skills map into the rewrites
        print("\n[info] Generating JD-skill coverage report with model:", args.large_model, file=sys.stderr)
        try:
            coverage_md = generate_integration_report(
                jd_title=jd_title,
                analysis=analysis,
                resume_sections=resume_sections,
                rewrites_md=rewrites_md,
                model=args.large_model,
            )
            print("\n=== JD SKILLS COVERAGE REPORT ===")
            print(coverage_md)
        except Exception as e:
            print(f"[warn] Failed to generate JD-skill coverage report: {e}", file=sys.stderr)

    # -------- Cover letter generation --------
    if args.mode in {"cover-letter", "full"}:
        print("\n[info] Generating tailored cover letter with large model:", args.large_model, file=sys.stderr)
        try:
            cover_letter = generate_cover_letter_large_model(
                jd_title=jd_title,
                jd_text=jd_text,
                analysis=analysis,
                resume_sections=resume_sections,
                large_model=args.large_model,
            )
            print("\n=== COVER LETTER DRAFT ===")
            print(cover_letter)
        except Exception as e:
            print(f"[warn] Failed to generate cover letter: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
