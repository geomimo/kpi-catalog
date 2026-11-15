"""Flask app for the KPI Catalog (PRD §10–11).

Run with: uv run flask --app kpi_catalog.web run --debug
"""

from flask import Flask, render_template, request

from kpi_catalog import db
from kpi_catalog.auth import require
from kpi_catalog.web import account, editor, home, kpis

# The PRD §10 site map: (endpoint, URL rule, page title, what the page will do).
# Pages without an entry in VIEWS are placeholders. Database access: db.get_db().
PAGES = [
    ("home", "/", "Home", 'Search, "KPIs of <your divisions>", facet entry points.'),
    ("browse", "/kpis", "Browse KPIs", "Facets, community-tag filter, A–Z index, tag cloud."),
    ("kpi", "/kpis/<slug>", "KPI", "Definitions by division, divergence, lineage, used-in, versions, tags."),
    ("compare", "/kpis/<slug>/compare", "Compare definitions", "The KPI's definitions side by side."),
    ("new_definition", "/definitions/new", "Create New KPI Definition", "Editor; save a draft or submit for review."),
    ("definition", "/definitions/<definition_id>", "Definition", "One definition: details, lineage, usage, history."),
    ("edit_definition", "/definitions/<definition_id>/edit", "Edit definition", "Edit a draft; submit for review."),
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
NAV_SECTION = {
    "home": "home",
    "browse": "catalog", "kpi": "catalog", "compare": "catalog", "definition": "catalog",
    "new_definition": "catalog", "edit_definition": "catalog", "my_definitions": "catalog",
    "review": "catalog", "curate_tags": "catalog", "curate_community_tags": "catalog",
    "vocabulary": "vocabulary", "concept": "vocabulary",
    "governance_flags": "governance",
}

# Pages with a real view; every other page in PAGES is still a placeholder.
VIEWS = {
    "home": home.index,
    "kpi": kpis.kpi_page,
    "compare": kpis.compare_page,
    "definition": kpis.definition_page,
    "new_definition": editor.new_definition,
    "edit_definition": editor.edit_definition,
    "my_definitions": editor.my_definitions,
}

# Pages that take form posts.
POST_PAGES = {"new_definition", "edit_definition"}

# Placeholder pages already guarded by the permission they will need (PRD §10). Real views check their own.
PLACEHOLDER_PERMISSIONS = {
    "review": "definition.approve",
    "curate_tags": "tag.manage",
    "curate_community_tags": "tag.manage",
    "governance_flags": "governance.manage",
}


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_path=str(db.INSTANCE))
    # The session holds the "log in as" user and "Recently Viewed". Local demo, no hosting (PRD §11), so a
    # fixed dev key is fine; FLASK_SECRET_KEY overrides it.
    app.config["SECRET_KEY"] = "konfusio-local-demo"
    app.config.from_prefixed_env()
    app.config.update(config or {})
    db.init_app(app)

    @app.context_processor
    def inject_nav():
        return {"section": NAV_SECTION.get(request.endpoint), **account.nav_context()}

    for endpoint, rule, title, summary in PAGES:
        view = VIEWS.get(endpoint) or _placeholder(title, summary)
        if endpoint in PLACEHOLDER_PERMISSIONS:
            view = require(PLACEHOLDER_PERMISSIONS[endpoint])(view)
        methods = ["GET", "POST"] if endpoint in POST_PAGES else ["GET"]
        app.add_url_rule(rule, endpoint, view, methods=methods)

    app.add_url_rule("/login-as", "login_as", account.login_as, methods=["POST"])
    app.add_url_rule("/logout", "logout", account.logout, methods=["POST"])
    app.register_error_handler(403, account.forbidden)
    return app


def _placeholder(title: str, summary: str):
    def view(**params):
        return render_template("placeholder.html", title=title, summary=summary, params=params)

    view.__name__ = f"placeholder_{title}"
    return view
