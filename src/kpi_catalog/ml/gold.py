"""Gold labels for the ML evaluation (task M3, PRD §6).

T1 (theme): two annotators label the same 40 definitions by hand, independently; disagreements are resolved
together. T2 (business line): the HF `domain` mapped through domain_to_division.csv, generated, not labelled.

    uv run python -m kpi_catalog.ml.gold prepare   # sample, theme list, blank annotator sheets, T2 gold
    uv run python -m kpi_catalog.ml.gold compare   # check both sheets, write t1_gold.csv, report agreement

Labels must be made by people, never by an LLM or the tagger (PRD §3.5): the model is scored against them.
"""

import argparse
import csv
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

from rdflib import Graph, Namespace
from rdflib.namespace import SKOS

from kpigen.inputs import load_sources, norm_domain, read_csv
from kpigen.paths import CURATION, RAW, ROOT, SEED

GOLD = ROOT / "data" / "gold"
VOCAB = ROOT / "vocab" / "kpi-vocabulary.ttl"
KV = Namespace("https://example.org/kpi-catalog/vocab/")

SAMPLE_SEED = 42
SAMPLE_SIZE = 40
ANNOTATORS = ("a", "b")          # who is who: data/gold/README.md
SCORED_ORIGINS = ("huggingface", "dbt")  # real source text; GenAI-drafted ones stay out (PRD §3.5)
ML_INPUT = ("display_name", "definition_text", "formula")  # what the tagger sees, and so what annotators see
SHEET_FIELDS = ("definition_id", *ML_INPUT, "theme_1", "theme_2", "note")
GOLD_FIELDS = ("definition_id", "a_theme_1", "a_theme_2", "b_theme_1", "b_theme_2",
               "agreement", "theme_1", "theme_2", "resolution_note")


def local(uri) -> str:
    return str(uri).removeprefix(str(KV))


def load_vocab(vocab: Path = VOCAB) -> Graph:
    g = Graph()
    g.parse(vocab, format="turtle")
    return g


def themes(g: Graph) -> list[dict[str, str]]:
    """The T1 candidates: every narrower concept of a Category perspective, read from the vocabulary."""
    rows = []
    for p in g.objects(KV.CategoryScheme, SKOS.hasTopConcept):
        for t in g.objects(p, SKOS.narrower):
            rows.append({"theme": local(t), "label": str(g.value(t, SKOS.prefLabel)),
                         "perspective": local(p), "perspective_label": str(g.value(p, SKOS.prefLabel)),
                         "definition": str(g.value(t, SKOS.definition)),
                         "scope_note": str(g.value(t, SKOS.scopeNote) or "")})
    return sorted(rows, key=lambda r: (r["perspective_label"], r["label"]))


def business_lines(g: Graph) -> set[str]:
    return {local(c) for c in g.subjects(SKOS.inScheme, KV.BusinessLineScheme)}


def eligible(definitions: list[dict]) -> list[dict]:
    """Definitions the ML is scored on: real source text, not deprecated (M10)."""
    return [d for d in definitions if d["origin"] in SCORED_ORIGINS and d["status"] != "deprecated"]


def draw_sample(pool: list[dict], size: int = SAMPLE_SIZE, seed: int = SAMPLE_SEED) -> list[dict]:
    """`size` KPIs at random, one definition each, so near-duplicate variants of one KPI don't count twice."""
    by_kpi: dict[str, list[dict]] = defaultdict(list)
    for d in sorted(pool, key=lambda d: d["definition_id"]):
        by_kpi[d["kpi_id"]].append(d)
    if len(by_kpi) < size:
        raise ValueError(f"only {len(by_kpi)} KPIs in the pool, can't sample {size}")
    rng = random.Random(seed)
    kpis = sorted(rng.sample(sorted(by_kpi), size))
    return sorted((rng.choice(by_kpi[k]) for k in kpis), key=lambda d: d["definition_id"])


def t2_rows(pool: list[dict], raw: Path = RAW, curation: Path = CURATION) -> list[dict[str, str]]:
    sources = load_sources(raw)
    domains = {norm_domain(r["hf_domain"]): r["business_line"]
               for r in read_csv(curation / "domain_to_division.csv")}
    rows = []
    for d in pool:
        if d["origin"] != "huggingface":
            continue  # T2 is scored on HF rows only (PRD §6)
        domain = sources[d["origin_ref"]].domain
        rows.append({"definition_id": d["definition_id"], "origin_ref": d["origin_ref"],
                     "hf_domain": domain, "business_line": domains[domain]})
    return sorted(rows, key=lambda r: r["definition_id"])


