# src/agents/research_analyst.py
# PURPOSE: Agent 1 — Research Analyst
#
# ROLE: Gathers and synthesizes qualitative information from SEC filings
# and earnings call transcripts. Does NOT form opinions — compiles facts.
#
# INPUTS (from LangGraph state):
#   - state.ticker: company ticker
#   - state.legal_name: company legal name
#   - state.sector: company sector
#   - state.mda: MD&A section text from edgar.py
#   - state.risk_factors: Risk Factors section text from edgar.py
#   - state.full_text: full filing text from edgar.py
#   - state.transcript_text: earnings call transcript from transcripts.py
#   - state.transcript_quarter: quarter label e.g. "Q2 2026"
#
# PROCESS:
#   1. Build ChromaDB retriever from filing text using indexer.py
#   2. Run 6 targeted queries against the index:
#      Q1: "What is the company's primary business model and revenue sources?"
#      Q2: "What does management say about liquidity and near-term obligations?"
#      Q3: "What debt facilities and covenants does the company have?"
#      Q4: "Is there any going concern language from auditor or management?"
#      Q5: "What are the top risk factors disclosed by management?"
#      Q6: "Has management changed language around key risks vs prior periods?"
#   3. Summarize transcript for management tone assessment
#   4. Produce ResearchAnalystOutput Pydantic object
#
# OUTPUTS (written to LangGraph state):
#   - state.research_analyst_output: ResearchAnalystOutput as dict
#   - state.current_stage: "research_analyst_complete"
#
# DEPENDENCIES:
#   - src/rag/indexer.py: build_filing_index(), query_filing()
#   - src/schemas/models.py: ResearchAnalystOutput, ManagementTone
#   - langchain_groq: ChatGroq
#   - Groq API key from .env
#
# LLM PROMPT STRUCTURE:
#   System: "You are a senior credit research analyst at a major bank.
#            Your job is to extract specific qualitative credit risk signals
#            from SEC filings and earnings call transcripts.
#            Be precise, factual, and reference specific sections.
#            Output ONLY valid JSON matching the ResearchAnalystOutput schema."
#   User:   [filing chunks from ChromaDB] + [transcript text] + [schema]
#
# ERROR HANDLING:
#   - If filing data missing: set going_concern_flag=False, note in observations
#   - If transcript missing: set transcript_available=False, skip tone assessment
#   - If LLM output fails Pydantic validation: retry up to 2 times
#   - If all retries fail: raise RuntimeError with descriptive message

import os
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from src.schemas.models import ResearchAnalystOutput, ManagementTone
from src.rag.indexer import build_filing_index, query_filing

load_dotenv()

# Initialize LLM
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.1
)

# Queries run against ChromaDB index
FILING_QUERIES = [
    "What is the company's primary business model and main revenue sources?",
    "What does management say about liquidity, cash position, and ability to meet near-term obligations?",
    "What debt facilities, credit agreements, and covenants does the company have?",
    "Is there any going concern language from the auditor or management?",
    "What are the top risk factors disclosed by management?",
    "Has management changed language around any key risks compared to prior periods?"
]


def run_research_analyst(state: dict) -> dict:
    """
    Runs the Research Analyst agent.

    Input: state (dict) — LangGraph pipeline state
    Output: updated state dict with research_analyst_output populated

    TODO: Build and test this in notebooks/02_agent_testing.ipynb first.
    Steps:
        1. Build filing index using build_filing_index()
        2. Run FILING_QUERIES against index using query_filing()
        3. Combine query results + transcript into LLM prompt
        4. Call LLM with ResearchAnalystOutput schema in prompt
        5. Parse and validate JSON output with Pydantic
        6. Retry up to 2 times if validation fails
        7. Write output to state
    """
    # STUB — to be implemented in notebooks/02_agent_testing.ipynb
    raise NotImplementedError(
        "run_research_analyst not yet implemented. "
        "Build in notebooks/02_agent_testing.ipynb first."
    )