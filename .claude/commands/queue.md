---
description: File the current ask as a queued GitHub Issue so the always-on executor works it and opens a draft PR
---
# /queue

Hand the current task to the always-on executor (Andre's Mac mini) instead of
doing it in this session. Perfect from a phone: describe what you want, run
`/queue`, and a draft PR shows up for review.

```
/queue               # file what we just discussed as a queued issue
/queue <one-liner>   # file exactly this as a queued issue
```

## Steps

1. Distill the ask into an issue: a `type: description` title
   (type ∈ feat|fix|chore|test|docs|refactor) and a body with **acceptance
   criteria** as a checklist. If the ask is too vague to write acceptance
   criteria, ask ONE clarifying question first — the executor refuses to guess.
2. Pick the target repo: the current repo, unless the ask names another.
3. Create the issue with the `queued` label plus the type label:
   `gh issue create -R <repo> --title "<title>" --label queued --label <type> --body "<body>"`
   (In a cloud session without `gh`, use the built-in GitHub tools to create
   the issue and apply both labels.)
4. Report back: issue number + URL, and what happens next — the executor polls
   for `queued`, branches `type/IS-NNN-slug`, implements per conventions, runs
   `/review`, and opens a **draft PR** relabelled `needs-review`.

## Notes

- The executor only picks up **open issues labelled `queued`** on repos it
  watches. Filing without the label parks it in the backlog instead.
- Never use `/queue` for work needing secrets, deploys, or destructive ops —
  the executor's permission set blocks those; it will just self-block.
