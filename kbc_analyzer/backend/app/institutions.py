"""Single source of truth for which banks Mymble offers a connection to.

S8-01: the one list every institution-aware piece of code reads from —
the bank picker's GET /api/auth/enable-banking/institutions endpoint,
POST /reauthorize's validation, and enable_banking_sessions' institution
column all agree with this list, not a copy of it. Adding a third bank
is meant to be exactly one line here plus a real Enable Banking ASPSP
name/country pair to look up, not a structural change anywhere else.

Each name must match Enable Banking's own ASPSP `name` field exactly
(confirmed live via GET /aspsps?country=BE for both entries below,
S8-01) — kbc_analyzer.enablebanking.EnableBankingClient._find_aspsp
matches on this string.
"""

SUPPORTED_INSTITUTIONS: list[dict[str, str]] = [
    {"id": "KBC", "name": "KBC", "country": "BE"},
    {"id": "ING", "name": "ING", "country": "BE"},
]

SUPPORTED_INSTITUTION_IDS: list[str] = [i["id"] for i in SUPPORTED_INSTITUTIONS]


def is_supported_institution(institution_id: str) -> bool:
    """True if institution_id is one of the banks Mymble currently offers a connection to."""
    return institution_id in SUPPORTED_INSTITUTION_IDS
