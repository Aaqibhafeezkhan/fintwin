# Publishing the paper

The paper is published on **Zenodo** together with the code and data:

- Concept DOI (always the latest version): [10.5281/zenodo.23434606](https://doi.org/10.5281/zenodo.23434606)
- Each GitHub release is archived automatically as a new version under that DOI (`.zenodo.json` holds the metadata).

To publish a new version after changing the paper or the code:

```bash
cd engine
uv run python scripts/research_assets.py      # tables, figures and numbers from docs/paper/research.json
uv run python scripts/arxiv_bundle.py         # PDF + self-contained LaTeX source in docs/paper/dist/
gh release create vX.Y.Z docs/paper/dist/fintwin.pdf docs/paper/dist/fintwin-arxiv.tar.gz
```

`arxiv_bundle.py` also writes a plain-text abstract (`abstract.txt`) and compiles the LaTeX source in an empty folder,
so the bundle is ready if the paper is ever submitted to arXiv, SSRN or a journal.

**Title:** Does Simulation Add Information Beyond Persistence? A Financial Digital Twin Tested on a Survivorship-Free Panel of SEC Filers

**Keywords:** digital twin; system dynamics; corporate liquidity; cash-flow prediction; bankruptcy prediction; stress testing; XBRL; forecast encompassing

**JEL:** G32, G33, G17, C53, C63, M41
