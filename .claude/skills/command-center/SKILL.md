---
name: command-center
description: claudeMeow command center — run checklist.yaml checks per repo, or roll up across all repos
---
# /checklist — command-center skill

The claudeMeow command center. Two layers:

- **Atom (per-repo):** load `plugins/core/checklist.yaml`, run each check in
  the current repo, render a ✅/❌ table.
- **Roll-up (`--all`):** run the same checklist across every configured repo,
  print a repo × check matrix, and surface open `queued`/`blocked` issues and
  `needs-review` PRs via `gh`.

`checklist.yaml` is the SINGLE source of truth. Never hardcode checks here or
in the command doc — read them from the spec every run.

---

## Trigger

```
/checklist           # this repo
/cc                  # alias
/checklist --all     # cross-project roll-up
```

---

## Steps — per-repo (the atom)

1. **Locate the spec.** `plugins/core/checklist.yaml` under `CLAUDE_MEOW_PATH`
   (default `~/claudeMeow`). Confirm it exists before proceeding.

2. **Parse the checks.** Read `.checks[]` — each has `id`, `title`, `check`.

   ```sh
   yq -o=json '.checks' "$CLAUDE_MEOW_PATH/plugins/core/checklist.yaml"
   ```

3. **Run each check in the repo root**, read-only, capturing only the exit code.
   The `check` string is untrusted-but-repo-authored shell; run it in a
   subshell with the repo root as cwd:

   ```sh
   ( cd "$REPO_ROOT" && sh -c "$CHECK_CMD" >/dev/null 2>&1 )
   status=$?   # 0 => ✅ satisfied, non-zero => ❌ not satisfied
   ```

   Never mutate state. If a check would write, network-mutate, or is missing a
   tool, treat a non-zero exit as ❌ — do not "fix" anything.

4. **Render the table.**

   ```
   ## Command center — <repo name>

   | Check                                | Status |
   |--------------------------------------|--------|
   | CLAUDE.md present in repo root       | ✅     |
   | Custom GitHub labels created (queued)| ❌     |
   | ...                                  | ...    |

   6/6 green — ready.        # or: 4/6 green — 2 to fix.
   ```

5. **Summarise.** Count green vs red. List the `id`s of red checks so the next
   action is obvious. Do not auto-remediate.

---

## Steps — cross-project roll-up (`--all`)

1. **Resolve the repo list.** Read `CLAUDE_MEOW_REPOS` (newline- or
   colon-separated absolute paths) if set; otherwise discover git repos one
   level under `CLAUDE_MEOW_WORKSPACE` (default `~/src`):

   ```sh
   find "$WORKSPACE" -maxdepth 2 -type d -name .git -print 2>/dev/null
   ```

   Portable to bash 3.2 — iterate with a `while read` loop, never `mapfile`.

2. **Run the per-repo checklist in each repo.** Reuse the atom steps above per
   repo; collect one status per (repo, check id).

3. **Render the matrix** — repos as rows, check ids as columns:

   ```
   ## Command center — roll-up (<N> repos)

   | Repo        | claude-md | labels | guards | perms | pre-commit | tests |
   |-------------|-----------|--------|--------|-------|------------|-------|
   | claudeMeow  | ✅        | ✅     | ✅     | ✅    | ✅         | ✅    |
   | project-x   | ✅        | ❌     | ✅     | ❌    | ✅         | ✅    |

   Fully green: 1/2 repos.
   ```

4. **Surface open work via `gh`** (read-only queries):

   ```sh
   # Open issues that are queued or blocked, across all our repos. Use `gh
   # search` (not `gh issue list`) — only search accepts the `repository` field:
   gh search issues --state open --label queued  --json number,title,repository
   gh search issues --state open --label blocked --json number,title,repository

   # PRs awaiting review:
   gh search prs --state open --label needs-review --json number,title,repository
   ```

   For multi-repo, iterate repos and pass `--repo <owner>/<name>`, or use
   `gh search issues` / `gh search prs` with a label filter.

5. **Render the work queue** beneath the matrix:

   ```
   ### Queued / blocked issues
   - blocked  #42  fix flaky auth test        (project-x)
   - queued   #51  add rate-limit adapter      (project-x)

   ### Needs review
   - PR #77  feat(core): checklist command      (claudeMeow) — review requested
   ```

---

## Rules

- **Read-only, non-destructive.** Every check and every `gh` call is a query.
  Never write files, push, mutate labels, or change settings.
- **`checklist.yaml` is authoritative.** If a check is wrong or missing, edit
  the spec — do not special-case it in this skill.
- **bash 3.2 portable.** `set -euo pipefail` in any helper script; no
  `mapfile`/`readarray`; prefer `rg`/`fd`/`jq`/`yq` with POSIX fallbacks.
- **No hardcoded ticket refs.** Runtime issue/PR numbers from `gh` are data and
  fine to display; never bake a specific ticket id into logic.
- Missing tool (`gh` not authed, `yq` absent) → report the gap plainly; do not
  crash the whole roll-up.

---

## Output contract

- Per-repo: one ✅/❌ table + green/red tally + list of failing check ids.
- `--all`: repo × check matrix + fully-green tally + queued/blocked issue list +
  needs-review PR list.
