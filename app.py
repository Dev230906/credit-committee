import streamlit as st
import sys
import os
import time
import json
sys.path.insert(0, os.path.abspath('.'))

from src.graph import build_graph, get_initial_state

# ─────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────
st.set_page_config(
    page_title="Credit Committee AI",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────
# BLOOMBERG DARK NAVY THEME
# ─────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #0a0e1a; color: #e0e0e0; }
    [data-testid="stSidebar"] {
        background-color: #0d1117;
        border-right: 1px solid #1e2d3d;
    }
    [data-testid="stSidebar"] * { color: #e0e0e0 !important; }
    h1, h2, h3 {
        color: #ff6600 !important;
        font-family: 'Courier New', monospace !important;
    }
    [data-testid="metric-container"] {
        background-color: #0d1117;
        border: 1px solid #1e2d3d;
        border-radius: 4px;
        padding: 10px;
    }
    .stTextInput input {
        background-color: #0d1117 !important;
        color: #ff6600 !important;
        border: 1px solid #ff6600 !important;
        font-family: 'Courier New', monospace !important;
        font-size: 1.2rem !important;
    }
    .stButton button {
        background-color: #ff6600 !important;
        color: #0a0e1a !important;
        border: none !important;
        font-weight: bold !important;
        font-family: 'Courier New', monospace !important;
        border-radius: 2px !important;
    }
    .stButton button:hover { background-color: #cc5200 !important; }
    .streamlit-expanderHeader {
        background-color: #0d1117 !important;
        color: #ff6600 !important;
        border: 1px solid #1e2d3d !important;
    }
    .stDataFrame { background-color: #0d1117 !important; }
    p, li, span { color: #e0e0e0 !important; }
    hr { border-color: #1e2d3d !important; }
    .stAlert {
        background-color: #0d1117 !important;
        border: 1px solid #1e2d3d !important;
    }
    .rating-badge {
        font-size: 2.5rem;
        font-weight: bold;
        font-family: 'Courier New', monospace;
        padding: 8px 20px;
        border-radius: 4px;
        display: inline-block;
    }
    .rating-ig {
        background-color: #003300;
        color: #00ff00;
        border: 1px solid #00ff00;
    }
    .rating-hy {
        background-color: #332200;
        color: #ff6600;
        border: 1px solid #ff6600;
    }
    .rating-distressed {
        background-color: #330000;
        color: #ff0000;
        border: 1px solid #ff0000;
    }
    .section-header {
        background-color: #0d1117;
        border-left: 3px solid #ff6600;
        padding: 8px 12px;
        margin: 10px 0;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        color: #ff6600 !important;
        letter-spacing: 0.1em;
        text-transform: uppercase;
    }
    .agent-card {
        background-color: #0d1117;
        border: 1px solid #1e2d3d;
        border-radius: 4px;
        padding: 15px;
        margin: 8px 0;
    }
    .devil-card {
        background-color: #0d1117;
        border: 1px solid #cc0000;
        border-radius: 4px;
        padding: 15px;
        margin: 8px 0;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────
def init_session_state():
    defaults = {
        "pipeline":          None,
        "thread_config":     None,
        "pipeline_running":  False,
        "pipeline_complete": False,
        "awaiting_input":    False,
        "current_stage":     "idle",
        "final_state":       None,
        "ticker":            "",
        "stage_log":         [],
        "errors":            [],
        "warnings":          []
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session_state()


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
def clean(val: str) -> str:
    """Strips enum prefixes from string values."""
    return str(val).replace("InternalRating.", "").replace(
        "LendingDecision.", "").replace(
        "ManagementTone.", "").replace(
        "ConfidenceLevel.", "").replace(
        "RiskProbability.", "")


def get_rating_class(rating: str) -> str:
    rating = clean(rating)
    if rating in ["AAA", "AA", "A", "BBB"]:
        return "rating-ig"
    elif rating in ["BB", "B"]:
        return "rating-hy"
    return "rating-distressed"


def format_pd(pd_val) -> str:
    if pd_val is None:
        return "N/A"
    try:
        return f"{float(pd_val) * 100:.2f}%"
    except Exception:
        return "N/A"


def safe_macro_snapshot(snapshot: dict) -> dict:
    """
    Converts macro snapshot to plain serializable dict.
    FRED returns pandas Series — extract scalar values only.
    """
    result = {}
    for k, v in snapshot.items():
        if v is None:
            continue
        try:
            result[k] = {
                "latest_value": float(v.get("latest_value", 0)),
                "direction":    str(v.get("direction", "unknown")),
                "qoq_change":   float(v.get("qoq_change", 0) or 0),
                "latest_date":  str(v.get("latest_date", ""))
            }
        except Exception:
            pass
    return result


def generate_pdf(out: dict, final_state: dict) -> bytes:
    """Generates PDF credit memo using ReportLab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer,
        Table, TableStyle, HRFlowable
    )
    from io import BytesIO

    buffer = BytesIO()
    doc    = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )

    styles  = getSampleStyleSheet()
    navy    = colors.HexColor("#0a0e1a")
    orange  = colors.HexColor("#ff6600")
    white   = colors.white
    gray    = colors.HexColor("#aaaaaa")

    title_style = ParagraphStyle(
        "Title", parent=styles["Heading1"],
        textColor=orange, fontSize=16,
        fontName="Courier-Bold"
    )
    header_style = ParagraphStyle(
        "Header", parent=styles["Heading2"],
        textColor=orange, fontSize=11,
        fontName="Courier-Bold"
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        textColor=colors.black, fontSize=9,
        fontName="Courier"
    )

    story = []

    # Title
    story.append(Paragraph("CREDIT COMMITTEE MEMORANDUM", title_style))
    story.append(Paragraph("CONFIDENTIAL — FOR INTERNAL USE ONLY", body_style))
    story.append(HRFlowable(width="100%", color=orange))
    story.append(Spacer(1, 0.3*cm))

    # Company header
    rating   = clean(out.get("final_rating", "N/A"))
    decision = clean(out.get("lending_decision", "N/A"))
    story.append(Paragraph(
        f"{out.get('company_name', 'N/A')} ({out.get('ticker', '')})",
        header_style
    ))
    story.append(Paragraph(
        f"Sector: {out.get('sector', 'N/A')} | "
        f"Analysis Date: {out.get('analysis_date', 'N/A')}",
        body_style
    ))
    story.append(Spacer(1, 0.3*cm))

    # Decision table
    pd_12m = format_pd(out.get("pd_12month"))
    pd_3y  = format_pd(out.get("pd_3year"))
    conf   = clean(out.get("confidence_level", "N/A"))

    decision_data = [
        ["INTERNAL RATING", "DECISION", "12M PD", "3Y PD", "CONFIDENCE"],
        [rating, decision, pd_12m, pd_3y, conf]
    ]
    decision_table = Table(decision_data, colWidths=[3*cm, 3*cm, 3*cm, 3*cm, 3*cm])
    decision_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), orange),
        ("TEXTCOLOR",   (0, 0), (-1, 0), white),
        ("FONTNAME",    (0, 0), (-1, 0), "Courier-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 9),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME",    (0, 1), (-1, 1), "Courier-Bold"),
        ("FONTSIZE",    (0, 1), (-1, 1), 11),
        ("GRID",        (0, 0), (-1, -1), 0.5, gray),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
    ]))
    story.append(decision_table)
    story.append(Spacer(1, 0.5*cm))

    # Risk factors
    story.append(Paragraph("TOP RISK FACTORS", header_style))
    story.append(HRFlowable(width="100%", color=orange))
    for rf in out.get("top_risk_factors", []):
        sev = rf.get("severity", "Low")
        story.append(Paragraph(
            f"[{sev.upper()}] {rf.get('rank', '')}. {rf.get('factor', 'N/A')}",
            ParagraphStyle("RiskHeader", parent=body_style,
                          textColor=colors.red if sev == "High"
                          else orange if sev == "Medium"
                          else colors.HexColor("#ffcc00"),
                          fontName="Courier-Bold")
        ))
        story.append(Paragraph(rf.get("description", "N/A"), body_style))
        story.append(Spacer(1, 0.2*cm))

    # Mitigants
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("MITIGANTS", header_style))
    story.append(HRFlowable(width="100%", color=orange))
    for m in out.get("mitigants", []):
        story.append(Paragraph(f"✓ {m}", body_style))

    # Narrative
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("COMMITTEE NARRATIVE", header_style))
    story.append(HRFlowable(width="100%", color=orange))
    story.append(Paragraph(out.get("narrative_rationale", "N/A"), body_style))

    # Rating summary
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph("RATING COMMITTEE SUMMARY", header_style))
    story.append(HRFlowable(width="100%", color=orange))
    ca_r = clean(out.get("credit_analyst_rating", "N/A"))
    da_r = clean(out.get("devils_advocate_rating", "N/A"))
    rating_data = [
        ["Credit Analyst", "Devil's Advocate", "Final Rating"],
        [ca_r, da_r, rating]
    ]
    rating_table = Table(rating_data, colWidths=[5*cm, 5*cm, 5*cm])
    rating_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), orange),
        ("TEXTCOLOR",   (0, 0), (-1, 0), white),
        ("FONTNAME",    (0, 0), (-1, 0), "Courier-Bold"),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME",    (0, 1), (-1, 1), "Courier-Bold"),
        ("FONTSIZE",    (0, 1), (-1, 1), 12),
        ("GRID",        (0, 0), (-1, -1), 0.5, gray),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
    ]))
    story.append(rating_table)

    doc.build(story)
    return buffer.getvalue()


def run_pipeline_to_interrupt(ticker: str):
    """Runs pipeline up to human input interrupt."""
    pipeline      = build_graph()
    thread_config = {"configurable": {"thread_id": f"{ticker}_{int(time.time())}"}}
    initial_state = get_initial_state(ticker)

    st.session_state["pipeline"]         = pipeline
    st.session_state["thread_config"]    = thread_config
    st.session_state["pipeline_running"] = True
    st.session_state["stage_log"]        = []

    accumulated_state = dict(initial_state)

    for event in pipeline.stream(initial_state, config=thread_config):
        if isinstance(event, dict):
            for node_name, node_output in event.items():
                if node_name != "__end__" and isinstance(node_output, dict):
                    stage = node_output.get("current_stage", "unknown")
                    st.session_state["stage_log"].append(
                        f"✓ {node_name.replace('_', ' ').title()} — {stage}"
                    )
                    st.session_state["current_stage"] = stage
                    accumulated_state.update(node_output)

    # Fix macro_snapshot serialization
    if accumulated_state.get("macro_snapshot"):
        accumulated_state["macro_snapshot"] = safe_macro_snapshot(
            accumulated_state["macro_snapshot"]
        )

    st.session_state["final_state"]      = accumulated_state
    st.session_state["pipeline_running"] = False
    st.session_state["awaiting_input"]   = True


def resume_pipeline(human_input: str):
    """Resumes pipeline after human input."""
    pipeline      = st.session_state["pipeline"]
    thread_config = st.session_state["thread_config"]
    accumulated_state = dict(st.session_state.get("final_state", {}))

    # Extract agent ratings from accumulated state to pass explicitly
    ca_out = accumulated_state.get("credit_analyst_output") or {}
    da_out = accumulated_state.get("devils_advocate_output") or {}
    
    pipeline.update_state(
        config=thread_config,
        values={
            "human_input":              human_input if human_input.strip() else None,
            # Pass full agent outputs explicitly so orchestrator has them
            "credit_analyst_output":    ca_out,
            "devils_advocate_output":   da_out,
            "research_analyst_output":  accumulated_state.get("research_analyst_output") or {},
            "legal_name":               accumulated_state.get("legal_name", ""),
            "ticker":                   accumulated_state.get("ticker", ""),
            "sector":                   accumulated_state.get("sector", ""),
            "macro_narrative":          accumulated_state.get("macro_narrative", ""),
        }
    )

    accumulated_state["human_input"] = human_input if human_input.strip() else None

    for event in pipeline.stream(None, config=thread_config):
        if isinstance(event, dict):
            for node_name, node_output in event.items():
                if node_name != "__end__" and isinstance(node_output, dict):
                    stage = node_output.get("current_stage", "unknown")
                    st.session_state["stage_log"].append(
                        f"✓ {node_name.replace('_', ' ').title()} — {stage}"
                    )
                    st.session_state["current_stage"] = stage
                    accumulated_state.update(node_output)

    st.session_state["final_state"]       = accumulated_state
    st.session_state["awaiting_input"]    = False
    st.session_state["pipeline_complete"] = True


# ─────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='text-align:center; padding: 20px 0;'>
        <div style='font-size:1.5rem; font-weight:bold;
                    color:#ff6600; font-family:Courier New;
                    letter-spacing:0.15em;'>
            CREDIT COMMITTEE AI
        </div>
        <div style='font-size:0.7rem; color:#666;
                    letter-spacing:0.2em; margin-top:4px;'>
            MULTI-AGENT CREDIT ANALYSIS
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")

    page = st.radio(
        "NAVIGATION",
        ["Dashboard", "Agent Outputs", "Credit Memo", "Financials", "Settings"],
        label_visibility="visible"
    )
    st.markdown("---")

    if st.session_state["pipeline_complete"]:
        ticker = st.session_state.get("ticker", "")
        st.markdown(f"""
        <div style='font-size:0.75rem; color:#00ff00; font-family:Courier New;'>
            ● ANALYSIS COMPLETE<br>
            <span style='color:#666;'>{ticker}</span>
        </div>
        """, unsafe_allow_html=True)
    elif st.session_state["pipeline_running"]:
        st.markdown("""
        <div style='font-size:0.75rem; color:#ff6600; font-family:Courier New;'>
            ● PIPELINE RUNNING...
        </div>
        """, unsafe_allow_html=True)
    elif st.session_state["awaiting_input"]:
        st.markdown("""
        <div style='font-size:0.75rem; color:#ffcc00; font-family:Courier New;'>
            ● AWAITING ANALYST INPUT
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style='font-size:0.75rem; color:#666; font-family:Courier New;'>
            ● IDLE
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────
# PAGE 1 — DASHBOARD
# ─────────────────────────────────────────
if page == "Dashboard":
    st.markdown("""
    <div class='section-header'>
        CREDIT COMMITTEE AI — CORPORATE CREDIT ANALYSIS SYSTEM
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])
    with col1:
        ticker_input = st.text_input(
            "ENTER TICKER SYMBOL",
            placeholder="e.g. AAPL, BA, NVDA",
            value=st.session_state.get("ticker", "")
        ).upper().strip()
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        run_button = st.button("▶ RUN ANALYSIS", use_container_width=True)

    if run_button and ticker_input:
        st.session_state["ticker"]            = ticker_input
        st.session_state["pipeline_complete"] = False
        st.session_state["awaiting_input"]    = False
        st.session_state["final_state"]       = None
        st.session_state["stage_log"]         = []
        with st.spinner(f"Running credit committee analysis for {ticker_input}..."):
            run_pipeline_to_interrupt(ticker_input)
        st.rerun()

    if st.session_state["stage_log"]:
        st.markdown("<div class='section-header'>PIPELINE PROGRESS</div>",
                    unsafe_allow_html=True)
        for log in st.session_state["stage_log"]:
            st.markdown(f"""
            <div style='font-family:Courier New; font-size:0.8rem;
                        color:#00ff00; padding:2px 0;'>{log}</div>
            """, unsafe_allow_html=True)

    if st.session_state["awaiting_input"]:
        st.markdown("---")
        st.markdown("<div class='section-header'>ANALYST OVERRIDE — OPTIONAL</div>",
                    unsafe_allow_html=True)
        st.markdown("""
        <div style='font-family:Courier New; font-size:0.8rem; color:#aaa;'>
            The committee has completed its analysis. You may inject an analyst
            view before the final decision is rendered. Leave blank to proceed.
        </div>
        """, unsafe_allow_html=True)
        human_input = st.text_area(
            "ANALYST VIEW",
            placeholder="e.g. Strong defense backlog provides revenue stability...",
            height=100
        )
        if st.button("▶ RUN ORCHESTRATOR", use_container_width=True):
            with st.spinner("Synthesizing final credit memo..."):
                resume_pipeline(human_input)
            st.rerun()

    if st.session_state["pipeline_complete"]:
        final_state = st.session_state["final_state"]
        out         = final_state.get("orchestrator_output", {}) if final_state else {}

        if out:
            st.markdown("---")
            st.markdown("<div class='section-header'>COMMITTEE DECISION</div>",
                        unsafe_allow_html=True)

            rating   = clean(out.get("final_rating", "N/A"))
            decision = clean(out.get("lending_decision", "N/A"))
            css_cls  = get_rating_class(rating)

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"""
                <div class='agent-card' style='text-align:center;'>
                    <div style='font-size:0.7rem; color:#666;
                                font-family:Courier New;'>INTERNAL RATING</div>
                    <div class='rating-badge {css_cls}'>{rating}</div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                dc = ("#00ff00" if decision == "Approve"
                      else "#ff6600" if decision == "Conditional"
                      else "#ff0000")
                st.markdown(f"""
                <div class='agent-card' style='text-align:center;'>
                    <div style='font-size:0.7rem; color:#666;
                                font-family:Courier New;'>DECISION</div>
                    <div style='font-size:1.8rem; font-weight:bold;
                                color:{dc}; font-family:Courier New;'>
                        {decision}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col3:
                st.markdown(f"""
                <div class='agent-card' style='text-align:center;'>
                    <div style='font-size:0.7rem; color:#666;
                                font-family:Courier New;'>12M PD</div>
                    <div style='font-size:1.8rem; font-weight:bold;
                                color:#ff6600; font-family:Courier New;'>
                        {format_pd(out.get('pd_12month'))}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col4:
                st.markdown(f"""
                <div class='agent-card' style='text-align:center;'>
                    <div style='font-size:0.7rem; color:#666;
                                font-family:Courier New;'>3Y PD</div>
                    <div style='font-size:1.8rem; font-weight:bold;
                                color:#ff6600; font-family:Courier New;'>
                        {format_pd(out.get('pd_3year'))}
                    </div>
                </div>
                """, unsafe_allow_html=True)

            errors   = final_state.get("errors", []) if final_state else []
            warnings = final_state.get("warnings", []) if final_state else []
            for e in errors:
                st.error(f"Error: {e}")
            for w in warnings:
                st.warning(f"Warning: {w}")


# ─────────────────────────────────────────
# PAGE 2 — AGENT OUTPUTS
# ─────────────────────────────────────────
elif page == "Agent Outputs":
    st.markdown("<div class='section-header'>AGENT REASONING TRACES</div>",
                unsafe_allow_html=True)

    if not st.session_state["pipeline_complete"] and not st.session_state["awaiting_input"]:
        st.info("Run an analysis from the Dashboard to view agent outputs.")
    else:
        final_state = st.session_state.get("final_state", {}) or {}

        # Agent 1
        ra_output = final_state.get("research_analyst_output") or {}
        with st.expander("AGENT 1 — RESEARCH ANALYST", expanded=True):
            if ra_output:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Business Summary**")
                    st.write(ra_output.get("business_summary", "N/A"))
                    st.markdown("**Liquidity Assessment**")
                    st.write(ra_output.get("liquidity_assessment", "N/A"))
                with col2:
                    st.markdown("**Management Tone**")
                    st.markdown(f"`{clean(ra_output.get('management_tone', 'N/A'))}`")
                    st.markdown("**Going Concern Flag**")
                    gc = ra_output.get("going_concern_flag", False)
                    st.markdown(f"{'🔴 YES' if gc else '🟢 NO'}")
                    st.markdown("**Covenant Observations**")
                    st.write(ra_output.get("covenant_observations", "N/A"))
                st.markdown("**Top Risk Factors**")
                for rf in ra_output.get("risk_factors", []):
                    st.markdown(f"**{rf.get('rank', '')}. {rf.get('description', '')}**")
                    st.caption(f"Source: {rf.get('source', 'N/A')}")
            else:
                st.info("Research Analyst output not yet available.")

        # Agent 2
        ca_output = final_state.get("credit_analyst_output") or {}
        with st.expander("AGENT 2 — CREDIT ANALYST", expanded=True):
            if ca_output:
                metrics = [
                    ("Debt/EBITDA",       ca_output.get("debt_to_ebitda"),     "x"),
                    ("Interest Coverage", ca_output.get("interest_coverage"),  "x"),
                    ("Current Ratio",     ca_output.get("current_ratio"),      "x"),
                    ("FCF to Debt",       ca_output.get("fcf_to_debt"),        "x"),
                    ("Net Debt/EBITDA",   ca_output.get("net_debt_to_ebitda"), "x"),
                    ("DSCR",              ca_output.get("dscr"),               "x"),
                    ("Altman Z",          ca_output.get("altman_z"),           ""),
                    ("Z-Zone",            ca_output.get("altman_zone"),        ""),
                ]
                cols = st.columns(4)
                for i, (label, val, suffix) in enumerate(metrics):
                    with cols[i % 4]:
                        display = f"{val}{suffix}" if val is not None else "N/A"
                        st.metric(label, display)

                st.markdown("**Trends**")
                tcol1, tcol2, tcol3 = st.columns(3)
                with tcol1:
                    st.metric("Leverage", ca_output.get("leverage_trend", "N/A"))
                with tcol2:
                    st.metric("Coverage", ca_output.get("coverage_trend", "N/A"))
                with tcol3:
                    st.metric("Cashflow", ca_output.get("cashflow_trend", "N/A"))

                prelim = clean(ca_output.get("preliminary_rating", "N/A"))
                st.markdown(f"**Preliminary Rating:** ### `{prelim}`")
                st.write(ca_output.get("preliminary_rating_rationale", "N/A"))
                st.markdown("**Quantitative Narrative**")
                st.write(ca_output.get("quantitative_narrative", "N/A"))
            else:
                st.info("Credit Analyst output not yet available.")

        # Agent 3
        da_output = final_state.get("devils_advocate_output") or {}
        with st.expander("AGENT 3 — DEVIL'S ADVOCATE ⚠️", expanded=True):
            if da_output:
                counter = clean(da_output.get("counter_rating", "N/A"))
                st.markdown(f"**Counter Rating:** `{counter}`")
                st.markdown(f"**Default Trigger:** {da_output.get('most_likely_default_trigger', 'N/A')}")
                st.markdown(f"**Macro Vulnerability:** {da_output.get('macro_vulnerability', 'N/A')}")
                st.markdown("**Bear Case**")
                st.write(da_output.get("bear_case_narrative", "N/A"))
                st.markdown("**Adversarial Risks**")
                for risk in da_output.get("adversarial_risks", []):
                    prob  = risk.get("probability", "N/A")
                    color = ("#ff0000" if prob == "High"
                             else "#ff6600" if prob == "Medium"
                             else "#ffcc00")
                    st.markdown(f"""
                    <div class='devil-card'>
                        <span style='color:{color}; font-weight:bold;'>[{prob}]</span>
                        <strong> {risk.get('risk_description', 'N/A')}</strong><br>
                        <small style='color:#aaa;'>
                            Evidence: {risk.get('filing_evidence', 'N/A')[:200]}
                        </small><br>
                        <small style='color:#888;'>
                            Impact: {risk.get('quantitative_impact', 'N/A')}
                        </small>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Devil's Advocate output not yet available.")

        if st.session_state["pipeline_complete"]:
            hi = final_state.get("human_input")
            if hi:
                with st.expander("SENIOR ANALYST OVERRIDE", expanded=False):
                    st.write(hi)


# ─────────────────────────────────────────
# PAGE 3 — CREDIT MEMO
# ─────────────────────────────────────────
elif page == "Credit Memo":
    st.markdown("<div class='section-header'>CREDIT COMMITTEE MEMORANDUM — CONFIDENTIAL</div>",
                unsafe_allow_html=True)

    if not st.session_state["pipeline_complete"]:
        st.info("Complete an analysis to view the credit memo.")
    else:
        final_state = st.session_state.get("final_state", {}) or {}
        out         = final_state.get("orchestrator_output", {}) or {}

        if not out:
            st.error("Orchestrator output not available.")
        else:
            rating   = clean(out.get("final_rating", "N/A"))
            decision = clean(out.get("lending_decision", "N/A"))
            css_cls  = get_rating_class(rating)

            col1, col2 = st.columns([2, 1])
            with col1:
                st.markdown(f"""
                <div style='font-family:Courier New;'>
                    <div style='font-size:1.2rem; color:#ff6600; font-weight:bold;'>
                        {out.get('company_name', 'N/A')}
                    </div>
                    <div style='font-size:0.8rem; color:#666;'>
                        {out.get('ticker', '')} | {out.get('sector', '')} |
                        Analysis Date: {out.get('analysis_date', 'N/A')}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                st.markdown(f"""
                <div style='text-align:right;'>
                    <div class='rating-badge {css_cls}'>{rating}</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")

            col1, col2, col3, col4 = st.columns(4)
            dc   = ("#00ff00" if decision == "Approve"
                    else "#ff6600" if decision == "Conditional"
                    else "#ff0000")
            conf = clean(out.get("confidence_level", "N/A"))
            cc   = ("#00ff00" if conf == "High"
                    else "#ff6600" if conf == "Medium"
                    else "#ff0000")

            for col, label, val, color in [
                (col1, "DECISION",   decision.upper(), dc),
                (col2, "12M PD",     format_pd(out.get("pd_12month")), "#ff6600"),
                (col3, "3Y PD",      format_pd(out.get("pd_3year")),   "#ff6600"),
                (col4, "CONFIDENCE", conf.upper(), cc),
            ]:
                with col:
                    st.markdown(f"""
                    <div class='agent-card' style='text-align:center;'>
                        <div style='font-size:0.7rem; color:#666;
                                    font-family:Courier New;'>{label}</div>
                        <div style='font-size:1.5rem; font-weight:bold;
                                    color:{color}; font-family:Courier New;'>
                            {val}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("<div class='section-header'>TOP RISK FACTORS</div>",
                        unsafe_allow_html=True)
            for rf in out.get("top_risk_factors", []):
                sev   = rf.get("severity", "Low")
                color = ("#ff0000" if sev == "High"
                         else "#ff6600" if sev == "Medium"
                         else "#ffcc00")
                st.markdown(f"""
                <div class='agent-card'>
                    <span style='color:{color}; font-weight:bold;
                                 font-family:Courier New;'>[{sev.upper()}]</span>
                    <strong style='color:#ff6600;'>
                        {rf.get('rank', '')}. {rf.get('factor', 'N/A')}
                    </strong><br>
                    <span style='color:#aaa; font-size:0.85rem;'>
                        {rf.get('description', 'N/A')}
                    </span>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<div class='section-header'>MITIGANTS</div>",
                        unsafe_allow_html=True)
            for m in out.get("mitigants", []):
                st.markdown(f"""
                <div style='font-family:Courier New; font-size:0.85rem;
                            color:#00ff00; padding:3px 0;'>✓ {m}</div>
                """, unsafe_allow_html=True)

            if decision == "Conditional" and out.get("decision_conditions"):
                st.markdown("<div class='section-header'>CONDITIONS</div>",
                            unsafe_allow_html=True)
                st.write(out["decision_conditions"])

            st.markdown("<div class='section-header'>COMMITTEE NARRATIVE</div>",
                        unsafe_allow_html=True)
            st.markdown(f"""
            <div class='agent-card' style='font-size:0.9rem;
                        line-height:1.6; color:#e0e0e0;'>
                {out.get('narrative_rationale', 'N/A')}
            </div>
            """, unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("<div class='section-header'>RATING COMMITTEE SUMMARY</div>",
                        unsafe_allow_html=True)
            rcol1, rcol2, rcol3 = st.columns(3)
            with rcol1:
                st.metric("Credit Analyst",  clean(out.get("credit_analyst_rating", "N/A")))
            with rcol2:
                st.metric("Devil's Advocate", clean(out.get("devils_advocate_rating", "N/A")))
            with rcol3:
                st.metric("Final Rating", rating)

            st.markdown("---")
            # PDF download — implemented
            try:
                pdf_bytes = generate_pdf(out, final_state)
                st.download_button(
                    label="⬇ DOWNLOAD PDF MEMO",
                    data=pdf_bytes,
                    file_name=f"credit_memo_{out.get('ticker', 'unknown')}_{out.get('analysis_date', 'today')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"PDF generation failed: {e}")


# ─────────────────────────────────────────
# PAGE 4 — FINANCIALS
# ─────────────────────────────────────────
elif page == "Financials":
    st.markdown("<div class='section-header'>FINANCIAL DATA & MACRO CONTEXT</div>",
                unsafe_allow_html=True)

    if not st.session_state["pipeline_complete"] and not st.session_state["awaiting_input"]:
        st.info("Run an analysis to view financial data.")
    else:
        final_state = st.session_state.get("final_state", {}) or {}
        ratio_table = final_state.get("ratio_table", {}) or {}
        ratios      = ratio_table.get("ratios", {}) or {}

        if ratios:
            st.markdown("<div class='section-header'>CREDIT RATIOS</div>",
                        unsafe_allow_html=True)
            ratio_list = [
                ("Debt / EBITDA",     ratios.get("debt_to_ebitda"),     "x"),
                ("Interest Coverage", ratios.get("interest_coverage"),  "x"),
                ("Current Ratio",     ratios.get("current_ratio"),      "x"),
                ("FCF to Debt",       ratios.get("fcf_to_debt"),        "x"),
                ("Net Debt/EBITDA",   ratios.get("net_debt_to_ebitda"), "x"),
                ("DSCR",              ratios.get("dscr"),               "x"),
                ("Altman Z-Score",    ratios.get("altman_z"),           ""),
                ("Altman Zone",       ratios.get("altman_zone"),        ""),
            ]
            cols = st.columns(4)
            for i, (label, val, suffix) in enumerate(ratio_list):
                with cols[i % 4]:
                    display = f"{val}{suffix}" if val is not None else "N/A"
                    st.metric(label, display)
        else:
            st.info("Financial ratio data not available.")

        macro_narrative = final_state.get("macro_narrative")
        if macro_narrative:
            st.markdown("---")
            st.markdown("<div class='section-header'>MACRO CONTEXT</div>",
                        unsafe_allow_html=True)
            st.markdown(f"""
            <div class='agent-card' style='font-size:0.9rem;
                        line-height:1.6; color:#e0e0e0;'>
                {macro_narrative}
            </div>
            """, unsafe_allow_html=True)

        macro_snapshot = final_state.get("macro_snapshot", {}) or {}
        if macro_snapshot:
            st.markdown("<div class='section-header'>MACRO SNAPSHOT</div>",
                        unsafe_allow_html=True)
            cols = st.columns(5)
            for i, (series_id, data) in enumerate(macro_snapshot.items()):
                if data and isinstance(data, dict):
                    with cols[i % 5]:
                        direction_symbol = (
                            "▲" if data.get("direction") == "up" else "▼"
                        )
                        direction_color = (
                            "#00ff00" if data.get("direction") == "up"
                            else "#ff0000"
                        )
                        try:
                            qoq = abs(float(data.get("qoq_change", 0) or 0))
                        except Exception:
                            qoq = 0
                        st.markdown(f"""
                        <div class='agent-card' style='text-align:center;'>
                            <div style='font-size:0.65rem; color:#666;
                                        font-family:Courier New;'>{series_id}</div>
                            <div style='font-size:1.2rem; font-weight:bold;
                                        color:#ff6600; font-family:Courier New;'>
                                {data.get('latest_value', 'N/A')}
                            </div>
                            <div style='font-size:0.8rem; color:{direction_color};'>
                                {direction_symbol} {qoq:.2f}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)


# ─────────────────────────────────────────
# PAGE 5 — SETTINGS
# ─────────────────────────────────────────
elif page == "Settings":
    st.markdown("<div class='section-header'>SYSTEM SETTINGS</div>",
                unsafe_allow_html=True)

    st.markdown("**Clear ChromaDB Cache**")
    st.caption("Clears stored filing indexes. Next run will re-index from scratch.")
    clear_ticker = st.text_input("Ticker to clear", placeholder="e.g. AAPL")
    if st.button("CLEAR CACHE"):
        if clear_ticker:
            import chromadb
            try:
                client = chromadb.PersistentClient(path="data/chroma")
                client.delete_collection(f"filing_{clear_ticker.lower()}")
                st.success(f"Cache cleared for {clear_ticker.upper()}")
            except Exception as e:
                st.error(f"Failed: {e}")

    st.markdown("---")
    st.markdown("**Pipeline Status**")
    st.json({
        "pipeline_running":  st.session_state.get("pipeline_running"),
        "pipeline_complete": st.session_state.get("pipeline_complete"),
        "awaiting_input":    st.session_state.get("awaiting_input"),
        "current_stage":     st.session_state.get("current_stage"),
        "ticker":            st.session_state.get("ticker"),
        "stage_log":         st.session_state.get("stage_log", [])
    })

    st.markdown("---")
    if st.button("RESET SESSION"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()