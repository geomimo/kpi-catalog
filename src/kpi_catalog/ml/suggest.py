"""Suggestions for the definition editor (PRD §6, F10). The interface is fixed here; M8 fills in the body.

The editor passes the form as it stands. M8 encodes the same text the batch tagger encodes for seed definitions
(`tagger.definition_input`: display name, definition text, formula), so a new submission is compared with the
saved embeddings like for like, and only the new text is encoded at runtime.
"""

from collections.abc import Mapping


def suggest_for_definition(form: Mapping[str, str | None]) -> dict:
    """Suggestions for a definition being written. `form` has at least display_name, definition_text, formula and
    unit (empty or missing while not filled in). Returns:

        {"tags": [{label, facet, concept_uri, confidence}],      # theme and business line (T1/T2)
         "measure_type": {label, concept_uri} | None,            # from the unit (vocab/skos.measure_types)
         "similar": [{definition_id, display_name, kpi_slug, score}]}  # "a similar KPI already exists"

    Everything is empty until M8.
    """
    return {"tags": [], "measure_type": None, "similar": []}
