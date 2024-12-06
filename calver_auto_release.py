#!/usr/bin/env python3
"""calver-auto-release: Create new release tags with CalVer format."""

from __future__ import annotations

import datetime
import operator
import os
from typing import TYPE_CHECKING

import git
from packaging import version

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

DEFAULT_SKIP_PATTERNS = ["[skip release]", "[pre-commit.ci]", "⬆️ Update"]
DEFAULT_FOOTER = (
    "\n\n🙏 Thank you for using this project! Please report any issues "
    "or feedback on the GitHub repository."
)


def create_release(
    *,
    repo_path: str | Path = ".",
    skip_patterns: Sequence[str] | None = None,
    footer: str | None = None,
    dry_run: bool = False,
) -> str | None:
    """Create a new release tag with CalVer format.

    Parameters
    ----------
    repo_path
        Path to the git repository.
    skip_patterns
        List of patterns to check in commit messages to skip release.
    footer
        Custom footer to add to release notes.
    dry_run
        If True, only return the version without creating the release.

    Returns
    -------
    str | None
        The new version number if a release was created or would be created (dry_run),
        None if release was skipped.

    """
    skip_patterns = skip_patterns or DEFAULT_SKIP_PATTERNS
    footer = footer or DEFAULT_FOOTER

    repo = git.Repo(repo_path)

    if _is_already_tagged(repo):
        print("Current commit is already tagged!")
        return None

    if _should_skip_release(repo, skip_patterns):
        print("Skipping release due to commit message!")
        return None

    new_version = _get_new_version(repo)
    commit_messages = _get_commit_messages_since_last_release(repo)
    release_notes = _format_release_notes(commit_messages, new_version, footer)

    if not dry_run:
        _create_tag(repo, new_version, release_notes)
        _push_tag(repo, new_version)

        # Write the output version to the GITHUB_OUTPUT environment file if it exists
        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:  # noqa: PTH123
                f.write(f"version={new_version}\n")

        print(f"Created new tag: {new_version}")

    return new_version


def _is_already_tagged(repo: git.Repo) -> bool:
    """Check if the current commit is already tagged."""
    return bool(repo.git.tag(points_at="HEAD"))


def _should_skip_release(repo: git.Repo, skip_patterns: Sequence[str]) -> bool:
    """Check if the commit message contains any skip patterns."""
    commit_message = repo.head.commit.message.split("\n")[0]
    return any(pattern in commit_message for pattern in skip_patterns)


def _get_new_version(repo: git.Repo) -> str:
    """Get the new version number."""
    try:
        latest_tag = max(repo.tags, key=operator.attrgetter("commit.committed_datetime"))
        last_version = version.parse(latest_tag.name)
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        patch = (
            last_version.micro + 1
            if last_version.major == now.year and last_version.minor == now.month
            else 0
        )
    except ValueError:  # No tags exist
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        patch = 0

    return f"{now.year}.{now.month}.{patch}"


def _set_author(repo: git.Repo) -> None:
    """Set author information."""
    author_name = repo.head.commit.author.name
    author_email = repo.head.commit.author.email
    os.environ["GIT_AUTHOR_NAME"] = author_name
    os.environ["GIT_AUTHOR_EMAIL"] = author_email
    os.environ["GIT_COMMITTER_NAME"] = author_name
    os.environ["GIT_COMMITTER_EMAIL"] = author_email


def _create_tag(repo: git.Repo, new_version: str, release_notes: str) -> None:
    """Create a new tag."""
    _set_author(repo)
    repo.create_tag(new_version, message=f"Release {new_version}\n\n{release_notes}")


def _push_tag(repo: git.Repo, new_version: str) -> None:
    """Push the new tag to the remote repository."""
    origin = repo.remote("origin")
    origin.push(new_version)


def _get_commit_messages_since_last_release(repo: git.Repo) -> str:
    """Get the commit messages since the last release."""
    try:
        latest_tag = max(repo.tags, key=operator.attrgetter("commit.committed_datetime"))
        return repo.git.log(f"{latest_tag}..HEAD", "--pretty=format:%s")  # type: ignore[no-any-return]
    except ValueError:  # No tags exist
        return repo.git.log("--pretty=format:%s")  # type: ignore[no-any-return]


def _format_release_notes(commit_messages: str, new_version: str, footer: str) -> str:
    """Format the release notes."""
    header = f"🚀 Release {new_version}\n\n"
    intro = "📝 This release includes the following changes:\n\n"
    commit_list = commit_messages.split("\n")
    formatted_commit_list = [f"- {commit}" for commit in commit_list]
    commit_section = "\n".join(formatted_commit_list)
    return f"{header}{intro}{commit_section}{footer}"


def cli() -> None:
    """Command-line interface for calver-auto-release."""
    import argparse

    parser = argparse.ArgumentParser(description="Create a new release with CalVer format.")
    parser.add_argument(
        "--repo-path",
        type=str,
        default=".",
        help="Path to the git repository (default: current directory)",
    )
    parser.add_argument(
        "--skip-pattern",
        action="append",
        help="Pattern to check in commit messages to skip release (can be specified multiple times)",  # noqa: E501
    )
    parser.add_argument(
        "--footer",
        type=str,
        help="Custom footer to add to release notes",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only show what would be done without creating the release",
    )

    args = parser.parse_args()

    version = create_release(
        repo_path=args.repo_path,
        skip_patterns=args.skip_pattern,
        footer=args.footer,
        dry_run=args.dry_run,
    )

    if version and args.dry_run:
        print(f"Would create new tag: {version}")


if __name__ == "__main__":
    cli()
