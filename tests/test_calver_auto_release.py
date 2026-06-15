"""Tests for calver-auto-release."""

from __future__ import annotations

import datetime
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import git
import pytest

from calver_auto_release import (
    DEFAULT_FOOTER,
    DEFAULT_SKIP_PATTERNS,
    _format_release_notes,
    _get_commit_messages_since_last_release,
    _get_new_version,
    _should_skip_release,
    cli,
    create_release,
)


@pytest.fixture  # type: ignore[misc]
def git_repo(tmp_path: Path) -> git.Repo:
    """Create a temporary git repository."""
    repo = git.Repo.init(tmp_path)

    # Configure git user
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    # Create and commit a dummy file
    dummy_file = tmp_path / "dummy.txt"
    dummy_file.write_text("Hello, World!")
    repo.index.add([str(dummy_file)])
    repo.index.commit("Initial commit")

    # Create a fake remote
    remote_path = tmp_path / "remote"
    remote_path.mkdir()
    git.Repo.init(remote_path, bare=True)
    repo.create_remote("origin", url=str(remote_path))

    return repo


@pytest.fixture  # type: ignore[misc]
def git_repo_with_tag(git_repo: git.Repo) -> git.Repo:
    """Create a temporary git repository with a tag."""
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    tag_name = f"v{now.year}.{now.month}.0"
    git_repo.create_tag(tag_name, message=f"Release {tag_name}")
    return git_repo


def _commit_file(repo: git.Repo, message: str) -> None:
    """Append to a tracked file and commit it."""
    history = Path(repo.working_dir) / "history.txt"
    existing = history.read_text() if history.exists() else ""
    history.write_text(f"{existing}{message}\n")
    repo.index.add([str(history)])
    repo.index.commit(message)


def test_create_release_basic(git_repo: git.Repo) -> None:
    """Test basic release creation."""
    version = create_release(repo_path=git_repo.working_dir)
    assert version is not None
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    assert version == f"v{now.year}.{now.month}.0"
    assert version in [tag.name for tag in git_repo.tags]


def test_create_release_with_existing_tag(git_repo_with_tag: git.Repo) -> None:
    """Test release creation with existing tag."""
    # Create a new commit
    dummy_file = Path(git_repo_with_tag.working_dir) / "dummy2.txt"
    dummy_file.write_text("New file")
    git_repo_with_tag.index.add([str(dummy_file)])
    git_repo_with_tag.index.commit("Second commit")

    version = create_release(repo_path=git_repo_with_tag.working_dir)
    assert version is not None
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    assert version == f"v{now.year}.{now.month}.1"


def test_create_release_skip_patterns(git_repo: git.Repo) -> None:
    """Test release skipping based on commit message."""
    # Create a commit with skip pattern
    dummy_file = Path(git_repo.working_dir) / "dummy2.txt"
    dummy_file.write_text("New file")
    git_repo.index.add([str(dummy_file)])
    git_repo.index.commit("[skip release] Skip this release")

    version = create_release(repo_path=git_repo.working_dir)
    assert version is None
    assert not git_repo.tags


def test_create_release_dry_run(git_repo: git.Repo) -> None:
    """Test dry run mode."""
    version = create_release(repo_path=git_repo.working_dir, dry_run=True)
    assert version is not None
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    assert version == f"v{now.year}.{now.month}.0"
    assert not git_repo.tags


def test_create_release_already_tagged(git_repo_with_tag: git.Repo) -> None:
    """Test when commit is already tagged."""
    version = create_release(repo_path=git_repo_with_tag.working_dir)
    assert version is None


def test_create_release_ignores_non_release_tag_on_head(git_repo: git.Repo) -> None:
    """Test that non-CalVer tags on HEAD do not block a release."""
    git_repo.create_tag("build-artifact")

    version = create_release(repo_path=git_repo.working_dir, dry_run=True)

    assert version is not None


def test_create_release_custom_footer(git_repo: git.Repo) -> None:
    """Test release creation with custom footer."""
    custom_footer = "\nCustom footer"
    version = create_release(repo_path=git_repo.working_dir, footer=custom_footer)
    assert version is not None
    tag = git_repo.tags[0]
    assert custom_footer in tag.tag.message


