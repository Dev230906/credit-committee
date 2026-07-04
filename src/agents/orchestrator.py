import os
import json
from datetime import date
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from src.schemas.models import (
    OrchestratorOutput,
    LendingDecision,
    get_pd_from_rating
)

load_dotenv()

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.1
)

APPROVE_RATINGS     = ["AAA", "AA", "A", "BBB"]
CONDITIONAL_RATINGS = ["BB", "B"]
DECLINE_RATINGS     = ["CCC", "CC", "C", "D"]

SYSTEM_PROMPT = """You are the chair of a credit committee at a major bank.
You have just heard from three analysts and must render a final credit decision.
Synthesize all inputs into a structured credit memo.
If human input is provided, weight it most heavily.
Output ONLY valid JSON — no preamble, no markdown backticks."""

SCHEMA = """
Output a JSON object with these exact fields:
{
  "company_name": "Apple Inc.",
  "ticker": "AAPL",
  "sector": "Technology",
  "analysis_date": "2026-07-04",
  "final_rating": "AAA",
  "pd_12month": null,
  "pd_3year": null,
  "top_risk_factors": [
    {"rank": 1, "factor": "factor name", "description": "detailed description", "severity": "High"},
    {"rank": 2, "factor": "factor name", "description": "detailed description", "severity": "Medium"},
    {"rank": 3, "factor": "factor name", "description": "detailed description", "severity": "Medium"},
    {"rank": 4, "factor": "factor name", "description": "detailed description", "severity": "Low"},
    {"rank": 5, "factor": "factor name", "description": "detailed description", "severity": "Low"}
  ],
  "mitigants": ["mitigant 1", "mitigant 2", "mitigant 3"],
  "lending_decision": "Approve",
  "decision_conditions": null,
  "narrative_rationale": "400 word committee chair narrative explaining the decision",
  "confidence_level": "High",
  "confidence_rationale": "one sentence explaining confidence level",
  "credit_analyst_rating": "AAA",
  "devils_advocate_rating": "AA",
  "human_input_received": false
}
final_rating must be one of: AAA, AA, A, BBB, BB, B, CCC, CC, C, D
lending_decision must be one of: Approve, Conditional, Decline
severity must be one of: High, Medium, Low
confidence_level must be one of: High, Medium, Low
pd_12month and pd_3year must be null — populated after validation
Output ONLY the JSON object. No preamble, no markdown backticks."""


def determine_lending_decision(rating: str) -> LendingDecision:
    """Maps final rating to lending decision."""
    rating = rating.replace("InternalRating.", "")
    if rating in APPROVE_RATINGS:
        return LendingDecision.APPROVE
    elif rating in CONDITIONAL_RATINGS:
        return LendingDecision.CONDITIONAL
    return LendingDecision.DECLINE


def run_orchestrator(state: dict) -> dict:
    """
    Runs the Orchestrator agent.
    Input: state (dict) — LangGraph pipeline state
    Output: updated state dict with orchestrator_output populated
    """

    from datetime import date

    # LangGraph passes only delta on resume from interrupt
    # Use .get() with fallbacks for ALL fields
    ticker          = state.get("ticker") or ""
    legal_name      = state.get("legal_name") or ""
    sector          = state.get("sector") or ""
    research_output = state.get("research_analyst_output") or {}
    credit_output   = state.get("credit_analyst_output") or {}
    devil_output    = state.get("devils_advocate_output") or {}
    macro_narrative = state.get("macro_narrative") or "Not available"
    human_input     = state.get("human_input") or None

    # If critical fields missing build safe fallbacks
    if not legal_name:
        legal_name = ticker or "Unknown Company"
    if not sector:
        sector = "Unknown"

    credit_rating = str(credit_output.get(
        "preliminary_rating", "BBB"
    )).replace("InternalRating.", "")

    devil_rating = str(devil_output.get(
        "counter_rating", "BB"
    )).replace("InternalRating.", "")

    human_section = (
        f"\nSENIOR ANALYST OVERRIDE (weight most heavily):\n{human_input}"
        if human_input else "\nNo human input provided."
    )

    user_prompt = f"""
Company: {legal_name}
Sector: {sector}
Ticker: {ticker}
Analysis Date: {date.today().isoformat()}

RESEARCH ANALYST OUTPUT:
Business Summary: {research_output.get('business_summary', 'N/A')[:300]}
Liquidity: {research_output.get('liquidity_assessment', 'N/A')[:200]}
Covenants: {research_output.get('covenant_observations', 'N/A')[:200]}
Management Tone: {research_output.get('management_tone', 'N/A')}
Going Concern: {research_output.get('going_concern_flag', False)}
Top Risks: {str(research_output.get('risk_factors', []))[:400]}

CREDIT ANALYST OUTPUT:
Preliminary Rating: {credit_rating}
Primary Concern: {credit_output.get('primary_concern', 'N/A')}
Narrative: {credit_output.get('quantitative_narrative', 'N/A')[:300]}
Rationale: {credit_output.get('preliminary_rating_rationale', 'N/A')[:200]}

DEVIL'S ADVOCATE OUTPUT:
Counter Rating: {devil_rating}
Default Trigger: {devil_output.get('most_likely_default_trigger', 'N/A')}
Bear Case: {devil_output.get('bear_case_narrative', 'N/A')[:300]}
Adversarial Risks: {str(devil_output.get('adversarial_risks', []))[:400]}
Macro Vulnerability: {devil_output.get('macro_vulnerability', 'N/A')[:200]}

MACRO CONTEXT:
{macro_narrative}
{human_section}

LENDING DECISION MAPPING:
Approve     : final_rating in AAA, AA, A, BBB
Conditional : final_rating in BB, B
Decline     : final_rating in CCC, CC, C, D

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
            output = OrchestratorOutput(**data)

            output.lending_decision = determine_lending_decision(
                str(output.final_rating).replace("InternalRating.", "")
            )

            final_rating_str  = str(
                output.final_rating
            ).replace("InternalRating.", "")
            pd_12m, pd_3y     = get_pd_from_rating(final_rating_str)
            output.pd_12month = pd_12m
            output.pd_3year   = pd_3y
            output.human_input_received = bool(human_input)
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
        return {
            "errors": state.get("errors", []) + [
                f"Orchestrator failed after 3 attempts: {last_error}"
            ],
            "current_stage": "orchestrator_failed"
        }

    print(f"Orchestrator complete — "
          f"final_rating: {output.final_rating}, "
          f"decision: {output.lending_decision}, "
          f"PD 12m: {output.pd_12month:.4f}, "
          f"PD 3y: {output.pd_3year:.4f}")

    return {
        "orchestrator_output": json.loads(
            json.dumps(output.model_dump(), default=str)
        ),
        "current_stage": "orchestrator_complete"
    }