"""Recognize supported dashboard questions about the selected LGA."""

import re

CASE_COUNT = "What is the latest reported case count?"
REPORTING = "What is the reporting completeness and timeliness?"
MODEL_ERROR = "Which model had the lowest error for this LGA?"

MONTH = r"(?P<month>[0-9]{4}-(?:0[1-9]|1[0-2]))"
REQUEST = r"(?:(?:what (?:is|was)|show(?: me)?|give me) )?(?:the )?"
CASE_TERMS = r"(?:reported )?(?:confirmed )?(?:malaria )?case count"

PATTERNS = (
    (CASE_COUNT, rf"{REQUEST}(?:latest|most recent) {CASE_TERMS}"),
    (CASE_COUNT, rf"{REQUEST}{CASE_TERMS} (?:for|in) {MONTH}"),
    (CASE_COUNT, rf"how many (?:confirmed )?malaria cases were reported (?:for|in) {MONTH}"),
    (REPORTING, rf"{REQUEST}(?:nhmis )?reporting (?:completeness and timeliness|completeness|timeliness)"
                rf"(?: (?:for|in) {MONTH})?"),
    (MODEL_ERROR, r"which model (?:had|has) the lowest (?:backtest )?error"),
)


def match_dashboard_question(query):
    """Return a guided question and optional month, or None for other queries."""
    normalized = " ".join(query.lower().split()).rstrip("?.!")
    normalized = normalized.removesuffix(" for this lga")
    for question, pattern in PATTERNS:
        match = re.fullmatch(pattern, normalized)
        if match:
            return question, match.groupdict().get("month")
    return None
