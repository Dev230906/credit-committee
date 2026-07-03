import os
from fredapi import Fred
from dotenv import load_dotenv

load_dotenv()

FRED_API_KEY = os.getenv("FRED_API_KEY")
fred = Fred(api_key=FRED_API_KEY)


def get_macro_context() -> dict:
    """
    Pulls five macro series from FRED and returns current snapshot
    plus 8-quarter history for each.

    Output: dict with keys:
        - snapshot: dict (latest value for each series)
        - history: dict (8-quarter DataFrame for each series)
        - narrative: str (plain English summary for LLM)
        - status: dict
    """

    result = {
        "snapshot": {},
        "history": {},
        "narrative": None,
        "status": {}
    }

    series_map = {
        "GDP":      "Gross Domestic Product (Billions USD)",
        "UNRATE":   "Unemployment Rate (%)",
        "FEDFUNDS": "Federal Funds Rate (%)",
        "BAA10Y":   "Moody's BAA Corporate Bond Spread (%)",
        "T10Y2Y":   "10Y minus 2Y Treasury Spread (%)"
    }

    failed = []

    for series_id, description in series_map.items():
        try:
            data = fred.get_series(series_id)

            if series_id == "GDP":
                recent = data.tail(8)
            else:
                recent = data.resample("QE").mean().tail(8)

            latest_val  = round(float(recent.iloc[-1]), 2)
            latest_date = str(recent.index[-1].date())

            if len(recent) >= 2:
                prev_val   = float(recent.iloc[-2])
                qoq_change = round(latest_val - prev_val, 2)
                direction  = "up" if qoq_change > 0 else "down"
            else:
                qoq_change = None
                direction  = "unknown"

            result["snapshot"][series_id] = {
                "description": description,
                "latest_value": latest_val,
                "latest_date": latest_date,
                "qoq_change": qoq_change,
                "direction": direction
            }

            result["history"][series_id] = recent

        except Exception as e:
            failed.append(series_id)
            result["snapshot"][series_id] = None

    # --- Build plain English narrative for LLM ---
    try:
        s = result["snapshot"]

        gdp      = s.get("GDP", {})
        unrate   = s.get("UNRATE", {})
        fedfunds = s.get("FEDFUNDS", {})
        baa10y   = s.get("BAA10Y", {})
        t10y2y   = s.get("T10Y2Y", {})

        narrative_parts = []

        if gdp:
            narrative_parts.append(
                f"GDP stood at ${gdp['latest_value']:,}bn as of "
                f"{gdp['latest_date']}, "
                f"{'expanding' if gdp['direction'] == 'up' else 'contracting'} "
                f"by ${abs(gdp['qoq_change']):,}bn quarter over quarter."
            )

        if unrate:
            narrative_parts.append(
                f"The unemployment rate is {unrate['latest_value']}%, "
                f"{'rising' if unrate['direction'] == 'up' else 'falling'} "
                f"{abs(unrate['qoq_change'])}pp quarter over quarter."
            )

        if fedfunds:
            narrative_parts.append(
                f"The Federal Funds Rate stands at {fedfunds['latest_value']}%, "
                f"indicating a "
                f"{'tight' if fedfunds['latest_value'] > 4 else 'moderate' if fedfunds['latest_value'] > 2 else 'loose'} "
                f"monetary policy environment."
            )

        if baa10y:
            narrative_parts.append(
                f"The Moody's BAA corporate bond spread is "
                f"{baa10y['latest_value']}%, suggesting "
                f"{'elevated' if baa10y['latest_value'] > 3 else 'moderate' if baa10y['latest_value'] > 1.5 else 'compressed'} "
                f"credit risk appetite in the market."
            )

        if t10y2y:
            curve_desc = (
                "inverted (recession signal)" if t10y2y['latest_value'] < 0
                else "flat" if t10y2y['latest_value'] < 0.5
                else "positively sloped"
            )
            narrative_parts.append(
                f"The 10Y-2Y Treasury spread is {t10y2y['latest_value']}%, "
                f"indicating a {curve_desc} yield curve."
            )

        result["narrative"] = " ".join(narrative_parts)

    except Exception as e:
        result["status"]["narrative_error"] = str(e)

    if failed:
        result["status"]["failed_series"] = failed
        result["status"]["success"] = len(failed) < 3
    else:
        result["status"]["success"] = True

    return result