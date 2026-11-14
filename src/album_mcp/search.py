"""Keyword-over-meaning search.

Meaning comes from the assistant: when it files a capture it writes a summary
and tags in Korean and English, and when it searches it expands the user's
question into several terms (synonyms, both languages). This module ranks
captures by weighted term hits across summary, tags, Apple labels and OCR.

Korean OCR often splits syllables with spaces ("이 런 것"), so matching is
done on whitespace-stripped, lower-cased text.
"""

from __future__ import annotations

import re

from .db import Capture

WEIGHTS = {"tags": 4.0, "summary": 3.0, "labels": 2.0, "ocr": 1.0, "filename": 0.5}
_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub("", s.lower())


def terms_of(query: str) -> list[str]:
    parts = re.split(r"[\s,|/]+", query.strip())
    seen, out = set(), []
    for p in parts:
        n = _norm(p)
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def score(c: Capture, terms: list[str]) -> tuple[float, list[str]]:
    fields = {
        "tags": _norm(" ".join(c.tags)),
        "summary": _norm(c.summary or ""),
        "labels": _norm(" ".join(c.labels)),
        "ocr": _norm(c.ocr_text),
        "filename": _norm(c.filename),
    }
    tagset = {_norm(t) for t in c.tags}
    total, hit_terms = 0.0, []
    for t in terms:
        s = 0.0
        for f, text in fields.items():
            n = text.count(t)
            if n:
                s += WEIGHTS[f] * min(n, 3)
        if t in tagset:
            s += 4.0  # exact tag
        if s:
            hit_terms.append(t)
            total += s
    # captures matching more distinct terms rank higher
    total *= 1 + 0.5 * (len(hit_terms) - 1) if hit_terms else 0
    return total, hit_terms


def rank(captures: list[Capture], query: str, limit: int = 50) -> list[tuple[Capture, float, list[str]]]:
    terms = terms_of(query)
    if not terms:
        res = [(c, 0.0, []) for c in sorted(captures, key=lambda c: c.created_at, reverse=True)]
        return res[:limit]
    scored = []
    for c in captures:
        s, hits = score(c, terms)
        if s > 0:
            scored.append((c, s, hits))
    scored.sort(key=lambda x: (x[1], x[0].created_at), reverse=True)
    return scored[:limit]
