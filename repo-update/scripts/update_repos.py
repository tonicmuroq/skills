#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


IN_PROGRESS_MARKERS = {
    "MERGE_HEAD": "merge",
    "rebase-apply": "rebase",
    "rebase-merge": "rebase",
    "CHERRY_PICK_HEAD": "cherry-pick",
    "REVERT_HEAD": "revert",
    "BISECT_LOG": "bisect",
}


class GitCommandError(RuntimeError):
    def __init__(self, repo: Path, args: list[str], returncode: int, stderr: str):
        command = " ".join(args)
        message = stderr.strip() or f"`{command}` exited with code {returncode}"
        super().__init__(message)
        self.repo = repo
        self.args = args
        self.returncode = returncode
        self.stderr = stderr


@dataclass
class RepoResult:
    repo: Path
    action: str
    branch: str | None = None
    upstream: str | None = None
    success: bool = True
    details: list[str] = field(default_factory=list)
    backup_branch: str | None = None
    stash_used: bool = False


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if check and completed.returncode != 0:
        raise GitCommandError(repo, ["git", *args], completed.returncode, completed.stderr)
    return completed


def is_repo_dir(path: Path) -> bool:
    return (path / ".git").is_dir() or (path / ".git").is_file()


def discover_repos(root: Path, include_root: bool) -> list[Path]:
    repos: list[Path] = []
    seen: set[Path] = set()

    if include_root and is_repo_dir(root):
        repos.append(root)
        seen.add(root.resolve())

    for current_dir, dirnames, filenames in os.walk(root):
        current = Path(current_dir)

        has_git = ".git" in dirnames or ".git" in filenames
        if has_git and current != root:
            resolved = current.resolve()
            if resolved not in seen:
                repos.append(current)
                seen.add(resolved)

        if ".git" in dirnames:
            dirnames.remove(".git")

    return sorted(repos, key=lambda path: str(path.relative_to(root)))


def relative_path(root: Path, repo: Path) -> str:
    try:
        return str(repo.relative_to(root))
    except ValueError:
        return str(repo)


def git_dir(repo: Path) -> Path:
    output = git(repo, "rev-parse", "--git-dir").stdout.strip()
    git_path = Path(output)
    if git_path.is_absolute():
        return git_path
    return (repo / git_path).resolve()


def in_progress_operations(repo: Path) -> list[str]:
    repo_git_dir = git_dir(repo)
    found = []
    for marker, label in IN_PROGRESS_MARKERS.items():
        if (repo_git_dir / marker).exists():
            found.append(label)
    return sorted(set(found))


