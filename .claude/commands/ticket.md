---
description: Load a GitHub Issue's context (title, acceptance criteria, labels) into the session
---
# /ticket

Load a GitHub Issue into the current session.

```
/ticket <ID>         # load Issue #ID
/ticket              # auto-detect from branch name (IS-NNN)
```

Fetches: title, acceptance criteria, labels, assignees, linked PRs.
Flags ambiguities before work starts.
Drafts a closing comment when the task is done.

Auto-triggers at session start if the current branch matches `type/IS-NNN-*`.

See: `plugins/core/skills/ticket-sync/SKILL.md`
