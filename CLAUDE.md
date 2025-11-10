# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a containerized service for synchronizing Windmill workspaces to Git repositories. The service provides a Flask webhook server that Windmill can call to trigger automated backups of workspace content to a remote Git repository.

**Key Security Design**: Secrets (Windmill tokens, Git tokens) are NOT stored in environment variables or docker-compose files. Instead, they are passed dynamically via JSON payload in API requests from Windmill, which manages them in its own secret store.

### Architecture

The system consists of three main components:

1. **Flask Web Server** (`app/server.py`): Lightweight HTTP server that exposes webhook endpoints for triggering syncs and health checks. Parses JSON payloads containing secrets and configuration for each sync request. Only accessible within the Docker network (not exposed to host).

2. **Sync Engine** (`app/sync.py`): Core logic that orchestrates the sync process:
   - Accepts configuration as function parameters (not from environment variables)
   - Pulls workspace content from Windmill using the `wmill` CLI
   - Manages Git repository state (init on first run, subsequent updates)
   - Commits changes and pushes to remote Git repository with PAT authentication
   - Handles error cases and provides detailed logging

3. **Docker Container**: Bundles Python 3.11, wmill CLI, Git, and the Flask application. Uses volume mounts for persistent workspace storage.

### Key Design Decisions

- **API-based configuration**: Secrets and sync parameters are passed via JSON payload in each API request. Only infrastructure settings (WINDMILL_BASE_URL, volume names) are in environment variables.
- **Security-first**: No secrets in `.env` files or docker-compose.yml. All sensitive data managed by Windmill and passed per-request.
- **Flexible**: Same container can sync different workspaces to different repositories without reconfiguration or restart.
- **Integrated with Windmill docker-compose**: This service is designed to be added as an additional service in your existing Windmill docker-compose file. It shares the same Docker network and can reference Windmill services directly (e.g., `windmill_server`).
- **Network isolation**: Service uses `expose` instead of `ports` - accessible only within Docker network, not from host machine. No authentication needed since it's isolated.
- **Webhook-only triggering**: Sync happens only when explicitly triggered via HTTP POST to `/sync` with JSON payload. This gives Windmill full control over backup timing and configuration via scheduled flows.
- **HTTPS + Personal Access Token**: Git authentication uses PAT injected into HTTPS URL (format: `https://TOKEN@github.com/user/repo.git`). No SSH key management required.
- **Stateless operation**: Each sync is independent. The container can be restarted without losing state (workspace data persists in Docker volume).

## Common Development Commands

### Build and Run

```bash
# Build the Docker image
docker-compose build

# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

### Testing

```bash
# Test the sync manually (from inside container) - requires env vars for testing
docker-compose exec windmill-git-sync python app/sync.py

# Test webhook endpoint with JSON payload (from another container in the network)
docker-compose exec windmill_server curl -X POST http://windmill-git-sync:8080/sync \
  -H "Content-Type: application/json" \
  -d '{
    "windmill_token": "your-token",
    "git_remote_url": "https://github.com/user/repo.git",
    "git_token": "your-git-token",
    "workspace": "admins",
    "git_branch": "main",
    "git_user_name": "Windmill Git Sync",
    "git_user_email": "windmill@example.com"
  }'

# Health check (from another container in the network)
docker-compose exec windmill_server curl http://windmill-git-sync:8080/health
```

### Development Workflow

```bash
# Edit code locally, rebuild and restart
docker-compose down
docker-compose up -d --build

# View live logs during testing
docker-compose logs -f windmill-git-sync

# Access container shell for debugging
docker-compose exec windmill-git-sync /bin/bash

# Inspect workspace directory
docker-compose exec windmill-git-sync ls -la /workspace
```

## Environment Configuration

Configuration is split between infrastructure (`.env` file) and secrets (API payload):

### Infrastructure Configuration (.env file)

**Integration Approach:** This service's configuration should be **added to your existing Windmill `.env` file**, not maintained as a separate file. The `.env.example` file shows what to add.

Required in your Windmill `.env` file:
- `WINDMILL_DATA_PATH`: Path to Windmill data directory (should already exist in your Windmill setup)
- `WINDMILL_BASE_URL`: URL of Windmill instance (default: `http://windmill_server:8000`)

The docker-compose service uses `${WINDMILL_DATA_PATH}/workspace` as the volume mount path for workspace data.

### Secrets Configuration (API Payload)

