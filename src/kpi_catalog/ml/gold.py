"""Gold labels for the ML evaluation (task M3, PRD §6).

T1 (theme): one annotator (George) labels 40 definitions by hand in t1_annotator_a.csv. T2 (business line): the
HF `domain` mapped through domain_to_division.csv, generated, not labelled.

    uv run python -m kpi_catalog.ml.gold prepare    # sample, theme list, blank annotator sheet, T2 gold
    uv run python -m kpi_catalog.ml.gold finalize   # check the sheet and write t1_gold.csv

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
SCORED_ORIGINS = ("huggingface", "dbt")  # real source text; GenAI-drafted ones stay out (PRD §3.5)
ML_INPUT = ("display_name", "definition_text", "formula")  # what the tagger sees, and so what annotators see
SHEET_FIELDS = ("definition_id", *ML_INPUT, "theme_1", "theme_2", "note")
GOLD_FIELDS = ("definition_id", "theme_1", "theme_2")
SHEET = "t1_annotator_a.csv"  # annotator A = George (data/gold/README.md)


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
    sheet = gold / SHEET
    if sheet.exists():  # never overwrite the labels
        print(f"kept {sheet.relative_to(ROOT)} (already exists)")
    else:
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
    """Problems in the annotator sheet: wrong rows, missing or unknown themes."""
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


def finalize(gold: Path = GOLD) -> int:
    """Check the annotator sheet and write t1_gold.csv (definition_id, theme_1, theme_2)."""
    valid = {t["theme"] for t in themes(load_vocab())}
    sample_ids = [r["definition_id"] for r in read_csv(gold / "t1_sample.csv")]
    rows = read_csv(gold / SHEET)
    errors = check_sheet(rows, sample_ids, valid, SHEET)
    if errors:
        print("\n".join(errors))
        print(f"{len(errors)} problem(s); fix {SHEET} and run finalize again.")
        return 1
    out = [{k: r[k].strip() for k in GOLD_FIELDS} for r in rows]
    write_csv(gold / "t1_gold.csv", GOLD_FIELDS, out)
    print(f"T1 gold set complete: {len(out)} definitions, {sum(bool(r['theme_2']) for r in out)} with a second theme; "
          f"theme_1 {dict(Counter(r['theme_1'] for r in out))}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m kpi_catalog.ml.gold", description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["prepare", "finalize"])
    args = parser.parse_args(argv)
    if args.command == "prepare":
        prepare()
        return 0
    return finalize()


if __name__ == "__main__":
    sys.exit(main())
