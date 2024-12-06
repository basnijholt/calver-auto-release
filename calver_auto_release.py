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
from rich.syntax import Syntax
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
        release_notes = _format_release_notes(commit_messages, new_version, footer, repo=repo)

    # Show release information
    _display_release_info(new_version, commit_messages.split("\n"), dry_run, release_notes)

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


def _display_release_info(
    version: str,
    commits: list[str],
    dry_run: bool,  # noqa: FBT001
    release_notes: str,
) -> None:
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

    # Create a panel for release notes with syntax highlighting
    release_notes_panel = Panel(
        Syntax(release_notes, "markdown", theme="monokai", line_numbers=False),
        title="📋 Release Notes Preview",
        border_style="green",
    )

    # Print everything
    console.print(info_panel)
    console.print(table)
    console.print(release_notes_panel)
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


def _get_commit_details(repo: git.Repo, since_ref: str | None = None) -> list[tuple[str, str, str]]:
    """Get detailed commit information since the last release.

    Returns
    -------
    list of (hash, author, message) tuples

    """
    log_format = "--pretty=format:%h|%an|%s"  # hash|author|subject
    if since_ref is None:
        log = repo.git.log(log_format)
    else:
        log = repo.git.log(f"{since_ref}..HEAD", log_format)

    commits = []
    for line in log.split("\n"):
        if line:
            hash_, author, message = line.split("|", 2)
            commits.append((hash_, author, message))
    return commits


def _format_release_notes(
    commit_messages: str,
    new_version: str,
    footer: str,
    *,
    repo: git.Repo | None = None,
) -> str:
    """Format the release notes with enhanced information.

    The version number will be displayed without the 'v' prefix in the release notes
    for better readability.
    """
    # Remove 'v' prefix for display in release notes
    display_version = new_version.lstrip("v")

    # Get repository URL if available
    repo_url = ""
    if repo is not None:
        try:
            remote_url = repo.remote("origin").url
            if remote_url.endswith(".git"):
                remote_url = remote_url[:-4]
            if "github.com" in remote_url:
                repo_url = remote_url.replace("git@github.com:", "https://github.com/")
        except (git.exc.GitCommandError, ValueError):
            # Ignore if we can't get the remote URL
            pass

    # Get detailed commit information if repo is available
    commits_info = []
    unique_authors = set()
    if repo is not None:
        try:
            latest_tag = max(repo.tags, key=operator.attrgetter("commit.committed_datetime"))
            commits_info = _get_commit_details(repo, latest_tag.name)
        except ValueError:  # No tags exist
            commits_info = _get_commit_details(repo)
        except git.exc.GitCommandError:
            # Fallback to simple commit messages if git commands fail
            commits_info = [("", "", msg) for msg in commit_messages.split("\n") if msg]

        unique_authors = {author for _, author, _ in commits_info}

    # Format the release notes with markdown
    parts = [
        f"# Release {display_version}\n",
        "## 📊 Statistics",
        f"- 📦 **{len(commits_info)}** commits",
        f"- 👥 **{len(unique_authors)}** contributors\n",
    ]

    if unique_authors:
        parts.extend(
            [
                "## 👥 Contributors",
                ", ".join(
                    f"@{author.lower().replace(' ', '')}" for author in sorted(unique_authors)
                ),
                "",
            ],
        )

    parts.append("## 📝 Changes\n")

    # Add commits with links if repo_url is available
    for hash_, author, message in commits_info:
        commit_line = f"- {message}"
        if repo_url and hash_:
            commit_line = (
                f"- [{message}]({repo_url}/commit/{hash_}) "
                f"by @{author.lower().replace(' ', '')}"
            )
        parts.append(commit_line)

    # Add footer with markdown formatting
    if footer:
        parts.extend(["", "---", footer.lstrip()])

    return "\n".join(parts)


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
    except Exception as e:  # pragma: no cover
        console.print(f"[bold red]Error:[/bold red] {e!s}")
        raise


if __name__ == "__main__":
    cli()
