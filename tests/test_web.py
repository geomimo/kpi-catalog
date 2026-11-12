"""W1: every page in the PRD §10 site map is served."""

import pytest

from kpi_catalog.web import create_app

SITE_MAP = [
    "/",
    "/kpis",
    "/kpis/gross-margin",
    "/definitions/DEF-0308/edit",
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


@pytest.fixture
def client():
    return create_app().test_client()


@pytest.mark.parametrize("path", SITE_MAP)
def test_route_serves_page(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert b'id="login-as"' in response.data


def test_site_map_covers_every_route():
    app = create_app()
    rules = {r.rule for r in app.url_map.iter_rules() if r.endpoint != "static"}
    assert len(rules) == len(SITE_MAP)
