# Data-quality log

Every data-quality finding and decision about the KPI Catalog dataset, with examples and where each decision is implemented. It feeds the report's dataset and data-quality section (tasks R1, R3). PRD §3.7 has the summary; this file has the details.

**How to use it**
- One entry per item, with a permanent ID: **S** = finding in the real sources, **E** = exclusion reason, **Q** = error or case seeded on purpose, **C** = our own data decision, **L** = lesson from the sample catalog. New entries take the next free ID; never renumber.
- Row references: `hf:N` is row N (0-based) of the HF file; `dbt:<name>` is a dbt metric; `DEF-…` and `KPI-…` are seed IDs.
- Update an entry when its decision changes; don't add a contradicting one. Unit mismatches found by the ML unit check (task M4) go under Q or C.

## 1. Sources

| Source | Version | Retrieved | Integrity |
|---|---|---|---|
| Hugging Face `kavish218/multi_domain_dataset`, `testcontext_file1.csv` (107 rows; columns `columnname`, `businessterm`, `description`, `domain`, `tablename`, `other columns for context`) | revision `c148c8c` | 5 Nov 2026 | SHA-256 pinned in `kpigen download` |
| dbt Labs `jaffle-sl-template`: `orders.yml`, `order_items.yml`, `customers.yml` (17 metrics) | commit `c54c8fb` | 5 Nov 2026 | SHA-256 pinned in `kpigen download` |

Neither source declares a licence, so both are downloaded into the git-ignored `data/raw/` and never committed (PRD §3.2). Full URLs and hashes: `data/raw/SOURCES.md` (written by `kpigen download`).

**Result:** 107 HF rows + 17 dbt metrics → 25 HF rows and 2 dbt metrics excluded (§3) → 82 HF + 15 dbt + 11 hand-written = **108 definitions of 62 KPIs**.

## 2. Findings in the real sources

### S1 · The HF `domain` mixes industries, business functions and sectors no single company spans
- **Found:** 20 domain values. Some are industries (`in retail`, `in telecommunications`, `in insurance`), some are business functions (`in finance`, `in accounting`, `in human resources`, `in marketing`), and some are sectors a retail group doesn't have (`in Education` 10 rows, `in healthcare` 6, `in personal finance` 2, `in public sector` 2).
- **Decision:** split the domain into two dimensions: the **division** that owns the definition and the **business line** it applies to. Functions map to `GroupWide` (e.g. `in finance` → FIN, GroupWide); industries map to a business line (`in retail` → COM, Stores). Sectors that don't fit the company are excluded (E3–E5).
- **Implemented in:** `kpigen/curation/domain_to_division.csv` (also the gold labels for ML task T2); `exclusions.csv`.

### S2 · Synonym label variants for the same measure
- **Found:** inventory turnover appears under 6 labels in 8 rows and two column names (`inv_turnover` in hf:22, 23, 38, 39, 53; `inv_turn` in hf:85, 86, 87): *Inventory Turnover*, *Inventory Turnover Ratio*, *Inventory Turnover Rate*, *Inventory Stock Turnover*, *Stock Turnover Rate*, *Product Turnover Ratio*. The quick ratio has 3 labels in 5 rows (hf:10, 11, 26, 27, 55): *Quick Ratio*, *Quick Assets Ratio*, *Quick Assets to Liabilities Ratio*.
- **Decision:** one KPI each (KPI-0018, KPI-0010). Each row keeps its label as the division's `display_name`; the labels become SKOS altLabels of the KPI in the KPI Glossary (task V4), so search for "stock turnover rate" finds Inventory Turnover.
- **Implemented in:** `row_to_kpi.csv`.

### S3 · A shared column name doesn't mean the same measure
- **Found:** three columns each hold three different measures:
  - `cust_fb`: *Customer Satisfaction Score* (hf:88), *Net Promoter Score (NPS)* (hf:89), *Customer Experience Rating* (hf:90);
  - `op_eff`: *Operational Efficiency Ratio* (hf:91), *Resource Utilization Rate* (hf:92), *Productivity Rate* (hf:93);
  - `emp_sat`: *Employee Satisfaction Index* (hf:82), *Employee Engagement Score* (hf:83), *Staff Wellbeing Index* (hf:84).
  The same happens with labels: *Accounts Payable Due* in hf:15 means internal amounts owed to departments, not money owed to suppliers.
- **Decision:** separate KPIs, linked pairwise as `related_to`, so the KPI page shows that they share a source column. Two more shared columns are not synonyms either: `mkt_spend` (the digital budget and advertising spend are `subset_of` total marketing expenditure) and `ship_cost` (shipping expenses vs freight costs vs delivery charges, which are a fee charged to customers, not a cost).
- **Implemented in:** `row_to_kpi.csv` (separate KPIs), `relationships.csv`.

