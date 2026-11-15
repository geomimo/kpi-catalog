"""KPI pages (PRD §9 F4–F7, §10; tasks W6–W8): KPI concept page, definition detail page, compare page.

Every query that lists, counts or opens a definition applies `auth.visible()` (PRD §4.5), including the far
end of a lineage link, so a draft never shows up, not even in a count.
"""

import sqlite3

from flask import abort, render_template, request, url_for

from kpi_catalog.auth import current_user, has_permission, visible
from kpi_catalog.db import get_db
from kpi_catalog.web.home import remember_kpi

STATUS_LABELS = {
    "approved": "Approved", "in_review": "In review", "draft": "Draft", "rejected": "Rejected", "deprecated": "Deprecated",
}
DECISION_LABELS = {"approved": "Approved", "rejected": "Rejected", "changes_requested": "Changes requested"}
FACET_LABELS = {"category": "Categories", "business_line": "Business line"}

# Lineage (Dependencies tab): "from" is built from "to".
LINEAGE_TYPES = ("composed_of", "cumulative_of")
# Related KPIs tab: (label when this KPI is "from", label when it is "to").
RELATED_LABELS = {
    "related_to": ("Related to", "Related to"),
    "subset_of": ("Subset of", "Has subset"),
    "cumulative_of": ("Cumulative of", "Has cumulative version"),
}

KPI_TABS = [("overview", "Overview"), ("definitions", "Definitions"), ("dependencies", "Dependencies"),
            ("related", "Related KPIs")]
DEFINITION_TABS = [("overview", "Overview"), ("definition", "Definition"), ("dependencies", "Dependencies"),
                   ("usage", "Usage"), ("history", "History")]

# One definition with its division, owner and KPI. The definition's alias is always `d`.
DEF_COLUMNS = """
    d.definition_id, d.kpi_id, d.division_id, d.display_name, d.definition_text, d.metric_type, d.formula, d.unit,
    d.grain, d.source_table, d.source_column, d.related_columns, d.status, d.version, d.superseded_by_id,
    d.owner_user_id, d.updated_at,
    v.code AS division_code, v.name AS division_name, u.full_name AS owner_name, u.job_title AS owner_title,
    k.slug AS kpi_slug, k.name AS kpi_name"""
DEF_JOINS = """
    JOIN divisions v ON v.division_id = d.division_id
    JOIN users u ON u.user_id = d.owner_user_id
    JOIN kpis k ON k.kpi_id = d.kpi_id"""


def _marks(values) -> str:
    return ", ".join("?" * len(values))


def _tab(tabs) -> str:
    tab = request.args.get("tab", tabs[0][0])
    return tab if tab in dict(tabs) else tabs[0][0]


# ---- Queries ------------------------------------------------------------------------------------------------

def get_kpi(con: sqlite3.Connection, slug: str):
    return con.execute("SELECT kpi_id, slug, name, description FROM kpis WHERE slug = ?", (slug,)).fetchone()


def kpi_definitions(con: sqlite3.Connection, kpi_id: str) -> list[dict]:
    """The KPI's definitions the visitor may see, by division, deprecated ones last within a division."""
    cond, params = visible("d")
    rows = con.execute(
        f"""SELECT {DEF_COLUMNS} FROM definitions d {DEF_JOINS}
             WHERE d.kpi_id = ? AND {cond}
             ORDER BY v.name, d.status = 'deprecated', d.display_name, d.definition_id""",
        [kpi_id, *params],
    )
    return [dict(r) for r in rows]


def get_definition(con: sqlite3.Connection, definition_id: str) -> dict | None:
    """One definition, or None if it doesn't exist or the visitor may not see it."""
    cond, params = visible("d")
    row = con.execute(f"SELECT {DEF_COLUMNS} FROM definitions d {DEF_JOINS} WHERE d.definition_id = ? AND {cond}",
                      [definition_id, *params]).fetchone()
    return dict(row) if row else None


