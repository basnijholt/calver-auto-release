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
