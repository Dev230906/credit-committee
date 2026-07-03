# src/agents/devil_advocate.py
# PURPOSE: Agent 3 — Devil's Advocate
#
# ROLE: Adversarial agent that finds the bear case exclusively.
# MUST disagree with Agent 2's rating regardless of what it is.
# counter_rating MUST be at least one notch below Agent 2's preliminary_rating.
#
# INPUTS (from LangGraph state):
#   - state.research_analyst_output: ResearchAnalystOutput dict (Agent 1)
#   - state.credit_analyst_output: CreditAnalystOutput dict (Agent 2)
#   - ChromaDB retriever (built from filing index)
#
# PROCESS:
#   1. Load ChromaDB retriever for ticker
#   2. Run 4 adversarial queries against index:
#      Q1: "What near-term debt maturities does the company face?"
#      Q2: "What contingent liabilities or legal proceedings exist?"
#      Q3: "What assumptions underlie management's forward guidance?"
#      Q4: "What macro or industry headwinds could impair revenue or margins?"
#   3. Combine adversarial query results with Agent 1 and Agent 2 outputs
#   4. Build adversarial prompt — explicitly instruct LLM to disagree
#   5. Enforce counter_rating is at least one notch below preliminary_rating
#      Rating order: AAA > AA > A > BBB > BB > B > CCC > CC > C > D
#      Use RATING_ORDER list to enforce this programmatically after LLM output
#   6. Produce DevilsAdvocateOutput Pydantic object
#
# OUTPUTS (written to LangGraph state):
#   - state.devils_advocate_output: DevilsAdvocateOutput as dict
#   - state.current_stage: "devils_advocate_complete"
#
# DEPENDENCIES:
#   - src/rag/indexer.py: build_filing_index(), query_filing()
#   - src/schemas/models.py: DevilsAdvocateOutput, InternalRating
#   - langchain_groq: ChatGroq
#
# LLM PROMPT STRUCTURE:
#   System: "You are the Devil's Advocate in a credit committee.
#            Your ONLY job is to find reasons this borrower will default.
#            You MUST disagree with the Credit Analyst's assessment.
#            Ground every argument in specific filing evidence.
#            Produce minimum 3, maximum 6 adversarial risk arguments.
#            Output ONLY valid JSON matching DevilsAdvocateOutput schema."
#   User:   [adversarial filing chunks] + [Agent 1 output] +
#           [Agent 2 output] + [schema]
#
# RATING ORDER (for enforcing counter_rating constraint):
RATING_ORDER = ["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C", "D"]
#
# ERROR HANDLING:
#   - If counter_rating is not below preliminary_rating: downgrade by one notch
#   - If fewer than 3 adversarial risks produced: retry with stricter prompt
#   - If LLM output fails Pydantic validation: retry up to 2 times

import os
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from src.schemas.models import DevilsAdvocateOutput, InternalRating
from src.rag.indexer import build_filing_index, query_filing

load_dotenv()

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.2  # slightly higher for adversarial creativity
)

ADVERSARIAL_QUERIES = [
    "What near-term debt maturities does the company face and how does it plan to refinance?",
    "What contingent liabilities, legal proceedings, or off-balance-sheet obligations exist?",
    "What assumptions underlie management's forward guidance and how sensitive are they?",
    "What macro or industry headwinds could materially impair revenue or margins?"
]


def enforce_counter_rating(
    counter_rating: str,
    preliminary_rating: str
) -> str:
    """
    Ensures counter_rating is at least one notch below preliminary_rating.
    If not, downgrades by one notch automatically.

    TODO: Implement in notebooks/02_agent_testing.ipynb
    """
    # STUB
    raise NotImplementedError("Implement in notebooks/02_agent_testing.ipynb")


def run_devil_advocate(state: dict) -> dict:
    """
    Runs the Devil's Advocate agent.

    Input: state (dict) — LangGraph pipeline state
    Output: updated state dict with devils_advocate_output populated

    TODO: Build and test in notebooks/02_agent_testing.ipynb
    Steps:
        1. Load ChromaDB retriever for ticker
        2. Run ADVERSARIAL_QUERIES against index
        3. Build adversarial prompt with all inputs
        4. Call LLM and parse DevilsAdvocateOutput
        5. Enforce counter_rating constraint using enforce_counter_rating()
        6. Retry up to 2 times if validation fails
        7. Write output to state
    """
    # STUB
    raise NotImplementedError(
        "run_devil_advocate not yet implemented. "
        "Build in notebooks/02_agent_testing.ipynb first."
    )