"""Credentials that must never land in a note: find them, or blank them out of text synapsidian prints.

Unattended runs write from session transcripts, so every script that writes text into the vault
refuses a hit (`secret_problems`), and the session digest blanks one before a skill reads it
(`redact`). No dependencies: scripts that run without PyYAML import this too.
"""

from __future__ import annotations

import re

SECRETS = {
    # To the END line when there is one, so `redact` takes the key's body along with its header.
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----(?:.*?-----END [A-Z ]*PRIVATE KEY-----)?", re.DOTALL),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\b(?:ghp|gho|ghs|ghu|github_pat)_[A-Za-z0-9_]{20,}"),
    "API key (sk-)": re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}"),
    "Slack token": re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    "Slack webhook": re.compile(r"hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]{20,}"),
    "Google API key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "Stripe live key": re.compile(r"\b[rs]k_live_[0-9A-Za-z]{20,}"),
    "npm token": re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"),
    "JSON web token": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
}


def secret_problems(text: str) -> list[str]:
    return [
        f"looks like a {label}; remove it, credentials never go in the vault"
        for label, pattern in SECRETS.items()
        if pattern.search(text)
    ]


def redact(text: str) -> str:
    """`text` with every credential replaced by `[redacted: <what it was>]`. Call it before
    cutting text to a length: a token cut short no longer matches and would stay in."""
    for label, pattern in SECRETS.items():
        text = pattern.sub(f"[redacted: {label}]", text)
    return text
