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


@pytest.mark.parametrize("annotator", gold.ANNOTATORS)
def test_annotator_sheets_are_well_formed(g, annotator):
    """Rows must match the sample; empty labels are fine (labelling in progress), unknown ones aren't."""
    rows = read_csv(gold.GOLD / f"t1_annotator_{annotator}.csv")
    assert tuple(rows[0]) == gold.SHEET_FIELDS
    sample_ids = [r["definition_id"] for r in read_csv(gold.GOLD / "t1_sample.csv")]
    valid = {t["theme"] for t in gold.themes(g)}
    errors = gold.check_sheet(rows, sample_ids, valid, annotator)
    assert [e for e in errors if "is empty" not in e] == []


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


def test_merge_agrees_keeps_resolutions_and_reopens_changed_rows():
    a = sheet(("Revenue", ""), ("Cost", "SupplyChain"), ("Tax", ""))
    b = sheet(("Revenue", ""), ("SupplyChain", ""), ("Risk", ""))
    rows = gold.merge(a, b, {})
    assert [r["agreement"] for r in rows] == ["same", "partial", "none"]
    assert rows[0]["theme_1"] == "Revenue" and rows[1]["theme_1"] == ""

    rows[1].update(theme_1="SupplyChain", theme_2="Cost", resolution_note="shipping cost")
    previous = {r["definition_id"]: r for r in rows}
    again = gold.merge(a, b, previous)
    assert again[1]["theme_1"] == "SupplyChain" and again[1]["resolution_note"] == "shipping cost"

    b[1]["theme_2"] = "Cost"  # an annotator changed the row: the old resolution no longer applies
    assert gold.merge(a, b, previous)[1]["theme_1"] == ""


def test_compare_end_to_end(tmp_path, g):
    shutil.copy(gold.GOLD / "t1_sample.csv", tmp_path)
    ids = [r["definition_id"] for r in read_csv(tmp_path / "t1_sample.csv")]
    for a, second in (("a", "Revenue"), ("b", "Cost")):
        with (tmp_path / f"t1_annotator_{a}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=gold.SHEET_FIELDS)
            w.writeheader()
            for i, d in enumerate(ids):
                w.writerow({"definition_id": d, "theme_1": "Revenue" if i else second})
    assert gold.compare(tmp_path) == 1  # one disagreement to resolve
    rows = read_csv(tmp_path / "t1_gold.csv")
    rows[0].update(theme_1="Revenue", resolution_note="test")
    gold.write_csv(tmp_path / "t1_gold.csv", gold.GOLD_FIELDS, rows)
    assert gold.compare(tmp_path) == 0
