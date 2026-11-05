"""Read the pinned sources, the curation files and scenarios.yaml, and check that they fit together."""

import csv
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .paths import CURATION, RAW, SCENARIOS

TODO_MARK = "TODO(george)"
DBT_FILES = ["orders", "order_items", "customers"]  # order fixes the dbt definition IDs


class InputError(SystemExit):
    pass


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def norm_domain(domain: str) -> str:
    return " ".join(domain.split())  # "in  finance" -> "in finance"


@dataclass
class SourceRow:
    origin: str           # huggingface | dbt
    origin_ref: str       # hf:<row> | dbt:<metric name>
    term: str
    definition_text: str
    source_table: str | None = None
    source_column: str | None = None
    related_columns: str | None = None
    domain: str | None = None
    dbt: dict = field(default_factory=dict)  # the raw dbt metric


def load_sources(raw: Path = RAW) -> dict[str, SourceRow]:
    rows: dict[str, SourceRow] = {}
    for i, r in enumerate(read_csv(raw / "hf" / "testcontext_file1.csv")):
        ref = f"hf:{i}"
        rows[ref] = SourceRow(
            origin="huggingface", origin_ref=ref, term=r["businessterm"].strip(),
            definition_text=r["description"].strip(), source_table=r["tablename"].strip(),
            source_column=r["columnname"].strip(), related_columns=r["other columns for context"].strip(),
            domain=norm_domain(r["domain"]),
        )
    for f in DBT_FILES:
        doc = yaml.safe_load((raw / "dbt" / f"{f}.yml").read_text(encoding="utf-8"))
        for m in doc["metrics"]:
            ref = f"dbt:{m['name']}"
            rows[ref] = SourceRow(
                origin="dbt", origin_ref=ref, term=m["label"], definition_text=m["description"].strip(),
                source_table=f, source_column=m["name"], dbt=m,
            )
    return rows


@dataclass
class Inputs:
    sources: dict[str, SourceRow]
    domains: dict[str, dict]
    kpis: list[dict]
    row_to_kpi: list[dict]
    exclusions: list[dict]
    relationships: list[dict]
    scenarios: dict


def load_inputs(raw: Path = RAW, curation: Path = CURATION, scenarios: Path = SCENARIOS) -> Inputs:
    inp = Inputs(
        sources=load_sources(raw),
        domains={norm_domain(r["hf_domain"]): r for r in read_csv(curation / "domain_to_division.csv")},
        kpis=read_csv(curation / "kpis.csv"),
        row_to_kpi=read_csv(curation / "row_to_kpi.csv"),
        exclusions=read_csv(curation / "exclusions.csv"),
        relationships=read_csv(curation / "relationships.csv"),
        scenarios=yaml.safe_load(scenarios.read_text(encoding="utf-8")),
    )
    check(inp)
    return inp


def _unique(values: list[str], what: str, errors: list[str]) -> None:
    seen: set[str] = set()
    for v in values:
        if v in seen:
            errors.append(f"duplicate {what}: {v}")
        seen.add(v)