def official_tags(con: sqlite3.Connection, def_ids: list[str]) -> dict[str, list[dict]]:
    """Official (SKOS) tags on these definitions, grouped by facet label. Rejected tags are hidden; a tag counts
    as "auto" (unchecked ML) unless a curator accepted it on at least one of the definitions."""
    if not def_ids:
        return {}
    rows = con.execute(
        f"""SELECT t.tag_id, t.label, t.facet, t.concept_uri,
                   max(dt.status = 'accepted') AS accepted, max(dt.confidence) AS confidence
              FROM definition_tags dt JOIN tags t ON t.tag_id = dt.tag_id
             WHERE t.kind = 'official' AND dt.status != 'rejected' AND dt.definition_id IN ({_marks(def_ids)})
             GROUP BY t.tag_id ORDER BY t.facet, t.label""",
        def_ids,
    )
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(FACET_LABELS.get(r["facet"], r["facet"]), []).append({
            "label": r["label"],
            "auto": not r["accepted"],
            "confidence": r["confidence"],
            "href": url_for("concept", concept_id=r["concept_uri"].rstrip("/").rsplit("/", 1)[-1]),
        })
    return groups


def community_tags(con: sqlite3.Connection, def_ids: list[str]) -> list[dict]:
    """Community tags on these definitions: {label, count}, count = how many of the definitions carry it."""
    if not def_ids:
        return []
    rows = con.execute(
        f"""SELECT t.label, count(DISTINCT dt.definition_id) AS count
              FROM definition_tags dt JOIN tags t ON t.tag_id = dt.tag_id
             WHERE t.kind = 'community' AND dt.definition_id IN ({_marks(def_ids)})
             GROUP BY t.tag_id ORDER BY count DESC, t.label""",
        def_ids,
    )
    return [dict(r) for r in rows]


def lineage(con: sqlite3.Connection, def_ids: list[str]) -> dict[str, dict[str, list[dict]]]:
    """Per definition: "built_from" (what it is computed from) and "feeds" (what is computed from it), each a list
    of the linked definition plus relationship_type, role, alias and offset_window. Links to definitions the
    visitor may not see are left out."""
    result = {i: {"built_from": [], "feeds": []} for i in def_ids}
    if not def_ids:
        return result
    cond, params = visible("d")
    for key, this_end, other_end in (("built_from", "from_definition_id", "to_definition_id"),
                                     ("feeds", "to_definition_id", "from_definition_id")):
        rows = con.execute(
            f"""SELECT r.{this_end} AS this_id, r.relationship_type, r.role, r.alias, r.offset_window, {DEF_COLUMNS}
                  FROM kpi_relationships r JOIN definitions d ON d.definition_id = r.{other_end} {DEF_JOINS}
                 WHERE r.{this_end} IN ({_marks(def_ids)})
                   AND r.relationship_type IN ({_marks(LINEAGE_TYPES)}) AND {cond}
                 ORDER BY CASE r.role WHEN 'numerator' THEN 0 WHEN 'denominator' THEN 1 WHEN 'input' THEN 2
                          ELSE 3 END, k.name, v.name""",
            [*def_ids, *LINEAGE_TYPES, *params],
        )
        for r in rows:
            result[r["this_id"]][key].append(dict(r))
    return result


def related_kpis(con: sqlite3.Connection, kpi_id: str, def_ids: list[str]) -> list[dict]:
    """Other KPIs linked to this one through related_to / subset_of / cumulative_of between visible definitions:
    {slug, name, relation}, one row per KPI and relation."""
    if not def_ids:
        return []
    cond, params = visible("d")
    found: dict[tuple, dict] = {}
    for this_end, other_end, side in (("from_definition_id", "to_definition_id", 0),
                                      ("to_definition_id", "from_definition_id", 1)):
        rows = con.execute(
            f"""SELECT DISTINCT r.relationship_type, k.slug, k.name
                  FROM kpi_relationships r JOIN definitions d ON d.definition_id = r.{other_end}
                  JOIN kpis k ON k.kpi_id = d.kpi_id
                 WHERE r.{this_end} IN ({_marks(def_ids)}) AND d.kpi_id != ?
                   AND r.relationship_type IN ({_marks(RELATED_LABELS)}) AND {cond}""",
            [*def_ids, kpi_id, *RELATED_LABELS, *params],
        )
        for r in rows:
            relation = RELATED_LABELS[r["relationship_type"]][side]
            found[(r["slug"], relation)] = {"slug": r["slug"], "name": r["name"], "relation": relation}
    return sorted(found.values(), key=lambda x: (x["name"], x["relation"]))


