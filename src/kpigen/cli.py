"""kpigen: generate and validate the KPI Catalog seed (PRD §3.4).

    uv run kpigen download     fetch the pinned sources into data/raw/ (the only network step)
    uv run kpigen              generate data/seed/ and validate it
    uv run kpigen --strict     same, but also fail while TODO(george) placeholders remain
    uv run kpigen validate     validate an existing seed directory
"""

import argparse
from collections import Counter
from pathlib import Path

from .paths import SEED


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="kpigen", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", nargs="?", default="generate", choices=["generate", "download", "validate"])
    p.add_argument("--out", type=Path, default=SEED, help="seed directory (default: data/seed)")
    p.add_argument("--strict", action="store_true", help="fail while TODO(george) placeholders remain")
    p.add_argument("--no-validate", action="store_true", help="skip validation (used by tests)")
    args = p.parse_args(argv)

    if args.command == "download":
        from .download import download
        download()
        return

    from .validate import SeedError, validate

    if args.command == "generate":
        from .download import check_present
        from .generate import Generator
        from .inputs import count_todos, load_inputs
        from .write import write_seed

        check_present()
        tables = Generator(load_inputs()).build()
        write_seed(tables, args.out)
        status = Counter(d["status"] for d in tables["definitions"])
        print(f"wrote {args.out}: {len(tables['definitions'])} definitions of {len(tables['kpis'])} KPIs "
              f"({', '.join(f'{k} {v}' for k, v in sorted(status.items()))}), {len(tables['users'])} users, "
              f"{len(tables['assets'])} assets, {len(tables['tags'])} community tags "
              f"({len(tables['definition_tags'])} uses), {len(tables['excluded'])} excluded source rows", flush=True)
        todos = count_todos()
        if todos:
            print(f"WARNING {sum(todos.values())} TODO(george) placeholders left: "
                  + ", ".join(f"{k} {v}" for k, v in todos.items()))
            if args.strict:
                raise SystemExit("--strict: fill in the TODO(george) placeholders first")
        if args.no_validate:
            return

    try:
        validate(args.out)
    except SeedError as e:
        raise SystemExit(f"INVALID SEED: {e}")


if __name__ == "__main__":
    main()
