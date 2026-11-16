"""Definition editor (W11, PRD §9 F10) and My Definitions (W12, F11).

- /definitions/new and /definitions/<id>/edit (drafts only; editing approved definitions is W20, PRD §14 Q7).
  Both need definition.propose in the chosen division. "Save Draft" keeps status draft, "Submit for Review" sets
  in_review. Validation happens on the server; errors are shown next to the fields and nothing is saved.
- /my-definitions: the user's own definitions by status, with the latest review comment.
Suggestions come from ml.suggest.suggest_for_definition(form) (a stub until M8): tags, measure type and similar
definitions; the panel shows the tags so far (measure type and similar-KPI warning: W11).
"""

import re
import sqlite3
from datetime import datetime, timezone

from flask import abort, flash, redirect, render_template, request, url_for

from kpi_catalog.auth import current_user, divisions_with, forbid, has_permission, require
from kpi_catalog.db import get_db, index_definition
from kpi_catalog.fields import GRAINS, METRIC_TYPES, UNITS
from kpi_catalog.ml.suggest import suggest_for_definition
from kpi_catalog.web.kpis import DEF_COLUMNS, DEF_JOINS, STATUS_LABELS

FORM_FIELDS = ("kpi_name", "new_kpi", "new_kpi_description", "division_id", "display_name", "definition_text",
               "formula", "unit", "grain", "metric_type", "source_table", "source_column", "owner_user_id")
MAX_SHORT = 200     # names, table and column names
MAX_LONG = 5000     # definition text, formula


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _next_id(con: sqlite3.Connection, table: str, column: str, prefix: str) -> str:
    """The next free ID, e.g. DEF-0311 (IDs are never reused or renumbered)."""
    n = con.execute(f"SELECT max(CAST(substr({column}, ?) AS INTEGER)) FROM {table} WHERE {column} LIKE ?",
                    (len(prefix) + 1, prefix + "%")).fetchone()[0] or 0
    return f"{prefix}{n + 1:04d}"


