# KPI Catalog

University group project for *Information Organization*: a website that organizes KPI definitions of a fictional retail group (Konfusio) with 8 divisions. It combines SKOS controlled vocabularies, faceted browsing, a folksonomy, ML auto-tagging, and a contributor → reviewer workflow with division-scoped roles.

- Requirements: [docs/PRD.md](docs/PRD.md) (read it before planning any feature)
- Assignment text: [group_project_description.md](group_project_description.md)
- Tasks and progress: [docs/TASKS.md](docs/TASKS.md). Prompts refer to tasks by ID (e.g. "work on W4"): check the task's "needs" are done, read the PRD sections it cites, and tick it when its "Done when" holds.

## Deadlines and capacity
- Mid-term description: **19 Nov 2026**. Final delivery (website, annotated dataset, vocabulary, presentation, ACM report): **21 Dec 2026**.
- Team of 3, part-time: George (dataset, vocabulary, ML), Liam (web app, report), Ioanna (UI wireframes, personas, user journeys). **Prefer the smallest change that satisfies a course requirement.** Don't add features outside PRD §9 without asking; use the cut order in PRD §12 when scope must shrink.

## Key decisions (details in the PRD)
| Topic | Decision |
|---|---|
| Dataset | Not fixed yet; the earlier sample catalog was inspiration only. A deterministic `kpigen`, written from scratch (fixed seed, no LLM or network calls at generation time), generates `data/seed/*.csv` (106 definitions). KPI text is **real** (HF `kavish218/multi_domain_dataset` @ `c148c8c`, dbt `jaffle-sl-template` @ `c54c8fb`, downloaded into git-ignored `data/raw/`) plus a few conflict cases and one quality KPI (PRD §14 Q2) we designed; the organization around it is synthetic. Our own seed text (KPI descriptions, conflict-case texts, community tags) was drafted with GenAI and is labelled so (PRD §3.5). Rows that don't fit the retail-group profile are excluded with a reason. See PRD §3. |
| Schema | `schema.sql` is the single source of truth (PRD §4): the seed is validated against it and the app is built from it. IDs are fixed in the curation files and never renumbered. |
| Stack | Flask + Jinja + SQLite (FTS5), Python 3.14 via uv. Local demo only, no hosting. |
| Roles | 5 division-scoped roles (Observer, Contributor, Curator, Reviewer, Admin). "Log in as" any seed user (no real auth); permissions are checked for real. No admin management UI. |
| Visibility | Approved and deprecated definitions are readable by everyone; drafts, in-review and rejected definitions only within the division (plus owner and Admin). |
| Versions | When a definition is superseded, its dashboard links, lineage and community tags move to the successor; the old version keeps only its review history and version chain (PRD §4.5). |
| Vocabulary | SKOS in Turtle (`vocab/kpi-vocabulary.ttl`), namespace `https://example.org/kpi-catalog/vocab/`. Schemes: Category (Balanced Scorecard + themes), Business line (NAICS), Division, Measure Type (from `unit`), Metric Type (dbt Semantic Layer), KPI Glossary. OWL is stretch only. |
| ML | Embedding similarity with `sentence-transformers/all-MiniLM-L6-v2`: tags Theme + Business line (the seed has none), checks units, flags synonyms and diverging definitions, suggests tags on submit. ML tags show as official with an "auto" marker until a curator accepts or rejects them. The batch skips deprecated definitions (PRD §6, §14 Q8). Evaluated against gold labels in `data/gold/` and baselines. |
| Tags | Official tags (`tags.kind = official`, SKOS concepts) and community tags (`kind = community`, folksonomy) attach to definitions and are always displayed as separate groups. Facets use official tags only; community tags get their own filter. Curators and Admin can promote community tags into SKOS. |
| Personas | Seed users: Emma Papadopoulos (USR-005, Observer), Katerina Okafor (USR-007, Curator), Noah Garcia (USR-053, Admin). |

## Commands
- `uv sync`: install dependencies
- `uv add <pkg>`: add a dependency (use uv, never pip)
- `uv run kpigen download`: fetch the pinned sources into `data/raw/` (the only network step)
- `uv run kpigen`: generate `data/seed/` and validate it (`schema.sql` + `tests/test_seed_rules.py`); `--strict` also fails on any `TODO(george)` placeholder
- `uv run pytest`: generator and seed tests
- Planned: `uv run kpi-catalog build` (load → tag → flag), `uv run flask --app kpi_catalog.web run --debug`

## Layout (planned, see PRD §11)
- `schema.sql`: the one schema definition.
- `src/kpigen/`: seed generator code. `kpigen/curation/*.csv` (domain_to_division, kpis, row_to_kpi, exclusions, relationships) and `kpigen/scenarios.yaml` hold every hand-made data decision. `data/seed/` is its output and is never edited by hand; change the curation files or the generator instead.
- `tests/test_seed_rules.py`: the PRD §3.6 business rules every seed must pass; `tests/test_kpigen.py`: generator tests.
- `data/raw/`: pinned source downloads (git-ignored; never commit them).
- `data/gold|annotated/`: gold labels and the exported annotated dataset. Every data-quality decision is logged in `data/quality_log.md` (it feeds the report).
- `vocab/`: hand-authored SKOS seed + generated exports.
- `src/kpi_catalog/{data,vocab,ml,web}/` + `db.py`.
- `docs/TASKS.md`: task tracker. `docs/user-journeys.md`, `docs/wireframes/`, `docs/demo-script.md`: Ioanna's UX inputs for the web pages and the demo.
- `exploration.ipynb`: scratch notebook.

## Conventions
- Never use an LLM to write or alter source KPI text (HF/dbt names, definitions). Seed text we supply ourselves may be GenAI-drafted (waived by George, 5 Nov) but must be listed as such in PRD §3.5 and kept out of the ML evaluation's scored text.
- The SKOS vocabulary is the single source of concept URIs: tags, facets and search expansion all reference it, so never hard-code category lists.
- Keep ML offline/batch for seed data; only new submissions are encoded at runtime.
- Persona prose in docs uses they/them pronouns.

## Keeping the docs in sync (mandatory)
Every new, changed or removed feature or decision must be recorded **in the same piece of work**, in each file where that information belongs. Update the existing text; don't append a contradicting note.

| File | Record here | Don't put here |
|---|---|---|
| `docs/PRD.md` | The decision and its reason: scope, features (§9), schema (§4), vocabulary (§5), ML (§6), personas and use cases (§7–8), site map and permissions (§10), milestones (§12), open questions (§14). Update "At a glance" if the big picture changes, the Status line in the header, and add a row to the **Change log (§15)**. | Setup steps |
| `CLAUDE.md` | Anything a future session needs to work correctly: key decisions table, commands, layout, conventions. One line per decision, pointing to the PRD section. | Feature details already in the PRD |
| `README.md` | What a newcomer needs: what the site does, current status, setup and run commands, data sources. | Design rationale |
| `docs/TASKS.md` | Task status (tick when done), new tasks with the next free ID, changed owners or dates | Decisions and their reasons |

Before finishing a task, check all three files against the change (renamed concepts, commands, paths, counts) and tick the task in `docs/TASKS.md`.
