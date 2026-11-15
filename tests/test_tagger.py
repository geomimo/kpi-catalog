"""Checks on the ML tagger (task M2, PRD §6) and the official tags it writes to (PRD §4.3).

A fake encoder (one fixed random vector per text) stands in for the model, so these tests don't load it.
"""

import hashlib

import numpy as np
import pytest

from kpi_catalog.ml import tagger
from kpi_catalog.vocab import skos
from kpigen.paths import SEED
from kpigen.validate import load_seed


def fake_encode(texts):
    rows = []
    for t in texts:
        rng = np.random.default_rng(int.from_bytes(hashlib.sha256(t.encode()).digest()[:8]))
        v = rng.normal(size=16)
        rows.append(v / np.linalg.norm(v))
    return np.array(rows)


@pytest.fixture(scope="module")
def g():
    return skos.load_vocab()


@pytest.fixture
def con():
    return load_seed(SEED)


def ml_tags(con):
    return con.execute("SELECT dt.definition_id, t.facet, dt.tag_id, dt.status, dt.confidence, dt.tagged_by"
                       " FROM definition_tags dt JOIN tags t USING (tag_id) WHERE dt.source = 'ml'").fetchall()


def test_official_tags_cover_category_and_business_line(con, g):
    n = len(skos.concepts(g, skos.KV.CategoryScheme)) + len(skos.business_lines(g))
    assert skos.ensure_official_tags(con, g) == n
    assert skos.ensure_official_tags(con, g) == 0  # idempotent
    facets = dict(con.execute("SELECT facet, count(*) FROM tags WHERE kind = 'official' GROUP BY facet").fetchall())
    assert facets == {"category": len(skos.concepts(g, skos.KV.CategoryScheme)),
                      "business_line": len(skos.business_lines(g))}


def test_every_live_definition_gets_a_theme_and_a_business_line(con, g):
    tagger.tag(con, fake_encode, g)
    live = {r[0] for r in con.execute("SELECT definition_id FROM definitions WHERE status <> 'deprecated'")}
    rows = ml_tags(con)
    themes = {t.name for t in skos.themes(g)}
    per_def = {}
    for def_id, facet, tag_id, status, conf, by in rows:
        assert status == "auto" and conf is not None and by is None
        per_def.setdefault(def_id, []).append((facet, tag_id))
    assert set(per_def) == live  # and so nothing on the deprecated DEF-0025 (M10)
    for tags in per_def.values():
        cats = [t for f, t in tags if f == "category"]
        assert 1 <= len(cats) <= tagger.MAX_THEMES
        assert all(t.removeprefix("TAG-") in themes for t in cats)  # themes only, never a perspective
        assert sum(f == "business_line" for f, _ in tags) == 1


def test_rerun_keeps_curator_decisions(con, g):
    tagger.tag(con, fake_encode, g)
    accepted, rejected = con.execute("SELECT definition_id, tag_id FROM definition_tags"
                                     " WHERE source = 'ml' ORDER BY definition_id, tag_id LIMIT 2").fetchall()
    con.execute("UPDATE definition_tags SET status = 'accepted' WHERE definition_id = ? AND tag_id = ?", accepted)
    con.execute("UPDATE definition_tags SET status = 'rejected' WHERE definition_id = ? AND tag_id = ?", rejected)
    n = len(ml_tags(con))
    tagger.tag(con, fake_encode, g)
    assert len(ml_tags(con)) == n
    status = dict(((d, t), s) for d, _, t, s, _, _ in ml_tags(con))
    assert status[accepted] == "accepted" and status[rejected] == "rejected"


def test_embeddings_are_saved_with_their_ids(con, g, tmp_path):
    tagger.tag(con, fake_encode, g, embeddings=tmp_path / "embeddings.npy")
    vectors = np.load(tmp_path / "embeddings.npy")
    ids = (tmp_path / "embeddings.ids.txt").read_text().split()
    assert len(ids) == len(vectors) == len({d for d, *_ in ml_tags(con)})
    assert "DEF-0025" not in ids


def test_pick_keeps_the_best_and_gates_the_rest():
    scores = np.array([0.10, 0.30, 0.20])
    assert tagger.pick(scores, k=2, tau_min=0.5) == [1]  # the best is kept even below tau_min
    assert tagger.pick(scores, k=2, tau_min=0.2) == [1, 2]
    assert tagger.pick(scores, k=1, tau_min=0.0) == [1]


def test_definition_input_matches_what_annotators_see():
    d = {"display_name": "ATOPU", "definition_text": "Turnover per active user.", "formula": "turnover / users"}
    assert tagger.definition_input(d) == "ATOPU. Turnover per active user. Formula: turnover / users."
    assert tagger.definition_input({**d, "formula": None}) == "ATOPU. Turnover per active user."