def current_branch(repo: Path) -> str | None:
    completed = git(repo, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    branch = completed.stdout.strip()
    return branch or None


def current_upstream(repo: Path) -> str | None:
    completed = git(
        repo,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{u}",
        check=False,
    )
    upstream = completed.stdout.strip()
    return upstream or None


def branch_remote(repo: Path, branch: str) -> str | None:
    completed = git(repo, "config", "--get", f"branch.{branch}.remote", check=False)
    remote = completed.stdout.strip()
    return remote or None


def has_tracked_changes(repo: Path) -> bool:
    unstaged = git(repo, "diff", "--quiet", "--ignore-submodules", "--exit-code", check=False)
    staged = git(
        repo,
        "diff",
        "--cached",
        "--quiet",
        "--ignore-submodules",
        "--exit-code",
        check=False,
    )
    return unstaged.returncode != 0 or staged.returncode != 0


def rev_parse(repo: Path, rev: str) -> str:
    return git(repo, "rev-parse", rev).stdout.strip()


def is_ancestor(repo: Path, older: str, newer: str) -> bool:
    completed = git(repo, "merge-base", "--is-ancestor", older, newer, check=False)
    return completed.returncode == 0


def sanitize_branch_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")
    return cleaned or "branch"


def create_backup_branch(repo: Path, branch: str, head_oid: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    short_oid = head_oid[:7]
    name = f"repo-update-backup/{timestamp}-{sanitize_branch_component(branch)}-{short_oid}"
    git(repo, "branch", name, head_oid)
    return name


def stash_push(repo: Path) -> bool:
    message = f"repo-update {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    completed = git(repo, "stash", "push", "--message", message, check=False)
    return completed.returncode == 0 and "No local changes" not in completed.stdout


def stash_pop(repo: Path) -> subprocess.CompletedProcess[str]:
    return git(repo, "stash", "pop", "--index", check=False)


def update_repo(root: Path, repo: Path) -> RepoResult:
    result = RepoResult(repo=repo, action="skipped")

    operations = in_progress_operations(repo)
    if operations:
        result.action = "blocked"
        result.success = False
        result.details.append(f"in-progress git operation: {', '.join(operations)}")
        return result

    branch = current_branch(repo)
    if not branch:
        result.action = "blocked"
        result.success = False
        result.details.append("detached HEAD")
        return result
    result.branch = branch

    upstream = current_upstream(repo)
    if not upstream:
        result.action = "blocked"
        result.success = False
        result.details.append("no upstream configured for current branch")
        return result
    result.upstream = upstream

    remote = branch_remote(repo, branch)
    if not remote or remote == ".":
        result.action = "failed"
        result.success = False
        result.details.append("unable to determine fetchable remote for current branch")
        return result

    git(repo, "fetch", "--prune", remote)

    head_oid = rev_parse(repo, "HEAD")
    upstream_oid = rev_parse(repo, "@{u}")

    if head_oid == upstream_oid:
        result.action = "up-to-date"
        result.details.append("already at upstream tip")
        return result

    if has_tracked_changes(repo):
        if not stash_push(repo):
            result.action = "failed"
            result.success = False
            result.details.append("unable to stash tracked local changes")
            return result
        result.stash_used = True
        result.details.append("stashed tracked local changes")

    try:
        if is_ancestor(repo, head_oid, upstream_oid):
            git(repo, "merge", "--ff-only", "@{u}")
            result.action = "fast-forwarded"
        else:
            backup_branch = create_backup_branch(repo, branch, head_oid)
            result.backup_branch = backup_branch
            result.details.append(f"saved previous HEAD to {backup_branch}")
            git(repo, "reset", "--hard", "@{u}")
            result.action = "reset-to-upstream"
    except GitCommandError:
        if result.stash_used:
            restored = stash_pop(repo)
            if restored.returncode == 0:
                result.details.append("restored stashed tracked changes after failure")
            else:
                result.details.append(
                    "failed while restoring stashed changes after update error; inspect stash manually"
                )
        raise

    if result.stash_used:
        restored = stash_pop(repo)
        if restored.returncode == 0:
            result.details.append("restored stashed tracked changes")
        else:
            result.success = False
            result.details.append("stash reapply conflicted; resolve manually and keep stash entry")

    return result


def print_repo_result(root: Path, result: RepoResult) -> None:
    repo_name = relative_path(root, result.repo)
    status = "OK" if result.success else "WARN"
    print(f"[{status}] {repo_name}: {result.action}")
    if result.branch and result.upstream:
        print(f"  branch: {result.branch} -> {result.upstream}")
    for detail in result.details:
        print(f"  detail: {detail}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update nested Git repos under a root directory.",
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Directory to scan for nested Git repos. Defaults to the current directory.",
    )
    parser.add_argument(
        "--include-root",
        action="store_true",
        help="Also update the root directory itself when it is a Git repo.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()

    if not root.is_dir():
        print(f"Root path is not a directory: {root}", file=sys.stderr)
        return 2

    repos = discover_repos(root, include_root=args.include_root)
    if not repos:
        print(f"No nested Git repos found under {root}")
        return 0

    print(f"Found {len(repos)} repo(s) under {root}")

    ok_count = 0
    warn_count = 0

    for repo in repos:
        try:
            result = update_repo(root, repo)
        except GitCommandError as error:
            result = RepoResult(repo=repo, action="failed", success=False)
            result.details.append(str(error))
        print_repo_result(root, result)
        if result.success:
            ok_count += 1
        else:
            warn_count += 1

    print(f"Summary: {ok_count} clean, {warn_count} requiring follow-up")
    return 0 if warn_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
