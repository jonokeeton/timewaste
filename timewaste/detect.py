"""Cheap keyword heuristic for spotting likely scam openers.

Used only to decide whether to auto-engage with a stranger. It's deliberately
simple: a handful of weighted patterns, summed into a score.
"""

import re

_PATTERNS: list[tuple[int, re.Pattern[str]]] = [
    (3, re.compile(r"\b(crypto|bitcoin|btc|usdt|eth|forex|binary option)s?\b", re.I)),
    (3, re.compile(r"\b(invest(ment)?|trading) (opportunit|platform|plan|mentor)", re.I)),
    (3, re.compile(r"\b(guaranteed|daily|weekly) (profit|return|income)s?\b", re.I)),
    (3, re.compile(r"\bgift ?cards?\b", re.I)),
    (3, re.compile(r"\b(verification|security|login) code\b", re.I)),
    (3, re.compile(r"\byou (have )?won\b|\bwinner\b|\bprize\b|\blottery\b", re.I)),
    (2, re.compile(r"\b(earn|make) \$?\d[\d,]*(k)?\b", re.I)),
    (2, re.compile(r"\b(part[- ]time|remote) (job|work|position)\b", re.I)),
    (2, re.compile(r"\b(recruiter|hr manager|hiring)\b", re.I)),
    (2, re.compile(r"\b(account|wallet) (has been )?(suspended|locked|compromised)\b", re.I)),
    (2, re.compile(r"\b(whatsapp|wa\.me|t\.me/)", re.I)),
    (2, re.compile(r"\b(wire|transfer|deposit|send) (the )?(money|funds|fee|payment)\b", re.I)),
    (2, re.compile(r"\b(inheritance|beneficiary|next of kin)\b", re.I)),
    (1, re.compile(r"\bhello dear\b|\bdear (friend|sir|madam)\b", re.I)),
    (1, re.compile(r"\b(urgent(ly)?|act now|limited time)\b", re.I)),
    (1, re.compile(r"https?://", re.I)),
    (1, re.compile(r"\b(wrong number|sorry,? (is this|who is))\b", re.I)),
]


def scam_score(text: str) -> int:
    return sum(weight for weight, pattern in _PATTERNS if pattern.search(text))


def looks_like_scam(text: str, threshold: int = 3) -> bool:
    return scam_score(text) >= threshold
