# src/agents/orchestrator.py
# PURPOSE: Agent 4 — Orchestrator (Credit Committee Chair)
#
# ROLE: Synthesizes all three agent outputs plus macro context and optional
# human input into the final credit memo. Most complex prompt in pipeline.
#
# INPUTS (from LangGraph state):
#   - state.research_analyst_output: ResearchAnalystOutput dict (Agent 1)
#   - state.credit_analyst_output: CreditAnalystOutput dict (Agent 2)
#   - state.devils_advocate_output: DevilsAdvocateOutput dict (Agent 3)
#   - state.macro_narrative: str from get_macro_context()
#   - state.macro_snapshot: dict from get_macro_context()
#   - state.human_input: str or None (from Streamlit injection point)
#
# PROCESS:
#   1. Combine all inputs into synthesis prompt
#   2. Weight inputs:
#      - Human input (if provided): highest weight — override signal
#      - Devil's Advocate risks grounded in filing evidence: high weight
#      - Credit Analyst quantitative assessment: base case
#      - Research Analyst qualitative signals: context
#      - Macro narrative: cycle adjustment
#   3. Determine final_rating by synthesizing above
#   4. Determine lending_decision:
#      - Approve: BBB and above, no material concerns
#      - Conditional: BB or B, manageable risk with conditions
#      - Decline: CCC and below, or B with material imminent risks
#   5. Populate OrchestratorOutput Pydantic object
#   6. After validation: call get_pd_from_rating(final_rating) to populate
#      pd_12month and pd_3year fields
#
# OUTPUTS (written to LangGraph state):
#   - state.orchestrator_output: OrchestratorOutput as dict
#   - state.current_stage: "orchestrator_complete"
#
# DEPENDENCIES:
#   - src/schemas/models.py: OrchestratorOutput, get_pd_from_rating()
#   - langchain_groq: ChatGroq
#
# LLM PROMPT STRUCTURE:
#   System: "You are the chair of a credit committee at a major bank.
#            You have just heard from three analysts and must render a
#            final credit decision. Synthesize all inputs into a structured
#            credit memo. If human input is provided, weight it most heavily.
#            Output ONLY valid JSON matching OrchestratorOutput schema."
#   User:   [Agent 1 output] + [Agent 2 output] + [Agent 3 output] +
#           [macro narrative] + [human input if any] + [schema]
#
# LENDING DECISION MAPPING:
#   Approve     : final_rating in [AAA, AA, A, BBB]
#   Conditional : final_rating in [BB, B]
#   Decline     : final_rating in [CCC, CC, C, D]
#
# ERROR HANDLING:
#   - If LLM output fails Pydantic validation: retry up to 2 times
#   - Always populate pd_12month and pd_3year from MOODYS_DEFAULT_RATES
#     after schema validation — never trust LLM to produce these values

import os
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from src.schemas.models import (
    OrchestratorOutput,
    LendingDecision,
    InternalRating,
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


def determine_lending_decision(rating: str) -> str:
    """
    Maps final rating to lending decision.
    TODO: Implement in notebooks/02_agent_testing.ipynb
    """
    # STUB
    raise NotImplementedError("Implement in notebooks/02_agent_testing.ipynb")


def run_orchestrator(state: dict) -> dict:
    """
    Runs the Orchestrator agent.

    Input: state (dict) — LangGraph pipeline state
    Output: updated state dict with orchestrator_output populated

    TODO: Build and test in notebooks/02_agent_testing.ipynb
    Steps:
        1. Combine all agent outputs into synthesis prompt
        2. Call LLM and parse OrchestratorOutput
        3. Override lending_decision using determine_lending_decision()
        4. Populate pd_12month and pd_3year using get_pd_from_rating()
        5. Retry up to 2 times if validation fails
        6. Write output to state
    """
    # STUB
    raise NotImplementedError(
        "run_orchestrator not yet implemented. "
        "Build in notebooks/02_agent_testing.ipynb first."
    )