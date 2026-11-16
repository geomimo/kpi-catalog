"""Checks on the ML evaluation helpers (task M5, PRD §6)."""

import pytest

from kpi_catalog.ml import evaluate
from kpi_catalog.vocab import skos


@pytest.fixture(scope="module")
def rules():
    return evaluate.keyword_rules(skos.themes(skos.load_vocab()))


def test_keyword_rules_use_vocabulary_labels(rules):
    assert evaluate.keyword_predict("Total sales in the period.", rules, "Cost") == "Revenue"  # altLabel "Sales"
    assert evaluate.keyword_predict("Number of widgets.", rules, "Cost") == "Cost"  # no hit: the fallback
    assert evaluate.keyword_predict("Salesforce licences.", rules, "Cost") == "Cost"  # whole words only


def test_keyword_ties_go_to_the_earliest_hit(rules):
    assert evaluate.keyword_predict("Tax on sales.", rules, "Cost") == "Tax"


def test_accuracy_and_macro_f1():
    acc, f1 = evaluate.accuracy_f1(["a", "a", "b", "b"], ["a", "a", "a", "b"])
    assert acc == 0.75
    assert f1 == pytest.approx((0.8 + 2 / 3) / 2)


def test_set_scores():
    s = evaluate.set_scores([{"a"}, {"a", "b"}], [{"a", "c"}, {"a"}])
    assert (s["precision"], s["recall"], s["exact"], s["second"]) == (2 / 3, 2 / 3, 0.0, 1)
