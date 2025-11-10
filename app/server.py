#!/usr/bin/env python3
"""
Flask server for receiving webhook triggers from Windmill to sync workspace to Git.
Internal service - not exposed outside Docker network.
"""
import logging
from flask import Flask, jsonify, request
from sync import sync_windmill_to_git

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({'status': 'healthy'}), 200


@app.route('/sync', methods=['POST'])
def trigger_sync():
    """
    Trigger a sync from Windmill workspace to Git repository.
    This endpoint is only accessible within the Docker network.

    Expected JSON payload:
    {
        "windmill_token": "string (required)",
        "git_remote_url": "string (required)",
        "git_token": "string (required)",
        "workspace": "string (optional, default: 'admins')",
        "git_branch": "string (optional, default: 'main')",
        "git_user_name": "string (optional, default: 'Windmill Git Sync')",
        "git_user_email": "string (optional, default: 'windmill@example.com')"
    }
    """
    logger.info("Sync triggered via webhook")

    # Parse JSON payload
    try:
        config = request.get_json(force=True)
        if not config:
            return jsonify({
                'success': False,
                'message': 'Request body must be valid JSON'
            }), 400
    except Exception as e:
        logger.error(f"Failed to parse JSON payload: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Invalid JSON payload: {str(e)}'
        }), 400

    # Validate required fields
    required_fields = ['windmill_token', 'git_remote_url', 'git_token']
    missing_fields = [field for field in required_fields if not config.get(field)]

    if missing_fields:
        error_message = f"Missing required fields: {', '.join(missing_fields)}"
        logger.error(error_message)
        return jsonify({
            'success': False,
            'message': error_message
        }), 400

    # Log configuration (without exposing secrets)
    workspace = config.get('workspace', 'admins')
    git_branch = config.get('git_branch', 'main')
    logger.info(f"Sync configuration - workspace: {workspace}, branch: {git_branch}")

    try:
        result = sync_windmill_to_git(config)

        if result['success']:
            logger.info(f"Sync completed successfully: {result['message']}")
            return jsonify(result), 200
        else:
            logger.error(f"Sync failed: {result['message']}")
            return jsonify(result), 500

    except Exception as e:
        logger.exception("Unexpected error during sync")
        return jsonify({
            'success': False,
            'message': f'Sync failed with error: {str(e)}'
        }), 500


if __name__ == '__main__':
    logger.info("Starting Windmill Git Sync server on port 8080")
    app.run(host='0.0.0.0', port=8080, debug=False)
