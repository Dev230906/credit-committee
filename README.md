# LLM-as-Credit-Committee

**LLM-as-Credit-Committee** is a multi-agent AI system that simulates the qualitative decision-making process of a corporate credit committee.

Given a company ticker, the system retrieves financial statements and computes credit ratios using **Yahoo Finance**, extracts key sections from the latest **SEC EDGAR 10-K**, incorporates **Federal Reserve** macroeconomic data, and enriches the analysis with the latest earnings call transcript scraped from the web.

The collected information is then analyzed by four specialized AI agents:

* **Research Analyst** – Extracts qualitative insights from filings and transcripts.
* **Credit Analyst** – Evaluates financial health and assigns a preliminary rating.
* **Devil's Advocate** – Challenges the investment thesis by constructing the bear case.
* **Orchestrator** – Synthesizes all perspectives into a structured credit memo.

The application includes a **Streamlit** interface, allows users to provide additional observations before the final decision, and generates a downloadable **PDF credit memo** containing an indicative internal rating, probability of default, and lending recommendation.

Getting Started

Clone the repository:

git clone <repository-url>
cd credit-committee

Create and activate a virtual environment:
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

Install dependencies:

pip install -r requirements.txt

Create a .env file containing:

GROQ_API_KEY=your_key

FRED_API_KEY=your_key

USER_EMAIL=your_email #required for web scraping

Launch the application:

streamlit run app.py