def write_csv(path: Path, fields, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fields), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def prepare(gold: Path = GOLD, seed_dir: Path = SEED, raw: Path = RAW) -> None:
    gold.mkdir(parents=True, exist_ok=True)
    g = load_vocab()
    pool = eligible(read_csv(seed_dir / "definitions.csv"))
    sample = draw_sample(pool)

    write_csv(gold / "themes.csv", ("theme", "label", "perspective", "perspective_label", "definition", "scope_note"),
              themes(g))
    write_csv(gold / "t1_sample.csv", ("definition_id", "kpi_id", "division_id", "origin", "origin_ref", "status"),
              ({k: d[k] for k in ("definition_id", "kpi_id", "division_id", "origin", "origin_ref", "status")}
               for d in sample))
    for a in ANNOTATORS:
        sheet = gold / f"t1_annotator_{a}.csv"
        if sheet.exists():  # never overwrite someone's labels
            print(f"kept {sheet.relative_to(ROOT)} (already exists)")
            continue
        write_csv(sheet, SHEET_FIELDS, ({**{k: d[k] for k in ("definition_id", *ML_INPUT)},
                                         "theme_1": "", "theme_2": "", "note": ""} for d in sample))
    t2 = t2_rows(pool, raw)
    unknown = {r["business_line"] for r in t2} - business_lines(g)
    if unknown:
        raise SystemExit(f"business lines missing from the vocabulary: {sorted(unknown)}")
    write_csv(gold / "t2_gold.csv", ("definition_id", "origin_ref", "hf_domain", "business_line"), t2)

    print(f"pool: {len(pool)} definitions of {len({d['kpi_id'] for d in pool})} KPIs")
    print(f"T1 sample: {len(sample)} definitions, one per KPI, seed {SAMPLE_SEED}; "
          f"origins {dict(Counter(d['origin'] for d in sample))}, "
          f"{len({d['division_id'] for d in sample})} divisions")
    print(f"T2 gold: {len(t2)} HF definitions; {dict(Counter(r['business_line'] for r in t2))}")


def check_sheet(rows: list[dict], sample_ids: list[str], valid: set[str], name: str) -> list[str]:
    """Problems in one annotator sheet: wrong rows, missing or unknown themes."""
    errors = []
    if [r["definition_id"] for r in rows] != sample_ids:
        return [f"{name}: rows don't match t1_sample.csv (don't add, remove or reorder rows)"]
    for r in rows:
        t1, t2 = r["theme_1"].strip(), r["theme_2"].strip()
        if not t1:
            errors.append(f"{name} {r['definition_id']}: theme_1 is empty")
        for t in (t1, t2):
            if t and t not in valid:
                errors.append(f"{name} {r['definition_id']}: unknown theme '{t}' (use a name from themes.csv)")
        if t2 and t2 == t1:
            errors.append(f"{name} {r['definition_id']}: theme_2 repeats theme_1")
    return errors


def merge(a_rows: list[dict], b_rows: list[dict], previous: dict[str, dict]) -> list[dict]:
    """One t1_gold row per definition. Identical labels are agreed; other rows keep an earlier resolution,
    as long as neither annotator's labels changed since."""
    out = []
    for a, b in zip(a_rows, b_rows, strict=True):
        la = (a["theme_1"].strip(), a["theme_2"].strip())
        lb = (b["theme_1"].strip(), b["theme_2"].strip())
        row = {"definition_id": a["definition_id"], "a_theme_1": la[0], "a_theme_2": la[1],
               "b_theme_1": lb[0], "b_theme_2": lb[1], "theme_1": "", "theme_2": "", "resolution_note": ""}
        if la == lb:
            row.update(agreement="same", theme_1=la[0], theme_2=la[1])
        else:
            row["agreement"] = "partial" if ({*la} - {""}) & ({*lb} - {""}) else "none"
            old = previous.get(row["definition_id"])
            if old and all(old[k] == row[k] for k in ("a_theme_1", "a_theme_2", "b_theme_1", "b_theme_2")):
                row.update(theme_1=old["theme_1"], theme_2=old["theme_2"], resolution_note=old["resolution_note"])
        out.append(row)
    return out


def compare(gold: Path = GOLD) -> int:
    g = load_vocab()
    th = themes(g)
    valid = {t["theme"] for t in th}
    sample_ids = [r["definition_id"] for r in read_csv(gold / "t1_sample.csv")]
    sheets = {a: read_csv(gold / f"t1_annotator_{a}.csv") for a in ANNOTATORS}
    errors = [e for a, rows in sheets.items() for e in check_sheet(rows, sample_ids, valid, f"annotator {a}")]
    if errors:
        print("\n".join(errors))
        print(f"{len(errors)} problem(s); fix the sheets and run compare again.")
        return 1

    gold_path = gold / "t1_gold.csv"
    previous = {r["definition_id"]: r for r in read_csv(gold_path)} if gold_path.exists() else {}
    rows = merge(sheets["a"], sheets["b"], previous)
    write_csv(gold_path, GOLD_FIELDS, rows)

    bad = [f"t1_gold.csv {r['definition_id']}: unknown theme '{t}'"
           for r in rows for t in (r["theme_1"], r["theme_2"]) if t and t not in valid]
    n = len(rows)
    same = sum(r["agreement"] == "same" for r in rows)
    primary = sum(a["theme_1"].strip() == b["theme_1"].strip() for a, b in zip(sheets["a"], sheets["b"]))
    perspective_of = {t["theme"]: t["perspective"] for t in th}
    persp = sum(perspective_of[a["theme_1"].strip()] == perspective_of[b["theme_1"].strip()]
                for a, b in zip(sheets["a"], sheets["b"]))
    open_rows = [r["definition_id"] for r in rows if not r["theme_1"]]
    print(f"identical labels: {same}/{n}; same theme_1: {primary}/{n}; same perspective of theme_1: {persp}/{n}")
    print(f"wrote {gold_path}")
    print("\n".join(bad) if bad else "")
    if open_rows:
        print(f"{len(open_rows)} disagreement(s) to resolve: fill theme_1/theme_2 and resolution_note in "
              f"t1_gold.csv for {', '.join(open_rows)}")
        return 1
    if bad:
        return 1
    print("T1 gold set complete.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m kpi_catalog.ml.gold", description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["prepare", "compare"])
    args = parser.parse_args(argv)
    if args.command == "prepare":
        prepare()
        return 0
    return compare()


if __name__ == "__main__":
    sys.exit(main())