def diverges(con: sqlite3.Connection, def_ids: list[str]) -> bool:
    """True if an open "definitions_diverge" flag (PRD §4.4; from M7, hand-inserted until then) involves one of
    these definitions."""
    if not def_ids:
        return False
    return con.execute(
        f"""SELECT 1 FROM similarity_flags
             WHERE type = 'definitions_diverge' AND status = 'open'
               AND (a_definition_id IN ({_marks(def_ids)}) OR b_definition_id IN ({_marks(def_ids)}))
             LIMIT 1""",
        [*def_ids, *def_ids],
    ).fetchone() is not None


def usage(con: sqlite3.Connection, definition_id: str) -> list[dict]:
    """Dashboards and reports that use the definition (assets are readable by everyone)."""
    rows = con.execute(
        """SELECT a.asset_id, a.name, a.asset_type, a.tool, a.url, a.description, v.name AS division_name
             FROM asset_definitions ad JOIN assets a ON a.asset_id = ad.asset_id
             JOIN divisions v ON v.division_id = a.division_id
            WHERE ad.definition_id = ? ORDER BY a.name""",
        (definition_id,),
    )
    return [dict(r) for r in rows]


def review_history(con: sqlite3.Connection, definition_id: str) -> list[dict]:
    rows = con.execute(
        """SELECT r.decision, r.comment, r.reviewed_at, u.full_name AS reviewer_name, u.job_title AS reviewer_title
             FROM reviews r JOIN users u ON u.user_id = r.reviewer_user_id
            WHERE r.definition_id = ? ORDER BY r.reviewed_at DESC, r.review_id DESC""",
        (definition_id,),
    )
    return [dict(r) for r in rows]


def version_chain(con: sqlite3.Connection, definition: dict) -> list[dict]:
    """The definition's versions through superseded_by_id, oldest first (only those the visitor may see)."""
    cond, params = visible("d")
    chain, seen = [definition], {definition["definition_id"]}
    current = definition
    while True:  # back: who was superseded by the current one
        row = con.execute(f"SELECT {DEF_COLUMNS} FROM definitions d {DEF_JOINS} WHERE d.superseded_by_id = ? AND {cond}",
                          [current["definition_id"], *params]).fetchone()
        if row is None or row["definition_id"] in seen:
            break
        current = dict(row)
        seen.add(current["definition_id"])
        chain.insert(0, current)
    current = definition
    while current["superseded_by_id"] and current["superseded_by_id"] not in seen:  # forward
        nxt = get_definition(con, current["superseded_by_id"])
        if nxt is None:
            break
        seen.add(nxt["definition_id"])
        chain.append(nxt)
        current = nxt
    return chain


def synonyms(kpi_name: str, definitions: list[dict]) -> list[str]:
    """Every other label the divisions use for this KPI."""
    names = {d["display_name"] for d in definitions if d["display_name"].casefold() != kpi_name.casefold()}
    return sorted(names, key=str.casefold)


def division_cards(definitions: list[dict]) -> list[dict]:
    """One card per division with a visible definition, linking to its first current (non-deprecated) one."""
    cards: dict[str, dict] = {}
    for d in definitions:
        card = cards.setdefault(d["division_id"], {"name": d["division_name"], "definitions": []})
        card["definitions"].append(d)
    for card in cards.values():
        current = [d for d in card["definitions"] if d["status"] != "deprecated"] or card["definitions"]
        card["href"] = url_for("definition", definition_id=current[0]["definition_id"])
        card["count"] = len(card["definitions"])
    return sorted(cards.values(), key=lambda c: c["name"])


def column_labels(columns: list[dict], kpi_name: str) -> list[dict]:
    """Compare-page headers: the division, plus the display name when a division has several columns or uses its
    own name, plus the ID when that is still ambiguous."""
    per_division: dict[str, int] = {}
    per_name: dict[tuple, int] = {}
    for c in columns:
        per_division[c["division_id"]] = per_division.get(c["division_id"], 0) + 1
        per_name[(c["division_id"], c["display_name"])] = per_name.get((c["division_id"], c["display_name"]), 0) + 1
    labels = []
    for c in columns:
        sub = None
        if per_division[c["division_id"]] > 1 or c["display_name"].casefold() != kpi_name.casefold():
            sub = c["display_name"]
        if per_name[(c["division_id"], c["display_name"])] > 1:
            sub = f"{c['display_name']} ({c['definition_id']})"
        labels.append({"title": c["division_name"], "sub": sub})
    return labels


