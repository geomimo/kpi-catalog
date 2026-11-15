"""Allowed values of the enum columns in schema.sql, for forms and checks.

These must match the CHECK constraints in schema.sql (tests/test_auth_editor.py::test_field_values_match_schema).
"""

UNITS = ("EUR", "USD", "%", "ratio", "times", "count", "score")
GRAINS = ("daily", "weekly", "monthly", "quarterly")
METRIC_TYPES = ("base", "simple", "ratio", "derived", "cumulative")
STATUSES = ("draft", "in_review", "approved", "rejected", "deprecated")
