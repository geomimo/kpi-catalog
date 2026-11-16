# User journeys (UC1–UC4)

Task **U2** in [TASKS.md](TASKS.md) · owner: Ioanna · source: [PRD §7–8](PRD.md#8-use-cases), site map [§10](PRD.md#10-site-map-and-permissions)

Each journey follows one persona through the site, step by step. Liam builds the pages from it (W4–W17), George adds any missing seed data from it (D10), and the demo script (U7) and report screenshots (U8) follow it.

## How to fill this in
- **One row per step**: one page and one thing the user does there.
- **Page**: a route from the §10 site map (e.g. `/kpis/turnover`). If a step needs a page that isn't in the site map, mark it **NEW** and tell Liam.
- **Action**: what the user clicks, types or chooses.
- **What the user sees**: the content that makes the step work (a warning, a list, a tag chip, a count). Be concrete, because Liam builds this and the screenshot shows it.
- **Seed data**: the IDs the step depends on (`DEF-…`, `KPI-…`, `USR-…`, `AST-…`, tag labels). The IDs filled in below are already in the seed (`kpigen/scenarios.yaml`). Write **MISSING: …** for anything that isn't there yet. George adds it in D10.
- **Gaps**: anything the step needs that no page or seed provides yet.
- Persona prose uses they/them.
- Rows marked `TODO(ioanna)` still need your input. The steps follow the PRD §8 main flow; add, split or reorder steps if the journey needs it.

---

## UC1 · Onboard

| | |
|---|---|
| **Persona** | Emma Papadopoulos (USR-005), Business Analyst, **Observer** in Finance |
| **Goal** | Find and understand the KPIs that matter to Finance |
| **Starting point** | TODO(ioanna): e.g. their first week, a colleague sent them the link |
| **Ends when** | TODO(ioanna): e.g. Emma knows what a Finance KPI means, where it comes from and which report uses it |

| # | Page | Action | What the user sees | Seed data |
|---|---|---|---|---|
| 1 | `/` | Logs in as Emma (account icon → switcher) | TODO(ioanna) | USR-005, home division FIN |
| 2 | `/` | Looks at "Finance KPIs" | TODO(ioanna) | Approved Finance definitions, e.g. DEF-0001, DEF-0005, DEF-0009 |
| 3 | `/kpis` | Picks facet Category: Financial → revenue | TODO(ioanna) | Official tags from the ML batch (`kpi-catalog build`) |
| 4 | `/kpis/<slug>` | Opens a Finance KPI | TODO(ioanna) | TODO(ioanna): which KPI? e.g. Total Revenue (DEF-0005) |
| 5 | `/definitions/<id>` | Reads Finance's definition, unit, grain and source table | TODO(ioanna) | TODO(ioanna) |
| 6 | `/definitions/<id>?tab=dependencies` | Checks the lineage | TODO(ioanna) | TODO(ioanna): does the chosen KPI have lineage? |
| 7 | `/definitions/<id>` | Reads the official and community tags | TODO(ioanna) | e.g. `board-pack` on DEF-0005 |
| 8 | `/definitions/<id>?tab=usage` | Sees "used in Finance Weekly Flash Report" | TODO(ioanna) | AST-001 (DEF-0001, 0005, 0007, 0009, 0301, 0307) |

**Gaps:** TODO(ioanna)

---

## UC2 · Clarify across divisions

| | |
|---|---|
| **Persona** | Emma (USR-005, Observer, Finance); Katerina (USR-007, Curator, Commercial) as needed |
| **Goal** | Understand why a KPI's numbers differ between divisions |
| **Starting point** | TODO(ioanna): e.g. the board pack's ATOPU doesn't match the Product dashboard |
| **Ends when** | TODO(ioanna) |

| # | Page | Action | What the user sees | Seed data |
|---|---|---|---|---|
| 1 | `/kpis?q=turnover` | Searches "turnover" | TODO(ioanna) | KPI-0058 Turnover |
| 2 | `/kpis/turnover` | Opens Turnover | Finance, Commercial and Product definitions with their currencies, and a "definitions diverge" warning | DEF-0301 (FIN, EUR), DEF-0302 (COM, USD), DEF-0303 (PRD, EUR); diverge flag from M7 |
| 3 | `/kpis/turnover/compare` | TODO(ioanna): compares them side by side? | TODO(ioanna) | DEF-0301, DEF-0302, DEF-0303 |
| 4 | `/kpis/atopu` | Opens ATOPU | TODO(ioanna) | KPI-0060: DEF-0306 (PRD), DEF-0307 (FIN) |
| 5 | `/definitions/DEF-0307?tab=dependencies` | Reads the lineage | Finance's ATOPU divides Finance turnover by Product active users | DEF-0307 → DEF-0301 (numerator), DEF-0304 (denominator) |
| 6 | `/definitions/DEF-0306?tab=dependencies` | Compares with Product's version | Product's ATOPU divides Product turnover by Product active users | DEF-0306 → DEF-0303, DEF-0304 |

**Gaps:** TODO(ioanna)

---

## UC3 · Contribute

| | |
|---|---|
| **Persona** | Katerina Okafor (USR-007), **Curator** in Commercial; reviewer: Noah Garcia (USR-053, Admin) |
| **Goal** | Publish Commercial's definition of stock turn |
| **Starting point** | TODO(ioanna): e.g. Katerina saved a draft last week |
| **Ends when** | The definition is approved (or sent back) and the review history shows it |

| # | Page | Action | What the user sees | Seed data |
|---|---|---|---|---|
| 1 | `/` | Logs in as Katerina | TODO(ioanna) | USR-007 |
| 2 | `/my-definitions` | Opens their drafts | TODO(ioanna) | DEF-0310 "Stock Turn Ratio" (draft, owner USR-007) |
| 3 | `/definitions/DEF-0310/edit` | Opens the draft | Theme and business-line suggestions, the measure type from the unit (`times`), "similar definitions already exist under …" | DEF-0310 → KPI-0018 Inventory Turnover; similar: DEF-0087 Stock Turnover Rate (in review); suggestions from M8 |
| 4 | `/definitions/DEF-0310/edit` | Confirms the KPI and submits | TODO(ioanna) | — |
| 5 | `/` | Logs in as Noah | TODO(ioanna) | USR-053 |
| 6 | `/review` | Opens the review queue | TODO(ioanna) | DEF-0310 plus DEF-0087, DEF-0090, DEF-0210 (in review) |
| 7 | `/review` | Approves, or requests changes with a comment | TODO(ioanna) | — |
| 8 | `/definitions/DEF-0310?tab=history` | Checks the result | Status and review history | — |

**Gaps:** TODO(ioanna)

---

## UC4 · Govern

| | |
|---|---|
| **Persona** | Noah Garcia (USR-053), Data Governance Lead, **Admin** |
| **Goal** | Keep the catalog consistent and trustworthy |
| **Starting point** | TODO(ioanna): e.g. their weekly governance round |
| **Ends when** | The updated vocabulary is exported as TTL |

| # | Page | Action | What the user sees | Seed data |
|---|---|---|---|---|
| 1 | `/` | Logs in as Noah | TODO(ioanna) | USR-053 |
| 2 | `/curate/tags` | Checks low-confidence "auto" tags, lowest first | TODO(ioanna) | ML tags from `kpi-catalog build` |
| 3 | `/governance/flags` | Resolves similarity flags (merge / relate / dismiss) | TODO(ioanna) | Synonyms DEF-0006 Product Revenue / DEF-0080 Total Product Sales; false friend DEF-0029 / DEF-0030 (should **not** be flagged); flags from M7 |
| 4 | `/governance/flags` | Fixes the `unit_mismatch` on Operating Expenses | TODO(ioanna) | DEF-0007 (unit `score` on purpose), flagged by M4 |
| 5 | `/curate/community-tags` | Merges `northstar` and `North Star` into `north-star` and promotes it | TODO(ioanna) | `north-star` on DEF-0301, 0304, 0306; `northstar` on DEF-0307; `North Star` on DEF-0305 |
| 6 | `/governance/flags` | Exports the updated TTL | TODO(ioanna) | — (V6) |

**Gaps:** TODO(ioanna)