### S4 · Homonymous abbreviation `inv_amt`
- **Found:** `inv_amt` stands for three unrelated measures: *Investment Amount* (hf:12, 29), *Invoice Amount* (hf:13) and *Inventory Amount* (hf:28, 43; hf:42 is a hospital row, excluded under E3).
- **Decision:** three separate KPIs (KPI-0011, KPI-0012, KPI-0013). *Inventory Amount* vs *Investment Amount* is the "false friend" the ML must not flag as a synonym (PRD §6, Q4 below).
- **Implemented in:** `row_to_kpi.csv`.

### S5 · No units, typos and defects in columns, short descriptions
- **Found:**
  - The HF file has no unit or grain for any row.
  - Column typo `ales_rev` for `sales_rev` (hf:58).
  - Defects in `other columns for context`: `out_of_stock items` with a space (hf:39), and an empty fragment `project_` (hf:9).
  - Descriptions are short: 40–115 characters, median 82.
  - One domain value has a double space (`in  finance`, 1 row).
- **Decision:** units and grain assigned by hand per row (C1). Typos in identifiers fixed through the `fix` column of the mapping (C2); hf:9's empty fragment is noted, not invented. Domains are whitespace-normalized when read. The short texts are a reason to use pretrained sentence embeddings rather than train a classifier (PRD §6).
- **Implemented in:** `row_to_kpi.csv` (`unit`, `grain`, `fix`, `note`); `src/kpigen/inputs.py` (`norm_domain`).

### S6 · Typos and template-only metrics in the dbt source
- **Found:** typos in metric descriptions: "Distict" (`customers_with_orders`), "amonunt" (`order_total`), "Excluded tax" for "Excludes tax" (`revenue_growth_mom`), "colaescing" (`orders_fill_nulls_with_zero`). Two metrics only demonstrate a dbt feature (E7). One label is lower case (`orders last 7 days`).
- **Decision:** typos in kept metrics fixed through the `fix` column (C2): DEF-0216, DEF-0201, DEF-0213; the label fixed to *Orders Last 7 Days* (DEF-0207). "colaescing" is in an excluded metric, so it isn't fixed.
- **Implemented in:** `row_to_kpi.csv` (`fix`), `exclusions.csv`.

## 3. Exclusions

All 27 excluded rows are in `kpigen/curation/exclusions.csv` and are copied to `data/seed/excluded.csv`. Counts match PRD §3.3.

| ID | Reason | Rows | Count |
|---|---|---|---|
| E1 | Not a quantitative measure: education identifier (*Student Identifier*, *College ID*, …) | hf:97–106 | 10 |
| E2 | Not a quantitative measure: a due date (*Accounts Payable Due Date*) | hf:31, 45 | 2 |
| E3 | Doesn't fit the company profile: hospital (patients, medical supplies, healthcare facility) | hf:42, 44, 46, 51, 52, 54 | 6 |
| E4 | Doesn't fit the company profile: household tax (personal finance) | hf:19, 35 | 2 |
| E5 | Doesn't fit the company profile: municipality infrastructure spending | hf:25, 41 | 2 |
| E6 | Doesn't fit the company profile: car, electronics and pharmaceutical defect rates | hf:73, 74, 75 | 3 |
| E7 | dbt template example, not a business KPI (*Orders (Fill nulls with 0)*, *Twice Orders*) | dbt:orders_fill_nulls_with_zero, dbt:twice_orders_fill_nulls_with_0 | 2 |

**Rule (company profile):** Konfusio is a retail group with 8 divisions and the business lines in the vocabulary (stores, online, food-to-go, membership, banking, insurance, mobile, property, own-brand production). A row is kept only if a retail group of this kind could own it. E3–E6 fail this rule; E1–E2 fail because they aren't measures at all.

**Side effect:** E6 removed the only examples of the Category theme *quality*, which led to C4.

## 4. Errors and cases seeded on purpose

These are in the seed deliberately, for the use cases and the ML evaluation. The report must not present them as findings in the sources.

