---
name: code-review
description: AI-as-judge review of a diff before merge — PASS / NEEDS_CHANGES / BLOCK with line-level comments; escalates reviewer to architect on structural issues
---
# /review — code-review skill

AI-as-judge before merging. Reads the diff, checks conventions, flags issues.
Returns PASS / NEEDS_CHANGES / BLOCK with line-level comments.
Escalates from haiku (`reviewer`) to sonnet (`architect`) if structural issues found.

---

## Trigger

```
/review              # review all staged + unstaged changes
/review <path>       # review specific file or directory
/review HEAD~3..HEAD # review specific commit range
```

Auto-triggered on PR open if the `on-pr-open` routine is configured.

---

## Steps

1. **Gather the diff.**
   ```sh
   git diff HEAD          # unstaged
   git diff --cached      # staged
   # or for a specific path:
   git diff HEAD -- <path>
   ```

2. **Load context.** Read the project's `CLAUDE.md` and any referenced ticket via `/ticket <ID>`.

3. **Run `reviewer` agent** over the full diff.
   - Checker list: commits, branch, tests, imports, docstrings, dead code, security, errors, types.

4. **If reviewer returns ESCALATE** → run `architect` agent on the flagged section.

5. **If reviewer returns NEEDS_CHANGES or BLOCK:**
   - List all issues with file:line references.
   - Do not open a PR.
   - Run `iterative-refinement` to fix (cap: 3 rounds).

6. **If reviewer returns PASS:**
   - Summarise what was checked.
   - Proceed to `git push` + PR open.

---

## Exit conditions

- PASS → PR can open.
- NEEDS_CHANGES after 3 refinement rounds → surface to user for manual decision.
- BLOCK → always surface to user, never auto-proceed.

---

## Output

Post review result as a PR comment if the PR already exists, or print to terminal.
