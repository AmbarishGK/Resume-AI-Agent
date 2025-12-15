from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _sanitize_verbatim(text: str) -> str:
    # Avoid breaking out of verbatim.
    return (text or "").replace("\\end{verbatim}", "\\end{verbat1m}")


def _latex_escape_text(s: str) -> str:
    # Minimal escaping for LaTeX text mode.
    # We only use this for short fields like titles (resume body is in verbatim).
    s = s or ""
    return (
        s.replace("\\", "\\textbackslash{}")
        .replace("&", "\\&")
        .replace("%", "\\%")
        .replace("$", "\\$")
        .replace("#", "\\#")
        .replace("_", "\\_")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("~", "\\textasciitilde{}")
        .replace("^", "\\textasciicircum{}")
    )


def render_resume_tex(resume_text: str, title: str | None = None) -> str:
    """Render a minimal LaTeX resume draft from plain text.

    Notes:
    - This intentionally does not attempt to reflow or reformat PDF extraction into a
      polished resume template.
    - It produces a compilable .tex and, if pdflatex exists, a PDF.
    """

    title = (title or "Resume Draft").strip() or "Resume Draft"
    title_tex = _latex_escape_text(title)
    body = _sanitize_verbatim(resume_text)

    return f"""\\documentclass[10pt]{{article}}
\\usepackage[margin=0.7in]{{geometry}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{lmodern}}
\\setlength{{\\parindent}}{{0pt}}
\\begin{{document}}
\\section*{{{title_tex}}}
\\begin{{verbatim}}
{body}
\\end{{verbatim}}
\\end{{document}}
"""


def render_cover_letter_tex(letter_text: str, title: str | None = None) -> str:
    title = (title or "Cover Letter").strip() or "Cover Letter"
    body = _sanitize_verbatim(letter_text)

    return f"""\\documentclass[11pt]{{article}}
\\usepackage[margin=1in]{{geometry}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{lmodern}}
\\setlength{{\\parindent}}{{0pt}}
\\begin{{document}}
\\section*{{{title}}}
\\begin{{verbatim}}
{body}
\\end{{verbatim}}
\\end{{document}}
"""


def pdflatex_available() -> bool:
    # Use PATH lookup.
    from shutil import which

    return which("pdflatex") is not None


def build_pdf_from_tex(tex: str, out_dir: Path, jobname: str = "resume") -> Path:
    """Write tex into out_dir and run pdflatex. Returns the output PDF path."""

    out_dir.mkdir(parents=True, exist_ok=True)
    tex_path = out_dir / f"{jobname}.tex"
    tex_path.write_text(tex, encoding="utf-8")

    cmd = [
        "pdflatex",
        "-interaction=nonstopmode",
        "-halt-on-error",
        f"-jobname={jobname}",
        tex_path.name,
    ]

    # Run twice for safety (refs), but keep it minimal.
    for _ in range(2):
        p = subprocess.run(
            cmd,
            cwd=str(out_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ},
        )
        if p.returncode != 0:
            tail = (p.stdout + "\n" + p.stderr)[-2000:]
            raise RuntimeError(f"pdflatex failed (code={p.returncode}):\n{tail}")

    pdf_path = out_dir / f"{jobname}.pdf"
    if not pdf_path.exists():
        raise RuntimeError("pdflatex did not produce a PDF")
    return pdf_path
