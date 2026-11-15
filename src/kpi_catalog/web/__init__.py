"""Flask app for the KPI Catalog (PRD §10–11).

Run with: uv run flask --app kpi_catalog.web run --debug
"""

from flask import Flask, render_template, request

from kpi_catalog import db
from kpi_catalog.web import home

# The PRD §10 site map: (endpoint, URL rule, page title, what the page will do).
# Pages without an entry in VIEWS are placeholders (data appears from W4); the
# "log in as" switcher and permission checks come in W3. Database access: db.get_db().
PAGES = [
    ("home", "/", "Home", 'Search, "KPIs of <your divisions>", facet entry points.'),
    ("browse", "/kpis", "Browse KPIs", "Facets, community-tag filter, A–Z index, tag cloud."),
    ("kpi", "/kpis/<slug>", "KPI", "Definitions by division, divergence, lineage, used-in, versions, tags."),
    ("edit_definition", "/definitions/<def_id>/edit", "Edit definition", "Editor with ML suggestions; submit for review."),
    ("my_definitions", "/my-definitions", "My definitions", "Own drafts, in-review and rejected definitions with review comments."),
    ("review", "/review", "Review queue", "Definitions awaiting review in the reviewer's divisions."),
    ("vocabulary", "/vocabulary", "Vocabulary", "SKOS concept schemes."),
    ("concept", "/vocabulary/<concept_id>", "Concept", "Broader, narrower and related concepts; tagged definitions."),
    ("curate_tags", "/curate/tags", "Validate auto tags", 'Accept or reject "auto" (ML) tags.'),
    ("curate_community_tags", "/curate/community-tags", "Community tags", "Community tags by frequency: merge or promote into the vocabulary."),
    ("governance_flags", "/governance/flags", "Governance flags", "Synonyms, divergences, unit mismatches; TTL export."),
    ("downloads", "/downloads", "Downloads", "SKOS vocabulary (Turtle) and the annotated dataset."),
    ("about", "/about", "About", "Problem, personas, use cases, methodology."),
]

# Top-bar section each page belongs to; the matching link is underlined.
# Role-specific pages get menu entries with W3.
NAV_SECTION = {
    "home": "home",
    "browse": "catalog", "kpi": "catalog",
    "vocabulary": "vocabulary", "concept": "vocabulary",
}

# Pages with a real view; every other page in PAGES is still a placeholder.
VIEWS = {"home": home.index}

# Extra work before a placeholder renders (until the page itself is built).
BEFORE = {"kpi": home.remember_kpi}  # W10 "Recently Viewed"; W4 replaces the KPI page


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_path=str(db.INSTANCE))
    # The session only holds "Recently Viewed" (and later the W3 "log in as" user). Local demo, no hosting
    # (PRD §11), so a fixed dev key is fine; FLASK_SECRET_KEY overrides it.
    app.config["SECRET_KEY"] = "konfusio-local-demo"
    app.config.from_prefixed_env()
    app.config.update(config or {})
    db.init_app(app)

    @app.context_processor
    def inject_nav():
        return {"section": NAV_SECTION.get(request.endpoint)}

    for endpoint, rule, title, summary in PAGES:
        view = VIEWS.get(endpoint) or _placeholder(title, summary, BEFORE.get(endpoint))
        app.add_url_rule(rule, endpoint, view)

    return app


def _placeholder(title: str, summary: str, before=None):
    def view(**params):
        if before:
            before(**params)
        return render_template("placeholder.html", title=title, summary=summary, params=params)

    return view
