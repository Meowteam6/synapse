---
description: Structured debugging loop — reproduce, isolate, fix, verify
---
# /debug

Structured debugging loop for a failing test, error, or unexpected behaviour.

```
/debug               # start debug session for current error in context
/debug "<error>"     # pass specific error message or stack trace
/debug <IS-NNN>      # debug a bug reported in a GitHub Issue
```

---

## Process

1. **Understand the symptom.** Read the error, stack trace, or issue description.
2. **Form a hypothesis.** State the most likely root cause (one sentence).
3. **Verify the hypothesis.** Add a targeted test or log, run it, read the output.
4. **If hypothesis confirmed:** fix the root cause (not just the symptom).
5. **If hypothesis wrong:** form the next hypothesis. Cap: 5 attempts.
6. **Run pre-commit** after fix: `pre-commit run --all-files`.
7. **Report** what the root cause was and what was fixed.

---

## Rules

- Fix the root cause, not the symptom.
- Do not catch exceptions to hide errors — fix the underlying problem.
- Do not increase timeouts to fix flakiness — find why it's flaky.
- If 5 hypotheses fail, stop and describe what you know. Ask for help.
