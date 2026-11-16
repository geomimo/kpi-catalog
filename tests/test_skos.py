"""Checks on the vocabulary helpers in kpi_catalog.vocab.skos (task V3, PRD §4.2, §5)."""

import pytest

from kpi_catalog.vocab import skos
from kpigen.inputs import read_csv
from kpigen.paths import SEED


@pytest.fixture(scope="module")
def g():
    return skos.load_vocab()


def test_measure_type_lookup(g):
    lookup = {unit: c.name for unit, c in skos.measure_types(g).items()}
    assert lookup == {"EUR": "MonetaryAmount", "USD": "MonetaryAmount", "%": "Percentage", "ratio": "Ratio",
                      "times": "Ratio", "count": "Count", "score": "Score"}


def test_every_seed_unit_has_a_measure_type(g):
    lookup = skos.measure_types(g)
    assert {d["unit"] for d in read_csv(SEED / "definitions.csv")} <= set(lookup)
