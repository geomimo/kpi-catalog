"""Home page (W10, PRD §10): search box, "Browse by Category" tiles, "Recently Viewed" KPIs.

"Recently Viewed" lives in the Flask session (signed cookie): the last RECENT_MAX KPI slugs opened, newest
first, no duplicates. Nothing is stored in the database.
"""

import sqlite3

from flask import render_template, session, url_for

from kpi_catalog.auth import visible
from kpi_catalog.db import get_db

RECENT_KEY = "recent_kpis"
RECENT_MAX = 5
TILE_LIMIT = 4

# Decoration only: an icon per tile key. A key not listed here gets DEFAULT_ICON, so new divisions (or, later,
# SKOS concepts) need no code change.
TILE_ICONS = {
    "FIN": "coins", "COM": "shopping-cart", "MKT": "speakerphone", "PRD": "package",
    "OPS": "settings", "PPL": "users", "RSK": "shield-check", "DAT": "database",
}
DEFAULT_ICON = "chart-bar"


def category_tiles(con: sqlite3.Connection, limit: int = TILE_LIMIT) -> list[dict]:
    """Entry points for "Browse by Category": the `limit` groups with the most KPIs, largest first.

    Each tile is {key, label, count, icon, href}. For now a group is a division and `count` is the number of
    distinct KPIs with an approved definition there. Only this query needs to change to switch the tiles to the
    SKOS Category concepts once official tags exist (V3/M2); the template only reads the tile fields.
    """
    rows = con.execute(
        """
        SELECT v.code AS key, v.name AS label, count(DISTINCT d.kpi_id) AS count
          FROM divisions v
          JOIN definitions d ON d.division_id = v.division_id AND d.status = 'approved'
         GROUP BY v.division_id
         ORDER BY count DESC, v.name
         LIMIT ?
        """,
        (limit,),
    )
    return [
        {**dict(r), "icon": TILE_ICONS.get(r["key"], DEFAULT_ICON), "href": url_for("browse", division=r["key"])}
        for r in rows
    ]


def remember_kpi(slug: str) -> None:
    """Put a KPI at the front of the session's recently-viewed list (only if the KPI exists)."""
    if get_db().execute("SELECT 1 FROM kpis WHERE slug = ?", (slug,)).fetchone() is None:
        return
    recent = [s for s in session.get(RECENT_KEY, []) if s != slug]
    session[RECENT_KEY] = [slug, *recent][:RECENT_MAX]


def recent_kpis(con: sqlite3.Connection, slugs: list[str]) -> list[dict]:
    """The KPIs for `slugs`, in that order: {slug, name, href, divisions} with the divisions that have a
    definition of it the visitor may see. Slugs that no longer exist are dropped."""
    if not slugs:
        return []
    marks = ", ".join("?" * len(slugs))
    kpis = {r["slug"]: {**dict(r), "divisions": []}
            for r in con.execute(f"SELECT kpi_id, slug, name FROM kpis WHERE slug IN ({marks})", slugs)}
    by_id = {k["kpi_id"]: k for k in kpis.values()}
    if by_id:
        ids = list(by_id)
        cond, params = visible("d")
        rows = con.execute(
            f"""
            SELECT DISTINCT d.kpi_id, v.name
              FROM definitions d JOIN divisions v ON v.division_id = d.division_id
             WHERE d.kpi_id IN ({", ".join("?" * len(ids))})
               AND {cond}
             ORDER BY v.name
            """,
            [*ids, *params],
        )
        for r in rows:
            by_id[r["kpi_id"]]["divisions"].append(r["name"])
    return [{**kpis[s], "href": url_for("kpi", slug=s)} for s in slugs if s in kpis]


def index():
    con = get_db()
    return render_template(
        "home.html",
        title="Home",
        tiles=category_tiles(con),
        recent=recent_kpis(con, session.get(RECENT_KEY, [])),
    )
