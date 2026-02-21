# DSCI560 Lab 6 - Oil Wells Data Wrangling & Visualization

## Collaborative Project: Mingtao Ding (Extraction/Database Design), Yi-Hsien Liu (Scraping/Cleaning), Ke Wu (Frontend/Deployment)

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

### 2.1 Raw PDF Files & OCR Cache
* **PDFs:** 77 well files provided by the North Dakota Industrial Commission.
* **OCR Cache:** Cached `.txt` files to avoid re-running Tesseract OCR (reduces run time from ~109 min to ~9 sec).

### 2.2 MySQL Database (`oil_wells_db`)
* **`well_info` Table (77 records):** Contains PDF-extracted data (API number, location, dates, casing) and Scraped data (Status, Type, City, Production).
* **`stimulation_data` Table (63 records):** Contains fracturing/treatment data linked by `well_file_no`.

---

## 3. Code Architecture

### Member A: Extraction & Database Setup
* `config.py`: Global configuration (paths, DB credentials, API ports).
* `db_setup.py`: Idempotent MySQL database and table initialization.
* `pdf_extractor.py`: Hybrid PyMuPDF / pytesseract (150 DPI) text extraction.
* `data_parser.py`: Complex regex parsing for 15+ fields (coordinates, casing, depths).
* `data_loader.py`: Safe MySQL insertion (`ON DUPLICATE KEY UPDATE`).
* `preprocess.py`: Text normalization and missing-value handling.

### Member B: Scraping & Data Cleaning
* `scrape_update_all.py`: Selenium + BeautifulSoup script that searches DrillingEdge using the extracted API numbers and updates the database with 5 new columns (Status, Type, City, Oil/Gas Production).
* `fix_outliers_pandas.py`: Pandas/NumPy script that groups coordinates by county, calculates medians and standard deviations, and applies geographic bounding-box logic to catch and fix severe OCR coordinate typos (e.g., negative latitudes).

### Member C: API, Frontend, & Deployment
* `api_server.py`: Flask REST API serving JSON endpoints with CORS enabled. Modified to run on `host="0.0.0.0"` to accept external cloud traffic.
* `index.html`: The frontend user interface. Uses **Leaflet.js** for interactive mapping, a Flexbox layout for the UI, and asynchronous JavaScript `fetch()` to populate clean, unified "Info Card" popups.

---

## 4. Extraction & Enrichment Results

| Metric | Value |
|--------|-------|
| PDFs processed / Wells extracted | 77 (100%) |
| Wells with API number | 76 (98.7%) |
| Valid Coordinates Mapped | 59 (76.6%) |
| Wells Scraped Successfully | 76 |
| Stimulation records | 63 |

---

## 5. Frontend Implementation (Member C)

The frontend is a single-page HTML application (`index.html`) featuring:
* **Leaflet.js Mapping:** Renders OpenStreetMap base tiles and plots well markers using valid coordinates (`latitude IS NOT NULL`).
* **Lazy-Loading Popups:** Bypasses Leaflet double-click bugs by using the native `popupopen` event to fetch data from the Flask API only when a user clicks a pin.
* **Data Formatting:** Automatically converts database `N/A` values to `Not Available`, filters out empty "ghost" stimulation records, and merges Member A and Member B's data into a single, seamless Info Card.

---

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

---

## 7. How to Run & Deploy

### 7.1 Local Database & Pipeline Execution
```bash
# 1. Activate virtual environment and install requirements
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Run the extraction pipeline
python main.py --reset

# 3. Run Member B's Scraper & Spatial Cleaner
python scrape_update_all.py
python fix_outliers_pandas.py
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