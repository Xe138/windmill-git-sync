#!/bin/bash
# Script to validate Docker build without requiring full Windmill docker-compose setup

set -e

echo "=== Validating Docker Build for Windmill Git Sync ==="
echo ""

# Build the Docker image
echo "Building Docker image..."
docker build -t windmill-git-sync:test .

echo ""
echo "=== Build Status ==="
if [ $? -eq 0 ]; then
    echo "✓ Docker image built successfully"

    # Show image details
    echo ""
    echo "=== Image Details ==="
    docker images windmill-git-sync:test --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"

    # Verify Python dependencies are installed
    echo ""
    echo "=== Verifying Python Dependencies ==="
    docker run --rm windmill-git-sync:test pip list | grep -E "(Flask|GitPython|requests|python-dotenv)"

    # Verify wmill CLI is installed
    echo ""
    echo "=== Verifying wmill CLI ==="
    docker run --rm windmill-git-sync:test wmill --version

    # Verify Git is installed
    echo ""
    echo "=== Verifying Git ==="
    docker run --rm windmill-git-sync:test git --version

    echo ""
    echo "=== Validation Complete ==="
    echo "✓ All checks passed"
    echo ""
    echo "To clean up the test image, run:"
    echo "  docker rmi windmill-git-sync:test"
else
    echo "✗ Docker build failed"
    exit 1
fi
