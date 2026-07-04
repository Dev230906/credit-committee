import json
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
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
    """
    ticker = state["ticker"]
    print(f"Starting data ingestion for {ticker}...")

    # Step 1: Resolve ticker
    resolved = resolve_ticker(ticker)
    if not resolved["status"]["success"]:
        state["errors"].append(
            f"Resolver failed: {resolved['status']['error']}"
        )
        state["current_stage"] = "data_ingestion_failed"
        return state

    state["legal_name"] = resolved["legal_name"]
    state["cik"]        = resolved["cik"]
    state["sector"]     = resolved["sector"]
    state["industry"]   = resolved["industry"]
    state["market_cap"] = resolved["market_cap"]

    # Step 2: Financial ratios
    ratio_data = get_financial_ratios(ticker)
    if ratio_data["status"]["success"]:
        state["ratio_table"]    = ratio_data
        state["raw_financials"] = ratio_data.get("raw", {})
    else:
        state["warnings"].append(
            f"Financial data failed: {ratio_data['status'].get('error')}"
        )

    # Step 3: EDGAR filing
    filing_data = get_filing(ticker, resolved["cik"])
    if filing_data["status"]["success"]:
        state["mda"]          = filing_data["mda"]
        state["risk_factors"] = filing_data["risk_factors"]
        state["full_text"]    = filing_data["full_text"]
    else:
        state["warnings"].append(
            f"Filing failed: {filing_data['status'].get('error')}"
        )

    # Step 4: Transcript
    transcript_data = get_transcript(ticker)
    if transcript_data["status"]["success"]:
        state["transcript_text"]    = transcript_data["transcript_text"]
        state["transcript_quarter"] = transcript_data["quarter"]
    else:
        state["warnings"].append(
            f"Transcript unavailable: {transcript_data['status'].get('error')}"
        )

    # Step 5: Macro context
    macro_data = get_macro_context()
    if macro_data["status"]["success"]:
        state["macro_narrative"] = macro_data["narrative"]
        state["macro_snapshot"]  = macro_data["snapshot"]
    else:
        state["warnings"].append("Macro data unavailable")

    state["current_stage"] = "data_ingestion_complete"
    print(f"Data ingestion complete for {ticker}")
    return state


def human_input_node(state: dict) -> dict:
    """Interrupt node — pauses for human input from Streamlit."""
    state["current_stage"] = "awaiting_human_input"
    return state


def build_graph() -> object:
    """
    Builds and compiles the LangGraph pipeline with memory checkpointer.
    Returns compiled graph ready for invocation.
    """
    graph = StateGraph(dict)

    graph.add_node("data_ingestion",   data_ingestion_node)
    graph.add_node("research_analyst", run_research_analyst)
    graph.add_node("credit_analyst",   run_credit_analyst)
    graph.add_node("devil_advocate",   run_devil_advocate)
    graph.add_node("human_input",      human_input_node)
    graph.add_node("orchestrator",     run_orchestrator)

    graph.set_entry_point("data_ingestion")
    graph.add_edge("data_ingestion",   "research_analyst")
    graph.add_edge("research_analyst", "credit_analyst")
    graph.add_edge("credit_analyst",   "devil_advocate")
    graph.add_edge("devil_advocate",   "human_input")
    graph.add_edge("human_input",      "orchestrator")
    graph.add_edge("orchestrator",     END)

    memory = MemorySaver()
    return graph.compile(
        checkpointer=memory,
        interrupt_before=["orchestrator"]
    )


def get_initial_state(ticker: str) -> dict:
    """Returns a clean initial state for a new pipeline run."""
    return {
        "ticker":                   ticker.upper(),
        "legal_name":               "",
        "cik":                      "",
        "sector":                   "",
        "industry":                 "",
        "market_cap":               None,
        "ratio_table":              None,
        "raw_financials":           None,
        "mda":                      None,
        "risk_factors":             None,
        "full_text":                None,
        "transcript_text":          None,
        "transcript_quarter":       None,
        "macro_narrative":          None,
        "macro_snapshot":           None,
        "research_analyst_output":  None,
        "credit_analyst_output":    None,
        "devils_advocate_output":   None,
        "human_input":              None,
        "orchestrator_output":      None,
        "current_stage":            "initialized",
        "errors":                   [],
        "warnings":                 []
    }