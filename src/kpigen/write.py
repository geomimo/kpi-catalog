"""Write the seed tables as CSV, byte-identical for identical input."""

import csv
import re
from pathlib import Path

from .paths import SCHEMA

# Seed tables in load order (parents before children). similarity_flags is ML output, not seed.
SEED_TABLES = [
    "divisions", "users", "roles", "permissions", "role_permissions", "user_roles", "kpis", "definitions",
    "kpi_relationships", "reviews", "assets", "asset_definitions", "tags", "definition_tags",
]


def schema_columns(schema: Path = SCHEMA) -> dict[str, list[str]]:
    """Column order per table, read from schema.sql so the CSVs always match it."""
    cols: dict[str, list[str]] = {}
    for name, body in re.findall(r"CREATE TABLE (\w+) \((.*?)\n\);", schema.read_text(encoding="utf-8"), re.S):
        cols[name] = []
        for line in body.splitlines():
            m = re.match(r"\s+([a-z_]+)\s+(TEXT|INTEGER|REAL)\b", line)
            if m:
                cols[name].append(m.group(1))
    return cols


def _cell(v) -> str:
    return "" if v is None else str(v)


def write_seed(tables: dict[str, list[dict]], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    cols = schema_columns()
    for name in SEED_TABLES:
        _write(out / f"{name}.csv", cols[name], tables[name])
    _write(out / "excluded.csv", ["origin", "origin_ref", "term", "reason_code", "reason"], tables["excluded"])


def _write(path: Path, header: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            extra = set(r) - set(header)
            if extra:
                raise ValueError(f"{path.name}: columns not in schema.sql: {sorted(extra)}")
            w.writerow([_cell(r.get(c)) for c in header])
