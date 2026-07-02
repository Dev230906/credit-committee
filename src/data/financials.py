import yfinance as yf
import pandas as pd

# Sectors excluded from analysis
EXCLUDED_SECTORS = [
    "Financial Services",
    "Insurance",
    "Banks",
    "Diversified Financials"
]

def get_financial_ratios(ticker: str) -> dict:
    """
    Pulls financial statements from yfinance and computes credit ratios.
    
    Input: ticker (str) — e.g. "AAPL"
    Output: dict with keys:
        - company_info: dict (name, sector, market cap)
        - ratios: dict (all seven ratios, None if unavailable)
        - raw: dict (raw financial values used in calculations)
        - latest_year: str (fiscal year of latest data)
        - status: dict (flags for what data was available)
    """

    result = {
        "company_info": {},
        "ratios": {},
        "raw": {},
        "latest_year": None,
        "status": {}
    }

    try:
        stock = yf.Ticker(ticker)

        # --- Company Info First (needed for sector check) ---
        try:
            info = stock.info
            sector = info.get("sector", "Unknown")
            result["company_info"] = {
                "name": info.get("longName", "Unknown"),
                "sector": sector,
                "industry": info.get("industry", "Unknown"),
                "market_cap": info.get("marketCap", None),
                "description": info.get("longBusinessSummary", "Not available")
            }
        except Exception as e:
            result["status"]["company_info_error"] = str(e)
            result["status"]["success"] = False
            return result

        # --- Sector Check ---
        if sector in EXCLUDED_SECTORS:
            result["status"]["success"] = False
            result["status"]["error"] = (
                f"Sector '{sector}' is not supported. "
                f"This tool is designed for non-financial corporates only. "
                f"Financial institutions use different credit frameworks "
                f"(Tier 1 Capital, NIM, NPL ratio) outside this system's scope."
            )
            return result

        # --- Market Cap Check (large cap only) ---
        market_cap = result["company_info"]["market_cap"]
        if market_cap and market_cap < 10_000_000_000:
            result["status"]["success"] = False
            result["status"]["error"] = (
                f"Market cap ${market_cap/1e9:.1f}bn is below the $10bn "
                f"large cap threshold. This tool is designed for large cap "
                f"companies only."
            )
            return result

        # --- Financial Statements ---
        try:
            annual_income   = stock.financials
            annual_balance  = stock.balance_sheet
            annual_cashflow = stock.cashflow
            latest_year     = annual_income.columns[0]
            result["latest_year"] = str(latest_year.date())
        except Exception as e:
            result["status"]["financials_error"] = str(e)
            result["status"]["success"] = False
            return result

        # --- Safe Extraction ---
        def safe_get(df, field, col):
            try:
                val = df.loc[field, col]
                return float(val) if not pd.isna(val) else None
            except KeyError:
                return None

        # --- Interest Expense Fallback ---
        def get_interest_expense(income_stmt):
            for col in income_stmt.columns:
                for field in ['Interest Expense', 'Interest Expense Non Operating']:
                    try:
                        val = income_stmt.loc[field, col]
                        if val is not None and not pd.isna(val) and val != 0:
                            return abs(float(val))
                    except KeyError:
                        continue
            return None

        # --- Extract Raw Values ---
        ebit                = safe_get(annual_income, 'EBIT', latest_year)
        ebitda              = safe_get(annual_income, 'EBITDA', latest_year)
        revenue             = safe_get(annual_income, 'Total Revenue', latest_year)
        net_income          = safe_get(annual_income, 'Net Income', latest_year)
        total_debt          = safe_get(annual_balance, 'Total Debt', latest_year)
        net_debt            = safe_get(annual_balance, 'Net Debt', latest_year)
        cash                = safe_get(annual_balance, 'Cash And Cash Equivalents', latest_year)
        total_assets        = safe_get(annual_balance, 'Total Assets', latest_year)
        current_assets      = safe_get(annual_balance, 'Current Assets', latest_year)
        current_liabilities = safe_get(annual_balance, 'Current Liabilities', latest_year)
        working_capital     = safe_get(annual_balance, 'Working Capital', latest_year)
        retained_earnings   = safe_get(annual_balance, 'Retained Earnings', latest_year)
        operating_cf        = safe_get(annual_cashflow, 'Operating Cash Flow', latest_year)
        free_cf             = safe_get(annual_cashflow, 'Free Cash Flow', latest_year)
        interest_expense    = get_interest_expense(annual_income)
        market_cap          = result["company_info"]["market_cap"]

        result["raw"] = {
            "ebit": ebit,
            "ebitda": ebitda,
            "revenue": revenue,
            "net_income": net_income,
            "total_debt": total_debt,
            "net_debt": net_debt,
            "cash": cash,
            "total_assets": total_assets,
            "current_assets": current_assets,
            "current_liabilities": current_liabilities,
            "working_capital": working_capital,
            "retained_earnings": retained_earnings,
            "operating_cf": operating_cf,
            "free_cf": free_cf,
            "interest_expense": interest_expense,
            "market_cap": market_cap
        }

        # --- Compute Ratios ---
        ratios = {}

        ratios["debt_to_ebitda"] = (
            round(total_debt / ebitda, 2)
            if total_debt and ebitda
            else None
        )

        ratios["interest_coverage"] = (
            round(ebit / interest_expense, 2)
            if ebit and interest_expense
            else None
        )

        ratios["current_ratio"] = (
            round(current_assets / current_liabilities, 2)
            if current_assets and current_liabilities
            else None
        )

        ratios["fcf_to_debt"] = (
            round(free_cf / total_debt, 2)
            if free_cf and total_debt
            else None
        )

        ratios["net_debt_to_ebitda"] = (
            round(net_debt / ebitda, 2)
            if net_debt and ebitda
            else None
        )

        ratios["dscr"] = (
            round(operating_cf / total_debt, 2)
            if operating_cf and total_debt
            else None
        )

        if all([
            working_capital, retained_earnings, ebit,
            market_cap, total_debt, revenue, total_assets
        ]):
            z = (
                1.2 * (working_capital / total_assets) +
                1.4 * (retained_earnings / total_assets) +
                3.3 * (ebit / total_assets) +
                0.6 * (market_cap / total_debt) +
                1.0 * (revenue / total_assets)
            )
            ratios["altman_z"]    = round(z, 2)
            ratios["altman_zone"] = (
                "SAFE"     if z > 2.99 else
                "GREY"     if z > 1.81 else
                "DISTRESS"
            )
        else:
            ratios["altman_z"]    = None
            ratios["altman_zone"] = None

        result["ratios"] = ratios
        result["status"]["success"] = True

    except Exception as e:
        result["status"]["error"] = str(e)
        result["status"]["success"] = False

    return result