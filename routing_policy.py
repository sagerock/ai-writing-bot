"""Deterministic routing guardrails for client workspaces.

The LLM router is useful for broad intent classification, but a question about
an organization's private operational data must never be mistaken for a public
"realtime" web-search request merely because it contains words such as
"current" or "last month".
"""
from __future__ import annotations

import re


_ORGANIZATION_REFERENCE = re.compile(
    r"\b(?:our|ours|we|us|we['’]?ve|the (?:center|school|organization|company)|"
    r"this (?:center|school|organization|company)|my (?:school|organization|company)|"
    r"cfa|center for anthroposophy)\b",
    re.IGNORECASE,
)

_PRIVATE_DATA_TOPIC = re.compile(
    r"\b(?:revenue|income|profit|loss|cash|money|sales|expenses?|budget|financial|"
    r"orders?|registrations?|enrollments?|attendance|tuition|donations?|"
    r"accounts? receivable|invoices?|students?|participants?|members?|"
    r"quickbooks|thinkific|cvent|zoom)\b",
    re.IGNORECASE,
)

_INHERENTLY_PRIVATE_SOURCE = re.compile(
    r"\b(?:quickbooks|thinkific|cvent|our (?:documents?|files?|library|records?|data)|"
    r"the (?:documents?|files?|records?) (?:we|i) (?:uploaded|provided))\b",
    re.IGNORECASE,
)


def is_internal_client_data_query(message: str, *, has_client_context: bool) -> bool:
    """Return whether a query should use private client sources, not the web."""
    if not has_client_context or not isinstance(message, str):
        return False
    return bool(
        _INHERENTLY_PRIVATE_SOURCE.search(message)
        or (
            _ORGANIZATION_REFERENCE.search(message)
            and _PRIVATE_DATA_TOPIC.search(message)
        )
    )
