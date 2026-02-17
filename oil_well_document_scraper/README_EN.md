# DSCI560 Lab 6 - Oil Wells Data Wrangling

## Member A: PDF Extraction + Database Design

---

## 1. Project Overview

This project extracts structured data from **77 scanned oil well PDF files** provided by the North Dakota Industrial Commission using OCR + regex parsing, stores the results in a MySQL database, and serves them via a Flask REST API for the frontend (Member C).

**Pipeline:**

```
PDF Files → OCR Text Extraction → Regex Parsing → MySQL Storage → Data Cleaning → REST API
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

### 3.1 `config.py` — Global Configuration

Centralized configuration for all parameters:
- PDF directory path (`DSCI560_Lab5/`)
- OCR output directory (`ocr_output/`)
- OCR resolution (150 DPI)
- MySQL connection parameters (host, port, user, password, database)
- Flask API settings (host, port=5001, debug=True)

### 3.2 `db_setup.py` — Database Initialization

Creates the MySQL database and tables:
- `create_database()`: Creates `oil_wells_db` database
- `create_tables()`: Creates `well_info` and `stimulation_data` tables
- `reset_tables()`: Drops and recreates tables (for re-running)
- `get_connection()`: Returns a database connection object

Design notes:
- `well_file_no` is a unique key to prevent duplicate inserts
- `stimulation_data` references `well_info` via `well_file_no` foreign key with CASCADE delete
- Reserved `scraped_*` columns for Member B's web-scraped data

### 3.3 `pdf_extractor.py` — PDF Text Extraction

Challenge: PDF files are scanned images — text cannot be copied directly.

Solution (hybrid approach):
1. **Try native text extraction first** (PyMuPDF `page.get_text()`) — if the page has embedded text, extract it instantly
2. **Fall back to OCR** (pytesseract at 150 DPI) — if native text < 50 characters, render the page as an image and run Tesseract OCR

Optimizations:
- **Caching**: OCR results saved to `ocr_output/` — subsequent runs read from cache
- **Reduced DPI**: 150 instead of 300, ~2x faster with sufficient accuracy
- **Hybrid extraction**: Pages with native text skip OCR entirely; some PDFs skip up to 85% of pages

### 3.4 `data_parser.py` — Regex Parser (Most Complex)

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

### 3.5 `data_loader.py` — Data Loading

Writes parsed data dicts into MySQL:
- Uses `INSERT ... ON DUPLICATE KEY UPDATE` for idempotent well_info writes
- Uses `COALESCE` to preserve existing non-null values
- Stimulation data: DELETE + INSERT to ensure consistency

### 3.6 `preprocess.py` — Data Preprocessing/Cleaning

Post-processing on database records:
- `remove_html_tags()`: Strip residual HTML tags
- `remove_special_chars()`: Remove non-ASCII special characters
- `normalize_api_number()`: Standardize API number format (add hyphens)
- `fill_missing_values()`: Fill empty text fields with "N/A" (lat/lon kept as NULL)
- `clean_all_text_fields()`: Execute all cleaning operations on the database

### 3.7 `api_server.py` — Flask REST API

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

### 3.8 `main.py` — Pipeline Orchestrator

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

## 4. Results

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

## 5. Interface for Member B (Web Scraping)

Member B is responsible for web scraping. The `well_info` table has 5 reserved columns:

```sql
UPDATE well_info SET
  scraped_well_status = '...',
  scraped_well_type = '...',
  scraped_closest_city = '...',
  scraped_oil_production = '...',
  scraped_gas_production = '...'
WHERE well_file_no = '22099';
```

Database connection:
```python
import mysql.connector
conn = mysql.connector.connect(
    host="localhost", port=3306,
    user="root", password="",
    database="oil_wells_db"
)
```

---

## 6. Interface for Member C (Frontend)

Member C is responsible for frontend visualization. Start the API server and call:

```bash
python api_server.py

GET http://localhost:5001/api/wells              # All wells (map markers)
GET http://localhost:5001/api/wells/22099         # Single well detail
GET http://localhost:5001/api/wells/search?q=Oasis  # Search
GET http://localhost:5001/api/stats               # Statistics
```

CORS is enabled — frontend can make cross-origin requests directly.

---

## 7. How to Re-run

```bash
# 1. Enter project directory
cd DSCI560-Lab6-Oil-Wells

# 2. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Make sure MySQL is running and Tesseract is installed
#    brew install tesseract   (macOS)

# 5. Run the pipeline (with OCR cache: ~9 seconds)
python main.py --reset

# 6. Start the API server
python api_server.py
```
