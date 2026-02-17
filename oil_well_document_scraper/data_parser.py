"""
data_parser.py
Parse OCR-extracted text from oil well PDFs to extract structured fields.
Uses regex matching to find API#, well name, operator, location,
coordinates, stimulation data, and other key fields.
"""

import re
import logging
import os

logger = logging.getLogger(__name__)


def _clean(text):
    """Remove extra whitespace and normalize."""
    if text is None:
        return ""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _extract_first(pattern, text, group=1, flags=re.IGNORECASE):
    """Extract the first match of a regex pattern."""
    m = re.search(pattern, text, flags)
    if m:
        return _clean(m.group(group))
    return ""


def _dms_to_decimal(degrees, minutes, seconds, direction):
    """Convert degrees-minutes-seconds to decimal degrees."""
    try:
        d = float(degrees)
        m = float(minutes)
        s = float(seconds)
        decimal = d + m / 60.0 + s / 3600.0
        if direction.upper() in ("S", "W"):
            decimal = -decimal
        return round(decimal, 6)
    except (ValueError, TypeError):
        return None


def extract_well_file_no(text, pdf_filename=""):
    """Extract well file number from text or filename."""
    # Try from filename first (e.g., W11745.pdf -> 11745)
    m = re.match(r"W(\d+)", pdf_filename, re.IGNORECASE)
    if m:
        return m.group(1)

    # Try from text
    patterns = [
        r"Well\s*File\s*(?:No\.?|Number|#)\s*[:.]?\s*(\d+)",
        r"File\s*(?:No\.?|Number|#)\s*[:.]?\s*(\d+)",
        r"ST\s*FILE\s*NO\s*[:.]?\s*(\d+)",
        r"NDIC\s*File\s*Number\s*[:.]?\s*(\d+)",
    ]
    for pat in patterns:
        val = _extract_first(pat, text)
        if val:
            return val
    return ""


def extract_api_number(text):
    """Extract API number (format: 33-053-XXXXX or similar)."""
    patterns = [
        r"API\s*#?\s*[:.]?\s*(33[\-\s]*\d{3}[\-\s]*\d{4,6}[\-\s]*\d{0,2}[\-\s]*\d{0,2})",
        r"API\s*(?:Number|No\.?)\s*[:.]?\s*(33[\-\s]*\d{3}[\-\s]*\d{4,6})",
        r"(33-\d{3}-\d{4,6}(?:-\d{2}(?:-\d{2})?)?)",
    ]
    for pat in patterns:
        val = _extract_first(pat, text)
        if val:
            # Normalize format: 33-053-02102
            val = re.sub(r"\s+", "", val)
            parts = val.split("-")
            if len(parts) >= 3:
                return "-".join(parts[:3])
            return val
    return ""


def extract_well_name(text):
    """Extract well name and number."""
    # Look in the completion report section first
    section = re.search(
        r"(?:WELL\s*COMPLETION|SUNDRY\s*NOTICES).*?Well\s*(?:Name|name)\s*(?:and\s*Number)?\s*[:.]?\s*\n\s*([A-Za-z][A-Za-z0-9\s\-\.\#\&\']+?\d[\w\-]*)",
        text, re.IGNORECASE | re.DOTALL
    )
    if section:
        val = section.group(1)
        val = re.split(r"\s{2,}|\t|\||\n", val)[0]
        val = _clean(val)
        if len(val) > 3 and len(val) < 80:
            return val

    patterns = [
        r"Well\s*Name\s*[:.]?\s*([A-Za-z][A-Za-z0-9\s\-\.\#\&\']{2,40}\d[\w\-]*)",
        r"Well\s*Name\s*(?:and\s*Number)?\s*[:.]?\s*\n\s*([A-Za-z][A-Za-z0-9\s\-\.\#\&\']{2,40}\d[\w\-]*)",
    ]
    for pat in patterns:
        val = _extract_first(pat, text, flags=re.IGNORECASE | re.MULTILINE)
        if val and len(val) > 3 and len(val) < 80:
            val = re.split(r"\s{2,}|\t|\||\n", val)[0]
            return _clean(val)
    return ""


