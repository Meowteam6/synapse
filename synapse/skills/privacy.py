"""
PHI handling for on-device care agents.

A note on what this module deliberately does *not* do.

The obvious implementation redacts resident names. That would be wrong
here. A shift-handoff note that says "PATIENT_REDACTED reports chest
discomfort" is clinically useless, and HIPAA never asked for it: names are
permitted, and necessary, for treatment within the facility. Over-redaction
in a care setting is itself a safety failure.

What this module targets is the subset of the 18 HIPAA identifiers that
have no business appearing in a triage note in the first place, and whose
presence usually means the model has started inventing detail: government
identifiers, contact information, record numbers, and full dates of birth.

The boundary that actually protects the resident in Nightingale is
architectural rather than textual -- inference runs against localhost and
the facility's data never leaves its hardware. This module is the second
layer, for the text that gets written down and passed between shifts.
"""

from __future__ import annotations

import re

# Ordered: more specific patterns first, so a phone number is not partially
# consumed by a looser numeric rule.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("[SSN]", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("[EMAIL]", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")),
    (
        "[PHONE]",
        re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    ),
    ("[MRN]", re.compile(r"\b(?:MRN|mrn|medical record(?: number)?)[:# ]*\s*\w+\b")),
    ("[DOB]", re.compile(r"\b(?:DOB|dob|date of birth)[:# ]*\s*[\d/.-]+\b")),
    (
        "[DOB]",
        re.compile(
            r"\b(?:born|b\.)\s+(?:on\s+)?"
            r"(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4})\b"
        ),
    ),
    (
        "[ADDRESS]",
        re.compile(
            r"\b\d{1,5}\s+[\w\s]{1,30}?\s"
            r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct)\b\.?",
            re.IGNORECASE,
        ),
    ),
)


def redact(text: str) -> str:
    """Replace out-of-scope PHI identifiers with typed placeholders.

    Resident names and room numbers are intentionally preserved -- they are
    required for treatment and handoff within the facility.

    Args:
        text: free text bound for a shift log or handoff note.

    Returns:
        The text with government identifiers, contact details, record
        numbers, dates of birth, and street addresses replaced.
    """
    if not text:
        return text

    for placeholder, pattern in _PATTERNS:
        text = pattern.sub(placeholder, text)
    return text


def findings(text: str) -> list[str]:
    """Report which identifier classes appear in a text.

    Used by the eval harness to flag agents that emit identifiers they were
    never given -- a reliable signal that the model is fabricating detail.

    Args:
        text: the text to scan.

    Returns:
        Sorted, de-duplicated placeholder labels found, e.g. ["[PHONE]"].
    """
    if not text:
        return []
    return sorted({label for label, pattern in _PATTERNS if pattern.search(text)})
