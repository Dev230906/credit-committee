# src/schemas/models.py
# PURPOSE: Pydantic output schemas for all four agents.
# Every agent produces a validated Pydantic object as output.
# These schemas are passed between agents via LangGraph state.
# If an agent's LLM output fails validation, the pipeline retries.

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


# --- Rating Scale ---
# Simplified 10-grade agency-mapped scale (no +/- notches)
# Moody's equivalent: Aaa, Aa, A, Baa, Ba, B, Caa, Ca, C, D
class InternalRating(str, Enum):
    AAA = "AAA"
    AA  = "AA"
    A   = "A"
    BBB = "BBB"
    BB  = "BB"
    B   = "B"
    CCC = "CCC"
    CC  = "CC"
    C   = "C"
    D   = "D"


# --- Moody's Historical Default Rate Table ---
# Source: Moody's Annual Default Study
# Maps internal rating to (12-month PD, 3-year PD)
MOODYS_DEFAULT_RATES = {
    "AAA": (0.0001, 0.0003),
    "AA":  (0.0002, 0.0006),
    "A":   (0.0006, 0.0020),
    "BBB": (0.0018, 0.0060),
    "BB":  (0.0120, 0.0400),
    "B":   (0.0350, 0.1400),
    "CCC": (0.1500, 0.3500),
    "CC":  (0.2500, 0.5000),
    "C":   (0.4000, 0.7000),
    "D":   (1.0000, 1.0000),
}


def get_pd_from_rating(rating: str) -> tuple:
    """
    Returns (pd_12month, pd_3year) for a given rating.
    Falls back to B-rated defaults if rating not found.
    """
    return MOODYS_DEFAULT_RATES.get(rating, (0.035, 0.14))


# --- Management Tone Scale ---
class ManagementTone(str, Enum):
    CONFIDENT  = "Confident"
    CAUTIOUS   = "Cautious"
    DEFENSIVE  = "Defensive"
    DISTRESSED = "Distressed"


# --- Lending Decision ---
class LendingDecision(str, Enum):
    APPROVE     = "Approve"
    CONDITIONAL = "Conditional"
    DECLINE     = "Decline"


# --- Confidence Level ---
class ConfidenceLevel(str, Enum):
    HIGH   = "High"
    MEDIUM = "Medium"
    LOW    = "Low"


# --- Adversarial Risk Probability ---
class RiskProbability(str, Enum):
    HIGH   = "High"
    MEDIUM = "Medium"
    LOW    = "Low"


# ============================================================
# AGENT 1 OUTPUT: Research Analyst
# ============================================================
class RiskFactor(BaseModel):
    """Single risk factor identified by Research Analyst."""
    rank        : int    = Field(..., description="Rank by severity, 1 = most severe")
    description : str    = Field(..., description="Risk factor description")
    source      : str    = Field(..., description="Where in the filing this was found")


class ResearchAnalystOutput(BaseModel):
    """
    Output schema for Agent 1 — Research Analyst.
    
    This agent reads SEC filings and earnings transcripts and extracts
    qualitative credit risk signals. It does NOT form opinions — it compiles.
    
    Inputs it receives:
        - ChromaDB retriever (query results from 10-K/10-Q)
        - Earnings call transcript text
        - yfinance company metadata (name, sector, description)
    
    This output is passed to Agent 2 (Credit Analyst) and Agent 3 
    (Devil's Advocate) via LangGraph state.
    """

    business_summary    : str = Field(
        ...,
        description="200 word max summary of business model and revenue sources"
    )
    liquidity_assessment : str = Field(
        ...,
        description="Management's stated liquidity position and cash runway"
    )
    covenant_observations : str = Field(
        ...,
        description="Key debt covenants, thresholds, and headroom if disclosed"
    )
    going_concern_flag  : bool = Field(
        ...,
        description="True if auditor or management flagged going concern risk"
    )
    risk_factors        : List[RiskFactor] = Field(
        ...,
        description="Top 5 risk factors ranked by severity"
    )
    management_tone     : ManagementTone = Field(
        ...,
        description="Overall tone assessment from earnings call transcript"
    )
    language_changes    : Optional[str] = Field(
        None,
        description="Notable changes in language vs prior filing if detectable"
    )
    transcript_available : bool = Field(
        ...,
        description="True if earnings call transcript was successfully scraped"
    )


