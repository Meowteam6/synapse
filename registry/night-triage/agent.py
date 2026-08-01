"""
night-triage: overnight call-button triage for a skilled nursing facility.

Runs entirely on the facility's own hardware. Nothing a resident says at
3am leaves the building.

The agent is deliberately thin. Its system prompt and output schema live in
agent.yaml so a facility can read and amend them without touching Python,
and the schema is enforced by constrained decoding rather than by parsing --
the model cannot emit a field it did not declare.

Two things happen in code rather than in the prompt, because a prompt is a
request and a care setting needs a guarantee:

  1. Fall escalation is floored. If the request mentions a fall, urgency is
     raised to at least `urgent` no matter what the model returned. Delayed
     intracranial bleeding after an unwitnessed fall is the failure mode
     that kills residents on anticoagulants, and it is not worth leaving to
     a 4B model's judgment.
  2. Every response is PHI-redacted before it is written to the shift log.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from synapse.skills import llm, privacy  # noqa: E402

# Ordered least to most urgent, so a floor can be applied by index.
URGENCY_LADDER = ("comfort", "routine", "urgent", "emergency")

# Substrings that force the fall floor. Deliberately broad: a false positive
# costs one nurse walk, a false negative costs a resident.
FALL_MARKERS = (
    "fell", "fall", "fallen", "slipped", "tripped", "on the floor",
    "got down", "ended up on", "helped me up", "couldn't get up",
    "can't get up", "went down",
)


def _at_least(urgency: str, floor: str) -> str:
    """Raise an urgency to a floor, leaving it alone if already higher.

    Args:
        urgency: the model's classification.
        floor: the minimum acceptable classification.

    Returns:
        Whichever of the two is more urgent.
    """
    try:
        current = URGENCY_LADDER.index(urgency)
    except ValueError:
        # An unrecognised label is treated as the floor rather than trusted.
        return floor
    return URGENCY_LADDER[max(current, URGENCY_LADDER.index(floor))]


def _mentions_fall(text: str) -> bool:
    """Return True if the text suggests the resident may have fallen."""
    lowered = text.lower()
    return any(marker in lowered for marker in FALL_MARKERS)


def _format_request(request: dict[str, Any]) -> str:
    """Render a triage request into the prompt body.

    Args:
        request: keys `utterance` (required), `resident_name`, `room`,
            `time`, and `context` (standing notes, e.g. anticoagulant use).

    Returns:
        The formatted prompt.

    Raises:
        ValueError: if `utterance` is missing or empty.
    """
    utterance = (request.get("utterance") or "").strip()
    if not utterance:
        raise ValueError("night-triage requires a non-empty `utterance`.")

    lines = [
        f"Resident: {request.get('resident_name', 'unknown')}",
        f"Room: {request.get('room', 'unknown')}",
        f"Time: {request.get('time', 'overnight')}",
    ]
    if request.get("context"):
        lines.append(f"Standing notes: {request['context']}")
    lines.append("")
    lines.append(f'The resident said: "{utterance}"')
    lines.append("")
    lines.append("Triage this call.")
    return "\n".join(lines)


def run(request: dict[str, Any]) -> dict[str, Any]:
    """Triage one overnight call-button press.

    Args:
        request: see `_format_request` for accepted keys.

    Returns:
        The agent's response conforming to agent.yaml's output_schema, plus
        `_meta` carrying model, seed, latency, and any safety floor applied.

    Raises:
        ValueError: if the request is malformed.
        llm.LLMError: if local inference fails. Failing loudly is correct
            here; a triage agent that degrades quietly is worse than one
            that is visibly down.
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

    floors_applied = []

    # Deterministic fall floor -- see module docstring.
    haystack = f"{request.get('utterance', '')} {request.get('context', '')}"
    if _mentions_fall(haystack):
        # Urgency and routing are floored independently. Nesting the routing
        # fix inside the urgency fix was a real defect: when the model
        # already returned `urgent` there was nothing to raise, the branch
        # was skipped, and `escalate_to: none` survived untouched. The
        # resident was correctly triaged and then routed to nobody, which is
        # the same outcome as not triaging at all. Certification caught it;
        # two rounds of review had not.
        raised = _at_least(response.get("urgency", "routine"), "urgent")
        if raised != response.get("urgency"):
            floors_applied.append("fall_floors_urgency")
            response["urgency"] = raised

        if response.get("escalate_to") in (None, "none", "aide"):
            floors_applied.append("fall_requires_nurse_assessment")
            response["escalate_to"] = "charge_nurse"

        flags = response.setdefault("red_flags", [])
        if not any("fall" in str(f).lower() for f in flags):
            flags.append("possible fall -- in-person nurse assessment required")

    response["handoff_note"] = privacy.redact(response.get("handoff_note", ""))

    response["_meta"] = {
        "agent": "night-triage",
        "model": completion.model,
        "seed": completion.seed,
        "latency_ms": completion.latency_ms,
        "floors_applied": floors_applied,
        "on_device": True,
    }
    return response
