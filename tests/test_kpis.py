"""W6–W8: KPI concept page, definition detail page, compare page (PRD §4.5, §9 F4–F7, §10).

Until "log in as" (W3) every visitor is an Observer: approved and deprecated definitions only. Expected values
are read from the seed CSVs, not hard-coded.
"""

import csv
import re
import shutil

import pytest

from kpi_catalog import db
from kpi_catalog.auth import PUBLIC_STATUSES
from kpi_catalog.web import create_app
from kpigen.paths import SEED


def rows(table):
    with (SEED / f"{table}.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


KPIS = {k["slug"]: k for k in rows("kpis")}
DEFS = {d["definition_id"]: d for d in rows("definitions")}
DIVISIONS = {v["division_id"]: v for v in rows("divisions")}
USERS = {u["user_id"]: u for u in rows("users")}


def defs_of(slug, public_only=True):
    kpi_id = KPIS[slug]["kpi_id"]
    return {i for i, d in DEFS.items() if d["kpi_id"] == kpi_id and (d["status"] in PUBLIC_STATUSES or not public_only)}


def html(client, path):
    response = client.get(path)
    assert response.status_code == 200, path
    return response.get_data(as_text=True)


def tbody(page):
    return re.search(r"<tbody>.*?</tbody>", page, re.S).group(0)


def def_links(fragment):
    return re.findall(r'href="/definitions/(DEF-\d+)"', fragment)


# ---- KPI concept page ---------------------------------------------------------------------------------------

def test_turnover_definitions_tab_lists_exactly_the_visible_definitions(client):
    expected = defs_of("turnover")
    page = html(client, "/kpis/turnover?tab=definitions")
    assert set(def_links(tbody(page))) == expected
    assert f"Definitions ({len(expected)})" in page


def test_concept_page_overview(client):
    page = html(client, "/kpis/turnover")
    assert KPIS["turnover"]["description"] in page.replace("&#39;", "'")
    assert "KPI Concept" in page and 'href="/kpis/turnover/compare"' in page
    assert "Not categorised yet" in page  # the test database has official tags (V3) but no ML tags on them (M2)
    cards = re.search(r'<ul class="division-cards">.*?</ul>', page, re.S).group(0)
    divisions = {DIVISIONS[DEFS[i]["division_id"]]["name"] for i in defs_of("turnover")}
    assert set(re.findall(r"<span>(.*?)</span>", cards)) == divisions


def test_unpublished_definitions_hidden_and_not_counted(client):
    """Inventory Turnover has a draft, an in-review and rejected definitions next to approved ones."""
    hidden = defs_of("inventory-turnover", public_only=False) - defs_of("inventory-turnover")
    assert {DEFS[i]["status"] for i in hidden} == {"draft", "in_review", "rejected"}
    for tab in ("overview", "definitions", "dependencies", "related"):
        page = html(client, f"/kpis/inventory-turnover?tab={tab}")
        assert not hidden & set(def_links(page)), tab
        assert f"Definitions ({len(defs_of('inventory-turnover'))})" in page
    for i in hidden:
        assert client.get(f"/definitions/{i}").status_code == 404
    page = html(client, "/kpis/inventory-turnover/compare?" + "&".join(f"d={i}" for i in hidden))
    assert not hidden & set(def_links(page))
    assert "No definitions selected" in page


def test_kpi_with_no_visible_definition_is_404(client):
    unpublished = [s for s in KPIS if not defs_of(s)]
    assert unpublished
    assert client.get(f"/kpis/{unpublished[0]}").status_code == 404


def test_deprecated_definition_greyed_with_successor(client):
    old = next(d for d in DEFS.values() if d["status"] == "deprecated")
    slug = next(s for s, k in KPIS.items() if k["kpi_id"] == old["kpi_id"])
    page = html(client, f"/kpis/{slug}?tab=definitions")
    row = re.search(rf'<tr class="is-deprecated">.*?{old["definition_id"]}.*?</tr>', page, re.S).group(0)
    assert "superseded by" in row and f'/definitions/{old["superseded_by_id"]}' in row


# ---- Lineage (W7) -------------------------------------------------------------------------------------------

def test_atopu_finance_divides_finance_turnover_by_product_active_users(client):
    fin = next(i for i in defs_of("atopu") if DIVISIONS[DEFS[i]["division_id"]]["code"] == "FIN")
    rels = {r["role"]: r["to_definition_id"] for r in rows("kpi_relationships") if r["from_definition_id"] == fin}
    assert DIVISIONS[DEFS[rels["numerator"]]["division_id"]]["code"] == "FIN"
    assert DIVISIONS[DEFS[rels["denominator"]]["division_id"]]["code"] == "PRD"

    def linked(fragment, role):
        m = re.search(rf'<span class="role">{role}</span>\s*<a href="/definitions/(DEF-\d+)">.*?</a>\s*'
                      r'<span class="chip">(.*?)</span>', fragment, re.S)
        return m.groups()

    page = html(client, "/kpis/atopu?tab=dependencies")
    section = next(s for s in page.split('<section class="card dependency">')[1:]
                   if def_links(s.split("</h2>")[0]) == [fin])
    assert linked(section, "numerator") == (rels["numerator"], "Finance")
    assert linked(section, "denominator") == (rels["denominator"], "Product")
    detail = html(client, f"/definitions/{fin}?tab=dependencies")
    assert linked(detail, "denominator") == (rels["denominator"], "Product")


def test_related_kpis_tab(client):
    rel = next(r for r in rows("kpi_relationships") if r["relationship_type"] == "related_to"
               and DEFS[r["from_definition_id"]]["status"] in PUBLIC_STATUSES
               and DEFS[r["to_definition_id"]]["status"] in PUBLIC_STATUSES
               and DEFS[r["from_definition_id"]]["kpi_id"] != DEFS[r["to_definition_id"]]["kpi_id"])
    slug_of = {k["kpi_id"]: s for s, k in KPIS.items()}
    page = html(client, f"/kpis/{slug_of[DEFS[rel['from_definition_id']]['kpi_id']]}?tab=related")
    assert f'href="/kpis/{slug_of[DEFS[rel["to_definition_id"]]["kpi_id"]]}"' in page


# ---- Definition detail page ---------------------------------------------------------------------------------

def test_finance_definition_detail(client):
    d = DEFS["DEF-0301"]
    assert DIVISIONS[d["division_id"]]["code"] == "FIN"
    owner = USERS[d["owner_user_id"]]
    page = html(client, "/definitions/DEF-0301")
    assert "Turnover – Finance" in page and "KPI Definition" in page
    assert owner["full_name"] in page and owner["job_title"] in page
    assert f"<tr><th>Unit</th><td>{d['unit']}</td></tr>" in page

    history = html(client, "/definitions/DEF-0301?tab=history")
    reviews = [r for r in rows("reviews") if r["definition_id"] == "DEF-0301"]
    assert reviews
    for r in reviews:
        assert USERS[r["reviewer_user_id"]]["full_name"] in history
        assert r["comment"] in history


def test_review_history_newest_first(client):
    counts = {}
    for r in rows("reviews"):
        counts.setdefault(r["definition_id"], []).append(r)
    def_id, reviews = next((i, rs) for i, rs in counts.items() if len(rs) > 1 and DEFS[i]["status"] in PUBLIC_STATUSES)
    page = html(client, f"/definitions/{def_id}?tab=history")
    dates = re.findall(r'<time class="muted small" datetime="([^"]+)"', page)
    assert dates == sorted((r["reviewed_at"] for r in reviews), reverse=True)


def test_version_chain(client):
    old = next(d for d in DEFS.values() if d["status"] == "deprecated")
    for def_id in (old["definition_id"], old["superseded_by_id"]):
        page = html(client, f"/definitions/{def_id}?tab=history")
        versions = re.search(r'<ol class="versions">.*?</ol>', page, re.S).group(0)
        assert "this version" in versions
        other = old["superseded_by_id"] if def_id == old["definition_id"] else old["definition_id"]
        assert f'/definitions/{other}' in versions


def test_usage_lists_finance_weekly_flash_report(client):
    asset = next(a for a in rows("assets") if a["name"] == "Finance Weekly Flash Report")
    def_id = next(r["definition_id"] for r in rows("asset_definitions") if r["asset_id"] == asset["asset_id"])
    page = html(client, f"/definitions/{def_id}?tab=usage")
    assert "Finance Weekly Flash Report" in page
    assert asset["tool"] in page


def test_definition_tab_formula(client):
    base = next(d for d in DEFS.values() if d["metric_type"] == "base" and not d["formula"]
                and d["status"] in PUBLIC_STATUSES)
    assert "No formula recorded" in html(client, f"/definitions/{base['definition_id']}?tab=definition")
    page = html(client, "/definitions/DEF-0307?tab=definition")
    assert f"<pre><code>{DEFS['DEF-0307']['formula']}</code></pre>" in page


# ---- Compare page -------------------------------------------------------------------------------------------

def column_ids(page):
    head = re.search(r"<thead>.*?</thead>", page, re.S).group(0)
    return def_links(head)


def test_compare_defaults_to_all_visible_definitions(client):
    page = html(client, "/kpis/accounts-receivable-outstanding/compare")
    assert "Comparing definitions of: <strong>Accounts Receivable Outstanding</strong>" in page
    assert sorted(column_ids(page)) == sorted(defs_of("accounts-receivable-outstanding"))
    for label in ("Definition", "Formula", "Unit", "Grain", "Data Source", "Owner", "Status"):
        assert f'<th scope="row">{label}' in page


def test_compare_remove_drops_column(client):
    ids = sorted(defs_of("accounts-receivable-outstanding"))
    page = html(client, "/kpis/accounts-receivable-outstanding/compare?" + "&".join(f"d={i}" for i in ids))
    assert column_ids(page) == ids
    # follow the × link of the first column
    chips = re.findall(r'<span class="chip chip-select">.*?<a href="([^"]+)"', page, re.S)
    assert len(chips) == len(ids)
    after = html(client, chips[0].replace("&amp;", "&"))
    assert column_ids(after) == ids[1:]
    assert ids[0] in "".join(re.findall(r'<details class="dropdown add-definition">.*?</details>', after, re.S))


def test_compare_marks_differing_rows(client):
    page = html(client, "/kpis/turnover/compare")
    differing = [s.strip() for s in re.findall(r'<tr class="differs">\s*<th scope="row">(\w[\w ]*)', page)]
    formulas = {DEFS[i]["formula"] for i in defs_of("turnover")}
    assert ("Formula" in differing) == (len(formulas) > 1)
    units = {DEFS[i]["unit"] for i in defs_of("turnover")}
    assert ("Unit" in differing) == (len(units) > 1)


def test_compare_labels_same_division_columns(client):
    page = html(client, "/kpis/accounts-receivable-outstanding/compare")
    finance = [i for i in defs_of("accounts-receivable-outstanding") if DIVISIONS[DEFS[i]["division_id"]]["code"] == "FIN"]
    assert len(finance) > 1  # several definitions in one division: columns need the display name
    for i in finance:
        assert DEFS[i]["display_name"] in page


# ---- 404s ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/kpis/no-such-kpi", "/kpis/no-such-kpi/compare", "/definitions/DEF-9999"])
def test_unknown_is_404(client, path):
    assert client.get(path).status_code == 404


# ---- Hand-inserted rows: divergence flag (W8) and official tags (until M7/M2) --------------------------------

@pytest.fixture
def own_client(seed_db, tmp_path):
    path = tmp_path / "catalog.sqlite"
    shutil.copy(seed_db, path)
    return path, create_app({"DATABASE": str(path), "TESTING": True}).test_client()


def test_divergence_banner(own_client):
    path, client = own_client
    assert "Divisions define this KPI differently" not in html(client, "/kpis/turnover")
    a, b = sorted(defs_of("turnover"))[:2]
    con = db.connect(path)
    with con:
        con.execute("INSERT INTO similarity_flags (flag_id, type, a_definition_id, b_definition_id, score, status) "
                    "VALUES ('FLG-TEST', 'definitions_diverge', ?, ?, 0.41, 'open')", (a, b))
    con.close()
    assert "Divisions define this KPI differently" in html(client, "/kpis/turnover")


def test_official_tags_grouped_by_facet_with_auto_marker(own_client):
    path, client = own_client
    con = db.connect(path)
    with con:  # the loader already made the official tags from the vocabulary (V3); attach two of them
        con.execute("INSERT INTO definition_tags (definition_id, tag_id, source, confidence, status, tagged_at) "
                    "VALUES ('DEF-0301', 'TAG-Revenue', 'ml', 0.83, 'auto', '2026-11-15T00:00:00Z')")
        con.execute("INSERT INTO definition_tags (definition_id, tag_id, source, status, tagged_by, tagged_at) "
                    "VALUES ('DEF-0302', 'TAG-Banking', 'curator', 'accepted', 'USR-007', '2026-11-15T00:00:00Z')")
    con.close()
    page = html(client, "/kpis/turnover")
    assert "Not categorised yet" not in page
    categories = re.search(r"<h3>Categories</h3>.*?</div>", page, re.S).group(0)
    assert "Revenue" in categories and '<span class="auto">auto</span>' in categories and "0.83" in categories
    assert 'href="/vocabulary/Revenue"' in categories
    business = re.search(r"<h3>Business line</h3>.*?</div>", page, re.S).group(0)
    assert "Banking" in business and "auto" not in business
    community = re.search(r'<div class="tag-group community">.*?</div>\s*</div>', page, re.S).group(0)
    assert "Revenue" not in community and "#" in community
