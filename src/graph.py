# src/graph.py
# PURPOSE: LangGraph state graph wiring all four agents together.
#
# GRAPH STRUCTURE:
#   START
#     ↓
#   data_ingestion     — runs all data modules in sequence
#     ↓
#   research_analyst   — Agent 1
#     ↓
#   credit_analyst     — Agent 2
#     ↓
#   devil_advocate     — Agent 3
#     ↓
#   human_input        — pauses for Streamlit injection
#     ↓
#   orchestrator       — Agent 4
#     ↓
#   END
#
# STATE OBJECT: PipelineState from src/schemas/models.py
# All nodes read from and write to this shared state.
#
# HUMAN INPUT NODE:
#   This is an interrupt node — LangGraph pauses execution here.
#   Streamlit reads state.current_stage == "awaiting_human_input"
#   and displays the injection panel.
#   When user clicks "Run Orchestrator", Streamlit writes
#   state.human_input and resumes the graph.
#
# DEPENDENCIES:
#   - src/agents/research_analyst.py: run_research_analyst()
#   - src/agents/credit_analyst.py: run_credit_analyst()
#   - src/agents/devil_advocate.py: run_devil_advocate()
#   - src/agents/orchestrator.py: run_orchestrator()
#   - src/data/financials.py: get_financial_ratios()
#   - src/data/edgar.py: get_filing()
#   - src/data/transcripts.py: get_transcript()
#   - src/data/macro.py: get_macro_context()
#   - src/data/resolver.py: resolve_ticker()
#   - src/schemas/models.py: PipelineState
#
# HOW TO BUILD:
#   1. Import StateGraph from langgraph.graph
#   2. Define state schema as PipelineState
#   3. Add nodes: add_node("research_analyst", run_research_analyst) etc.
#   4. Add edges: add_edge("research_analyst", "credit_analyst") etc.
#   5. Add interrupt before orchestrator node for human input
#   6. Compile graph with graph.compile(interrupt_before=["orchestrator"])
#   7. Run with graph.invoke({"ticker": ticker})
#
# TODO: Build and test in notebooks/02_agent_testing.ipynb
# after all four agents are individually working.

from langgraph.graph import StateGraph, END
from src.schemas.models import PipelineState
from src.agents.research_analyst import run_research_analyst
from src.agents.credit_analyst import run_credit_analyst
from src.agents.devil_advocate import run_devil_advocate
from src.agents.orchestrator import run_orchestrator
from src.data.financials import get_financial_ratios
from src.data.edgar import get_filing
from src.data.transcripts import get_transcript
from src.data.macro import get_macro_context
from src.data.resolver import resolve_ticker


def data_ingestion_node(state: dict) -> dict:
    """
    Runs all data modules and populates state before agents start.

    Steps:
        1. resolve_ticker() — validate and get CIK
        2. get_financial_ratios() — yfinance data + ratio computation
        3. get_filing() — EDGAR 10-K download and text extraction
        4. get_transcript() — stockanalysis.com transcript scrape
        5. get_macro_context() — FRED macro data pull

    TODO: Implement after all data modules are complete (they are).
    """
    # STUB
    raise NotImplementedError(
        "data_ingestion_node not yet implemented. "
        "Build in notebooks/02_agent_testing.ipynb."
    )


def human_input_node(state: dict) -> dict:
    """
    Interrupt node — pauses pipeline for human analyst input.
    Streamlit handles the actual pause/resume via LangGraph interrupt.
    This node just sets the stage flag.
    """
    state["current_stage"] = "awaiting_human_input"
    return state


def build_graph():
    """
    Builds and compiles the LangGraph pipeline.
    Returns compiled graph ready for invocation.

    TODO: Implement after all agents are complete.
    """
    # STUB
    raise NotImplementedError(
        "build_graph not yet implemented. "
        "Implement after all four agents are working."
    )