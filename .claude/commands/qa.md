---
description: Generate Playwright e2e tests for current changes or a named feature
---
# /qa

Run the `qa-playwright` skill to generate and verify e2e tests.

```
/qa                  # tests for current staged changes
/qa <feature>        # target a specific feature description
/qa <IS-NNN>         # pull acceptance criteria from GitHub Issue
```

Invokes the `qa-agent` (haiku) to generate test files.
Runs tests and iterates via `iterative-refinement` (cap 5) until green.

See: `plugins/core/skills/qa-playwright/SKILL.md`
