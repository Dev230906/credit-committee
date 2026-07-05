# LLM-as-Credit-Committee — Context Document

## What This Project Is
Four-agent AI pipeline replicating a bank credit committee.
Analyzes US large cap listed companies using public data only.
Produces a structured credit memo with internal rating and PD estimate.
Portfolio project for credit risk and fintech roles.

## Current Status
Project Completed
Current file in progress: None
Last working module: app.py.


## Stack
- LLM: LLaMA 3.3 70B via Groq (langchain-groq)
- Orchestration: LangGraph
- Financial data: yfinance
- Filings: sec-edgar-downloader + EDGAR API
- Transcripts: StockAnalysis scraper
- Macro: FRED API (fredapi)
- RAG: LlamaIndex + ChromaDB + sentence-transformers
- Structured output: Pydantic
- Interface: Streamlit (Dark navy, multi-page)
- PDF: ReportLab


## Agents
1. Research Analyst — qualitative signals from filings + transcript
2. Credit Analyst — ratio computation + preliminary rating
3. Devil's Advocate — adversarial bear case
4. Orchestrator — final credit memo synthesis

## Rating Scale
AAA, AA, A, BBB, BB, B, CCC, CC, C, D
PD scale inspired by Moody's rating scale

## Module Status
| Module | Status |
|--------|--------|
| src/data/resolver.py | completed |
| src/data/financials.py | completed |
| src/data/edgar.py | completed |
| src/data/transcripts.py | completed |
| src/data/macro.py | completed |
| src/rag/indexer.py | completed |
| src/agents/research_analyst.py | completed |
| src/agents/credit_analyst.py | completed |
| src/agents/devil_advocate.py | completed |
| src/agents/orchestrator.py | completed |
| src/schemas/models.py | completed |
| src/graph.py | completed |
| app.py | completed |

