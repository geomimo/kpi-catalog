"""Download the pinned external sources into data/raw/ (PRD §3.2).

The sources declare no licence, so they are fetched at fixed versions and never
committed. Each file is checked against a pinned SHA-256 so a changed upstream
file can't silently change the seed.
"""

import datetime as dt
import hashlib
import urllib.request

from .paths import RAW

HF_REVISION = "c148c8c2945589fec92d91380e2f5b314ad18a91"
DBT_COMMIT = "c54c8fb8bea86c0c4d3d5c588d55f8de9de57ade"

HF_BASE = f"https://huggingface.co/datasets/kavish218/multi_domain_dataset/resolve/{HF_REVISION}"
DBT_BASE = f"https://raw.githubusercontent.com/dbt-labs/jaffle-sl-template/{DBT_COMMIT}/models/marts/customer360"

# local path (relative to data/raw) -> (url, sha256)
SOURCES: dict[str, tuple[str, str]] = {
    "hf/testcontext_file1.csv": (f"{HF_BASE}/testcontext_file1.csv", "0732ee9881a547485e21f960671fb387e5beaeee9ff6d81266bda9134764b033"),
    "dbt/orders.yml": (f"{DBT_BASE}/orders.yml", "c3a5b6a19585e765ae2732542b9d5b3b09aba9b9a294a4a6dc655deb39d8a164"),
    "dbt/order_items.yml": (f"{DBT_BASE}/order_items.yml", "095c7aa7a61cfce4430c780bf376294862abb9cefbfbcf543517e3077561b6ff"),
    "dbt/customers.yml": (f"{DBT_BASE}/customers.yml", "6bd10a5ddd0d82ce0bc3b6f9fa6b5da6d99ae291d553da7be5b5e41bc2f99183"),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download() -> None:
    lines = [f"Retrieved {dt.date.today().isoformat()} by `uv run kpigen download`.", ""]
    for rel, (url, expected) in SOURCES.items():
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = resp.read()
        got = sha256(data)
        if got != expected:
            raise SystemExit(f"Hash mismatch for {rel}: expected {expected}, got {got}\n  {url}")
        target = RAW / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        lines.append(f"- {rel}: {url} (sha256 {got})")
        print(f"ok  {rel}")
    (RAW / "SOURCES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Sources written to {RAW}")


def check_present() -> None:
    """Fail clearly if the raw files are missing or changed (generation never downloads)."""
    for rel, (_, expected) in SOURCES.items():
        path = RAW / rel
        if not path.exists():
            raise SystemExit(f"Missing {path}. Run `uv run kpigen download` first.")
        if sha256(path.read_bytes()) != expected:
            raise SystemExit(f"{path} doesn't match its pinned hash. Run `uv run kpigen download` again.")
