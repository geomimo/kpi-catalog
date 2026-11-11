"""Build the seed tables from the inputs (PRD §3.4).

Real content (names, texts, formulas, dbt lineage) comes from the sources through the curation files;
fixtures come from scenarios.yaml; the rest of the organisation is filled with a seeded random
generator. Everything is iterated in a fixed order, so the same inputs always give the same output.
"""

import datetime as dt
import random
import re
from collections import defaultdict

from .inputs import Inputs, apply_fixes
from . import names

Table = list[dict]
DAY = dt.timedelta(days=1)


def ts(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:00Z")


def parse_ts(s: str) -> dt.datetime:
    s = str(s)
    return dt.datetime.fromisoformat(s.replace("Z", "")) if "T" in s else dt.datetime.fromisoformat(s + "T00:00")


class Generator:
    def __init__(self, inp: Inputs):
        self.inp = inp
        self.sc = inp.scenarios
        gen = self.sc["generation"]
        self.rng = random.Random(gen["random_seed"])
        self.ref = parse_ts(gen["reference_date"]) + dt.timedelta(hours=18)  # end of the working day
        self.earliest = parse_ts(gen["earliest_date"])
        self.div_id = {d["code"]: d["division_id"] for d in self.sc["divisions"]}
        self.role_id = {r["code"]: r["role_id"] for r in self.sc["roles"]}
        self.successor = {f["definition_id"]: f["superseded_by"]
                          for f in self.sc["definition_fixtures"] if f.get("superseded_by")}
        self.t: dict[str, Table] = {}

    # ------------------------------------------------------------------ helpers
    def when(self, lo: dt.datetime, hi: dt.datetime) -> dt.datetime:
        """A random office-hours timestamp between two moments."""
        lo = min(lo, hi)
        days = (hi.date() - lo.date()).days
        day = lo.date() + dt.timedelta(days=self.rng.randint(0, max(days, 0)))
        t = dt.datetime.combine(day, dt.time(self.rng.randint(8, 17), self.rng.choice([0, 15, 30, 45])))
        return min(max(t, lo), hi)

    def current(self, did: str) -> str:
        """The latest version of a definition. Links to a superseded one move to its successor (PRD §4.5)."""
        while did in self.successor:
            did = self.successor[did]
        return did

    # ------------------------------------------------------------------ build
    def build(self) -> dict[str, Table]:
        self.organisation()
        self.users()
        self.definitions()
        self.relationships()
        self.lifecycle()
        self.kpis()
        self.assets()
        self.community_tags()
        self.t["excluded"] = [
            {k: r[k] for k in ("origin", "origin_ref", "term", "reason_code", "reason")} for r in self.inp.exclusions
        ]
        return self.t

    def organisation(self) -> None:
        sc = self.sc
        self.t["divisions"] = [{k: d[k] for k in ("division_id", "code", "name", "description")} for d in sc["divisions"]]
        self.t["roles"] = [{k: r[k] for k in ("role_id", "code", "name", "description")} for r in sc["roles"]]
        self.t["permissions"] = [{k: p[k] for k in ("permission_id", "code", "description")} for p in sc["permissions"]]
        self.t["role_permissions"] = [
            {"role_id": self.role_id[r], "permission_id": p["permission_id"]} for p in sc["permissions"] for r in p["roles"]
        ]

    # ------------------------------------------------------------------ users
    def users(self) -> None:
        sc, rng = self.sc, self.rng
        company = sc["company"]
        fixtures = {u["user_id"]: u for u in sc["users"]}
        total = sc["generation"]["users_total"]
        free_ids = [f"USR-{i:03d}" for i in range(1, total + 1) if f"USR-{i:03d}" not in fixtures]

        # roles: (user, role, division code or None)
        roles: list[tuple[str, str, str | None]] = []
        for u in sc["users"]:
            roles += [(u["user_id"], r["role"], r["division"]) for r in u["roles"]]

        # Every division needs a curator, a reviewer and two contributors (owners and reviewers must exist).
        need = []
        for code in self.div_id:
            have = [r for _, r, d in roles if d == code]
            for role, n in (("curator", 1), ("reviewer", 1), ("contributor", 2)):
                need += [(role, code)] * max(0, n - have.count(role))
        div_weights = self._definition_counts()
        first_roles: dict[str, tuple[str, str]] = {}
        for uid in free_ids:
            if need:
                first_roles[uid] = need.pop(0)
            else:
                role = rng.choices(["observer", "contributor", "reviewer", "curator"], [4, 4, 1, 1])[0]
                code = rng.choices(list(div_weights), list(div_weights.values()))[0]
                first_roles[uid] = (role, code)

        used_names = {u["full_name"] for u in sc["users"]}
        used_emails: set[str] = set()
        rows = []
        for u in sc["users"]:
            rows.append(self._user_row(u["user_id"], u["full_name"], u["home_division"], u["job_title"],
                                       u["created_at"], used_emails, company))
        for uid in free_ids:
            role, code = first_roles[uid]
            while True:
                full = f"{rng.choice(names.FIRST)} {rng.choice(names.LAST)}"
                if full not in used_names:
                    used_names.add(full)
                    break
            title = f"{names.DIVISION_PREFIX[code]} {rng.choice(names.ROLE_TITLES[role])}"
            created = ts(self.when(self.earliest, self.ref - 90 * DAY))
            rows.append(self._user_row(uid, full, code, title, created, used_emails, company))
            roles.append((uid, role, code))
            if rng.random() < 0.3:  # a second role in another division
                other = rng.choice([c for c in self.div_id if c != code])
                roles.append((uid, rng.choice(["observer", "contributor"]), other))

        self.t["users"] = sorted(rows, key=lambda r: r["user_id"])
        self.user_created = {r["user_id"]: parse_ts(r["created_at"]) for r in rows}
        self.home = {r["user_id"]: r["home_division_id"] for r in rows}
        self.t["user_roles"] = sorted(
            ({"user_id": u, "role_id": self.role_id[r], "division_id": self.div_id[d] if d else None} for u, r, d in roles),
            key=lambda r: (r["user_id"], r["role_id"], r["division_id"] or ""),
        )
        self.holders: dict[tuple[str, str], list[str]] = defaultdict(list)  # (role, division code) -> users
        for u, r, d in sorted(roles):
            self.holders[(r, d)].append(u)

    def _user_row(self, uid, full, code, title, created, used_emails, company) -> dict:
        base = re.sub(r"[^a-z.]", "", full.lower().replace(" ", "."))
        email, n = f"{base}@{company['email_domain']}", 2
        while email in used_emails:
            email, n = f"{base}{n}@{company['email_domain']}", n + 1
        used_emails.add(email)
        return {"user_id": uid, "full_name": full, "email": email, "home_division_id": self.div_id[code],
                "job_title": title, "created_at": str(created)}

    def _definition_counts(self) -> dict[str, int]:
        counts = {c: 1 for c in self.div_id}
        for r in self.inp.row_to_kpi:
            counts[self._division_of(r)] += 1
        return counts

    def _division_of(self, r: dict) -> str:
        if r["division_code"]:
            return r["division_code"]
        return self.inp.domains[self.inp.sources[r["origin_ref"]].domain]["division_code"]

    # ------------------------------------------------------------------ definitions
    def definitions(self) -> None:
        self.defs: dict[str, dict] = {}
        self.dbt_metric_def: dict[str, str] = {}
        for r in self.inp.row_to_kpi:
            src = self.inp.sources[r["origin_ref"]]
            fx = r["fix"]
            d = {
                "definition_id": r["definition_id"], "kpi_id": r["kpi_id"],
                "division_id": self.div_id[self._division_of(r)],
                "display_name": apply_fixes(src.term, "display_name", fx),
                "definition_text": apply_fixes(src.definition_text, "definition_text", fx),
                "metric_type": r["metric_type"], "formula": dbt_formula(src.dbt) if src.dbt else None,
                "unit": r["unit"], "grain": r["grain"],
                "source_table": src.source_table,
                "source_column": apply_fixes(src.source_column, "source_column", fx),
                "related_columns": apply_fixes(src.related_columns, "related_columns", fx),
                "origin": src.origin, "origin_ref": src.origin_ref,
            }
            self.defs[d["definition_id"]] = d
            if src.dbt:
                self.dbt_metric_def[src.dbt["name"]] = d["definition_id"]
        for h in self.sc["handwritten_definitions"]:
            self.defs[h["definition_id"]] = {
                "definition_id": h["definition_id"], "kpi_id": h["kpi_id"], "division_id": self.div_id[h["division"]],
                "display_name": h["display_name"], "definition_text": h["definition_text"],
                "metric_type": h["metric_type"], "formula": h.get("formula"), "unit": h["unit"], "grain": h["grain"],
                "source_table": None, "source_column": None, "related_columns": None,
                "origin": "handwritten", "origin_ref": f"scenarios:{h['ref']}",
            }

    # ------------------------------------------------------------------ lineage
    def relationships(self) -> None:
        rels: list[dict] = []
        seen: set[tuple] = set()

        def add(a, b, typ, origin, role=None, alias=None, offset=None):
            a, b = self.current(a), self.current(b)
            key = (a, b, typ, role, alias, offset)
            if a == b or key in seen:  # moving links to a successor can create a loop or a duplicate
                return
            seen.add(key)
            rels.append({"from_definition_id": a, "to_definition_id": b, "relationship_type": typ, "role": role,
                         "alias": alias, "offset_window": offset, "origin": origin})

        by_measure = {}  # measure -> unfiltered simple metric (the "base" count/sum)
        metrics = {s.dbt["name"]: s.dbt for s in self.inp.sources.values() if s.dbt and s.dbt["name"] in self.dbt_metric_def}
        for name, m in metrics.items():
            if m["type"] == "simple" and not m.get("filter"):
                by_measure.setdefault(measure_name(m), name)
        for name in sorted(metrics, key=lambda n: self.dbt_metric_def[n]):
            m, me = metrics[name], self.dbt_metric_def[name]
            tp = m.get("type_params", {})
            if m["type"] == "ratio":
                for role in ("numerator", "denominator"):
                    ref = tp[role]["name"] if isinstance(tp[role], dict) else tp[role]
                    add(me, self.dbt_metric_def[ref], "composed_of", "dbt", role=role)
            elif m["type"] == "derived":
                for item in tp["metrics"]:
                    item = item if isinstance(item, dict) else {"name": item}
                    add(me, self.dbt_metric_def[item["name"]], "composed_of", "dbt", role="input",
                        alias=item.get("alias"), offset=item.get("offset_window"))
            elif m["type"] == "cumulative":
                base = by_measure.get(measure_name(m))
                if base and base != name:
                    add(me, self.dbt_metric_def[base], "cumulative_of", "dbt")
            elif m["type"] == "simple" and m.get("filter"):
                base = by_measure.get(measure_name(m))
                if base and base != name:
                    add(me, self.dbt_metric_def[base], "subset_of", "dbt")
        for r in self.inp.relationships:
            add(r["from_definition_id"], r["to_definition_id"], r["relationship_type"], "curation")
        for r in self.sc["handwritten_relationships"]:
            add(r["from"], r["to"], r["type"], "handwritten", role=r.get("role"))
        self.t["kpi_relationships"] = [{"relationship_id": f"REL-{i:04d}", **r} for i, r in enumerate(rels, 1)]

    # ------------------------------------------------------------------ owners, statuses, reviews, dates
    def lifecycle(self) -> None:
        rng = self.rng
        code_of = {v: k for k, v in self.div_id.items()}
        fixtures = {f["definition_id"]: f for f in self.sc["definition_fixtures"]}
        reviews: list[dict] = []

        # A newer version is dated after its predecessor's approval, so successors go last.
        successors = {f["superseded_by"]: did for did, f in fixtures.items() if f.get("superseded_by")}
        order = sorted(self.defs)
        order = [d for d in order if d not in successors] + [d for d in order if d in successors]

        for did in order:
            d, fx = self.defs[did], fixtures.get(did, {})
            code = code_of[d["division_id"]]
            # owner
            if fx.get("owner") or self._hand(did).get("owner"):
                owner = fx.get("owner") or self._hand(did)["owner"]
            else:
                pool = self.holders[("contributor", code)] + self.holders[("curator", code)] * 2
                owner = rng.choice(pool)
            # status
            status = fx.get("status") or self._random_status(code)
            d.update(owner_user_id=owner, status=status, version=fx.get("version", 1),
                     superseded_by_id=fx.get("superseded_by"))

            # timeline
            lo = max(self.earliest, self.user_created[owner])
            if did in successors:  # a newer version: created after its predecessor was approved
                lo = max(lo, parse_ts(self.defs[successors[did]]["_approved_at"]) + 60 * DAY)
            hi = self.ref - 45 * DAY
            if status in ("draft", "in_review"):  # open work is recent
                lo, hi = max(lo, self.ref - 75 * DAY), self.ref - 14 * DAY
            if fx.get("superseded_by"):
                hi = min(hi, self.earliest + 300 * DAY)
            t = self.when(lo, hi)
            d["created_at"] = ts(t)
            reviewers = [u for u in self.holders[("reviewer", code)] if u != owner]

            history = []
            if fx.get("changes_requested_before") or (not fx and rng.random() < 0.25):
                history.append("changes_requested")
            final = {"approved": "approved", "deprecated": "approved", "rejected": "rejected"}.get(status)
            if final:
                history.append(final)
            for decision in history:
                t = t + rng.randint(1, 10) * DAY
                reviews.append({"definition_id": did, "reviewer_user_id": rng.choice(reviewers),
                                "decision": decision, "comment": rng.choice(names.REVIEW_COMMENTS[decision]),
                                "reviewed_at": ts(t)})
                if decision == "approved":
                    d["_approved_at"] = ts(t)
            if history and history[-1] == "changes_requested":
                t = t + rng.randint(1, 3) * DAY  # edited (draft) or resubmitted (in_review) afterwards
            d["updated_at"] = ts(t)

        # a deprecated definition was last updated when its successor was approved
        for did, f in fixtures.items():
            if f.get("superseded_by"):
                self.defs[did]["updated_at"] = self.defs[f["superseded_by"]]["_approved_at"]

        reviews.sort(key=lambda r: (r["reviewed_at"], r["definition_id"]))
        self.t["reviews"] = [{"review_id": f"REV-{i:04d}", **r} for i, r in enumerate(reviews, 1)]
        cols = ["definition_id", "kpi_id", "division_id", "display_name", "definition_text", "metric_type", "formula",
                "unit", "grain", "source_table", "source_column", "related_columns", "owner_user_id", "status",
                "version", "superseded_by_id", "created_at", "updated_at", "origin", "origin_ref"]
        self.t["definitions"] = [{c: self.defs[k][c] for c in cols} for k in sorted(self.defs)]

    def _hand(self, did: str) -> dict:
        return next((h for h in self.sc["handwritten_definitions"] if h["definition_id"] == did), {})

    def _random_status(self, code: str) -> str:
        # Commercial's review queue is the UC3 demo, so random fill adds nothing to it.
        if code == "COM":
            return self.rng.choices(["approved", "draft", "rejected"], [82, 10, 8])[0]
        return self.rng.choices(["approved", "in_review", "draft", "rejected"], [74, 10, 8, 8])[0]

    # ------------------------------------------------------------------ kpis
    def kpis(self) -> None:
        first: dict[str, str] = {}
        for d in self.defs.values():
            first[d["kpi_id"]] = min(first.get(d["kpi_id"], d["created_at"]), d["created_at"])
        self.t["kpis"] = [
            {"kpi_id": k["kpi_id"], "slug": k["slug"], "name": k["name"], "description": k["description"],
             "created_at": first.get(k["kpi_id"], ts(self.earliest))}
            for k in self.inp.kpis
        ]

    # ------------------------------------------------------------------ assets
    def assets(self) -> None:
        rng, sc = self.rng, self.sc
        code_of = {v: k for k, v in self.div_id.items()}
        published = defaultdict(list)  # division code -> published definitions
        for did in sorted(self.defs):
            d = self.defs[did]
            if d["status"] in ("approved", "deprecated"):
                published[code_of[d["division_id"]]].append(did)

        rows, links, names_used = [], [], set()
        for a in sc["assets"]:
            linked = [self.defs[x] for x in a["definitions"]]
            created = max(parse_ts(x["updated_at"]) for x in linked) + DAY
            rows.append({"asset_id": a["asset_id"], "asset_type": a["asset_type"], "name": a["name"],
                         "description": a["description"], "tool": a["tool"],
                         "url": f"{sc['company']['bi_url']}/{a['asset_type']}s/{slugify(a['name'])}",
                         "division_id": self.div_id[a["division"]], "owner_user_id": a["owner"],
                         "created_at": ts(min(created, self.ref))})
            links += [(a["asset_id"], x) for x in a["definitions"]]
            names_used.add(a["name"])

        divisions = [c for c in self.div_id if published[c]]
        weights = [len(published[c]) for c in divisions]
        n = len(rows)
        while len(rows) < sc["generation"]["assets_total"]:
            code = rng.choices(divisions, weights)[0]
            cadence, noun = rng.choice(names.ASSET_CADENCES), rng.choice(names.ASSET_NOUNS)
            name = f"{names.DIVISION_NAME[code]} {cadence} {noun}"
            if name in names_used:
                continue
            names_used.add(name)
            n += 1
            aid = f"AST-{n:03d}"
            kind = "report" if noun.endswith(("Report", "Pack")) else "dashboard"
            picked = rng.sample(published[code], min(len(published[code]), rng.randint(2, 6)))
            chosen = sorted({self.current(x) for x in picked})  # a dashboard uses the latest version
            created = max(parse_ts(self.defs[x]["updated_at"]) for x in chosen) + rng.randint(1, 30) * DAY
            owner = rng.choice(sorted(u for u, h in self.home.items() if h == self.div_id[code]))
            rows.append({"asset_id": aid, "asset_type": kind, "name": name,
                         "description": f"{cadence} {noun.lower()} for the {names.DIVISION_NAME[code]} division.",
                         "tool": rng.choice(names.ASSET_TOOLS),
                         "url": f"{sc['company']['bi_url']}/{kind}s/{slugify(name)}",
                         "division_id": self.div_id[code], "owner_user_id": owner,
                         "created_at": ts(min(created, self.ref))})
            links += [(aid, x) for x in chosen]
        self.t["assets"] = rows
        self.t["asset_definitions"] = [{"asset_id": a, "definition_id": d} for a, d in sorted(links)]

    # ------------------------------------------------------------------ community tags
    def community_tags(self) -> None:
        rng, ct = self.rng, self.sc["community_tags"]
        labels = ct["labels"]
        tag_id = {label: f"TAG-{i:03d}" for i, label in enumerate(labels, 1)}
        users = sorted(self.user_created)
        published = sorted(d for d, x in self.defs.items() if x["status"] in ("approved", "deprecated"))
        uses: dict[tuple[str, str], dict] = {}

        def tag(label: str, did: str) -> None:
            did = self.current(did)
            key = (did, tag_id[label])
            if key in uses:
                return
            user = rng.choice(users)
            lo = max(parse_ts(self.defs[did]["updated_at"]), self.user_created[user])
            uses[key] = {"definition_id": did, "tag_id": tag_id[label], "source": "user", "confidence": None,
                         "status": None, "tagged_by": user, "tagged_at": ts(self.when(lo, self.ref))}

        for f in ct["fixtures"]:
            for did in f["definitions"]:
                tag(f["label"], did)
        for label in labels:  # every label is used at least once
            if not any(k[1] == tag_id[label] for k in uses):
                tag(label, rng.choice(published))
        # Labels with fixtures keep exactly their fixture uses, so the UC4 story (north-star variants) is stable.
        free = [label for label in labels if label not in {f["label"] for f in ct["fixtures"]}]
        for _ in range(self.sc["generation"]["community_tag_uses_per_label"] * len(free)):
            tag(rng.choice(free), rng.choice(published))

        first: dict[str, dict] = {}
        for u in sorted(uses.values(), key=lambda u: (u["tagged_at"], u["definition_id"])):
            first.setdefault(u["tag_id"], u)
        self.t["tags"] = [
            {"tag_id": tag_id[label], "kind": "community", "label": label, "facet": None, "concept_uri": None,
             "created_by": first[tag_id[label]]["tagged_by"], "created_at": first[tag_id[label]]["tagged_at"]}
            for label in labels
        ]
        self.t["definition_tags"] = [uses[k] for k in sorted(uses)]


# ---------------------------------------------------------------------- dbt helpers
def measure_name(m: dict) -> str | None:
    meas = m.get("type_params", {}).get("measure")
    return meas["name"] if isinstance(meas, dict) else meas


def clean_filter(f: str) -> str:
    """{{ Dimension('order_id__is_food_order') }} = true  ->  order_id__is_food_order = true"""
    f = re.sub(r"\{\{\s*Dimension\('([^']+)'\)\s*\}\}", r"\1", f)
    return " ".join(f.split())


def dbt_formula(m: dict) -> str:
    tp = m.get("type_params", {})
    if m["type"] == "ratio":
        num = tp["numerator"]["name"] if isinstance(tp["numerator"], dict) else tp["numerator"]
        den = tp["denominator"]["name"] if isinstance(tp["denominator"], dict) else tp["denominator"]
        return f"{num} / {den}"
    if m["type"] == "derived":
        return " ".join(tp["expr"].split())
    if m["type"] == "cumulative":
        window = tp.get("window")
        return f"cumulative {measure_name(m)} over {window}" if window else f"cumulative {measure_name(m)} (all time)"
    formula = measure_name(m)
    if m.get("filter"):
        formula += f" where {clean_filter(m['filter'])}"
    return formula


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
