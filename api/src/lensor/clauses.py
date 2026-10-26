# The 10 clause types of version 1. The names are the CUAD category names, in display order.
CLAUSE_TYPES: tuple[str, ...] = (
    "Expiration Date",
    "Renewal Term",
    "Notice Period to Terminate Renewal",
    "Governing Law",
    "Termination for Convenience",
    "Change of Control",
    "Anti-Assignment",
    "Non-Compete",
    "Cap on Liability",
    "Uncapped Liability",
)

_BY_LOWER = {name.lower(): name for name in CLAUSE_TYPES}


def canonical_clause_type(name: str) -> str | None:
    """Return the CLAUSE_TYPES spelling of a name, or None when it is not one of the 10."""
    return _BY_LOWER.get(name.strip().lower())
