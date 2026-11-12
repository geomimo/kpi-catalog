# Tasks

Progress tracker for the KPI Catalog, derived from the PRD's features (§9) and milestones (§12). Every `§` refers to [docs/PRD.md](PRD.md); read the cited section before starting a task.

## How to use this file
- **Status:** `[ ]` to do, `[x]` done. Add *(in progress)* after the title when you start one.
- **IDs are permanent.** Never renumber. A new task takes the next free number in its prefix. Use the ID in commit messages and prompts.
- **Tick the box in the same commit as the work**, once its "Done when" holds. Change dates and owners in place.
- **Decisions don't go here.** If a task changes scope or a decision, record it in the PRD, CLAUDE.md and README as CLAUDE.md requires. This file only tracks the work.
- **`cut #n`** marks a task that the PRD §12 cut order shrinks if we fall behind.
- **In a prompt:** *"Work on W4 from docs/TASKS.md."* The agent reads the task, checks its "needs" are done, and reads the PRD sections it cites.

## Team
| Person | Works on | Prefixes | PRD role |
|---|---|---|---|
| George | Dataset, vocabulary, ML | D, V, M | A |
| Liam | Web app (back and front), report | W, R | B, W (report) |
| Ioanna | UI wireframes, personas, user journeys | U | W (personas, journeys) |
| Everyone | Decisions, presentation, final checks | P | — |

**Critical path to the mid-term:** M1 (ML stack on 3.14, done) and D3 (`schema.sql`, done) unblock the rest → D4–D5 (reviewed, done) → V1 (vocabulary v0) → M2 (first tagging run). Liam can build W1–W3 on the generated seed in `data/seed/` now.

---

## Mid-term · 5–19 Nov

### Everyone
- [x] **P1 · Record the team split** · George · 5 Nov · PRD header, §14 Q6
- [x] **P2 · Choose the company name** · all · by 12 Nov · §14 Q1 · *done 11 Nov: Konfusio*
  - Done when: the name replaces "Acme" in the PRD, CLAUDE.md and README, and D5 uses it.

### George
- [x] **M1 · Check the ML stack on Python 3.14** · by 7 Nov · §6 Risk · *done 6 Nov: sentence-transformers 6.2.0 + torch 2.15.0 on 3.14.7; no pin needed*
  - Done when: `sentence-transformers` installs with `uv add` and `all-MiniLM-L6-v2` encodes a sentence. If it doesn't, the project is pinned to 3.13 and the docs say so.
- [x] **D1 · Commit the existing `kpigen` unchanged** · by 6 Nov · §3.4 · *dropped 5 Nov: there was no existing generator; D6 wrote it from scratch*
  - Done when: it is in `kpigen/` on main, so the rework has a baseline to diff against.
- [x] **D2 · Download the pinned sources** · by 8 Nov · §3.2
  - Done when: one command fills `data/raw/` with HF `testcontext_file1.csv` @ `c148c8c` and the three dbt YAMLs @ `c54c8fb`, git tracks nothing in `data/raw/`, and the retrieval date is noted for the report.
- [x] **D3 · Write `schema.sql`** · by 9 Nov · F0, §4
  - Done when: every table, foreign key, `CHECK` and `UNIQUE` from §4 is in it, it runs in `sqlite3` without errors, and Liam has reviewed it (W2 builds on it).
- [x] **P3 · Decide the *quality* theme** · by 10 Nov · §14 Q2 · *done 6 Nov: added Food Safety Incident Rate (KPI-0061, DEF-0308)*
  - Add one hand-written quality KPI, or leave the theme empty. Done when: the decision is in the PRD and D4 follows it.
- [x] **D4 · Write the curation files** · by 12 Nov · §3.3–3.4 · needs D2, P3
  - `domain_to_division.csv`, `kpis.csv`, `row_to_kpi.csv`, `exclusions.csv`, `relationships.csv`. Done when: every HF row and dbt metric appears exactly once in `row_to_kpi.csv` or `exclusions.csv`, the exclusion counts match §3.3 (or §3.3 is updated), and a second team member has reviewed the files. *Done 11 Nov: reviewed by George.*
