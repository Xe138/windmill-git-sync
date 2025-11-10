#!/usr/bin/env python3
"""
Core sync logic for pulling Windmill workspace and pushing to Git.
"""
import os
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any
from git import Repo, GitCommandError

logger = logging.getLogger(__name__)

# Configuration from environment variables (infrastructure only)
WORKSPACE_DIR = Path('/workspace')
WINDMILL_BASE_URL = os.getenv('WINDMILL_BASE_URL', 'http://windmill_server:8000')


def validate_config(config: Dict[str, Any]) -> None:
    """
    Validate required configuration is present in the provided config dict.

    Args:
        config: Configuration dictionary with sync parameters

    Raises:
        ValueError: If required fields are missing
    """
    required_fields = ['windmill_token', 'git_remote_url', 'git_token']
    missing = [field for field in required_fields if not config.get(field)]

    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")


def get_authenticated_url(url: str, token: str) -> str:
    """Insert token into HTTPS Git URL for authentication."""
    if url.startswith('https://'):
        # Format: https://TOKEN@github.com/user/repo.git
        return url.replace('https://', f'https://{token}@')
    return url


def run_wmill_sync(config: Dict[str, Any]) -> bool:
    """
    Run wmill sync to pull workspace from Windmill.

    Args:
        config: Configuration dictionary containing windmill_token and workspace

    Returns:
        bool: True if sync was successful

    Raises:
        RuntimeError: If wmill sync command fails
    """
    workspace = config.get('workspace', 'admins')
    windmill_token = config['windmill_token']

    logger.info(f"Syncing Windmill workspace '{workspace}' from {WINDMILL_BASE_URL}")

    env = os.environ.copy()
    env['WM_BASE_URL'] = WINDMILL_BASE_URL
    env['WM_TOKEN'] = windmill_token
    env['WM_WORKSPACE'] = workspace

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


def init_or_update_git_repo(config: Dict[str, Any]) -> Repo:
    """
    Initialize Git repository or open existing one.

    Args:
        config: Configuration dictionary containing optional git_user_name and git_user_email

    Returns:
        Repo: GitPython repository object
    """
    git_user_name = config.get('git_user_name', 'Windmill Git Sync')
    git_user_email = config.get('git_user_email', 'windmill@example.com')

    git_dir = WORKSPACE_DIR / '.git'

    if git_dir.exists():
        logger.info("Opening existing Git repository")
        repo = Repo(WORKSPACE_DIR)
    else:
        logger.info("Initializing new Git repository")
        repo = Repo.init(WORKSPACE_DIR)

        # Configure user
        repo.config_writer().set_value("user", "name", git_user_name).release()
        repo.config_writer().set_value("user", "email", git_user_email).release()

    return repo


def commit_and_push_changes(repo: Repo, config: Dict[str, Any]) -> bool:
    """
    Commit changes and push to remote Git repository.

    Args:
        repo: GitPython Repo object
        config: Configuration dictionary containing git_remote_url, git_token, git_branch, and workspace

    Returns:
        bool: True if changes were committed and pushed, False if no changes

    Raises:
        RuntimeError: If git push fails
    """
    workspace = config.get('workspace', 'admins')
    git_remote_url = config['git_remote_url']
    git_token = config['git_token']
    git_branch = config.get('git_branch', 'main')

    # Check if there are any changes
    if not repo.is_dirty(untracked_files=True):
        logger.info("No changes to commit")
        return False

    # Stage all changes
    repo.git.add(A=True)

    # Create commit
    commit_message = f"Automated Windmill workspace backup - {workspace}"
    repo.index.commit(commit_message)
    logger.info(f"Created commit: {commit_message}")

    # Configure remote with authentication
    authenticated_url = get_authenticated_url(git_remote_url, git_token)

    try:
        # Check if remote exists
        if 'origin' in [remote.name for remote in repo.remotes]:
            origin = repo.remote('origin')
            origin.set_url(authenticated_url)
        else:
            origin = repo.create_remote('origin', authenticated_url)

        # Push to remote
        logger.info(f"Pushing to {git_remote_url} (branch: {git_branch})")
        origin.push(refspec=f'HEAD:{git_branch}', force=False)
        logger.info("Push completed successfully")

        return True

    except GitCommandError as e:
        logger.error(f"Git push failed: {str(e)}")
        raise RuntimeError(f"Failed to push to Git remote: {str(e)}")


def sync_windmill_to_git(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main sync function: pulls from Windmill, commits, and pushes to Git.

    Args:
        config: Configuration dictionary with the following keys:
            - windmill_token (required): Windmill API token
            - git_remote_url (required): Git repository URL
            - git_token (required): Git authentication token
            - workspace (optional): Windmill workspace name (default: "admins")
            - git_branch (optional): Git branch to push to (default: "main")
            - git_user_name (optional): Git commit author name (default: "Windmill Git Sync")
            - git_user_email (optional): Git commit author email (default: "windmill@example.com")

    Returns:
        dict: Result with 'success' boolean and 'message' string
    """
    try:
        # Validate configuration
        validate_config(config)

        workspace = config.get('workspace', 'admins')

        # Pull from Windmill
        run_wmill_sync(config)

        # Initialize/update Git repo
        repo = init_or_update_git_repo(config)

        # Commit and push changes
        has_changes = commit_and_push_changes(repo, config)

        if has_changes:
            message = f"Successfully synced workspace '{workspace}' to Git"
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
    # Allow running sync directly for testing with environment variables
    logging.basicConfig(level=logging.INFO)

    # For testing: load config from environment variables
    test_config = {
        'windmill_token': os.getenv('WINDMILL_TOKEN', ''),
        'git_remote_url': os.getenv('GIT_REMOTE_URL', ''),
        'git_token': os.getenv('GIT_TOKEN', ''),
        'workspace': os.getenv('WINDMILL_WORKSPACE', 'admins'),
        'git_branch': os.getenv('GIT_BRANCH', 'main')
    }

    result = sync_windmill_to_git(test_config)
    print(result)
