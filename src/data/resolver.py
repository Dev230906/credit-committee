import yfinance as yf
import requests
import xml.etree.ElementTree as ET
import os
from dotenv import load_dotenv

load_dotenv()

USER_EMAIL = os.getenv("USER_EMAIL", "your_email@gmail.com")

EXCLUDED_SECTORS = [
    "Financial Services",
    "Insurance",
    "Banks",
    "Diversified Financials"
]

EXCLUDED_SIC_PREFIXES = ["60", "61", "62", "63", "64", "65"]


def resolve_ticker(ticker: str) -> dict:
    """
    Resolves a ticker to all identifiers needed by the pipeline.
    Validates: exists on yfinance, large cap, non-financial sector.

    Input: ticker (str) — e.g. "AAPL"
    Output: dict with keys:
        - ticker: str
        - legal_name: str
        - cik: str
        - sector: str
        - industry: str
        - market_cap: float
        - sic: str
        - sic_desc: str
        - status: dict (success bool + error message if failed)
    """

    result = {
        "ticker": ticker.upper(),
        "legal_name": None,
        "cik": None,
        "sector": None,
        "industry": None,
        "market_cap": None,
        "sic": None,
        "sic_desc": None,
        "status": {}
    }

    # --- Step 1: Validate ticker exists on yfinance ---
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        if not info or "longName" not in info:
            result["status"]["success"] = False
            result["status"]["error"] = (
                f"Ticker '{ticker}' not found on Yahoo Finance."
            )
            return result

        result["legal_name"] = info.get("longName", "Unknown")
        result["sector"]     = info.get("sector", "Unknown")
        result["industry"]   = info.get("industry", "Unknown")
        result["market_cap"] = info.get("marketCap", None)

    except Exception as e:
        result["status"]["success"] = False
        result["status"]["error"] = f"yfinance error: {str(e)}"
        return result

    # --- Step 2: Sector check ---
    if result["sector"] in EXCLUDED_SECTORS:
        result["status"]["success"] = False
        result["status"]["error"] = (
            f"Sector '{result['sector']}' is not supported. "
            f"This tool is designed for non-financial corporates only."
        )
        return result

    # --- Step 3: Market cap check ---
    if result["market_cap"] and result["market_cap"] < 10_000_000_000:
        result["status"]["success"] = False
        result["status"]["error"] = (
            f"Market cap ${result['market_cap']/1e9:.1f}bn is below "
            f"the $10bn large cap threshold."
        )
        return result

    # --- Step 4: Get CIK from EDGAR ---
    try:
        headers = {"User-Agent": f"credit-committee-project {USER_EMAIL}"}
        response = requests.get(
            "https://www.sec.gov/cgi-bin/browse-edgar"
            "?action=getcompany&CIK={}&type=10-K"
            "&dateb=&owner=include&count=5"
            "&search_text=&output=atom".format(ticker),
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            try:
                # Clean namespace before parsing
                xml_text = response.text.replace(
                    'xmlns="http://www.w3.org/2005/Atom"', ''
                )
                # Remove any special characters that break parsing
                xml_text = xml_text.encode(
                    'ascii', 'ignore'
                ).decode('ascii')

                root = ET.fromstring(xml_text)
                company_info = root.find("company-info")

                if company_info is not None:
                    cik_el      = company_info.find("cik")
                    sic_el      = company_info.find("assigned-sic")
                    sic_desc_el = company_info.find("assigned-sic-desc")

                    result["cik"]      = cik_el.text      if cik_el      is not None else None
                    result["sic"]      = sic_el.text      if sic_el      is not None else None
                    result["sic_desc"] = sic_desc_el.text if sic_desc_el is not None else None

                    # Backup SIC-based financial sector check
                    if result["sic"] and any(
                        result["sic"].startswith(prefix)
                        for prefix in EXCLUDED_SIC_PREFIXES
                    ):
                        result["status"]["success"] = False
                        result["status"]["error"] = (
                            f"SIC code {result['sic']} "
                            f"({result['sic_desc']}) indicates a "
                            f"financial institution. Not supported."
                        )
                        return result
                else:
                    result["status"]["cik_warning"] = (
                        "CIK not found on EDGAR — "
                        "filing download may fail."
                    )
            except ET.ParseError as e:
                # XML parsing failed — non blocking, just warn
                result["status"]["cik_warning"] = (
                    f"EDGAR XML parsing failed: {str(e)}"
                )
        else:
            result["status"]["cik_warning"] = (
                f"EDGAR returned {response.status_code} — "
                f"CIK unavailable."
            )

    except Exception as e:
        result["status"]["cik_warning"] = (
            f"EDGAR lookup failed: {str(e)}"
        )

    result["status"]["success"] = True
    return result