"""
main.py
Main pipeline script for Member A's workflow:
  1. Set up database (create DB + tables)
  2. OCR extract text from all PDF files
  3. Parse extracted text for structured data
  4. Load data into MySQL
  5. Run data preprocessing
"""

import os
import sys
import logging
import time

import config
from db_setup import create_database, create_tables, reset_tables
from pdf_extractor import extract_text_from_directory
from data_parser import parse_well_pdf
from data_loader import load_well_data
from preprocess import run_preprocessing

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log", mode="w"),
    ]
)
logger = logging.getLogger(__name__)


def run_pipeline(reset=False):
    """Run the full data pipeline."""
    start_time = time.time()

    # Step 1: Database setup
    logger.info("=" * 60)
    logger.info("STEP 1: Database Setup")
    logger.info("=" * 60)
    create_database()
    if reset:
        logger.info("Resetting tables...")
        reset_tables()
    else:
        create_tables()

    # Step 2: OCR extraction
    logger.info("=" * 60)
    logger.info("STEP 2: PDF OCR Extraction")
    logger.info("=" * 60)
    logger.info("PDF directory: %s", config.PDF_DIR)
    logger.info("OCR output directory: %s", config.OCR_OUTPUT_DIR)

    texts = extract_text_from_directory()
    logger.info("Extracted text from %d PDF files", len(texts))

    # Step 3 & 4: Parse and load
    logger.info("=" * 60)
    logger.info("STEP 3 & 4: Parse and Load Data")
    logger.info("=" * 60)

    success_count = 0
    error_count = 0

    for pdf_file, full_text in texts.items():
        if not full_text.strip():
            logger.warning("Empty text for %s, skipping", pdf_file)
            error_count += 1
            continue

        try:
            well_info, stim_data = parse_well_pdf(full_text, pdf_file)

            if not well_info.get("well_file_no"):
                logger.warning("No well_file_no extracted from %s", pdf_file)
                error_count += 1
                continue

            load_well_data(well_info, stim_data)
            success_count += 1

            logger.info(
                "Loaded: %s (API: %s, Well: %s, Stim records: %d)",
                pdf_file,
                well_info.get("api_number", "N/A"),
                well_info.get("well_name", "N/A"),
                len(stim_data)
            )

        except Exception as e:
            logger.error("Error processing %s: %s", pdf_file, str(e))
            error_count += 1

    logger.info(
        "Loaded %d wells successfully, %d errors",
        success_count, error_count
    )

    # Step 5: Preprocessing
    logger.info("=" * 60)
    logger.info("STEP 5: Data Preprocessing")
    logger.info("=" * 60)
    run_preprocessing()

    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info("Pipeline complete in %.1f seconds", elapsed)
    logger.info("=" * 60)


def print_summary():
    """Print a summary of what is in the database."""
    from db_setup import get_connection

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) as cnt FROM well_info")
    total = cursor.fetchone()["cnt"]

    cursor.execute(
        "SELECT COUNT(*) as cnt FROM well_info "
        "WHERE api_number IS NOT NULL AND api_number != '' AND api_number != 'N/A'"
    )
    with_api = cursor.fetchone()["cnt"]

    cursor.execute(
        "SELECT COUNT(*) as cnt FROM well_info "
        "WHERE latitude IS NOT NULL"
    )
    with_coords = cursor.fetchone()["cnt"]

    cursor.execute("SELECT COUNT(*) as cnt FROM stimulation_data")
    stim_total = cursor.fetchone()["cnt"]

    cursor.close()
    conn.close()

    logger.info("--- Database Summary ---")
    logger.info("Total wells:              %d", total)
    logger.info("Wells with API#:          %d", with_api)
    logger.info("Wells with coordinates:   %d", with_coords)
    logger.info("Stimulation records:      %d", stim_total)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Oil Wells Data Pipeline - Member A"
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Drop and recreate tables before loading"
    )
    parser.add_argument(
        "--summary-only", action="store_true",
        help="Only print database summary without running pipeline"
    )
    args = parser.parse_args()

    if args.summary_only:
        print_summary()
    else:
        run_pipeline(reset=args.reset)
        print_summary()
