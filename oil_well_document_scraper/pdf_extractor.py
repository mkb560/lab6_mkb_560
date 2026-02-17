"""
pdf_extractor.py
Extract text from scanned PDF files using OCR (PyMuPDF + pytesseract).
Uses native text extraction first, falls back to OCR only for scanned pages.
"""

import os
import io
import logging
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import config

logger = logging.getLogger(__name__)

# Minimum character count to consider native text extraction sufficient
MIN_NATIVE_TEXT_LEN = 50


def extract_page_text(page, dpi=None):
    """
    Extract text from a single PDF page.
    First tries native text extraction (fast).
    Falls back to OCR if native text is too short (scanned page).
    """
    # Try native text extraction first
    native_text = page.get_text().strip()
    if len(native_text) >= MIN_NATIVE_TEXT_LEN:
        return native_text

    # Fall back to OCR for scanned pages
    if dpi is None:
        dpi = config.OCR_DPI
    pix = page.get_pixmap(dpi=dpi)
    img_bytes = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_bytes))
    text = pytesseract.image_to_string(img)
    return text


def extract_all_text(pdf_path, dpi=None):
    """
    Extract all text from a PDF and return as a single string.
    Uses native text where available, OCR for scanned pages only.
    """
    if dpi is None:
        dpi = config.OCR_DPI

    doc = fitz.open(pdf_path)
    all_text = ""
    native_count = 0
    ocr_count = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        try:
            native_text = page.get_text().strip()
        except Exception:
            native_text = ""

        if len(native_text) >= MIN_NATIVE_TEXT_LEN:
            text = native_text
            native_count += 1
        else:
            try:
                pix = page.get_pixmap(dpi=dpi)
                img_bytes = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_bytes))
                text = pytesseract.image_to_string(img)
            except Exception as e:
                logger.warning(
                    "  -> OCR failed on page %d: %s", page_num + 1, str(e)
                )
                text = ""
            ocr_count += 1

        all_text += f"\n--- PAGE {page_num + 1} ---\n{text}\n"

    doc.close()
    logger.info(
        "  -> %d pages: %d native text, %d OCR",
        native_count + ocr_count, native_count, ocr_count
    )
    return all_text


def extract_text_from_directory(pdf_dir=None, output_dir=None):
    """
    Iterate over all PDFs in a directory, OCR each one,
    and save the extracted text to .txt files.
    Returns a dict: {pdf_filename: full_text}
    """
    if pdf_dir is None:
        pdf_dir = config.PDF_DIR
    if output_dir is None:
        output_dir = config.OCR_OUTPUT_DIR

    os.makedirs(output_dir, exist_ok=True)

    pdf_files = sorted([f for f in os.listdir(pdf_dir) if f.lower().endswith(".pdf")])
    results = {}

    for idx, pdf_file in enumerate(pdf_files):
        pdf_path = os.path.join(pdf_dir, pdf_file)
        txt_file = pdf_file.replace(".pdf", ".txt")
        txt_path = os.path.join(output_dir, txt_file)

        # Skip if already processed
        if os.path.exists(txt_path):
            logger.info(
                "[%d/%d] Already processed: %s, loading from cache",
                idx + 1, len(pdf_files), pdf_file
            )
            with open(txt_path, "r", encoding="utf-8") as f:
                results[pdf_file] = f.read()
            continue

        logger.info(
            "[%d/%d] Processing: %s",
            idx + 1, len(pdf_files), pdf_file
        )

        try:
            full_text = extract_all_text(pdf_path)
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(full_text)
            results[pdf_file] = full_text
            logger.info("  -> Saved OCR text to %s", txt_path)
        except Exception as e:
            logger.error("  -> Error processing %s: %s", pdf_file, str(e))
            results[pdf_file] = ""

    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )
    texts = extract_text_from_directory()
    print(f"Processed {len(texts)} PDF files.")
