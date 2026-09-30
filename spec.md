# Planning Risk Radar — spec

A focused prototype for a Chief Risk Officer assessing the risk of **not obtaining planning
permission** for a proposed UK data centre. Not a corporate risk platform.

Built for the Antler UK16 Wednesday sprint, 30 Sep 2026.

## 1. Verified capability (checked before building, not assumed)

| Thing | Status | Evidence |
|---|---|---|
| Google Search grounding | **WORKS** | `gemini-2.5-flash` + `tools:[{google_search:{}}]` returned 13 real `webSearchQueries` and grounding chunks |
| Source URLs | **WORKS, with a catch** | grounding returns `vertexaisearch.cloud.google.com/grounding-api-redirect/...`, which 302s to the publisher. Resolved server side at retrieval time and stored, because the redirect expires |
| Credential | `GEMINI_API_KEY` | already in his environment; no Vertex project, no gcloud auth, no Custom Search key needed |

Not used, and why: Vertex AI Search (needs a GCP project and billing the Antler day accounts do not
carry past today), Custom Search JSON API (no `GOOGLE_CSE_ID` exists), and the Antler DevStar day
accounts (expire end of day, per the Google session this morning).

If `GEMINI_API_KEY` is missing the app renders a setup state naming the exact variable. It never
falls back to fictional findings.

## 2. Architecture

```
FastAPI (one process)  ->  SQLite (data/app.db)
         |
         +-- app/search.py   grounded retrieval + redirect resolution
         +-- app/assess.py   the heuristic (deterministic, documented below)
         +-- static/         vanilla JS SPA, no build step
```

Run: `uvicorn app.main:app --reload --port 8099`. No npm, no bundler.

## 3. Data model

- **project** — location, capacity_mw, cooling, grid_demand_mw, residential_m, context
- **review** — a timestamped snapshot of a project's search; enables "what changed"
- **evidence** — concern, title, publisher, resolved_url, redirect_url, published_date,
  retrieved_at, source_type (`planning_decision` | `authority_publication` | `news` | `unknown`),
  stance (`supporting` | `contradicting` | `context`), claim_type
- **risk** — register row: category, title, likelihood_band, impact_band, mitigation, notes,
  origin (`manual` | `csv` | `suggested`), accepted
- **assessment** — per concern per review: impact_band, likelihood_band, basis, insufficient flag

## 4. Screens

Overview, Risk detail, Evidence, Register, Suggested, Comparison. Decision-relevant summary first,
evidence one click away.

## 5. Assessment method (the part that must not lie)

**Impact and likelihood are computed separately, shown separately, and never multiplied into one
score.**

**Impact** comes from PROJECT INPUTS only, by stated rule. It never moves because of what was found
online. e.g. water concern impact is High when cooling is evaporative and capacity >= 100MW, Medium
when evaporative below that, Low when closed loop or air cooled. Every rule that fired is printed
on the risk detail screen.

**Likelihood** comes ONLY from comparable planning **decisions** retrieved, never from article
counts or sentiment. Fewer than 3 comparable decisions means the band is `INSUFFICIENT EVIDENCE`,
which is rendered distinctly from `LOW` and is never treated as low.

Explicitly not done: no probability of refusal, no sentiment score, no regulatory-grade claim. Where
sources disagree the disagreement is shown as two stances on the same concern rather than resolved.

**What changed** diffs the current review's evidence URLs against the previous saved review. With no
prior review it says "no prior review, nothing to compare" rather than inventing a trend.

## 6. Trust rules enforced in code

- Every evidence row carries a resolved URL and a retrieval timestamp, or it is not stored.
- Facts, reported claims, assumptions and suggested actions are separate fields, rendered separately.
- Search-derived risks land in **Suggested** and require explicit acceptance before entering the register.
- Unreachable page or missing date renders as "not available" rather than being filled in.

## 7. Accessibility

Bands are labelled in words and carry a shape, never colour alone. Palette is blue `#2563eb`,
orange `#f97316`, purple `#7c3aed`, cyan `#0891b2`, amber `#d97706`. No red/green pair anywhere.

## 8. Out of scope for this prototype

LLM scenario simulation, continuous monitoring, company-wide risk, auth, multi-tenant.
