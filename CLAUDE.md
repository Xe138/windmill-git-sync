# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a containerized service for synchronizing Windmill workspaces to Git repositories. The service provides a Flask webhook server that Windmill can call to trigger automated backups of workspace content to a remote Git repository.

### Architecture

The system consists of three main components:

1. **Flask Web Server** (`app/server.py`): Lightweight HTTP server that exposes webhook endpoints for triggering syncs and health checks. Only accessible within the Docker network (not exposed to host).

2. **Sync Engine** (`app/sync.py`): Core logic that orchestrates the sync process:
   - Pulls workspace content from Windmill using the `wmill` CLI
   - Manages Git repository state (init on first run, subsequent updates)
   - Commits changes and pushes to remote Git repository with PAT authentication
   - Handles error cases and provides detailed logging

3. **Docker Container**: Bundles Python 3.11, wmill CLI, Git, and the Flask application. Uses volume mounts for persistent workspace storage.

### Key Design Decisions

- **Integrated with Windmill docker-compose**: This service is designed to be added as an additional service in your existing Windmill docker-compose file. It shares the same Docker network and can reference Windmill services directly (e.g., `windmill_server`).
- **Network isolation**: Service uses `expose` instead of `ports` - accessible only within Docker network, not from host machine. No authentication needed since it's isolated.
- **Webhook-only triggering**: Sync happens only when explicitly triggered via HTTP POST to `/sync`. This gives Windmill full control over backup timing via scheduled flows.
- **HTTPS + Personal Access Token**: Git authentication uses PAT injected into HTTPS URL (format: `https://TOKEN@github.com/user/repo.git`). No SSH key management required.
- **Stateless operation**: Each sync is independent. The container can be restarted without losing state (workspace data persists in Docker volume).
- **Single workspace focus**: Designed to sync one Windmill workspace per container instance. For multiple workspaces, run multiple containers with different configurations.

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
# Test the sync manually (from inside container)
docker-compose exec windmill-git-sync python app/sync.py

# Test webhook endpoint (from another container in the network)
docker-compose exec windmill_server curl -X POST http://windmill-git-sync:8080/sync

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

All configuration is done via `.env` file (copy from `.env.example`). Required variables:

- `WINDMILL_TOKEN`: API token from Windmill for workspace access
- `WORKSPACE_VOLUME`: External Docker volume name for persistent workspace storage (default: `windmill-workspace-data`)
- `GIT_REMOTE_URL`: HTTPS URL of Git repository (e.g., `https://github.com/user/repo.git`)
- `GIT_TOKEN`: Personal Access Token with repo write permissions

### Docker Compose Integration

The `docker-compose.yml` file contains a service definition meant to be **added to your existing Windmill docker-compose file**, not run standalone. The service:
- Does not declare its own network (uses the implicit network from the parent compose file)
- Assumes a Windmill service named `windmill_server` exists in the same compose file
- Uses `depends_on: windmill_server` to ensure proper startup order
- Requires an external Docker volume specified in `WORKSPACE_VOLUME` env var (created via `docker volume create windmill-workspace-data`)

## Code Structure

```
app/
├── server.py       # Flask application with /health and /sync endpoints
└── sync.py         # Core sync logic (wmill pull → git commit → push)
```

### Important Functions

- `sync.sync_windmill_to_git()`: Main entry point for sync operation. Returns dict with `success` bool and `message` string.
- `sync.validate_config()`: Checks required env vars are set. Raises ValueError if missing.
- `sync.run_wmill_sync()`: Executes `wmill sync pull` command with proper environment variables.
- `sync.commit_and_push_changes()`: Stages all changes, commits with automated message, and pushes to remote.

### Error Handling

The sync engine uses a try/except pattern that always returns a result dict, never raises to the web server. This ensures webhook requests always get a proper HTTP response with error details in JSON.

## Git Workflow

When making changes to this codebase:

1. Changes are tracked in the project's own Git repository (not the Windmill workspace backup repo)
2. The service manages commits to the **remote backup repository** specified in `GIT_REMOTE_URL`
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