| ID | What | Where | Expected outcome |
|---|---|---|---|
| Q1 | ***Operating Expenses* stored with unit `score`** (should be EUR) | DEF-0007 (hf:6), `row_to_kpi.csv` note | The ML unit check (T3, task M4) raises a `unit_mismatch` flag; Noah fixes the unit in UC4 (task W17) |
| Q2 | Real synonym pair kept under two KPIs: *Product Revenue* and *Total Product Sales* | hf:5 (DEF-0006), hf:79 (DEF-0080) | ML raises `possible_synonym`; Noah resolves it in UC4 (merge, relate or dismiss) |
| Q3 | Supersession: Finance *Capital Expenditure* v1 replaced by v2 (same text reworded, source table renamed) | hf:24 (DEF-0025) → hf:40 (DEF-0041), `scenarios.yaml` | Version chain shown on the KPI page; links moved to v2 (C5); ML skips v1 (C6) |
| Q4 | False friend: *Inventory Amount* vs *Investment Amount* (both `inv_amt`, S4) | KPI-0013, KPI-0011 | ML does **not** flag them as synonyms |
| Q5 | Conflict cases: Turnover, Active Users, ATOPU and Gross Margin % defined differently per division (hand-written; Gross Margin %: Finance full cost after rebates, DEF-0309, vs Commercial front margin, DEF-0311), plus gross vs net product revenue (real rows, DEF-0081/DEF-0082, linked `related_to`) | `scenarios.yaml`, `relationships.csv` | ML raises `definitions_diverge` for the same-KPI conflicts; shown on the KPI page (UC2) |

## 5. Our own data decisions

| ID | Decision | Reason | Where |
|---|---|---|---|
| C1 | **Units and grain assigned by hand** for every row. Result: EUR 51, count 14, % 10, times 9, USD 8, ratio 7, score 7 | The HF source has none (S5); the dbt YAML has no units | `row_to_kpi.csv` (`unit`, `grain`) |
| C2 | **Typos fixed only through the `fix` column**, as `field:old=>new`; all other source text is kept word for word, and no LLM writes or alters source KPI text | Keeps every change to real text visible and reversible | `row_to_kpi.csv` (`fix`); CLAUDE.md conventions |
| C3 | **Text we supplied ourselves was drafted with GenAI and labelled so:** KPI descriptions, conflict-case texts and formulas, Katerina's draft, the quality KPI, 35 community-tag labels, and the SKOS concept labels, definitions and scope notes. The 11 GenAI-drafted definitions are reported separately in the ML evaluation | Waived by George, 5 Nov; the evaluation must not score the model on LLM-written text | PRD §3.5 |
| C4 | **One hand-written quality KPI added:** *Food Safety Incident Rate* (Operations, `%`, DEF-0308, KPI-0061) | E6 left the theme *quality* empty; an empty concept would be a T1 candidate no gold label can match (P3) | `scenarios.yaml`; PRD §14 Q2 |
| C5 | **Links move off a superseded definition:** dashboard links, lineage and community tags point at the successor; the old version keeps its review history | A deprecated definition must not keep feeding dashboards or other definitions; every dashboard that would use DEF-0025 uses DEF-0041 | `kpigen` generator, `tests/test_seed_rules.py`; PRD §4.5 |
| C6 | **ML skips deprecated definitions** (T1–T3, similarity flags) and leaves them out of the gold set and evaluation (M10) | Same reason as C5; the near-identical text would count twice | PRD §6, §14 Q8 |
| C7 | **Several definitions per KPI and division are allowed**, told apart by `source_table` | Divisions keep variants of the same KPI from different source tables (e.g. Commercial has 6 inventory-turnover definitions, S2) | `schema.sql`; PRD §4.2 |
| C8 | **Business lines link to NAICS 2022 with `closeMatch`, not `exactMatch`;** Online gets only a `broadMatch` and Membership no match | NAICS 2022 removed the nonstore industries (old 454110) and classifies retailers by merchandise line, so a grocer's web shop falls under 445110; a paid retail membership isn't an industry. All codes checked 12 Nov against the Census Bureau's NAICS 2022 code list, concordance and manual (task V2); none changed. Insurance = direct carrier 524126 (Konfusio underwrites), Mobile = reseller 517121 (MVNO) | `vocab/kpi-vocabulary.ttl`; PRD §5, §14 Q4 |

## 6. Lessons from the sample catalog

The earlier sample catalog was inspiration only (PRD §3). Its problems are why the rules above exist.

| ID | Problem in the sample | Rule it led to |
|---|---|---|
| L1 | Its generator *guessed* groupings, units and divisions | Those decisions are hand-edited curation files (`kpigen/curation/`), reviewed before use |
| L2 | Its tags were generator output that would quietly have become "truth" | No theme or business-line tags in the seed (`test_no_theme_or_business_line_tags_in_the_seed`); gold labels are kept separate in `data/gold/` |
| L3 | It superseded definitions across different meanings (Portfolio Equity → Total Equity), had review comments that didn't fit, linked dashboards across divisions and repeated dashboard names | The business rules in `tests/test_seed_rules.py` (PRD §3.6) |
| L4 | Its tag categories were muddled: functions filed as industries, a duplicate `supply-chain`, `north-star` as a theme | Official tags come only from the SKOS vocabulary; Division and Business line are separate facets (S1); `north-star` is a community tag |
| L5 | Its KPI descriptions were copied from one division's definition | `kpis.csv` holds division-neutral descriptions |
