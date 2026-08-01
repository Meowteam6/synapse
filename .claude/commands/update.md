---
description: Pull latest claudeMeow and re-run install.sh (Mac only)
---
# /update

Pull latest changes from the claudeMeow plugin repo and refresh the plugin cache.

```
/update              # pull latest and re-run install.sh
```

---

## Steps

1. `cd` to the claudeMeow repo location (set by `CLAUDE_MEOW_PATH` env var, or `~/claudeMeow` default).
2. `git pull origin main`
3. Re-run `bash install.sh` to apply any new symlinks or configs.
4. Report what changed (run `git log --oneline HEAD@{1}..HEAD`).
