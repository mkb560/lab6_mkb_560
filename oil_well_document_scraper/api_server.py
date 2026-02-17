"""
api_server.py
Flask API server for serving well data to the frontend (Member C).
Provides REST endpoints to query well info and stimulation data.
"""

import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from db_setup import get_connection
import config

app = Flask(__name__)
CORS(app)

logger = logging.getLogger(__name__)


@app.route("/api/wells", methods=["GET"])
def get_all_wells():
    """Get all wells with basic info for map markers."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, well_file_no, api_number, well_name, operator,
               field_name, county, state, latitude, longitude,
               well_status, well_type, scraped_well_status,
               scraped_well_type, scraped_closest_city
        FROM well_info
        ORDER BY well_file_no
    """)
    wells = cursor.fetchall()

    # Convert Decimal to float for JSON serialization
    for w in wells:
        if w.get("latitude") is not None:
            w["latitude"] = float(w["latitude"])
        if w.get("longitude") is not None:
            w["longitude"] = float(w["longitude"])

    cursor.close()
    conn.close()
    return jsonify({"status": "ok", "count": len(wells), "data": wells})


@app.route("/api/wells/<well_file_no>", methods=["GET"])
def get_well_detail(well_file_no):
    """Get full details for a single well including stimulation data."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Well info
    cursor.execute(
        "SELECT * FROM well_info WHERE well_file_no = %s",
        (well_file_no,)
    )
    well = cursor.fetchone()

    if not well:
        cursor.close()
        conn.close()
        return jsonify({"status": "error", "message": "Well not found"}), 404

    # Convert Decimal to float
    if well.get("latitude") is not None:
        well["latitude"] = float(well["latitude"])
    if well.get("longitude") is not None:
        well["longitude"] = float(well["longitude"])

    # Convert datetime fields to string
    for key in ["created_at", "updated_at"]:
        if well.get(key):
            well[key] = str(well[key])

    # Stimulation data
    cursor.execute(
        "SELECT * FROM stimulation_data WHERE well_file_no = %s",
        (well_file_no,)
    )
    stim_records = cursor.fetchall()
    for s in stim_records:
        if s.get("created_at"):
            s["created_at"] = str(s["created_at"])

    cursor.close()
    conn.close()

    return jsonify({
        "status": "ok",
        "well_info": well,
        "stimulation_data": stim_records,
    })


@app.route("/api/wells/search", methods=["GET"])
def search_wells():
    """Search wells by name, API number, or county."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"status": "error", "message": "Query parameter 'q' is required"}), 400

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    search_pattern = f"%{query}%"
    cursor.execute("""
        SELECT id, well_file_no, api_number, well_name, operator,
               county, latitude, longitude
        FROM well_info
        WHERE well_name LIKE %s
           OR api_number LIKE %s
           OR county LIKE %s
           OR operator LIKE %s
        ORDER BY well_file_no
    """, (search_pattern, search_pattern, search_pattern, search_pattern))

    wells = cursor.fetchall()
    for w in wells:
        if w.get("latitude") is not None:
            w["latitude"] = float(w["latitude"])
        if w.get("longitude") is not None:
            w["longitude"] = float(w["longitude"])

    cursor.close()
    conn.close()
    return jsonify({"status": "ok", "count": len(wells), "data": wells})


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Get summary statistics."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT COUNT(*) as total_wells FROM well_info")
    total = cursor.fetchone()["total_wells"]

    cursor.execute(
        "SELECT COUNT(*) as with_coords FROM well_info "
        "WHERE latitude IS NOT NULL"
    )
    with_coords = cursor.fetchone()["with_coords"]

    cursor.execute("SELECT COUNT(*) as total_stim FROM stimulation_data")
    total_stim = cursor.fetchone()["total_stim"]

    cursor.execute(
        "SELECT COUNT(*) as scraped FROM well_info "
        "WHERE scraped_well_status IS NOT NULL AND scraped_well_status != '' "
        "AND scraped_well_status != 'N/A'"
    )
    scraped = cursor.fetchone()["scraped"]

    cursor.close()
    conn.close()

    return jsonify({
        "status": "ok",
        "total_wells": total,
        "wells_with_coordinates": with_coords,
        "total_stimulation_records": total_stim,
        "wells_with_scraped_data": scraped,
    })


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )
    app.run(
        host=config.API_HOST,
        port=config.API_PORT,
        debug=config.API_DEBUG
    )
