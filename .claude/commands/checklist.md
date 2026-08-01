---
description: Command center — per-repo checklist status table, or --all for the cross-project roll-up
---
# /checklist  (alias /cc)

Render the claudeMeow command center: run every check in
`plugins/core/checklist.yaml` against the current repo and print a
green/red table. `--all` rolls the same checks up across all configured
repos and surfaces open work from GitHub.

`plugins/core/checklist.yaml` is the SINGLE source of truth. This command
does not hardcode any check — add or edit checks there, not here.

```
/checklist           # this repo: render checklist.yaml as a ✅/❌ table
/cc                  # alias for /checklist
/checklist --all     # cross-project roll-up + open queued/blocked/needs-review
```

Per-repo (the atom): loads `checklist.yaml`, runs each read-only `check`
in the repo root, and renders one row per check. Exit 0 → ✅, non-zero → ❌.

Cross-project (`--all`): runs the per-repo checklist over every configured
repo, prints a matrix (repo × check), then queries `gh` for open issues
labelled `queued` / `blocked` and PRs labelled `needs-review`.

All checks are READ-ONLY and non-destructive.

See: `plugins/core/skills/command-center/SKILL.md`
