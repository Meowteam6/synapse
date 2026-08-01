---
description: Generate or update CLAUDE.md for the current repo
---
# /onboard

Generate or update `CLAUDE.md` for the current project.

```
/onboard             # generate from scratch
/onboard --update    # update existing CLAUDE.md with new discoveries
```

Reads repo structure, existing docs, test config, and package manifests.
Asks clarifying questions only when context is genuinely missing.
Outputs a complete `CLAUDE.md` with: domain, key entities, conventions, test commands, forbidden patterns.

See: `plugins/core/skills/project-onboarding/SKILL.md`
