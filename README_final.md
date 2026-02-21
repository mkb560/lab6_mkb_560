# DSCI560 Lab 6 - Oil Wells Data Wrangling

## Collaborative Project: Mingtao Ding (Extraction/Database Design), Yi-Hsien Lou (Scraping/Cleaning), Ke Wu (Frontend/Deployment)

---

## 1. Project Overview

This full-stack data engineering project extracts structured data from **77 scanned oil well PDF files**, enriches the data via web scraping, cleans spatial outliers, and serves an interactive web map via a REST API and an Apache Web Server.

**Pipeline:**

```text
PDF Files → OCR Text Extraction → Regex Parsing → MySQL Storage 
   ↓
DrillingEdge Scraping → MySQL Enrichment
   ↓
Pandas Spatial Cleaning → Database Update
   ↓
Flask REST API (Backend) ↔ Leaflet.js Interactive Map (Frontend / Apache)
```

---

## 2. Data Storage

### 2.1 Raw PDF Files
```
DSCI560_Lab5/                ← 77 PDF files
├── W11745.pdf
├── W11920.pdf
├── W15358.pdf
├── ...
└── W90329.pdf
```

### 2.2 OCR Text Cache
```
ocr_output/                  ← 77 cached text files (avoids re-running OCR)
├── W11745.txt
├── W11920.txt
├── ...
└── W90329.txt
```
Each `.txt` file contains the OCR text from all pages of the corresponding PDF:
```
--- PAGE 1 ---
(text content)

--- PAGE 2 ---
(text content)
...
```

### 2.3 MySQL Database
- **Database**: `oil_wells_db`
- **Connection**: `localhost:3306`, user `root`, password empty
- **Tables**: 2

#### `well_info` Table (77 records — one per well)

| Column | Type | Description | Source |
|--------|------|-------------|--------|
| `id` | INT | Auto-increment PK | Auto |
| `well_file_no` | VARCHAR(20) | Well file number (unique key) | PDF filename |
| `api_number` | VARCHAR(30) | API number (e.g., 33-053-02102) | PDF regex |
| `well_name` | VARCHAR(255) | Well name | PDF regex |
| `operator` | VARCHAR(255) | Operator company | PDF regex |
| `field_name` | VARCHAR(100) | Field/prospect name | PDF regex |
| `location_desc` | VARCHAR(500) | Location description | PDF regex |
| `section` | VARCHAR(20) | Section number | PDF regex |
| `township` | VARCHAR(20) | Township | PDF regex |
| `range_dir` | VARCHAR(20) | Range direction | PDF regex |
| `county` | VARCHAR(100) | County name | PDF regex |
| `state` | VARCHAR(50) | State (default: ND) | PDF regex |
| `latitude` | DECIMAL(10,6) | Latitude | PDF regex |
| `longitude` | DECIMAL(10,6) | Longitude | PDF regex |
| `elevation_gl` | VARCHAR(50) | Ground level elevation | PDF regex |
| `elevation_kb` | VARCHAR(50) | Kelly bushing elevation | PDF regex |
| `spud_date` | VARCHAR(50) | Spud date | PDF regex |
| `completion_date` | VARCHAR(50) | Completion date | PDF regex |
| `well_status` | VARCHAR(100) | Well status (Producing/Flowing/etc.) | PDF regex |
| `well_type` | VARCHAR(100) | Well type | PDF regex |
| `total_depth` | VARCHAR(100) | Total depth | PDF regex |
| `producing_method` | VARCHAR(100) | Producing method (Pumping/Flowing/etc.) | PDF regex |
| `surface_casing` | TEXT | Surface casing info | PDF regex |
| `production_casing` | TEXT | Production casing info | PDF regex |
| `pdf_filename` | VARCHAR(255) | Source PDF filename | Auto |
| `scraped_well_status` | VARCHAR(255) | Scraped well status | Member B |
| `scraped_well_type` | VARCHAR(255) | Scraped well type | Member B |
| `scraped_closest_city` | VARCHAR(255) | Scraped nearest city | Member B |
| `scraped_oil_production` | VARCHAR(255) | Scraped oil production | Member B |
| `scraped_gas_production` | VARCHAR(255) | Scraped gas production | Member B |
| `created_at` | TIMESTAMP | Created timestamp | Auto |
| `updated_at` | TIMESTAMP | Updated timestamp | Auto |

#### `stimulation_data` Table (63 records — fracturing/stimulation treatments)

