#!/bin/bash
set -e

# Install act if not already installed
if ! command -v act &> /dev/null; then
    echo "Installing act..."
    curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
fi

# Run tests
echo "Running normal release test..."
act -j test-normal -W .github/test-cases/test-action.yml

echo "Running skip release test..."
act -j test-skip -W .github/test-cases/test-action.yml

echo "Running custom footer test..."
act -j test-custom-footer -W .github/test-cases/test-action.yml
