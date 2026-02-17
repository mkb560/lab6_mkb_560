"""
db_setup.py
Create MySQL database and tables for oil well data.
"""

import mysql.connector
from mysql.connector import Error
import config


def get_connection(use_database=True):
    """Get a MySQL connection."""
    params = {
        "host": config.MYSQL_HOST,
        "port": config.MYSQL_PORT,
        "user": config.MYSQL_USER,
        "password": config.MYSQL_PASSWORD,
    }
    if use_database:
        params["database"] = config.MYSQL_DATABASE
    return mysql.connector.connect(**params)


def create_database():
    """Create the database if it does not exist."""
    conn = get_connection(use_database=False)
    cursor = conn.cursor()
    cursor.execute(
        f"CREATE DATABASE IF NOT EXISTS `{config.MYSQL_DATABASE}` "
        f"DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    conn.commit()
    cursor.close()
    conn.close()
    print(f"[db_setup] Database '{config.MYSQL_DATABASE}' is ready.")


def create_tables():
    """Create the well_info and stimulation_data tables."""
    conn = get_connection()
    cursor = conn.cursor()

    # ---- well_info table ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS well_info (
            id              INT AUTO_INCREMENT PRIMARY KEY,
            well_file_no    VARCHAR(20),
            api_number      VARCHAR(30),
            well_name       VARCHAR(255),
            operator        VARCHAR(255),
            field_name      VARCHAR(100),
            location_desc   VARCHAR(500),
            section         VARCHAR(20),
            township        VARCHAR(20),
            range_dir       VARCHAR(20),
            county          VARCHAR(100),
            state           VARCHAR(50) DEFAULT 'ND',
            latitude        DECIMAL(10, 6),
            longitude       DECIMAL(10, 6),
            elevation_gl    VARCHAR(50),
            elevation_kb    VARCHAR(50),
            spud_date       VARCHAR(50),
            completion_date VARCHAR(50),
            well_status     VARCHAR(100),
            well_type       VARCHAR(100),
            total_depth     VARCHAR(100),
            producing_method VARCHAR(100),
            surface_casing  TEXT,
            production_casing TEXT,
            pdf_filename    VARCHAR(255),
            -- web scraped fields (filled by Member B)
            scraped_well_status  VARCHAR(255),
            scraped_well_type    VARCHAR(255),
            scraped_closest_city VARCHAR(255),
            scraped_oil_production VARCHAR(255),
            scraped_gas_production VARCHAR(255),
            created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_well_file (well_file_no)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # ---- stimulation_data table ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stimulation_data (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            well_file_no        VARCHAR(20),
            date_stimulated     VARCHAR(50),
            stimulated_formation VARCHAR(100),
            top_ft              VARCHAR(50),
            bottom_ft           VARCHAR(50),
            stimulation_stages  VARCHAR(50),
            volume              VARCHAR(50),
            volume_units        VARCHAR(50),
            treatment_type      VARCHAR(100),
            acid_pct            VARCHAR(50),
            lbs_proppant        VARCHAR(50),
            max_treatment_pressure_psi VARCHAR(50),
            max_treatment_rate_bbls_min VARCHAR(50),
            details             TEXT,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (well_file_no) REFERENCES well_info(well_file_no)
                ON DELETE CASCADE ON UPDATE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("[db_setup] Tables 'well_info' and 'stimulation_data' are ready.")


def reset_tables():
    """Drop and recreate all tables (use with caution)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
    cursor.execute("DROP TABLE IF EXISTS stimulation_data")
    cursor.execute("DROP TABLE IF EXISTS well_info")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()
    cursor.close()
    conn.close()
    print("[db_setup] Tables dropped.")
    create_tables()


if __name__ == "__main__":
    create_database()
    create_tables()
