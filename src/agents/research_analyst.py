import os
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from src.schemas.models import ResearchAnalystOutput
from src.rag.indexer import build_filing_index, query_filing

load_dotenv()

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.1
)

FILING_QUERIES = [
    "What is the company's primary business model and main revenue sources?",
    "What does management say about liquidity, cash position, and ability to meet near-term obligations?",
    "What debt facilities, credit agreements, and covenants does the company have?",
    "Is there any going concern language from the auditor or management?",
    "What are the top risk factors disclosed by management?",
    "Has management changed language around any key risks compared to prior periods?"
]

SCHEMA_DESCRIPTION = """
Output a JSON object with these exact fields:
{
  "business_summary": "200 word max summary of business model and revenue sources",
  "liquidity_assessment": "management stated liquidity position and cash runway",
  "covenant_observations": "key debt covenants thresholds and headroom if disclosed",
  "going_concern_flag": false,
  "risk_factors": [
    {"rank": 1, "description": "risk description", "source": "where in filing"},
    {"rank": 2, "description": "risk description", "source": "where in filing"},
    {"rank": 3, "description": "risk description", "source": "where in filing"},
    {"rank": 4, "description": "risk description", "source": "where in filing"},
    {"rank": 5, "description": "risk description", "source": "where in filing"}
  ],
  "management_tone": "Confident",
  "language_changes": null,
  "transcript_available": true
}
management_tone must be one of: Confident, Cautious, Defensive, Distressed
going_concern_flag must be true or false
Output ONLY the JSON object. No preamble, no markdown backticks."""

SYSTEM_PROMPT = """You are a senior credit research analyst at a major bank.
Your job is to extract specific qualitative credit risk signals from SEC filings
and earnings call transcripts. Be precise, factual, and reference specific
sections. Output ONLY valid JSON — no preamble, no markdown backticks."""


def run_research_analyst(state: dict) -> dict:
    """
    Runs the Research Analyst agent.
    Input: state (dict) — LangGraph pipeline state
    Output: updated state dict with research_analyst_output populated
    """

    ticker     = state["ticker"]
    legal_name = state["legal_name"]
    sector     = state["sector"]

    # --- Build filing index ---
    filing_data = {
        "mda":          state.get("mda"),
        "risk_factors": state.get("risk_factors"),
        "full_text":    state.get("full_text")
    }

    index_data = build_filing_index(ticker, filing_data)

    if not index_data["status"]["success"]:
        state["errors"].append(
            f"Research Analyst: index build failed — "
            f"{index_data['status'].get('error')}"
        )
        state["current_stage"] = "research_analyst_failed"
        return state

    retriever = index_data["retriever"]

    # --- Run filing queries ---
    query_results = {}
    for i, query in enumerate(FILING_QUERIES):
        try:
            query_results[f"Q{i+1}"] = query_filing(retriever, query)
        except Exception as e:
            query_results[f"Q{i+1}"] = f"Query failed: {str(e)}"

    # --- Build context ---
    ratios = state.get("ratio_table", {}).get("ratios", {})
    ratio_summary = f"""
Debt/EBITDA: {ratios.get('debt_to_ebitda', 'N/A')}x
Interest Coverage: {ratios.get('interest_coverage', 'N/A')}x
Current Ratio: {ratios.get('current_ratio', 'N/A')}x
FCF to Debt: {ratios.get('fcf_to_debt', 'N/A')}x
Altman Z-Score: {ratios.get('altman_z', 'N/A')} ({ratios.get('altman_zone', 'N/A')})
"""

    filing_context = "\n\n".join([
        f"{k}: {v[:500]}" for k, v in query_results.items()
    ])

    transcript_text      = state.get("transcript_text", "")
    transcript_available = bool(transcript_text)
    transcript_context   = (
        transcript_text[:3000]
        if transcript_available
        else "Transcript unavailable"
    )

    user_prompt = f"""
Company: {legal_name}
Sector: {sector}
Ticker: {ticker}

FINANCIAL RATIO SUMMARY:
{ratio_summary}

FILING EXCERPTS (from SEC 10-K):
{filing_context}

EARNINGS CALL TRANSCRIPT (most recent):
{transcript_context}

{SCHEMA_DESCRIPTION}
"""

    # --- Call LLM with retry ---
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
            output = ResearchAnalystOutput(**data)
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
                        f"{SCHEMA_DESCRIPTION}"
                    ))
                ]).content

    if output is None:
        state["errors"].append(
            f"Research Analyst failed after 3 attempts: {last_error}"
        )
        state["current_stage"] = "research_analyst_failed"
        return state

    # --- Write to state ---
    state["research_analyst_output"] = json.loads(json.dumps(output.model_dump(), default=str))
    state["current_stage"]           = "research_analyst_complete"

    print(f"Research Analyst complete — "
          f"tone: {output.management_tone}, "
          f"going concern: {output.going_concern_flag}")

    return state