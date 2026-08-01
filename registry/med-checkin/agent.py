"""
med-checkin: medication pass check-in for a skilled nursing facility.

Runs entirely on the facility's own hardware.

As with every Synapse agent, the prompt and output schema live in agent.yaml
so a facility can read and amend them without touching Python. What lives
here in code is the small set of rules that must hold even when the model
gets it wrong.

Medication is where "helpful" becomes dangerous. The failure mode is not an
agent that says something alarming -- it is an agent that quietly answers
"what's this one for?", or writes `taken` into the MAR because the resident
usually takes it. Both are plausible, fluent, and wrong, and neither is
reliably prevented by asking a 4B model nicely.

So three rules are enforced deterministically:

  1. A refusal always escalates. A resident declining medication is their
     right and a clinical event; whether the model classified it as
     interesting is not relevant.
  2. Any hint of a double dose, wrong pill, or borrowed medication escalates.
  3. An ambiguous answer is recorded as `unclear`, never as `taken`. The MAR
     is a legal record. Inferring administration into it is falsification,
     and the resident is the one who pays for it.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from synapse.skills import llm, privacy  # noqa: E402

REFUSAL_MARKERS = (
    "not taking", "won't take", "wont take", "don't want", "dont want",
    "refuse", "no thank", "no thanks", "not today", "skip it", "leave it",
    "i'm not", "im not", "rather not", "no pills", "not gonna",
)

DOSING_ERROR_MARKERS = (
    "already took", "took it twice", "two of them", "double", "extra one",
    "wrong pill", "wrong one", "not my usual", "different colour",
    "different color", "found a pill", "her pill", "his pill", "off the floor",
    "someone else", "twice today", "again",
)

AMBIGUITY_MARKERS = (
    "i think", "probably", "maybe", "i guess", "might have", "can't remember",
    "cant remember", "don't remember", "dont remember", "not sure", "i suppose",
    "someone came", "the girl came", "somebody came",
)


def _contains(text: str, markers: tuple[str, ...]) -> bool:
    """Return True if any marker appears in the text, case-insensitively."""
    lowered = text.lower()
    return any(marker in lowered for marker in markers)


def _format_request(request: dict[str, Any]) -> str:
    """Render a check-in request into the prompt body.

    Args:
        request: keys `utterance` (required), `resident_name`, `room`,
            `time`, and `context` (the scheduled pass, standing notes).

    Returns:
        The formatted prompt.

    Raises:
        ValueError: if `utterance` is missing or empty.
    """
    utterance = (request.get("utterance") or "").strip()
    if not utterance:
        raise ValueError("med-checkin requires a non-empty `utterance`.")

    lines = [
        f"Resident: {request.get('resident_name', 'unknown')}",
        f"Room: {request.get('room', 'unknown')}",
        f"Time: {request.get('time', 'scheduled pass')}",
    ]
    if request.get("context"):
        lines.append(f"Standing notes: {request['context']}")
    lines.append("")
    lines.append(f'The resident said: "{utterance}"')
    lines.append("")
    lines.append("Record this medication pass.")
    return "\n".join(lines)


def run(request: dict[str, Any]) -> dict[str, Any]:
    """Record one medication pass check-in.

    Args:
        request: see `_format_request` for accepted keys.

    Returns:
        The agent's response conforming to agent.yaml's output_schema, plus
        `_meta` carrying model, seed, latency, and any floor applied.

    Raises:
        ValueError: if the request is malformed.
        llm.LLMError: if local inference fails.
    """
    import yaml

    manifest = yaml.safe_load((Path(__file__).parent / "agent.yaml").read_text())

    model = llm.care_model()
    response, completion = llm.structured(
        _format_request(request),
        schema=manifest["output_schema"],
        model=model,
        system=manifest["system_prompt"],
    )

    floors_applied: list[str] = []
    utterance = request.get("utterance", "")
    concerns = response.setdefault("concerns", [])

    def escalate(reason: str, floor: str) -> None:
        """Force escalation to the charge nurse and record why."""
        floors_applied.append(floor)
        response["escalate_to"] = "charge_nurse"
        if not any(reason.lower() in str(c).lower() for c in concerns):
            concerns.append(reason)

    if _contains(utterance, DOSING_ERROR_MARKERS):
        escalate(
            "possible dosing error reported -- nurse must verify before next pass",
            "dosing_error_requires_nurse",
        )

    if _contains(utterance, REFUSAL_MARKERS) and response.get("outcome") not in (
        "refused",
        "partial",
    ):
        response["outcome"] = "refused"

    # An ambiguous answer must never be recorded as administered.
    if _contains(utterance, AMBIGUITY_MARKERS) and response.get("outcome") == "taken":
        floors_applied.append("ambiguity_blocks_taken")
        response["outcome"] = "unclear"

    # The escalation invariant, keyed on the outcome rather than on the
    # wording that produced it. Anything other than a clean, confirmed
    # `taken` needs a nurse. Deriving this from markers alone was a real
    # defect: the model could return `refused` with escalate_to `none`
    # whenever the resident declined in words no marker list anticipated,
    # and a silent refusal is exactly the event this agent exists to catch.
    OUTCOME_REASONS = {
        "refused": "resident declined medication -- refusal is a clinical event",
        "partial": "only part of the pass was taken -- nurse must reconcile",
        "unclear": "administration not confirmed -- MAR cannot record `taken`",
        "not_offered": "scheduled pass was not offered -- nurse must reconcile",
    }
    outcome = response.get("outcome")
    if outcome in OUTCOME_REASONS:
        escalate(OUTCOME_REASONS[outcome], f"{outcome}_requires_nurse")

    response["mar_note"] = privacy.redact(response.get("mar_note", ""))

    response["_meta"] = {
        "agent": "med-checkin",
        "model": completion.model,
        "seed": completion.seed,
        "latency_ms": completion.latency_ms,
        "floors_applied": floors_applied,
        "on_device": True,
    }
    return response
