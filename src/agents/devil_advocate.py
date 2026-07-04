import os
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from src.schemas.models import DevilsAdvocateOutput, InternalRating
from src.rag.indexer import build_filing_index, query_filing

load_dotenv()

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.2
)

RATING_ORDER = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D"]

ADVERSARIAL_QUERIES = [
    "What near-term debt maturities does the company face and how does it plan to refinance?",
    "What contingent liabilities, legal proceedings, or off-balance-sheet obligations exist?",
    "What assumptions underlie management's forward guidance and how sensitive are they?",
    "What macro or industry headwinds could materially impair revenue or margins?"
]

SYSTEM_PROMPT = """You are the Devil's Advocate in a credit committee at a major bank.
Your ONLY job is to find reasons this borrower will default.
You MUST disagree with the Credit Analyst's assessment.
Ground every argument in specific filing evidence.
Produce minimum 3, maximum 6 adversarial risk arguments.
Output ONLY valid JSON — no preamble, no markdown backticks."""

SCHEMA = """
Output a JSON object with these exact fields:
{
  "adversarial_risks": [
    {
      "rank": 1,
      "risk_description": "description of risk",
      "filing_evidence": "specific text from filing supporting this",
      "quantitative_impact": "estimated financial impact if risk materializes",
      "probability": "High"
    },
    {
      "rank": 2,
      "risk_description": "description of risk",
      "filing_evidence": "specific text from filing",
      "quantitative_impact": "estimated impact",
      "probability": "Medium"
    },
    {
      "rank": 3,
      "risk_description": "description of risk",
      "filing_evidence": "specific text from filing",
      "quantitative_impact": "estimated impact",
      "probability": "Low"
    }
  ],
  "most_likely_default_trigger": "single most plausible path to default in 12-24 months",
  "bear_case_narrative": "200 word max bear case summary",
  "counter_rating": "AA",
  "macro_vulnerability": "how a macro downturn specifically hurts this borrower"
}
adversarial_risks must have minimum 3 items
probability must be one of: High, Medium, Low
counter_rating must be one of: AAA, AA, A, BBB, BB, B, CCC, CC, C, D
Output ONLY the JSON object. No preamble, no markdown backticks."""


def enforce_counter_rating(
    counter_rating: str,
    preliminary_rating: str
) -> InternalRating:
    """Ensures counter_rating is at least one notch below preliminary_rating."""
    try:
        prelim_idx  = RATING_ORDER.index(preliminary_rating)
        counter_idx = RATING_ORDER.index(counter_rating)
        if counter_idx <= prelim_idx:
            new_idx = min(prelim_idx + 1, len(RATING_ORDER) - 1)
            return InternalRating(RATING_ORDER[new_idx])
        return InternalRating(counter_rating)
    except ValueError:
        return InternalRating(RATING_ORDER[min(
            RATING_ORDER.index(preliminary_rating) + 1, 9
        )])


def run_devil_advocate(state: dict) -> dict:
    """
    Runs the Devil's Advocate agent.
    Input: state (dict) — LangGraph pipeline state
    Output: updated state dict with devils_advocate_output populated
    """

    ticker             = state["ticker"]
    research_output    = state.get("research_analyst_output", {})
    credit_output      = state.get("credit_analyst_output", {})
    preliminary_rating = str(credit_output.get(
        "preliminary_rating", "BBB"
    )).replace("InternalRating.", "")

    # --- Load index and run adversarial queries ---
    filing_data = {
        "mda":          state.get("mda"),
        "risk_factors": state.get("risk_factors"),
        "full_text":    state.get("full_text")
    }
    index_data = build_filing_index(ticker, filing_data)
    retriever  = index_data["retriever"]

    adversarial_context = {}
    for i, query in enumerate(ADVERSARIAL_QUERIES):
        try:
            adversarial_context[f"AQ{i+1}"] = query_filing(retriever, query)
        except Exception as e:
            adversarial_context[f"AQ{i+1}"] = f"Query failed: {str(e)}"

    filing_evidence = "\n\n".join([
        f"{k}: {v[:400]}" for k, v in adversarial_context.items()
    ])

    user_prompt = f"""
Company: {state['legal_name']}
Sector: {state['sector']}
Ticker: {ticker}

CREDIT ANALYST PRELIMINARY RATING: {preliminary_rating}
You MUST assign a counter_rating that is LOWER (worse) than {preliminary_rating}.

RESEARCH ANALYST OUTPUT:
Business: {research_output.get('business_summary', 'N/A')[:200]}
Risk Factors: {str(research_output.get('risk_factors', []))[:300]}
Management Tone: {research_output.get('management_tone', 'N/A')}
Going Concern: {research_output.get('going_concern_flag', False)}

CREDIT ANALYST OUTPUT:
Rating: {preliminary_rating}
Primary Concern: {credit_output.get('primary_concern', 'N/A')}
Narrative: {credit_output.get('quantitative_narrative', 'N/A')[:200]}

ADVERSARIAL FILING EVIDENCE:
{filing_evidence}

MACRO CONTEXT:
{state.get('macro_narrative', 'Not available')}

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
            output = DevilsAdvocateOutput(**data)

            # Enforce counter_rating constraint
            output.counter_rating = enforce_counter_rating(
                str(output.counter_rating).replace("InternalRating.", ""),
                preliminary_rating
            )
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
            f"Devil's Advocate failed after 3 attempts: {last_error}"
        )
        state["current_stage"] = "devils_advocate_failed"
        return state

    state["devils_advocate_output"] = json.loads(json.dumps(output.model_dump(), default=str))
    state["current_stage"]          = "devils_advocate_complete"

    print(f"Devil's Advocate complete — "
          f"counter_rating: {output.counter_rating}, "
          f"default trigger: {output.most_likely_default_trigger[:80]}")

    return state