"""Business rules every seed must satisfy (PRD §3.6). schema.sql covers FKs, CHECKs and UNIQUEs.

Runs against KPIGEN_SEED_DIR (default data/seed). `uv run kpigen` runs this file after generating.
"""

import os
from pathlib import Path

import pytest
import yaml

from kpigen.paths import SCENARIOS, SEED
from kpigen.validate import load_seed

SEED_DIR = Path(os.environ.get("KPIGEN_SEED_DIR", SEED))


@pytest.fixture(scope="module")
def db():
    if not (SEED_DIR / "definitions.csv").exists():
        pytest.skip(f"no seed in {SEED_DIR}; run `uv run kpigen`")
    return load_seed(SEED_DIR)


@pytest.fixture(scope="module")
def scenarios():
    return yaml.safe_load(SCENARIOS.read_text(encoding="utf-8"))


def rows(db, sql):
    return db.execute(sql).fetchall()


def test_supersession_stays_within_kpi_and_division(db):
    bad = rows(db, """
        SELECT old.definition_id, new.definition_id FROM definitions old
        JOIN definitions new ON new.definition_id = old.superseded_by_id
        WHERE old.kpi_id <> new.kpi_id OR old.division_id <> new.division_id
           OR old.status <> 'deprecated' OR new.version <= old.version""")
    assert bad == [], "superseded across KPI/division, not deprecated, or version not increased"


def test_every_owner_holds_a_role_in_the_definitions_division(db):
    bad = rows(db, """
        SELECT d.definition_id, d.owner_user_id FROM definitions d
        WHERE NOT EXISTS (SELECT 1 FROM user_roles ur
                          WHERE ur.user_id = d.owner_user_id AND ur.division_id = d.division_id)""")
    assert bad == []


def test_every_reviewer_is_a_reviewer_in_the_division_and_not_the_owner(db):
    bad = rows(db, """
        SELECT r.review_id FROM reviews r JOIN definitions d USING (definition_id)
        WHERE r.reviewer_user_id = d.owner_user_id
           OR NOT EXISTS (SELECT 1 FROM user_roles ur JOIN roles ro USING (role_id)
                          WHERE ur.user_id = r.reviewer_user_id AND ro.code = 'reviewer'
                            AND ur.division_id = d.division_id)""")
    assert bad == []


def test_published_and_rejected_definitions_have_a_matching_review(db):
    # The latest review decides the status: approved/deprecated <- approved, rejected <- rejected.
    bad = rows(db, """
        SELECT d.definition_id, d.status, (
            SELECT r.decision FROM reviews r WHERE r.definition_id = d.definition_id
            ORDER BY r.reviewed_at DESC, r.review_id DESC LIMIT 1) AS last
        FROM definitions d
        WHERE d.status IN ('approved', 'rejected', 'deprecated')
          AND last IS NOT (CASE d.status WHEN 'rejected' THEN 'rejected' ELSE 'approved' END)""")
    assert bad == []


def test_no_review_or_update_after_the_reference_date(db, scenarios):
    ref = str(scenarios["generation"]["reference_date"]) + "T23:59:59Z"
    assert rows(db, f"SELECT review_id FROM reviews WHERE reviewed_at > '{ref}'") == []
    assert rows(db, f"SELECT definition_id FROM definitions WHERE updated_at > '{ref}'") == []
    assert rows(db, """
        SELECT r.review_id FROM reviews r JOIN definitions d USING (definition_id)
        WHERE r.reviewed_at < d.created_at""") == []


def test_every_scenario_fixture_is_present(db, scenarios):
    def have(table, key, value):
        return db.execute(f"SELECT 1 FROM {table} WHERE {key} = ?", (value,)).fetchone() is not None

    for u in scenarios["users"]:
        assert have("users", "user_id", u["user_id"]), u["user_id"]
        assert db.execute("SELECT full_name FROM users WHERE user_id = ?", (u["user_id"],)).fetchone()[0] == u["full_name"]
        for r in u["roles"]:
            found = db.execute("""
                SELECT 1 FROM user_roles ur JOIN roles ro USING (role_id) LEFT JOIN divisions dv USING (division_id)
                WHERE ur.user_id = ? AND ro.code = ? AND dv.code IS ?""", (u["user_id"], r["role"], r["division"])).fetchone()
            assert found, f"{u['user_id']} lacks {r['role']} in {r['division']}"
    for d in scenarios["handwritten_definitions"]:
        assert have("definitions", "definition_id", d["definition_id"]), d["definition_id"]
    for f in scenarios["definition_fixtures"]:
        got = db.execute("SELECT status, owner_user_id, superseded_by_id, version FROM definitions WHERE definition_id = ?",
                         (f["definition_id"],)).fetchone()
        assert got, f["definition_id"]
        assert got[0] == f["status"], f["definition_id"]
        if "owner" in f:
            assert got[1] == f["owner"], f["definition_id"]
        if "superseded_by" in f:
            assert got[2] == f["superseded_by"], f["definition_id"]
        if "version" in f:
            assert got[3] == f["version"], f["definition_id"]
    for a in scenarios["assets"]:
        linked = {r[0] for r in rows(db, f"SELECT definition_id FROM asset_definitions WHERE asset_id = '{a['asset_id']}'")}
        assert linked == set(a["definitions"]), a["asset_id"]
    for t in scenarios["community_tags"]["fixtures"]:
        for did in t["definitions"]:
            assert db.execute("""SELECT 1 FROM definition_tags dt JOIN tags t USING (tag_id)
                                 WHERE t.kind = 'community' AND t.label = ? AND dt.definition_id = ?""",
                              (t["label"], did)).fetchone(), (t["label"], did)
    for r in scenarios["handwritten_relationships"]:
        assert db.execute("""SELECT 1 FROM kpi_relationships WHERE from_definition_id = ? AND to_definition_id = ?
                             AND relationship_type = ? AND role IS ?""", (r["from"], r["to"], r["type"], r.get("role"))).fetchone()


def test_dashboard_names_are_unique_and_link_only_their_own_division(db):
    assert rows(db, "SELECT name FROM assets GROUP BY lower(name) HAVING count(*) > 1") == []
    bad = rows(db, """
        SELECT a.asset_id, d.definition_id FROM asset_definitions ad
        JOIN assets a USING (asset_id) JOIN definitions d USING (definition_id)
        WHERE a.division_id <> d.division_id OR d.status NOT IN ('approved', 'deprecated')""")
    assert bad == []


def test_no_theme_or_business_line_tags_in_the_seed(db):
    assert rows(db, "SELECT tag_id FROM tags WHERE kind <> 'community' OR facet IS NOT NULL") == []
    assert rows(db, "SELECT tag_id FROM definition_tags WHERE source <> 'user' OR status IS NOT NULL") == []


def test_a_reviewer_never_also_writes_in_the_same_division(db):
    """Separation of duties (§4.5): no user is Reviewer and Contributor/Curator in one division."""
    bad = rows(db, """
        SELECT a.user_id, a.division_id FROM user_roles a JOIN roles ra ON ra.role_id = a.role_id
        JOIN user_roles b ON b.user_id = a.user_id AND b.division_id = a.division_id
        JOIN roles rb ON rb.role_id = b.role_id
        WHERE ra.code = 'reviewer' AND rb.code IN ('contributor', 'curator')""")
    assert bad == []

