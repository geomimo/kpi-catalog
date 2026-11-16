"""The `kpi-catalog` command (PRD §11).

    uv run kpi-catalog build [--db instance/catalog.sqlite]

`build` (M6) goes from data/seed/ to the database the app runs on: schema.sql, the seed, the official tags and the
search index (`db.build`), then the ML batch (`tagger.run`: T1/T2 tags, T3 unit check, search index again). The old
database is deleted first, so definitions made in the app are lost. The similarity flags (M7) join the batch here.
"""

import argparse
import sys
from pathlib import Path

from kpi_catalog import db
from kpi_catalog.ml import tagger
from kpigen.paths import SEED


def build(db_path: Path = db.DATABASE, encode: tagger.Encoder | None = None, seed_dir: Path = SEED):
    """Build a tagged and flagged database at `db_path`, embeddings next to it. Returns `tagger.run`'s result.
    `encode` defaults to the real model; tests pass a fake one."""
    db_path = Path(db_path)
    db.build(db_path, seed_dir)
    con = db.connect(db_path)
    try:
        return tagger.run(con, encode or tagger.sentence_encoder(), db_path.with_name("embeddings.npy"))
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kpi-catalog", description="KPI Catalog commands (PRD §11).")
    commands = parser.add_subparsers(dest="command", required=True)
    build_cmd = commands.add_parser("build", help="data/seed/ → tagged and flagged instance/catalog.sqlite (M6)")
    build_cmd.add_argument("--db", type=Path, default=db.DATABASE)
    args = parser.parse_args(argv)
    try:
        result = build(args.db)
    except db.SeedError as e:
        print(e, file=sys.stderr)
        return 1
    con = db.connect(args.db)
    counts = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("kpis", "definitions", "users")}
    con.close()
    print(f"Built {args.db}: " + ", ".join(f"{n} {t}" for t, n in counts.items()) + "; search index ready.")
    tagger.report(*result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