# ---- Views --------------------------------------------------------------------------------------------------

def _kpi_or_404(con, slug):
    kpi = get_kpi(con, slug)
    if kpi is None:
        abort(404)
    definitions = kpi_definitions(con, kpi["kpi_id"])
    if not definitions:  # nothing the visitor may see: the KPI isn't published yet
        abort(404)
    return dict(kpi), definitions


def kpi_page(slug: str):
    con = get_db()
    kpi, definitions = _kpi_or_404(con, slug)
    remember_kpi(slug)
    ids = [d["definition_id"] for d in definitions]
    by_id = {d["definition_id"]: d for d in definitions}
    for d in definitions:
        if d["superseded_by_id"]:
            d["successor"] = by_id.get(d["superseded_by_id"]) or get_definition(con, d["superseded_by_id"])
    tab = _tab(KPI_TABS)
    return render_template(
        "kpi.html",
        title=kpi["name"],
        kpi=kpi,
        definitions=definitions,
        tab=tab,
        tabs=KPI_TABS,
        diverges=diverges(con, ids),
        official=official_tags(con, ids) if tab == "overview" else {},
        community=community_tags(con, ids) if tab == "overview" else [],
        synonyms=synonyms(kpi["name"], definitions),
        divisions=division_cards(definitions),
        lineage=lineage(con, ids) if tab == "dependencies" else {},
        related=related_kpis(con, kpi["kpi_id"], ids) if tab == "related" else [],
        status_labels=STATUS_LABELS,
    )


def definition_page(definition_id: str):
    con = get_db()
    d = get_definition(con, definition_id)
    if d is None:
        abort(404)
    tab = _tab(DEFINITION_TABS)
    ids = [definition_id]
    return render_template(
        "definition.html",
        title=f"{d['kpi_name']} – {d['division_name']}",
        d=d,
        can_edit=d["status"] == "draft" and has_permission(current_user(), "definition.propose", d["division_id"]),
        tab=tab,
        tabs=DEFINITION_TABS,
        official=official_tags(con, ids),
        community=community_tags(con, ids),
        lineage=lineage(con, ids)[definition_id] if tab == "dependencies" else {},
        usage=usage(con, definition_id) if tab == "usage" else [],
        reviews=review_history(con, definition_id) if tab == "history" else [],
        versions=version_chain(con, d) if tab == "history" else [],
        status_labels=STATUS_LABELS,
        decision_labels=DECISION_LABELS,
    )


COMPARE_ROWS = [
    ("Definition", "definition_text"), ("Formula", "formula"), ("Unit", "unit"), ("Grain", "grain"),
    ("Data Source", "source_table"), ("Owner", "owner_name"), ("Status", "status"),
]


def compare_page(slug: str):
    con = get_db()
    kpi, definitions = _kpi_or_404(con, slug)
    by_id = {d["definition_id"]: d for d in definitions}
    if "d" in request.args:  # explicit selection (possibly empty after removing every column)
        chosen = list(dict.fromkeys(x for x in request.args.getlist("d") if x in by_id))
    else:
        chosen = list(by_id)
    columns = [by_id[x] for x in chosen]

    def link(ids):
        return url_for("compare", slug=slug, d=ids or "")

    selected = [{**c, "remove_href": link([x for x in chosen if x != c["definition_id"]])} for c in columns]
    available = [{**d, "add_href": link([*chosen, d["definition_id"]])} for d in definitions
                 if d["definition_id"] not in chosen]
    rows = []
    for label, field in COMPARE_ROWS:
        values = [c[field] for c in columns]
        rows.append({"label": label, "field": field, "cells": values, "differs": len(columns) > 1 and len(set(values)) > 1})
    return render_template(
        "compare.html",
        title=f"Compare definitions: {kpi['name']}",
        kpi=kpi,
        columns=columns,
        labels=column_labels(columns, kpi["name"]),
        selected=selected,
        available=available,
        rows=rows,
        status_labels=STATUS_LABELS,
    )
