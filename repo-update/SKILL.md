---
name: repo-update
description: Update every nested Git repository under the current working directory so local checkouts follow their configured upstream branches. Use when Codex needs to keep many sibling repos in sync with remotes, fast-forward clean histories, follow remote truth after rebases or force-pushes, stash tracked local changes before updating, and then reapply those changes after the refresh.
---

# Repo Update

Keep a directory of nested repositories aligned with their remotes without hand-writing a fragile loop each time. Prefer the bundled updater script over ad hoc shell one-liners.

## Workflow

1. Change into the directory that contains the repos to refresh.
2. Run the bundled script:

```bash
python3 /path/to/repo-update/scripts/update_repos.py --root .
```

3. Add `--include-root` only when the current directory itself is also a repo that should be updated.
4. Read the per-repo summary and handle any non-clean results manually.

## What The Script Does

- Discover nested repos by looking for directories or worktrees that contain `.git`.
- Skip repos with detached `HEAD`, missing upstream configuration, or an in-progress merge, rebase, cherry-pick, revert, or bisect.
- Fetch the tracked remote for the current branch.
- Fast-forward when `HEAD` is an ancestor of the upstream tip.
- Create a `repo-update-backup/...` branch and `git reset --hard` to upstream when local history no longer matches upstream. This is the "follow remote truth" path for rebases, force-pushes, and other rewrites.
- Stash tracked local changes before merge/reset work, then try to reapply the stash afterward.
- Leave untracked files alone.

## Result Interpretation

- `up-to-date`: No branch movement was needed.
- `fast-forwarded`: Local branch moved cleanly to upstream.
- `reset-to-upstream`: Local history differed from upstream; a backup branch was created before reset.
- `restored stashed tracked changes`: A detail line showing the tracked stash reapplied cleanly.
- `stash reapply conflicted`: A detail line showing the repo updated, but reapplying the stash conflicted. Resolve it manually; the stash entry is kept when Git cannot apply it cleanly.
- `blocked` or `failed`: The repo was not updated automatically. Inspect the reported reason.

## Operational Rules

- Prefer the script instead of manually composing `find ... -exec git ...` commands.
- Assume the current working directory is the scan root unless the user asks for a different path.
- Preserve local committed history before forced resets by keeping the generated backup branch name in the final report.
- Call out repos that need manual attention instead of silently ignoring them.
- Do not clean untracked files unless the user explicitly asks for that behavior.