- [x] **D5 · Write `scenarios.yaml`** · by 13 Nov · §3.4 · needs D4, P2, U2
  - Done when: every fixture listed in §3.4 is present with a fixed ID, and every step of the user journeys (U2) has the seed data it needs. *Done 11 Nov: reviewed by George, hf:24 → hf:40 supersession confirmed; Konfusio set by P2; further cases for the journeys go in D10.*
- [ ] **D10 · Add seed cases for the user journeys** · by 17 Nov · §3.4, §8 · needs U2
  - Done when: every step in `docs/user-journeys.md` has the seed data it needs (new fixtures in `scenarios.yaml` with fixed IDs), and `uv run kpigen` still passes.
- [ ] **V1 · Vocabulary v0** · by 14 Nov · §5
  - Hand-authored `vocab/kpi-vocabulary.ttl` with the Category (Balanced Scorecard + themes), Business line, Measure Type and Metric Type schemes. Every concept has a `skos:definition`, because the ML encodes it. Done when: rdflib parses the file without errors.
- [x] **D6 · Write `kpigen`** · by 15 Nov · F0, §3.4 · needs D3, D4, D5
  - Seed 42, reference date 2026-10-01, no network or LLM calls. Random fill: ~50 users, owners, statuses, review history, ~35 dashboards, ~40 community tags. `uv run kpigen` entry point. Done when: it writes `data/seed/*.csv` and `excluded.csv` with ~105 definitions, and two runs give byte-identical files.
- [x] **D7 · Validate the seed** · by 15 Nov · §3.6 · needs D6
  - Load into SQLite with `schema.sql`, plus the seven business rules in `tests/test_seed_rules.py`. Done when: `uv run kpigen` fails on a deliberately broken seed and passes on the real one.
- [ ] **D8 · Start `data/quality_log.md`** · by 17 Nov · §3.7 · needs D4
  - Done when: findings S1–S6, every exclusion reason, the seeded *Operating Expenses* error and the lessons from the sample catalog are logged. Feeds R1 and R3.
- [x] **M10 · Decide whether ML tags superseded definitions** · by 17 Nov · §4.5, §6, §14 Q8 · *done 11 Nov: the ML batch skips deprecated definitions*
  - The seed moves dashboards, lineage and community tags off a superseded definition (DEF-0025); M2 would still tag it. Done when: the decision is in PRD §6 and §14 Q8, and M2 follows it.
- [ ] **M2 · First tagging run (T1 theme, T2 business line)** · by 18 Nov · F9, §6 · needs M1, V1, D7, W2, M10
  - `ml/tagger.py`; embeddings saved as `.npy`. Done when: every definition except the deprecated ones (M10) has theme and business-line rows in `definition_tags` (`source = ml`, `status = auto`), and a short spot check is written up for the mid-term status.

### Liam
- [x] **W1 · Flask skeleton** · by 12 Nov · §10–11 · *done 11 Nov: placeholders for all 13 site-map routes, simple.css vendored, `tests/test_web.py`*
  - App factory in `src/kpi_catalog/web/`, base layout with navbar, small classless CSS, a placeholder for every page in the site map. Done when: `uv run flask --app kpi_catalog.web run --debug` serves every route.
- [x] **W2 · Database loader (`db.py`)** · by 15 Nov · §4, §11 · needs D3 · *done 11 Nov: `flask init-db`, FTS5 table `definitions_fts`, `tests/test_db.py`*
  - Creates `instance/catalog.sqlite` from `schema.sql`, loads `data/seed/*.csv`, builds the FTS5 index. Use the generated seed in `data/seed/`. Done when: it loads the real seed with foreign keys enforced.
- [ ] **W3 · "Log in as" and permission checks** · by 19 Nov · F1, §4.1, §4.5, §10 · needs W2
  - Switcher with seed users grouped by division and persona shortcuts; one check function (user, permission, division); the visibility rule for unpublished definitions. Done when: pytest covers every cell of the §10 capability table.
- [ ] **R1 · Mid-term description** · draft by 16 Nov, submit 19 Nov · §13 mid-term checklist
  - Inputs from George (dataset, vocabulary, ML status) and Ioanna (personas, site map). Done when: all six checklist questions are answered and the whole team has read it.

### Ioanna
- [ ] **U1 · Personas** · by 10 Nov · §7
  - Emma, Katerina and Noah in report-ready form (they/them). Done when: §7 reflects any changes and R1 can use them.
