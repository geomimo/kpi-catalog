# KPI Catalog: Product Requirements Document

| | |
|---|---|
| **Course** | Information Organization, group project |
| **Status** | Draft v4, 5 Nov 2026. `kpigen` and `schema.sql` written; the seed validates; curation drafts and hand-written texts pending review. History in [§15](#15-change-log) |
| **Deadlines** | Mid-term description **19 Nov 2026** · Final delivery **21 Dec 2026** |
| **Team** | **A** = George (dataset, vocabulary, ML) · **B** = Liam (web app) · **W** = Liam (report) and Ioanna (personas, user journeys, UI wireframes). Slides owner still open ([§14](#14-open-questions)) |
| **Tasks and progress** | [`docs/TASKS.md`](TASKS.md) |
| **Source of truth for requirements** | [`group_project_description.md`](../group_project_description.md) |

Guiding rule: **build the smallest thing that satisfies every course requirement**, and make the organizing approaches visibly work together (the rubric rewards integration).

---

## At a glance (5-minute read)

**Status (5 Nov 2026):** planning is done (this PRD). The seed generator `kpigen` (written from scratch; there was no earlier generator to rework) and `schema.sql` exist, and the generated seed passes validation. The curation files are drafts awaiting review, and the hand-written texts are placeholders ([§3](#3-collection-and-generation-plan)). The website, vocabulary and ML are not started.

**The problem.** In a company with many departments, the same KPI name means different things: *Turnover* is counted one way in Finance, another in Commercial and a third in Product. Different names also mean the same thing (*Inventory Turnover* = *Stock Turnover Rate*). New employees can't tell which KPIs matter to them or what they mean, and departments argue about numbers that were never comparable.

**The solution.** A KPI catalog website for a fictional retail group, **Acme**, with 8 divisions. Anyone can look up a KPI and see every division's definition side by side, what it is calculated from, and which dashboards use it. Divisions publish definitions through a review step, so the catalog stays trustworthy.

**How it works**

| Part | What it does | Why (course requirement) |
|---|---|---|
| **Seed data** (`kpigen`) | A deterministic script builds 105 **real** KPI definitions (from Hugging Face, dbt and a few hand-written conflict cases), plus a **synthetic** organization around them (users, roles, reviews, dashboards) | The collection we organize: real content, with a realistic organization around it ([§3](#3-collection-and-generation-plan)) |
| **SKOS vocabulary** | Controlled lists: Category (Balanced Scorecard), Business line (NAICS), Division, Measure Type, Metric Type, and a KPI Glossary with synonyms | Formal organization in a standard format ([§5](#5-controlled-vocabulary-skos)) |
| **Community tags** | Anyone can add free tags. They are shown apart from official tags, and curators promote good ones into the vocabulary | Informal organization, connected to the formal one |
| **ML** (sentence embeddings) | Tags every definition with a theme and a business line, flags wrong units, finds synonyms and diverging definitions, and suggests tags while someone writes a definition | "Simple ML to auto-tag", and it keeps the catalog organized as it grows ([§6](#6-ml-approach)) |
| **Roles and workflow** | "Log in as" any seed user. Observers read; Contributors and Curators write; Reviewers approve; the Admin governs | Different users get different interactions ([§7](#7-personas)–[§8](#8-use-cases)) |
| **Website** (Flask + SQLite) | Browse with facets, search that understands synonyms, a KPI page (definitions, lineage, dashboards), an editor, and review and curation queues | Shows the use cases working ([§9](#9-features)–[§10](#10-site-map-and-permissions)) |

**Who uses it**
- **Emma** (new analyst, Observer) learns the Finance KPIs and finds out why ATOPU differs between departments.
- **Katerina** (Commercial Analytics Lead, Curator) publishes Commercial's definitions; a reviewer approves them.
- **Noah** (Data Governance Lead, Admin) checks ML tags, resolves conflicts and tidies the community tags.

**Key choices and why**
- **Real definitions, synthetic organization.** Public KPI datasets have no departments, owners or approval history, so we generate those, never the KPI text. LLM-written text would leave nothing to reflect on in the data-quality section and would make the ML evaluation circular.
- **One coherent company.** Source rows that don't fit a retail group (hospitals, municipalities, households) are excluded, with a recorded reason.
- **SKOS rather than OWL.** It is simpler and made for controlled vocabularies. What SKOS can't express (who owns a definition, what it is built from) lives in the database; OWL is a stretch goal ([§5](#what-skos-cant-express-report-material--stretch-goal)).
- **Pretrained embeddings rather than training a classifier.** With about 105 short definitions there is too little data to train on.
- **Approved definitions are visible to everyone.** The point is transparency across departments; only drafts are restricted to the division.
- **"Log in as" rather than real login.** Authentication isn't graded, but permission checks are still real.

**Deliverables:** website (local demo), annotated dataset, SKOS file, presentation and a 5–6 page ACM report by **21 Dec**; mid-term description by **19 Nov**.

---

## 1. Overview and problem

**Acme** (working name, still to be decided) is a fictional large retail group. It runs **stores**, an **online shop and app**, **food-to-go** counters and a paid **membership**, and also has a **bank and insurance arm**, a **mobile network**, a **property arm** (tenants in its shopping centres) and **own-brand production**. Some large supermarket groups really are set up this way. Acme has **8 group-wide divisions**: Finance, Commercial, Marketing, Product, Operations, People, Risk & Compliance, Data & Analytics. Every division reports KPIs, but:

1. **Onboarding load.** New employees don't know which KPIs matter to their division, what each one measures, which table it comes from, or which dashboards use it. Someone has to explain it, every time.
2. **Cross-division miscommunication.** For example:
   - **Turnover** is booked revenue in Finance, product revenue excluding tax in Commercial, and gross completed purchases before refunds in Product.
   - **Active Users** means *transacting in the last 30 days* in Product but *any session in the last 30 days* in Marketing.
   - **ATOPU** in the Finance board pack divides *Finance* turnover by *Product's* active users, so it never matches the Product dashboard.
   - Different names often mean the same thing: *Inventory Turnover*, *Stock Turnover Rate* and *Inventory Stock Turnover* are one measure.

**The KPI Catalog** is a website that organizes these KPI definitions so people can find, understand and compare them, and so divisions can maintain them through a governed workflow. It combines:
- **Formal organization:** SKOS controlled vocabularies, faceted classification, hierarchy, synonym control and typed relationships (lineage).
- **Informal organization:** community tags (a folksonomy), shown apart from official tags, and an A–Z listing.
- **Computational organization:** ML auto-tagging (theme, business line), unit checks, and detection of synonyms and diverging definitions.
- **Social organization:** contributor → reviewer approval workflow, curator validation of ML tags, and promotion of community tags into the vocabulary.

## 2. Goals and non-goals

### Goals (mapped to the grading criteria)
| Goal | Rubric criterion |
|---|---|
| Every course deliverable and report section is covered (see [§13](#13-requirements-traceability)) | Comprehensiveness |
| Every design choice has a written rationale (sources, curation, vocabulary, ML, site structure) | Rationale |
| Formal, informal, computational and social organization all appear in the site | Various organization approaches |
| SKOS + Dublin Core, reusing the Balanced Scorecard, NAICS and the dbt Semantic Layer metric types | Application of standards |
| Approaches feed each other: ML tags point to SKOS concepts, curators validate ML tags, community tags get promoted into SKOS, search expands queries through altLabels, measure type comes from units via the vocabulary | Integration |

### Non-goals (explicitly out of scope)
- **LLM-written KPI content.** GenAI may help write code, never definitions or tags in the seed.
- Real authentication. A **"log in as" switcher over the seed users** replaces it, and permissions are still checked for real.
- Admin management UI (users, roles, divisions). The Admin role exists and has full visibility; the management pages are only described in the report.
- *Editing* KPI relationships and dashboard links. Both are **shown read-only** from the seed data.
- Diffs between definition versions. Only the `superseded_by` chain is shown.
- Comments (stretch). Public hosting (the demo runs locally).

## 3. Collection and generation plan

### 3.1 Principles
1. **Real content, synthetic organization.** Every KPI name, definition text and formula comes from a real public source, or from a **small hand-written set of conflict cases** that we design and label as ours. Divisions, users, roles, owners, statuses, versions, reviews and dashboards are synthetic.
2. **One coherent company.** A source row is kept only if it plausibly belongs to Acme's profile ([§1](#1-overview-and-problem)). Every excluded row is recorded with a reason.
3. **Reproducible.** The generator is deterministic: fixed random seed, fixed reference date, **no LLM or API calls when it runs**. Running it twice gives byte-identical CSVs.
4. **Every curation decision is visible.** Groupings, units, divisions and exclusions live in hand-edited files that two team members review. These files are the evidence for the report's data-quality section.

### 3.2 Sources
| Source | Pinned version | What we take | Licence |
|---|---|---|---|
| Hugging Face [`kavish218/multi_domain_dataset`](https://huggingface.co/datasets/kavish218/multi_domain_dataset), `testcontext_file1.csv` | revision `c148c8c2945589fec92d91380e2f5b314ad18a91` | Term, description, domain, table, column, context columns (107 rows) | None declared |
| dbt Labs [`jaffle-sl-template`](https://github.com/dbt-labs/jaffle-sl-template): `orders.yml`, `order_items.yml`, `customers.yml` | commit `c54c8fb8bea86c0c4d3d5c588d55f8de9de57ade` | Semantic Layer metrics: names, descriptions, formulas, lineage (17 metrics); they fit Acme's food-to-go business | None declared |
| Hand-written conflict cases (in `scenarios.yaml`) | in repo | Turnover, Active Users, ATOPU, Gross Margin % per division (~6–8 definitions) | Ours |

Because neither external source declares a licence, the generator **downloads them at the pinned versions** into the git-ignored folder `data/raw/` and **never commits copies**. The report cites both with their version and retrieval date (first retrieved 5 Nov 2026; `kpigen download` checks each file against a pinned SHA-256, so a later retrieval gives the same bytes).

### 3.3 What gets excluded (expected)
| Reason | Rows |
|---|---|
| Not a quantitative measure: education identifiers (*Student Identifier*, *College ID*, …) | 10 |
| Not a quantitative measure: *Accounts Payable Due Date* (a date) | 2 |
| Doesn't fit the company profile: hospital (patients, medical supplies, healthcare facility) | 6 |
| Doesn't fit the company profile: household tax (personal finance) | 2 |
| Doesn't fit the company profile: municipality infrastructure spending | 2 |
| Doesn't fit the company profile: car, electronics and pharmaceutical defect rates | 3 |
| dbt template examples, not business KPIs (*Twice Orders*, *Orders (Fill nulls with 0)*) | 2 |

**Result:** 82 HF + 15 dbt + 8 hand-written (7 conflict cases + Katerina's UC3 draft) = **105 definitions** of 60 KPIs. (The earlier estimate counted 1 municipality row; the pinned file has 2, rows 25 and 41.) Removing the defect rates leaves the Category theme *quality* with no example ([§14](#14-open-questions)).

### 3.4 The generator: `kpigen`
There was no earlier generator to rework, so `kpigen` was written from scratch with GenAI help (code in `src/kpigen/`). `uv run kpigen download` fetches the pinned sources and checks their SHA-256; `uv run kpigen` generates and validates without any network or LLM call.

```
data/raw/ (downloaded, pinned)     kpigen/curation/*.csv    kpigen/scenarios.yaml
              └────────────────────────────┬──────────────────────────┘
                                        kpigen  (seed 42, reference date 2026-10-01)
                                           ▼
                         data/seed/<table>.csv  +  data/seed/excluded.csv
                                           ▼
                validate: load into SQLite with schema.sql (foreign keys + CHECKs)
                          + pytest business rules (§3.6) → seed accepted only if both pass
```

**Hand-edited inputs** (`kpigen/curation/`):

| File | One row per | Decides |
|---|---|---|
| `domain_to_division.csv` | HF domain | Division and business line (also the gold labels for ML task T2) |
| `kpis.csv` | KPI | Fixed `kpi_id`, slug, name, and a division-neutral description |
| `row_to_kpi.csv` | Source row (HF row number / dbt metric) | Fixed `definition_id`, the KPI it belongs to (every merge or split happens here), the label the division uses, **unit**, **grain** |
| `exclusions.csv` | Excluded source row | Reason (from [§3.3](#33-what-gets-excluded-expected)); copied to `data/seed/excluded.csv` |
| `relationships.csv` | Hand-curated link between two definitions | `related_to` / `subset_of` links for findings S3 (shared column names) and gross vs net product revenue. dbt lineage is derived from the YAML (ratio → numerator/denominator, derived → inputs, cumulative → `cumulative_of`, filtered simple metric → `subset_of`); ATOPU lineage is in `scenarios.yaml` |

**Who writes what.** GenAI may draft the *decisions* in these files (grouping, division, unit, grain, exclusions) for two team members to review, but never free text: division-neutral KPI descriptions, the hand-written conflict-case definitions and the community-tag labels are written by a person. Until then they hold a `TODO(george)` placeholder; `uv run kpigen` warns about them and `uv run kpigen --strict` fails.

**`kpigen/scenarios.yaml`** (fixtures copied exactly, with fixed IDs):
- **People:**
  - Emma Papadopoulos (Observer, Finance; account created Oct 2026)
  - Katerina Okafor (Curator, Commercial)
  - Noah Garcia (Admin)
  - Dimitris Jansen (Reviewer, Commercial)
  - Anna Okafor (Contributor, Commercial)
- **UC1:** at least 5 approved Finance definitions, some with lineage, linked to a "Finance Weekly Flash Report".
- **UC2 (hand-written definitions):**
  - Turnover: Finance booked revenue (EUR), Commercial revenue excluding tax (USD), Product gross before refunds.
  - Active Users: Product transacting vs Marketing any session, **both approved**.
  - ATOPU: Finance and Product versions, with lineage.
  - Gross vs net product revenue.
- **UC3:**
  - A draft by Katerina under an existing KPI with a near-duplicate label.
  - 2–3 in-review items for Dimitris, one with a "changes requested" history.
- **UC4:**
  - *Operating Expenses* with unit `score` (a **deliberately seeded error**, documented in the quality log).
  - One real synonym pair under two different KPIs.
  - One false friend (*Inventory Amount* vs *Investment Amount*).
  - Community-tag variants: `north-star`, `northstar`, `North Star`, `board-pack`, `profitability` (fixture labels keep exactly their fixture uses, so the UC4 story stays stable).
  - One definition correctly superseded by a newer version (draft: Finance *Capital Expenditure*, `hf:24` → `hf:40`; to be confirmed).

**Random fill (seeded)** around the fixtures:
- About 50 users with 1–2 division-scoped roles each.
- Owners and statuses for the remaining definitions.
- A review history for every definition that isn't a draft, with generic comments per decision type, not text that pretends to know the content.
- About 35 dashboards and reports, linked only to definitions of their own division.
- About 40 community tags.

**The seed contains no theme or business-line tags.** Those come only from the ML run ([§6](#6-ml-approach)).

### 3.5 Real vs synthetic (state this in the report)
| Real | Hand-written by us | Synthetic (generated) |
|---|---|---|
| HF and dbt KPI names, texts, formulas, dbt lineage | Conflict-case definitions and their lineage; curation decisions (grouping, units, divisions, exclusions); gold labels | Users, roles, owners, statuses, versions, reviews, dashboards, community tags |

### 3.6 Validation (runs after every generation)
- **`schema.sql`**: foreign keys, `CHECK` constraints on every enum, `UNIQUE` constraints.
- **pytest business rules:**
  - A definition is superseded only by one in the same division and the same KPI.
  - Every owner holds a role in that definition's division.
  - Every reviewer holds the Reviewer role in that division and isn't the owner.
  - Every approved, rejected or deprecated definition has a matching review.
  - Every fixture from `scenarios.yaml` is present with its fixed ID.
  - Dashboard names are unique.
  - No theme or business-line tags exist in the seed.

### 3.7 Data quality: findings and lessons (report material)
**Findings in the real sources** (each handled by a curation file and logged in `data/quality_log.md`):

| # | Finding | Handled by |
|---|---|---|
| S1 | HF `domain` mixes **industries** (retail, telecom) with **business functions** (finance, HR, marketing), and includes sectors no single company spans (hospitals, municipalities, households) | Split into Division + Business line (`domain_to_division.csv`); company-profile rule (`exclusions.csv`) |
| S2 | Synonym label variants (up to 6 labels for inventory turnover; 3 for the quick ratio) | One KPI; each label kept as the division's label and as a SKOS altLabel (`row_to_kpi.csv`) |
| S3 | A shared column name doesn't mean the same measure (`cust_fb` = CSAT / NPS / CX rating; `op_eff`; `emp_sat`) | Separate KPIs, linked as related |
| S4 | Homonymous abbreviation `inv_amt` (inventory / investment / invoice amount) | Separate KPIs |
| S5 | No units in the HF data; column typos (`ales_rev`); short descriptions (40–115 chars) | Units and grain assigned by hand; typos fixed in the mapping; short texts are why we use pretrained embeddings |
| S6 | dbt typos ("Distict", "amonunt", "colaescing") and template-only metrics | Typos fixed in the mapping; template metrics excluded |

**Lessons from the sample catalog** (why the rules above exist):
- The sample's generator *guessed* groupings, units and divisions → those are now hand-edited mapping files.
- Its tags were generator output that would have quietly become "truth" → no theme or business-line tags in the seed; gold labels are kept separate.
- It produced supersession across different meanings (Portfolio Equity → Total Equity), review comments that didn't fit, dashboards linked across divisions and duplicate dashboard names → the pytest rules above.
- Its tag categories were muddled (functions filed as industries, duplicate `supply-chain`, `north-star` as a theme) → official tags come only from SKOS; `north-star` becomes a community tag.
- Its KPI descriptions were copied from one division's definition → `kpis.csv` holds division-neutral descriptions.

## 4. Information model

The schema is derived from the features in [§9](#9-features) and lives in **one executable file, `schema.sql`** (SQLite). The generator's output is validated against it, the app creates its database from it, and this section documents it. Only tables used by MVP features are included; stretch tables are added only if built. IDs are readable strings (`DIV-001`, `KPI-0001`, `DEF-0001`, …) that are **fixed in the hand-edited files**, so regenerating never renumbers anything.

```
divisions ─┬─< user_roles >── users            roles ─< role_permissions >─ permissions
           │                     │ owner / reviewer / tagger
           └─< definitions >─────┘
kpis ─────────< definitions ─< definition_tags >─ tags (official → SKOS concept | community)
                definitions ─< kpi_relationships >─ definitions    (lineage, typed)
                definitions ─< reviews                              (workflow history)
                definitions ─< asset_definitions >─ assets          ("used in")
                definitions ─< similarity_flags                     (ML output)
```

### 4.1 Organization and access
| Table | Columns (constraints) | In seed |
|---|---|---|
| `divisions` | `division_id` PK · `code` UNIQUE (FIN, COM, MKT, PRD, OPS, PPL, RSK, DAT) · `name` · `description` | ✅ |
| `users` | `user_id` PK · `full_name` · `email` UNIQUE · `home_division_id` FK · `job_title` · `created_at` | ✅ |
| `roles` | `role_id` PK · `code` UNIQUE ∈ {observer, contributor, curator, reviewer, admin} · `name` · `description` | ✅ |
| `permissions` | `permission_id` PK · `code` UNIQUE · `description` | ✅ |
| `role_permissions` | `role_id` FK · `permission_id` FK · PK (both) | ✅ |
| `user_roles` | `user_id` FK · `role_id` FK · `division_id` FK, NULL only for admin · UNIQUE (user, role, division) | ✅ |

**Permissions** (only those the app checks):

| Code | Scope | Observer | Contributor | Curator | Reviewer | Admin |
|---|---|:-:|:-:|:-:|:-:|:-:|
| `tag.add_community` | everywhere | ✅ | ✅ | ✅ | ✅ | ✅ |
| `definition.view_unpublished` | division | | ✅ | ✅ | ✅ | |
| `definition.view_unpublished_all` | all | | | | | ✅ |
| `definition.propose` | division | | ✅ | ✅ | | ✅ |
| `definition.edit` / `definition.deprecate` | division | | | ✅ | | ✅ |
| `definition.approve` | division | | | | ✅ | ✅ |
| `tag.manage` (validate ML tags, promote community tags) | division | | | ✅ | | ✅ |
| `governance.manage` (flags page, TTL export) | all | | | | | ✅ |

The app has one check function: *does user U hold a role with permission P in division D?* An Admin has every permission everywhere.

### 4.2 Catalog
| Table | Columns (constraints) | In seed |
|---|---|---|
| `kpis` | `kpi_id` PK · `slug` UNIQUE · `name` · `description` (division-neutral) · `created_at` | ✅ |
| `definitions` (several per KPI and division allowed, told apart by `source_table`) | `definition_id` PK · `kpi_id` FK · `division_id` FK · `display_name` (the label this division uses) · `definition_text` · `metric_type` ∈ {base, simple, ratio, derived, cumulative} · `formula` NULL · `unit` ∈ {EUR, USD, %, ratio, times, count, score} · `grain` ∈ {daily, weekly, monthly, quarterly} · `source_table` NULL · `source_column` NULL · `related_columns` NULL · `owner_user_id` FK · `status` ∈ {draft, in_review, approved, rejected, deprecated} · `version` ≥ 1 · `superseded_by_id` FK NULL · `created_at` · `updated_at` · `origin` ∈ {huggingface, dbt, handwritten, app} · `origin_ref` | ✅ |
| `kpi_relationships` | `relationship_id` PK · `from_definition_id` FK · `to_definition_id` FK · `relationship_type` ∈ {composed_of, subset_of, cumulative_of, related_to} · `role` ∈ {numerator, denominator, input} NULL · `alias` NULL · `offset_window` NULL · `origin` | ✅ |
| `reviews` | `review_id` PK · `definition_id` FK · `reviewer_user_id` FK · `decision` ∈ {approved, rejected, changes_requested} · `comment` · `reviewed_at` | ✅ |
| `assets` | `asset_id` PK · `asset_type` ∈ {dashboard, report} · `name` UNIQUE · `description` · `tool` · `url` · `division_id` FK · `owner_user_id` FK · `created_at` | ✅ |
| `asset_definitions` | `asset_id` FK · `definition_id` FK · PK (both) | ✅ |

**Derived at load time, not in the seed:** each definition's **measure type**, taken from `unit` through the SKOS Measure Type mapping ([§5](#5-controlled-vocabulary-skos)).

### 4.3 Tags (official and community)
| Table | Columns (constraints) | In seed |
|---|---|---|
| `tags` | `tag_id` PK · `kind` ∈ {official, community} · `label` · `facet` ∈ {category, business_line}, required for official, NULL for community · `concept_uri`, required for official, NULL for community · `created_by` FK NULL · `created_at` · UNIQUE (kind, label) | Community tags only; official tags are generated from the SKOS file at load |
| `definition_tags` | `definition_id` FK · `tag_id` FK · `source` ∈ {ml, curator, user} · `confidence` (ML only) · `status` ∈ {auto, accepted, rejected}, NULL for community tags · `tagged_by` FK NULL (NULL for ML) · `tagged_at` · PK (definition, tag) | Community taggings only |

- **Official tags** are SKOS concepts. They come from ML (`status = auto` until checked) or from curators (`accepted`). A curator accepting or rejecting a tag changes its status; rejected tags are hidden.
- **Community tags** are free text added by any user. Promoting one makes it an altLabel of an existing concept, or a new concept: the community tagging is repointed to the official tag and the SKOS export gains the label.

### 4.4 ML output
| Table | Columns (constraints) | In seed |
|---|---|---|
| `similarity_flags` | `flag_id` PK · `type` ∈ {possible_synonym, definitions_diverge, unit_mismatch} · `a_definition_id` FK · `b_definition_id` FK NULL (NULL for unit checks) · `score` · `status` ∈ {open, merged, related, dismissed, fixed} · `resolved_by` FK NULL · `resolved_at` NULL | — (produced by ML) |

Embeddings are stored in a `.npy` file next to the database, not in a table.

### 4.5 Definition lifecycle and visibility
```
draft ──submit──► in_review ──approve──► approved ──supersede──► deprecated (superseded_by_id)
  ▲                  │ └──reject──► rejected
  └─changes_requested┘
```
- **Who does what:** Contributors and Curators create and submit drafts; Reviewers decide; Curators edit approved definitions and deprecate them. A Reviewer cannot edit (separation of duties).
- **Who sees what:** `approved` and `deprecated` definitions are readable by **everyone**. `draft`, `in_review` and `rejected` ones are readable by their owner, by users with `definition.view_unpublished` in that division, and by Admins.

**Annotated dataset deliverable:** `data/annotated/` has the same CSV layout as `data/seed/`, after ML tagging and curation (official tags with source, confidence and status; similarity flags). It also contains a flat `definitions_annotated.csv` (one row per definition with KPI, division, measure type, theme and business line, each with label, URI, confidence and source).

## 5. Controlled vocabulary (SKOS)

**Format:** SKOS in Turtle, `vocab/kpi-vocabulary.ttl`, namespace `https://example.org/kpi-catalog/vocab/` (prefix `kv:`).
**Reused standards and vocabularies:**
- SKOS (W3C)
- Dublin Core Terms (`dct:source`, `dct:subject`, `dct:created`, `dct:modified`, `dct:creator`)
- Balanced Scorecard perspectives (Kaplan & Norton, 1992)
- NAICS 2022 (business lines)
- dbt Semantic Layer metric types (`simple`, `ratio`, `derived`, `cumulative`)
- QUDT, optional, for units

Related work to cite: KPIOnto (Diamantini, Potena & Storti).

| Scheme | Origin | Contents (draft v0) | Used for |
|---|---|---|---|
| **Category** | Hand-authored; top level = Balanced Scorecard, narrower concepts = themes | **Financial** → revenue · cost · balance-sheet · tax · risk<br>**Customer** → customer · engagement<br>**Internal Process** → supply-chain · quality · efficiency<br>**Learning & Growth** → workforce | ML target (T1); official tags; facet |
| **Business line** | Hand-authored from Acme's profile | Stores · Online · Food-to-go · Membership · Banking · Insurance · Mobile · Property · Own-brand production · **Group-wide**. Each has `skos:closeMatch` + `skos:notation` to a NAICS 2022 code; **check every code against NAICS 2022 before publishing** | ML target (T2); official tags; facet |
| **Division** | Generated from `divisions` | The 8 divisions, with `skos:notation` = division code | Facet |
| **Measure Type** | Hand-authored | Monetary Amount (`EUR`, `USD`) · Percentage / Rate (`%`) · Ratio (`ratio`, `times`) · Count (`count`) · Score / Index (`score`); units listed with `skos:notation` | Derived facet; ML unit check (T3) |
| **Metric Type** | Reused from the dbt Semantic Layer | simple · ratio · derived · cumulative, + *base* (no formula recorded) | Facet; explains formulas |
| **KPI Glossary** | Generated from the curated data | One `skos:Concept` per KPI: `prefLabel` = KPI name, `altLabel` = every other `display_name` + promoted community tags, `dct:subject` → Category / Business line concepts. Lineage as `kv:composedOf`, `kv:subsetOf`, `kv:cumulativeOf`, each declared `rdfs:subPropertyOf skos:related`; `related_to` → `skos:related` | Search expansion, vocabulary browser, export |

```turtle
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dct:  <http://purl.org/dc/terms/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix kv:   <https://example.org/kpi-catalog/vocab/> .
@prefix kpi:  <https://example.org/kpi-catalog/kpi/> .

kv:composedOf rdfs:subPropertyOf skos:related ;
    rdfs:label "composed of"@en .

kv:Financial a skos:Concept ;
    skos:inScheme kv:CategoryScheme ; skos:topConceptOf kv:CategoryScheme ;
    skos:prefLabel "Financial"@en ;
    dct:source "Kaplan & Norton (1992), The Balanced Scorecard" ;
    skos:narrower kv:Revenue .

kv:Revenue a skos:Concept ;
    skos:inScheme kv:CategoryScheme ;
    skos:prefLabel "Revenue"@en ;
    skos:altLabel "Turnover"@en, "Sales"@en ;
    skos:definition "Measures of income earned from selling goods or services."@en ;
    skos:broader kv:Financial .

kpi:inventory_turnover a skos:Concept ;
    skos:inScheme kv:KpiGlossary ;
    skos:prefLabel "Inventory Turnover"@en ;
    skos:altLabel "Inventory Turnover Ratio"@en, "Inventory Turnover Rate"@en,
                  "Inventory Stock Turnover"@en, "Stock Turnover Rate"@en, "Product Turnover Ratio"@en ;
    dct:subject kv:SupplyChain .

kpi:atopu a skos:Concept ;
    skos:inScheme kv:KpiGlossary ;
    skos:prefLabel "Average Turnover per Active User"@en ;
    skos:altLabel "ATOPU"@en ;
    kv:composedOf kpi:turnover, kpi:active_users .
```

**Lifecycle:** the hand-authored schemes are a seed TTL; the Division and KPI Glossary schemes are generated from the database. Official tags are created from the Category and Business line concepts when the database is loaded. Runtime changes (promotions, merges) are written to SQLite, and an **Export** action regenerates `vocab/kpi-vocabulary.export.ttl` with rdflib. Validation: rdflib parses the file without errors, plus a Skosify / SKOS Play check (their visualizations also give us report figures).

### What SKOS can't express (report material + stretch goal)

**In short:** SKOS can say "Turnover is a KPI, also called Revenue, in the Financial category". It can't say "*this* definition of Turnover belongs to Finance" or "Finance's ATOPU is built from Finance's turnover". Those details live in the database instead.

**Why.** SKOS works with *concepts* (ideas such as "Turnover") and their names. Our catalog has a layer below that: each KPI has several *definitions*, one per division, each with its own text, formula and owner. SKOS has no place for that layer, which causes two problems:

1. **It can't tie a definition to a division.** We could put all three Turnover texts on the Turnover concept, but nothing would say which one is Finance's, Commercial's or Product's.
2. **It can't show what a specific definition is built from.** Take ATOPU (average turnover per active user):

   | | Divides … | … by |
   |---|---|---|
   | ATOPU, Product version | Product's turnover | Product's active users |
   | ATOPU, Finance version | **Finance's** turnover | **Product's** active users |

   In SKOS we can only write "ATOPU is made of Turnover and Active Users". That is true of both versions, so it hides the reason the Finance board pack and the Product dashboard never match.

**What we do.** Each tool does what it's good at:
- The **database** holds the details: which division owns each definition, and which definitions feed which (including numerator and denominator). The KPI page and its lineage panel read from it.
- **SKOS** holds the vocabulary: names, synonyms, categories, business lines and links between KPIs. It drives the facets, search and the vocabulary browser.

**Stretch S1 (OWL).** OWL is a richer W3C standard that can treat each definition as an item in its own right, with properties such as "owned by Finance" or "numerator: Finance turnover". A small schema (`KPI`, `Definition`, `Division`, `hasDefinition`, `ownedBy`, `hasNumerator` / `hasDenominator`) would let us ask "which definitions use another division's numbers?", which would catch the ATOPU problem automatically. Go/no-go decision on 12 Dec.

**For the report:** write this up even if we skip OWL. Showing where the chosen standard stops, with the ATOPU example, counts toward "application of standards" and "reflection on challenges".

## 6. ML approach

The seed has **no** theme or business-line tags, so ML is their only automatic source. Curators then check them.

| Task | Predicts | Input | Gold labels for evaluation (`data/gold/`) |
|---|---|---|---|
| **T1 Theme** | 1–2 Category themes (perspective derived via `skos:broader`) | `display_name + definition_text` (+ formula, when present) | 40 definitions labelled by hand by two team members |
| **T2 Business line** | 1 Business line concept | same | The original HF `domain`, mapped through `domain_to_division.csv` (all HF definitions; not evaluated on dbt and hand-written ones) |
| **T3 Unit check** | Measure Type, predicted from the text alone | same | Compared with the measure type derived from `unit`; a disagreement creates a `unit_mismatch` flag (the seeded *Operating Expenses* error must be caught) |

**Method (embedding similarity, no training):**
1. Encode each definition with `sentence-transformers/all-MiniLM-L6-v2` (small and CPU-friendly).
2. Encode each concept as `prefLabel + altLabels + skos:definition`.
3. Compute cosine similarity and keep the top-k concepts above a minimum score `τ_min`.
4. Write `definition_tags` rows with `source = ml`, the `confidence`, and `status = auto`. They show up straight away as official tags with an **"auto"** marker. The curator's validation queue lists them lowest confidence first.

Embeddings for the seed data are **computed offline once**; the web app only encodes new submissions.

**Evaluation (for the report):**
- **Metrics:** accuracy and macro-F1 per task. T1 at both theme and perspective level.
- **Baselines:** majority class, and keyword rules (e.g. "revenue|sales" → revenue).
- Use the gold set to tune `τ_min`.
- Optional: Cohen's κ between the two annotators.

**Runtime reuse of the same model:**
- **Submit suggestions:** while a contributor or curator writes a definition, the form suggests a theme and a business line, shows the measure type derived from the chosen unit, and warns "a similar KPI already exists: …".
- **Similarity flags:**
  - `possible_synonym`: definitions under **different** KPIs with similarity > `τ_high`. The Admin can merge (altLabel), relate, or dismiss.
  - `definitions_diverge`: definitions of the **same** KPI in different divisions with similarity < `τ_low`. This shows as a warning on the KPI page.
  - Expected hits from the scenarios: Turnover, Active Users, ATOPU, gross vs net product revenue, the seeded synonym pair. The false friend should *not* be flagged.

**How ML improves the organization (report argument):**
- It applies the controlled vocabulary to every definition, including each new submission, without hand-tagging, and that makes the Category and Business line facets possible.
- It catches data-quality errors (wrong units).
- It surfaces synonyms and conflicts that string matching misses, while avoiding string matching's false matches (*Inventory Amount* vs *Investment Amount*).

**Risk:** check early that `torch` / `sentence-transformers` install on Python 3.14. If they don't, pin the project to 3.13.

## 7. Personas

> Each persona is a **fixed seed user** from `scenarios.yaml` that the demo can "log in as". Pronouns are they/them throughout.

### P1: Emma Papadopoulos, Business Analyst, Finance (USR-005, **Observer** in Finance)
- **Context:** joined in October 2026. Builds the weekly finance flash report and is comfortable with spreadsheets and SQL.
- **Goals:** learn which KPIs Finance owns, what each one means, which table it comes from and which dashboards use it, without interrupting colleagues all the time.
- **Frustrations:** the board pack's ATOPU doesn't match the Product dashboard; "turnover" in Commercial's numbers isn't Finance's turnover; column names such as `inv_turn` are cryptic.
- **Uses:** UC1, UC2.

### P2: Katerina Okafor, Commercial Analytics Lead (USR-007, **Curator** in Commercial)
- **Context:** curates Commercial's definitions (e.g. Sales Revenue, Revenue, Gross Margin %, the inventory-turnover variants), personally owns several of them, and presents them to leadership.
- **Goals:** publish the division's definitions once and stop re-explaining them; keep them tagged and linked to the dashboards that use them; make sure other divisions read *Revenue* the way Commercial means it (excluding tax).
- **Frustrations:** definitions live in slide decks and dbt YAML; Finance and Product use the same words for different numbers; there is no record of who approved what.
- **Uses:** UC3, UC2 (and division-level tag validation in UC4).

### P3: Noah Garcia, Data Governance Lead (USR-053, **Admin**)
- **Context:** responsible for consistent reporting terminology across all 8 divisions.
- **Goals:** a single consistent catalog; a tidy controlled vocabulary; ML tags that can be trusted; conflicts and duplicates caught early; nothing published without review.
- **Frustrations:** every division invents new names for the same metric; community tags multiply (`north-star`, `northstar`, `North Star`); unit errors slip into reports.
- **Uses:** UC4.

**Supporting seed users (in the demo, no persona write-up):** Dimitris Jansen (USR-008, Commercial Controller, **Reviewer**) approves Katerina's submissions; Anna Okafor (USR-009, BI Developer, **Contributor** in Commercial) proposes definitions.

## 8. Use cases

| ID | Persona | Goal | Main flow (with scenario data) | Pages |
|---|---|---|---|---|
| **UC1 Onboard** | P1 (Observer) | Find and understand the KPIs that matter to my division | Log in as Emma → home shows "Finance KPIs" → facet Category: Financial → revenue → open a Finance KPI → read Finance's definition, unit, grain and source table, its lineage, its official and community tags, and "used in *Finance Weekly Flash Report*" | `/`, `/kpis`, `/kpis/<slug>` |
| **UC2 Clarify across divisions** | P1, P2 | Understand why a KPI's numbers differ between divisions | Search "turnover" → KPI *Turnover* lists the Finance, Commercial and Product definitions (and currencies) with a "definitions diverge" warning → open *ATOPU*: the lineage panel shows Finance's version divides Finance turnover by Product active users, while Product's divides Product turnover by Product active users | `/kpis?q=`, `/kpis/<slug>` |
| **UC3 Contribute** | P2 (Curator) + Reviewer | Publish my division's definition | Log in as Katerina → open the scenario draft → the form shows theme and business-line suggestions, the measure type from the unit, and "similar definitions already exist under …" → confirm the KPI and submit → log in as Dimitris (Reviewer) → approve, or request changes with a comment → the status and review history appear on the definition | `/definitions/<id>/edit`, `/my-definitions`, `/review` |
| **UC4 Govern** | P3 (Admin) | Keep the catalog consistent and trustworthy | Log in as Noah → check low-confidence "auto" tags → resolve similarity flags (merge / relate / dismiss) → fix the `unit_mismatch` flag on *Operating Expenses* → promote the community tag `north-star` (merging `northstar` and `North Star` into it) → export the updated TTL | `/curate/tags`, `/curate/community-tags`, `/governance/flags` |

**Success criteria (for the demo):** each use case runs end to end in the local site with the scenario data, and each step is visible in a screenshot for the report.

## 9. Features

**Priority:** MVP = required for the final deliverable · Stretch = only if time allows · Out = cut.

| ID | Feature | Priority | Use case | Course requirement | Owner |
|---|---|---|---|---|---|
| F0 | **Seed generation**: `kpigen`, curation files, `scenarios.yaml`, `schema.sql`, validation ([§3](#3-collection-and-generation-plan)) | MVP | all | dataset, data quality | A |
| F1 | Navbar + **"log in as" switcher** (seed users grouped by division; persona shortcuts); permissions checked through `user_roles` × `role_permissions` | MVP | all | website, interactions | B |
| F2 | **Browse with facets** from official tags and fields: Division, Category (2-level), Business line, Measure Type, Metric Type, Grain, Status; a **separate "Community tags" filter**; A–Z index | MVP | UC1 | formal + informal org | B |
| F3 | **Keyword search** (SQLite FTS5 over KPI names, labels, definition text, official and community tags) with **query expansion through SKOS altLabels**; each result shows why it matched (e.g. "matched community tag #board-pack") | MVP | UC2 | vocabulary integration | B + A |
| F4 | **KPI page**: every visible definition, grouped by division (label, text, formula, unit/currency, grain, source table/column, owner, status). **Official tags** as solid chips grouped by facet, linked to concept pages, ML ones marked **"auto"** with the confidence on hover. **Community tags** in a separate row ("unofficial, not reviewed") as outlined `#tag` chips with a count | MVP | UC1, UC2 | formal vs informal, made visible | B |
| F5 | **Divergence panel**: "definitions diverge" warnings + "similar KPIs" | MVP | UC2 | ML | B + A |
| F6 | **Lineage panel** (read-only `kpi_relationships`: numerator/denominator/input, subset, cumulative) | MVP | UC2 | formal org (relationships) | B |
| F7 | **"Used in" panel** (read-only dashboards) + **version chain** (`superseded_by`) + **review history** | MVP | UC1, UC3 | website | B |
| F8 | **Vocabulary browser**: schemes → concept pages (definition, broader/narrower/related, tagged definitions) | MVP | UC1, UC4 | formal org, standards | B |
| F9 | **Batch ML**: T1 theme + T2 business-line tagging, T3 unit check, similarity flags; evaluation script | MVP | — | ML | A |
| F10 | **Definition editor + submit** (draft → in_review) with ML suggestions and a similar-KPI warning | MVP | UC3 | ML integration, contributor role | B + A |
| F11 | **My definitions** (own drafts, in-review, rejected, with review comments) | MVP | UC3 | contributor role | B |
| F12 | **Review queue** (approve / reject / request changes + comment) for Reviewers in their division | MVP | UC3 | reviewer role, governance | B |
| F13 | **ML tag validation queue** ("auto" tags, lowest confidence first; accept / change / reject) for Curators (own division) and Admin (all) | MVP | UC4 | ML + human in the loop | B |
| F14 | **Community tags**: any user adds free tags to a definition; tag cloud on browse | MVP | UC1 | informal org | B |
| F15 | **Community-tag promotion** to an altLabel or new concept, merging variants; **Export TTL** | MVP | UC4 | informal ↔ formal integration | B + A |
| F16 | **Governance flags page** (possible synonyms, diverging definitions, unit mismatches; merge / relate / dismiss / fixed) | MVP | UC4 | ML | B + A |
| F17 | **Downloads**: SKOS TTL, annotated dataset | MVP | — | deliverables | A |
| F18 | **About page**: problem, personas, use cases, method, site map | MVP | — | report ↔ website | W + B |
| S1 | Small OWL schema for KPI / Definition / Division / lineage | Stretch | — | standards | A |
| S2 | Semantic search using the stored embeddings | Stretch | UC2 | ML | A |
| S3 | Comments on definitions (adds a `comments` table) | Stretch | UC2 | social org | B |
| S4 | Dashboard page listing all definitions it uses | Stretch | UC1 | website | B |
| S5 | Inter-annotator agreement (Cohen's κ) on the gold set | Stretch | — | data quality | A + W |
| — | Admin management UI · editing relationships/dashboard links · version diffs · real auth · hosting · LLM-written content | Out | — | — | — |

## 10. Site map and permissions

```
/                          Home: search, "KPIs of <your divisions>", facet entry points, log-in-as switcher
├── /kpis                  Browse & search: facets, community-tag filter, A–Z, tag cloud
│   └── /kpis/<slug>       KPI page: definitions by division, divergence, lineage, used-in, versions, tags
├── /definitions/<id>/edit [definition.propose / definition.edit] Editor with ML suggestions; submit for review
├── /my-definitions        [definition.propose] Own drafts / in-review / rejected + review comments
├── /review                [definition.approve] Review queue for the reviewer's divisions
├── /vocabulary            Concept schemes
│   └── /vocabulary/<id>   Concept page: broader/narrower/related, tagged definitions
├── /curate/tags           [tag.manage] "Auto" tag validation (own division; Admin sees all)
├── /curate/community-tags [tag.manage] Community tags by frequency → merge / promote
├── /governance/flags      [governance.manage] Synonyms, divergences, unit mismatches; TTL export
├── /downloads             SKOS TTL, annotated dataset
└── /about                 Problem, personas, use cases, methodology
```

| Capability | Observer | Contributor | Curator | Reviewer | Admin |
|---|:-:|:-:|:-:|:-:|:-:|
| Read approved + deprecated definitions (all divisions), vocabulary, downloads | ✅ | ✅ | ✅ | ✅ | ✅ |
| Add community tags | ✅ | ✅ | ✅ | ✅ | ✅ |
| See drafts / in-review / rejected | — | division | division | division | all |
| Propose and submit definitions | — | division | division | — | all |
| Edit / deprecate approved definitions | — | — | division | — | all |
| Approve / reject / request changes | — | — | — | division | all |
| Validate "auto" tags, promote community tags | — | — | division | — | all |
| Governance flags, TTL export | — | — | — | — | ✅ |

"Division" means: in the divisions where the user holds that role (`user_roles.division_id`). Users can hold roles in more than one division. The home page uses `home_division_id`.

## 11. Architecture and repo layout

**Stack:** Python 3.14 (uv) · Flask + Jinja templates · SQLite (FTS5, verified available) · rdflib · sentence-transformers · scikit-learn (metrics only) · pandas · pytest. Minimal CSS (a classless or small framework; no JS build step).

```
data/raw (pinned downloads) + kpigen/curation + scenarios.yaml ──► kpigen ──► data/seed/*.csv
data/seed ──► validate (schema.sql + pytest) ──► load (+ official tags from SKOS, measure type) ──► instance/catalog.sqlite
catalog.sqlite ──► ml tag / unit check / similarity ──► definition_tags (source=ml), similarity_flags
data/gold/*.csv ──► ml evaluate ──► reports/ml_eval.md
catalog.sqlite ──► Flask app ──► export ──► data/annotated/, vocab/kpi-vocabulary.export.ttl
```

**Planned layout**
```
schema.sql                  the single schema definition (generator validation + app database)
kpigen/                     hand-edited generator inputs
  curation/                 domain_to_division.csv, kpis.csv, row_to_kpi.csv, exclusions.csv, relationships.csv
  scenarios.yaml            fixtures + hand-written conflict cases
data/raw/                   pinned source downloads (git-ignored)
data/seed/                  generator output; never edited by hand
data/{gold,annotated}/      gold labels; exported annotated dataset
vocab/                      hand-authored SKOS seed + generated exports
src/kpigen/                 seed generator: download, inputs + coverage check, generate, write, validate
src/kpi_catalog/
  db.py                     create from schema.sql + load seed CSVs
  vocab/skos.py             load / query / export SKOS; unit → measure type; official tags
  ml/tagger.py              T1/T2 tagging, T3 unit check, submit suggestions
  ml/similarity.py          synonym / divergence flags
  ml/evaluate.py            gold-set metrics vs baselines
  auth.py                   log-in-as + permission check
  web/                      Flask app factory, routes, templates/, static/
tests/test_seed_rules.py    business-rule checks (§3.6)
tests/test_kpigen.py        generator tests (determinism, coverage, validation catches errors)
docs/PRD.md
```

**Commands:** `uv run kpigen download` (pinned sources) · `uv run kpigen` (generate + validate seed) · `uv run kpi-catalog build` (load → tag → flag; reuses the existing `kpi-catalog` script entry point) · `uv run flask --app kpi_catalog.web run --debug`.

## 12. Milestones

| Dates | Milestone | A (data/ML) | B (web) | W (writer) |
|---|---|---|---|---|
| **4–19 Nov** | **Mid-term** | Write kpigen, `schema.sql`, curation files and `scenarios.yaml` until validation passes; quality log; vocab v0; first tagging run | Flask skeleton, DB loader, log-in-as, base layout, site map (can start on the generated seed; texts are placeholders until D4/D5 are reviewed) | Mid-term description ([checklist](#mid-term-checklist-19-nov)), persona drafts, case-study draft |
| 20 Nov–3 Dec | Core catalog | SKOS v1, gold set + evaluation, unit check | Browse, facets, search, KPI page (tags, divergence, lineage, used-in, versions), vocabulary pages | Report skeleton in the ACM Overleaf template; collection + data-quality sections |
| 4–12 Dec | Workflows | Suggestions API, similarity flags, TTL export | Editor + submit, review queue, tag validation, community tags + promotion, governance flags | Use-case write-ups, ML section; **12 Dec: OWL go/no-go** |
| 13–17 Dec | Polish | Final metrics, annotated export | UX polish, scripted demo path per persona | Screenshots, site-map figure, reflection section |
| 18–21 Dec | Ship | — | Demo rehearsal | Final report, presentation, contribution statement |

### Cut order if we fall behind
1. Drop all Stretch items (S1–S5).
2. F16 governance page → keep only the warnings on the KPI page (F5) and on submit.
3. F13 tag validation → accept/reject buttons on the KPI page instead of a separate queue.
4. F15 promotion → curator promotes by editing the TTL by hand; the page only lists community tags by frequency.
5. F7 → keep "used in"; drop the version chain and review history.

**Never cut:** real-content seed with validation, the SKOS file, the annotated dataset, auto-tagging + evaluation, facets + search, community tags shown apart from official tags, log-in-as with per-role views, the submit → review flow, the site map.

## 13. Requirements traceability

| Course requirement (`group_project_description.md`) | Where it is covered | Owner |
|---|---|---|
| **Website** | F1–F18, [§10](#10-site-map-and-permissions) | B |
| **Annotated dataset** | `data/annotated/` ([§4.5](#45-definition-lifecycle-and-visibility)) | A |
| **Ontology / controlled vocabulary in a standard format** | `vocab/kpi-vocabulary.ttl`, SKOS ([§5](#5-controlled-vocabulary-skos)) | A |
| **Final presentation** | Live demo of UC1–UC4 + slides | W + all |
| Report: dataset description + data-quality reflection | [§3](#3-collection-and-generation-plan): sources, company-profile rule, exclusions, real vs synthetic, findings S1–S6, lessons from the sample; `data/quality_log.md` | W + A |
| Report: 6-question case study | Sketch below | W |
| Report: use cases + personas (≥3) | [§7](#7-personas), [§8](#8-use-cases) | W |
| Report: controlled vocabulary / ontology | [§5](#5-controlled-vocabulary-skos) | W + A |
| Report: ML approach + how it improves organization | [§6](#6-ml-approach), `reports/ml_eval.md` | W + A |
| Report: site map | [§10](#10-site-map-and-permissions) | W + B |
| Report: challenges + class concepts | Curation decisions, SKOS limitations, ML vs baselines, official vs community tags, permissions vs transparency | W |
| Report: individual contribution statement | Last section of the report | all |
| Informal **and** formal organization | Community tags + A–Z (informal); SKOS facets, hierarchy, lineage (formal); shown separately in the UI | A + B |
| "Simple ML to auto-tag according to the vocabulary" | F9, tags point to SKOS concept URIs | A |
| "Show how the website enables the intended interactions" | UC1–UC4 demo + screenshots | B + W |

### 6-question case study (sketch for the report)
*Check the exact question wording against the course template.*
- **What is being organized?** About 105 definitions of roughly 50 KPIs owned by 8 divisions of a retail group, plus their lineage, the dashboards that use them and their review history. These are descriptions of data, not the data itself.
- **Why is it being organized?** To reduce onboarding effort, prevent cross-division misinterpretation, and give governance one reviewed source of truth. Supported interactions: find, compare, contribute, review, curate.
- **How much is it being organized?** Per definition: label, text, formula, unit, grain, source, owner, status, version, Category, Business line, Measure Type, Metric Type, official and community tags. Per KPI: preferred/alternative labels and lineage. Six concept schemes, two of them hierarchical.
- **When is it being organized?** Up front, when the seed is curated (mapping files) and tagged (batch ML). At writing time (ML suggestions) and at review time (reviewer). Continuously through community tags, with the vocabulary evolving through promotion.
- **How / by whom?** A hybrid: source authors (HF, dbt); our curation (mapping files); contributors and curators (domain experts); reviewers (managers); the governance lead (professional); the ML tagger (computational); all users (social tagging).
- **Where?** In a web application backed by SQLite and a SKOS vocabulary file. Organizing principles: facets, hierarchy, synonym control, typed relations, alphabetical order, keyword relevance, and access by role.

### Mid-term checklist (19 Nov)
| Mid-term question | Answer from |
|---|---|
| What dataset have you chosen? Present and describe it. | [§3](#3-collection-and-generation-plan): sources, company profile, real vs synthetic, generation plan |
| What is the main problem and who are the users? | [§1](#1-overview-and-problem), [§7](#7-personas) |
| What kind of website; how is information presented; which interactions? | [§8](#8-use-cases), [§9](#9-features), [§10](#10-site-map-and-permissions) |
| What will the ontology look like; which existing vocabularies can you use? | [§5](#5-controlled-vocabulary-skos): SKOS, Balanced Scorecard, NAICS, dbt Semantic Layer metric types, Dublin Core; KPIOnto as related work |
| What kind of ML; how will you use its results? | [§6](#6-ml-approach) |
| Current status | Fill in at submission time; target by 19 Nov = the "Mid-term" row in [§12](#12-milestones) |

## 14. Open questions
1. **Company name:** keep "Acme" or choose another?
2. **Theme *quality*:** with the defect rates excluded, add one hand-written quality KPI (e.g. a food-safety incident rate), or leave the theme empty?
3. **Thresholds:** `τ_min`, `τ_high`, `τ_low`, tuned on the gold set.
4. **NAICS codes:** check every Business line code against NAICS 2022.
5. **OWL (S1):** go/no-go on 12 Dec.
6. **Team split:** resolved 5 Nov (see the header; George owns `kpigen`). Still open: who makes the slides and leads the demo (task P4).

## 15. Change log

Every change to a feature or decision gets a row here, with the PRD sections it touched (the rule is in `CLAUDE.md`).

| Date | Version | Change | Sections |
|---|---|---|---|
| 4 Nov 2026 | v1 | First PRD: Hugging Face dataset framed as a conglomerate; SKOS vocabulary; embedding-similarity ML (category + measure type); 3 personas, 4 use cases; Flask + SQLite; local demo | all |
| 4 Nov 2026 | v2 | Schema aligned with the sample catalog: 8 divisions, 5 division-scoped roles, lineage, dashboards, reviews, versions; ML tags theme + industry; measure type from `unit`; approved definitions readable by everyone; personas became seed users | §1, §3–§10 |
| 5 Nov 2026 | v2 | Added the plain-language "What SKOS can't express" subsection and the "At a glance" summary | §5, top |
| 5 Nov 2026 | v3 | Dataset to be generated by a reworked, deterministic `kpigen` from real KPI text plus hand-written conflict cases; retail-group company profile with exclusion rule; Business line replaces Industry; `schema.sql` as the single schema; fixed IDs; official vs community tags shown separately; ML tags marked "auto" | top, §1–§6, §9–§14 |
| 5 Nov 2026 | v3 | Rule added: every feature change is recorded in PRD, CLAUDE.md and README.md where it belongs; this change log added | §15 |
| 5 Nov 2026 | v3 | Team split recorded (George = A; Liam = B + report; Ioanna = personas, user journeys, UI wireframes); task tracker `docs/TASKS.md` added | header, §14 |
| 5 Nov 2026 | v4 | No earlier `kpigen` existed: written from scratch (`src/kpigen/`, `kpigen download` with pinned hashes); `schema.sql` written; new curation file `relationships.csv`; GenAI drafts curation decisions but free text stays `TODO(george)`; several definitions per KPI × division allowed; 2 municipality rows (not 1) excluded → 82 HF, 105 definitions of 60 KPIs | header, top, §3.3, §3.4, §4.2, §11, §12 |
