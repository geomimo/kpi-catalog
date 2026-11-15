"""ML tagging (PRD §6): T1 theme and T2 business line (task M2) and the T3 unit check (task M4), no training.

Each definition (`display_name`, `definition_text`, `formula`) and each concept (prefLabel, altLabels,
skos:definition) is encoded with all-MiniLM-L6-v2. A definition gets its most similar theme, plus a second theme
if that one also scores at least `TAU_MIN`, and its most similar business line. The best concept is always kept,
however low its score, so every definition gets tagged; low scores come first in the curator's queue.

Rows go to `definition_tags` with `source = ml`, the cosine similarity as `confidence`, and `status = auto`.
Deprecated definitions are skipped (M10). A rerun replaces the `auto` rows and keeps every tag a curator has
accepted or rejected. The definition embeddings are saved as `.npy` next to the database, for the similarity
flags (M7) and the submit suggestions (M8).

T3 predicts each definition's measure type from its `K_UNIT` most similar other definitions: their measure types
(looked up from their units) vote, weighted by similarity. If at least `MIN_SHARE` of the vote goes to a measure
type other than the one the definition's own unit gives, it gets an open `unit_mismatch` flag with that share as
its score. Comparing the text with the Measure Type concepts directly was tried first and rejected: MiniLM
captures what a text is about, not what kind of number it gives, so it flagged 33 of 107 definitions (PRD §6).

    uv run python -m kpi_catalog.ml.tagger [--db instance/catalog.sqlite]
    uv run python -m kpi_catalog.ml.tagger --from-seed   # build the database from data/seed first (until W2)
"""

import argparse
import sqlite3
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from kpi_catalog.vocab import skos
from kpigen.paths import ROOT, SEED

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DB = ROOT / "instance" / "catalog.sqlite"
MAX_THEMES = 2
TAU_MIN = 0.54  # a second theme needs at least this score; tuned on the T1 gold set by M5 (PRD §14 Q3)
K_UNIT = 5  # neighbours that vote on a definition's measure type (T3)
MIN_SHARE = 0.8  # share of the vote that must disagree with the unit before a unit_mismatch flag is raised

Encoder = Callable[[Sequence[str]], np.ndarray]  # texts -> unit-length row vectors


def sentence_encoder(model: str = MODEL) -> Encoder:
    from sentence_transformers import SentenceTransformer  # slow import, only when really encoding
    st = SentenceTransformer(model)
    return lambda texts: st.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)


def definition_input(d) -> str:
    """The tagger's view of a definition; annotators see exactly these fields (data/gold/README.md)."""
    parts = [d["display_name"], d["definition_text"]]
    if d["formula"]:
        parts.append(f"Formula: {d['formula']}")
    return ". ".join(p.strip().rstrip(".") for p in parts) + "."


def concept_input(c: skos.Concept) -> str:
    return "; ".join([c.label, *c.alt_labels]) + ". " + c.definition


def pick(scores: np.ndarray, k: int, tau_min: float) -> list[int]:
    """Indices of the best concept and of up to k-1 more that score at least tau_min, best first."""
    order = np.argsort(-scores, kind="stable")
    return [int(order[0])] + [int(i) for i in order[1:k] if scores[i] >= tau_min]


def tag(con: sqlite3.Connection, encode: Encoder, g=None, embeddings: Path | None = None,
        now: str | None = None, tau_min: float = TAU_MIN) -> dict[str, Counter]:
    """Write theme and business-line rows for every non-deprecated definition. Returns tag counts per facet."""
    g = g if g is not None else skos.load_vocab()
    now = now or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    skos.ensure_official_tags(con, g, now)
    cur = con.cursor()
    cur.row_factory = sqlite3.Row  # on a cursor, so the caller's connection is left as it was
    defs = cur.execute("SELECT definition_id, display_name, definition_text, formula FROM definitions"
                       " WHERE status <> 'deprecated' ORDER BY definition_id").fetchall()
    vectors = encode([definition_input(d) for d in defs])
    if embeddings is not None:
        embeddings.parent.mkdir(parents=True, exist_ok=True)
        np.save(embeddings, vectors)
        embeddings.with_suffix(".ids.txt").write_text("".join(f"{d['definition_id']}\n" for d in defs))

    tasks = {"category": (skos.themes(g), MAX_THEMES), "business_line": (skos.business_lines(g), 1)}
    con.execute("DELETE FROM definition_tags WHERE source = 'ml' AND status = 'auto'")
    counts = {}
    for facet, (cands, k) in tasks.items():
        scores = vectors @ encode([concept_input(c) for c in cands]).T
        counts[facet] = Counter()
        for d, row in zip(defs, scores):
            for i in pick(row, k, tau_min):
                cur = con.execute("INSERT OR IGNORE INTO definition_tags"
                                  " (definition_id, tag_id, source, confidence, status, tagged_by, tagged_at)"
                                  " VALUES (?, ?, 'ml', ?, 'auto', NULL, ?)",
                                  (d["definition_id"], skos.official_tag_id(cands[i].name),
                                   round(float(row[i]), 4), now))
                if cur.rowcount:  # 0 when a curator already accepted or rejected this tag
                    counts[facet][cands[i].name] += 1
    con.commit()
    return counts


