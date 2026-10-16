"""Build the arXiv / SSRN submission bundle for docs/paper and prove that it compiles on its own.

    uv run python scripts/arxiv_bundle.py

arXiv compiles with pdflatex and does not run BibTeX, so the bundle ships the generated .bbl. The bundle is
compiled in an empty directory (pdflatex only, twice) before it is written, so a missing file fails here
rather than on arXiv. Output: docs/paper/dist/fintwin-arxiv.tar.gz and docs/paper/dist/fintwin.pdf.
"""

import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

PAPER = Path(__file__).resolve().parents[2] / "docs" / "paper"
DIST = PAPER / "dist"


def run(cmd: list[str], cwd: Path) -> None:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, errors="replace")
    if r.returncode != 0:
        raise SystemExit(f"{' '.join(cmd)} failed in {cwd}:\n{r.stdout[-3000:]}")


def write_abstracts(tex: str) -> None:
    """Abstract for the submission forms, with every macro expanded: abstract_arxiv.txt keeps TeX math (arXiv renders
    it; at most 1,920 characters), abstract.txt is plain Unicode for SSRN."""
    macros = {}
    for f in ("numbers.tex", "research_numbers.tex"):
        for name, val in re.findall(r"\\newcommand\{\\(\w+)\}\{(.*)\}", (PAPER / f).read_text(encoding="utf-8")):
            macros[name] = val
    macros["twin"] = "FinTwin"
    body = tex.split("\\begin{abstract}", 1)[1].split("\\medskip", 1)[0].replace("\\noindent", "")
    body = re.sub(r"\\(\w+)(\{\})?", lambda mt: macros.get(mt.group(1), mt.group(0)), body)
    body = " ".join(body.replace("{,}", ",").replace("$-$", "-").replace("\\%", "%").replace("\\&", "&").replace("~", " ").split())
    arxiv = body.replace("--", "-")
    plain = (body.replace("$\\rho$", "ρ").replace("$''$", "″").replace("--", "–").replace("$", ""))
    (PAPER / "abstract_arxiv.txt").write_text(arxiv + "\n", encoding="utf-8")
    (PAPER / "abstract.txt").write_text(plain + "\n", encoding="utf-8")
    if "\\" in plain:
        raise SystemExit(f"unexpanded LaTeX left in the abstract: {plain}")
    if len(arxiv) > 1920:
        raise SystemExit(f"abstract is {len(arxiv)} characters; arXiv allows 1,920")


def main() -> None:
    # fresh build with BibTeX in place, to produce an up-to-date .bbl
    run(["latexmk", "-pdf", "-interaction=nonstopmode", "-quiet", "fintwin.tex"], PAPER)
    tex = (PAPER / "fintwin.tex").read_text(encoding="utf-8")
    model = (PAPER / "sections" / "model.tex").read_text(encoding="utf-8")
    inputs = set(re.findall(r"\\input\{([^}]+)\}", tex + model))
    figures = set(re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", tex + model))
    files = {"fintwin.tex", "fintwin.bbl"}
    files |= {f if f.endswith(".tex") else f + ".tex" for f in inputs}
    files |= set(figures)
    missing = [f for f in files if not (PAPER / f).exists()]
    if missing:
        raise SystemExit(f"missing files: {missing}")

    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp) / "fintwin"
        for f in sorted(files):
            (stage / f).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(PAPER / f, stage / f)
        # 00README tells arXiv which file is the top-level document
        (stage / "00README.json").write_text(
            '{"spec_version": 1, "process": {"compiler": "pdflatex"}, '
            '"sources": [{"filename": "fintwin.tex", "usage": "toplevel"}]}\n',
            encoding="utf-8",
        )
        for _ in range(2):  # pdflatex only, exactly like arXiv
            run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "fintwin.tex"], stage)
        log = (stage / "fintwin.log").read_text(encoding="utf-8", errors="replace")
        bad = [ln for ln in log.splitlines() if "undefined" in ln and ("Reference" in ln or "Citation" in ln)]
        if bad:
            raise SystemExit("unresolved references in the standalone build:\n" + "\n".join(bad[:10]))
        DIST.mkdir(exist_ok=True)
        shutil.copy2(stage / "fintwin.pdf", DIST / "fintwin.pdf")
        with tarfile.open(DIST / "fintwin-arxiv.tar.gz", "w:gz") as tar:
            for f in sorted([*files, "00README.json"]):
                tar.add(stage / f, arcname=f)
    write_abstracts(tex)
    for f in ("aux", "log", "out", "fls", "fdb_latexmk", "blg"):
        (PAPER / f"fintwin.{f}").unlink(missing_ok=True)
    size = (DIST / "fintwin-arxiv.tar.gz").stat().st_size
    print(f"{len(files) + 1} files, {size / 1024:.0f} KB -> {DIST / 'fintwin-arxiv.tar.gz'}; standalone build OK")


if __name__ == "__main__":
    main()
