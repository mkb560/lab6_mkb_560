# lab6_mkb_560
## DrillingEdge Web Scraping & Database Enrichment

### Goal
Enrich each well in MySQL (`oil_wells_db.well_info`) with 5 additional fields scraped from **DrillingEdge**:

- `scraped_well_status`
- `scraped_well_type`
- `scraped_closest_city`
- `scraped_oil_production`
- `scraped_gas_production`

The workflow uses **Selenium** to automate the form-based search (API# → “Search Database” → click result) and uses **requests + BeautifulSoup** to parse the Well Details page efficiently.

---

### Prerequisites
1. **MySQL is running** and the database is loaded:
   - Database: `oil_wells_db`
   - Table: `well_info`
2. Python 3 installed
3. Network access to `https://www.drillingedge.com`

> **Note:** One record may have `api_number = 'N/A'` (missing API). This script excludes it by design.

---

### Python Dependencies
Install dependencies in a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install selenium webdriver-manager requests beautifulsoup4 mysql-connector-python
```

---

### How to Use

From the `oil_well_document_scraper/` directory:

```bash
python scrape_update_all.py
```
This script updates these columns in oil_wells_db.well_info:
scraped_well_status
scraped_well_type
scraped_closest_city
scraped_oil_production
scraped_gas_production

```markdown
**Verify (should be 0):**
```sql
USE oil_wells_db;

SELECT COUNT(*) AS still_NA_status
FROM well_info
WHERE api_number IS NOT NULL
  AND api_number <> ''
  AND UPPER(api_number) <> 'N/A'
  AND scraped_well_status = 'N/A';
