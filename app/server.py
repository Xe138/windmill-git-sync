#!/usr/bin/env python3
"""
Flask server for receiving webhook triggers from Windmill to sync workspace to Git.
Internal service - not exposed outside Docker network.
"""
import logging
from flask import Flask, jsonify
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
    """
    logger.info("Sync triggered via webhook")

    try:
        result = sync_windmill_to_git()

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
