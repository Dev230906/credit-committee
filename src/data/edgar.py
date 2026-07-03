import os
import re
from sec_edgar_downloader import Downloader
from dotenv import load_dotenv

load_dotenv()

USER_EMAIL = os.getenv("USER_EMAIL", "your_email@gmail.com")


def extract_text_from_filing(file_path: str) -> dict:
    """
    Extracts readable text sections from a raw SEC filing.
    Strips XBRL/HTML tags and returns clean text for key sections.

    Input: file_path (str) — path to full-submission.txt
    Output: dict with keys:
        - full_text: str (first 500k chars of cleaned text)
        - mda: str (Management Discussion & Analysis)
        - risk_factors: str (Risk Factors section)
        - status: dict
    """

    result = {
        "full_text": None,
        "mda": None,
        "risk_factors": None,
        "status": {}
    }

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            raw = f.read()

        # --- Strip HTML/XBRL tags ---
        clean = re.sub(r'<script[^>]*>.*?</script>', ' ', raw, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<style[^>]*>.*?</style>', ' ', clean, flags=re.DOTALL | re.IGNORECASE)
        clean = re.sub(r'<[^>]+>', ' ', clean)
        clean = re.sub(r'&[a-zA-Z#0-9]+;', ' ', clean)
        clean = re.sub(r'\s+', ' ', clean)

        result["status"]["total_chars"] = len(clean)

        # --- Extract MD&A ---
        mda_matches = list(re.finditer(
            r'item\s*7[\.\s]*management.{0,50}discussion',
            clean,
            flags=re.IGNORECASE
        ))

        if len(mda_matches) >= 2:
            start_pos = mda_matches[1].start()
            search_from = start_pos + 5_000
            end_match = re.search(
                r'item\s*7a[\.\s]*quantitative|item\s*8[\.\s]*financial\s*statements',
                clean[search_from:],
                flags=re.IGNORECASE
            )
            if end_match:
                end_pos = search_from + end_match.start()
                result["mda"] = clean[start_pos:end_pos][:80_000]
            else:
                result["mda"] = clean[start_pos:start_pos + 80_000]
            result["status"]["mda_found"] = True

        elif len(mda_matches) == 1:
            start_pos = mda_matches[0].start()
            result["mda"] = clean[start_pos:start_pos + 80_000]
            result["status"]["mda_found"] = True
            result["status"]["mda_warning"] = "Only one match — may be TOC"
        else:
            result["status"]["mda_found"] = False

        # --- Extract Risk Factors ---
        risk_matches = list(re.finditer(
            r'item\s*1a[\.\s]*risk\s*factors',
            clean,
            flags=re.IGNORECASE
        ))

        if len(risk_matches) >= 2:
            start_pos = risk_matches[1].start()
            search_from = start_pos + 5_000
            end_match = re.search(
                r'item\s*1b[\.\s]*unresolved|item\s*2[\.\s]*properties',
                clean[search_from:],
                flags=re.IGNORECASE
            )
            if end_match:
                end_pos = search_from + end_match.start()
                result["risk_factors"] = clean[start_pos:end_pos][:80_000]
            else:
                result["risk_factors"] = clean[start_pos:start_pos + 80_000]
            result["status"]["risk_factors_found"] = True

        elif len(risk_matches) == 1:
            start_pos = risk_matches[0].start()
            result["risk_factors"] = clean[start_pos:start_pos + 80_000]
            result["status"]["risk_factors_found"] = True
            result["status"]["risk_warning"] = "Only one match — may be TOC"
        else:
            result["status"]["risk_factors_found"] = False

        # Store truncated full text for general queries
        result["full_text"] = clean[:500_000]
        result["status"]["success"] = True

    except Exception as e:
        result["status"]["success"] = False
        result["status"]["error"] = str(e)

    return result


def get_filing(ticker: str, cik: str) -> dict:
    """
    Downloads most recent 10-K from EDGAR and extracts key sections.

    Input:
        ticker (str) — e.g. "AAPL"
        cik (str) — e.g. "0000320193"
    Output: dict with keys:
        - ticker: str
        - file_path: str
        - full_text: str
        - mda: str
        - risk_factors: str
        - status: dict
    """

    result = {
        "ticker": ticker.upper(),
        "file_path": None,
        "full_text": None,
        "mda": None,
        "risk_factors": None,
        "status": {}
    }

    # --- Step 1: Download filing ---
    try:
        filing_dir = "data/filings"
        dl = Downloader("credit-committee", USER_EMAIL, filing_dir)
        dl.get("10-K", ticker, limit=1)
        result["status"]["download"] = "success"
    except Exception as e:
        result["status"]["success"] = False
        result["status"]["error"] = f"Download failed: {str(e)}"
        return result

    # --- Step 2: Find downloaded file ---
    try:
        ticker_dir = os.path.join(
            filing_dir, "sec-edgar-filings",
            ticker.upper(), "10-K"
        )

        filing_folders = sorted(os.listdir(ticker_dir), reverse=True)

        if not filing_folders:
            result["status"]["success"] = False
            result["status"]["error"] = "No filing folders found after download"
            return result

        latest_folder = os.path.join(ticker_dir, filing_folders[0])
        file_path = os.path.join(latest_folder, "full-submission.txt")

        if not os.path.exists(file_path):
            result["status"]["success"] = False
            result["status"]["error"] = f"full-submission.txt not found in {latest_folder}"
            return result

        result["file_path"] = file_path
        result["status"]["file_found"] = True

    except Exception as e:
        result["status"]["success"] = False
        result["status"]["error"] = f"File search failed: {str(e)}"
        return result

    # --- Step 3: Extract text sections ---
    extracted = extract_text_from_filing(file_path)

    if not extracted["status"]["success"]:
        result["status"]["success"] = False
        result["status"]["error"] = extracted["status"].get("error", "Extraction failed")
        return result

    result["full_text"]    = extracted["full_text"]
    result["mda"]          = extracted["mda"]
    result["risk_factors"] = extracted["risk_factors"]
    result["status"].update(extracted["status"])
    result["status"]["success"] = True

    return result