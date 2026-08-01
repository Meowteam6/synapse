"""
Gemma 4 inference for Synapse, across two tiers with different privacy rules.

Synapse runs models in two distinct roles, and conflating them is the
mistake that makes "on-prem AI" claims dishonest:

  care tier    Runs resident-facing agents. Real residents, real PHI, real
               consequences. Always local, over Ollama, on the facility's
               own hardware. There is no configuration that routes a care
               call off the box -- `care_model` will not return a remote
               provider, and that is enforced in code rather than in docs.

  author tier  Writes test scenarios and judges responses. Runs at
               certification time, before deployment, over synthetic
               residents that Synapse invented. No PHI has ever existed at
               this tier by construction.

Because the author tier holds no patient data, it may run remotely, and
there is a good reason to let it: certification is the slow part. Grading
nineteen checks against a 4B model on a Mac mini takes roughly half an hour
of wall clock; the same work against Gemma 4 on Cerebras takes seconds. A
facility can therefore certify an agent quickly, then run it slowly and
privately forever after.

The boundary is the product. Care never leaves the building. Certification
never had anything to leak.

Two guarantees this module makes, both of which the eval harness depends on:

  1. Determinism. temperature=0 and a fixed seed, so the same scenario
     scored twice produces the same verdict. A compliance report that
     cannot be reproduced is not a compliance report.
  2. Schema conformance. Structured calls use Ollama's `format` parameter
     (JSON-schema-constrained decoding) rather than tool-calling. Gemma
     builds on Ollama advertise only the "completion" capability, so
     tool-calling is not available; constrained decoding is both available
     and more reliable at 4B scale.

No silent fallbacks. A model that is missing, a daemon that is down, or a
response that does not satisfy the schema raises. An agent that fails loudly
in a care setting is safe; one that degrades quietly is not.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import requests

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Remote author-tier inference. Optional: with no key configured, Synapse
# runs entirely on localhost and certification simply takes longer.
CEREBRAS_HOST = os.getenv("CEREBRAS_HOST", "https://api.cerebras.ai/v1")
CEREBRAS_PREFIX = "cerebras:"
CEREBRAS_RATE_LIMIT_RETRIES = 4
CEREBRAS_BACKOFF_SECONDS = 12

# Candidate Gemma 4 identifiers on Cerebras, tried in order against their
# /models endpoint. Hosted model naming drifts, so the tag is discovered at
# runtime rather than hardcoded, and `CEREBRAS_MODEL` overrides outright.
CEREBRAS_MODEL_PREFERENCE = (
    "gemma4-31b",
    "gemma4-26b",
    "gemma4-12b",
    "gemma-4-31b",
    "gemma-4-12b",
)

# Preference order for the agent-facing model. Gemma 4's on-device class
# (e4b/e2b) comes first: the deployment story is a Mac mini in a facility
# closet, not a workstation. Anything gemma3 is a development stand-in and
# is reported as such by `synapse doctor`.
CARE_MODEL_PREFERENCE = (
    "gemma4:e4b",
    "gemma4:e2b",
    "gemma4:12b-it-qat",
    "gemma3:4b-it-qat",
)

# The scenario generator is not latency-bound -- it runs offline, before
# deployment -- so it gets the largest locally available model. Grading a
# small model with a bigger one that still never leaves the box is the
# whole trick.
AUTHOR_MODEL_PREFERENCE = (
    "gemma4:12b-it-qat",
    "gemma4:e4b",
    "gemma4:e2b",
    "gemma3:4b-it-qat",
)

DEFAULT_SEED = 42
DEFAULT_TIMEOUT = 180


class LLMError(RuntimeError):
    """Raised when local inference cannot produce a usable result."""


class ModelUnavailableError(LLMError):
    """Raised when no acceptable local model is installed."""


@dataclass
class Completion:
    """A single local inference result, with the provenance an audit needs."""

    text: str
    model: str
    seed: int
    latency_ms: int
    raw: dict[str, Any] = field(default_factory=dict)

    def json(self) -> Any:
        """Parse the completion as JSON.

        Raises:
            LLMError: if the text is not valid JSON.
        """
        try:
            return json.loads(self.text)
        except json.JSONDecodeError as exc:
            raise LLMError(
                f"{self.model} returned non-JSON output: {self.text[:400]}"
            ) from exc


def installed_models() -> list[str]:
    """Return the model tags currently installed in the local Ollama daemon.

    Raises:
        LLMError: if the Ollama daemon is unreachable.
    """
    try:
        resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise LLMError(
            f"Ollama is not reachable at {OLLAMA_HOST}. Start it with: ollama serve"
        ) from exc
    return [m["name"] for m in resp.json().get("models", [])]


def resolve_model(preference: tuple[str, ...], override: str | None = None) -> str:
    """Pick the best installed model from an ordered preference list.

    Lets the build proceed on whatever Gemma is on disk and pick up a
    better one the moment its download finishes, with no code change.

    Args:
        preference: model tags, best first.
        override: explicit tag that wins if installed.

    Returns:
        An installed model tag.

    Raises:
        ModelUnavailableError: if none of the candidates are installed.
    """
    available = installed_models()
    candidates = (override, *preference) if override else preference

    for tag in candidates:
        if tag and tag in available:
            return tag

    raise ModelUnavailableError(
        f"None of {list(candidates)} are installed. Have: {available or 'nothing'}. "
        f"Install one with: ollama pull {preference[0]}"
    )


def cerebras_key() -> str | None:
    """Return the configured Cerebras API key, or None."""
    return os.getenv("CEREBRAS_API_KEY") or None


def cerebras_models() -> list[str]:
    """List models available on Cerebras for the configured key.

    Never raises. An unreachable or unconfigured author tier degrades to
    local inference -- certification gets slower, not impossible.

    Returns:
        Model ids, empty when unconfigured or unreachable.
    """
    key = cerebras_key()
    if not key:
        return []
    try:
        resp = requests.get(
            f"{CEREBRAS_HOST}/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=10,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Cerebras unreachable, staying local: %s", exc)
        return []
    return [m["id"] for m in resp.json().get("data", [])]


def cerebras_model() -> str | None:
    """Resolve the best Gemma build available on Cerebras.

    Hosted model naming drifts, so the tag is discovered against the live
    /models endpoint rather than hardcoded.

    Returns:
        A prefixed tag such as `cerebras:gemma4-31b`, or None when the
        author tier is unconfigured or offers no Gemma build.
    """
    if not cerebras_key():
        return None

    override = os.getenv("CEREBRAS_MODEL")
    if override:
        return f"{CEREBRAS_PREFIX}{override}"

    available = cerebras_models()
    for candidate in CEREBRAS_MODEL_PREFERENCE:
        if candidate in available:
            return f"{CEREBRAS_PREFIX}{candidate}"

    gemma = [m for m in available if "gemma" in m.lower()]
    return f"{CEREBRAS_PREFIX}{gemma[0]}" if gemma else None


def is_remote(tag: str) -> bool:
    """Return True if the tag routes to a remote provider."""
    return tag.startswith(CEREBRAS_PREFIX)


def care_model() -> str:
    """Resolve the model that runs resident-facing agents.

    Always local. A remote override is rejected rather than honoured: the
    care tier handles resident PHI, and the guarantee that it never leaves
    the building belongs in code, not in configuration discipline.

    Raises:
        ValueError: if SYNAPSE_CARE_MODEL names a remote provider.
        ModelUnavailableError: if no local model is installed.
    """
    override = os.getenv("SYNAPSE_CARE_MODEL")
    if override and is_remote(override):
        raise ValueError(
            f"SYNAPSE_CARE_MODEL={override!r} routes off-device. The care tier "
            f"handles resident PHI and must run locally. Set a local Ollama tag."
        )
    return resolve_model(CARE_MODEL_PREFERENCE, override)


def author_model() -> str:
    """Resolve the model that authors and grades test scenarios.

    Prefers Cerebras when configured. Certification is the slow step and
    the author tier holds only synthetic residents, so remote inference
    buys a large speedup at no privacy cost. Falls back to local so
    Synapse still certifies with no network at all.

    Returns:
        A local Ollama tag or a `cerebras:`-prefixed tag.
    """
    override = os.getenv("SYNAPSE_AUTHOR_MODEL")
    if override:
        if is_remote(override):
            return override
        return resolve_model(AUTHOR_MODEL_PREFERENCE, override)

    return cerebras_model() or resolve_model(AUTHOR_MODEL_PREFERENCE)


def is_gemma4(tag: str) -> bool:
    """Return True if the tag is a Gemma 4 build, local or remote."""
    stripped = tag.removeprefix(CEREBRAS_PREFIX).lower()
    return stripped.startswith("gemma4") or stripped.startswith("gemma-4")


def _strict_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a schema satisfying Cerebras strict-mode rules.

    Strict structured output requires every object to set
    `additionalProperties: false` and to list all of its properties as
    required. Ollama imposes neither, so agent manifests are written
    without them and the constraint is applied here rather than pushed
    onto everyone authoring a rubric.

    Args:
        schema: a JSON schema as declared in an agent manifest.

    Returns:
        A deep copy with strict-mode constraints applied throughout.
    """
    if not isinstance(schema, dict):
        return schema

    out = {k: v for k, v in schema.items()}

    if out.get("type") == "object":
        properties = {
            name: _strict_schema(spec) for name, spec in out.get("properties", {}).items()
        }
        out["properties"] = properties
        out["additionalProperties"] = False
        out["required"] = list(properties)

    if out.get("type") == "array" and isinstance(out.get("items"), dict):
        out["items"] = _strict_schema(out["items"])

    return out


