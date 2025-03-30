import os
import logging

logger = logging.getLogger(__name__)

def cleanup_temp_file(file_path):
    """Delete a temporary file"""
    if not file_path:
        logger.debug("Cleanup skipped: No file path provided.")
        return False
    logger.info(f"Initiating cleanup of temporary file: {file_path}")
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Successfully deleted temporary file: {file_path}")
            return True
        else:
            logger.warning(f"Cleanup skipped: File not found at {file_path}")
            return False
    except Exception as e:
        logger.error(f"Error cleaning up temporary file {file_path}: {str(e)}")
        return False
