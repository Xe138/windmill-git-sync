# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2025-11-09

### Added
- Containerized service for syncing Windmill workspaces to Git repositories
- Flask webhook server with `/sync` and `/health` endpoints
- wmill CLI integration for pulling workspace content from Windmill
- Automated Git commit and push functionality with PAT authentication
- Docker container with Python 3.11, wmill CLI, Git, and Flask
- Network isolation - service only accessible within Docker network (no host exposure)
- Integration with existing Windmill docker-compose files
- External volume support for persistent workspace data
- Comprehensive documentation (README.md and CLAUDE.md)
- MIT License
- Docker build validation script (`scripts/validate_docker_build.sh`)
- GitHub workflow for automated Docker image builds on version tags
- GitHub Container Registry (GHCR) publishing support
- Automated draft release creation for stable versions

### Changed
- Refactored security model: secrets now passed via JSON API payload instead of environment variables
- Updated sync.py to accept configuration via function parameters rather than env vars
- Enhanced server.py to parse and validate JSON payloads with required fields
- Improved documentation to reflect API-based secret configuration model
- Removed secret values from .env.example and docker-compose.yml

### Security
- Secrets (Windmill tokens, Git tokens) no longer stored in environment variables
- All sensitive data managed by Windmill and passed per-request via JSON payload
- Network-isolated design ensures service is only accessible within Docker network
- PAT-based Git authentication using HTTPS (no SSH key management required)

[Unreleased]: https://github.com/yourusername/windmill-git-sync/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/yourusername/windmill-git-sync/releases/tag/v0.1.0
