"""Checks on the gold-label files and tooling (task M3, PRD §6)."""

import csv
import shutil

import pytest

from kpi_catalog.ml import gold
from kpigen.inputs import read_csv
from kpigen.paths import CURATION, RAW, SEED


@pytest.fixture(scope="module")
def g():
    return gold.load_vocab()


@pytest.fixture(scope="module")
def pool():
    return gold.eligible(read_csv(SEED / "definitions.csv"))


def test_pool_is_real_text_and_not_deprecated(pool):
    assert {d["origin"] for d in pool} <= {"huggingface", "dbt"}
    assert all(d["status"] != "deprecated" for d in pool)
    assert "DEF-0025" not in {d["definition_id"] for d in pool}


def test_sample_is_deterministic_and_one_per_kpi(pool):
    s = gold.draw_sample(pool)
    assert s == gold.draw_sample(pool)
    assert len(s) == gold.SAMPLE_SIZE
    assert len({d["kpi_id"] for d in s}) == gold.SAMPLE_SIZE


def test_committed_sample_matches_the_sampler(pool):
    committed = [r["definition_id"] for r in read_csv(gold.GOLD / "t1_sample.csv")]
    assert committed == [d["definition_id"] for d in gold.draw_sample(pool)], \
        "t1_sample.csv is out of date: run `uv run python -m kpi_catalog.ml.gold prepare`"


def test_themes_come_from_the_vocabulary(g):
    th = gold.themes(g)
    assert len(th) == len({t["theme"] for t in th}) == 11
    assert all(t["definition"] and t["perspective"].endswith("Perspective") for t in th)


def test_annotator_sheet_is_well_formed(g):
    """Rows must match the sample; empty labels are fine (labelling in progress), unknown ones aren't."""
    rows = read_csv(gold.GOLD / gold.SHEET)
    assert tuple(rows[0]) == gold.SHEET_FIELDS
    sample_ids = [r["definition_id"] for r in read_csv(gold.GOLD / "t1_sample.csv")]
    valid = {t["theme"] for t in gold.themes(g)}
    errors = gold.check_sheet(rows, sample_ids, valid, gold.SHEET)
    assert [e for e in errors if "is empty" not in e] == []


def test_committed_t1_gold_matches_the_sheet():
    path = gold.GOLD / "t1_gold.csv"
    if not path.exists():
        pytest.skip("t1_gold.csv not written yet: run `uv run python -m kpi_catalog.ml.gold finalize`")
    sheet = [{k: r[k].strip() for k in gold.GOLD_FIELDS} for r in read_csv(gold.GOLD / gold.SHEET)]
    assert read_csv(path) == sheet, "t1_gold.csv is out of date: run finalize"


def test_t2_gold_covers_every_eligible_hf_definition(g, pool):
    rows = read_csv(gold.GOLD / "t2_gold.csv")
    assert [r["definition_id"] for r in rows] == sorted(d["definition_id"] for d in pool
                                                        if d["origin"] == "huggingface")
    assert {r["business_line"] for r in rows} <= gold.business_lines(g)
    if (RAW / "hf" / "testcontext_file1.csv").exists():
        assert rows == gold.t2_rows(pool, RAW, CURATION), "t2_gold.csv is out of date: run prepare"


def sheet(*labels):
    return [{"definition_id": f"DEF-{i}", "theme_1": t1, "theme_2": t2} for i, (t1, t2) in enumerate(labels)]


def test_check_sheet_reports_problems():
    rows = sheet(("Revenue", ""), ("", ""), ("Revnue", ""), ("Cost", "Cost"))
    errors = gold.check_sheet(rows, ["DEF-0", "DEF-1", "DEF-2", "DEF-3"], {"Revenue", "Cost"}, "a")
    assert len(errors) == 3
    assert gold.check_sheet(rows[:1], ["DEF-9"], {"Revenue"}, "a")[0].endswith("reorder rows)")


def test_finalize_end_to_end(tmp_path):
    shutil.copy(gold.GOLD / "t1_sample.csv", tmp_path)
    ids = [r["definition_id"] for r in read_csv(tmp_path / "t1_sample.csv")]

    def write(first):
        with (tmp_path / gold.SHEET).open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=gold.SHEET_FIELDS)
            w.writeheader()
            for i, d in enumerate(ids):
                w.writerow({"definition_id": d, "theme_1": first if i == 0 else "Revenue"})

    write("Revnue")
    assert gold.finalize(tmp_path) == 1 and not (tmp_path / "t1_gold.csv").exists()
    write("Cost")
    assert gold.finalize(tmp_path) == 0
    rows = read_csv(tmp_path / "t1_gold.csv")
    assert len(rows) == len(ids) and rows[0] == {"definition_id": ids[0], "theme_1": "Cost", "theme_2": ""}