def extract_operator(text):
    """Extract operator name."""
    patterns = [
        r"Well\s*Operator\s*[:.]?\s*([A-Za-z][A-Za-z0-9\s\.,\-\&\']+?(?:Inc|LLC|Corp|Company|Co|LP|Ltd)\.?)",
        r"Operator\s*[:.]?\s*\n?\s*([A-Za-z][A-Za-z0-9\s\.,\-\&\']+?(?:Inc|LLC|Corp|Company|Co|LP|Ltd)\.?)",
        r"Operator\s*(?:Telephone)?\s*(?:Number)?\s*\n\s*([A-Za-z][A-Za-z0-9\s\.,\-\&\']+?(?:Inc|LLC|Corp|Company|Co|LP|Ltd)\.?)",
    ]
    for pat in patterns:
        val = _extract_first(pat, text, flags=re.IGNORECASE | re.MULTILINE)
        if val and len(val) > 3 and len(val) < 120:
            # Remove prefixes like 'FROM' or 'TO'
            val = re.sub(r'^(?:FROM|TO)\s+', '', val, flags=re.IGNORECASE)
            return _clean(val)
    return ""


def extract_field_name(text):
    """Extract field/prospect name."""
    patterns = [
        r"Field\s*Name\s*[:.]?\s*([A-Za-z][A-Za-z\s\-]{1,30})",
        r"Field/?\s*Prospect\s*[:.]?\s*([A-Za-z][A-Za-z\s\-]{1,30})",
        r"Field\s*[:.]?\s*\n\s*([A-Z][A-Z\s\-]{1,30})",
        r"\|\s*Field\s*\n\s*([A-Z][A-Z\s\-]{1,20})",
    ]
    for pat in patterns:
        val = _extract_first(pat, text, flags=re.IGNORECASE | re.MULTILINE)
        if val and len(val) > 1 and len(val) < 40:
            val = re.split(r"\s{2,}|\t|\||\n", val)[0]
            # Remove trailing words like 'County', 'Pool'
            val = re.sub(r'\s*(?:County|Pool|Address|Telephone).*$', '', val, flags=re.IGNORECASE)
            return _clean(val)
    return ""


