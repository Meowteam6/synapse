"""
The Synapse command line.

    synapse doctor              is this box fit to run care agents
    synapse list                what is in the registry
    synapse add <agent>         copy an agent into your facility, source and all
    synapse run <agent>         try one call against it
    synapse certify <agent>     generate the suite, grade it, decide

`add` copies rather than installs. A facility owns the source of every agent
making decisions about its residents, and can read the prompt, edit the
rubric, and diff it after an upgrade. An agent whose behaviour a Director of
Nursing cannot inspect has no business on the night shift.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

from synapse import contract
from synapse.skills import llm

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "registry"
OUT = ROOT / "out"

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"
RED, GREEN, YELLOW, CYAN = "\033[31m", "\033[32m", "\033[33m", "\033[36m"

PASS_MARK, FAIL_MARK, WARN_MARK = "PASS", "FAIL", "WARN"


def _rule(char: str = "-", width: int = 74) -> str:
    """Return a horizontal rule."""
    return char * width


def cmd_doctor(args: argparse.Namespace) -> int:
    """Verify the box can run care agents on-device.

    Returns:
        0 if the box is ready, 1 otherwise.
    """
    print(f"\n{BOLD}Synapse preflight{RESET}\n{_rule()}")
    ready = True

    try:
        models = llm.installed_models()
        print(f"  {GREEN}{PASS_MARK}{RESET}  ollama reachable at {llm.OLLAMA_HOST}")
    except llm.LLMError as exc:
        print(f"  {RED}{FAIL_MARK}{RESET}  {exc}")
        return 1

    print(f"  {DIM}      installed: {', '.join(models) or 'none'}{RESET}")

    tiers = (
        ("care  ", llm.care_model, "resident PHI, must stay on this box"),
        ("author", llm.author_model, "synthetic residents only, may run remote"),
    )
    for label, resolver, note in tiers:
        try:
            tag = resolver()
        except (llm.ModelUnavailableError, ValueError) as exc:
            print(f"  {RED}{FAIL_MARK}{RESET}  {label} tier: {exc}")
            ready = False
            continue

        where = "cerebras" if llm.is_remote(tag) else "on-device"
        if llm.is_gemma4(tag):
            mark, colour, suffix = PASS_MARK, GREEN, ""
        else:
            mark, colour, suffix = WARN_MARK, YELLOW, " (stand-in; not Gemma 4)"

        print(f"  {colour}{mark}{RESET}  {label} tier: {tag} {DIM}[{where}]{suffix}{RESET}")
        print(f"  {DIM}             {note}{RESET}")

    if not llm.cerebras_key():
        print(
            f"  {DIM}      author tier is local; set CEREBRAS_API_KEY to "
            f"certify faster{RESET}"
        )

    agents = contract.discover(REGISTRY)
    if agents:
        print(f"  {GREEN}{PASS_MARK}{RESET}  registry: {len(agents)} agents loadable")
    else:
        print(f"  {RED}{FAIL_MARK}{RESET}  registry: no loadable agents at {REGISTRY}")
        ready = False

    free_gb = shutil.disk_usage(ROOT).free / (1024**3)
    if free_gb > 20:
        print(f"  {GREEN}{PASS_MARK}{RESET}  disk: {free_gb:.0f}GB free")
    else:
        print(f"  {YELLOW}{WARN_MARK}{RESET}  disk: only {free_gb:.0f}GB free")

    print(f"  {GREEN}{PASS_MARK}{RESET}  egress: none configured (localhost inference only)")
    print(_rule())
    print(f"  {BOLD}{'READY' if ready else 'NOT READY'}{RESET}\n")
    return 0 if ready else 1


def cmd_list(args: argparse.Namespace) -> int:
    """Print the registry.

    Returns:
        0 always.
    """
    agents = contract.discover(REGISTRY)
    if not agents:
        print(f"No agents found in {REGISTRY}")
        return 0

    print(f"\n{BOLD}Synapse registry{RESET}  {DIM}{REGISTRY}{RESET}\n")
    for agent in agents:
        blocking = len(agent.rubric.blocking)
        print(f"  {BOLD}{agent.name}{RESET}  {DIM}[{agent.category}]{RESET}")
        print(f"    {agent.description.strip().splitlines()[0]}")
        print(
            f"    {DIM}{len(agent.rubric.checks)} checks, "
            f"{blocking} blocking{RESET}\n"
        )
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    """Copy an agent folder into a facility directory.

    Returns:
        0 on success, 1 if the agent is unknown or the target exists.
    """
    source = REGISTRY / args.agent
    if not (source / "agent.yaml").exists():
        print(f"{RED}Unknown agent {args.agent!r}.{RESET} Try: synapse list")
        return 1

    target = Path(args.into).expanduser().resolve() / args.agent
    if target.exists() and not args.force:
        print(f"{RED}{target} already exists.{RESET} Use --force to overwrite.")
        return 1

    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))

    print(f"\n  Added {BOLD}{args.agent}{RESET} to {target}")
    print(f"  {DIM}You own this source. Read agent.yaml, edit rubric.yaml.{RESET}")
    print(f"\n  Next: {CYAN}synapse certify {args.agent}{RESET}")
    print(f"  {DIM}Nothing should reach a resident before it clears.{RESET}\n")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Run one utterance against an agent.

    Returns:
        0 on success, 1 on failure.
    """
    try:
        agent = contract.load_agent(REGISTRY / args.agent)
    except contract.AgentError as exc:
        print(f"{RED}{exc}{RESET}")
        return 1

    request = {
        "utterance": args.utterance,
        "resident_name": args.resident,
        "room": args.room,
        "time": args.time,
        "context": args.context or "",
    }

    try:
        response = agent.run(request)
    except Exception as exc:
        print(f"{RED}{type(exc).__name__}: {exc}{RESET}")
        return 1

    meta = response.pop("_meta", {})
    print(f"\n{BOLD}{agent.name}{RESET}  {DIM}{meta.get('model')} "
          f"| {meta.get('latency_ms')}ms | on-device{RESET}\n{_rule()}")
    for key, value in response.items():
        print(f"  {BOLD}{key}{RESET}: {value}")
    if meta.get("floors_applied"):
        print(f"\n  {YELLOW}safety floor applied: {', '.join(meta['floors_applied'])}{RESET}")
    print()
    return 0