# ============================================================
# AGENT 2 OUTPUT: Credit Analyst
# ============================================================
class CreditAnalystOutput(BaseModel):
    """
    Output schema for Agent 2 — Credit Analyst.
    
    This agent receives the Research Analyst output and the ratio table
    from financials.py. It interprets the quantitative picture and maps
    it to a preliminary internal rating.
    
    Inputs it receives:
        - ResearchAnalystOutput (from Agent 1)
        - ratio_table (dict from get_financial_ratios())
    
    This output is passed to Agent 3 (Devil's Advocate) and Agent 4
    (Orchestrator) via LangGraph state.
    
    Rating mapping guidelines (embedded in agent system prompt):
        AAA/AA : Debt/EBITDA < 1x, Coverage > 15x, Z > 5
        A      : Debt/EBITDA 1-2x, Coverage 8-15x, Z > 4
        BBB    : Debt/EBITDA 2-3x, Coverage 4-8x, Z > 3
        BB     : Debt/EBITDA 3-5x, Coverage 2-4x, Z 2-3
        B      : Debt/EBITDA 5-7x, Coverage 1.5-2x, Z 1.5-2
        CCC    : Debt/EBITDA > 7x, Coverage < 1.5x, Z < 1.8
        CC/C/D : Coverage < 1x, negative FCF, imminent default risk
    """

    # Ratio summary
    debt_to_ebitda      : Optional[float] = Field(None, description="Debt/EBITDA ratio")
    interest_coverage   : Optional[float] = Field(None, description="EBIT/Interest Expense")
    current_ratio       : Optional[float] = Field(None, description="Current Assets/Current Liabilities")
    fcf_to_debt         : Optional[float] = Field(None, description="Free Cash Flow/Total Debt")
    net_debt_to_ebitda  : Optional[float] = Field(None, description="Net Debt/EBITDA")
    dscr                : Optional[float] = Field(None, description="Debt Service Coverage Ratio")
    altman_z            : Optional[float] = Field(None, description="Altman Z-Score")
    altman_zone         : Optional[str]   = Field(None, description="SAFE / GREY / DISTRESS")

    # Trend assessment
    leverage_trend      : str = Field(
        ...,
        description="Improving / Stable / Deteriorating — based on quarterly trend"
    )
    coverage_trend      : str = Field(
        ...,
        description="Improving / Stable / Deteriorating — based on quarterly trend"
    )
    cashflow_trend      : str = Field(
        ...,
        description="Improving / Stable / Deteriorating — based on quarterly trend"
    )

    # Quantitative narrative and rating
    quantitative_narrative  : str = Field(
        ...,
        description="300 word max interpretation of the quantitative picture"
    )
    primary_concern         : str = Field(
        ...,
        description="Single metric most responsible for the preliminary rating"
    )
    preliminary_rating      : InternalRating = Field(
        ...,
        description="Preliminary internal rating based on quantitative analysis"
    )
    preliminary_rating_rationale : str = Field(
        ...,
        description="One paragraph explaining the rating decision"
    )


# ============================================================
# AGENT 3 OUTPUT: Devil's Advocate
# ============================================================
class AdversarialRisk(BaseModel):
    """Single adversarial risk argument."""
    rank                : int           = Field(..., description="Rank by severity")
    risk_description    : str           = Field(..., description="Description of the risk")
    filing_evidence     : str           = Field(..., description="Specific text from filing supporting this risk")
    quantitative_impact : str           = Field(..., description="Estimated financial impact if risk materializes")
    probability         : RiskProbability = Field(..., description="High / Medium / Low")


class DevilsAdvocateOutput(BaseModel):
    """
    Output schema for Agent 3 — Devil's Advocate.
    
    This agent receives Agent 1 and Agent 2 outputs and must produce
    an adversarial bear case. It CANNOT agree with Agent 2's rating.
    Its counter_rating must be at least one notch below Agent 2's
    preliminary_rating.
    
    Inputs it receives:
        - ResearchAnalystOutput (from Agent 1)
        - CreditAnalystOutput (from Agent 2)
        - ChromaDB retriever (for additional filing queries)
    
    This output is passed to Agent 4 (Orchestrator) via LangGraph state.
    
    Adversarial queries this agent runs against ChromaDB:
        1. "What near-term debt maturities does the company face?"
        2. "What contingent liabilities or legal proceedings exist?"
        3. "What assumptions underlie management's forward guidance?"
        4. "What macro or industry headwinds could impair revenue?"
    """

    adversarial_risks       : List[AdversarialRisk] = Field(
        ...,
        description="Minimum 3, maximum 6 adversarial risk arguments"
    )
    most_likely_default_trigger : str = Field(
        ...,
        description="Single most plausible path to default in 12-24 months"
    )
    bear_case_narrative     : str = Field(
        ...,
        description="200 word max bear case summary"
    )
    counter_rating          : InternalRating = Field(
        ...,
        description="Devil's Advocate rating — must be at least one notch below Agent 2"
    )
    macro_vulnerability     : str = Field(
        ...,
        description="How a macro downturn specifically hurts this borrower"
    )


