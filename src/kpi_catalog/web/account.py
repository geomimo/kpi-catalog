""""Log in as" (W3, PRD §7, §9 F1) and the role-based top bar from Ioanna's navigation wireframe.

The switcher offers only the three personas in auth.PERSONA_USER_IDS. The menus are derived from permissions,
not from role names, so they always match what the user is allowed to open.
"""

from flask import abort, flash, redirect, render_template, request, session, url_for

from kpi_catalog.auth import PERSONA_USER_IDS, SESSION_KEY, current_user, has_permission, load_user
from kpi_catalog.db import get_db


def catalog_menu(user: dict | None) -> list[tuple[str, str, str]]:
    """(endpoint, label, icon) items of the Catalog dropdown, as in the wireframe: Contributor: Browse KPIs,
    My Definitions, Create New KPI; Curator: ... Create / Edit KPI, Tag Curation; Reviewer: Browse KPIs, Review
    Queue; Admin: all of them. An Observer only browses, so Catalog is a plain link."""
    items = [("browse", "Browse KPIs", "search")]
    if has_permission(user, "definition.propose"):
        items.append(("my_definitions", "My Definitions", "file-text"))
        if has_permission(user, "definition.edit"):
            items.append(("new_definition", "Create / Edit KPI", "pencil"))
        else:
            items.append(("new_definition", "Create New KPI", "plus"))
    if has_permission(user, "definition.approve"):
        items.append(("review", "Review Queue", "circle-check"))
    if has_permission(user, "tag.manage"):
        items.append(("curate_tags", "Tag Curation", "tag"))
    return items


def personas() -> list[dict]:
    """The switcher entries: each persona with name, job title and role(s)."""
    con = get_db()
    return [u for u in (load_user(con, uid) for uid in PERSONA_USER_IDS) if u is not None]


def role_label(user: dict) -> str:
    """"Observer · Finance", "Curator · Commercial", "Admin"."""
    return ", ".join(f"{role} · {division}" if division else role for role, division in user["roles"]) or "No role"


def nav_context() -> dict:
    user = current_user()
    return {
        "user": user,
        "catalog_items": catalog_menu(user),
        "show_governance": has_permission(user, "governance.manage"),
        "personas": personas(),
        "role_label": role_label,
    }


def _back(target: str | None) -> str:
    """Only redirect to a path on this site."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("home")


def login_as():
    """POST /login-as: user_id must be one of the personas."""
    user_id = request.form.get("user_id", "")
    if user_id not in PERSONA_USER_IDS:
        abort(400, description="You can only log in as one of the demo personas.")
    session[SESSION_KEY] = user_id
    user = load_user(get_db(), user_id)
    flash(f"You are now {user['full_name']} ({role_label(user)}).")
    return redirect(_back(request.form.get("next")))


def logout():
    """POST /logout: back to an anonymous, read-only visitor."""
    session.pop(SESSION_KEY, None)
    flash("Logged out. You are browsing as a read-only visitor.")
    return redirect(_back(request.form.get("next")))


def forbidden(error):
    return render_template("403.html", title="Not allowed", message=error.description), 403
