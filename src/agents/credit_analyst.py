import os
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from src.schemas.models import CreditAnalystOutput

load_dotenv()

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.1
)

SYSTEM_PROMPT = """You are a senior credit analyst at a major bank.
Your job is to interpret financial ratios and assign a preliminary internal credit rating.
Use the rating mapping guidelines provided.
Output ONLY valid JSON — no preamble, no markdown backticks."""

RATING_GUIDELINES = """
RATING MAPPING GUIDELINES — apply these strictly:
AAA/AA : Debt/EBITDA < 1x AND Interest Coverage > 15x AND Altman Z > 5
A      : Debt/EBITDA 1-2x AND Interest Coverage 8-15x AND Altman Z > 4
BBB    : Debt/EBITDA 2-3x AND Interest Coverage 4-8x AND Altman Z > 3
BB     : Debt/EBITDA 3-5x AND Interest Coverage 2-4x AND Altman Z 2-3
B      : Debt/EBITDA 5-7x AND Interest Coverage 1.5-2x AND Altman Z 1.5-2
CCC    : Debt/EBITDA > 7x AND Interest Coverage < 1.5x AND Altman Z < 1.8
CC/C/D : Interest Coverage < 1x OR negative FCF AND imminent default risk

IMPORTANT: Use the LOWEST applicable rating if metrics are mixed.
Example: If Debt/EBITDA is 0.68x (AAA) but Current Ratio is 0.89x (weak),
the rating should still reflect the overall credit quality — do not 
automatically assign AAA just because one metric looks strong.

TREND ASSESSMENT:
- Improving: ratio moving in positive direction over last 3 quarters
- Deteriorating: ratio moving in negative direction over last 3 quarters  
- Stable: minimal change quarter over quarter

If a ratio is N/A or unavailable, note it but do not use it to justify a rating.
"""

SCHEMA = """
Output a JSON object with these exact fields:
{
  "debt_to_ebitda": 0.68,
  "interest_coverage": 33.83,
  "current_ratio": 0.89,
  "fcf_to_debt": 1.0,
  "net_debt_to_ebitda": 0.43,
  "dscr": 1.13,
  "altman_z": 29.77,
  "altman_zone": "SAFE",
  "leverage_trend": "Stable",
  "coverage_trend": "Stable",
  "cashflow_trend": "Stable",
  "quantitative_narrative": "300 word max interpretation of the quantitative picture",
  "primary_concern": "single metric most responsible for the rating",
  "preliminary_rating": "AAA",
  "preliminary_rating_rationale": "one paragraph explaining the rating decision"
}
preliminary_rating must be one of: AAA, AA, A, BBB, BB, B, CCC, CC, C, D
leverage_trend, coverage_trend, cashflow_trend must be: Improving, Stable, or Deteriorating
Output ONLY the JSON object. No preamble, no markdown backticks."""


def run_credit_analyst(state: dict) -> dict:
    """
    Runs the Credit Analyst agent.
    Input: state (dict) — LangGraph pipeline state
    Output: updated state dict with credit_analyst_output populated
    """

    ratio_table     = state.get("ratio_table", {})
    ratios          = ratio_table.get("ratios", {})
    research_output = state.get("research_analyst_output", {})

    ratio_context = f"""
FINANCIAL RATIOS (Latest Year: {ratio_table.get('latest_year', 'N/A')}):
| Metric              | Value                                      |
|---------------------|--------------------------------------------|
| Debt/EBITDA         | {ratios.get('debt_to_ebitda', 'N/A')}x    |
| Interest Coverage   | {ratios.get('interest_coverage', 'N/A')}x  |
| Current Ratio       | {ratios.get('current_ratio', 'N/A')}x      |
| FCF to Debt         | {ratios.get('fcf_to_debt', 'N/A')}x        |
| Net Debt/EBITDA     | {ratios.get('net_debt_to_ebitda', 'N/A')}x |
| DSCR                | {ratios.get('dscr', 'N/A')}x              |
| Altman Z-Score      | {ratios.get('altman_z', 'N/A')} ({ratios.get('altman_zone', 'N/A')})|
"""

    research_context = f"""
RESEARCH ANALYST SUMMARY:
Business: {research_output.get('business_summary', 'N/A')[:300]}
Liquidity: {research_output.get('liquidity_assessment', 'N/A')[:200]}
Management Tone: {research_output.get('management_tone', 'N/A')}
Going Concern Flag: {research_output.get('going_concern_flag', False)}
"""

    user_prompt = f"""
Company: {state['legal_name']}
Sector: {state['sector']}
Ticker: {state['ticker']}

{ratio_context}

{research_context}

{RATING_GUIDELINES}

{SCHEMA}
"""

    last_error   = None
    llm_response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_prompt)
    ]).content
    output = None

    for attempt in range(3):
        try:
            clean = llm_response.strip()
            if clean.startswith("```"):
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            clean  = clean.strip()
            clean  = clean.replace('"null"', 'null')
            data   = json.loads(clean)
            output = CreditAnalystOutput(**data)
            break

        except Exception as e:
            last_error = str(e)
            if attempt < 2:
                llm_response = llm.invoke([
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=(
                        f"Your output failed validation: {last_error}\n"
                        f"Fix and return ONLY valid JSON.\n"
                        f"Previous output: {llm_response}\n"
                        f"{SCHEMA}"
                    ))
                ]).content

    if output is None:
        state["errors"].append(
            f"Credit Analyst failed after 3 attempts: {last_error}"
        )
        state["current_stage"] = "credit_analyst_failed"
        return state

    state["credit_analyst_output"] = json.loads(json.dumps(output.model_dump(), default=str))
    state["current_stage"]         = "credit_analyst_complete"

    print(f"Credit Analyst complete — "
          f"rating: {output.preliminary_rating}, "
          f"primary concern: {output.primary_concern}")

    return state