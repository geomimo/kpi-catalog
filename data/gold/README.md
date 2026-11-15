# Gold labels (task M3)

The answer key the ML tagger is scored against (PRD §6, task M5). **Every label here is made by a person.**
No LLM, no tagger output and no other tool may suggest or check a label: the model would be graded against
its own kind of answers (PRD §3.5).

| File | What it is | Made by |
|---|---|---|
| `themes.csv` | The 11 themes you can choose from, with their perspective, SKOS definition and scope note | `prepare`, from `vocab/kpi-vocabulary.ttl` |
| `t1_sample.csv` | The 40 definitions to label: 40 of the 57 eligible KPIs at random (seed 42), one definition each | `prepare` |
| `t1_annotator_a.csv` | Annotator A's labels: **George** | A, by hand |
| `t1_annotator_b.csv` | Annotator B's labels: **TBD** | B, by hand |
| `t1_gold.csv` | Both annotators' labels side by side and the agreed T1 gold label | `compare`, then both annotators for the disagreements |
| `t2_gold.csv` | Business line of every eligible HF definition, from its `domain` via `kpigen/curation/domain_to_division.csv` | `prepare` |

Eligible = real source text (Hugging Face or dbt) and not deprecated: 96 definitions of 57 KPIs. The 11
GenAI-drafted definitions and the deprecated DEF-0025 are left out (PRD §3.5, §6).

## Commands
```
uv run python -m kpi_catalog.ml.gold prepare   # regenerate themes, sample and T2; never overwrites an annotator sheet
uv run python -m kpi_catalog.ml.gold compare   # check both sheets, write t1_gold.csv, print the agreement
```

## How to label (both annotators)

1. **Open only your own sheet** (`t1_annotator_a.csv` or `_b.csv`; Excel or Google Sheets is fine, but save it
   back as CSV with the same columns and row order). Don't look at the other sheet, talk about specific
   definitions, or look at ML output until both sheets are finished.
2. **Read `themes.csv` first**, including the scope notes: they settle the borderline cases.
3. **For each row, judge only what you see**: `display_name`, `definition_text` and `formula`. That is all the
   tagger sees. Ask "what does this number measure?", not "which department owns it?".
4. **`theme_1` (required):** the one theme that best describes what the KPI measures. Write the name exactly
   as in the `theme` column of `themes.csv` (e.g. `BalanceSheet`, `CustomerRelationship`).
5. **`theme_2` (optional):** only if the definition is clearly also about a second theme, as a scope note
   allows (e.g. Supply Chain with Cost for shipping costs). Leave it empty when in doubt. Most rows have one theme.
6. **`note` (optional):** anything you were unsure about. It helps the resolution meeting.
7. Run `compare` when you're done. It lists every empty, misspelled or unknown theme; fix them and run it again.

## Resolving disagreements

Once both sheets pass, `compare` writes `t1_gold.csv`. Rows where both annotators gave the same labels are
filled in automatically (`agreement = same`). For every other row (`partial` or `none`), meet, decide
together, and fill in `theme_1`, `theme_2` and a short `resolution_note`. Run `compare` again: it keeps your
resolutions (unless one of the annotators later changes that row) and reports "T1 gold set complete" when no
row is open. Record the agreement figures in `data/quality_log.md` and PRD §6.
