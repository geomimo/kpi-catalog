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


@pytest.fixture
def login_as(client):
    """Set the session user directly (bypasses the switcher's three personas, so every role can be tested).
    Pass None to log out."""
    def login(user_id):
        with client.session_transaction() as s:
            if user_id is None:
                s.pop("user_id", None)
            else:
                s["user_id"] = user_id
    return login
