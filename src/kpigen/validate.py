"""Validate a seed (PRD §3.6): load it into SQLite with schema.sql, then run the business-rule tests."""

import csv
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from .paths import ROOT, RULE_TESTS, SCHEMA
from .write import SEED_TABLES


class SeedError(Exception):
    pass


def load_seed(seed_dir: Path, schema: Path = SCHEMA) -> sqlite3.Connection:
    """An in-memory database built from schema.sql and the seed CSVs. Raises SeedError on any violation."""
    con = sqlite3.connect(":memory:")
    con.executescript(schema.read_text(encoding="utf-8"))
    fill_from_seed(con, seed_dir)
    return con


def fill_from_seed(con: sqlite3.Connection, seed_dir: Path) -> None:
    """Load the seed CSVs into a database that already has the schema, as one transaction.

    Foreign keys are on but deferred to the end of the transaction (definitions.superseded_by_id can point
    forward); PRAGMA foreign_key_check runs before the commit. Empty cells become NULL. On any violation
    the whole load is rolled back and SeedError lists the problems. Shared by kpigen and the app (W2).
    """
    con.commit()
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("BEGIN")
    con.execute("PRAGMA defer_foreign_keys = ON")
    errors = []
    try:
        for table in SEED_TABLES:
            path = seed_dir / f"{table}.csv"
            if not path.exists():
                raise SeedError(f"missing {path}")
            with path.open(encoding="utf-8", newline="") as fh:
                reader = csv.reader(fh)
                header = next(reader)
                sql = f"INSERT INTO {table} ({', '.join(header)}) VALUES ({', '.join('?' * len(header))})"
                for n, row in enumerate(reader, 2):
                    try:
                        con.execute(sql, [v if v != "" else None for v in row])
                    except sqlite3.DatabaseError as e:  # CHECK, UNIQUE, NOT NULL, triggers
                        errors.append(f"{table}.csv line {n}: {e}")
        for table, rowid, parent, _ in con.execute("PRAGMA foreign_key_check"):
            errors.append(f"{table} rowid {rowid}: foreign key to {parent} doesn't resolve")
        if errors:
            raise SeedError("Seed doesn't fit schema.sql:\n  " + "\n  ".join(errors[:50]))
        con.commit()
    except BaseException:
        con.rollback()
        raise


def validate(seed_dir: Path) -> None:
    load_seed(seed_dir)
    print(f"ok  {seed_dir} loads into schema.sql (FKs, CHECKs, UNIQUEs)", flush=True)
    env = {**os.environ, "KPIGEN_SEED_DIR": str(seed_dir)}
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(RULE_TESTS)],
                            cwd=ROOT, env=env)
    if result.returncode != 0:
        raise SeedError("business-rule tests failed (tests/test_seed_rules.py)")
    print("ok  business rules (tests/test_seed_rules.py)")
