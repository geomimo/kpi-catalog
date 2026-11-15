"""Who may do and see what (PRD §4.1, §4.5, §10).

- "Log in as" (W3): the session holds a user_id; only the three demo personas can be chosen in the app.
- One permission check: has_permission(user, code, division_id). A role grants its permissions in the division
  where it is held (user_roles.division_id); the admin role (division NULL) has every permission everywhere.
- One visibility rule: visible() is the SQL condition used wherever definitions are listed, counted or opened.
"""

import sqlite3
from functools import wraps

from flask import abort, g, has_request_context, session

from kpi_catalog.db import get_db

# The personas the "log in as" switcher offers (PRD §7). Other seed users stay owners and reviewers only.
PERSONA_USER_IDS = ("USR-005", "USR-007", "USR-053")  # Emma (Observer), Katerina (Curator), Noah (Admin)
SESSION_KEY = "user_id"

# Readable by everyone (PRD §4.5).
PUBLIC_STATUSES = ("approved", "deprecated")


def load_user(con: sqlite3.Connection, user_id: str) -> dict | None:
    """A user with their roles and permissions: {user_id, full_name, job_title, home_division_id, home_division,
    roles: [(role_name, division_name or None)], admin: bool, perms: {code: {division_id, ...}}}."""
    user = con.execute(
        """SELECT u.user_id, u.full_name, u.job_title, u.home_division_id, v.name AS home_division
             FROM users u JOIN divisions v ON v.division_id = u.home_division_id WHERE u.user_id = ?""",
        (user_id,),
    ).fetchone()
    if user is None:
        return None
    user = dict(user)
    rows = con.execute(
        """SELECT r.code AS role, r.name AS role_name, ur.division_id, v.name AS division_name, p.code AS perm
             FROM user_roles ur JOIN roles r ON r.role_id = ur.role_id
             LEFT JOIN divisions v ON v.division_id = ur.division_id
             JOIN role_permissions rp ON rp.role_id = r.role_id
             JOIN permissions p ON p.permission_id = rp.permission_id
            WHERE ur.user_id = ?
            ORDER BY r.role_id, v.name""",
        (user_id,),
    ).fetchall()
    user["admin"] = any(r["role"] == "admin" for r in rows)
    user["roles"] = list(dict.fromkeys((r["role_name"], r["division_name"]) for r in rows))
    user["perms"] = {}
    for r in rows:
        if r["division_id"] is not None:
            user["perms"].setdefault(r["perm"], set()).add(r["division_id"])
    return user


def current_user() -> dict | None:
    """The logged-in user (loaded once per request), or None for an anonymous visitor."""
    if not has_request_context():
        return None
    if "user" not in g:
        user_id = session.get(SESSION_KEY)
        g.user = load_user(get_db(), user_id) if user_id else None
    return g.user


def has_permission(user: dict | None, code: str, division_id: str | None = None) -> bool:
    """Does `user` hold a role granting `code` in `division_id`? With division_id None: in any division.
    Admins have every permission everywhere; an anonymous visitor (None) has none (read-only)."""
    if user is None:
        return False
    if user["admin"]:
        return True
    divisions = user["perms"].get(code, set())
    return bool(divisions) if division_id is None else division_id in divisions


def divisions_with(user: dict | None, code: str) -> list[str]:
    """The division_ids where `user` holds `code` (every division for admins), sorted."""
    if user is None:
        return []
    if user["admin"]:
        return [r[0] for r in get_db().execute("SELECT division_id FROM divisions ORDER BY division_id")]
    return sorted(user["perms"].get(code, set()))


def visible(alias: str = "d") -> tuple[str, list]:
    """An SQL condition, and its parameters, that keeps only the definitions (table alias `alias`) the current
    visitor may read (PRD §4.5): approved and deprecated for everyone; draft, in_review and rejected for the owner,
    for users with definition.view_unpublished in that division, and for admins. Use it in every query that
    lists, counts or opens definitions:

        cond, params = visible("d")
        con.execute(f"SELECT ... FROM definitions d WHERE d.kpi_id = ? AND {cond}", [kpi_id, *params])
    """
    public = f"{alias}.status IN ({', '.join('?' * len(PUBLIC_STATUSES))})"
    user = current_user()
    if user is None:
        return public, list(PUBLIC_STATUSES)
    if user["admin"]:
        return "1 = 1", []
    divisions = divisions_with(user, "definition.view_unpublished")
    in_division = f" OR {alias}.division_id IN ({', '.join('?' * len(divisions))})" if divisions else ""
    return (f"({public} OR {alias}.owner_user_id = ?{in_division})",
            [*PUBLIC_STATUSES, user["user_id"], *divisions])


def forbid(code: str, division_id: str | None = None):
    """Abort with a 403 that says, in words, which permission is missing (from permissions.description)."""
    row = get_db().execute("SELECT description FROM permissions WHERE code = ?", (code,)).fetchone()
    what = row["description"].lower() if row else code
    where = ""
    if division_id:
        name = get_db().execute("SELECT name FROM divisions WHERE division_id = ?", (division_id,)).fetchone()
        where = f" in {name['name']}" if name else ""
    abort(403, description=f"This needs permission to {what}{where}.")


def require(code: str):
    """Route decorator: 403 unless the current user holds `code` in at least one division."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not has_permission(current_user(), code):
                forbid(code)
            return view(*args, **kwargs)
        return wrapped
    return decorator
