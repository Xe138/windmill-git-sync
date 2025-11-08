#!/usr/bin/env python3
"""
Core sync logic for pulling Windmill workspace and pushing to Git.
"""
import os
import subprocess
import logging
from pathlib import Path
from git import Repo, GitCommandError

logger = logging.getLogger(__name__)

# Configuration from environment variables
WORKSPACE_DIR = Path('/workspace')
WINDMILL_BASE_URL = os.getenv('WINDMILL_BASE_URL', 'http://windmill:8000')
WINDMILL_TOKEN = os.getenv('WINDMILL_TOKEN', '')
WINDMILL_WORKSPACE = os.getenv('WINDMILL_WORKSPACE', 'default')
GIT_REMOTE_URL = os.getenv('GIT_REMOTE_URL', '')
GIT_TOKEN = os.getenv('GIT_TOKEN', '')
GIT_BRANCH = os.getenv('GIT_BRANCH', 'main')
GIT_USER_NAME = os.getenv('GIT_USER_NAME', 'Windmill Git Sync')
GIT_USER_EMAIL = os.getenv('GIT_USER_EMAIL', 'windmill@example.com')


def validate_config():
    """Validate required configuration is present."""
    missing = []

    if not WINDMILL_TOKEN:
        missing.append('WINDMILL_TOKEN')
    if not GIT_REMOTE_URL:
        missing.append('GIT_REMOTE_URL')
    if not GIT_TOKEN:
        missing.append('GIT_TOKEN')

    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")


def get_authenticated_url(url: str, token: str) -> str:
    """Insert token into HTTPS Git URL for authentication."""
    if url.startswith('https://'):
        # Format: https://TOKEN@github.com/user/repo.git
        return url.replace('https://', f'https://{token}@')
    return url


def run_wmill_sync():
    """Run wmill sync to pull workspace from Windmill."""
    logger.info(f"Syncing Windmill workspace '{WINDMILL_WORKSPACE}' from {WINDMILL_BASE_URL}")

    env = os.environ.copy()
    env['WM_BASE_URL'] = WINDMILL_BASE_URL
    env['WM_TOKEN'] = WINDMILL_TOKEN
    env['WM_WORKSPACE'] = WINDMILL_WORKSPACE

    try:
        # Run wmill sync in the workspace directory
        result = subprocess.run(
            ['wmill', 'sync', 'pull', '--yes'],
            cwd=WORKSPACE_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )

        logger.info("Windmill sync completed successfully")
        logger.debug(f"wmill output: {result.stdout}")

        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"wmill sync failed: {e.stderr}")
        raise RuntimeError(f"Failed to sync from Windmill: {e.stderr}")


def init_or_update_git_repo():
    """Initialize Git repository or open existing one."""
    git_dir = WORKSPACE_DIR / '.git'

    if git_dir.exists():
        logger.info("Opening existing Git repository")
        repo = Repo(WORKSPACE_DIR)
    else:
        logger.info("Initializing new Git repository")
        repo = Repo.init(WORKSPACE_DIR)

        # Configure user
        repo.config_writer().set_value("user", "name", GIT_USER_NAME).release()
        repo.config_writer().set_value("user", "email", GIT_USER_EMAIL).release()

    return repo


def commit_and_push_changes(repo: Repo):
    """Commit changes and push to remote Git repository."""
    # Check if there are any changes
    if not repo.is_dirty(untracked_files=True):
        logger.info("No changes to commit")
        return False

    # Stage all changes
    repo.git.add(A=True)

    # Create commit
    commit_message = f"Automated Windmill workspace backup - {WINDMILL_WORKSPACE}"
    repo.index.commit(commit_message)
    logger.info(f"Created commit: {commit_message}")

    # Configure remote with authentication
    authenticated_url = get_authenticated_url(GIT_REMOTE_URL, GIT_TOKEN)

    try:
        # Check if remote exists
        if 'origin' in [remote.name for remote in repo.remotes]:
            origin = repo.remote('origin')
            origin.set_url(authenticated_url)
        else:
            origin = repo.create_remote('origin', authenticated_url)

        # Push to remote
        logger.info(f"Pushing to {GIT_REMOTE_URL} (branch: {GIT_BRANCH})")
        origin.push(refspec=f'HEAD:{GIT_BRANCH}', force=False)
        logger.info("Push completed successfully")

        return True

    except GitCommandError as e:
        logger.error(f"Git push failed: {str(e)}")
        raise RuntimeError(f"Failed to push to Git remote: {str(e)}")


def sync_windmill_to_git():
    """
    Main sync function: pulls from Windmill, commits, and pushes to Git.

    Returns:
        dict: Result with 'success' boolean and 'message' string
    """
    try:
        # Validate configuration
        validate_config()

        # Pull from Windmill
        run_wmill_sync()

        # Initialize/update Git repo
        repo = init_or_update_git_repo()

        # Commit and push changes
        has_changes = commit_and_push_changes(repo)

        if has_changes:
            message = f"Successfully synced workspace '{WINDMILL_WORKSPACE}' to Git"
        else:
            message = "Sync completed - no changes to commit"

        return {
            'success': True,
            'message': message
        }

    except Exception as e:
        logger.exception("Sync failed")
        return {
            'success': False,
            'message': str(e)
        }


if __name__ == '__main__':
    # Allow running sync directly for testing
    logging.basicConfig(level=logging.INFO)
    result = sync_windmill_to_git()
    print(result)
