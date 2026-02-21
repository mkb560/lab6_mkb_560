import mysql.connector

WELL_FILE_NO = 11745

DATA = {
    "scraped_well_status": "Active",
    "scraped_well_type": "Oil & Gas",
    "scraped_closest_city": "Williston",
    "scraped_oil_production": "518 BBL",
    "scraped_gas_production": "518 MCF",
}

def main():
    conn = mysql.connector.connect(
        host="localhost",
        port=3306,
        user="root",
        password="",
        database="oil_wells_db",
    )
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE well_info SET
            scraped_well_status = %s,
            scraped_well_type = %s,
            scraped_closest_city = %s,
            scraped_oil_production = %s,
            scraped_gas_production = %s
        WHERE well_file_no = %s
        """,
        (
            DATA["scraped_well_status"],
            DATA["scraped_well_type"],
            DATA["scraped_closest_city"],
            DATA["scraped_oil_production"],
            DATA["scraped_gas_production"],
            WELL_FILE_NO,
        ),
    )

    conn.commit()
    print("Updated rows:", cur.rowcount)

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()