- [ ] **U2 · User journeys UC1–UC4** · by 12 Nov · §8
  - In `docs/user-journeys.md`. Done when: each step names the page, the action, what the user sees and the seed data it needs (George adds any missing data in D10).
- [ ] **U3 · Site-map figure** · by 15 Nov · §10
  - Done when: an image of the §10 site map (pages and who can open them) is ready for R1 and the report.
- [ ] **U4 · Wireframes: reading pages** · by 19 Nov · F1–F8, §10
  - Navbar with the log-in-as switcher; home; browse and search (facets, community-tag filter, A–Z, tag cloud); KPI page (definitions by division, official vs community tag chips, the "auto" marker, divergence, lineage and used-in panels); vocabulary and concept pages. Exported to `docs/wireframes/`. Done when: Liam has reviewed them before starting W4.

---

## Core catalog · 20 Nov–3 Dec

### Everyone
- [ ] **P4 · Choose who makes the slides and leads the demo** · all · by 3 Dec · §13
  - The presentation has no owner yet. Done when: the owner is named in the Team table and on R10.

### George
- [ ] **V3 · Official tags and measure type at load** · by 22 Nov · §4.2–4.3, §5 · needs V1, W2
  - `vocab/skos.py`: create official tags from the Category and Business line concepts, and map `unit` to Measure Type. Done when: the loader calls it and the facets can query both.
- [ ] **M3 · Gold labels** · George + one other member (TBD) · by 26 Nov · §6 · needs D7
  - Done when: 40 definitions have T1 theme labels from two annotators working independently, disagreements are resolved, and the T1 and T2 gold sets are in `data/gold/`.
- [ ] **V2 · Check the NAICS 2022 codes** · by 26 Nov · §5, §14 Q4
  - Done when: every Business line's `skos:closeMatch` and `skos:notation` has been checked against NAICS 2022, with the source cited.
- [ ] **V4 · Vocabulary v1** · by 27 Nov · §5 · needs V3
  - Generate the Division and KPI Glossary schemes from the database (altLabels from `display_name`, `dct:subject`, lineage properties), plus an altLabel lookup for search expansion (W5). Done when: rdflib parses the combined vocabulary and "Stock Turnover Rate" resolves to Inventory Turnover.
- [ ] **M4 · Unit check (T3)** · by 1 Dec · F9, §6 · needs M2, V3
  - Done when: *Operating Expenses* gets a `unit_mismatch` flag, and every other mismatch has been reviewed and logged in the quality log.
- [ ] **V5 · Validate the vocabulary** · by 3 Dec · §5 · needs V4
  - Done when: Skosify or SKOS Play reports no errors (any remaining warnings are explained), and its visualizations are saved as report figures.
- [ ] **M5 · ML evaluation** · by 3 Dec · §6 · needs M2, M3
  - `ml/evaluate.py`: accuracy and macro-F1 per task (T1 at theme and perspective level) against majority-class and keyword baselines; tune `τ_min`. Done when: the script generates `reports/ml_eval.md`.
- [ ] **M6 · One build command** · by 3 Dec · §11 · needs W2, M2, M4
  - Done when: `uv run kpi-catalog build` goes from `data/seed/` to a tagged and flagged database, and the README lists the command.

### Liam
- [ ] **R2 · Report skeleton** · by 26 Nov · §13
  - Done when: the ACM two-column Overleaf project has every section the assignment requires, with a page budget per section (5–6 pages in total).
- [ ] **W4 · Browse with facets** · by 27 Nov · F2 · needs W3, V3, M2, U4
  - Division, Category (two levels), Business line, Measure Type, Metric Type, Grain, Status; a separate community-tag filter; A–Z index. Done when: UC1's browse steps work as described in U2.
- [ ] **W5 · Search** · by 1 Dec · F3 · needs W4, V4
  - FTS5 over KPI names, labels, definition text and both kinds of tag, with altLabel expansion; each result says why it matched. Done when: "stock turnover" finds Inventory Turnover and the result says it matched an altLabel.
- [ ] **W6 · KPI page** · by 1 Dec · F4 · needs W3, V3, M2, U4
  - Done when: definitions are grouped by division with every field, official tags show as chips grouped by facet (ML ones marked "auto", with the confidence on hover), and community tags sit in their own row with counts.
