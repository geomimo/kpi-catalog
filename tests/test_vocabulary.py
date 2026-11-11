"""Checks on the hand-authored SKOS vocabulary, vocab/kpi-vocabulary.ttl (task V1, PRD §5).

rdflib accepts any well-formed Turtle, including typos that silently create new, unconnected concepts
(`kv:Finacial`). These tests catch that and the SKOS rules that are easy to break by hand.
"""

import csv
import re
from collections import Counter, defaultdict

import pytest
from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, SKOS

from kpigen.paths import CURATION, ROOT, SCHEMA

VOCAB = ROOT / "vocab" / "kpi-vocabulary.ttl"
KV = Namespace("https://example.org/kpi-catalog/vocab/")
SCHEMES = {"Category": KV.CategoryScheme, "BusinessLine": KV.BusinessLineScheme,
           "MeasureType": KV.MeasureTypeScheme, "MetricType": KV.MetricTypeScheme}


@pytest.fixture(scope="module")
def g():
    graph = Graph()
    graph.parse(VOCAB, format="turtle")
    return graph


@pytest.fixture(scope="module")
def concepts(g):
    return set(g.subjects(RDF.type, SKOS.Concept))


def in_scheme(g, scheme):
    return set(g.subjects(SKOS.inScheme, scheme))


def schema_enum(column):
    """Values of a `column IN (...)` CHECK in schema.sql."""
    match = re.search(rf"CHECK \({column} IN \(([^)]*)\)\)", SCHEMA.read_text(encoding="utf-8"))
    return set(re.findall(r"'([^']*)'", match.group(1)))


def notations(g, scheme, datatype):
    found = defaultdict(set)
    for concept in in_scheme(g, scheme):
        for code in g.objects(concept, SKOS.notation):
            assert code.datatype == datatype, f"{concept} notation {code!r} should be typed {datatype}"
            found[str(code)].add(concept)
    return found


def test_declares_exactly_the_four_v1_schemes(g):
    assert set(g.subjects(RDF.type, SKOS.ConceptScheme)) == set(SCHEMES.values())


def test_every_kv_term_is_declared(g, concepts):
    """Catches typos: every kv: URI used as a subject or object must be a declared concept, scheme or datatype."""
    declared = concepts | set(g.subjects(RDF.type, SKOS.ConceptScheme)) | set(g.subjects(RDF.type, RDFS.Datatype))
    used = {t for triple in g for t in (triple[0], triple[2])
            if isinstance(t, URIRef) and t.startswith(str(KV))}
    assert used - declared == set()


def test_every_concept_has_one_label_one_definition_one_scheme(g, concepts):
    for c in concepts:
        pref = [l for l in g.objects(c, SKOS.prefLabel) if l.language == "en"]
        definition = [d for d in g.objects(c, SKOS.definition) if d.language == "en"]
        assert len(pref) == 1, f"{c} needs exactly one prefLabel@en"
        assert len(definition) == 1, f"{c} needs exactly one skos:definition@en (the ML encodes it)"
        assert len(set(g.objects(c, SKOS.inScheme))) == 1, f"{c} must be in exactly one scheme"


def test_every_label_has_a_language_tag(g):
    for prop in (SKOS.prefLabel, SKOS.altLabel, SKOS.definition, SKOS.scopeNote):
        untagged = [(s, o) for s, o in g.subject_objects(prop) if o.language is None]
        assert untagged == [], f"{prop} without @en"


def test_labels_are_unique_within_a_scheme(g):
    for name, scheme in SCHEMES.items():
        labels = Counter(str(l).casefold() for c in in_scheme(g, scheme)
                         for prop in (SKOS.prefLabel, SKOS.altLabel) for l in g.objects(c, prop))
        assert [l for l, n in labels.items() if n > 1] == [], f"duplicate labels in {name}"


def test_hierarchy_is_written_in_both_directions(g):
    broader = set(g.subject_objects(SKOS.broader))
    narrower = {(n, b) for b, n in g.subject_objects(SKOS.narrower)}
    assert broader == narrower, "every skos:broader needs the matching skos:narrower and vice versa"
    top_of = set(g.subject_objects(SKOS.topConceptOf))
    has_top = {(c, s) for s, c in g.subject_objects(SKOS.hasTopConcept)}
    assert top_of == has_top, "every skos:topConceptOf needs the matching skos:hasTopConcept and vice versa"


def test_top_concepts_belong_to_their_scheme_and_have_no_parent(g):
    for c, scheme in g.subject_objects(SKOS.topConceptOf):
        assert (c, SKOS.inScheme, scheme) in g
        assert list(g.objects(c, SKOS.broader)) == [], f"top concept {c} has a broader concept"


def test_category_is_perspectives_then_themes(g):
    """Two levels, one parent per theme, so T1 can derive the perspective unambiguously."""
    scheme = SCHEMES["Category"]
    tops = set(g.objects(scheme, SKOS.hasTopConcept))
    themes = in_scheme(g, scheme) - tops
    assert tops and themes
    for t in themes:
        parents = set(g.objects(t, SKOS.broader))
        assert len(parents) == 1 and parents <= tops, f"theme {t} needs exactly one perspective as parent"
        assert list(g.objects(t, SKOS.narrower)) == [], f"theme {t} should have no narrower concepts"
    for p in tops:
        assert list(g.objects(p, SKOS.narrower)), f"perspective {p} has no themes"


@pytest.mark.parametrize("name", ["BusinessLine", "MeasureType", "MetricType"])
def test_flat_schemes_have_only_top_concepts(g, name):
    scheme = SCHEMES[name]
    assert in_scheme(g, scheme) == set(g.objects(scheme, SKOS.hasTopConcept))


def test_related_is_not_used_inside_a_hierarchy(g):
    for a, b in g.subject_objects(SKOS.related):
        assert (a, SKOS.broader, b) not in g and (b, SKOS.broader, a) not in g


def test_business_lines_cover_the_curation_file(g):
    with (CURATION / "domain_to_division.csv").open(encoding="utf-8") as f:
        used = {row["business_line"] for row in csv.DictReader(f)}
    assert {KV[b] for b in used} - in_scheme(g, SCHEMES["BusinessLine"]) == set()


def test_business_line_naics_links(g):
    for c in in_scheme(g, SCHEMES["BusinessLine"]):
        for code in g.objects(c, SKOS.notation):
            assert code.datatype == KV.NAICS2022
            assert any(f"input={code}&" in str(m) for m in g.objects(c, SKOS.closeMatch)), \
                f"{c}: NAICS notation {code} without the matching closeMatch"
        assert (c, SKOS.exactMatch, None) not in g, "use closeMatch/broadMatch: a business line is not a NAICS industry"


def test_measure_types_cover_every_unit_once(g):
    found = notations(g, SCHEMES["MeasureType"], KV.UnitCode)
    assert set(found) == schema_enum("unit")
    assert all(len(cs) == 1 for cs in found.values()), "a unit maps to more than one measure type"


def test_metric_types_cover_every_metric_type_once(g):
    found = notations(g, SCHEMES["MetricType"], KV.MetricTypeCode)
    assert set(found) == schema_enum("metric_type")
    assert all(len(cs) == 1 for cs in found.values())
