---
name: ticket-sync
description: Pull GitHub Issue context (acceptance criteria, labels) into the session; draft the closing comment
---
# /ticket — ticket-sync skill

Pulls GitHub Issue context into the session.
Fetches acceptance criteria, flags ambiguities, drafts a status-update comment on completion.

---

## Trigger

```
/ticket <ID>          # load GitHub Issue #ID
/ticket               # auto-detect from branch name (type/IS-NNN-description)
```

Auto-triggers at session start if the current branch matches `type/IS-NNN-*`.

---

## Steps

1. **Resolve the issue number.**
   - Explicit: use the provided ID.
   - Auto: parse `git branch --show-current` → extract `NNN` from `type/IS-NNN-*`.

2. **Fetch the issue.**
   ```sh
   gh issue view <ID> --json title,body,labels,assignees,comments
   ```

3. **Parse and display:**
   - Title
   - Acceptance criteria (look for checklist items `- [ ]`)
   - Labels (determines type: feat/fix/chore)
   - Any linked PRs

4. **Flag ambiguities.** If acceptance criteria are missing or vague:
   - List the specific questions.
   - Do not start work until ambiguities are resolved or the user decides to proceed anyway.

5. **On task completion,** draft a closing comment:
   ```
   Done in PR #<N>. Implemented: <summary of what was done>.
   ```
   Ask the user to post it or post automatically if auto mode is on.

---

## Branch → issue auto-detection

Pattern: `(feat|fix|chore|test|docs|refactor)/IS-(\d+)-.*`

Extraction: `git branch --show-current | grep -oP 'IS-\K\d+'`

---

## Output format

```
## Issue #<ID> — <title>

**Labels:** <labels>
**Assignees:** <assignees>

### Acceptance criteria
- [ ] <criterion>
- [ ] <criterion>

### Ambiguities
- <question> — clarify before starting?

### Linked PRs
- PR #<N>: <title>
```