Secrets are passed in the JSON body of POST requests to `/sync`:

- `windmill_token` (required): Windmill API token for workspace access
- `git_remote_url` (required): HTTPS URL of Git repository (e.g., `https://github.com/user/repo.git`)
- `git_token` (required): Personal Access Token with repo write permissions
- `workspace` (optional): Workspace name to sync (default: `admins`)
- `git_branch` (optional): Branch to push to (default: `main`)
- `git_user_name` (optional): Git commit author name (default: `Windmill Git Sync`)
- `git_user_email` (optional): Git commit author email (default: `windmill@example.com`)

### Docker Compose Integration

The `docker-compose.yml` file contains a service definition meant to be **added to your existing Windmill docker-compose file**, not run standalone. The service:
- Does not declare its own network (uses the implicit network from the parent compose file)
- Assumes a Windmill service named `windmill_server` exists in the same compose file
- Uses `depends_on: windmill_server` to ensure proper startup order
- Mounts workspace directory from existing Windmill data path: `${WINDMILL_DATA_PATH}/workspace:/workspace`
- Only exposes infrastructure config as environment variables (no secrets)
- Reads from the same `.env` file as your Windmill services

## Code Structure

```
app/
├── server.py       # Flask application with /health and /sync endpoints
└── sync.py         # Core sync logic (wmill pull → git commit → push)
```

### Important Functions

- `sync.sync_windmill_to_git(config: Dict[str, Any])`: Main entry point for sync operation. Accepts config dictionary with secrets and parameters. Returns dict with `success` bool and `message` string.
- `sync.validate_config(config: Dict[str, Any])`: Validates required fields are present in config dict. Raises ValueError if missing required fields (windmill_token, git_remote_url, git_token).
- `sync.run_wmill_sync(config: Dict[str, Any])`: Executes `wmill sync pull` command using config parameters, not environment variables.
- `sync.commit_and_push_changes(repo: Repo, config: Dict[str, Any])`: Stages all changes, commits with automated message, and pushes to remote using config parameters.

### Error Handling

The server validates JSON payloads and returns appropriate HTTP status codes:
- **400 Bad Request**: Missing required fields or invalid JSON
- **200 OK**: Sync succeeded (returns success dict)
- **500 Internal Server Error**: Sync failed (returns error dict)

The sync engine uses a try/except pattern that always returns a result dict, never raises to the web server. This ensures webhook requests always get a proper HTTP response with error details in JSON.

## Git Workflow

When making changes to this codebase:

1. Changes are tracked in the project's own Git repository (not the Windmill workspace backup repo)
2. The service manages commits to the **remote backup repository** specified in the API payload's `git_remote_url`
3. Commits to the backup repo use the automated format: "Automated Windmill workspace backup - {workspace_name}"

## Network Architecture

This service is designed to be added to your existing Windmill docker-compose file. When added, all services share the same Docker Compose network automatically.

Expected service topology within the same docker-compose file:

```
Services in docker-compose.yml:
├── windmill_server (Windmill API server on port 8000)
├── windmill_worker (Windmill workers)
├── postgres (Database)
└── windmill-git-sync (this service on port 8080)
```

The service references `windmill_server` via `WINDMILL_BASE_URL=http://windmill_server:8000`. If your Windmill server service has a different name, update `WINDMILL_BASE_URL` in `.env`.

## Extending the Service

### Adding Scheduled Syncs

To add cron-based scheduling in addition to webhooks:

1. Install `APScheduler` in `requirements.txt`
2. Add scheduler initialization in `server.py`
3. Update configuration to support `SYNC_SCHEDULE` env var (e.g., `0 */6 * * *` for every 6 hours)

### Adding Slack/Discord Notifications

To notify on sync completion:

1. Add `slack-sdk` or `discord-webhook` to `requirements.txt`
2. Add notification function in `sync.py`
3. Call notification function in `sync_windmill_to_git()` after successful push
4. Add webhook URL as env var in `.env` and `docker-compose.yml`

### Supporting SSH Authentication

To support SSH keys instead of PAT:

1. Update `docker-compose.yml` to mount SSH key: `~/.ssh/id_rsa:/root/.ssh/id_rsa:ro`
2. Add logic in `sync.get_authenticated_url()` to detect SSH vs HTTPS URLs
3. Configure Git to use SSH: `git config core.sshCommand "ssh -i /root/.ssh/id_rsa"`
