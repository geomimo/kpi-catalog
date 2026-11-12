"""Flask app for the KPI Catalog (PRD §10–11).

Run with: uv run flask --app kpi_catalog.web run --debug
"""

from flask import Flask, render_template

# The PRD §10 site map: (endpoint, URL rule, page title, what the page will do).
# Every page is a placeholder for now; the database comes in W2 and the
# "log in as" switcher and permission checks in W3.
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

# Pages linked from the navbar, in order.
NAV = [
    ("home", "Home"),
    ("browse", "Browse"),
    ("vocabulary", "Vocabulary"),
    ("my_definitions", "My definitions"),
    ("review", "Review"),
    ("curate_tags", "Auto tags"),
    ("curate_community_tags", "Community tags"),
    ("governance_flags", "Governance"),
    ("downloads", "Downloads"),
    ("about", "About"),
]


def create_app() -> Flask:
    app = Flask(__name__)

    @app.context_processor
    def inject_nav():
        return {"nav": NAV}

    for endpoint, rule, title, summary in PAGES:
        app.add_url_rule(rule, endpoint, _placeholder(title, summary))

    return app


def _placeholder(title: str, summary: str):
    def view(**params):
        return render_template("placeholder.html", title=title, summary=summary, params=params)

    return view