def extract_location(text):
    """Extract location description (section, township, range, county)."""
    result = {
        "location_desc": "",
        "section": "",
        "township": "",
        "range_dir": "",
        "county": "",
    }

    # Pattern: LOCATION: SURF:SWSW SEC 2 153N 101W, MCKENZIE CO, ND
    m = re.search(
        r"LOCATION\s*[:.]?\s*(?:SURF\s*[:.]?)?\s*[A-Z]{2,4}\s*"
        r"(?:SEC\.?|Section)\s*(\d+)\s*[,\s]*"
        r"T?(\d+)\s*N\s*[,\s]*R?(\d+)\s*W"
        r"[,\s]*([A-Za-z]+)\s*(?:CO|County)",
        text, re.IGNORECASE
    )
    if m:
        result["location_desc"] = _clean(m.group(0))
        result["section"] = m.group(1)
        result["township"] = m.group(2) + "N"
        result["range_dir"] = m.group(3) + "W"
        result["county"] = _clean(m.group(4))
        return result

    # Pattern: SWSW|12|153|101 w |McKenzie (table-like)
    m = re.search(
        r"LOCATION\s*(?:OF\s*WELL)?[^\n]*\n[^\n]*?"
        r"[NESW]{2,4}\s*[|\s]\s*(\d+)\s*[|\s]\s*(\d+)\s*[|\s]\s*(\d+)\s*(?:[wW])?\s*[|\s]\s*([A-Za-z]+)",
        text, re.IGNORECASE
    )
    if m:
        result["section"] = m.group(1)
        result["township"] = m.group(2) + "N"
        result["range_dir"] = m.group(3) + "W"
        result["county"] = _clean(m.group(4))
        result["location_desc"] = _clean(m.group(0))
        return result

    # Pattern: SW NW Sec. 30, T153N, R100W, McKenzie County
    m = re.search(
        r"([NESW]{2,4})\s*(?:SEC\.?|Section)\s*(\d+)\s*[,\s]*"
        r"T(\d+)\s*N?\s*[,\s\-]*R(\d+)\s*W"
        r"(?:[,\s]*([A-Za-z]+)\s*(?:County)?)?",
        text, re.IGNORECASE
    )
    if m:
        result["location_desc"] = _clean(m.group(0))
        result["section"] = m.group(2)
        result["township"] = m.group(3) + "N"
        result["range_dir"] = m.group(4) + "W"
        if m.group(5):
            result["county"] = _clean(m.group(5))
        return result

    # Pattern from footages: 153 N 101 W
    m = re.search(
        r"(\d+)\s*N\s+(\d+)\s*W",
        text, re.IGNORECASE
    )
    if m:
        result["township"] = m.group(1) + "N"
        result["range_dir"] = m.group(2) + "W"

    # County
    m = re.search(
        r"(?:County|Co\.?)\s*[:.]?\s*([A-Za-z]+)",
        text, re.IGNORECASE
    )
    if m:
        result["county"] = _clean(m.group(1))

    # Section
    m = re.search(r"Section\s*[:.]?\s*(\d+)", text, re.IGNORECASE)
    if m:
        result["section"] = m.group(1)

    return result


def extract_coordinates(text):
    """Extract latitude and longitude from text."""
    lat = None
    lon = None

    # DMS format: Latitude: 48deg 4' 58.501" N
    # Match patterns like: 48  4' 58.501 N or 48 deg 4' 58.501" N
    lat_m = re.search(
        r"Latitude\s*[:.]?\s*(\d{2})\s*[^0-9\n]{1,5}\s*(\d{1,2})\s*['\x27\x60]\s*"
        r"(\d{1,2}\.?\d*)\s*[\"'\x22]?\s*([NS])",
        text, re.IGNORECASE
    )
    lon_m = re.search(
        r"Longitude\s*[:.]?\s*(\d{2,3})\s*[^0-9\n]{1,5}\s*(\d{1,2})\s*['\x27\x60]\s*"
        r"(\d{1,2}\.?\d*)\s*[\"'\x22]?\s*([EW])",
        text, re.IGNORECASE
    )

    if lat_m:
        lat = _dms_to_decimal(
            lat_m.group(1), lat_m.group(2),
            lat_m.group(3), lat_m.group(4)
        )
    if lon_m:
        lon = _dms_to_decimal(
            lon_m.group(1), lon_m.group(2),
            lon_m.group(3), lon_m.group(4)
        )

    # Decimal degrees: Latitude: 48.083472 (must have 4+ decimal digits)
    # Exclude calibration/magnetic latitude values
    if lat is None:
        for m in re.finditer(
            r"Latitude\s*[:.]?\s*([\-]?\d{2}\.\d{4,})\s*([NS])?",
            text, re.IGNORECASE
        ):
            # Skip if preceded by ORIGINAL, CALIBRATION, or CHANGE
            start = max(0, m.start() - 50)
            context = text[start:m.start()].upper()
            if any(w in context for w in ["ORIGINAL", "RIGINAL", "CALIBRATION", "ALIBRATION", "CHANGE", "BASED ON", "MAGNETIC"]):
                continue
            lat = float(m.group(1))
            if m.group(2) and m.group(2).upper() == "S":
                lat = -lat
            break

    if lon is None:
        for m in re.finditer(
            r"Longitude\s*[:.]?\s*([\-]?\d{2,3}\.\d{4,})\s*([EW])?",
            text, re.IGNORECASE
        ):
            start = max(0, m.start() - 50)
            context = text[start:m.start()].upper()
            if any(w in context for w in ["ORIGINAL", "RIGINAL", "CALIBRATION", "ALIBRATION", "CHANGE", "BASED ON", "MAGNETIC"]):
                continue
            lon = float(m.group(1))
            if m.group(2) and m.group(2).upper() == "W":
                lon = -abs(lon)
            break

    # Try Site Position format: Northing: ... Latitude: 48deg... N \n ... Longitude: 102deg... W
    if lat is None and lon is None:
        m = re.search(
            r"Site\s*Position.*?Latitude\s*[:.]?\s*(\d{2})\s*[^0-9\n]{1,5}\s*"
            r"(\d{1,2})\s*['\x27\x60]\s*(\d{1,2}\.?\d*)\s*[\"'\x22]?\s*([NS])",
            text, re.IGNORECASE | re.DOTALL
        )
        if m:
            lat = _dms_to_decimal(m.group(1), m.group(2), m.group(3), m.group(4))

        m = re.search(
            r"Site\s*Position.*?Longitude\s*[:.]?\s*(\d{2,3})\s*[^0-9\n]{1,5}\s*"
            r"(\d{1,2})\s*['\x27\x60]\s*(\d{1,2}\.?\d*)\s*[\"'\x22]?\s*([EW])",
            text, re.IGNORECASE | re.DOTALL
        )
        if m:
            lon = _dms_to_decimal(m.group(1), m.group(2), m.group(3), m.group(4))

    return lat, lon


