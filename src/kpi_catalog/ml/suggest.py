"""Tag suggestions for the definition editor (PRD §6, F10). Stub until M8.

George's M8 replaces the body: encode only the new text with all-MiniLM-L6-v2 and return theme and
business-line suggestions. The editor already calls this function and shows whatever it returns.
"""


def suggest_for_definition(text: str) -> list[dict]:
    """Suggested official tags for a definition text: [{label, facet, concept_uri, confidence}]. Empty until M8."""
    return []
