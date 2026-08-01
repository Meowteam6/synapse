---
description: AI review of the current diff — must PASS before any PR opens
---
# /review

Run the `code-review` skill on the current diff.

```
/review              # all staged + unstaged changes
/review <path>       # specific file or directory
/review <ref>..<ref> # specific commit range
```

Invokes the `reviewer` agent (haiku).
Escalates to `architect` (sonnet) on structural issues.
Runs `iterative-refinement` (cap 3) to fix NEEDS_CHANGES issues.

A PASS result means the PR can open.
A BLOCK result must be resolved manually.

See: `plugins/core/skills/code-review/SKILL.md`