def extract_elevation(text):
    """Extract ground level and KB elevation."""
    gl = _extract_first(
        r"(?:GL|Ground\s*Level)\s*[-:.]?\s*([\d,]+(?:\.\d+)?)\s*'?\s*(?:ft)?",
        text
    )
    kb = _extract_first(
        r"(?:KB|Kelly\s*Bushing)\s*[-:.]?\s*([\d,]+(?:\.\d+)?)\s*'?\s*(?:ft)?",
        text
    )
    # Also try: Elevation: GL - 1850' KB - 1872'
    m = re.search(
        r"ELEVATION\s*[:.]?\s*GL\s*[-:.]?\s*([\d,]+)'?\s*KB\s*[-:.]?\s*([\d,]+)",
        text, re.IGNORECASE
    )
    if m:
        gl = gl or m.group(1)
        kb = kb or m.group(2)
    return gl, kb


def extract_dates(text):
    """Extract spud date and completion date."""
    spud = _extract_first(
        r"Spud\s*Date\s*[:.]?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\w+\s+\d{1,2},?\s*\d{4})",
        text
    )
    comp = _extract_first(
        r"(?:Comp(?:letion)?\s*Date|COMP\s*DATE|Date\s*Well\s*Completed)\s*[:.]?\s*"
        r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|\w+\s+\d{1,2},?\s*\d{4})",
        text
    )
    return spud, comp


def extract_well_status(text):
    """Extract well status."""
    # Look for explicit status keywords near "Status" label
    m = re.search(
        r"(?:We[il]l\s+)?Status\s*(?:\(Producing\s+or\s+Shut.In\))?\s*[:.]?\s*\n?\s*"
        r"((?:Producing|Shut.?In|Abandoned|Active|Pumping|Flowing|Inactive|Temporarily\s+Abandoned)"
        r"(?:\s+(?:Oil|Gas|Water)\s+Well)?)",
        text, re.IGNORECASE
    )
    if m:
        return _clean(m.group(1))

    # Status on a line after date + method (common layout in completion reports)
    m = re.search(
        r"(?:We[il]l\s+)?Status\s*\(Producing\s+or\s+Shut.In\)\s*\n"
        r".*?(Producing|Shut.?In|Abandoned|Pumping|Flowing|Inactive)",
        text, re.IGNORECASE
    )
    if m:
        return _clean(m.group(1))

    # PRESENT STATUS or STATUS OF WELL
    m = re.search(
        r"(?:PRESENT\s+)?STATUS\s*(?:OF\s*WELL)?\s*[:.]?\s*"
        r"(PUMPING\s+OIL\s+WELL|FLOWING|SHUT.?IN|ABANDONED|PRODUCING|ACTIVE|INACTIVE)",
        text, re.IGNORECASE
    )
    if m:
        return _clean(m.group(1))
    return ""


