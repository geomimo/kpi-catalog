"""W3 (log in as, permissions, visibility), W11 (definition editor) and W12 (My Definitions).

The switcher offers three personas; the tests set the session user directly (login_as fixture) so that all five
roles of the PRD §10 capability table are covered: Emma (Observer, Finance), Anna (Contributor, Commercial),
Katerina (Curator, Commercial), Dimitris (Reviewer, Commercial), Noah (Admin).
"""

import csv
import re
import shutil

import pytest

from kpi_catalog import db
from kpi_catalog.auth import PERSONA_USER_IDS, has_permission, load_user
from kpi_catalog.fields import GRAINS, METRIC_TYPES, STATUSES, UNITS
from kpi_catalog.web import create_app
from kpigen.paths import SCHEMA, SEED

EMMA, ANNA, KATERINA, DIMITRIS, NOAH = "USR-005", "USR-009", "USR-007", "USR-008", "USR-053"
ROLES = {"observer": EMMA, "contributor": ANNA, "curator": KATERINA, "reviewer": DIMITRIS, "admin": NOAH}
FIN, COM = "DIV-001", "DIV-002"
UNPUBLISHED = ("draft", "in_review", "rejected")


def rows(table):
    with (SEED / f"{table}.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


DEFS = {d["definition_id"]: d for d in rows("definitions")}
ROLE_CODES = {r["role_id"]: r["code"] for r in rows("roles")}


def unpublished_in(division, not_owned_by):
    return next(i for i, d in DEFS.items() if d["division_id"] == division and d["status"] in UNPUBLISHED
                and d["owner_user_id"] not in not_owned_by)


def html(client, path, status=200):
    response = client.get(path)
    assert response.status_code == status, (path, response.status_code)
    return response.get_data(as_text=True)


# ---- PRD §10 capability table: every cell --------------------------------------------------------------------

# "yes" = everywhere, "division" = only in the divisions where the role is held, "all" = every division, None = no.
CAPABILITIES = {
    "read published":            {"observer": "yes", "contributor": "yes", "curator": "yes", "reviewer": "yes", "admin": "yes"},
    "add community tags":        {"observer": "yes", "contributor": "yes", "curator": "yes", "reviewer": "yes", "admin": "yes"},
    "see unpublished":           {"observer": None, "contributor": "division", "curator": "division", "reviewer": "division", "admin": "all"},
    "propose and submit":        {"observer": None, "contributor": "division", "curator": "division", "reviewer": None, "admin": "all"},
    "edit / deprecate approved": {"observer": None, "contributor": None, "curator": "division", "reviewer": None, "admin": "all"},
    "approve / reject":          {"observer": None, "contributor": None, "curator": None, "reviewer": "division", "admin": "all"},
    "validate and promote tags": {"observer": None, "contributor": None, "curator": "division", "reviewer": None, "admin": "all"},
    "governance, TTL export":    {"observer": None, "contributor": None, "curator": None, "reviewer": None, "admin": "yes"},
}
PERMISSION = {
    "add community tags": ["tag.add_community"],
    "see unpublished": ["definition.view_unpublished"],
    "propose and submit": ["definition.propose"],
    "edit / deprecate approved": ["definition.edit", "definition.deprecate"],
    "approve / reject": ["definition.approve"],
    "validate and promote tags": ["tag.manage"],
    "governance, TTL export": ["governance.manage"],
}
# Pages guarded by the capability: 200 if the role has it somewhere, 403 otherwise.
PAGE = {
    "propose and submit": "/definitions/new",
    "approve / reject": "/review",
    "validate and promote tags": "/curate/tags",
    "governance, TTL export": "/governance/flags",
}
CELLS = [(cap, role) for cap in CAPABILITIES for role in ROLES]


@pytest.mark.parametrize("capability,role", CELLS, ids=[f"{c}-{r}" for c, r in CELLS])
def test_capability_table(app, client, login_as, capability, role):
    expected = CAPABILITIES[capability][role]
    user_id = ROLES[role]
    own = FIN if role == "observer" else COM
    other = COM if own == FIN else FIN
    login_as(user_id)

    if capability == "read published":
        other_def = next(i for i, d in DEFS.items() if d["division_id"] != own and d["status"] == "approved")
        html(client, f"/definitions/{other_def}")
        html(client, "/vocabulary")
        html(client, "/downloads")
        return

    if capability == "see unpublished":
        # Not their own definitions: the owner may always see theirs.
        in_own = unpublished_in(own, not_owned_by={user_id})
        in_other = unpublished_in(other, not_owned_by={user_id})
        assert client.get(f"/definitions/{in_own}").status_code == (200 if expected else 404)
        assert client.get(f"/definitions/{in_other}").status_code == (200 if expected == "all" else 404)
        return

    with app.app_context():
        user = load_user(db.get_db(), user_id)
        for code in PERMISSION[capability]:
            if expected == "yes":
                assert has_permission(user, code)
            elif expected == "all":
                assert has_permission(user, code, own) and has_permission(user, code, other)
            elif expected == "division":
                assert has_permission(user, code, own) and not has_permission(user, code, other)
            else:
                assert not has_permission(user, code) and not has_permission(user, code, own)
    if capability in PAGE:
        assert client.get(PAGE[capability]).status_code == (200 if expected else 403)


def test_anonymous_has_no_permissions(app):
    with app.app_context():
        for code in ("tag.add_community", "definition.propose", "definition.approve", "governance.manage"):
            assert not has_permission(None, code)


# ---- Top bar and "log in as" ---------------------------------------------------------------------------------

MENUS = {
    EMMA: None,  # Catalog is a plain link
    ANNA: ["Browse KPIs", "My Definitions", "Create New KPI"],
    KATERINA: ["Browse KPIs", "My Definitions", "Create / Edit KPI", "Tag Curation"],
    DIMITRIS: ["Browse KPIs", "Review Queue"],
    NOAH: ["Browse KPIs", "My Definitions", "Create / Edit KPI", "Review Queue", "Tag Curation"],
}


@pytest.mark.parametrize("user_id", list(MENUS))
def test_top_bar_menus_by_role(client, login_as, user_id):
    login_as(user_id)
    page = html(client, "/")
    nav = re.search(r'<nav class="mainnav".*?</nav>', page, re.S).group(0)
    menu = re.search(r'<ul class="catalog-menu">(.*?)</ul>', nav, re.S)
    if MENUS[user_id] is None:
        assert menu is None and '<a href="/kpis">Catalog</a>' in nav
    else:
        assert [s.strip() for s in re.findall(r"</svg>([^<]*)</a>", menu.group(1))] == MENUS[user_id]
    assert ('href="/governance/flags"' in nav) == (user_id == NOAH)


def test_anonymous_top_bar(client):
    page = html(client, "/")
    assert '<ul class="catalog-menu">' not in page and 'href="/governance/flags"' not in page
    assert "Browsing as a read-only visitor" in page


def test_switcher_offers_exactly_the_three_personas(client, login_as):
    login_as(KATERINA)
    page = html(client, "/")
    menu = re.search(r'<div class="account-menu">.*?</ul>', page, re.S).group(0)
    assert re.findall(r'name="user_id" value="(USR-\d+)"', menu) == list(PERSONA_USER_IDS)
    current = re.findall(r'class="persona is-current" aria-current="true">\s*<strong>(.*?)</strong>', menu)
    assert current == ["Katerina Okafor"]
    for name, title in (("Emma Papadopoulos", "Business Analyst"), ("Noah Garcia", "Data Governance Lead")):
        assert name in menu and title in menu
    assert "Observer · Finance" in menu and "Curator · Commercial" in menu and ">Admin<" in menu


def test_login_as_and_logout(client):
    response = client.post("/login-as", data={"user_id": KATERINA, "next": "/kpis/turnover"})
    assert response.status_code == 302 and response.headers["Location"].endswith("/kpis/turnover")
    with client.session_transaction() as s:
        assert s["user_id"] == KATERINA
    assert "Katerina" in html(client, "/")
    client.post("/logout", data={"next": "/"})
    with client.session_transaction() as s:
        assert "user_id" not in s


@pytest.mark.parametrize("user_id", [ANNA, DIMITRIS, "USR-001", "USR-999", "", "USR-005 "])
def test_login_as_rejects_non_personas(client, user_id):
    assert client.post("/login-as", data={"user_id": user_id}).status_code == 400
    with client.session_transaction() as s:
        assert "user_id" not in s


def test_login_as_ignores_offsite_next(client):
    response = client.post("/login-as", data={"user_id": EMMA, "next": "//evil.example/x"})
    assert response.headers["Location"].endswith("/")


# ---- Field values ---------------------------------------------------------------------------------------------

def test_field_values_match_schema():
    schema = SCHEMA.read_text(encoding="utf-8")

    def allowed(column):
        m = re.search(rf"\b{column}\s+TEXT NOT NULL\s+CHECK \({column} IN \(([^)]*)\)\)", schema)
        return tuple(re.findall(r"'([^']*)'", m.group(1)))

    assert allowed("unit") == UNITS
    assert allowed("grain") == GRAINS
    assert allowed("metric_type") == METRIC_TYPES
    assert allowed("status") == STATUSES


# ---- Editor (W11) -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("user_id", [EMMA, DIMITRIS])
def test_editor_forbidden_without_propose(client, login_as, user_id):
    login_as(user_id)
    assert client.get("/definitions/new").status_code == 403


@pytest.mark.parametrize("user_id", [ANNA, KATERINA])
def test_editor_offers_only_own_divisions(client, login_as, user_id):
    login_as(user_id)
    page = html(client, "/definitions/new")
    select = re.search(r'<select id="division_id".*?</select>', page, re.S).group(0)
    assert re.findall(r'<option value="(DIV-\d+)"', select) == [COM]
    assert "Tag suggestions arrive with the ML model" in page


@pytest.fixture
def rw(seed_db, tmp_path):
    """A writable copy of the database with its own app, client and login helper."""
    path = tmp_path / "catalog.sqlite"
    shutil.copy(seed_db, path)
    app = create_app({"DATABASE": str(path), "TESTING": True})
    client = app.test_client()

    def login(user_id):
        with client.session_transaction() as s:
            if user_id is None:
                s.clear()
            else:
                s["user_id"] = user_id

    return path, client, login


def form(**overrides):
    values = {
        "kpi_name": "Turnover", "division_id": COM, "display_name": "Commercial Net Turnover",
        "definition_text": "Net sales of the zyxwvut channel after returns, excluding tax.",
        "formula": "sum(net_sales_excl_tax) - sum(returns)", "unit": "EUR", "grain": "monthly",
        "metric_type": "simple", "source_table": "sales_orders", "source_column": "net_amount", "action": "draft",
    }
    values.update(overrides)
    return {k: v for k, v in values.items() if v is not None}


def count(path, sql, *args):
    con = db.connect(path)
    try:
        return con.execute(sql, args).fetchone()[0]
    finally:
        con.close()


def turnover_definitions_count(page):
    return int(re.search(r"Definitions \((\d+)\)", page).group(1))


def test_anna_saves_a_draft_visible_only_where_allowed(rw):
    path, client, login = rw
    other_contributor = next(r["user_id"] for r in rows("user_roles")
                             if r["division_id"] == COM and ROLE_CODES[r["role_id"]] == "contributor"
                             and r["user_id"] != ANNA)
    login(None)
    public_count = turnover_definitions_count(html(client, "/kpis/turnover"))

    login(ANNA)
    response = client.post("/definitions/new", data=form())
    assert response.status_code == 302
    new_id = response.headers["Location"].rsplit("/", 1)[-1]
    assert new_id == f"DEF-{max(int(i[4:]) for i in DEFS) + 1:04d}"  # the next free ID after the seed's
    page = html(client, f"/definitions/{new_id}")
    assert "Draft saved." in page and "Commercial Net Turnover" in page
    assert count(path, "SELECT count(*) FROM definitions WHERE definition_id = ? AND status = 'draft' "
                       "AND version = 1 AND origin = 'app' AND origin_ref IS NULL AND owner_user_id = ?",
                 new_id, ANNA) == 1
    mine = html(client, "/my-definitions?tab=draft")
    assert f"/definitions/{new_id}" in mine and f"/definitions/{new_id}/edit" in mine

    for viewer in (other_contributor, NOAH):
        login(viewer)
        html(client, f"/definitions/{new_id}")
        assert turnover_definitions_count(html(client, "/kpis/turnover")) == public_count + 1
    for viewer in (EMMA, None):
        login(viewer)
        assert client.get(f"/definitions/{new_id}").status_code == 404
        page = html(client, "/kpis/turnover?tab=definitions")
        assert turnover_definitions_count(page) == public_count and new_id not in page

    # The search index knows the new text.
    assert count(path, "SELECT count(*) FROM definitions_fts WHERE definitions_fts MATCH 'zyxwvut'") == 1


def test_submit_for_review_sets_in_review(rw):
    path, client, login = rw
    login(KATERINA)
    response = client.post("/definitions/new", data=form(action="submit"))
    new_id = response.headers["Location"].rsplit("/", 1)[-1]
    assert count(path, "SELECT count(*) FROM definitions WHERE definition_id = ? AND status = 'in_review'", new_id) == 1
    assert "Submitted for review." in html(client, f"/definitions/{new_id}")


@pytest.mark.parametrize("missing", ["kpi_name", "definition_text", "unit", "grain", "metric_type", "formula"])
def test_missing_required_field_saves_nothing(rw, missing):
    path, client, login = rw
    before = count(path, "SELECT count(*) FROM definitions")
    login(ANNA)
    response = client.post("/definitions/new", data=form(**{missing: ""}, action="submit"))
    assert response.status_code == 422
    page = response.get_data(as_text=True)
    assert "Nothing was saved." in page and f'id="{missing}-error"' in page
    assert "sum(net_sales_excl_tax)" in page or missing == "formula"  # what the user typed is kept
    assert count(path, "SELECT count(*) FROM definitions") == before


def test_formula_optional_for_base_metrics(rw):
    path, client, login = rw
    login(ANNA)
    assert client.post("/definitions/new", data=form(metric_type="base", formula="")).status_code == 302


def test_new_kpi_concept(rw):
    path, client, login = rw
    login(ANNA)
    page = client.post("/definitions/new", data=form(kpi_name="Click and Collect Share", new_kpi="1")).get_data(as_text=True)
    assert 'id="new_kpi_description-error"' in page  # a new concept needs a description
    response = client.post("/definitions/new", data=form(kpi_name="Click and Collect Share", new_kpi="1",
                                                         new_kpi_description="Share of online orders collected in store."))
    assert response.status_code == 302
    next_kpi = f"KPI-{max(int(k['kpi_id'][4:]) for k in rows('kpis')) + 1:04d}"
    assert count(path, "SELECT count(*) FROM kpis WHERE kpi_id = ? AND slug = 'click-and-collect-share'", next_kpi) == 1
    # An existing name can't be created again; an unknown name needs the "new concept" box.
    assert 'id="kpi_name-error"' in client.post("/definitions/new", data=form(new_kpi="1", new_kpi_description="x")).get_data(as_text=True)
    assert 'id="kpi_name-error"' in client.post("/definitions/new", data=form(kpi_name="No Such KPI")).get_data(as_text=True)


def test_division_outside_own_is_rejected(rw):
    path, client, login = rw
    login(ANNA)
    page = client.post("/definitions/new", data=form(division_id=FIN)).get_data(as_text=True)
    assert 'id="division_id-error"' in page


def test_owner_rules(rw):
    path, client, login = rw
    finance_user = next(r["user_id"] for r in rows("user_roles") if r["division_id"] == FIN)
    # Noah (Admin) holds no division role: he must name an owner from the division.
    login(NOAH)
    assert 'id="owner_user_id-error"' in client.post("/definitions/new", data=form()).get_data(as_text=True)
    assert client.post("/definitions/new", data=form(owner_user_id=ANNA)).status_code == 302
    # Katerina (Curator) may name Anna, but not someone outside Commercial.
    login(KATERINA)
    assert 'id="owner_user_id-error"' in client.post("/definitions/new", data=form(owner_user_id=finance_user)).get_data(as_text=True)
    response = client.post("/definitions/new", data=form(owner_user_id=ANNA))
    new_id = response.headers["Location"].rsplit("/", 1)[-1]
    assert count(path, "SELECT count(*) FROM definitions WHERE definition_id = ? AND owner_user_id = ?", new_id, ANNA) == 1
    # Anna (Contributor) can't pick: she is always the owner.
    login(ANNA)
    response = client.post("/definitions/new", data=form(owner_user_id=KATERINA))
    new_id = response.headers["Location"].rsplit("/", 1)[-1]
    assert count(path, "SELECT count(*) FROM definitions WHERE definition_id = ? AND owner_user_id = ?", new_id, ANNA) == 1


def test_edit_own_draft_then_submit(rw):
    path, client, login = rw
    login(ANNA)
    new_id = client.post("/definitions/new", data=form()).headers["Location"].rsplit("/", 1)[-1]
    page = html(client, f"/definitions/{new_id}/edit")
    assert "Commercial Net Turnover" in page and "sum(net_sales_excl_tax)" in page
    response = client.post(f"/definitions/{new_id}/edit", data=form(definition_text="Revised text.", action="submit"))
    assert response.status_code == 302
    assert count(path, "SELECT count(*) FROM definitions WHERE definition_id = ? AND status = 'in_review' "
                       "AND definition_text = 'Revised text.'", new_id) == 1
    # No longer a draft: no more editing here.
    assert client.get(f"/definitions/{new_id}/edit").status_code == 403


def test_cannot_edit_drafts_outside_own_divisions(rw):
    path, client, login = rw
    finance_draft = next(i for i, d in DEFS.items() if d["division_id"] == FIN and d["status"] == "draft")
    login(ANNA)
    assert client.get(f"/definitions/{finance_draft}/edit").status_code == 403
    assert client.post(f"/definitions/{finance_draft}/edit", data=form(division_id=FIN)).status_code == 403
    login(EMMA)
    assert client.get(f"/definitions/{finance_draft}/edit").status_code == 403
    login(NOAH)
    html(client, f"/definitions/{finance_draft}/edit")


def test_cannot_edit_approved_here(client, login_as):
    login_as(KATERINA)
    approved = next(i for i, d in DEFS.items() if d["division_id"] == COM and d["status"] == "approved")
    assert client.get(f"/definitions/{approved}/edit").status_code == 403


def test_unknown_definition_edit_is_404(client, login_as):
    login_as(NOAH)
    assert client.get("/definitions/DEF-9999/edit").status_code == 404


# ---- My Definitions (W12) -------------------------------------------------------------------------------------

def test_my_definitions_tabs_and_review_comments(client, login_as):
    owner = max(USERS_WITH_OWNED, key=lambda u: len({DEFS[i]["status"] for i in USERS_WITH_OWNED[u]}))
    login_as(owner)
    owned = USERS_WITH_OWNED[owner]
    page = html(client, "/my-definitions")
    assert f"All ({len(owned)})" in page
    for key, label in (("draft", "Draft"), ("in_review", "In review"), ("rejected", "Rejected"), ("approved", "Approved")):
        assert f"{label} ({sum(1 for i in owned if DEFS[i]['status'] == key)})" in page
    assert set(re.findall(r'<td><a href="/definitions/(DEF-\d+)">', page)) == set(owned)
    reviews = {}
    for r in sorted(rows("reviews"), key=lambda r: (r["reviewed_at"], r["review_id"])):
        reviews[r["definition_id"]] = r  # latest wins
    for i in owned:
        latest = reviews.get(i)
        shown = latest and (DEFS[i]["status"] in ("in_review", "rejected") or latest["decision"] == "changes_requested")
        if shown:
            assert latest["comment"] in page


USERS_WITH_OWNED = {}
for _i, _d in DEFS.items():
    if any(r["user_id"] == _d["owner_user_id"] and ROLE_CODES[r["role_id"]] in ("contributor", "curator")
           for r in rows("user_roles")):
        USERS_WITH_OWNED.setdefault(_d["owner_user_id"], []).append(_i)


def test_my_definitions_needs_propose(client, login_as):
    for user_id in (EMMA, DIMITRIS):
        login_as(user_id)
        assert client.get("/my-definitions").status_code == 403


def test_editor_passes_the_form_to_the_m8_suggestions(client, login_as, monkeypatch):
    """The interface M8 fills in (ml/suggest.py): the editor passes the whole form, the panel shows the tags."""
    seen = []

    def fake_suggest(form):
        seen.append(dict(form))
        return {"tags": [{"label": "Revenue", "facet": "category", "concept_uri": "u", "confidence": 0.9}],
                "measure_type": None, "similar": []}

    monkeypatch.setattr("kpi_catalog.web.editor.suggest_for_definition", fake_suggest)
    login_as(KATERINA)
    page = html(client, "/definitions/new")
    assert '<span class="chip">Revenue</span>' in page
    assert "Tag suggestions arrive with the ML model" not in page
    response = client.post("/definitions/new", data={"display_name": "Shrink", "definition_text": "Lost stock.",
                                                     "formula": "", "unit": "%", "action": "draft"})
    assert response.status_code == 422  # incomplete form: re-rendered with the suggestions for what was typed
    assert {"display_name": "Shrink", "definition_text": "Lost stock.", "formula": "", "unit": "%"}.items() <= seen[-1].items()