- [ ] **W7 · Lineage, used-in, versions, review history** · by 3 Dec · F6, F7 · needs W6 · versions and history are cut #5
  - Done when: ATOPU shows that Finance's version divides Finance turnover by Product active users (UC2), and the Finance Weekly Flash Report appears under "used in".
- [ ] **W8 · Divergence panel** · by 3 Dec · F5 · needs W6
  - Use a few hand-inserted `similarity_flags` rows until M7 lands. Done when: Turnover shows a "definitions diverge" warning.
- [ ] **W9 · Vocabulary browser** · by 3 Dec · F8 · needs V4
  - Done when: `/vocabulary` lists the schemes, and each concept page shows its definition, broader, narrower and related concepts, and the definitions tagged with it.
- [ ] **W10 · Home page** · by 3 Dec · §10 · needs W4, W5
  - Done when: it shows search, "KPIs of <your divisions>" for the logged-in user, and facet entry points.
- [ ] **R3 · Dataset and data-quality section** · Liam + George · by 3 Dec · §3, §13 · needs D8
- [ ] **R4 · Six-question case study** · by 3 Dec · §13
  - Done when: it is written from the §13 sketch and the question wording is checked against the course template.

### Ioanna
- [ ] **U5 · Wireframes: workflow pages** · by 1 Dec · F10–F16, §10
  - Definition editor with ML suggestions, My definitions, review queue, tag validation queue, community-tag promotion, governance flags. Exported to `docs/wireframes/`. Done when: Liam has reviewed them before starting W11.

---

## Workflows · 4–12 Dec

### George
- [ ] **M7 · Similarity flags** · by 7 Dec · F9, §6, §14 Q3 · needs M2
  - `ml/similarity.py`: `possible_synonym` (above `τ_high`) and `definitions_diverge` (below `τ_low`). Done when: the expected hits listed in §6 are flagged, the false friend (*Inventory Amount* vs *Investment Amount*) is not, and the thresholds are recorded.
- [ ] **M8 · Suggestions for new submissions** · by 8 Dec · F10, §6 · needs M2, M7
  - One function the editor calls: theme and business-line suggestions, the measure type from the unit, and "a similar KPI already exists". It encodes only the new text. Done when: W11 can call it and Katerina's scenario draft gets the near-duplicate warning (UC3).
- [ ] **V6 · TTL export** · by 10 Dec · F15, §5 · needs V4
  - Done when: it writes `vocab/kpi-vocabulary.export.ttl` from the database, including promoted and merged labels, and rdflib parses the result.
- [ ] **P5 · OWL go/no-go** · 12 Dec · §5 (stretch S1), §14 Q5
  - Done when: the decision is in the PRD; if it is "go", S1 gets broken into tasks here.

### Liam
- [ ] **W12 · My definitions** · by 8 Dec · F11 · needs W3
  - Done when: a user's own drafts, in-review and rejected definitions are listed with their review comments.
- [ ] **W13 · Review queue** · by 8 Dec · F12, §4.5 · needs W3
  - Done when: a Reviewer can approve, reject or request changes with a comment, only in their own divisions and never on their own definitions, and the decision appears in the review history (UC3 as Dimitris).
- [ ] **W14 · Community tags** · by 8 Dec · F14 · needs W6
  - Done when: any user can add a tag to a definition, and browse shows a tag cloud.
- [ ] **W11 · Definition editor and submit** · by 10 Dec · F10 · needs M8, U5
  - Build the form first; plug in M8 when it is ready. Done when: a Contributor or Curator can create and edit a draft, sees the ML suggestions and the similar-KPI warning, and submits it (draft → in_review).
- [ ] **R5 · Personas and use cases section** · Liam + Ioanna · by 10 Dec · §7–8 · needs U1, U2
- [ ] **W15 · ML tag validation queue** · by 12 Dec · F13 · needs W6, M2 · cut #3
  - Done when: a Curator (own division) or the Admin (all divisions) can accept, change or reject "auto" tags, lowest confidence first, and rejected tags are hidden.
- [ ] **W16 · Community-tag promotion and TTL export button** · by 12 Dec · F15 · needs W14, V6 · cut #4
  - Done when: Noah can merge `northstar` and `North Star` into `north-star` and promote it (UC4), and the export contains the new label.
- [ ] **W17 · Governance flags page** · by 12 Dec · F16 · needs M7 · cut #2
  - Done when: Noah can merge, relate, dismiss or mark each flag fixed, including fixing the *Operating Expenses* unit (UC4).
