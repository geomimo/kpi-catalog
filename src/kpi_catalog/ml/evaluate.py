"""ML evaluation (task M5, PRD §6): the tagger against the gold sets and baselines, written to reports/ml_eval.md.

    uv run python -m kpi_catalog.ml.evaluate

- T1 theme: the 40 hand-labelled definitions (data/gold/t1_gold.csv), at theme and at perspective level.
  The top theme is scored against `theme_1` (accuracy, macro-F1) and, leniently, against either gold theme.
  `τ_min` only decides the second theme, so it is tuned on the theme sets (micro-F1 over definition-theme pairs).
- T2 business line: the 81 HF definitions (data/gold/t2_gold.csv). A "fall back to Group-wide below a score"
  variant is measured too, as an option; the tagger doesn't use it.
- T3 unit check: no gold set; the flags are listed with the seeded error (Q1) marked.
- Baselines: majority class (of the gold set itself) and keyword rules built from the vocabulary's prefLabels and
  altLabels, so no rule is written after seeing the gold labels.

Predictions are computed here from the seed and the vocabulary, not read from the database, so curator decisions
can't leak into the scores. The 11 GenAI-drafted definitions have no gold labels and are listed unscored (PRD §3.5).
"""

import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.metrics import classification_report, f1_score

from kpi_catalog.ml import tagger
from kpi_catalog.ml.gold import GOLD
from kpi_catalog.vocab import skos
from kpigen.inputs import read_csv
from kpigen.paths import ROOT, SEED

REPORT = ROOT / "reports" / "ml_eval.md"
TAU_GRID = [round(0.30 + 0.01 * i, 2) for i in range(41)]  # 0.30 ... 0.70
FALLBACK_GRID = [round(0.01 * i, 2) for i in range(41)]  # 0.00 ... 0.40
GROUP_WIDE = "GroupWide"
SEEDED_UNIT_ERROR = "DEF-0007"  # Operating Expenses stored as `score` (data/quality_log.md Q1)


def accuracy_f1(gold: list[str], pred: list[str]) -> tuple[float, float]:
    labels = sorted(set(gold) | set(pred))
    acc = sum(g == p for g, p in zip(gold, pred)) / len(gold)
    return acc, f1_score(gold, pred, labels=labels, average="macro", zero_division=0)


def set_scores(gold: list[set[str]], pred: list[set[str]]) -> dict[str, float]:
    """Micro precision, recall and F1 over (definition, theme) pairs, and the share of exactly matching sets."""
    tp = sum(len(g & p) for g, p in zip(gold, pred))
    n_pred, n_gold = sum(map(len, pred)), sum(map(len, gold))
    precision, recall = tp / n_pred, tp / n_gold
    f1 = 2 * precision * recall / (precision + recall) if tp else 0.0
    return {"precision": precision, "recall": recall, "f1": f1,
            "exact": sum(g == p for g, p in zip(gold, pred)) / len(gold),
            "second": sum(len(p) == 2 for p in pred)}


def keyword_rules(cands: list[skos.Concept]) -> list[tuple[str, re.Pattern]]:
    return [(c.name, re.compile("|".join(rf"\b{re.escape(kw.lower())}\b" for kw in (c.label, *c.alt_labels))))
            for c in cands]


