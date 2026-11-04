"""Recognize supported dashboard questions and resolve named LGAs."""

import re

CASE_COUNT = "What is the latest reported case count?"
LGA_OVERVIEW = "Tell me about this LGA"
REPORTING = "What is the reporting completeness and timeliness?"
COMPARE_REPORTING = "Compare reporting rates"
MODEL_ERROR = "Which model had the lowest error for this LGA?"

MONTH = r"(?P<month>(?!0000)[0-9]{4}-(?:0[1-9]|1[0-2]))"
REQUEST = r"(?:(?:what (?:is|was)|show(?: me)?|give me) )?(?:the )?"
CASE_TERMS = r"(?:reported )?(?:confirmed )?(?:malaria )?case count"
REPORTING_TERMS = r"(?:nhmis )?reporting (?:completeness and timeliness|completeness|timeliness|rates?)"

PATTERNS = (
    (LGA_OVERVIEW, rf"(?:tell me about|summari[sz]e|(?:give me an )?overview of) "
                   rf"(?:this|the selected|the current) (?:lga|local government area)(?: (?:for|in) {MONTH})?"),
    (CASE_COUNT, rf"{REQUEST}(?:latest|most recent) {CASE_TERMS}"),
    (CASE_COUNT, rf"{REQUEST}{CASE_TERMS} (?:for|in) {MONTH}"),
    (CASE_COUNT, rf"how many (?:confirmed )?malaria cases were reported (?:for|in) {MONTH}"),
    (CASE_COUNT, r"how many (?:confirmed )?malaria cases were reported in the (?:latest|most recent) month"),
    (REPORTING, rf"{REQUEST}{REPORTING_TERMS}(?: (?:for|in) {MONTH})?"),
    (REPORTING, rf"(?:were (?:nhmis )?reports|how many (?:nhmis )?reports were) "
                rf"(?:submitted|completed) on time (?:for|in) {MONTH}"),
    (MODEL_ERROR, r"which model (?:had|has) the lowest (?:backtest )?(?:error|mae|mean absolute error)"),
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


def match_named_question(query):
    """Return the supported question, month, and names as written by the user."""
    query = " ".join(query.lower().split()).rstrip("?.!")
    trailing_month = re.search(rf" (?:for|in) {MONTH}$", query)
    month = trailing_month.group("month") if trailing_month else None
    if trailing_month:
        query = query[:trailing_month.start()]
    comparison = re.fullmatch(rf"compare (?:the )?{REPORTING_TERMS} between (.+?) and (.+)", query)
    if comparison:
        return COMPARE_REPORTING, month, comparison.groups()

    for separator in re.finditer(r" (?:for|in) ", query):
        subject = query[:separator.start()]
        match = match_dashboard_question(subject)
        if not match and month:
            match = match_dashboard_question(f"{subject} in {month}")
        if match and match[0] in (CASE_COUNT, REPORTING):
            if month and match[1] and month != match[1]:
                return None
            return match[0], month or match[1], (query[separator.end():],)
    return None


def resolve_lga(name, roster):
    """Find a unique LGA by name, optionally qualified by state or FCT."""
    def words(value):
        return " ".join(re.findall(r"[a-z0-9]+", value.lower()))

    def lga(value):
        return re.sub(r" (?:local government area|lga|area council)$", "", words(value))

    def state(value):
        normalized = words(value).removesuffix(" state")
        return "fct" if normalized in {"abuja", "abuja fct", "federal capital territory"} else normalized

    parts = re.split(r"\s+in\s+|,\s*", name, maxsplit=1)
    matches = [unit for unit, unit_name, state_name in roster
               if lga(unit_name) == lga(parts[0]) and (len(parts) == 1 or state(state_name) == state(parts[1]))]
    if not matches:
        raise ValueError(f'I couldn’t match "{name}" to an LGA. Try the LGA name followed by its state or FCT.')
    if len(matches) > 1:
        raise ValueError(f'More than one LGA matches "{name}". Add the state name to specify which one you mean.')
    return matches[0]