# ============================================================
# AGENT 4 OUTPUT: Orchestrator (Final Credit Memo)
# ============================================================
class FinalRiskFactor(BaseModel):
    """Single risk factor in the final credit memo."""
    rank        : int    = Field(..., description="Rank 1-5 by severity")
    factor      : str    = Field(..., description="Risk factor name")
    description : str    = Field(..., description="Detailed description")
    severity    : str    = Field(..., description="High / Medium / Low")


class OrchestratorOutput(BaseModel):
    """
    Output schema for Agent 4 — Orchestrator.
    
    This agent receives all three prior agent outputs plus macro context
    and optional human analyst input. It synthesizes everything into the
    final credit memo.
    
    Inputs it receives:
        - ResearchAnalystOutput (from Agent 1)
        - CreditAnalystOutput (from Agent 2)
        - DevilsAdvocateOutput (from Agent 3)
        - macro_narrative (str from get_macro_context())
        - human_input (str, optional — from Streamlit injection point)
    
    PD is NOT generated by the LLM — it is looked up from
    MOODYS_DEFAULT_RATES using the final_rating as the key.
    Call get_pd_from_rating(final_rating) after this schema is populated.
    
    This output feeds:
        - Streamlit Credit Memo page (rendered as formatted tables)
        - ReportLab PDF generator
        - MLflow run logger
    """

    # Company context
    company_name    : str = Field(..., description="Legal company name")
    ticker          : str = Field(..., description="Exchange ticker")
    sector          : str = Field(..., description="Company sector")
    analysis_date   : str = Field(..., description="Date of analysis YYYY-MM-DD")

    # Final rating and PD
    # PD fields are populated AFTER schema validation using get_pd_from_rating()
    final_rating    : InternalRating = Field(
        ...,
        description="Final internal rating after committee synthesis"
    )
    pd_12month      : Optional[float] = Field(
        None,
        description="12-month probability of default — populated from Moody's table"
    )
    pd_3year        : Optional[float] = Field(
        None,
        description="3-year probability of default — populated from Moody's table"
    )

    # Risk factors and mitigants
    top_risk_factors : List[FinalRiskFactor] = Field(
        ...,
        description="Top 5 risk factors ranked by severity"
    )
    mitigants       : List[str] = Field(
        ...,
        description="List of factors that reduce default risk"
    )

    # Decision
    lending_decision : LendingDecision = Field(
        ...,
        description="Approve / Conditional / Decline"
    )
    decision_conditions : Optional[str] = Field(
        None,
        description="If Conditional — what conditions must be met"
    )

    # Narrative and confidence
    narrative_rationale : str = Field(
        ...,
        description="400 word committee chair narrative explaining the decision"
    )
    confidence_level    : ConfidenceLevel = Field(
        ...,
        description="High / Medium / Low — based on data completeness and agent agreement"
    )
    confidence_rationale : str = Field(
        ...,
        description="One sentence explaining confidence level"
    )

    # Agent agreement summary
    credit_analyst_rating   : InternalRating = Field(
        ...,
        description="Agent 2 preliminary rating — for reference"
    )
    devils_advocate_rating  : InternalRating = Field(
        ...,
        description="Agent 3 counter rating — for reference"
    )
    human_input_received    : bool = Field(
        ...,
        description="True if human analyst provided input before Orchestrator ran"
    )


# ============================================================
# LANGGRAPH STATE
# ============================================================
class PipelineState(BaseModel):
    """
    Shared state object passed between all LangGraph nodes.
    Each agent reads from and writes to this state.
    
    Flow:
        Input → resolver → financials → edgar → transcripts → 
        macro → indexer → research_analyst → credit_analyst → 
        devil_advocate → human_input → orchestrator → output
    """

    # Input
    ticker          : str = ""

    # Resolved identifiers (from resolver.py)
    legal_name      : str = ""
    cik             : str = ""
    sector          : str = ""
    industry        : str = ""
    market_cap      : Optional[float] = None

    # Financial data (from financials.py)
    ratio_table     : Optional[dict] = None
    raw_financials  : Optional[dict] = None

    # Filing data (from edgar.py)
    mda             : Optional[str] = None
    risk_factors    : Optional[str] = None
    full_text       : Optional[str] = None

    # Transcript (from transcripts.py)
    transcript_text : Optional[str] = None
    transcript_quarter : Optional[str] = None

    # Macro context (from macro.py)
    macro_narrative : Optional[str] = None
    macro_snapshot  : Optional[dict] = None

    # Agent outputs
    research_analyst_output : Optional[dict] = None
    credit_analyst_output   : Optional[dict] = None
    devils_advocate_output  : Optional[dict] = None
    human_input             : Optional[str]  = None
    orchestrator_output     : Optional[dict] = None

    # Pipeline status
    current_stage   : str  = "initialized"
    errors          : List[str] = []
    warnings        : List[str] = []

    class Config:
        arbitrary_types_allowed = True