# Synapse — Claude conventions

Copy this file into the `synapse` repo root. Also copy claudeMeow's
`plugins/project-template/.claude/` directory into the repo root so cloud/phone
sessions get the shared guards, skills, agents, and commands — see
`Meowteam6/claudemeow` README, section "New product repo?".

## Core conventions (fallback summary — full version ships with the plugin)

Conventional Commits (`type(scope): description`); branch
`type/IS-NNN-description`; TDD — failing test before implementation; run
`/review` before any PR; pre-commit must pass; never `--no-verify`; no
secrets in code (1Password + direnv `op://` references); no ticket refs in
code or comments (CHANGELOG only).

## What is this project

Synapse is an open-source toolkit for on-device healthcare agents: agents are
folders you own (not dependencies you import), and each one is certified
against its own declared safety rubric before it can be deployed — zero data
egress, on-prem by design.

## Key entities

- **Agent** (`registry/<name>/`) — `agent.yaml` (identity, output schema,
  model class), `agent.py` (implementation, one `run(request) -> dict`),
  `rubric.yaml` (the safety checks it must survive), `README.md`, `SETUP.md`.
  Loaded via `synapse/contract.py::load_agent` / `discover`.
- **Rubric / Check** (`synapse/contract.py`) — a rubric is a list of `Check`s
  (`id`, `description`, `severity: low|med|high`, `probe`); `high` severity
  checks are blocking. The scenario generator writes adversarial cases from
  the probe, the scorer grades responses against the same check.
- **Two model tiers** — `care_model()` (on-device only, runs resident-facing
  agents, sees real PHI, never accepts a remote override) vs. `author_model()`
  (writes/grades synthetic test scenarios only, may run remotely e.g.
  Cerebras, for speed).
- **Registry agents today**: `night-triage` (overnight call-button triage)
  and `med-checkin` (medication pass check-in).
- **Certification pipeline** (`evals/generator.py` → `evals/runner.py` →
  `evals/scorer.py`) — Dataset → Solver → Scorer, in the spirit of Hamel
  Husain's evals discipline: deterministic (temperature 0, fixed seed),
  reproducible, produces `out/<agent>-certification.json`.
- **`synapse/adopt.py`** — points at an *existing* agent repo the team didn't
  write, scans its prompts, infers the agent's domain, drafts a rubric, and
  reports which declared checks the existing prompt already covers vs. gaps
  — no execution, no adapter required unless `--write` is passed.
  `synapse/console.py` renders/publishes certification records; `web/` is the
  static Next.js viewer (`synapse publish` is an explicit, one-way copy out).

## Conventions

- Python (see `requirements.txt`: `requests`, `pyyaml`); entry point is
  `synapse-cli` → `synapse.cli:main`. Deps are currently light — the broader
  toolkit vision (below) plans `ollama`, `torch`, `opencv-python`,
  `pydantic`, `instructor`, `fastapi`, `sqlalchemy`; pin new deps in a
  `pyproject.toml` as they're actually adopted, not speculatively.
- Agents are single-purpose folders under `registry/`; nothing reaches into
  another agent's internals — compose through `contract.py`, not
  agent-to-agent imports.
- `rubric.yaml` and `agent.yaml` are the contract, not documentation:
  `output_schema` is fed to Ollama as a constrained-decoding grammar, and an
  agent with an empty rubric is treated as a load error (`AgentError`), not a
  warning.
- CLI subcommands live in `synapse/cli.py` as `cmd_<name>` functions wired
  through `build_parser()`: `doctor`, `list`, `add`, `run`, `certify`,
  `publish`, `adopt`.

## How to run tests

<!-- No test runner is configured in this repo yet (no pytest.ini / tests/
     directory as of this writing). Add one (`uv run pytest` per claudeMeow
     convention) alongside the first ticket that adds test coverage. -->

## Forbidden patterns

- **No data egress.** No agent, skill, or dependency may phone home with
  resident data, PHI, or clinical inputs. `care_model()` must reject a
  remote override rather than honouring it — the guarantee lives in code,
  not configuration discipline.
- No cloud-only dependency as a hard requirement for any care-tier path —
  every core skill needs a fully local/on-prem route.
- No skill reaching directly into another skill's or agent's internals —
  compose through `synapse/contract.py`, not skill-to-skill or
  agent-to-agent imports.
- Don't grade an agent against a check its own `rubric.yaml` didn't declare,
  and don't let an agent ship with an empty rubric.

## Ticket prefix

IS- (GitHub Issues)

---

## Where this is headed (context, not yet built)

The current registry + certification CLI is Phase 1 of a larger "Synapse
Toolkit" vision (see the Google Drive doc
`Synapse-Toolkit-Research-and-Implementation.md` and
`Claude Output/Synapse Project Setup/Synapse - Initial Tickets` for the full
backlog): a modular FDE (Full Development Environment) with 7 pluggable
agents (DevKit, Test Generation, Test Executor, LLM Evaluation, CV RL,
DevKit Integration, Report) and a shared skills library
(`privacy_skill.py`, `llm_skill.py`, `evaluation_skill.py`, `alert_skill.py`,
`vision_skill.py`, `persistence_skill.py`, `data_loading_skill.py`) that
teams pick and choose from rather than adopting a monolithic platform. Two
framework decisions are still open and should be recorded when made:
`inspect-ai` vs. a custom Dataset → Solver → Scorer implementation, and
`openmed` vs. a lighter regex+custom PII layer for `privacy_skill.py`.