- [ ] **W20 · Supersede a definition in the app** · Liam · by 12 Dec · F7, §4.5, §14 Q7 · needs W11, W13 · cut #5
  - The PRD shows `approved → deprecated (superseded_by_id)`, but no task builds it. First settle §14 Q7. Done when: either a Curator can submit a new version of an approved definition, and approving it deprecates the old one and moves its dashboard links, lineage and community tags to the new one (the same rule as `test_nothing_links_to_a_superseded_definition`); or Q7 decides versioning stays seed-only and this task is dropped.
- [ ] **R6 · Vocabulary section** · Liam + George · by 12 Dec · §5 · needs V5
  - Includes "What SKOS can't express" with the ATOPU example, whatever P5 decides.
- [ ] **R7 · ML section** · Liam + George · draft by 12 Dec, final numbers by 17 Dec · §6 · needs M5, M9
  - Method, results against the baselines, and how ML improves the organization.

### Ioanna
- [ ] **U6 · Walk through UC1–UC2 on the built site** · by 5 Dec · §8 · needs W4–W10
  - Done when: every journey step has been tried as Emma and Katerina, and the gaps are listed for Liam (as new W tasks or under W19).

---

## Polish · 13–17 Dec

### George
- [ ] **M9 · Final ML metrics** · by 15 Dec · §6 · needs M5, M7
  - Done when: `reports/ml_eval.md` has the final numbers and the chosen thresholds are recorded in PRD §14 Q3.
- [ ] **D9 · Annotated dataset and downloads page** · by 17 Dec · F17, §4.5 · needs M6, V6
  - Done when: `data/annotated/` has the seed's CSV layout after ML and curation plus `definitions_annotated.csv`, and `/downloads` serves it along with the TTL.

### Liam
- [ ] **W18 · About page** · Liam + Ioanna · by 15 Dec · F18
  - Done when: it covers the problem, personas, use cases, method and site map.
- [ ] **R8 · Site-map section** · by 15 Dec · §10 · needs U3
- [ ] **W19 · Polish and fix walkthrough issues** · by 17 Dec · §8 · needs U6, U7
  - Done when: UC1–UC4 run end to end with the scenario data and every issue from U6 and U7 is closed or consciously dropped.
- [ ] **R9 · Challenges and class concepts** · by 17 Dec · §13
  - Curation decisions, the limits of SKOS, ML against baselines, official vs community tags, permissions vs transparency.

### Ioanna
- [ ] **U7 · Walk through UC3–UC4 and write the demo script** · by 15 Dec · §8 · needs W11–W17
  - Done when: the gaps are listed for Liam, and `docs/demo-script.md` has a click path and talking points for each persona.

---

## Ship · 18–21 Dec
- [ ] **U8 · Report screenshots** · Ioanna · by 18 Dec · §8 success criteria · needs W19
  - Done when: every use-case step has a screenshot for the report and the slides.
- [ ] **P6 · Fresh-clone check** · George + Liam · by 19 Dec · §11
  - Done when: following the README on a fresh clone builds the database, runs the site, and produces the TTL and the annotated dataset.
- [ ] **R10 · Presentation slides** · owner from P4 · by 19 Dec · §13
  - Done when: the slides cover the problem, the organization approaches and how they fit together, and the ML results, and lead into the live demo (U7).
- [ ] **R11 · Demo rehearsal** · all · by 20 Dec · needs R10, U7
- [ ] **R12 · Contribution statement** · all · by 20 Dec · §13
- [ ] **R13 · Submit the final report and deliverables** · Liam · 21 Dec · needs R3–R9, R12
  - Done when: the report is 5–6 pages in ACM format, the team has proofread it, and it is submitted with the website, annotated dataset, vocabulary and slides.

---

## Stretch · only once the current milestone's tasks are done (§9)
- [ ] **S1 · Small OWL schema** · George · only if P5 is "go" · §5
- [ ] **S2 · Semantic search with the stored embeddings** · George · F3, §9
- [ ] **S3 · Comments on definitions** · Liam · §9
- [ ] **S4 · Dashboard page listing its definitions** · Liam · §9
- [ ] **S5 · Cohen's κ on the gold set** · George + the second M3 annotator · needs M3 · §6
