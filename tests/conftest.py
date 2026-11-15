"""Shared fixtures: one app database built from the real seed in a temp directory (never instance/)."""

import pytest

from kpi_catalog import db
from kpi_catalog.web import create_app


@pytest.fixture(scope="session")
def seed_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("webdb") / "catalog.sqlite"
    db.build(path)
    return path


@pytest.fixture
def app(seed_db):
    return create_app({"DATABASE": str(seed_db), "TESTING": True})


@pytest.fixture
def client(app):
    return app.test_client()
