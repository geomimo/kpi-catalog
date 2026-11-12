"""W2: the database loader builds the app database from schema.sql + data/seed/ (PRD §4, §11)."""

import csv
import shutil
import sqlite3

import pytest

from kpi_catalog import db
from kpi_catalog.web import create_app
from kpigen.paths import SEED
from kpigen.write import SEED_TABLES


def csv_rows(table, seed_dir=SEED):
    with (seed_dir / f"{table}.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    path = tmp_path_factory.mktemp("db") / "catalog.sqlite"
    db.build(path)
    con = db.connect(path)
    yield path, con
    con.close()


def test_real_seed_loads_with_matching_counts(built):
    _, con = built
    for table in SEED_TABLES:
        assert con.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == len(csv_rows(table)), table
    counts = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("definitions", "kpis", "users")}
    assert counts == {"definitions": 106, "kpis": 61, "users": 53}


def test_foreign_keys_on_and_consistent(built):
    _, con = built
    assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("UPDATE definitions SET kpi_id = 'KPI-9999' WHERE definition_id = 'DEF-0301'")


def test_empty_cells_become_null(built):
    _, con = built
    missing = [r["definition_id"] for r in csv_rows("definitions") if r["superseded_by_id"] == ""]
    nulls = con.execute("SELECT count(*) FROM definitions WHERE superseded_by_id IS NULL").fetchone()[0]
    assert nulls == len(missing)


def test_search_finds_turnover(built):
    _, con = built
    hits = {r["definition_id"] for r in con.execute(
        "SELECT definition_id FROM definitions_fts WHERE definitions_fts MATCH 'turnover'")}
    turnover_kpi = {r["definition_id"] for r in csv_rows("definitions") if r["kpi_id"] == "KPI-0058"}
    assert turnover_kpi == {"DEF-0301", "DEF-0302", "DEF-0303"}
    assert turnover_kpi <= hits
    assert con.execute("SELECT count(*) FROM definitions_fts").fetchone()[0] == 106


def test_search_index_includes_tag_labels(built):
    _, con = built
    tag, def_id = con.execute(
        "SELECT t.label, dt.definition_id FROM definition_tags dt JOIN tags t USING (tag_id) LIMIT 1").fetchone()
    query = '"' + tag.replace('"', '""') + '"'
    hits = {r[0] for r in con.execute(
        "SELECT definition_id FROM definitions_fts WHERE tag_labels MATCH ?", (query,))}
    assert def_id in hits


def test_search_index_can_be_rebuilt(built):
    _, con = built
    db.build_search_index(con)
    assert con.execute("SELECT count(*) FROM definitions_fts").fetchone()[0] == 106


def test_broken_seed_fails_and_leaves_no_database(tmp_path):
    seed = tmp_path / "seed"
    shutil.copytree(SEED, seed)
    rows = csv_rows("definitions", seed)
    rows[0]["kpi_id"] = "KPI-9999"
    with (seed / "definitions.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    path = tmp_path / "catalog.sqlite"
    path.write_text("old database")
    with pytest.raises(db.SeedError, match="foreign key"):
        db.build(path, seed_dir=seed)
    assert list(tmp_path.glob("catalog.sqlite*")) == []


def test_get_db_per_request(built):
    path, _ = built
    app = create_app({"DATABASE": str(path)})
    with app.app_context():
        con = db.get_db()
        assert con is db.get_db()
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert con.execute("SELECT name FROM kpis WHERE slug = 'turnover'").fetchone()["name"] == "Turnover"
    with pytest.raises(sqlite3.ProgrammingError):
        con.execute("SELECT 1")


def test_init_db_command(tmp_path):
    path = tmp_path / "catalog.sqlite"
    app = create_app({"DATABASE": str(path)})
    result = app.test_cli_runner().invoke(args=["init-db"])
    assert result.exit_code == 0, result.output
    assert "106 definitions" in result.output
    assert path.exists()