| Column | Type | Description |
|--------|------|-------------|
| `id` | INT | Auto-increment PK |
| `well_file_no` | VARCHAR(20) | Foreign key → well_info |
| `date_stimulated` | VARCHAR(50) | Stimulation date |
| `stimulated_formation` | VARCHAR(100) | Formation (e.g., Bakken) |
| `top_ft` | VARCHAR(50) | Top depth (ft) |
| `bottom_ft` | VARCHAR(50) | Bottom depth (ft) |
| `stimulation_stages` | VARCHAR(50) | Number of frac stages |
| `volume` | VARCHAR(50) | Fluid volume |
| `volume_units` | VARCHAR(50) | Volume units (Barrels/Gallons) |
| `treatment_type` | VARCHAR(100) | Treatment type |
| `acid_pct` | VARCHAR(50) | Acid percentage |
| `lbs_proppant` | VARCHAR(50) | Proppant weight (lbs) |
| `max_treatment_pressure_psi` | VARCHAR(50) | Max treatment pressure (PSI) |
| `max_treatment_rate_bbls_min` | VARCHAR(50) | Max treatment rate (BBLS/min) |
| `details` | TEXT | Additional details |
| `created_at` | TIMESTAMP | Created timestamp |

### 2.4 Exported Data Files
```
exported_data/
├── oil_wells_db.sql         ← Full SQL dump (schema + data)
├── well_info.csv            ← 77 wells, 31 columns
└── stimulation_data.csv     ← 63 records, 16 columns
```

### 2.5 Log File
```
pipeline.log                 ← Pipeline execution log
```

---

## 3. Code Files

### Mingtao Ding (Extraction/Database design)

#### `config.py` — Global Configuration

Centralized configuration for all parameters:
- PDF directory path (`DSCI560_Lab5/`)
- OCR output directory (`ocr_output/`)
- OCR resolution (150 DPI)
- MySQL connection parameters (host, port, user, password, database)
- Flask API settings (host, port=5001, debug=True)

#### `db_setup.py` — Database Initialization

Creates the MySQL database and tables:
- `create_database()`: Creates `oil_wells_db` database
- `create_tables()`: Creates `well_info` and `stimulation_data` tables
- `reset_tables()`: Drops and recreates tables (for re-running)
- `get_connection()`: Returns a database connection object

Design notes:
- `well_file_no` is a unique key to prevent duplicate inserts
- `stimulation_data` references `well_info` via `well_file_no` foreign key with CASCADE delete
- Reserved `scraped_*` columns for Member B's web-scraped data

#### `pdf_extractor.py` — PDF Text Extraction

Challenge: PDF files are scanned images — text cannot be copied directly.

Solution (hybrid approach):
1. **Try native text extraction first** (PyMuPDF `page.get_text()`) — if the page has embedded text, extract it instantly
2. **Fall back to OCR** (pytesseract at 150 DPI) — if native text < 50 characters, render the page as an image and run Tesseract OCR

Optimizations:
- **Caching**: OCR results saved to `ocr_output/` — subsequent runs read from cache
- **Reduced DPI**: 150 instead of 300, ~2x faster with sufficient accuracy
- **Hybrid extraction**: Pages with native text skip OCR entirely; some PDFs skip up to 85% of pages

#### `data_parser.py` — Regex Parser (Most Complex)

The core of the project (~680 lines). Extracts structured fields from OCR text using 15+ regex-based functions.

| Function | Extracts | Key Challenge |
|----------|----------|---------------|
| `extract_well_file_no()` | Well file number | From filename or "File No" in text |
| `extract_api_number()` | API number | Format XX-XXX-XXXXX; exclude phone numbers |
| `extract_well_name()` | Well name | OCR noise; length limits; prioritize completion report section |
| `extract_operator()` | Operator company | Remove "FROM...TO..." prefixes |
| `extract_field_name()` | Field name | Strip trailing "County"/"Pool" noise |
| `extract_location()` | Location info | 4 sub-fields: Section/Township/Range/County |
| `extract_coordinates()` | Lat/Lon | **Most complex** — DMS / decimal / Site Position formats |
| `extract_elevation()` | Elevation | GL and KB values |
| `extract_dates()` | Dates | Spud date and completion date |
| `extract_well_status()` | Well status | Producing/Flowing/Shut-In/Abandoned |
| `extract_well_type()` | Well type | Oil/Gas |
| `extract_total_depth()` | Total depth | 7 regex patterns for TD/MD/TVD formats |
| `extract_producing_method()` | Producing method | Pumping/Flowing/Gas Lift |
| `extract_casing()` | Casing info | Surface and production casing |
| `extract_stimulation_data()` | Stimulation data | Date/formation/stages/volume/proppant/pressure/rate |

**Coordinate extraction challenges:**
1. Multiple formats across PDFs (DMS vs decimal vs Site Position)
2. OCR misreads (e.g., "ORIGINAL" → "CRIGINAL")
3. Magnetic calibration latitude values that look like real coordinates but are not

**Solution:** Check the 50-character context before each "Latitude" match. Skip if context contains "ORIGINAL" / "RIGINAL" / "CALIBRATION" / "ALIBRATION" / "MAGNETIC".

#### `data_loader.py` — Data Loading

