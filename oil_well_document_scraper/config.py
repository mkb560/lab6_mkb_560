import os

# ----- PDF settings -----
PDF_DIR = os.path.join(os.path.dirname(__file__), "DSCI560_Lab5")
OCR_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "ocr_output")
OCR_DPI = 150

# ----- MySQL settings -----
MYSQL_HOST = "localhost"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = ""
MYSQL_DATABASE = "oil_wells_db"

# ----- Flask API settings -----
API_HOST = "0.0.0.0"
API_PORT = 5001
API_DEBUG = True