def _complete_cerebras(
    messages: list[dict[str, str]],
    *,
    model: str,
    schema: dict[str, Any] | None,
    seed: int,
    temperature: float,
    timeout: int,
) -> Completion:
    """Run one author-tier call against Cerebras.

    Only ever reached for the author tier -- `care_model` cannot return a
    remote tag, so no resident data can arrive here.

    Cerebras exposes an OpenAI-compatible surface, so schema enforcement
    uses `response_format: json_schema` rather than Ollama's `format`.

    Args:
        messages: chat messages, system turn first when present.
        model: a `cerebras:`-prefixed tag.
        schema: JSON schema the output must satisfy.
        seed: forwarded for reproducibility.
        temperature: defaults to 0 upstream.
        timeout: seconds before the request is abandoned.

    Returns:
        A Completion carrying the text plus provenance.

    Raises:
        LLMError: if the key is missing, transport fails, or the response
            is empty.
    """
    key = cerebras_key()
    if not key:
        raise LLMError(
            f"{model} requires CEREBRAS_API_KEY. Unset it to certify locally."
        )

    tag = model.removeprefix(CEREBRAS_PREFIX)
    payload: dict[str, Any] = {
        "model": tag,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
        "seed": seed,
    }
    if schema is not None:
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "synapse_output",
                "strict": True,
                "schema": _strict_schema(schema),
            },
        }

    started = time.perf_counter()
    resp = None

    # Cerebras meters tokens per minute, and certification is bursty by
    # nature -- a rubric fans out into many generation calls at once. A 429
    # is a pacing problem, not a failure, so back off and continue rather
    # than dropping the check and leaving a gap in the record.
    for attempt in range(CEREBRAS_RATE_LIMIT_RETRIES + 1):
        try:
            resp = requests.post(
                f"{CEREBRAS_HOST}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {key}"},
                timeout=timeout,
            )
            resp.raise_for_status()
            break
        except requests.RequestException as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status == 429 and attempt < CEREBRAS_RATE_LIMIT_RETRIES:
                wait = CEREBRAS_BACKOFF_SECONDS * (attempt + 1)
                logger.info("Cerebras rate limit, waiting %ds", wait)
                time.sleep(wait)
                continue
            detail = f" -- {exc.response.text[:300]}" if exc.response is not None else ""
            raise LLMError(f"Cerebras call failed on {tag}: {exc}{detail}") from exc

    if resp is None:
        raise LLMError(f"Cerebras call failed on {tag}: exhausted retries.")

    latency_ms = int((time.perf_counter() - started) * 1000)
    body = resp.json()
    choices = body.get("choices") or []
    text = (choices[0].get("message", {}).get("content", "") if choices else "").strip()

    if not text:
        raise LLMError(f"{model} returned an empty response.")

    return Completion(
        text=text, model=model, seed=seed, latency_ms=latency_ms, raw=body
    )


