---
name: iterative-refinement
description: Write → review → fix loop with explicit exit conditions; called by /review and /qa, rarely invoked directly
---
# iterative-refinement skill

Write → review → fix loop with explicit exit conditions.
Called by other skills (`/review`, `/qa`). Not usually invoked directly.

---

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `cap` | 3 | Maximum iterations before surfacing to user |
| `check_cmd` | (from caller) | Command to run to verify success |
| `fix_agent` | (from caller) | Which agent performs the fix |

---

## Loop

```
iteration = 0
while iteration < cap:
    run check_cmd
    if all checks pass:
        exit DONE
    read failure output
    fix_agent applies fixes
    run pre-commit run --all-files
    iteration += 1

if iteration == cap:
    exit NEEDS_HUMAN — surface failures to user
```

---

## Exit conditions

| Condition | Status | Action |
|---|---|---|
| All checks pass | DONE | Caller proceeds |
| Cap reached | NEEDS_HUMAN | Print remaining failures, stop |
| BLOCK-level issue found | ESCALATE | Surface immediately, do not iterate |
| Flaky failure (random pass/fail) | FLAG | Mark as flaky, don't count as failure |

---

## Used by

- `/review` — iterate on code issues (cap: 3)
- `/qa` — iterate on failing tests (cap: 5)
- Custom callers can override cap and commands

---

## Example invocation (from `/qa`)

```
iterative-refinement:
  cap: 5
  check_cmd: uv run pytest tests/e2e/ -v --tb=short
  fix_agent: qa-agent
```
