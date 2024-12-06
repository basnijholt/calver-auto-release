# calver-auto-release 🏷️
[![PyPI](https://img.shields.io/pypi/v/calver-auto-release)](https://pypi.org/project/calver-auto-release/)
[![Python Versions](https://img.shields.io/pypi/pyversions/calver-auto-release)](https://pypi.org/project/calver-auto-release/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pytest](https://github.com/basnijholt/calver-auto-release/actions/workflows/pytest.yml/badge.svg)](https://github.com/basnijholt/calver-auto-release/actions/workflows/pytest.yml)

🏷️ Automatically create GitHub releases using Calendar Versioning (CalVer) on every commit.

This tool is perfect for:
- 📦 Packages where users should always use the latest version
- 🔬 Research software where releases are not tied to specific feature completions
- 🔄 Projects with continuous deployment where each merge to main is a potential release
- 🤖 Automating away the decision of "when should we release?"

By automatically creating a release on every commit to your main branch, you ensure that:
1. Users always have access to the latest changes
2. Version numbers clearly indicate when changes were made
3. Each change is properly documented through commit messages
4. The release process is completely automated

> [!NOTE]
> For the best experience, we recommend using **squash merges** for your Pull Requests.
> This ensures that:
> - Each release corresponds to one logical change
> - Release notes are clean and meaningful
> - The git history remains linear and easy to understand
>
> Configure this in your GitHub repository settings under "Pull Requests" → "Allow squash merging" and uncheck other merge methods.


<details>
<summary>ToC</summary>
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Features](#features)
- [Usage](#usage)
  - [GitHub Action](#github-action)
  - [CLI Usage](#cli-usage)
  - [Python API](#python-api)
  - [Release Notes Format](#release-notes-format)
  - [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Skip Release Patterns](#skip-release-patterns)
  - [Version Format](#version-format)
  - [Custom Footer](#custom-footer)
- [License](#license)
- [Contributing](#contributing)
  - [Development](#development)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
</details>

## Features
- 📅 Automatic Calendar Versioning (`v{YYYY}.{MM}.{PATCH}`)
- 🤖 Creates GitHub releases automatically
- 📝 Generates release notes from commit messages
- 🏷️ Supports release skipping with commit message flags
- 🔄 Integrates with GitHub Actions
- 🐍 Can be used as a Python package
- 🖥️ Command-line interface included
- 🧪 Dry-run mode for testing
- 📋 Customizable release notes format

## Usage

### GitHub Action

Add this to your workflow file (e.g., `.github/workflows/release.yml`):

```yaml
name: Create Release
on:
  push:
    branches:
      - main
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      # Create release with CalVer
      - uses: basnijholt/calver-auto-release@v1
        id: release
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          # Optional: custom configuration
          skip_patterns: "[skip release],[no-release]"
          footer: "Custom footer text"

      # Optional: publish to PyPI
      # Only run if a new version was created
      - name: Build package
        if: steps.release.outputs.version != ''
        run: |
          python -m pip install build
          python -m build

      # Option 1: Publish with official PyPA action
      - name: Publish package distributions to PyPI
        if: steps.release.outputs.version != ''
        uses: pypa/gh-action-pypi-publish@release/v1

      # Option 2: Publish with twine
      # - name: Publish package distributions to PyPI
      #   if: steps.release.outputs.version != ''
      #   env:
      #     TWINE_USERNAME: __token__
      #     TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
      #   run: |
      #     python -m pip install twine
      #     twine upload dist/*
```

The action creates a new release with CalVer versioning, and you can optionally add your preferred method for publishing to PyPI or any other post-release tasks.

> [!IMPORTANT]
> The `secrets.GITHUB_TOKEN` variable is automatically populated (see [docs](https://docs.github.com/en/actions/security-guides/automatic-token-authentication)).
> However, releases created using `GITHUB_TOKEN` will not trigger other workflows that run on the `release` event.
> If you need to trigger other workflows when a release is created, you'll need to:
> 1. Create a Personal Access Token (PAT) with `contents: write` permissions at https://github.com/settings/tokens
> 2. Add it to your repository secrets (e.g., as `PAT`)
> 3. Use it in the workflow:
>    ```yaml
>    - uses: basnijholt/calver-auto-release@v1
>      with:
>        github_token: ${{ secrets.PAT }}  # Instead of secrets.GITHUB_TOKEN
>    ```

### CLI Usage
```bash
# Basic usage
calver-auto-release --repo-path /path/to/repo

# Dry run (show what would happen without creating the release)
calver-auto-release --repo-path /path/to/repo --dry-run

# Custom skip patterns
calver-auto-release --repo-path /path/to/repo --skip-pattern "[no-release]" --skip-pattern "[skip]"
```

### Python API
```python
from calver_auto_release import create_release

# Basic usage
create_release()  # Uses current directory

# With custom configuration
create_release(
    repo_path="/path/to/repo",
    skip_patterns=["[skip]", "[no-release]"],
    footer="\nCustom footer text",
    dry_run=True,  # Show what would happen without creating the release
)
```

### Release Notes Format
The generated release notes will have this format:
```
🚀 Release YYYY.MM.PATCH

📝 This release includes the following changes:

- First commit message
- Second commit message
- etc.

🙏 Thank you for using this project! Please report any issues or feedback on the GitHub repository
```

### Requirements
- Git repository with an 'origin' remote configured
- Python 3.10 or higher
- Git command-line tools installed

## Installation

Install using pip:
```bash
pip install calver-auto-release
```

Or using [uv](https://github.com/astral-sh/uv):
```bash
uv pip install calver-auto-release
```

## Configuration

### Skip Release Patterns

You can skip creating a release by including these patterns in your commit message:
- `[skip release]`
- `[pre-commit.ci]`
- `⬆️ Update`

### Version Format

The version format follows CalVer: `YYYY.MM.PATCH`
- `YYYY`: Current year
- `MM`: Current month
- `PATCH`: Incremental number, resets when year or month changes

### Custom Footer

You can customize the footer text that appears at the end of each release note:

```python
create_release(
    footer="\nCustom footer text for all releases"
)
```

Or via CLI:
```bash
calver-auto-release --footer "Custom footer text"
```

Or in the GitHub Action:
```yaml
- uses: basnijholt/calver-auto-release@v1
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    footer: "Custom footer text"
```

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development

1. Clone the repository
2. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
3. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```
4. Run tests:
   ```bash
   pytest
   ```