def _slug(con: sqlite3.Connection, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "kpi"
    slug, n = base, 2
    while con.execute("SELECT 1 FROM kpis WHERE slug = ?", (slug,)).fetchone():
        slug, n = f"{base}-{n}", n + 1
    return slug


def _members(con: sqlite3.Connection, division_ids: list[str]) -> dict[str, list[dict]]:
    """Users holding a role in each division (the possible owners there), by division_id."""
    if not division_ids:
        return {}
    rows = con.execute(
        f"""SELECT DISTINCT ur.division_id, u.user_id, u.full_name, u.job_title
              FROM user_roles ur JOIN users u ON u.user_id = ur.user_id
             WHERE ur.division_id IN ({", ".join("?" * len(division_ids))})
             ORDER BY u.full_name""",
        division_ids,
    )
    members: dict[str, list[dict]] = {d: [] for d in division_ids}
    for r in rows:
        members[r["division_id"]].append(dict(r))
    return members


def can_pick_owner(user: dict | None, division_id: str | None = None) -> bool:
    """Curators and admins may name another owner (they hold definition.edit there)."""
    return has_permission(user, "definition.edit", division_id)


def validate(con: sqlite3.Connection, user: dict, form: dict, current_owner: str | None = None) -> tuple[dict, dict]:
    """Check the submitted form. Returns (clean values, {field: error message}). `current_owner` is the draft's
    owner when editing: users who may not pick an owner keep it."""
    v = {k: (form.get(k) or "").strip() for k in FORM_FIELDS}
    errors: dict[str, str] = {}
    data: dict = {"new_kpi": v["new_kpi"] == "1"}

    kpi = con.execute("SELECT kpi_id, name FROM kpis WHERE name = ? COLLATE NOCASE", (v["kpi_name"],)).fetchone()
    if not v["kpi_name"]:
        errors["kpi_name"] = "Choose a KPI concept, or create a new one."
    elif len(v["kpi_name"]) > MAX_SHORT:
        errors["kpi_name"] = f"Keep the name under {MAX_SHORT} characters."
    elif data["new_kpi"]:
        if kpi:
            errors["kpi_name"] = f"“{kpi['name']}” already exists: pick it from the list instead of creating it again."
        if not v["new_kpi_description"]:
            errors["new_kpi_description"] = "Describe the new KPI concept in one neutral line (no division's view)."
        data.update(kpi_id=None, kpi_name=v["kpi_name"], kpi_description=v["new_kpi_description"])
    elif kpi is None:
        errors["kpi_name"] = "No KPI concept has this name. Pick one from the list, or tick “This is a new KPI concept”."
    else:
        data.update(kpi_id=kpi["kpi_id"], kpi_name=kpi["name"])

    allowed = divisions_with(user, "definition.propose")
    if v["division_id"] not in allowed:
        errors["division_id"] = "Choose one of the divisions where you may propose definitions."
    data["division_id"] = v["division_id"]

    data["display_name"] = v["display_name"] or data.get("kpi_name") or v["kpi_name"]
    if len(data["display_name"]) > MAX_SHORT:
        errors["display_name"] = f"Keep the name under {MAX_SHORT} characters."

    data["definition_text"] = v["definition_text"]
    if not v["definition_text"]:
        errors["definition_text"] = "Write the full definition: what is counted, how and when."
    elif len(v["definition_text"]) > MAX_LONG:
        errors["definition_text"] = f"Keep the definition under {MAX_LONG} characters."

    for field, options, label in (("unit", UNITS, "unit"), ("grain", GRAINS, "grain"),
                                  ("metric_type", METRIC_TYPES, "metric type")):
        if v[field] not in options:
            errors[field] = f"Choose a {label}."
        data[field] = v[field]

    data["formula"] = v["formula"] or None
    if not v["formula"] and v["metric_type"] != "base":
        errors["formula"] = "A formula is required unless the metric type is “base”."
    elif len(v["formula"]) > MAX_LONG:
        errors["formula"] = f"Keep the formula under {MAX_LONG} characters."

    for field in ("source_table", "source_column"):
        data[field] = v[field] or None
        if len(v[field]) > MAX_SHORT:
            errors[field] = f"Keep it under {MAX_SHORT} characters."

    # Owner: must hold a role in the definition's division (the seed's business rule, tests/test_seed_rules.py).
    if can_pick_owner(user, v["division_id"]) and v["owner_user_id"]:
        owner = v["owner_user_id"]
    else:
        owner = current_owner or user["user_id"]
    data["owner_user_id"] = owner
    if "division_id" not in errors and not con.execute(
            "SELECT 1 FROM user_roles WHERE user_id = ? AND division_id = ?", (owner, v["division_id"])).fetchone():
        division = con.execute("SELECT name FROM divisions WHERE division_id = ?", (v["division_id"],)).fetchone()
        errors["owner_user_id"] = (f"The owner must hold a role in {division['name']}. "
                                   "Pick someone from that division.")
    return data, errors


def save(con: sqlite3.Connection, data: dict, status: str, definition_id: str | None = None) -> str:
    """Write a valid form as a new definition (or update the draft `definition_id`); returns the definition_id."""
    now = _now()
    with con:
        kpi_id = data["kpi_id"]
        if data["new_kpi"]:
            kpi_id = _next_id(con, "kpis", "kpi_id", "KPI-")
            con.execute("INSERT INTO kpis (kpi_id, slug, name, description, created_at) VALUES (?, ?, ?, ?, ?)",
                        (kpi_id, _slug(con, data["kpi_name"]), data["kpi_name"], data["kpi_description"], now))
        values = (kpi_id, data["division_id"], data["display_name"], data["definition_text"], data["metric_type"],
                  data["formula"], data["unit"], data["grain"], data["source_table"], data["source_column"],
                  data["owner_user_id"], status)
        if definition_id is None:
            definition_id = _next_id(con, "definitions", "definition_id", "DEF-")
            con.execute(
                """INSERT INTO definitions (kpi_id, division_id, display_name, definition_text, metric_type, formula,
                       unit, grain, source_table, source_column, owner_user_id, status, definition_id, version,
                       created_at, updated_at, origin, origin_ref)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, 'app', NULL)""",
                (*values, definition_id, now, now),
            )
        else:
            con.execute(
                """UPDATE definitions SET kpi_id = ?, division_id = ?, display_name = ?, definition_text = ?,
                       metric_type = ?, formula = ?, unit = ?, grain = ?, source_table = ?, source_column = ?,
                       owner_user_id = ?, status = ?, updated_at = ?
                   WHERE definition_id = ?""",
                (*values, now, definition_id),
            )
        index_definition(con, definition_id)
    return definition_id


def _render(user: dict, form: dict, errors: dict, definition: dict | None = None, status: int = 200):
    con = get_db()
    division_ids = divisions_with(user, "definition.propose")
    divisions = [dict(r) for r in con.execute(
        f"SELECT division_id, name FROM divisions WHERE division_id IN ({', '.join('?' * len(division_ids))})"
        " ORDER BY name", division_ids)]
    pick_divisions = [d for d in divisions if can_pick_owner(user, d["division_id"])]
    members = _members(con, [d["division_id"] for d in pick_divisions])
    return render_template(
        "editor.html",
        title=f"Edit {definition['definition_id']}" if definition else "Create New KPI Definition",
        definition=definition,
        form=form,
        errors=errors,
        kpi_names=[r[0] for r in con.execute("SELECT name FROM kpis ORDER BY name")],
        divisions=divisions,
        owner_groups=[(d, members[d["division_id"]]) for d in pick_divisions],
        can_pick_owner=bool(pick_divisions),
        units=UNITS, grains=GRAINS, metric_types=METRIC_TYPES,
        suggestions=suggest_for_definition(form),
    ), status


def _submit(user: dict, definition_id: str | None = None, current_owner: str | None = None):
    con = get_db()
    form = request.form.to_dict()
    action = form.get("action")
    data, errors = validate(con, user, form, current_owner)
    if action not in ("draft", "submit"):
        errors["action"] = "Use “Save Draft” or “Submit for Review”."
    if errors:
        definition = {"definition_id": definition_id} if definition_id else None
        return _render(user, form, errors, definition, status=422)
    status = "in_review" if action == "submit" else "draft"
    definition_id = save(con, data, status, definition_id)
    flash("Submitted for review." if status == "in_review" else "Draft saved.")
    return redirect(url_for("definition", definition_id=definition_id))


@require("definition.propose")
def new_definition():
    user = current_user()
    if request.method == "POST":
        return _submit(user)
    divisions = divisions_with(user, "definition.propose")
    form = {
        "division_id": user["home_division_id"] if user["home_division_id"] in divisions else "",
        "owner_user_id": "" if user["admin"] else user["user_id"],
        "unit": "", "grain": "monthly", "metric_type": "",
        "kpi_name": request.args.get("kpi", ""),
    }
    return _render(user, form, {})


def edit_definition(definition_id: str):
    con = get_db()
    row = con.execute(f"SELECT {DEF_COLUMNS} FROM definitions d {DEF_JOINS} WHERE d.definition_id = ?",
                      (definition_id,)).fetchone()
    if row is None:
        abort(404)
    user = current_user()
    if not has_permission(user, "definition.propose", row["division_id"]):
        forbid("definition.propose", row["division_id"])
    if row["status"] != "draft":
        abort(403, description="Only drafts can be edited here. Editing approved definitions comes later (W20).")
    if request.method == "POST":
        return _submit(user, definition_id, row["owner_user_id"])
    form = {k: row[k] or "" for k in ("division_id", "display_name", "definition_text", "formula", "unit", "grain",
                                      "metric_type", "source_table", "source_column", "owner_user_id")}
    form["kpi_name"] = row["kpi_name"]
    return _render(user, form, {}, dict(row))


# ---- My Definitions (W12) -----------------------------------------------------------------------------------

MY_TABS = [("all", "All"), ("draft", "Draft"), ("in_review", "In review"), ("rejected", "Rejected"),
           ("approved", "Approved")]
SHOW_COMMENT = ("in_review", "rejected")


@require("definition.propose")
def my_definitions():
    con = get_db()
    user = current_user()
    rows = [dict(r) for r in con.execute(
        f"""SELECT {DEF_COLUMNS}, r.decision AS review_decision, r.comment AS review_comment,
                   r.reviewed_at, ru.full_name AS reviewer_name
              FROM definitions d {DEF_JOINS}
              LEFT JOIN reviews r ON r.review_id = (
                   SELECT r2.review_id FROM reviews r2 WHERE r2.definition_id = d.definition_id
                    ORDER BY r2.reviewed_at DESC, r2.review_id DESC LIMIT 1)
              LEFT JOIN users ru ON ru.user_id = r.reviewer_user_id
             WHERE d.owner_user_id = ?
             ORDER BY d.updated_at DESC, d.definition_id DESC""",
        (user["user_id"],),
    )]
    for d in rows:
        d["show_comment"] = d["review_comment"] and (
            d["status"] in SHOW_COMMENT or d["review_decision"] == "changes_requested")
        d["editable"] = d["status"] == "draft" and has_permission(user, "definition.propose", d["division_id"])
    counts = {key: sum(1 for d in rows if key == "all" or d["status"] == key) for key, _ in MY_TABS}
    tab = request.args.get("tab", "all")
    tab = tab if tab in dict(MY_TABS) else "all"
    return render_template(
        "my_definitions.html",
        title="My Definitions",
        rows=[d for d in rows if tab == "all" or d["status"] == tab],
        tab=tab, tabs=MY_TABS, counts=counts,
        status_labels=STATUS_LABELS,
    )