def test_create_release_custom_skip_patterns(git_repo: git.Repo) -> None:
    """Test release creation with custom skip patterns."""
    # Create a commit with custom skip pattern
    dummy_file = Path(git_repo.working_dir) / "dummy2.txt"
    dummy_file.write_text("New file")
    git_repo.index.add([str(dummy_file)])
    git_repo.index.commit("[custom-skip] Skip this release")

    version = create_release(
        repo_path=git_repo.working_dir,
        skip_patterns=["[custom-skip]"],
    )
    assert version is None
    assert not git_repo.tags


def test_format_release_notes(git_repo: git.Repo) -> None:
    """Test release notes formatting."""
    # First test without repo
    commit_messages = "First commit\nSecond commit"
    version = "2024.1.0"
    notes = _format_release_notes(commit_messages, version, DEFAULT_FOOTER)

    # Check the main structure
    assert "# Release 2024.1.0" in notes
    assert "## 📊 Statistics" in notes
    assert "## 📝 Changes" in notes

    # Check the commit messages
    assert "First commit" in notes
    assert "Second commit" in notes

    # Check statistics
    assert "**2** commits" in notes  # 2 commits from the commit_messages
    assert "**0** contributors" in notes  # 0 because no author information without repo

    # Check footer
    footer_content = "🙏 Thank you for using this project! Please report any issues or feedback on the GitHub repository"  # noqa: E501
    assert footer_content in notes

    # Now test with actual repo
    # Create two more commits with different authors
    dummy_file2 = Path(git_repo.working_dir) / "file2.txt"
    dummy_file2.write_text("Second file")
    git_repo.index.add([str(dummy_file2)])
    git_repo.index.commit(
        "First commit",
        author=git.Actor("John Doe", "john@example.com"),
        committer=git.Actor("John Doe", "john@example.com"),
    )

    dummy_file3 = Path(git_repo.working_dir) / "file3.txt"
    dummy_file3.write_text("Third file")
    git_repo.index.add([str(dummy_file3)])
    git_repo.index.commit(
        "Second commit",
        author=git.Actor("Jane Doe", "jane@example.com"),
        committer=git.Actor("Jane Doe", "jane@example.com"),
    )

    notes_with_repo = _format_release_notes(
        commit_messages,
        version,
        DEFAULT_FOOTER,
        repo=git_repo,
    )

    # Check if contributors section exists
    assert "## 👥 Contributors" in notes_with_repo
    assert "@johndoe" in notes_with_repo
    assert "@janedoe" in notes_with_repo
    assert "@testuser" in notes_with_repo  # From the initial commit

    # Check statistics with actual commits
    assert "**3** commits" in notes_with_repo  # Initial + 2 new commits
    assert "**3** contributors" in notes_with_repo  # Test User + John Doe + Jane Doe


def test_format_release_notes_links_github_commits(git_repo: git.Repo) -> None:
    """Test that GitHub remotes produce linked commit entries."""
    git_repo.remote("origin").set_url("git@github.com:example/project.git")

    notes = _format_release_notes(
        "Initial commit",
        "v2024.1.0",
        "",
        repo=git_repo,
    )

    commit_hash = git_repo.head.commit.hexsha[:7]
    assert f"https://github.com/example/project/commit/{commit_hash}" in notes
    assert "[Initial commit]" in notes


def test_format_release_notes_without_remote(git_repo: git.Repo) -> None:
    """Test release notes formatting when no origin remote exists."""
    git_repo.delete_remote("origin")

    notes = _format_release_notes(
        "Initial commit",
        "v2024.1.0",
        "",
        repo=git_repo,
    )

    assert "- Initial commit" in notes


def test_format_release_notes_falls_back_on_git_log_error(git_repo_with_tag: git.Repo) -> None:
    """Test fallback to simple commit messages when detailed git log fails."""
    with patch(
        "calver_auto_release._get_commit_details",
        side_effect=git.exc.GitCommandError("git log", 1),
    ):
        notes = _format_release_notes(
            "Fallback commit",
            "v2024.1.0",
            "",
            repo=git_repo_with_tag,
        )

    assert "- Fallback commit" in notes
    assert "**1** commits" in notes


def test_should_skip_release(git_repo: git.Repo) -> None:
    """Test skip release detection."""
    for pattern in DEFAULT_SKIP_PATTERNS:
        dummy_file = Path(git_repo.working_dir) / f"dummy_{pattern}.txt"
        dummy_file.write_text("New file")
        git_repo.index.add([str(dummy_file)])
        git_repo.index.commit(f"Test commit {pattern}")
        assert _should_skip_release(git_repo, DEFAULT_SKIP_PATTERNS)