def extract_well_type(text):
    """Extract well type."""
    val = _extract_first(
        r"Well\s*Type\s*[:.]?\s*([A-Za-z][A-Za-z\s\-]{2,40})",
        text
    )
    if val:
        val = re.split(r"\s{3,}|\t|\n", val)[0]
        # Only keep meaningful types
        if len(val) < 60:
            return _clean(val)
    return ""


def extract_total_depth(text):
    """Extract total depth."""
    patterns = [
        r"ROTARY\s*TD\s*[:.]?\s*([\d,]+'?\s*(?:TVD|TMD|MD)?(?:\s*[/,]\s*[\d,]+'?\s*(?:TVD|TMD|MD)?)?)",
        r"Total\s*depth\s*changed\s*to\s*[:.]?\s*([\d,]+'?\s*(?:MD|TVD)?(?:\s*[/,]\s*[\d,]+'?\s*(?:TVD|TMD|MD)?)?)",
        r"Total\s*Depth\s*of\s*([\d,]+'?\s*(?:ft|feet|TVD|TMD|MD)?)",
        r"Total\s*Depth\s*/?\s*Date\s*[:.]?\s*\n?\s*([\d,]+)",
        r"Total\s*Depth\s*[:.]?\s*([\d,]+)\s*'?\s*(?:ft|TVD|TMD|MD)?",
        r"drilled\s+to\s+a?\s*total\s+depth.*?of\s+([\d,]+'?)\s*(?:ft|feet|TVD)?",
        r"(?:TD|total\s*depth)\s*(?:of|was|is|at)?\s*([\d,]+)\s*'?\s*(?:ft|TVD|MD)?",
    ]
    for pat in patterns:
        val = _extract_first(pat, text)
        if val and re.search(r'\d', val):
            return _clean(val)
    return ""


def extract_producing_method(text):
    """Extract producing method."""
    m = re.search(
        r"Producing\s*Method\s*[:.]?\s*"
        r"(?:\([^)]*\)\s*)?"
        r"(Flowing|Pumping|Gas\s*Lift|Rod\s*Pump|ESP|Plunger)",
        text, re.IGNORECASE
    )
    if m:
        return _clean(m.group(1))
    return ""


def extract_casing(text):
    """Extract surface and production casing info."""
    surf = _extract_first(
        r"SURF(?:ACE)?\s*C(?:A)?SG\s*[:.]?\s*(.+?)(?:\n|$)",
        text, flags=re.IGNORECASE | re.MULTILINE
    )
    if not surf:
        # Try: Surface: 9 5/8" ... @ depth
        surf = _extract_first(
            r"Surface\s*[:.]?\s*(\d[^\n]{10,80})",
            text, flags=re.IGNORECASE | re.MULTILINE
        )
    prod = _extract_first(
        r"PROD(?:UCTION)?\s*C(?:A)?SG\s*[:.]?\s*(.+?)(?:\n|$)",
        text, flags=re.IGNORECASE | re.MULTILINE
    )
    return _clean(surf)[:200], _clean(prod)[:200]


