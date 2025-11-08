# Windmill Git Sync

A containerized service for syncing Windmill workspaces to Git repositories via webhook triggers.

## Overview

This service provides automated backup of Windmill workspaces to Git. It runs a lightweight Flask web server that responds to webhook requests from Windmill, syncing the workspace content using the `wmill` CLI and pushing changes to a remote Git repository.

## Features

- **Webhook-triggered sync**: Windmill can trigger backups via HTTP POST requests
- **Dockerized**: Runs as a container in the same network as Windmill
- **Git integration**: Automatic commits and pushes to remote repository
- **Authentication**: Supports Personal Access Token (PAT) authentication for Git
- **Health checks**: Built-in health endpoint for monitoring

## Quick Start

This service is designed to be added to your existing Windmill docker-compose file.

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your configuration:
   - Set `WINDMILL_TOKEN` to your Windmill API token
   - Set `GIT_REMOTE_URL` to your Git repository URL
   - Set `GIT_TOKEN` to your Git Personal Access Token
   - Set `WORKSPACE_VOLUME` to an external Docker volume name

3. Create the external volume:
   ```bash
   docker volume create windmill-workspace-data
   ```

4. Add the `windmill-git-sync` service block from `docker-compose.yml` to your existing Windmill docker-compose file.

5. Build and start the service:
   ```bash
   docker-compose up -d windmill-git-sync
   ```

6. Trigger a sync from Windmill (see Integration section below) or test from another container:
   ```bash
   docker-compose exec windmill_server curl -X POST http://windmill-git-sync:8080/sync
   ```

## Configuration

All configuration is done via environment variables in `.env`:

| Variable | Required | Description |
|----------|----------|-------------|
| `WINDMILL_BASE_URL` | Yes | URL of Windmill instance (e.g., `http://windmill:8000`) |
| `WINDMILL_TOKEN` | Yes | Windmill API token for authentication |
| `WINDMILL_WORKSPACE` | No | Workspace name (default: `default`) |
| `WORKSPACE_VOLUME` | Yes | External Docker volume name for workspace data |
| `GIT_REMOTE_URL` | Yes | HTTPS Git repository URL |
| `GIT_TOKEN` | Yes | Git Personal Access Token |
| `GIT_BRANCH` | No | Branch to push to (default: `main`) |
| `GIT_USER_NAME` | No | Git commit author name |
| `GIT_USER_EMAIL` | No | Git commit author email |

## API Endpoints

This service is only accessible within the Docker network (not exposed to the host).

- `GET /health` - Health check endpoint
- `POST /sync` - Trigger a workspace sync to Git

## Integration with Windmill

Create a scheduled flow or script in Windmill to trigger backups:

```typescript
export async function main() {
  const response = await fetch('http://windmill-git-sync:8080/sync', {
    method: 'POST'
  });
  return await response.json();
}
```

## Development

See [CLAUDE.md](CLAUDE.md) for development instructions and architecture details.

## License

MIT