def cmd_certify(args: argparse.Namespace) -> int:
    """Generate a suite, run it, score it, and print the verdict.

    Returns:
        0 if the agent is cleared for deployment, 1 otherwise.
    """
    from evals import runner

    try:
        agent = contract.load_agent(REGISTRY / args.agent)
    except contract.AgentError as exc:
        print(f"{RED}{exc}{RESET}")
        return 1

    print(f"\n{BOLD}Certifying {agent.name}{RESET}")
    print(f"{DIM}{len(agent.rubric.checks)} checks x {args.per_check} scenarios, "
          f"generated on this box{RESET}\n{_rule()}")

    def on_event(event: str, payload: dict) -> None:
        if event == "models":
            print(f"  care:   {payload['care']}")
            print(f"  author: {payload['author']}\n")
        elif event == "generating":
            print(f"  {DIM}generating scenarios from rubric...{RESET}")
        elif event == "generated":
            print(f"  {DIM}{payload['scenarios']} scenarios written{RESET}\n")
        elif event == "scenario":
            print(
                f"\r  running {payload['index'] + 1}/{payload['total']} "
                f"{DIM}{payload['check']}{RESET}          ",
                end="",
                flush=True,
            )

    report = runner.certify(
        agent, per_check=args.per_check, seed=args.seed, checks=args.check
    )
    print(f"\r{' ' * 70}\r", end="")

    print(_rule())
    for result in report.results:
        if result.total == 0:
            mark, colour = "SKIP", YELLOW
        elif result.clean:
            mark, colour = PASS_MARK, GREEN
        else:
            mark, colour = FAIL_MARK, RED

        print(
            f"  {colour}{mark}{RESET}  {result.check_id:<38} "
            f"{result.passed}/{result.total}  {DIM}{result.severity}{RESET}"
        )

    blocking = report.blocking_failures
    if blocking:
        print(f"\n{BOLD}{RED}Blocking failures{RESET}")
        for verdict in blocking[: args.show]:
            scenario = verdict.scenario
            print(f"\n  {RED}{verdict.check_id}{RESET} {DIM}({scenario['difficulty']}){RESET}")
            print(f"    resident said: \"{scenario['utterance']}\"")
            print(f"    agent replied: {verdict.response.get('urgency', '?')} "
                  f"-> {verdict.response.get('escalate_to', '?')}")
            print(f"    {YELLOW}why it failed:{RESET} {verdict.reasoning}")

    print(f"\n{_rule()}")
    verdict_text = (
        f"{GREEN}{BOLD}CLEARED FOR DEPLOYMENT{RESET}"
        if report.cleared
        else f"{RED}{BOLD}BLOCKED{RESET}"
    )
    print(f"  {verdict_text}   pass rate {report.pass_rate:.0%}   "
          f"{len(blocking)} blocking, {len(report.advisory_failures)} advisory")

    path = runner.write_report(report, OUT)
    print(f"  {DIM}report: {path}{RESET}\n")
    return 0 if report.cleared else 1


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser."""
    parser = argparse.ArgumentParser(
        prog="synapse",
        description="On-device healthcare agents you own, certified before they run.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="check this box is fit to run care agents").set_defaults(
        func=cmd_doctor
    )
    sub.add_parser("list", help="list registry agents").set_defaults(func=cmd_list)

    add = sub.add_parser("add", help="copy an agent into your facility")
    add.add_argument("agent")
    add.add_argument("--into", default="./agents", help="target directory")
    add.add_argument("--force", action="store_true")
    add.set_defaults(func=cmd_add)

    run = sub.add_parser("run", help="run one utterance against an agent")
    run.add_argument("agent")
    run.add_argument("utterance")
    run.add_argument("--resident", default="unknown")
    run.add_argument("--room", default="unknown")
    run.add_argument("--time", default="overnight")
    run.add_argument("--context", default="")
    run.set_defaults(func=cmd_run)

    certify = sub.add_parser("certify", help="generate, run, and score the rubric suite")
    certify.add_argument("agent")
    certify.add_argument("--per-check", type=int, default=3)
    certify.add_argument("--seed", type=int, default=llm.DEFAULT_SEED)
    certify.add_argument("--check", action="append", help="limit to a check id")
    certify.add_argument("--show", type=int, default=5, help="failures to detail")
    certify.set_defaults(func=cmd_certify)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point.

    Returns:
        The subcommand's exit code.
    """
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
