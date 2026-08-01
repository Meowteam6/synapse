"""
The Synapse agent contract.

An agent is a folder you own, not a dependency you import:

    registry/night-triage/
      agent.yaml    manifest: identity, schema, model class
      agent.py      the implementation: one `run(request) -> dict`
      rubric.yaml   what "safe" means for this agent
      README.md     what it does
      SETUP.md      how to wire it into a facility

Two of those files carry weight beyond documentation.

`agent.yaml` declares the agent's output schema, which is fed straight to
Ollama as a constrained-decoding grammar. The schema is therefore not a
suggestion -- an agent structurally cannot emit a field it did not declare.

`rubric.yaml` is the part a general-purpose agent registry does not need.
In healthcare you cannot install an agent and trust it, so every agent
declares the checks it must survive. The scenario generator reads the
rubric to author adversarial cases aimed at each check, and the scorer
reads the same rubric to grade the responses. One file defines both sides,
so an agent cannot be graded against a standard it never claimed.
"""

from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import yaml

logger = logging.getLogger(__name__)

REQUIRED_MANIFEST_KEYS = ("name", "description", "category", "output_schema")


class AgentError(RuntimeError):
    """Raised when an agent folder is malformed or fails to load."""


@dataclass
class Check:
    """One safety property an agent must satisfy.

    Attributes:
        id: stable identifier, e.g. "escalates_cardiac_symptoms".
        description: what the check asserts, in clinical terms.
        severity: consequence of failing -- low, med, or high.
        probe: guidance the scenario generator uses to attack this check.
    """

    id: str
    description: str
    severity: str
    probe: str

    @property
    def is_blocking(self) -> bool:
        """Return True if failing this check should block deployment."""
        return self.severity == "high"


@dataclass
class Rubric:
    """The full set of checks an agent declares it will survive."""

    checks: list[Check]
    scope_note: str = ""

    @property
    def blocking(self) -> list[Check]:
        """Return only the checks that block deployment when failed."""
        return [c for c in self.checks if c.is_blocking]

    def get(self, check_id: str) -> Check | None:
        """Return a check by id, or None."""
        return next((c for c in self.checks if c.id == check_id), None)


@dataclass
class Agent:
    """A loaded agent: manifest, rubric, and its callable implementation."""

    name: str
    description: str
    category: str
    output_schema: dict[str, Any]
    system_prompt: str
    rubric: Rubric
    run: Callable[[dict[str, Any]], dict[str, Any]]
    path: Path
    manifest: dict[str, Any] = field(default_factory=dict)

    @property
    def blocking_check_ids(self) -> list[str]:
        """Return the ids of checks that block deployment."""
        return [c.id for c in self.rubric.blocking]


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML file into a dict.

    Raises:
        AgentError: if the file is missing or does not parse to a mapping.
    """
    if not path.exists():
        raise AgentError(f"Missing required file: {path}")
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise AgentError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise AgentError(f"{path} must contain a YAML mapping.")
    return data


def load_rubric(path: Path) -> Rubric:
    """Load and validate a rubric.yaml.

    Args:
        path: path to the rubric file.

    Returns:
        The parsed Rubric.

    Raises:
        AgentError: if the rubric is empty or a check is malformed.
    """
    data = _read_yaml(path)
    raw_checks = data.get("checks") or []

    if not raw_checks:
        raise AgentError(
            f"{path} declares no checks. An agent with no rubric cannot be "
            f"deployed -- there would be nothing to hold it to."
        )

    checks = []
    for raw in raw_checks:
        missing = {"id", "description", "severity", "probe"} - set(raw)
        if missing:
            raise AgentError(f"{path}: check {raw.get('id', '?')} missing {missing}")
        if raw["severity"] not in {"low", "med", "high"}:
            raise AgentError(
                f"{path}: check {raw['id']} has severity {raw['severity']!r}; "
                f"expected low, med, or high."
            )
        checks.append(Check(**{k: raw[k] for k in ("id", "description", "severity", "probe")}))

    return Rubric(checks=checks, scope_note=data.get("scope_note", ""))


def load_agent(folder: Path) -> Agent:
    """Load an agent from its folder.

    Args:
        folder: directory containing agent.yaml, agent.py, and rubric.yaml.

    Returns:
        The loaded Agent.

    Raises:
        AgentError: if the folder is malformed or agent.py exposes no run().
    """
    manifest = _read_yaml(folder / "agent.yaml")

    missing = set(REQUIRED_MANIFEST_KEYS) - set(manifest)
    if missing:
        raise AgentError(f"{folder / 'agent.yaml'} is missing keys: {sorted(missing)}")

    rubric = load_rubric(folder / "rubric.yaml")

    module_path = folder / "agent.py"
    if not module_path.exists():
        raise AgentError(f"Missing required file: {module_path}")

    spec = importlib.util.spec_from_file_location(
        f"synapse_agent_{folder.name.replace('-', '_')}", module_path
    )
    if spec is None or spec.loader is None:
        raise AgentError(f"Could not load {module_path}")

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise AgentError(f"{module_path} raised on import: {exc}") from exc

    run = getattr(module, "run", None)
    if not callable(run):
        raise AgentError(f"{module_path} must define a callable `run(request)`.")

    return Agent(
        name=manifest["name"],
        description=manifest["description"],
        category=manifest["category"],
        output_schema=manifest["output_schema"],
        system_prompt=manifest.get("system_prompt", ""),
        rubric=rubric,
        run=run,
        path=folder,
        manifest=manifest,
    )


def discover(registry_root: Path) -> list[Agent]:
    """Load every agent in a registry directory.

    A malformed agent is logged and skipped rather than aborting discovery,
    so one bad folder cannot take the whole facility's registry offline.

    Args:
        registry_root: directory holding one folder per agent.

    Returns:
        Successfully loaded agents, sorted by name.
    """
    if not registry_root.exists():
        return []

    agents = []
    for folder in sorted(p for p in registry_root.iterdir() if p.is_dir()):
        if not (folder / "agent.yaml").exists():
            continue
        try:
            agents.append(load_agent(folder))
        except AgentError as exc:
            logger.error("Skipping agent %s: %s", folder.name, exc)

    return sorted(agents, key=lambda a: a.name)
