# Submitting the paper: Zenodo, arXiv, SSRN

Everything here is free. Do the steps in this order, so that the arXiv and SSRN versions can cite the Zenodo DOI.

## 0. Build the submission files

```bash
cd engine
uv run python scripts/research_assets.py      # tables, figures and numbers from docs/paper/research.json
uv run python scripts/arxiv_bundle.py         # -> docs/paper/dist/fintwin-arxiv.tar.gz and fintwin.pdf
```

`arxiv_bundle.py` compiles the bundle in an empty folder with plain `pdflatex` (no BibTeX), as arXiv does.

## 1. Zenodo: a permanent DOI for the code and data

1. Sign in at <https://zenodo.org> with **Log in with GitHub**.
2. Open *Settings → GitHub* (<https://zenodo.org/account/settings/github/>), find `SpiliosDimakopoulos/fintwin` and switch it **On**.
3. Create a GitHub release (for example `v1.0.0`). Zenodo archives it automatically and mints two DOIs: one for the release and a *concept DOI* that always resolves to the latest version. Metadata come from `.zenodo.json` in the repository root.
4. Cite the concept DOI in the paper, the README badge and `CITATION.cff`, then publish a second release (`v1.0.1`) so that the archived paper contains its own DOI.

## 2. arXiv

- **Account:** <https://arxiv.org/user/register>. Use your full name exactly as on the paper.
- **Endorsement:** a first submission to a category usually needs an endorser. If arXiv asks, it shows a code; send it to an author who has published in `q-fin.RM` (for example by e-mail, with the abstract and a link to the repository).
- **Upload:** *Start new submission* → upload `docs/paper/dist/fintwin-arxiv.tar.gz`. arXiv processes it and shows the PDF; check it page by page.
- **Licence:** CC BY 4.0 (lets others reuse the work with attribution).
- **Primary category:** `q-fin.RM` (Risk Management). **Cross-lists:** `q-fin.CP` (Computational Finance), `stat.AP` (Applications).
- **Title, abstract, comments:** see *Metadata* below. arXiv limits the abstract to 1,920 characters, plain text.

## 3. SSRN

- **Account:** <https://www.ssrn.com> → *Register*.
- **Submit:** *Submit a paper* → upload `docs/paper/dist/fintwin.pdf`.
- **Classification:** JEL codes and keywords below. Ask for distribution in the FEN (Financial Economics Network) eJournals on *Risk Management* and *Corporate Finance: Capital Structure & Payout Policies*; SSRN editors make the final choice.
- After the arXiv version is public, add its link to the SSRN entry (*Edit → Additional links*).

## Metadata

**Title:** What Can a Financial Digital Twin Tell Us? Simulating Corporate Liquidity Stress from SEC Filings, with Out-of-Sample Evidence from COVID-19 and a Decade of Data

**Author:** Spilios Dimakopoulos (Independent researcher)

**Keywords:** stress testing; corporate liquidity; financial distress prediction; system dynamics; digital twin; XBRL; COVID-19; probabilistic forecasting

**JEL:** G32, G33, G17, C53, C63

**arXiv comments field:** `21 pages. Code, data and an interactive version: https://github.com/SpiliosDimakopoulos/fintwin`

**Abstract (plain text):** see `abstract.txt` next to this file; it is regenerated together with the paper.
