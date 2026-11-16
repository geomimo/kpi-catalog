"""Checks on the generated Division and KPI Glossary schemes and the combined vocabulary (task V4, PRD §5)."""

from collections import Counter

import pytest
from rdflib import RDF, Graph, URIRef
from rdflib.namespace import DCTERMS, SKOS

from kpi_catalog import db
from kpi_catalog.vocab import glossary as gl
from kpi_catalog.vocab.skos import KV

STOCK_TURNOVER_RATE = "DEF-0087"  # in review; the only definition called "Stock Turnover Rate"
KATERINAS_DRAFT = "DEF-0310"  # "Stock Turn Ratio"


@pytest.fixture(scope="module")
def con(seed_db):
    c = db.connect(seed_db)
    yield c
    c.close()


@pytest.fixture(scope="module")
def g(con):
    """The combined vocabulary after a Turtle round trip, as the export (V6) will write it."""
    return Graph().parse(data=gl.combined(con).serialize(format="turtle"), format="turtle")


def kpi(slug):
    return gl.kpi_concept(slug)


def test_combined_vocabulary_has_all_six_schemes(g):
    assert set(g.subjects(RDF.type, SKOS.ConceptScheme)) == {
        KV.CategoryScheme, KV.BusinessLineScheme, KV.MeasureTypeScheme, KV.MetricTypeScheme,
        KV.DivisionScheme, KV.KpiGlossary}


def test_every_concept_has_one_label_one_definition_one_scheme(g):
    for c in g.subjects(RDF.type, SKOS.Concept):
        assert len(list(g.objects(c, SKOS.prefLabel))) == 1, c
        assert len(list(g.objects(c, SKOS.definition))) == 1, c
        assert len(list(g.objects(c, SKOS.inScheme))) == 1, c


def test_labels_are_unique_within_each_scheme(g):
    for scheme in g.subjects(RDF.type, SKOS.ConceptScheme):
        labels = Counter(str(l).casefold() for c in g.subjects(SKOS.inScheme, scheme)
                         for p in (SKOS.prefLabel, SKOS.altLabel) for l in g.objects(c, p))
        assert [l for l, n in labels.items() if n > 1] == [], scheme


def test_top_concepts_written_in_both_directions(g):
    assert set(g.subject_objects(SKOS.topConceptOf)) == {(c, s) for s, c in g.subject_objects(SKOS.hasTopConcept)}


def test_divisions(g, con):
    codes = {str(n): c for c in g.subjects(SKOS.inScheme, KV.DivisionScheme) for n in g.objects(c, SKOS.notation)}
    assert set(codes) == {r["code"] for r in con.execute("SELECT code FROM divisions")}
    assert codes["RSK"] == KV.RiskComplianceDivision
    assert all(n.datatype == KV.DivisionCode for n in g.objects(None, SKOS.notation) if str(n) in codes)


def test_one_glossary_concept_per_kpi_with_a_non_draft_definition(g, con):
    expected = {kpi(r["slug"]) for r in con.execute(
        "SELECT DISTINCT slug FROM kpis JOIN definitions USING (kpi_id) WHERE status <> 'draft'")}
    assert set(g.subjects(SKOS.inScheme, KV.KpiGlossary)) == expected


def test_stock_turnover_rate_resolves_to_inventory_turnover(g, con):
    """The V4 done-when: an in-review definition's name is a synonym; a draft's name isn't yet."""
    assert con.execute("SELECT status FROM definitions WHERE definition_id = ?",
                       (STOCK_TURNOVER_RATE,)).fetchone()["status"] == "in_review"
    [match] = gl.label_index(g)["stock turnover rate"]
    assert (match.uri, match.label, match.alt) == (str(kpi("inventory-turnover")), "Inventory Turnover", True)
    draft_name = con.execute("SELECT display_name FROM definitions WHERE definition_id = ?",
                             (KATERINAS_DRAFT,)).fetchone()["display_name"]
    assert draft_name.casefold() not in gl.label_index(g)


def test_label_index_covers_the_hand_authored_schemes_too(g):
    hits = {(m.uri, m.alt) for m in gl.label_index(g)["turnover"]}
    assert hits == {(str(kpi("turnover")), False), (str(KV.Revenue), True)}


def test_atopu_lineage(g):
    assert set(g.objects(kpi("atopu"), KV.composedOf)) == {kpi("turnover"), kpi("active-users")}


def test_related_to_is_symmetric(g):
    pairs = set(g.subject_objects(SKOS.related))
    assert pairs and pairs == {(b, a) for a, b in pairs}


def test_lineage_skips_drafts(g, con):
    """Revenue's only definition (dbt, DEF-0208) is a draft, so neither the concept nor the link to it exists yet."""
    assert (kpi("revenue"), RDF.type, SKOS.Concept) not in g
    assert (kpi("revenue-growth-mom"), KV.composedOf, kpi("revenue")) not in g


def test_subjects_come_from_official_tags_except_rejected(con):
    """The seed has no official taggings (ML adds them), so add two and roll back."""
    try:
        for tag, status in (("TAG-SupplyChain", "accepted"), ("TAG-Revenue", "rejected")):
            con.execute("INSERT INTO definition_tags (definition_id, tag_id, source, status, tagged_by, tagged_at)"
                        " VALUES ('DEF-0039', ?, 'curator', ?, 'USR-007', '2026-11-16T00:00:00Z')", (tag, status))
        subjects = set(gl.glossary_graph(con).objects(kpi("inventory-turnover"), DCTERMS.subject))
    finally:
        con.rollback()
    assert subjects == {URIRef(KV.SupplyChain)}
