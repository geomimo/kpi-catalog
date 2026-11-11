"""Tests of the generator itself: coverage checks, determinism, and that validation catches errors."""

import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from kpigen.download import SOURCES
from kpigen.generate import Generator
from kpigen.inputs import InputError, load_inputs
from kpigen.paths import CURATION, RAW, ROOT, SCENARIOS
from kpigen.validate import SeedError, load_seed
from kpigen.write import write_seed

pytestmark = pytest.mark.skipif(
    not all((RAW / rel).exists() for rel in SOURCES), reason="data/raw/ missing; run `uv run kpigen download`"
)


def generate(out: Path, curation: Path = CURATION) -> None:
    write_seed(Generator(load_inputs(curation=curation)).build(), out)


def test_two_runs_are_byte_identical(tmp_path):
    generate(tmp_path / "a")
    generate(tmp_path / "b")
    files = sorted(p.name for p in (tmp_path / "a").iterdir())
    assert files == sorted(p.name for p in (tmp_path / "b").iterdir())
    for name in files:
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes(), name


def test_every_source_row_is_mapped_or_excluded_once():
    inp = load_inputs()
    refs = [r["origin_ref"] for r in inp.row_to_kpi] + [r["origin_ref"] for r in inp.exclusions]
    assert sorted(refs) == sorted(inp.sources)


def _copy_curation(tmp_path: Path) -> Path:
    cur = tmp_path / "curation"
    shutil.copytree(CURATION, cur)
    return cur


def _rewrite(path: Path, edit) -> None:
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    header = list(rows[0])
    rows = edit(rows)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, header, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def test_a_row_that_is_neither_mapped_nor_excluded_is_rejected(tmp_path):
    cur = _copy_curation(tmp_path)
    _rewrite(cur / "exclusions.csv", lambda rows: rows[1:])
    with pytest.raises(InputError, match="neither mapped nor excluded"):
        load_inputs(curation=cur)


def test_a_row_that_is_mapped_twice_is_rejected(tmp_path):
    cur = _copy_curation(tmp_path)
    _rewrite(cur / "row_to_kpi.csv", lambda rows: rows + [{**rows[0], "definition_id": "DEF-0999"}])
    with pytest.raises(InputError, match="duplicate source row"):
        load_inputs(curation=cur)


def test_a_hand_made_link_to_a_superseded_definition_is_rejected(tmp_path):
    import yaml
    sc = yaml.safe_load(SCENARIOS.read_text(encoding="utf-8"))
    old = next(f["definition_id"] for f in sc["definition_fixtures"] if f.get("superseded_by"))
    sc["assets"][0]["definitions"].append(old)
    path = tmp_path / "scenarios.yaml"
    path.write_text(yaml.safe_dump(sc), encoding="utf-8")
    with pytest.raises(InputError, match="links superseded definition"):
        load_inputs(scenarios=path)


def _break(seed: Path, table: str, edit) -> None:
    _rewrite(seed / f"{table}.csv", edit)


def test_validation_rejects_a_bad_enum(tmp_path):
    generate(tmp_path)
    _break(tmp_path, "definitions", lambda rows: [{**rows[0], "unit": "GBP"}] + rows[1:])
    with pytest.raises(SeedError, match="CHECK constraint"):
        load_seed(tmp_path)


def test_validation_rejects_a_dangling_foreign_key(tmp_path):
    generate(tmp_path)
    _break(tmp_path, "definitions", lambda rows: [{**rows[0], "kpi_id": "KPI-9999"}] + rows[1:])
    with pytest.raises(SeedError, match="foreign key"):
        load_seed(tmp_path)


def test_business_rules_reject_an_owner_without_a_role_in_the_division(tmp_path):
    generate(tmp_path)
    # USR-005 (Emma) is only an Observer in Finance: give her a Commercial definition.
    _break(tmp_path, "definitions",
           lambda rows: [{**r, "owner_user_id": "USR-005"} if r["division_id"] == "DIV-002" else r for r in rows])
    load_seed(tmp_path)  # still fits the schema ...
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests/test_seed_rules.py",
         "-k", "owner_holds_a_role"],
        cwd=ROOT, env={**os.environ, "KPIGEN_SEED_DIR": str(tmp_path)},
        capture_output=True,
    )
    assert result.returncode != 0  # ... but breaks a business rule
