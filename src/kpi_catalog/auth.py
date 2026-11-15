"""Who may see what (PRD §4.5, §10). Every page that lists or opens definitions goes through `visible()`.

Until "log in as" (W3) there is no logged-in user, so every visitor is treated as an Observer: only approved
and deprecated definitions are readable. W3 adds the user: their own definitions, the divisions where they
hold `definition.view_unpublished`, and everything for Admins.
"""

# Readable by everyone (PRD §4.5).
PUBLIC_STATUSES = ("approved", "deprecated")


def current_user():
    """The logged-in user, or None for an anonymous visitor (always None until W3)."""
    return None


def visible(alias: str = "d") -> tuple[str, list]:
    """An SQL condition, and its parameters, that keeps only the definitions (table alias `alias`) the current
    visitor may read. Use it in every query that lists, counts or opens definitions:

        cond, params = visible("d")
        con.execute(f"SELECT ... FROM definitions d WHERE d.kpi_id = ? AND {cond}", [kpi_id, *params])
    """
    if current_user() is None:
        return f"{alias}.status IN ({', '.join('?' * len(PUBLIC_STATUSES))})", list(PUBLIC_STATUSES)
    raise NotImplementedError("visibility for logged-in users comes with W3")
