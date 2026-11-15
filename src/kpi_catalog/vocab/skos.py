"""Read the SKOS vocabulary (PRD §5) and create the official tags from it.

Official tags are the Category and Business line concepts as rows of `tags` (`kind = official`), so that
definitions can be tagged with them. Their IDs are `TAG-<concept local name>` (e.g. `TAG-Revenue`): stable, and
apart from the numbered community tags of the seed (`TAG-001`, ...).
"""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import SKOS

from kpigen.paths import ROOT

VOCAB = ROOT / "vocab" / "kpi-vocabulary.ttl"
KV = Namespace("https://example.org/kpi-catalog/vocab/")
FACETS = {"category": KV.CategoryScheme, "business_line": KV.BusinessLineScheme}


@dataclass(frozen=True)
class Concept:
    name: str  # local name, the stable ID (e.g. "Revenue")
    uri: str
    label: str
    alt_labels: tuple[str, ...]
    definition: str
    broader: str | None  # local name of the broader concept, if any


def local(uri) -> str:
    return str(uri).removeprefix(str(KV))


def load_vocab(vocab: Path = VOCAB) -> Graph:
    g = Graph()
    g.parse(vocab, format="turtle")
    return g


def concepts(g: Graph, scheme: URIRef) -> list[Concept]:
    """Every concept of a scheme, sorted by local name."""
    out = []
    for c in g.subjects(SKOS.inScheme, scheme):
        broader = g.value(c, SKOS.broader)
        out.append(Concept(name=local(c), uri=str(c), label=str(g.value(c, SKOS.prefLabel)),
                           alt_labels=tuple(sorted(str(a) for a in g.objects(c, SKOS.altLabel))),
                           definition=str(g.value(c, SKOS.definition)),
                           broader=local(broader) if broader is not None else None))
    return sorted(out, key=lambda c: c.name)


def themes(g: Graph) -> list[Concept]:
    """The Category themes (the narrower concepts of the Balanced Scorecard perspectives), the T1 candidates."""
    return [c for c in concepts(g, KV.CategoryScheme) if c.broader is not None]


def business_lines(g: Graph) -> list[Concept]:
    return concepts(g, KV.BusinessLineScheme)


def official_tag_id(concept_name: str) -> str:
    return f"TAG-{concept_name}"


def ensure_official_tags(con: sqlite3.Connection, g: Graph, now: str | None = None) -> int:
    """Insert an official tag for every Category and Business line concept that has none yet. Returns the count."""
    now = now or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    before = con.total_changes
    for facet, scheme in FACETS.items():
        for c in concepts(g, scheme):
            con.execute("INSERT OR IGNORE INTO tags (tag_id, kind, label, facet, concept_uri, created_by, created_at)"
                        " VALUES (?, 'official', ?, ?, ?, NULL, ?)",
                        (official_tag_id(c.name), c.label, facet, c.uri, now))
    return con.total_changes - before
