"""W10 (in progress): the homepage from Ioanna's wireframe: top bar, search, category tiles, recently viewed."""

import csv
import re
from collections import defaultdict

from kpi_catalog.web.home import RECENT_KEY, RECENT_MAX
from kpigen.paths import SEED


def csv_rows(table):
    with (SEED / f"{table}.csv").open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def expected_tiles():
    """(code, name, n) per division from the CSVs: distinct KPIs with an approved definition, largest first."""
    kpis = defaultdict(set)
    for d in csv_rows("definitions"):
        if d["status"] == "approved":
            kpis[d["division_id"]].add(d["kpi_id"])
    divs = [(v["code"], v["name"], len(kpis[v["division_id"]])) for v in csv_rows("divisions")]
    return sorted((t for t in divs if t[2]), key=lambda t: (-t[2], t[1]))


def section(html, section_id):
    return re.search(rf'<section id="{section_id}".*?</section>', html, re.S).group(0)


def test_homepage_ok(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'action="/kpis"' in html and 'name="q"' in html
    assert "Search for a KPI (e.g., Turnover, Active Users…)" in html
    assert '<a href="/" aria-current="page">Home</a>' in html


def test_tiles_show_top_divisions_with_counts(client):
    html = client.get("/").get_data(as_text=True)
    tiles = re.findall(r'<a class="tile" href="/kpis\?division=(\w+)">.*?'
                       r'<span class="tile-label">(.*?)</span>.*?<span class="tile-count">(\d+) KPIs?</span>', html, re.S)
    expected = [(code, name.replace("&", "&amp;"), str(n)) for code, name, n in expected_tiles()[:4]]
    assert tiles == expected
    assert expected[0][:2] == ("FIN", "Finance")


def test_recently_viewed_empty_invites(client):
    html = client.get("/").get_data(as_text=True)
    assert "KPIs you open will show up here" in section(html, "recent")


def test_recently_viewed_lists_opened_kpi(client):
    assert client.get("/kpis/turnover").status_code == 200
    recent = section(client.get("/").get_data(as_text=True), "recent")
    assert '<a class="row" href="/kpis/turnover">' in recent
    assert '<span class="row-name">Turnover</span>' in recent
    turnover = {r["kpi_id"] for r in csv_rows("kpis") if r["slug"] == "turnover"}
    names = {v["division_id"]: v["name"] for v in csv_rows("divisions")}
    chips = {names[d["division_id"]] for d in csv_rows("definitions")
             if d["kpi_id"] in turnover and d["status"] in ("approved", "deprecated")}
    assert set(re.findall(r'<span class="chip">(.*?)</span>', recent)) == chips


def test_recently_viewed_newest_first_no_duplicates_max(client):
    # KPIs an Observer can open (a KPI with no published definition is a 404 and isn't remembered).
    public = {d["kpi_id"] for d in csv_rows("definitions") if d["status"] in ("approved", "deprecated")}
    slugs = [r["slug"] for r in csv_rows("kpis") if r["kpi_id"] in public][: RECENT_MAX + 2]
    for slug in [*slugs, slugs[-1], slugs[-3]]:
        client.get(f"/kpis/{slug}")
    with client.session_transaction() as s:
        # Visits s0..s6, s6 again, s4 again → newest first, unique, last RECENT_MAX (5).
        expected = [slugs[-3], slugs[-1], slugs[-2], slugs[-4], slugs[-5]]
        assert s[RECENT_KEY] == expected
    recent = section(client.get("/").get_data(as_text=True), "recent")
    assert re.findall(r'href="/kpis/([\w-]+)"', recent) == expected


def test_unknown_kpi_not_remembered(client):
    client.get("/kpis/no-such-kpi")
    with client.session_transaction() as s:
        assert RECENT_KEY not in s
