# Gold labels (task M3)

The answer key the ML tagger is scored against (PRD §6, task M5). **Every label here is made by a person.**
No LLM, no tagger output and no other tool may suggest or check a label: the model would be graded against
its own kind of answers (PRD §3.5).

| File | What it is | Made by |
|---|---|---|
| `themes.csv` | The 11 themes you can choose from, with their perspective, SKOS definition and scope note | `prepare`, from `vocab/kpi-vocabulary.ttl` |
| `t1_sample.csv` | The 40 definitions to label: 40 of the 57 eligible KPIs at random (seed 42), one definition each | `prepare` |
| `t1_annotator_a.csv` | The T1 labels, with notes: annotator A, **George** (the only annotator, decided 15 Nov) | George, by hand |
| `t1_gold.csv` | The T1 gold set M5 reads: `definition_id`, `theme_1`, `theme_2` | `finalize`, from the sheet |
| `t2_gold.csv` | Business line of every eligible HF definition, from its `domain` via `kpigen/curation/domain_to_division.csv` | `prepare` |

Eligible = real source text (Hugging Face or dbt) and not deprecated: 96 definitions of 57 KPIs. The 11
GenAI-drafted definitions and the deprecated DEF-0025 are left out (PRD §3.5, §6). With one annotator there is
no inter-annotator agreement; the report names this as a limitation.

## Commands
```
uv run python -m kpi_catalog.ml.gold prepare    # regenerate themes, sample and T2; never overwrites the sheet
uv run python -m kpi_catalog.ml.gold finalize   # check the sheet, write t1_gold.csv
```

## How to label

1. **Read `themes.csv` first**, including the scope notes: they settle the borderline cases.
2. **For each row, judge only what you see**: `display_name`, `definition_text` and `formula`. That is all the
   tagger sees. Ask "what does this number measure?", not "which department owns it?".
3. **`theme_1` (required):** the one theme that best describes what the KPI measures. Write the name exactly
   as in the `theme` column of `themes.csv` (e.g. `BalanceSheet`, `CustomerRelationship`).
4. **`theme_2` (optional):** only if the definition is clearly also about a second, different theme, as a scope
   note allows (e.g. Supply Chain with Cost for shipping costs). Leave it empty when in doubt.
5. **`note` (optional):** anything you were unsure about; it feeds the report's discussion of the results.
6. Edit the sheet in VS Code, or in Excel or Google Sheets saved as CSV UTF-8 with the same columns and row order.
7. Run `finalize`. It lists every empty, misspelled, unknown or repeated theme; fix them and run it again until
   it reports "T1 gold set complete". Commit both the sheet and `t1_gold.csv`.