def test_get_new_version_no_tags(git_repo: git.Repo) -> None:
    """Test version generation with no existing tags."""
    version = _get_new_version(git_repo)
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    assert version == f"v{now.year}.{now.month}.0"


def test_get_new_version_ignores_branch_specific_tags(git_repo: git.Repo) -> None:
    """Branch-specific tags must not reset the patch counter or release boundary."""
    base_branch = git_repo.active_branch.name

    git_repo.create_tag("v2026.6.142", message="Release v2026.6.142")
    _commit_file(git_repo, "Make SaaS API type check portable (#1287)")
    git_repo.create_tag("v2026.6.143", message="Release v2026.6.143")

    git_repo.git.checkout("-b", "hotfix/sso-cookie-domain")
    _commit_file(git_repo, "Regenerate SaaS API schema for SSO hotfix")
    git_repo.create_tag("v2026.6.142-sso-cookie.2")
    git_repo.git.checkout(base_branch)

    _commit_file(git_repo, "List unstructured file memories (#1286)")

    version = _get_new_version(git_repo, today=datetime.date(2026, 6, 15))
    commit_messages = _get_commit_messages_since_last_release(git_repo)

    assert version == "v2026.6.144"
    assert "List unstructured file memories (#1286)" in commit_messages
    assert "Make SaaS API type check portable (#1287)" not in commit_messages
    assert "Regenerate SaaS API schema for SSO hotfix" not in commit_messages


def test_get_new_version_skips_exact_tag_from_unmerged_branch(git_repo: git.Repo) -> None:
    """A release candidate must never collide with any exact CalVer tag."""
    base_branch = git_repo.active_branch.name

    git_repo.create_tag("v2026.6.143", message="Release v2026.6.143")
    git_repo.git.checkout("-b", "release-candidate")
    _commit_file(git_repo, "Candidate build")
    git_repo.create_tag("v2026.6.144")
    git_repo.git.checkout(base_branch)
    _commit_file(git_repo, "Mainline fix")

    version = _get_new_version(git_repo, today=datetime.date(2026, 6, 15))
    commit_messages = _get_commit_messages_since_last_release(git_repo)

    assert version == "v2026.6.145"
    assert "Mainline fix" in commit_messages
    assert "Candidate build" not in commit_messages


def test_get_new_version_handles_zero_padded_existing_tag(git_repo: git.Repo) -> None:
    """Zero-padded month tags should still reserve their parsed version tuple."""
    git_repo.create_tag("v2026.06.1", message="Release v2026.06.1")

    version = _get_new_version(git_repo, today=datetime.date(2026, 6, 15))

    assert version == "v2026.6.2"


def test_cli(git_repo: git.Repo, capsys: pytest.CaptureFixture) -> None:
    """Test CLI interface."""
    with patch("sys.argv", ["calver-auto-release", "--repo-path", git_repo.working_dir]):
        cli()

    captured = capsys.readouterr()
    assert "Created new tag:" in captured.out
    assert git_repo.tags


def test_cli_dry_run(git_repo: git.Repo, capsys: pytest.CaptureFixture) -> None:
    """Test CLI interface with dry run."""
    with patch(
        "sys.argv",
        ["calver-auto-release", "--repo-path", git_repo.working_dir, "--dry-run"],
    ):
        cli()

    captured = capsys.readouterr()
    assert "Would create new tag:" in captured.out
    assert not git_repo.tags


def test_cli_skip_pattern(git_repo: git.Repo) -> None:
    """Test CLI interface with custom skip pattern."""
    # Create a commit with custom skip pattern
    dummy_file = Path(git_repo.working_dir) / "dummy2.txt"
    dummy_file.write_text("New file")
    git_repo.index.add([str(dummy_file)])
    git_repo.index.commit("[custom-skip] Skip this release")

    with patch(
        "sys.argv",
        [
            "calver-auto-release",
            "--repo-path",
            git_repo.working_dir,
            "--skip-pattern",
            "[custom-skip]",
        ],
    ):
        cli()

    assert not git_repo.tags


def test_github_environment(git_repo: git.Repo, tmp_path: Path) -> None:
    """Test GitHub Actions environment handling."""
    github_output = tmp_path / "github_output"
    with patch.dict(os.environ, {"GITHUB_OUTPUT": str(github_output)}):
        version = create_release(repo_path=git_repo.working_dir)

    assert version is not None
    assert github_output.exists()
    assert f"version={version}" in github_output.read_text()


