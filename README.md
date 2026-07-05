# LLM-as-Credit-Committee

**LLM-as-Credit-Committee** is a multi-agent AI system that simulates the qualitative decision-making process of a corporate credit committee.

Given a company ticker, the system retrieves financial statements and computes credit ratios using **Yahoo Finance**, extracts key sections from the latest **SEC EDGAR 10-K**, incorporates **Federal Reserve** macroeconomic data, and enriches the analysis with the latest earnings call transcript scraped from the web.

The collected information is then analyzed by four specialized AI agents:

* **Research Analyst** – Extracts qualitative insights from filings and transcripts.
* **Credit Analyst** – Evaluates financial health and assigns a preliminary rating.
* **Devil's Advocate** – Challenges the investment thesis by constructing the bear case.
* **Orchestrator** – Synthesizes all perspectives into a structured credit memo.

The application includes a **Streamlit** interface, allows users to provide additional observations before the final decision, and generates a downloadable **PDF credit memo** containing an indicative internal rating, probability of default, and lending recommendation.

