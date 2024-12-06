"""Integration tests for the GitHub Action."""

import os
import subprocess
from pathlib import Path

import git
import pytest


def test_action_yml_structure() -> None:
    """Test the structure of action.yml."""
    import yaml

    with open("action.yml") as f:  # noqa: PTH123
        action = yaml.safe_load(f)

    # Verify required fields
    assert "name" in action
    assert "description" in action
    assert "inputs" in action
    assert "runs" in action

    # Verify inputs
    assert "github_token" in action["inputs"]
    assert action["inputs"]["github_token"]["required"] is True

    # Verify it's a composite action
    assert action["runs"]["using"] == "composite"


@pytest.fixture  # type: ignore[misc]
def test_repo(tmp_path: Path) -> git.Repo:
    """Create a temporary git repository for testing."""
    repo = git.Repo.init(tmp_path)

    # Configure git user
    repo.config_writer().set_value("user", "name", "Test User").release()
    repo.config_writer().set_value("user", "email", "test@example.com").release()

    # Create and commit a dummy file
    dummy_file = tmp_path / "dummy.txt"
    dummy_file.write_text("Hello, World!")
    repo.index.add([str(dummy_file)])
    repo.index.commit("Initial commit")

    return repo


def test_action_execution(
    test_repo: git.Repo,
) -> None:
    """Test that the action executes successfully."""
    result = subprocess.run(
        [
            "calver-auto-release",
            "--repo-path",
            str(test_repo.working_dir),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Would create new tag:" in result.stdout


@pytest.mark.skipif(  # type: ignore[misc]
    "GITHUB_ACTIONS" not in os.environ,
    reason="Only runs on GitHub Actions",
)
def test_github_environment() -> None:
    """Test that the action executes in the GitHub Actions environment."""
    # Verify we're in GitHub Actions
    assert "GITHUB_ACTIONS" in os.environ
    assert "GITHUB_WORKSPACE" in os.environ
    assert "GITHUB_OUTPUT" in os.environ

    # Verify git is available and initialized
    assert Path("action.yml").exists()
    assert (
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )

    # Verify GitHub-specific paths
    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    assert workspace.exists()
    assert (workspace / "action.yml").exists()


def test_action_functionality(test_repo: git.Repo) -> None:
    """Test the core functionality of the action in a controlled environment."""
    result = subprocess.run(
        [
            "calver-auto-release",
            "--repo-path",
            str(test_repo.working_dir),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Would create new tag:" in result.stdout


def test_action_skip_patterns(test_repo: git.Repo) -> None:
    """Test that skip patterns work correctly."""
    # Create a commit that should be skipped
    test_file = Path(test_repo.working_dir) / "skip.txt"
    test_file.write_text("skip")
    test_repo.index.add([str(test_file)])
    test_repo.index.commit("[skip release] Test skip")

    result = subprocess.run(
        [
            "calver-auto-release",
            "--repo-path",
            str(test_repo.working_dir),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Skipping release" in result.stdout


def test_action_custom_footer(test_repo: git.Repo) -> None:
    """Test that custom footer is included."""
    custom_footer = "Custom footer for testing"
    result = subprocess.run(
        [
            "calver-auto-release",
            "--repo-path",
            str(test_repo.working_dir),
            "--dry-run",
            "--footer",
            custom_footer,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Would create new tag:" in result.stdout
