"""
data_loader.py
Load parsed well data into MySQL database.
"""

import logging
import mysql.connector
from db_setup import get_connection

logger = logging.getLogger(__name__)


def insert_well_info(well_info):
    """
    Insert or update a well_info record in the database.
    Uses INSERT ... ON DUPLICATE KEY UPDATE to handle re-runs.
    """
    conn = get_connection()
    cursor = conn.cursor()

    sql = """
        INSERT INTO well_info (
            well_file_no, api_number, well_name, operator, field_name,
            location_desc, section, township, range_dir, county, state,
            latitude, longitude, elevation_gl, elevation_kb,
            spud_date, completion_date, well_status, well_type,
            total_depth, producing_method, surface_casing,
            production_casing, pdf_filename
        ) VALUES (
            %(well_file_no)s, %(api_number)s, %(well_name)s, %(operator)s,
            %(field_name)s, %(location_desc)s, %(section)s, %(township)s,
            %(range_dir)s, %(county)s, %(state)s, %(latitude)s, %(longitude)s,
            %(elevation_gl)s, %(elevation_kb)s, %(spud_date)s,
            %(completion_date)s, %(well_status)s, %(well_type)s,
            %(total_depth)s, %(producing_method)s, %(surface_casing)s,
            %(production_casing)s, %(pdf_filename)s
        )
        ON DUPLICATE KEY UPDATE
            api_number = COALESCE(NULLIF(VALUES(api_number), ''), api_number),
            well_name = COALESCE(NULLIF(VALUES(well_name), ''), well_name),
            operator = COALESCE(NULLIF(VALUES(operator), ''), operator),
            field_name = COALESCE(NULLIF(VALUES(field_name), ''), field_name),
            location_desc = COALESCE(NULLIF(VALUES(location_desc), ''), location_desc),
            section = COALESCE(NULLIF(VALUES(section), ''), section),
            township = COALESCE(NULLIF(VALUES(township), ''), township),
            range_dir = COALESCE(NULLIF(VALUES(range_dir), ''), range_dir),
            county = COALESCE(NULLIF(VALUES(county), ''), county),
            latitude = COALESCE(VALUES(latitude), latitude),
            longitude = COALESCE(VALUES(longitude), longitude),
            elevation_gl = COALESCE(NULLIF(VALUES(elevation_gl), ''), elevation_gl),
            elevation_kb = COALESCE(NULLIF(VALUES(elevation_kb), ''), elevation_kb),
            spud_date = COALESCE(NULLIF(VALUES(spud_date), ''), spud_date),
            completion_date = COALESCE(NULLIF(VALUES(completion_date), ''), completion_date),
            well_status = COALESCE(NULLIF(VALUES(well_status), ''), well_status),
            well_type = COALESCE(NULLIF(VALUES(well_type), ''), well_type),
            total_depth = COALESCE(NULLIF(VALUES(total_depth), ''), total_depth),
            producing_method = COALESCE(NULLIF(VALUES(producing_method), ''), producing_method),
            surface_casing = COALESCE(NULLIF(VALUES(surface_casing), ''), surface_casing),
            production_casing = COALESCE(NULLIF(VALUES(production_casing), ''), production_casing),
            pdf_filename = VALUES(pdf_filename)
    """

    try:
        cursor.execute(sql, well_info)
        conn.commit()
        logger.info(
            "Inserted/updated well_info for well_file_no=%s",
            well_info.get("well_file_no")
        )
    except mysql.connector.Error as e:
        logger.error(
            "Error inserting well_info for %s: %s",
            well_info.get("well_file_no"), str(e)
        )
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def insert_stimulation_records(well_file_no, stim_records):
    """
    Insert stimulation records for a given well.
    Deletes existing records first to avoid duplicates on re-run.
    """
    if not stim_records:
        return

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Remove existing stim records for this well
        cursor.execute(
            "DELETE FROM stimulation_data WHERE well_file_no = %s",
            (well_file_no,)
        )

        sql = """
            INSERT INTO stimulation_data (
                well_file_no, date_stimulated, stimulated_formation,
                top_ft, bottom_ft, stimulation_stages, volume,
                volume_units, treatment_type, acid_pct, lbs_proppant,
                max_treatment_pressure_psi, max_treatment_rate_bbls_min,
                details
            ) VALUES (
                %(well_file_no)s, %(date_stimulated)s, %(stimulated_formation)s,
                %(top_ft)s, %(bottom_ft)s, %(stimulation_stages)s, %(volume)s,
                %(volume_units)s, %(treatment_type)s, %(acid_pct)s,
                %(lbs_proppant)s, %(max_treatment_pressure_psi)s,
                %(max_treatment_rate_bbls_min)s, %(details)s
            )
        """

        for record in stim_records:
            record["well_file_no"] = well_file_no
            cursor.execute(sql, record)

        conn.commit()
        logger.info(
            "Inserted %d stimulation records for well %s",
            len(stim_records), well_file_no
        )
    except mysql.connector.Error as e:
        logger.error(
            "Error inserting stim data for %s: %s",
            well_file_no, str(e)
        )
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def load_well_data(well_info, stim_records):
    """Load a complete well record (info + stimulation) into the database."""
    well_file_no = well_info.get("well_file_no")
    if not well_file_no:
        logger.warning("Skipping record with no well_file_no")
        return

    insert_well_info(well_info)
    insert_stimulation_records(well_file_no, stim_records)
