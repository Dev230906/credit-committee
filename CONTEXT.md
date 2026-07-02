# LLM-as-Credit-Committee — Context Document

## What This Project Is
Four-agent AI pipeline replicating a bank credit committee.
Analyzes US large cap listed companies using public data only.
Produces a structured credit memo with internal rating and PD estimate.
Portfolio project for credit risk and fintech roles.

## Current Status
Week 1 — Project skeleton created. Starting data pipeline.
Current file in progress: None yet.
Last working module: None yet.
Known issues: None yet.

## Stack
- LLM: LLaMA 3.3 70B via Groq (langchain-groq)
- Orchestration: LangGraph
- Financial data: yfinance
- Filings: sec-edgar-downloader + EDGAR API
- Transcripts: Motley Fool scraper
- Macro: FRED API (fredapi)
- RAG: LlamaIndex + ChromaDB + sentence-transformers
- Structured output: Pydantic
- Interface: Streamlit (Bloomberg dark navy, multi-page)
- PDF: ReportLab
- Tracking: MLflow (local)

## Agents
1. Research Analyst — qualitative signals from filings + transcript
2. Credit Analyst — ratio computation + preliminary rating
3. Devil's Advocate — adversarial bear case
4. Orchestrator — final credit memo synthesis

## Rating Scale
AAA, AA, A, BBB, BB, B, CCC, CC, C, D
PD mapped to Moody's historical default rates by category

## Module Status
| Module | Status |
|--------|--------|
| src/data/resolver.py | Not started |
| src/data/financials.py | Not started |
| src/data/edgar.py | Not started |
| src/data/transcripts.py | Not started |
| src/data/macro.py | Not started |
| src/rag/indexer.py | Not started |
| src/agents/research_analyst.py | Not started |
| src/agents/credit_analyst.py | Not started |
| src/agents/devil_advocate.py | Not started |
| src/agents/orchestrator.py | Not started |
| src/schemas/models.py | Not started |
| src/graph.py | Not started |
| app.py | Not started |

## Session Log
### [Date]
- Created project skeleton
- Installed dependencies
- Got Groq and FRED API keys