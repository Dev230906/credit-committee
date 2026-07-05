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

WEIGHTING RULES — follow these strictly:
1. If human analyst input is provided, weight it most heavily
2. The Credit Analyst quantitative rating is your BASE CASE — start from it
3. Only adjust DOWN if Devil's Advocate provides specific filing evidence
4. Do NOT average ratings — the final_rating must equal the Credit Analyst
   rating OR one notch below if Devil's Advocate evidence is strong
5. NEVER produce a final_rating more than two notches from Credit Analyst rating

Output ONLY valid JSON — no preamble, no markdown backticks."""


def build_schema(legal_name: str, ticker: str, sector: str,
                 credit_rating: str, devil_rating: str) -> str:
    return f"""
Output a JSON object with these exact fields.
Use the EXACT values specified for company_name, ticker, sector,
credit_analyst_rating, and devils_advocate_rating:

{{
  "company_name": "{legal_name}",
  "ticker": "{ticker}",
  "sector": "{sector}",
  "analysis_date": "{date.today().isoformat()}",
  "final_rating": "<must be one of: AAA AA A BBB BB B CCC CC C D>",
  "pd_12month": null,
  "pd_3year": null,
  "top_risk_factors": [
    {{"rank": 1, "factor": "<risk name>", "description": "<detailed description>", "severity": "High"}},
    {{"rank": 2, "factor": "<risk name>", "description": "<detailed description>", "severity": "Medium"}},
    {{"rank": 3, "factor": "<risk name>", "description": "<detailed description>", "severity": "Medium"}},
    {{"rank": 4, "factor": "<risk name>", "description": "<detailed description>", "severity": "Low"}},
    {{"rank": 5, "factor": "<risk name>", "description": "<detailed description>", "severity": "Low"}}
  ],
  "mitigants": ["<mitigant 1>", "<mitigant 2>", "<mitigant 3>"],
  "lending_decision": "<Approve or Conditional or Decline>",
  "decision_conditions": null,
  "narrative_rationale": "<400 word committee chair narrative>",
  "confidence_level": "<High or Medium or Low>",
  "confidence_rationale": "<one sentence>",
  "credit_analyst_rating": "{credit_rating}",
  "devils_advocate_rating": "{devil_rating}",
  "human_input_received": false
}}

final_rating must be one of: AAA, AA, A, BBB, BB, B, CCC, CC, C, D
lending_decision must be one of: Approve, Conditional, Decline
severity must be one of: High, Medium, Low
confidence_level must be one of: High, Medium, Low
pd_12month and pd_3year must be null
Output ONLY the JSON object. No preamble, no markdown backticks."""


def determine_lending_decision(rating: str) -> LendingDecision:
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

    ticker          = state.get("ticker") or ""
    legal_name      = state.get("legal_name") or ticker or "Unknown Company"
    sector          = state.get("sector") or "Unknown"
    research_output = state.get("research_analyst_output") or {}
    credit_output   = state.get("credit_analyst_output") or {}
    devil_output    = state.get("devils_advocate_output") or {}
    macro_narrative = state.get("macro_narrative") or "Not available"
    human_input     = state.get("human_input") or None

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

    # Build schema with actual values embedded
    schema = build_schema(legal_name, ticker, sector, credit_rating, devil_rating)

    user_prompt = f"""
Company: {legal_name}
Sector: {sector}
Ticker: {ticker}
Analysis Date: {date.today().isoformat()}

CREDIT ANALYST PRELIMINARY RATING: {credit_rating}
Your final_rating should be {credit_rating} unless Devil's Advocate
provides strong specific evidence to justify a lower rating.

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

DEVIL'S ADVOCATE OUTPUT:
Counter Rating: {devil_rating}
Default Trigger: {devil_output.get('most_likely_default_trigger', 'N/A')}
Bear Case: {devil_output.get('bear_case_narrative', 'N/A')[:300]}
Adversarial Risks: {str(devil_output.get('adversarial_risks', []))[:400]}

MACRO CONTEXT:
{macro_narrative}
{human_section}

LENDING DECISION MAPPING:
Approve     : final_rating in AAA, AA, A, BBB
Conditional : final_rating in BB, B
Decline     : final_rating in CCC, CC, C, D

{schema}
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
            clean = clean.strip()
            clean = clean.replace('"null"', 'null')
            data  = json.loads(clean)

            # Force correct values regardless of LLM output
            data["company_name"]           = legal_name
            data["ticker"]                 = ticker
            data["sector"]                 = sector
            data["credit_analyst_rating"]  = credit_rating
            data["devils_advocate_rating"] = devil_rating
            data["analysis_date"]          = date.today().isoformat()

            output = OrchestratorOutput(**data)

            # Override lending decision programmatically
            output.lending_decision = determine_lending_decision(
                str(output.final_rating).replace("InternalRating.", "")
            )

            # Populate PD from Moody's table
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
                        f"{schema}"
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