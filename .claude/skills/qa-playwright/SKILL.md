---
name: qa-playwright
description: Generate and iterate Playwright e2e tests from a ticket or feature description
---
# /qa — qa-playwright skill

Generates and iterates Playwright e2e tests from a ticket or feature description.
Identifies user flows, generates test files, proposes edge cases, runs them.

---

## Trigger

```
/qa                   # generate tests for current staged changes
/qa <feature>         # target a specific feature description
/qa <IS-NNN>          # pull acceptance criteria from GitHub Issue
```

---

## Steps

1. **Load context.**
   - If a ticket ID is provided: run `/ticket <ID>` to load acceptance criteria.
   - If no ticket: read `git diff HEAD` to understand what changed.
   - Read the project's test conventions from `CLAUDE.md`.

2. **Run `qa-agent`** to generate the test plan and test files.
   - Identify happy path + failure paths.
   - Generate one file per flow.
   - Propose edge cases beyond the acceptance criteria.

3. **Run the tests.**
   ```sh
   # Python / pytest
   uv run pytest tests/e2e/ -v --tb=short

   # JS/TS
   npx playwright test
   ```

4. **Iterate** using `iterative-refinement` until all tests pass (cap: 5 rounds).
   - Each round: read failure output → fix test or implementation → re-run.
   - Never modify the acceptance criteria to make tests pass.

5. **Report** the final result.

---

## Exit conditions

- All tests green → done.
- Tests still failing after 5 rounds → surface to user with a summary of what's stuck.
- Flaky test detected (intermittent pass/fail) → flag as flaky, do not count as passing.

---

## File conventions

Follow the project's `CLAUDE.md`. Defaults if not specified:
- Python: `tests/e2e/test_<feature>.py` with `@pytest.mark.e2e`
- JS/TS: `e2e/<feature>.spec.ts`
- One describe block per flow, one test per assertion.
- Descriptive names: `test_user_can_do_X_and_see_Y`.
