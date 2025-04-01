import os
import logging
from . import strings_en
from . import strings_es

# Set language based on environment
BOT_LANGUAGE = os.getenv('BOT_LANGUAGE', 'english').lower()
s = strings_es if BOT_LANGUAGE == 'spanish' else strings_en

logger = logging.getLogger(__name__)

def cleanup_temp_file(file_path):
    """Delete a temporary file"""
    if not file_path:
        logger.debug(s.LOG_CLEANUP_SKIPPED_NO_PATH)
        return False
    logger.info(s.LOG_CLEANUP_INITIATED.format(path=file_path))
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(s.LOG_CLEANUP_SUCCESS.format(path=file_path))
            return True
        else:
            logger.warning(s.WARN_CLEANUP_NOT_FOUND.format(path=file_path))
            return False
    except Exception as e:
        logger.error(s.ERROR_CLEANUP_FAILED.format(path=file_path, error=str(e)))
        return False