def extract_stimulation_data(text):
    """
    Extract stimulation data from the 'Well Specific Stimulations' section.
    Returns a list of dicts with stimulation info.
    """
    stim_records = []

    # Look for the stimulation section
    stim_section = re.search(
        r"Well\s*Specific\s*Stimulations?\s*(.*?)(?:ADDITIONAL\s*INFORMATION|"
        r"hereby\s*swear|Page\s*\d|SFN\s*\d|$)",
        text, re.IGNORECASE | re.DOTALL
    )

    if not stim_section:
        # Try alternative patterns for stimulation data
        stim_section = re.search(
            r"(?:PERFORATION\s*RECORD|Acid,\s*Frac)(.*?)(?:PRODUCTION|Date.+?First\s*Production)",
            text, re.IGNORECASE | re.DOTALL
        )

    if not stim_section:
        return stim_records

    section_text = stim_section.group(1)

    # Pattern 1: structured stimulation table
    # Date Stimulated | Formation | Top | Bottom | Stages | Volume | Units
    # Type Treatment | Acid% | Lbs Proppant | Max Pressure | Max Rate
    blocks = re.split(
        r"Date\s*Stimulated",
        section_text, flags=re.IGNORECASE
    )

    for block in blocks[1:]:  # skip first empty split
        if not block.strip():
            continue

        record = {
            "date_stimulated": "",
            "stimulated_formation": "",
            "top_ft": "",
            "bottom_ft": "",
            "stimulation_stages": "",
            "volume": "",
            "volume_units": "",
            "treatment_type": "",
            "acid_pct": "",
            "lbs_proppant": "",
            "max_treatment_pressure_psi": "",
            "max_treatment_rate_bbls_min": "",
            "details": "",
        }

        # Date
        m = re.search(
            r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})",
            block
        )
        if m:
            record["date_stimulated"] = m.group(1)

        # Formation
        m = re.search(
            r"(?:Formation)?\s*(?:Top)?\s*\n?\s*([A-Za-z][A-Za-z\s]+?)\s+(\d+)\s+(\d+)",
            block, re.IGNORECASE
        )
        if m:
            record["stimulated_formation"] = _clean(m.group(1))
            record["top_ft"] = m.group(2)
            record["bottom_ft"] = m.group(3)

        # Stages
        m = re.search(r"(\d+)\s+(\d+)\s+(Barrels|Gallons|BBL)", block, re.IGNORECASE)
        if m:
            record["stimulation_stages"] = m.group(1)
            record["volume"] = m.group(2)
            record["volume_units"] = m.group(3)

        # Treatment type
        m = re.search(
            r"(Sand\s*Frac|Acid\s*Frac|Acid|Fracture|Frac|Hydraulic)",
            block, re.IGNORECASE
        )
        if m:
            record["treatment_type"] = _clean(m.group(1))

        # Acid %
        m = re.search(r"Acid\s*%?\s*[:.]?\s*([\d.]+)", block, re.IGNORECASE)
        if m:
            record["acid_pct"] = m.group(1)

        # Lbs Proppant
        m = re.search(r"(?:Lbs\s*)?Proppant\s*[:.]?\s*([\d,]+)", block, re.IGNORECASE)
        if not m:
            m = re.search(r"([\d,]+)\s+(?:\d+)\s+[\d.]+\s*$", block, re.MULTILINE)
        if m:
            record["lbs_proppant"] = m.group(1).replace(",", "")

        # Max pressure
        m = re.search(
            r"(?:Maximum\s*)?(?:Treatment\s*)?Pressure\s*(?:\(PSI\))?\s*[:.]?\s*([\d,]+)",
            block, re.IGNORECASE
        )
        if not m:
            # Try getting the number after proppant in the table row
            m2 = re.search(
                r"(?:Sand\s*Frac|Acid|Frac)\s+(?:[\d.]+\s+)?([\d,]+)\s+([\d,]+)\s+([\d.]+)",
                block, re.IGNORECASE
            )
            if m2:
                record["lbs_proppant"] = record["lbs_proppant"] or m2.group(1).replace(",", "")
                record["max_treatment_pressure_psi"] = m2.group(2)
                record["max_treatment_rate_bbls_min"] = m2.group(3)
        else:
            record["max_treatment_pressure_psi"] = m.group(1).replace(",", "")

        # Max rate
        if not record["max_treatment_rate_bbls_min"]:
            m = re.search(
                r"(?:Maximum\s*)?(?:Treatment\s*)?Rate\s*(?:\(BBLS/Min\))?\s*[:.]?\s*([\d.]+)",
                block, re.IGNORECASE
            )
            if m:
                record["max_treatment_rate_bbls_min"] = m.group(1)

        # Details - additional proppant breakdown
        details_parts = []
        for dm in re.finditer(
            r"(\d+(?:/\d+)?\s+(?:Mesh|White|Ceramic|Sand|Resin)\s*[:.]?\s*[\d,]+)",
            block, re.IGNORECASE
        ):
            details_parts.append(_clean(dm.group(1)))
        if details_parts:
            record["details"] = "; ".join(details_parts)

        # Only add if we got at least some data
        has_data = any(
            v for k, v in record.items()
            if k != "details" and v
        )
        if has_data:
            stim_records.append(record)

    # If no structured stim data found, try to parse from DETAILS OF WORK section
    if not stim_records:
        acid_m = re.search(
            r"Acidiz\w*\s+(?:open\s+hole\s+)?(?:section\s+)?w/?\s*"
            r"(\d+)\s*gal\s+([\d.]+%?\s*HCl?)",
            text, re.IGNORECASE
        )
        if acid_m:
            record = {
                "date_stimulated": "",
                "stimulated_formation": "",
                "top_ft": "",
                "bottom_ft": "",
                "stimulation_stages": "",
                "volume": acid_m.group(1),
                "volume_units": "Gallons",
                "treatment_type": "Acid",
                "acid_pct": acid_m.group(2),
                "lbs_proppant": "",
                "max_treatment_pressure_psi": "",
                "max_treatment_rate_bbls_min": "",
                "details": "",
            }
            stim_records.append(record)

    return stim_records


