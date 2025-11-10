#!/usr/bin/env python3
"""
Core sync logic for pulling Windmill workspace and pushing to Git.
"""
import os
import shutil
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

    try:
        # Run wmill sync in the workspace directory with explicit flags
        # Note: When using --base-url, --token and --workspace are required
        result = subprocess.run(
            [
                'wmill', 'sync', 'pull',
                '--base-url', WINDMILL_BASE_URL,
                '--token', windmill_token,
                '--workspace', workspace,
                '--yes'
            ],
            cwd=WORKSPACE_DIR,
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


def is_workspace_empty() -> bool:
    """
    Check if workspace directory is empty or not initialized as a git repo.

    Returns:
        bool: True if directory is empty or not a git repository
    """
    git_dir = WORKSPACE_DIR / '.git'

    # Check if .git directory exists
    if not git_dir.exists():
        # Check if workspace is completely empty or has no meaningful content
        workspace_contents = list(WORKSPACE_DIR.iterdir())
        return len(workspace_contents) == 0

    return False


def clone_remote_repository(config: Dict[str, Any]) -> Repo:
    """
    Clone remote repository to workspace directory.

    Args:
        config: Configuration dictionary containing git_remote_url, git_token, git_branch

    Returns:
        Repo: GitPython repository object

    Raises:
        RuntimeError: If clone fails
    """
    git_remote_url = config['git_remote_url']
    git_token = config['git_token']
    git_branch = config.get('git_branch', 'main')
    git_user_name = config.get('git_user_name', 'Windmill Git Sync')
    git_user_email = config.get('git_user_email', 'windmill@example.com')

    authenticated_url = get_authenticated_url(git_remote_url, git_token)

    logger.info(f"Cloning remote repository from {git_remote_url}")

    try:
        # Clone the repository
        repo = Repo.clone_from(authenticated_url, WORKSPACE_DIR)

        # Configure user
        repo.config_writer().set_value("user", "name", git_user_name).release()
        repo.config_writer().set_value("user", "email", git_user_email).release()

        # Check if the specified branch exists
        try:
            repo.git.checkout(git_branch)
            logger.info(f"Checked out existing branch '{git_branch}'")
        except GitCommandError:
            # Branch doesn't exist, create it as orphan
            logger.info(f"Branch '{git_branch}' doesn't exist, creating new branch")
            repo.git.checkout('--orphan', git_branch)
            # Remove all files from staging (orphan branch starts with staged files)
            try:
                repo.git.rm('-rf', '.')
            except GitCommandError:
                # If rm fails (no files to remove), that's fine
                pass

        logger.info("Repository cloned successfully")
        return repo

    except GitCommandError as e:
        logger.error(f"Failed to clone repository: {str(e)}")
        raise RuntimeError(f"Failed to clone remote repository: {str(e)}")


def sync_local_with_remote(repo: Repo, config: Dict[str, Any]) -> None:
    """
    Sync local repository with remote (fetch and hard reset).

    Args:
        repo: GitPython Repo object
        config: Configuration dictionary containing git_branch

    Raises:
        RuntimeError: If sync fails
    """
    git_branch = config.get('git_branch', 'main')

    logger.info(f"Syncing local repository with remote branch '{git_branch}'")

    try:
        # Fetch from remote
        origin = repo.remote('origin')
        origin.fetch()
        logger.info("Fetched from remote")

        # Reset local branch to match remote
        try:
            repo.git.reset('--hard', f'origin/{git_branch}')
            logger.info(f"Reset local branch to match origin/{git_branch}")
        except GitCommandError as e:
            # Branch might not exist on remote yet, which is fine
            logger.info(f"Branch '{git_branch}' doesn't exist on remote yet, will be created on push")

    except GitCommandError as e:
        logger.error(f"Failed to sync with remote: {str(e)}")
        raise RuntimeError(f"Failed to sync local repository with remote: {str(e)}")


def init_or_update_git_repo(config: Dict[str, Any]) -> Repo:
    """
    Initialize Git repository, clone from remote if needed, or open existing one.

    Args:
        config: Configuration dictionary containing optional git_user_name and git_user_email

    Returns:
        Repo: GitPython repository object
    """
    git_user_name = config.get('git_user_name', 'Windmill Git Sync')
    git_user_email = config.get('git_user_email', 'windmill@example.com')

    git_dir = WORKSPACE_DIR / '.git'

    # Check if workspace is empty/uninitialized
    if is_workspace_empty():
        # Try to clone from remote
        logger.info("Workspace is empty, attempting to clone from remote")
        return clone_remote_repository(config)

    # Repository already exists
    if git_dir.exists():
        logger.info("Opening existing Git repository")
        repo = Repo(WORKSPACE_DIR)

        # Sync with remote before continuing
        sync_local_with_remote(repo, config)

        return repo
    else:
        # Workspace has files but no git repo - delete contents and clone
        logger.info("Workspace has files but no git repository, cleaning and cloning from remote")

        # Delete all contents in workspace
        for item in WORKSPACE_DIR.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

        logger.info("Workspace cleaned, attempting to clone from remote")
        return clone_remote_repository(config)


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
        push_info = origin.push(refspec=f'HEAD:{git_branch}', force=False)

        # Check push results for errors
        if push_info:
            for info in push_info:
                if info.flags & info.ERROR:
                    error_msg = f"Push failed: {info.summary}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
                elif info.flags & info.REJECTED:
                    error_msg = f"Push rejected (non-fast-forward): {info.summary}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)

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

        # Initialize/update Git repo (must happen BEFORE wmill sync to clone if needed)
        repo = init_or_update_git_repo(config)

        # Pull from Windmill (overwrites files with Windmill workspace content)
        run_wmill_sync(config)

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
