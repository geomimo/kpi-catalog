"""Repository paths used by kpigen."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
SEED = ROOT / "data" / "seed"
CURATION = ROOT / "kpigen" / "curation"
SCENARIOS = ROOT / "kpigen" / "scenarios.yaml"
SCHEMA = ROOT / "schema.sql"
RULE_TESTS = ROOT / "tests" / "test_seed_rules.py"
