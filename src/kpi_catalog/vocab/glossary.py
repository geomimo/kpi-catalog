"""Generate the Division and KPI Glossary schemes from the database, and look concepts up by label (task V4, PRD §5).

The hand-authored schemes (Category, Business line, Measure Type, Metric Type) live in vocab/kpi-vocabulary.ttl.
The other two come from the database, so they follow the data:

- **Division**: one concept per division, `skos:notation` = division code (`kv:DivisionCode`).
- **KPI Glossary**: one concept per KPI, `kpi:<slug>`. prefLabel = KPI name, altLabel = every other display name,
  `skos:definition` = the division-neutral KPI description, `dct:subject` = the official tags of its definitions
  (Category and Business line concepts; rejected tags left out), lineage as `kv:composedOf` / `kv:subsetOf` /
  `kv:cumulativeOf` (sub-properties of `skos:related`) and `related_to` as `skos:related`.

Only definitions in GLOSSARY_STATUSES count: every status except draft (decided 16 Nov). A label is a name in use,
not the definition's content, so in-review and rejected names are synonyms too; drafts stay private until
submitted. A KPI whose definitions are all drafts has no glossary concept yet.

`combined(con)` is the whole vocabulary; `label_index(g)` maps every pref- and altLabel to its concepts, for search
expansion (W5) and the vocabulary browser (W9).
"""

import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass

from rdflib import RDF, Graph, Literal, Namespace, URIRef
from rdflib.namespace import DCTERMS, SKOS

from kpi_catalog.vocab.skos import KV, load_vocab

KPI = Namespace("https://example.org/kpi-catalog/kpi/")
GLOSSARY_STATUSES = ("approved", "deprecated", "in_review", "rejected")
LINEAGE = {"composed_of": KV.composedOf, "subset_of": KV.subsetOf, "cumulative_of": KV.cumulativeOf}


@dataclass(frozen=True)
class LabelMatch:
    uri: str
    scheme: str  # local name of the concept's scheme, e.g. "KpiGlossary"
    label: str  # the concept's prefLabel
    matched: str  # the label that matched, as written in the vocabulary
    alt: bool  # True if `matched` is an altLabel


def division_concept(name: str) -> URIRef:
    """`Risk & Compliance` → kv:RiskComplianceDivision (like the Category's `...Perspective` suffix)."""
    return KV["".join(w[0].upper() + w[1:] for w in re.findall(r"[A-Za-z0-9]+", name)) + "Division"]


def kpi_concept(slug: str) -> URIRef:
    return KPI[slug]


def _new_graph() -> Graph:
    g = Graph()
    for prefix, ns in (("skos", SKOS), ("dct", DCTERMS), ("kv", KV), ("kpi", KPI)):
        g.bind(prefix, ns)
    return g


def _scheme(g: Graph, scheme: URIRef, title: str, description: str) -> None:
    g.add((scheme, RDF.type, SKOS.ConceptScheme))
    g.add((scheme, DCTERMS.title, Literal(title, lang="en")))
    g.add((scheme, DCTERMS.description, Literal(description, lang="en")))


def _concept(g: Graph, c: URIRef, scheme: URIRef, label: str, definition: str) -> None:
    """A concept of a flat scheme: every concept is a top concept, written in both directions."""
    g.add((c, RDF.type, SKOS.Concept))
    g.add((c, SKOS.inScheme, scheme))
    g.add((c, SKOS.topConceptOf, scheme))
    g.add((scheme, SKOS.hasTopConcept, c))
    g.add((c, SKOS.prefLabel, Literal(label, lang="en")))
    g.add((c, SKOS.definition, Literal(definition, lang="en")))


def divisions_graph(con: sqlite3.Connection) -> Graph:
    g = _new_graph()
    _scheme(g, KV.DivisionScheme, "Division",
            "Konfusio's divisions. Each division keeps its own definitions of a KPI.")
    for d in con.execute("SELECT code, name, description FROM divisions ORDER BY division_id"):
        c = division_concept(d["name"])
        _concept(g, c, KV.DivisionScheme, d["name"], d["description"])
        g.add((c, SKOS.notation, Literal(d["code"], datatype=KV.DivisionCode)))
    return g