def keyword_predict(text: str, rules, fallback: str) -> str:
    """The concept with the most label hits in the text; ties go to the earliest hit; no hit gives `fallback`."""
    text = text.lower()
    best = None
    for name, rx in rules:
        hits = list(rx.finditer(text))
        if hits:
            key = (-len(hits), hits[0].start())
            if best is None or key < best[0]:
                best = (key, name)
    return best[1] if best else fallback


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def evaluate(encode: tagger.Encoder) -> dict:
    g = skos.load_vocab()
    themes, lines = skos.themes(g), skos.business_lines(g)
    perspective = {t.name: t.broader for t in themes}
    labels = {c.name: c.label for c in [*skos.concepts(g, skos.KV.CategoryScheme), *lines]}

    defs = {d["definition_id"]: d for d in read_csv(SEED / "definitions.csv") if d["status"] != "deprecated"}
    ids = sorted(defs)
    row = {d: i for i, d in enumerate(ids)}
    texts = [tagger.definition_input(defs[d]) for d in ids]
    vectors = encode(texts)
    theme_scores = vectors @ encode([tagger.concept_input(c) for c in themes]).T
    line_scores = vectors @ encode([tagger.concept_input(c) for c in lines]).T
    top_theme = [themes[int(np.argmax(s))].name for s in theme_scores]
    top_line = [lines[int(np.argmax(s))].name for s in line_scores]

    # --- T1 ---------------------------------------------------------------------------------------------
    t1 = read_csv(GOLD / "t1_gold.csv")
    gold1 = [r["theme_1"] for r in t1]
    gold_sets = [{r["theme_1"], *([r["theme_2"]] if r["theme_2"] else [])} for r in t1]
    majority1 = Counter(gold1).most_common(1)[0][0]
    rules1 = keyword_rules(themes)
    preds1 = {"Majority class": [majority1] * len(t1),
              "Keyword rules": [keyword_predict(texts[row[r["definition_id"]]], rules1, majority1) for r in t1],
              "Embedding similarity (tagger)": [top_theme[row[r["definition_id"]]] for r in t1]}
    t1_rows = []
    for name, pred in preds1.items():
        acc, f1 = accuracy_f1(gold1, pred)
        p_acc, p_f1 = accuracy_f1([perspective[x] for x in gold1], [perspective[x] for x in pred])
        lenient = sum(p in s for p, s in zip(pred, gold_sets)) / len(t1)
        t1_rows.append((name, acc, f1, lenient, p_acc, p_f1))
    emb1 = preds1["Embedding similarity (tagger)"]
    per_class = classification_report(gold1, emb1, labels=sorted(set(gold1)), output_dict=True, zero_division=0)
    misses = [(r["definition_id"], defs[r["definition_id"]]["display_name"], p, r["theme_1"], r["theme_2"])
              for r, p in zip(t1, emb1) if p not in gold_sets[t1.index(r)]]

    sweep = []
    for tau in TAU_GRID:
        pred_sets = [{themes[i].name for i in tagger.pick(theme_scores[row[r["definition_id"]]], tagger.MAX_THEMES, tau)}
                     for r in t1]
        sweep.append((tau, set_scores(gold_sets, pred_sets)))
    best_tau = max(sweep, key=lambda s: (round(s[1]["f1"], 6), -s[0]))[0]  # ties go to the lowest τ
    current = next(s for t, s in sweep if t == tagger.TAU_MIN) if tagger.TAU_MIN in TAU_GRID else None

    # --- T2 ---------------------------------------------------------------------------------------------
    t2 = read_csv(GOLD / "t2_gold.csv")
    gold2 = [r["business_line"] for r in t2]
    majority2 = Counter(gold2).most_common(1)[0][0]
    rules2 = keyword_rules(lines)
    t2_scores = [line_scores[row[r["definition_id"]]] for r in t2]
    preds2 = {"Majority class": [majority2] * len(t2),
              "Keyword rules": [keyword_predict(texts[row[r["definition_id"]]], rules2, majority2) for r in t2],
              "Embedding similarity (tagger)": [top_line[row[r["definition_id"]]] for r in t2]}
    fallback = []
    for tau in FALLBACK_GRID:
        pred = [lines[int(np.argmax(s))].name if s.max() >= tau else GROUP_WIDE for s in t2_scores]
        fallback.append((tau, *accuracy_f1(gold2, pred)))
    best_fb = max(fallback, key=lambda f: (round(f[2], 6), -f[0]))  # best macro-F1; ties go to the lower τ
    t2_rows = [(name, *accuracy_f1(gold2, pred)) for name, pred in preds2.items()]
    confusions = Counter((gl, p) for gl, p in zip(gold2, preds2["Embedding similarity (tagger)"]) if gl != p)

    # --- T3 and the unscored definitions ----------------------------------------------------------------
    from kpigen.validate import load_seed
    flags = tagger.check_units(load_seed(SEED), ids, vectors, g)
    drafted = [(d, defs[d]["display_name"], defs[d]["division_id"],
                [themes[i].name for i in tagger.pick(theme_scores[row[d]], tagger.MAX_THEMES, tagger.TAU_MIN)],
                top_line[row[d]]) for d in ids if defs[d]["origin"] == "handwritten"]

    return {"labels": labels, "t1_n": len(t1), "t1_rows": t1_rows, "per_class": per_class, "misses": misses,
            "majority1": majority1, "gold_second": sum(len(s) == 2 for s in gold_sets), "sweep": sweep, "best_tau": best_tau, "current": current,
            "t2_n": len(t2), "t2_rows": t2_rows, "majority2": majority2, "fallback": fallback, "best_fb": best_fb,
            "confusions": confusions, "flags": flags, "n_live": len(ids), "drafted": drafted}


