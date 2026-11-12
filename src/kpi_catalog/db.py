"""The app database (PRD §4, §11): build instance/catalog.sqlite from schema.sql + data/seed/, search index, Flask access.

Build it with: uv run flask --app kpi_catalog.web init-db
"""

import os
import sqlite3
from pathlib import Path

import click
from flask import Flask, current_app, g
from flask.cli import with_appcontext

from kpigen.paths import ROOT, SCHEMA, SEED
from kpigen.validate import SeedError, fill_from_seed

INSTANCE = ROOT / "instance"
DATABASE = INSTANCE / "catalog.sqlite"

__all__ = ["DATABASE", "INSTANCE", "SeedError", "build", "build_search_index", "connect", "get_db", "init_app"]


def connect(path: Path) -> sqlite3.Connection:
    """A connection with foreign keys enforced and rows readable by column name."""
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def build(db_path: Path = DATABASE, seed_dir: Path = SEED, schema: Path = SCHEMA) -> None:
    """Build the database from scratch: schema.sql, then every seed CSV (foreign-key order), then the search index.

    Any old file is deleted first. The build writes to a temporary file that only replaces the target once
    everything has loaded and passed PRAGMA foreign_key_check, so a failed build (SeedError) leaves no database.
    Called by `flask init-db` and, later, by `kpi-catalog build` (M6).
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = db_path.with_name(db_path.name + ".building")
    db_path.unlink(missing_ok=True)
    tmp.unlink(missing_ok=True)
    try:
        con = connect(tmp)
        try:
            con.executescript(schema.read_text(encoding="utf-8"))
            fill_from_seed(con, seed_dir)
            build_search_index(con)
        finally:
            con.close()
        os.replace(tmp, db_path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def build_search_index(con: sqlite3.Connection) -> None:
    """(Re)build the FTS5 table definitions_fts: one row per definition with its KPI name, display name,
    definition text and the labels of all its tags (official and community).

    Safe to re-run whenever tags change (official tags arrive with V3 and M2). Every definition is indexed;
    the visibility rule (PRD §4.5) is applied when querying, by joining back to definitions.
    """
    with con:
        con.execute("DROP TABLE IF EXISTS definitions_fts")
        con.execute(
            "CREATE VIRTUAL TABLE definitions_fts USING fts5("
            " definition_id UNINDEXED, kpi_name, display_name, definition_text, tag_labels,"
            " tokenize = 'porter unicode61')"
        )
        con.execute(
            """
            INSERT INTO definitions_fts (definition_id, kpi_name, display_name, definition_text, tag_labels)
            SELECT d.definition_id, k.name, d.display_name, d.definition_text,
                   (SELECT group_concat(t.label, ' ; ')
                      FROM definition_tags dt JOIN tags t ON t.tag_id = dt.tag_id
                     WHERE dt.definition_id = d.definition_id)
              FROM definitions d JOIN kpis k ON k.kpi_id = d.kpi_id
            """
        )


def get_db() -> sqlite3.Connection:
    """The current request's connection (opened on first use, closed at teardown)."""
    if "db" not in g:
        g.db = connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


@click.command("init-db")
@with_appcontext
def init_db_command() -> None:
    """Build instance/catalog.sqlite from schema.sql and data/seed/ (deletes the old file)."""
    path = Path(current_app.config["DATABASE"])
    try:
        build(path)
    except SeedError as e:
        raise click.ClickException(str(e)) from e
    con = connect(path)
    counts = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("kpis", "definitions", "users")}
    con.close()
    click.echo(f"Built {path}: " + ", ".join(f"{n} {t}" for t, n in counts.items()) + "; search index ready.")


def init_app(app: Flask) -> None:
    app.config.setdefault("DATABASE", str(DATABASE))
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
