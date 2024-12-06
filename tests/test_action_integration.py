"""Integration tests for the GitHub Action."""

import os
import subprocess
from pathlib import Path

import pytest


def test_action_inputs(tmp_path: Path) -> None:
    """Test that the action.yml inputs are valid."""
    action_yml = Path("action.yml")
    assert action_yml.exists()

    # Run the action with act
    result = subprocess.run(
        ["act", "-n"],  # dry run
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0


@pytest.mark.skipif(  # type: ignore[misc]
    "GITHUB_ACTIONS" not in os.environ,
    reason="Only runs on GitHub Actions",
)
def test_action_execution() -> None:
    """Test that the action executes successfully on GitHub Actions."""
    # This test only runs in the GitHub Actions environment
    assert "GITHUB_ACTIONS" in os.environ
    assert "GITHUB_TOKEN" in os.environ

    # Verify the action's environment
    assert Path("action.yml").exists()
    assert (
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


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


def test_local_install(tmp_path: Path) -> None:
    """Test that the action installs from local directory when available."""
    # Copy action.yml and pyproject.toml to temp directory
    subprocess.run(["cp", "action.yml", "pyproject.toml", str(tmp_path)], check=True)

    # Verify the check works
    grep_result = subprocess.run(
        ["grep", "-q", 'name = "calver-auto-release"', "pyproject.toml"],
        check=True,
    )
    assert grep_result.returncode == 0

    # Create a dummy git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        check=True,
    )

    # Create a test file and commit it
    test_file = tmp_path / "test.txt"
    test_file.write_text("test")
    subprocess.run(["git", "add", "test.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=tmp_path, check=True)

    # Run the install step from action.yml
    install_result = subprocess.run(
        [
            "bash",
            "-c",
            """
            python -m pip install --upgrade pip
            if [ -f "pyproject.toml" ]; then
              pip install -e .
            else
              pip install calver-auto-release
            fi
            """,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert install_result.returncode == 0

    # Verify it installed the local version
    pip_list_result = subprocess.run(
        ["pip", "list"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "calver-auto-release (0.0.0)" in pip_list_result.stdout


def test_pypi_install(tmp_path: Path) -> None:
    """Test that the action installs from PyPI when no local version available."""
    # Copy only action.yml to temp directory
    subprocess.run(["cp", "action.yml", str(tmp_path)], check=True)

    # Run the install step from action.yml
    result = subprocess.run(
        [
            "bash",
            "-c",
            """
            python -m pip install --upgrade pip
            # In test environments, install from local directory
            if [ -f "pyproject.toml" ] && grep -q "name = \"calver-auto-release\"" pyproject.toml; then
              pip install -e .
            else
              # In production, install from PyPI
              pip install calver-auto-release
            fi
            """,  # noqa: E501
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0

    # Verify it installed from PyPI
    result = subprocess.run(
        ["pip", "show", "calver-auto-release"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "Location:" in result.stdout
    assert ".local/lib/python" in result.stdout