def render(r: dict) -> str:
    L = r["labels"]
    out = ["# ML evaluation (task M5)", "",
           "Generated by `uv run python -m kpi_catalog.ml.evaluate`; don't edit by hand. Method: PRD §6.",
           f"Model `{tagger.MODEL}`; current tagger settings: `τ_min` = {tagger.TAU_MIN}, up to "
           f"{tagger.MAX_THEMES} themes; unit check with {tagger.K_UNIT} neighbours and a {pct(tagger.MIN_SHARE)} vote.",
           "Gold labels: T1 by one annotator (no agreement figure); T2 from the HF `domain` (data/gold/README.md).", "",
           f"## T1 theme ({r['t1_n']} definitions)", "",
           "Top theme against `theme_1`; *lenient* counts a hit on either gold theme. Perspective = the theme's "
           "Balanced Scorecard parent.", "",
           "| Method | Accuracy | Macro-F1 | Lenient accuracy | Perspective accuracy | Perspective macro-F1 |",
           "|---|---|---|---|---|---|"]
    out += [f"| {n} | {pct(a)} | {f:.3f} | {pct(le)} | {pct(pa)} | {pf:.3f} |" for n, a, f, le, pa, pf in r["t1_rows"]]
    out += ["", f"Majority class = {L[r['majority1']]}. Keyword rules: a theme's prefLabel and altLabels as whole "
            "words; no hit falls back to the majority class.", "",
            "**Per theme (tagger, themes that occur as `theme_1`):**", "",
            "| Theme | Gold count | Precision | Recall | F1 |", "|---|---|---|---|---|"]
    out += [f"| {L[k]} | {int(v['support'])} | {v['precision']:.2f} | {v['recall']:.2f} | {v['f1-score']:.2f} |"
            for k, v in sorted(r["per_class"].items()) if k in L]
    out += ["", "Themes with no gold example can't be measured.", "",
            "**Misses (top theme is neither gold theme):**", "",
            "| Definition | Predicted | Gold theme_1 | Gold theme_2 |", "|---|---|---|---|"]
    out += [f"| {d} {n} | {L[p]} | {L[g1]} | {L[g2] if g2 else ''} |" for d, n, p, g1, g2 in r["misses"]]
    out += ["", "### Tuning `τ_min` (second theme)", "",
            "The top theme is always kept, so `τ_min` only adds second themes. Micro-F1 over (definition, theme) "
            f"pairs against the gold theme sets; *exact* = the predicted set equals the gold set. "
            f"{r['gold_second']} of {r['t1_n']} gold sets have a second theme.", "",
            "| `τ_min` | Second themes | Precision | Recall | F1 | Exact sets |", "|---|---|---|---|---|---|"]
    shown = {t for t in TAU_GRID if round(t * 100) % 5 == 0} | {r["best_tau"], tagger.TAU_MIN}
    out += [f"| {t:.2f}{' (best)' if t == r['best_tau'] else ''}{' (current)' if t == tagger.TAU_MIN else ''} | "
            f"{s['second']} | {s['precision']:.3f} | {s['recall']:.3f} | {s['f1']:.3f} | {pct(s['exact'])} |"
            for t, s in r["sweep"] if t in shown]
    out += ["", f"Best `τ_min` on this gold set: **{r['best_tau']:.2f}** (ties go to the lowest value). "
            "Tuned on 40 definitions, so it is optimistic.", "",
            f"## T2 business line ({r['t2_n']} HF definitions)", "",
            "| Method | Accuracy | Macro-F1 |", "|---|---|---|"]
    out += [f"| {n} | {pct(a)} | {f:.3f} |" for n, a, f in r["t2_rows"]]
    t, a, f = r["best_fb"]
    out += [f"| *Option, not used:* tagger, but Group-wide when the best score is below {t:.2f} (tuned here) "
            f"| {pct(a)} | {f:.3f} |",
            "", f"Majority class = {L[r['majority2']]}. The fallback threshold is tuned on the same 81 definitions it "
            "is scored on, so its row is optimistic.", "",
            "**Most common confusions (gold → tagger):** " +
            "; ".join(f"{L[g]} → {L[p]} ({n})" for (g, p), n in r["confusions"].most_common(6)), "",
            f"## T3 unit check ({r['n_live']} definitions)", "",
            "No gold set: the seed has one unit error on purpose (data/quality_log.md Q1). Flags:", "",
            "| Definition | Unit (measure type) | Neighbours' vote | Finding |", "|---|---|---|---|"]
    out += [f"| {f['definition_id']} | {f['unit']} ({f['measure_type']}) | {f['predicted']} {pct(f['share'])} | "
            f"{'seeded error Q1, caught' if f['definition_id'] == SEEDED_UNIT_ERROR else 'see data/quality_log.md (C10)'} |"
            for f in r["flags"]]
    caught = any(f["definition_id"] == SEEDED_UNIT_ERROR for f in r["flags"])
    out += ["", f"Seeded error caught: **{'yes' if caught else 'NO'}**; other flags: "
            f"{sum(f['definition_id'] != SEEDED_UNIT_ERROR for f in r['flags'])}.", "",
            "## GenAI-drafted definitions (unscored)", "",
            "Our own texts (PRD §3.5) have no gold labels and are kept out of the scores. The tagger's output, for "
            "reference:", "", "| Definition | Division | Themes | Business line |", "|---|---|---|---|"]
    out += [f"| {d} {n} | {div} | {', '.join(L[t] for t in ts)} | {L[b]} |" for d, n, div, ts, b in r["drafted"]]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    report = render(evaluate(tagger.sentence_encoder()))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(report, encoding="utf-8")
    print(report)
    print(f"wrote {REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
