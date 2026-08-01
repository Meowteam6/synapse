---
name: project-onboarding
description: Read a repo's structure and docs, ask domain questions, and emit a tight CLAUDE.md
---
# /onboard — project-onboarding skill

Reads a repo's structure and existing docs, asks clarifying questions about the domain,
and outputs a tight `CLAUDE.md` with key entities, conventions, forbidden patterns, and test commands.

---

## Trigger

```
/onboard              # generate or update CLAUDE.md for current repo
/onboard --update     # update existing CLAUDE.md with any changes discovered
```

---

## Steps

1. **Read the repo structure.**
   ```sh
   find . -name "*.md" -not -path "*/node_modules/*" -not -path "*/.git/*" | head -20
   cat README.md 2>/dev/null || true
   cat pyproject.toml package.json 2>/dev/null | head -60
   ```

2. **Read existing conventions** if present:
   - `CLAUDE.md` (project root)
   - `.claude/` directory
   - Any `docs/adr/` directory

3. **Read test conventions:**
   ```sh
   find . -name "pytest.ini" -o -name "jest.config.*" -o -name "playwright.config.*" 2>/dev/null
   ```

4. **Ask the user** (only if genuinely unclear):
   - What is the primary domain? (one sentence)
   - What are the key entities?
   - Any forbidden patterns specific to this project?
   - Any external services that Claude should know about?

5. **Generate `CLAUDE.md`** using the `project-template/CLAUDE.md` as a base.
   Fill in every section from gathered context.

6. **Validate** the generated file:
   - All sections complete (no placeholder text remaining)
   - Test commands verified runnable
   - Forbidden patterns list non-empty

---

## Output

Write to `CLAUDE.md` in the project root (or update in place with `--update`).
Print a diff of what changed if updating.

---

## `CLAUDE.md` sections to populate

```markdown
# <Project Name> — Claude conventions

## What is this project
<one sentence>

## Key entities
<domain objects>

## Conventions
<naming, structure, patterns>

## How to run tests
<exact commands>

## Forbidden patterns
<what Claude must not do>

## Ticket prefix
IS-  (GitHub Issues)
```
