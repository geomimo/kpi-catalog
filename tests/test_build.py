"""`kpi-catalog build` (M6) end to end: loader (W2) → official tags (V3) → ML batch (M2, M4) → search index →
web pages. The fake encoder from the tagger tests stands in for the model."""

import sqlite3

import pytest
from test_tagger import fake_encode

from kpi_catalog import cli, db
from kpi_catalog.ml import tagger
from kpi_catalog.vocab import skos
from kpi_catalog.web import create_app


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    path = tmp_path_factory.mktemp("build") / "catalog.sqlite"
    counts, mismatches = cli.build(path, encode=fake_encode)
    return path, counts, mismatches


@pytest.fixture
def con(built):
    con = db.connect(built[0])
    yield con
    con.close()


def test_loader_makes_an_official_tag_per_concept(seed_db):
    """V3: every built database has the official tags, ML or not."""
    g = skos.load_vocab()
    expected = {skos.official_tag_id(c.name) for scheme in skos.FACETS.values() for c in skos.concepts(g, scheme)}
    con = db.connect(seed_db)
    assert {r[0] for r in con.execute("SELECT tag_id FROM tags WHERE kind = 'official'")} == expected
    assert con.execute("SELECT count(*) FROM definition_tags dt JOIN tags t USING (tag_id)"
                       " WHERE t.kind = 'official'").fetchone()[0] == 0  # attached only by the ML batch
    con.close()


def test_build_tags_every_live_definition(built, con):
    live = {r[0] for r in con.execute("SELECT definition_id FROM definitions WHERE status <> 'deprecated'")}
    for facet in ("category", "business_line"):
        tagged = {r[0] for r in con.execute(
            "SELECT dt.definition_id FROM definition_tags dt JOIN tags t USING (tag_id)"
            " WHERE dt.source = 'ml' AND dt.status = 'auto' AND t.facet = ?", (facet,))}
        assert tagged == live, facet
    path = built[0]
    ids, vectors = tagger.load_embeddings(path.with_name("embeddings.npy"))
    assert set(ids) == live and len(vectors) == len(ids)


def test_build_runs_the_unit_check(built, con):
    flagged = {r[0] for r in con.execute("SELECT a_definition_id FROM similarity_flags WHERE type = 'unit_mismatch'")}
    assert flagged == {m["definition_id"] for m in built[2]}


def test_search_index_includes_ml_tags(con):
    """The index is rebuilt after tagging, so search (F3) can match official tag labels."""
    rows = con.execute("SELECT dt.definition_id, t.label FROM definition_tags dt JOIN tags t USING (tag_id)"
                       " WHERE dt.source = 'ml'").fetchall()
    labels = dict(con.execute("SELECT definition_id, tag_labels FROM definitions_fts"))
    assert rows and all(r["label"] in labels[r["definition_id"]] for r in rows)
    definition_id, label = rows[0]
    hits = {r[0] for r in con.execute("SELECT definition_id FROM definitions_fts WHERE tag_labels MATCH ?",
                                      (f'"{label}"',))}
    assert definition_id in hits


def test_web_shows_the_ml_tags(built, con):
    r = con.execute("SELECT d.definition_id, t.label, dt.confidence FROM definition_tags dt"
                    " JOIN tags t USING (tag_id) JOIN definitions d USING (definition_id)"
                    " WHERE dt.source = 'ml' AND d.status = 'approved' LIMIT 1").fetchone()
    client = create_app({"DATABASE": str(built[0]), "TESTING": True}).test_client()
    page = client.get(f"/definitions/{r['definition_id']}").get_data(as_text=True)
    assert r["label"] in page and '<span class="auto">auto</span>' in page and f"{r['confidence']:.2f}" in page


def test_tagger_rerun_on_a_built_database_keeps_the_index_current(built, tmp_path):
    """`python -m kpi_catalog.ml.tagger` on an existing database (e.g. after app edits) re-indexes too."""
    path = tmp_path / "catalog.sqlite"
    with sqlite3.connect(built[0]) as src, sqlite3.connect(path) as dst:
        src.backup(dst)
    con = db.connect(path)
    with con:
        con.execute("DELETE FROM definition_tags WHERE source = 'ml'")
    db.build_search_index(con)
    tagger.run(con, fake_encode, tmp_path / "embeddings.npy")
    n_fts = con.execute("SELECT count(*) FROM definitions_fts WHERE tag_labels IS NOT NULL").fetchone()[0]
    n_tagged = con.execute("SELECT count(DISTINCT definition_id) FROM definition_tags").fetchone()[0]
    con.close()
    assert n_fts == n_tagged > 0
