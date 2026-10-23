# Mock peer review: "Does Simulation Add Information Beyond Persistence?"

Date: 2026-10-23 · Manuscript: `docs/paper/fintwin.pdf` (24 pages, revision branch) · Reviewer persona: referee for an
empirical finance / forecasting journal (e.g. International Journal of Forecasting, Journal of Banking & Finance).

**Package status.** Only the manuscript exists. There is no paper-finalizer package (no target journal, cover letter,
title page, declarations or checklist) and no manuscript-dev-log. This review therefore covers the manuscript only;
submission compliance could not be reviewed.

## Step 1: Referee report (Persona A)

**Overall: Major Revision.** A fresh search found no close published competitor (originality holds). The weaknesses
are in the central result.

### Fatal issues
None.

### Major issues
1. **§6.2 / Table 3: the encompassing regression is restricted.** The dependent variable and every regressor are
   departures from N1, so N1's noise enters all of them with the same sign, and N1's weight is restricted to 1 − Σb.
   This is Lekakos's objection in regression form. The standard unconstrained Fair–Shiller regression in levels was
   missing.
2. **§6.3 / Table 4: the hybrid lacked combination-puzzle controls.** Any second, noisier forecast blended with a
   small weight lowers the error (Bates & Granger 1969; Smith & Wallis 2009). N3+N6 was the only control; N3+N1,
   N3+N2 and N3+N5 were missing, and so was the literature.
3. **Abstract / §6.3: the headline "3.5%" was chosen after the results.** It came from a hybrid built on N3, chosen
   after N3 turned out to be the best rule; the pre-specified hybrid was built on N1. The manuscript did not disclose
   this.
4. **Framework §2.4 and §5.1 overclaimed pre-registration.** "For each hypothesis the decision rule was fixed..."
   is true only for H2. The "earlier draft" of the rule was never committed, so it cannot be verified.
5. **The title overclaimed.** "Every Non-Financial SEC Filer" is false: the sample is US-GAAP filers with $50M+
   revenue and 16 quarters of history.
6. **§3.3: the bankruptcy census was not validated.** Item 1.03 was described inaccurately: it is also filed at plan
   confirmation. There was no recall check and no discussion of measurement error.
7. **The outcomes of H1–H3 were never stated explicitly.**

### Minor issues
- `references.bib`: Lyytinen et al. is 2024, vol. 13(3), not 2023 (checked on IDEAS/RePEc).
- Framework: the IMF WP/20/238 description "static or one-period cash-flow rules" is not supported. The paper
  projects net income, funding availability and debt service.
- Conclusion and Discussion said "a sixth", but λ is 0.10–0.15.
- Ford/GM example: "reported operating cash flow rose" was inaccurate; it exceeded the rule's prediction.
- §10: the 75-day reporting lag for conformal was not explained.
- §5.3: clustering is by firm only; cross-sectional dependence within a year was not discussed.
- Leftovers: `SUBMISSION.md`, `abstract.txt`, `.zenodo.json`, README, `findings.png`, the evidence page and the CV kit
  carried the old title or the uncaveated "3.5%" claim. The data-audit sentence is missing because the audit has not
  finished.

### Citations re-verified (fresh searches)
Kritzinger et al. 2018 (model/shadow/twin taxonomy) ✓ · Fair & Shiller 1990 AER 80(3):375–389 ✓ (the
regression-on-two-forecasts method is as attributed) · Gibbs & Candès 2021 NeurIPS ✓ · Fama & French 2000 (mean
reversion ≈38%/yr) ✓ · Dechow–Kothari–Watts 1998 JAE 25(2):133–168 ✓ · IMF WP/20/238 ✓ (characterization corrected)
· Lyytinen et al. ✓ (year corrected) · Smith & Wallis 2009 OBES 71(3):331–355 ✓ (Crossref) · 8-K Item 1.03 usage ✓
(also plan confirmations).

## Step 2: Fixes (Persona B)

| # | Fix | Status |
|---|---|---|
| M1 | Added the unconstrained levels encompassing regression to the code (`transmission.encompassing`), the GitHub run, Table 3 and the text. Twin coefficient 0.23, t = 9.5 (FCF: 10.7). | **Resolved.** The result holds. |
| M2 | Added combinations N3+N1, N3+N2, N3+N5 and N3+T0 with paired CIs (Table 4), plus the Smith–Wallis citation. **The finding changed:** for operating cash flow, N3+N5 reaches 12.49 vs 12.45 for N3+T1 (p = 0.30). Only for FCF does the twin beat every simple combination (0.21 pp, CI 0.05–0.37). The abstract, introduction, §6.3, discussion, conclusion, README, site, CV kit and response letter were rewritten to match. | **Resolved.** The claim is weaker and now correct. |
| M3 | Disclosed in §5.1 ("Specifications added after the run"). | **Resolved.** |
| M4 | Framework now says the rule applies to H2 only; §5.1 says the earlier draft was never committed. | **Resolved.** |
| M5 | New title: "...Tested on a Survivorship-Free Panel of SEC Filers" (paper, abstract, Zenodo, SUBMISSION). | **Resolved.** |
| M6 | §3.3 now describes Item 1.03 correctly. Census recall: 33/35 of the known 2020 filers; 63% of firms have several 1.03 filings; measurement error is acknowledged. | **Resolved.** |
| M7 | New paragraph "The hypotheses": H1 rejected, H2 accepted with small magnitude, H3 partly supported. | **Resolved.** |
| minor | Lyytinen year, IMF wording, λ wording, Ford/GM, conformal lag, clustering caveat, stale metadata, findings figure (now shows the regression combination) | **Resolved.** |

## Step 3: Re-check of the changes
- The abstract, §6.3, the discussion and the conclusion now say the same thing (checked in the compiled PDF).
- Table 4 and the text agree: FCF −0.21 [−0.37, −0.05]; CFO vs regression −0.05 [−0.14, 0.04].
- Three new problems introduced by the fixes were found and corrected:
  - a duplicated sentence in §5.3;
  - an opaque label "N5 + change in revenue" in Table 2;
  - the negative 4-quarter weight in the levels regression, now explained as mean reversion.
- The compile is clean: 24 pages, no errors, no overfull boxes.
- The claim "presumably because the twin models capital expenditure" is labelled as conjecture. It remains untested
  and is a candidate for a future check (decompose the FCF gain into CFO and capex).

## Genuine blockers (need something external)
1. **No submission package.** Run paper-finalizer once a target journal is chosen: cover letter, declarations
   (COI, funding, data availability, CRediT), the journal's format and length.
2. ~~Data-audit numbers~~: added to §3.1 after workflow run 39849497834 finished (1,043 → 748 gaps; 87% of
   panels end at the last filed quarter; the mismatches come from SEC companyfacts lag and untagged revenue,
   verified by hand on HCA, Coca-Cola, Semtech and Garmin). **Still open:** a fallback parser for filings
   missing from companyfacts.
3. **Acknowledging the commenting researchers by name** needs their permission.
4. **SSRN posting** is the author's decision.