def glossary_graph(con: sqlite3.Connection) -> Graph:
    g = _new_graph()
    _scheme(g, KV.KpiGlossary, "KPI Glossary",
            "One concept per KPI: its name, the names divisions use for it, its subjects and its lineage.")
    marks = ", ".join("?" * len(GLOSSARY_STATUSES))

    names = defaultdict(list)  # slug → display names, in definition order
    for r in con.execute(f"SELECT k.slug, d.display_name FROM definitions d JOIN kpis k USING (kpi_id)"
                         f" WHERE d.status IN ({marks}) ORDER BY d.definition_id", GLOSSARY_STATUSES):
        names[r["slug"]].append(r["display_name"])
    for k in con.execute("SELECT slug, name, description FROM kpis ORDER BY kpi_id"):
        if k["slug"] not in names:
            continue
        c = kpi_concept(k["slug"])
        _concept(g, c, KV.KpiGlossary, k["name"], k["description"])
        seen = {k["name"].casefold()}
        for name in names[k["slug"]]:
            if name.casefold() not in seen:  # SKOS: pref- and altLabels are disjoint, one altLabel per spelling
                seen.add(name.casefold())
                g.add((c, SKOS.altLabel, Literal(name, lang="en")))

    for r in con.execute(f"SELECT DISTINCT k.slug, t.concept_uri FROM definition_tags dt"
                         f" JOIN tags t USING (tag_id) JOIN definitions d USING (definition_id) JOIN kpis k USING (kpi_id)"
                         f" WHERE t.kind = 'official' AND dt.status <> 'rejected' AND d.status IN ({marks})",
                         GLOSSARY_STATUSES):
        g.add((kpi_concept(r["slug"]), DCTERMS.subject, URIRef(r["concept_uri"])))

    for r in con.execute(f"SELECT DISTINCT kf.slug AS a, kt.slug AS b, r.relationship_type AS type"
                         f" FROM kpi_relationships r"
                         f" JOIN definitions df ON df.definition_id = r.from_definition_id"
                         f" JOIN definitions dt ON dt.definition_id = r.to_definition_id"
                         f" JOIN kpis kf ON kf.kpi_id = df.kpi_id JOIN kpis kt ON kt.kpi_id = dt.kpi_id"
                         f" WHERE df.status IN ({marks}) AND dt.status IN ({marks}) AND kf.kpi_id <> kt.kpi_id",
                         GLOSSARY_STATUSES * 2):
        a, b = kpi_concept(r["a"]), kpi_concept(r["b"])
        if r["type"] == "related_to":  # symmetric: written both ways, like the hierarchies
            g.add((a, SKOS.related, b))
            g.add((b, SKOS.related, a))
        else:
            g.add((a, LINEAGE[r["type"]], b))
    return g


def combined(con: sqlite3.Connection, seed: Graph | None = None) -> Graph:
    """The whole vocabulary: the hand-authored TTL plus the Division and KPI Glossary schemes from `con`."""
    g = _new_graph()
    for part in (seed if seed is not None else load_vocab(), divisions_graph(con), glossary_graph(con)):
        g += part
    return g


def label_index(g: Graph) -> dict[str, list[LabelMatch]]:
    """Case-folded pref- or altLabel → the concepts that carry it (any scheme). `"stock turnover rate"` →
    `[LabelMatch(kpi:inventory-turnover, "KpiGlossary", "Inventory Turnover", "Stock Turnover Rate", alt=True)]`."""
    index = defaultdict(list)
    for c in g.subjects(RDF.type, SKOS.Concept):
        scheme = str(g.value(c, SKOS.inScheme)).removeprefix(str(KV))
        pref = str(g.value(c, SKOS.prefLabel))
        for prop, alt in ((SKOS.prefLabel, False), (SKOS.altLabel, True)):
            for label in g.objects(c, prop):
                index[str(label).casefold()].append(LabelMatch(str(c), scheme, pref, str(label), alt))
    return {k: sorted(v, key=lambda m: (m.alt, m.uri)) for k, v in index.items()}