Writes parsed data dicts into MySQL:
- Uses `INSERT ... ON DUPLICATE KEY UPDATE` for idempotent well_info writes
- Uses `COALESCE` to preserve existing non-null values
- Stimulation data: DELETE + INSERT to ensure consistency

#### `preprocess.py` — Data Preprocessing/Cleaning

Post-processing on database records:
- `remove_html_tags()`: Strip residual HTML tags
- `remove_special_chars()`: Remove non-ASCII special characters
- `normalize_api_number()`: Standardize API number format (add hyphens)
- `fill_missing_values()`: Fill empty text fields with "N/A" (lat/lon kept as NULL)
- `clean_all_text_fields()`: Execute all cleaning operations on the database

#### `api_server.py` — Flask REST API

Serves data to Member C's frontend:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/wells` | GET | All wells with basic info (for map markers) |
| `/api/wells/<well_file_no>` | GET | Single well detail + stimulation records |
| `/api/wells/search?q=xxx` | GET | Search by name/API#/county/operator |
| `/api/stats` | GET | Summary statistics |

```bash
python api_server.py
# Visit http://localhost:5001/api/stats
```

CORS enabled for cross-origin frontend requests.

#### `main.py` — Pipeline Orchestrator

Chains all pipeline steps together:

```
Step 1: Create database and tables (db_setup)
Step 2: OCR extract all PDF texts (pdf_extractor)
Step 3: Parse texts to extract structured data (data_parser)
Step 4: Load data into MySQL (data_loader)
Step 5: Preprocess and clean data (preprocess)
```

Usage:
```bash
# Full run (or re-run from scratch)
python main.py --reset

# View database statistics only
python main.py --summary-only
```

---

#### Data Extraction Results

| Metric | Value |
|--------|-------|
| PDFs processed | 77 |
| Wells extracted | 77 (100%) |
| Wells with API number | 76 (98.7%) |
| Wells with coordinates | 59 (76.6%) |
| Wells with status | 38 (49.4%) |
| Wells with total depth | 76 (98.7%) |
| Stimulation records | 63 |
| OCR processing time | ~109 min |
| Re-run time (with cache) | ~9 sec |

---

### Yi-Hsien Lou(Scraping/Cleaning)

#### `scrape_update_all.py` - Data Scrape From https://www.drillingedge.com 

The workflow uses Selenium to automate the form-based search (API# → “Search Database” → click result) and uses requests + BeautifulSoup to parse the Well Details page efficiently.

### Ke Wu (Frontend)

#### `data_optimize.py`- Auto-correct typo in positional data

 Pandas/NumPy script that groups coordinates by county, calculates medians and standard deviations, and applies geographic bounding-box logic to catch and fix severe OCR coordinate typos (e.g., latitudes/longtitudes that is near North Dakota).

 #### `index.html`- Front End based on Leaflet
 
 The frontend user interface. Uses **Leaflet.js** for interactive mapping, a Flexbox layout for the UI, and asynchronous JavaScript `fetch()` to populate clean, unified "Oil Well Info Card" popups.



## 6. Cloud Deployment & Web Server Setup

This project is deployed on a Google Cloud Platform (GCP) Ubuntu Virtual Machine. 

### 6.1 Apache Web Server
* Installed via `sudo apt install apache2`.
* The `index.html` file is hosted in the absolute root web directory: `/var/www/html/`.
* Apache automatically serves the map frontend on default Port 80 to anyone visiting the VM's Public IP.

### 6.2 Firewall & Networking Rules
To allow the frontend and backend to communicate over the public internet, the following rules were established:
1.  **Frontend (HTTP/Port 80):** "Allow HTTP Traffic" enabled in GCP VM settings.
2.  **Backend (Flask/Port 5001):** A custom VPC Firewall Rule (`allow-flask-api`) was created in GCP to allow Ingress TCP traffic on port 5001 from `0.0.0.0/0`.
3.  **UFW (Ubuntu Firewall):** Ports 80 and 5001 explicitly allowed via `sudo ufw allow`.

## 7. How to Run & Deploy

### 7.1 Local Database & Pipeline Execution
```bash
# 1. Activate virtual environment and install requirements
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Run the extraction pipeline
python main.py --reset

# 3. Scraper & Spatial Cleaner
python scrape_update_all.py
python data_optimize.py
```

### 7.2 Cloud Server Deployment
```bash
# 1. Start the Flask API in the background (listen to all IPs)
# Ensure api_server.py has app.run(host="0.0.0.0", port=5001)
python api_server.py

# 2. Update the Frontend IP
# Open index.html and change API_BASE_URL to your VM's Public IP
# Example: const API_BASE_URL = "http://YOUR_PUBLIC_IP:5001/api";

# 3. Deploy to Apache
sudo cp index.html /var/www/html/

# 4. View the Map
# Open a web browser and navigate to: http://YOUR_PUBLIC_IP
```