def test_real_git_operations(tmp_path: Path) -> None:
    """Test actual git operations using subprocess."""
    # Initialize a new repo
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    remote_path = tmp_path / "remote"
    remote_path.mkdir()

    # Initialize bare remote repository
    subprocess.run(["git", "init", "--bare"], cwd=remote_path, check=True)

    # Initialize local repository
    subprocess.run(["git", "init"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_path,
        check=True,
    )

    # Add remote
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote_path)],
        cwd=repo_path,
        check=True,
    )

    # Create and commit a file
    test_file = repo_path / "test.txt"
    test_file.write_text("Hello, World!")
    subprocess.run(["git", "add", "test.txt"], cwd=repo_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_path,
        check=True,
    )

    # Run the CLI
    with patch("sys.argv", ["calver-auto-release", "--repo-path", str(repo_path)]):
        cli()

    # Verify the tag was created
    result = subprocess.run(
        ["git", "tag"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip()


@pytest.fixture  # type: ignore[misc]
def cli_repo(tmp_path: Path) -> git.Repo:
    """Create a temporary git repository for CLI testing."""
    repo = git.Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    # Set up remote
    remote_path = tmp_path / "remote"
    remote_path.mkdir()
    git.Repo.init(remote_path, bare=True)
    repo.create_remote("origin", url=str(remote_path))

    return repo


def test_cli_environment_variables(cli_repo: git.Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test CLI behavior with environment variables."""
    # Create and commit a test file
    test_file = Path(cli_repo.working_dir) / "test.txt"
    test_file.write_text("test")
    cli_repo.index.add([str(test_file)])
    cli_repo.index.commit("Initial commit")

    # Test skip patterns from environment (with dry run)
    monkeypatch.setenv("CALVER_SKIP_PATTERNS", "[no-release], [skip-ci]")
    monkeypatch.setenv("CALVER_DRY_RUN", "true")  # Add this line
    with patch("sys.argv", ["calver-auto-release", "--repo-path", cli_repo.working_dir]):
        cli()
    assert not cli_repo.tags  # No tags should be created with dry run

    # Test custom footer from environment (with dry run)
    custom_footer = "Custom footer from env"
    monkeypatch.setenv("CALVER_FOOTER", custom_footer)
    monkeypatch.setenv("CALVER_DRY_RUN", "true")  # Keep dry run
    with patch("sys.argv", ["calver-auto-release", "--repo-path", cli_repo.working_dir]):
        cli()
    assert not cli_repo.tags  # Still no tags

    # Test actual release with different dry run values
    for dry_run_value in ["false", "FALSE", "False"]:
        monkeypatch.setenv("CALVER_DRY_RUN", dry_run_value)
        with patch("sys.argv", ["calver-auto-release", "--repo-path", cli_repo.working_dir]):
            cli()
        assert len(cli_repo.tags) == 1  # Now we should have a tag
        cli_repo.delete_tag(cli_repo.tags[0])  # Clean up for next iteration


def test_cli_environment_variables_precedence(
    cli_repo: git.Repo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that command line arguments take precedence over environment variables."""
    # Create and commit a test file with skip pattern
    test_file = Path(cli_repo.working_dir) / "test.txt"
    test_file.write_text("test")
    cli_repo.index.add([str(test_file)])
    cli_repo.index.commit("[no-release] Test skip")

    # Set environment variables that would allow release
    monkeypatch.setenv("CALVER_SKIP_PATTERNS", "[different-pattern]")
    monkeypatch.setenv("CALVER_FOOTER", "Footer from env")
    monkeypatch.setenv("CALVER_DRY_RUN", "false")

    # CLI args should take precedence and prevent release
    with patch(
        "sys.argv",
        [
            "calver-auto-release",
            "--repo-path",
            cli_repo.working_dir,
            "--skip-pattern",
            "[no-release]",
        ],
    ):
        cli()

    assert not cli_repo.tags  # No tags should be created due to skip pattern


def test_cli_environment_variables_invalid(
    cli_repo: git.Repo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test CLI behavior with invalid environment variables."""
    # Create and commit a test file
    test_file = Path(cli_repo.working_dir) / "test.txt"
    test_file.write_text("test")
    cli_repo.index.add([str(test_file)])
    cli_repo.index.commit("Initial commit")

    # Test invalid dry run value
    monkeypatch.setenv("CALVER_DRY_RUN", "invalid")
    with patch("sys.argv", ["calver-auto-release", "--repo-path", cli_repo.working_dir]):
        version = create_release(repo_path=cli_repo.working_dir)
    assert version is not None  # Should default to False for invalid value