def complete(
    prompt: str,
    *,
    model: str,
    system: str | None = None,
    schema: dict[str, Any] | None = None,
    seed: int = DEFAULT_SEED,
    temperature: float = 0.0,
    timeout: int = DEFAULT_TIMEOUT,
) -> Completion:
    """Run one local inference call.

    Args:
        prompt: the user-turn content.
        model: an installed Ollama tag.
        system: optional system-turn content.
        schema: JSON schema for constrained decoding. When supplied, the
            model is forced to emit conforming JSON.
        seed: fixed for reproducibility.
        temperature: defaults to 0 for determinism.
        timeout: seconds before the request is abandoned.

    Returns:
        A Completion carrying the text plus provenance.

    Raises:
        LLMError: on transport failure or an empty response.
    """
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    if is_remote(model):
        return _complete_cerebras(
            messages,
            model=model,
            schema=schema,
            seed=seed,
            temperature=temperature,
            timeout=timeout,
        )

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "seed": seed},
    }
    if schema is not None:
        payload["format"] = schema

    started = time.perf_counter()
    try:
        resp = requests.post(
            f"{OLLAMA_HOST}/api/chat", json=payload, timeout=timeout
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise LLMError(f"Local inference failed on {model}: {exc}") from exc

    latency_ms = int((time.perf_counter() - started) * 1000)
    body = resp.json()
    text = (body.get("message") or {}).get("content", "").strip()

    if not text:
        raise LLMError(f"{model} returned an empty response.")

    logger.debug("%s completed in %dms", model, latency_ms)
    return Completion(
        text=text, model=model, seed=seed, latency_ms=latency_ms, raw=body
    )


def structured(
    prompt: str,
    *,
    schema: dict[str, Any],
    model: str,
    system: str | None = None,
    seed: int = DEFAULT_SEED,
    retries: int = 2,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[Any, Completion]:
    """Run a schema-constrained call and return the parsed object.

    Constrained decoding makes malformed output rare but not impossible at
    4B scale, so a bounded retry runs with a perturbed seed before failing.

    Args:
        prompt: the user-turn content.
        schema: JSON schema the output must satisfy.
        model: an installed Ollama tag.
        system: optional system-turn content.
        seed: base seed; perturbed on retry.
        retries: additional attempts after the first.
        timeout: seconds per attempt.

    Returns:
        A (parsed_object, completion) pair. The completion is retained so
        callers can record model, seed, and latency in the audit trail.

    Raises:
        LLMError: if every attempt fails to produce conforming JSON.
    """
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        attempt_seed = seed + attempt
        try:
            completion = complete(
                prompt,
                model=model,
                system=system,
                schema=schema,
                seed=attempt_seed,
                timeout=timeout,
            )
            return completion.json(), completion
        except LLMError as exc:
            last_error = exc
            logger.warning(
                "structured call attempt %d/%d failed on %s: %s",
                attempt + 1,
                retries + 1,
                model,
                exc,
            )

    raise LLMError(
        f"{model} failed to produce schema-conforming output after "
        f"{retries + 1} attempts."
    ) from last_error
