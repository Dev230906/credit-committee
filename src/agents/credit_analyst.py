# src/agents/credit_analyst.py
# PURPOSE: Agent 2 — Credit Analyst
#
# ROLE: Interprets quantitative financial ratios and maps them to a
# preliminary internal rating. Pure quantitative analysis — no filing queries.
#
# INPUTS (from LangGraph state):
#   - state.research_analyst_output: ResearchAnalystOutput dict (from Agent 1)
#   - state.ratio_table: dict from get_financial_ratios() containing:
#       {
#         "ratios": {
#           "debt_to_ebitda": float or None,
#           "interest_coverage": float or None,
#           "current_ratio": float or None,
#           "fcf_to_debt": float or None,
#           "net_debt_to_ebitda": float or None,
#           "dscr": float or None,
#           "altman_z": float or None,
#           "altman_zone": str or None
#         },
#         "company_info": {...},
#         "latest_year": str
#       }
#
# PROCESS:
#   1. Format ratio table as markdown table for LLM prompt
#   2. Build prompt with rating mapping guidelines:
#      AAA/AA : Debt/EBITDA < 1x, Coverage > 15x, Altman Z > 5
#      A      : Debt/EBITDA 1-2x, Coverage 8-15x, Z > 4
#      BBB    : Debt/EBITDA 2-3x, Coverage 4-8x, Z > 3
#      BB     : Debt/EBITDA 3-5x, Coverage 2-4x, Z 2-3
#      B      : Debt/EBITDA 5-7x, Coverage 1.5-2x, Z 1.5-2
#      CCC    : Debt/EBITDA > 7x, Coverage < 1.5x, Z < 1.8
#      CC/C/D : Coverage < 1x, negative FCF, imminent default risk
#   3. Also assess trends: is leverage rising or falling quarter over quarter?
#   4. Produce CreditAnalystOutput Pydantic object
#
# OUTPUTS (written to LangGraph state):
#   - state.credit_analyst_output: CreditAnalystOutput as dict
#   - state.current_stage: "credit_analyst_complete"
#
# DEPENDENCIES:
#   - src/schemas/models.py: CreditAnalystOutput, InternalRating
#   - langchain_groq: ChatGroq
#   - Groq API key from .env
#
# LLM PROMPT STRUCTURE:
#   System: "You are a senior credit analyst at a major bank.
#            Your job is to interpret financial ratios and assign a
#            preliminary internal credit rating.
#            Use the rating mapping guidelines provided.
#            Output ONLY valid JSON matching the CreditAnalystOutput schema."
#   User:   [formatted ratio table] + [research analyst summary] + [schema]
#
# ERROR HANDLING:
#   - If ratio is None: note as unavailable, do not attempt to interpret it
#   - If majority of ratios are None: flag low confidence in output
#   - If LLM output fails Pydantic validation: retry up to 2 times

import os
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from src.schemas.models import CreditAnalystOutput, InternalRating

load_dotenv()

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.1
)


def format_ratio_table(ratio_table: dict) -> str:
    """
    Formats ratio dict as readable markdown table for LLM prompt.
    TODO: Implement in notebooks/02_agent_testing.ipynb
    """
    # STUB
    raise NotImplementedError("Implement in notebooks/02_agent_testing.ipynb")


def run_credit_analyst(state: dict) -> dict:
    """
    Runs the Credit Analyst agent.

    Input: state (dict) — LangGraph pipeline state
    Output: updated state dict with credit_analyst_output populated

    TODO: Build and test in notebooks/02_agent_testing.ipynb
    Steps:
        1. Extract ratio_table from state
        2. Format as markdown table using format_ratio_table()
        3. Build LLM prompt with ratios + rating guidelines + schema
        4. Call LLM and parse CreditAnalystOutput
        5. Retry up to 2 times if validation fails
        6. Write output to state
    """
    # STUB
    raise NotImplementedError(
        "run_credit_analyst not yet implemented. "
        "Build in notebooks/02_agent_testing.ipynb first."
    )