def load_embeddings(path: Path) -> tuple[list[str], np.ndarray]:
    """The definition IDs and vectors that `tag` saved."""
    return path.with_suffix(".ids.txt").read_text().split(), np.load(path)


def unit_flag_id(definition_id: str) -> str:
    return f"FLAG-UNIT-{definition_id}"


def check_units(con: sqlite3.Connection, ids: Sequence[str], vectors: np.ndarray, g=None,
                k: int = K_UNIT, min_share: float = MIN_SHARE) -> list[dict]:
    """T3: raise a unit_mismatch flag where a definition's neighbours disagree with its unit. Returns the mismatches.

    A rerun replaces the open flags and keeps every flag the Admin has already resolved (dismissed, fixed).
    """
    g = g if g is not None else skos.load_vocab()
    lookup = skos.measure_types(g)
    units = dict(con.execute("SELECT definition_id, unit FROM definitions"))
    own = [lookup[units[i]].name for i in ids]
    sims = vectors @ vectors.T
    np.fill_diagonal(sims, -np.inf)  # a definition doesn't vote for itself
    found = []
    for a, row in enumerate(sims):
        votes = Counter()
        for j in np.argsort(-row, kind="stable")[:k]:
            votes[own[j]] += max(float(row[j]), 0.0)
        total = sum(votes.values())
        if not total:
            continue
        predicted, weight = votes.most_common(1)[0]
        share = weight / total
        if predicted != own[a] and share >= min_share:
            found.append({"definition_id": ids[a], "unit": units[ids[a]], "measure_type": own[a],
                          "predicted": predicted, "share": round(share, 4)})
    con.execute("DELETE FROM similarity_flags WHERE type = 'unit_mismatch' AND status = 'open'")
    con.executemany("INSERT OR IGNORE INTO similarity_flags (flag_id, type, a_definition_id, b_definition_id, score,"
                    " status, resolved_by, resolved_at) VALUES (?, 'unit_mismatch', ?, NULL, ?, 'open', NULL, NULL)",
                    [(unit_flag_id(f["definition_id"]), f["definition_id"], f["share"]) for f in found])
    con.commit()
    return found


def build_from_seed(db: Path, seed_dir: Path = SEED) -> None:
    """Stopgap until the loader (W2, db.py) exists: schema.sql + the seed CSVs, written to `db`."""
    from kpigen.validate import load_seed
    mem = load_seed(seed_dir)
    mem.commit()  # load_seed leaves its inserts in an open transaction, which would block the backup
    db.parent.mkdir(parents=True, exist_ok=True)
    db.unlink(missing_ok=True)
    with sqlite3.connect(db) as out:
        mem.backup(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m kpi_catalog.ml.tagger", description=__doc__.splitlines()[0])
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--from-seed", action="store_true", help="(re)build the database from data/seed first")
    args = parser.parse_args(argv)
    if args.from_seed:
        build_from_seed(args.db)
    elif not args.db.exists():
        print(f"{args.db} doesn't exist: build it with the loader, or pass --from-seed")
        return 1
    con = sqlite3.connect(args.db)
    con.execute("PRAGMA foreign_keys = ON")
    g = skos.load_vocab()
    embeddings = args.db.with_name("embeddings.npy")
    counts = tag(con, sentence_encoder(), g, embeddings=embeddings)
    for facet, c in counts.items():
        print(f"{facet}: {sum(c.values())} auto tags; {dict(c.most_common())}")
    mismatches = check_units(con, *load_embeddings(embeddings), g)
    print(f"unit check: {len(mismatches)} unit_mismatch flag(s)")
    for f in mismatches:
        print(f"  {f['definition_id']}: unit {f['unit']} ({f['measure_type']}), neighbours say {f['predicted']}"
              f" ({f['share']:.0%})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
