#!/bin/bash
# Setup script for windmill-git-sync

set -e

echo "Setting up Windmill Git Sync..."

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your configuration"
else
    echo "✓ .env file already exists"
fi

# Create Docker volume if it doesn't exist
if ! docker volume inspect windmill-workspace-data >/dev/null 2>&1; then
    echo "Creating windmill-workspace-data Docker volume..."
    docker volume create windmill-workspace-data
    echo "✓ Volume created"
else
    echo "✓ windmill-workspace-data already exists"
fi

echo ""
echo "Setup complete! Next steps:"
echo "1. Edit .env with your Windmill and Git configuration"
echo "2. Add the windmill-git-sync service block from docker-compose.yml to your Windmill docker-compose file"
echo "3. Run: docker-compose up -d windmill-git-sync"
echo "4. Test from within Docker network: docker-compose exec windmill_server curl -X POST http://windmill-git-sync:8080/sync"