def parse_well_pdf(text, pdf_filename=""):
    """
    Parse the full OCR text from a well PDF and return a dict
    with well_info fields and a list of stimulation records.
    """
    well_file_no = extract_well_file_no(text, pdf_filename)

    api = extract_api_number(text)
    well_name = extract_well_name(text)
    operator = extract_operator(text)
    field_name = extract_field_name(text)
    location = extract_location(text)
    lat, lon = extract_coordinates(text)
    gl, kb = extract_elevation(text)
    spud, comp = extract_dates(text)
    status = extract_well_status(text)
    well_type = extract_well_type(text)
    td = extract_total_depth(text)
    prod_method = extract_producing_method(text)
    surf_csg, prod_csg = extract_casing(text)
    stim_data = extract_stimulation_data(text)

    well_info = {
        "well_file_no": well_file_no,
        "api_number": api,
        "well_name": well_name,
        "operator": operator,
        "field_name": field_name,
        "location_desc": location.get("location_desc", ""),
        "section": location.get("section", ""),
        "township": location.get("township", ""),
        "range_dir": location.get("range_dir", ""),
        "county": location.get("county", ""),
        "state": "ND",
        "latitude": lat,
        "longitude": lon,
        "elevation_gl": gl,
        "elevation_kb": kb,
        "spud_date": spud,
        "completion_date": comp,
        "well_status": status,
        "well_type": well_type,
        "total_depth": td,
        "producing_method": prod_method,
        "surface_casing": surf_csg,
        "production_casing": prod_csg,
        "pdf_filename": pdf_filename,
    }

    return well_info, stim_data


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1:
        txt_file = sys.argv[1]
        with open(txt_file, "r", encoding="utf-8") as f:
            text = f.read()

        fname = os.path.basename(txt_file).replace(".txt", ".pdf")
        info, stims = parse_well_pdf(text, fname)

        print("=== Well Info ===")
        for k, v in info.items():
            print(f"  {k}: {v}")

        print(f"\n=== Stimulation Records ({len(stims)}) ===")
        for i, s in enumerate(stims):
            print(f"  Record {i + 1}:")
            for k, v in s.items():
                if v:
                    print(f"    {k}: {v}")
