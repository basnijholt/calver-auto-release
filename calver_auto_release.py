#!/usr/bin/env python3
"""calver-auto-release: Create new release tags with CalVer format.

Creates tags in the format vYYYY.MM.PATCH (e.g., v2024.3.1) and corresponding
GitHub releases with automatically generated release notes.
"""

from __future__ import annotations

import datetime
import operator
import os
from typing import TYPE_CHECKING

import git
from packaging import version
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

DEFAULT_SKIP_PATTERNS = ["[skip release]", "[pre-commit.ci]", "⬆️ Update"]
DEFAULT_FOOTER = (
    "\n\n🙏 Thank you for using this project! Please report any issues "
    "or feedback on the GitHub repository."
)

console = Console()


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
        The new version number (in format vYYYY.MM.PATCH) if a release was created
        or would be created (dry_run), None if release was skipped.

    """
    skip_patterns = skip_patterns or DEFAULT_SKIP_PATTERNS
    footer = footer or DEFAULT_FOOTER

    with console.status("[bold green]Checking repository..."):
        repo = git.Repo(repo_path)

        if _is_already_tagged(repo):
            console.print("[yellow]Current commit is already tagged![/yellow]")
            return None

        if _should_skip_release(repo, skip_patterns):
            console.print("[yellow]Skipping release due to commit message![/yellow]")
            return None

        new_version = _get_new_version(repo)
        commit_messages = _get_commit_messages_since_last_release(repo)
        release_notes = _format_release_notes(commit_messages, new_version, footer)

    # Show release information
    _display_release_info(new_version, commit_messages.split("\n"), dry_run)

    if not dry_run:
        with console.status("[bold green]Creating release..."):
            _create_tag(repo, new_version, release_notes)
            _push_tag(repo, new_version)

        # Write the output version to the GITHUB_OUTPUT environment file if it exists
        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:  # noqa: PTH123
                f.write(f"version={new_version}\n")

        console.print(f"[bold green]✨ Created new tag: {new_version}[/bold green]")

    return new_version


def _display_release_info(version: str, commits: list[str], dry_run: bool) -> None:  # noqa: FBT001
    """Display formatted release information."""
    # Create a table for commit messages
    table = Table(title="📝 Commits included in this release")
    table.add_column("Commit Message", style="cyan")

    for commit in commits:
        table.add_row(commit)

    # Create a panel with release information
    mode = "[yellow]DRY RUN[/yellow]" if dry_run else "[green]RELEASE[/green]"
    info_panel = Panel(
        f"[bold]Version:[/bold] {version}\n"
        f"[bold]Mode:[/bold] {mode}\n"
        f"[bold]Number of commits:[/bold] {len(commits)}",
        title="🚀 Release Information",
        border_style="blue",
    )

    # Print everything
    console.print(info_panel)
    console.print(table)
    console.print()


def _is_already_tagged(repo: git.Repo) -> bool:
    """Check if the current commit is already tagged."""
    return bool(repo.git.tag(points_at="HEAD"))


def _should_skip_release(repo: git.Repo, skip_patterns: Sequence[str]) -> bool:
    """Check if the commit message contains any skip patterns."""
    commit_message = repo.head.commit.message.split("\n")[0]
    return any(pattern in commit_message for pattern in skip_patterns)


def _get_new_version(repo: git.Repo) -> str:
    """Get the new version number.

    Returns a version string in the format vYYYY.MM.PATCH, e.g., v2024.3.1
    """
    try:
        latest_tag = max(repo.tags, key=operator.attrgetter("commit.committed_datetime"))
        # Remove 'v' prefix for version parsing
        last_version = version.parse(latest_tag.name.lstrip("v"))
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        patch = (
            last_version.micro + 1
            if last_version.major == now.year and last_version.minor == now.month
            else 0
        )
    except ValueError:  # No tags exist
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        patch = 0

    return f"v{now.year}.{now.month}.{patch}"


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
    """Format the release notes.

    The version number will be displayed without the 'v' prefix in the release notes
    for better readability.
    """
    # Remove 'v' prefix for display in release notes
    display_version = new_version.lstrip("v")
    header = f"🚀 Release {display_version}\n\n"
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

    # Handle environment variables if CLI args are not set
    if args.skip_pattern is None and "CALVER_SKIP_PATTERNS" in os.environ:
        skip_patterns = os.environ["CALVER_SKIP_PATTERNS"].split(",")
        args.skip_pattern = [p.strip() for p in skip_patterns]

    if args.footer is None and "CALVER_FOOTER" in os.environ:
        args.footer = os.environ["CALVER_FOOTER"]

    if not args.dry_run and "CALVER_DRY_RUN" in os.environ:
        args.dry_run = os.environ["CALVER_DRY_RUN"].lower() == "true"

    try:
        version = create_release(
            repo_path=args.repo_path,
            skip_patterns=args.skip_pattern,
            footer=args.footer,
            dry_run=args.dry_run,
        )

        if version and args.dry_run:
            console.print(
                f"[yellow]Would create new tag:[/yellow] [bold cyan]{version}[/bold cyan]",
            )
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e!s}")
        raise


if __name__ == "__main__":
    cli()
