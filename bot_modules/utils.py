import os
import logging
from PyPDF2 import PdfMerger
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

def merge_pdfs(base_filenames, output_filename="merged_output.pdf"):
    """
    Merges PDF files specified by base filenames into a single output PDF.

    Args:
        base_filenames (list[str]): A list of PDF filenames without the '.pdf' extension.
                                     These files are expected to be in the 'pdfs/' directory.
        output_filename (str): The desired name for the merged output PDF file.

    Returns:
        str or None: The path to the merged PDF file if successful, otherwise None.
    """
    pdf_dir = "pdfs"
    output_path = os.path.join(pdf_dir, output_filename) # Place output in the same dir
    merger = PdfMerger()
    merged_something = False

    logger.info(s.LOG_PDF_MERGE_START.format(count=len(base_filenames), output=output_path))

    for base_name in base_filenames:
        pdf_path = os.path.join(pdf_dir, f"{base_name}.pdf")
        if os.path.exists(pdf_path):
            try:
                merger.append(pdf_path)
                logger.debug(s.LOG_PDF_APPEND_SUCCESS.format(path=pdf_path))
                merged_something = True
            except Exception as e:
                logger.error(s.ERROR_PDF_APPEND_FAILED.format(path=pdf_path, error=str(e)))
        else:
            logger.warning(s.WARN_PDF_NOT_FOUND.format(path=pdf_path))

    if not merged_something:
        logger.warning(s.WARN_PDF_MERGE_NO_FILES.format(output=output_path))
        merger.close() # Close the merger object even if nothing was added
        return None

    try:
        # Ensure the output directory exists (though it should if input files are there)
        os.makedirs(pdf_dir, exist_ok=True)
        with open(output_path, "wb") as fout:
            merger.write(fout)
        logger.info(s.LOG_PDF_MERGE_SUCCESS.format(output=output_path))
        merger.close()
        return output_path
    except Exception as e:
        logger.error(s.ERROR_PDF_MERGE_WRITE_FAILED.format(output=output_path, error=str(e)))
        merger.close() # Ensure cleanup on error
        return None
