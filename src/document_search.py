"""Search selected project documentation and return excerpts with source locations."""

import re
from collections import Counter
from math import log1p

DOCUMENTS = {
    "README.md": {"Data plan", "Run the available data checks"},
    "APPROACH.md": {"First analytical question", "Minimum data contract", "Features and validation",
                    "Reporting confidence", "Intended product"},
    "docs/monthly_case_data.md": {"Unit of observation", "CSV fields", "Accompanying export notes",
                                  "What the checker does", "Supplied DHIS2 exports"},
}
STOP_WORDS = set("a an and are can did do does for from how i in into is it me of on or the to was were what when where which with you".split())


def terms(text):
    return set(re.findall(r"[a-z0-9]+", text.lower())) - STOP_WORDS


def search_documents(root, query, limit=4):
    query_terms = terms(query)
    if not query_terms:
        return []
    excerpts = []
    for filename, sections in DOCUMENTS.items():
        text = (root / filename).read_text(encoding="utf-8-sig")
        text = re.sub(r"(?ms)^\s*```[^\n]*\n.*?^\s*```[^\n]*$", "", text)
        parts = re.split(r"(?m)^## (.+)$", text)
        for section, body in zip(parts[1::2], parts[2::2]):
            if section.strip() not in sections:
                continue
            heading_terms = terms(section)
            for paragraph in re.split(r"\n\s*\n|\n(?=- )", body.strip()):
                if paragraph:
                    excerpt = {"file": filename, "section": section.strip(), "excerpt": paragraph}
                    excerpts.append((excerpt, terms(paragraph), heading_terms))
    frequencies = Counter(term for _, words, _ in excerpts for term in words & query_terms)
    weights = {term: log1p(len(excerpts) / frequency) for term, frequency in frequencies.items()}
    matches = []
    for excerpt, words, heading_terms in excerpts:
        hits = query_terms & words
        if hits:
            score = sum(weights[term] for term in sorted(hits)) + len(hits & heading_terms)
            matches.append((score, excerpt))
    return [result for _, result in sorted(matches, key=lambda item: item[0], reverse=True)[:limit]]
