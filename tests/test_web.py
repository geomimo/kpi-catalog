"""W1: every page in the PRD §10 site map is served (as Noah, the Admin, who may open all of them)."""

import pytest

from kpi_catalog.web import create_app

SITE_MAP = [
    "/",
    "/kpis",
    "/kpis/turnover",
    "/kpis/turnover/compare",
    "/definitions/new",
    "/definitions/DEF-0301",
    "/definitions/DEF-0310/edit",  # a draft
    "/my-definitions",
    "/review",
    "/vocabulary",
    "/vocabulary/theme-quality",
    "/curate/tags",
    "/curate/community-tags",
    "/governance/flags",
    "/downloads",
    "/about",
]

# Pages that need a permission (PRD §10): an anonymous visitor gets 403.
PROTECTED = ["/definitions/new", "/my-definitions", "/review", "/curate/tags", "/curate/community-tags",
             "/governance/flags"]


@pytest.mark.parametrize("path", SITE_MAP)
def test_route_serves_page(client, login_as, path):
    login_as("USR-053")
    response = client.get(path)
    assert response.status_code == 200
    assert b'id="login-as"' in response.data


@pytest.mark.parametrize("path", PROTECTED)
def test_protected_pages_forbidden_to_anonymous(client, path):
    response = client.get(path)
    assert response.status_code == 403
    assert b"You can't open this page" in response.data


def test_site_map_covers_every_page_route():
    app = create_app()
    pages = {r.rule for r in app.url_map.iter_rules()
             if r.endpoint not in ("static", "login_as", "logout")}
    assert len(pages) == len(SITE_MAP)
