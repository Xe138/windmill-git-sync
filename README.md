# Windmill Git Sync

A containerized service for syncing Windmill workspaces to Git repositories via webhook triggers.

## Overview

This service provides automated backup of Windmill workspaces to Git. It runs a lightweight Flask web server that responds to webhook requests from Windmill, syncing the workspace content using the `wmill` CLI and pushing changes to a remote Git repository.

**Security Model**: Secrets are managed by Windmill and passed via API requests, not stored in environment variables or docker-compose files.

## Features

- **Webhook-triggered sync**: Windmill can trigger backups via HTTP POST requests with dynamic configuration
- **Secure by default**: No secrets in environment variables - all sensitive data passed via API payload
- **Flexible**: Same container can sync different workspaces to different repositories per request
- **Dockerized**: Runs as a container in the same network as Windmill
- **Git integration**: Automatic commits and pushes to remote repository
- **Authentication**: Supports Personal Access Token (PAT) authentication for Git
- **Health checks**: Built-in health endpoint for monitoring

## Quick Start

This service is designed to be added to your existing Windmill docker-compose setup.

### Prerequisites

- An existing Windmill docker-compose installation with a `.env` file that includes `WINDMILL_DATA_PATH`

### Installation Steps

1. **Add configuration to your Windmill `.env` file:**

   Add the configuration from `.env.example` to your existing Windmill `.env` file:
   ```bash
   # Add to your existing Windmill .env file
   WINDMILL_BASE_URL=http://windmill_server:8000
   ```

   Your `.env` should already have `WINDMILL_DATA_PATH` defined (e.g., `WINDMILL_DATA_PATH=/mnt/user/appdata/windmill`).

2. **Add the service to your docker-compose file:**

   Add the `windmill-git-sync` service block from `docker-compose.yml` to your existing Windmill docker-compose file.

3. **Build and start the service:**
   ```bash
   docker-compose up -d windmill-git-sync
   ```

4. **Configure secrets in Windmill:**

   Store your tokens in Windmill's variable/resource system and trigger syncs from Windmill flows (see Integration section below).

## Configuration

Configuration is split between infrastructure settings (in `.env`) and secrets (passed via API):

### Infrastructure Configuration (.env file)

**Note:** These settings should be added to your existing Windmill `.env` file.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WINDMILL_BASE_URL` | No | `http://windmill_server:8000` | URL of Windmill instance |
| `WINDMILL_DATA_PATH` | Yes | - | Path to Windmill data directory (should already exist in your Windmill .env) |

### Secrets Configuration (API payload)

Secrets are **not stored in environment variables**. Instead, they are passed in the JSON payload of each `/sync` request:

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `windmill_token` | Yes | - | Windmill API token for authentication |
| `git_remote_url` | Yes | - | HTTPS Git repository URL (e.g., `https://github.com/user/repo.git`) |
| `git_token` | Yes | - | Git Personal Access Token with write access |
| `workspace` | No | `admins` | Windmill workspace name to sync |
| `git_branch` | No | `main` | Git branch to push to |
| `git_user_name` | No | `Windmill Git Sync` | Git commit author name |
| `git_user_email` | No | `windmill@example.com` | Git commit author email |

## API Endpoints

This service is only accessible within the Docker network (not exposed to the host).

### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy"
}
```

### `POST /sync`

Trigger a workspace sync to Git.

**Request Body (JSON):**
```json
{
  "windmill_token": "your-windmill-token",
  "git_remote_url": "https://github.com/username/repo.git",
  "git_token": "ghp_your_github_token",
  "workspace": "my-workspace",
  "git_branch": "main",
  "git_user_name": "Windmill Git Sync",
  "git_user_email": "windmill@example.com"
}
```

**Success Response (200):**
```json
{
  "success": true,
  "message": "Successfully synced workspace 'my-workspace' to Git"
}
```

**Validation Error Response (400):**
```json
{
  "success": false,
  "message": "Missing required fields: windmill_token, git_remote_url"
}
```

**Sync Error Response (500):**
```json
{
  "success": false,
  "message": "Git push failed: authentication error"
}
```

## Integration with Windmill

Create a scheduled flow or script in Windmill to trigger backups. Store secrets in Windmill's variable/resource system:

```typescript
type Windmill = {
  token: string;
}

type Github = {
  token: string;
}

export async function main(
  windmill: Windmill,
  github: Github
) {
  const response = await fetch('http://windmill-git-sync:8080/sync', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      windmill_token: windmill.token,
      git_remote_url: 'https://github.com/username/repo.git',
      git_token: github.token,
      workspace: 'my-workspace',              // optional, defaults to 'admins'
      git_branch: 'main',                     // optional, defaults to 'main'
      git_user_name: 'Windmill Git Sync',    // optional
      git_user_email: 'windmill@example.com' // optional
    })
  });

  return await response.json();
}
```

**Setting up Windmill Resources:**

1. In Windmill, create a Variable or Resource for your Windmill token
2. Create another Variable or Resource for your GitHub PAT
3. Schedule the above script to run on your desired backup schedule (e.g., hourly, daily)

## Development

See [CLAUDE.md](CLAUDE.md) for development instructions and architecture details.

## License

MIT
