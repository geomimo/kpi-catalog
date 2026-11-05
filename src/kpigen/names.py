"""Word lists for the synthetic organisation (users, job titles, dashboards, review comments).

None of this is KPI content: review comments are deliberately generic per decision type, so they
never pretend to know what a definition says (PRD §3.4).
"""

FIRST = [
    "Alex", "Amira", "Ben", "Carlos", "Chloe", "Daniel", "Elena", "Fatima", "Felix", "Giorgos", "Hana", "Ibrahim",
    "Ines", "Jakub", "Jonas", "Julia", "Kofi", "Lars", "Laura", "Lena", "Lucas", "Maria", "Marta", "Mateo", "Mei",
    "Nadia", "Nikos", "Olivia", "Omar", "Paula", "Pieter", "Priya", "Rafael", "Rosa", "Sam", "Sara", "Sofia",
    "Stefan", "Tariq", "Tom", "Valentina", "Wei", "Yusuf", "Zoe",
]
LAST = [
    "Andersen", "Bakker", "Becker", "Costa", "Dimitriou", "Dubois", "Fischer", "Georgiou", "Hansen", "Hoffmann",
    "Ivanova", "Jensen", "Kaya", "Kowalski", "Lambert", "Larsen", "Martin", "Meyer", "Moreau", "Nakamura", "Novak",
    "Nowak", "Pereira", "Petrov", "Rossi", "Santos", "Schmidt", "Silva", "Smit", "Tanaka", "Visser", "Weber",
    "Yilmaz", "Zhang",
]

DIVISION_NAME = {
    "FIN": "Finance", "COM": "Commercial", "MKT": "Marketing", "PRD": "Product",
    "OPS": "Operations", "PPL": "People", "RSK": "Risk & Compliance", "DAT": "Data & Analytics",
}
DIVISION_PREFIX = {
    "FIN": "Finance", "COM": "Commercial", "MKT": "Marketing", "PRD": "Product",
    "OPS": "Operations", "PPL": "People", "RSK": "Risk", "DAT": "Data",
}
ROLE_TITLES = {
    "observer": ["Analyst", "Associate", "Specialist", "Manager"],
    "contributor": ["Analyst", "BI Developer", "Reporting Analyst", "Data Analyst"],
    "curator": ["Analytics Lead", "Reporting Lead"],
    "reviewer": ["Controller", "Head of Reporting", "Director"],
}

ASSET_CADENCES = ["Daily", "Weekly", "Monthly", "Quarterly"]
ASSET_NOUNS = ["Performance Dashboard", "Overview Dashboard", "KPI Report", "Review Pack", "Trend Dashboard"]
ASSET_TOOLS = ["Power BI", "Tableau", "Looker", "Excel"]

REVIEW_COMMENTS = {
    "approved": [
        "Approved.",
        "Approved; consistent with the division's reporting standards.",
        "Looks good, approved.",
    ],
    "changes_requested": [
        "Please state the grain and the source table explicitly.",
        "Please explain how this differs from the other definitions of this KPI.",
        "Please check the unit before resubmitting.",
        "Please add the formula or the calculation steps.",
    ],
    "rejected": [
        "Rejected: duplicates an existing definition in this division.",
        "Rejected: not used in any of the division's reporting.",
    ],
}