def check(inp: Inputs) -> None:
    """Coverage and consistency of the hand-edited files (PRD §3.4, task D4)."""
    errors: list[str] = []
    sc = inp.scenarios

    # Every source row appears exactly once in row_to_kpi.csv or exclusions.csv.
    mapped = [r["origin_ref"] for r in inp.row_to_kpi]
    excluded = [r["origin_ref"] for r in inp.exclusions]
    _unique(mapped + excluded, "source row (mapped and/or excluded)", errors)
    for ref in inp.sources:
        if ref not in mapped and ref not in excluded:
            errors.append(f"source row {ref} is neither mapped nor excluded")
    for ref in mapped + excluded:
        if ref not in inp.sources:
            errors.append(f"{ref} isn't a row of the pinned sources")

    division_codes = {d["code"] for d in sc["divisions"]}
    kpi_ids = [k["kpi_id"] for k in inp.kpis]
    _unique(kpi_ids, "kpi_id", errors)
    _unique([k["slug"] for k in inp.kpis], "KPI slug", errors)
    hand = sc["handwritten_definitions"]
    def_ids = [r["definition_id"] for r in inp.row_to_kpi] + [d["definition_id"] for d in hand]
    _unique(def_ids, "definition_id", errors)

    for r in inp.row_to_kpi:
        src = inp.sources.get(r["origin_ref"])
        if r["kpi_id"] not in kpi_ids:
            errors.append(f"{r['origin_ref']}: unknown kpi_id {r['kpi_id']}")
        if src and src.origin == "huggingface":
            if r["division_code"]:
                errors.append(f"{r['origin_ref']}: HF rows take their division from domain_to_division.csv")
            if src.domain not in inp.domains:
                errors.append(f"{r['origin_ref']}: domain '{src.domain}' missing from domain_to_division.csv")
        elif r["division_code"] not in division_codes:
            errors.append(f"{r['origin_ref']}: division_code '{r['division_code']}' is not a division")
        for fix in filter(None, r["fix"].split(";")):
            fld, _, sub = fix.partition(":")
            old, sep, _new = sub.partition("=>")
            if fld not in FIXABLE or not sep:
                errors.append(f"{r['origin_ref']}: bad fix '{fix}' (use field:old=>new; fields {sorted(FIXABLE)})")
            elif src and old not in (getattr(src, FIXABLE[fld]) or ""):
                errors.append(f"{r['origin_ref']}: fix '{fix}' doesn't match the source text")
    for d in inp.domains.values():
        if d["division_code"] not in division_codes:
            errors.append(f"domain '{d['hf_domain']}': unknown division {d['division_code']}")

    for d in hand:
        if d["kpi_id"] not in kpi_ids:
            errors.append(f"{d['definition_id']}: unknown kpi_id {d['kpi_id']}")
        if d["division"] not in division_codes:
            errors.append(f"{d['definition_id']}: unknown division {d['division']}")
    known = set(def_ids)
    refs = [(r["from_definition_id"], r["to_definition_id"]) for r in inp.relationships]
    refs += [(r["from"], r["to"]) for r in sc["handwritten_relationships"]]
    for a, b in refs:
        for x in (a, b):
            if x not in known:
                errors.append(f"relationship refers to unknown definition {x}")
    for f in sc["definition_fixtures"]:
        for x in filter(None, [f["definition_id"], f.get("superseded_by")]):
            if x not in known:
                errors.append(f"definition_fixtures: unknown definition {x}")
    for a in sc["assets"]:
        errors += [f"{a['asset_id']}: unknown definition {x}" for x in a["definitions"] if x not in known]
    for t in sc["community_tags"]["fixtures"]:
        if t["label"] not in sc["community_tags"]["labels"]:
            errors.append(f"community tag fixture '{t['label']}' isn't in community_tags.labels")
        errors += [f"tag '{t['label']}': unknown definition {x}" for x in t["definitions"] if x not in known]

    if errors:
        raise InputError("Curation inputs are inconsistent:\n  " + "\n  ".join(errors))


# row_to_kpi.fix field -> SourceRow attribute it applies to (display_name fixes apply to the term)
FIXABLE = {
    "display_name": "term",
    "definition_text": "definition_text",
    "source_column": "source_column",
    "related_columns": "related_columns",
}


def apply_fixes(value: str | None, field_name: str, fixes: str) -> str | None:
    for fix in filter(None, fixes.split(";")):
        fld, _, sub = fix.partition(":")
        if fld == field_name and value is not None:
            old, _, new = sub.partition("=>")
            value = value.replace(old, new)
    return value


def count_todos(curation: Path = CURATION, scenarios: Path = SCENARIOS) -> dict[str, int]:
    files = sorted(curation.glob("*.csv")) + [scenarios]
    counts = {f.name: f.read_text(encoding="utf-8").count(TODO_MARK) for f in files}
    return {k: v for k, v in counts.items() if v}
