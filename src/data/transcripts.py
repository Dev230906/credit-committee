import re
import requests
from bs4 import BeautifulSoup


def get_transcript(ticker: str) -> dict:
    """
    Scrapes most recent earnings call transcript from stockanalysis.com

    Input: ticker (str) — e.g. "AAPL"
    Output: dict with keys:
        - ticker: str
        - transcript_text: str
        - quarter: str (e.g. "Q2 2026")
        - status: dict
    """

    result = {
        "ticker": ticker.upper(),
        "transcript_text": None,
        "quarter": None,
        "status": {}
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    base_url = "https://stockanalysis.com"
    index_url = f"{base_url}/stocks/{ticker.lower()}/transcripts/"

    try:
        # --- Step 1: Get transcripts index page ---
        session = requests.Session()
        index_response = session.get(
            index_url,
            headers=headers,
            timeout=10
        )

        if index_response.status_code != 200:
            result["status"]["success"] = False
            result["status"]["error"] = (
                f"Transcripts index page returned "
                f"{index_response.status_code}"
            )
            return result

        # --- Step 2: Find most recent transcript link ---
        soup = BeautifulSoup(index_response.text, "html.parser")
        links = soup.find_all("a", href=True)

        transcript_links = [
            l["href"] for l in links
            if "transcript" in l["href"].lower()
            and ticker.lower() in l["href"].lower()
            and l["href"] != f"/stocks/{ticker.lower()}/transcripts/"
            and "product-launch" not in l["href"].lower()
        ]

        # Deduplicate while preserving order
        seen = set()
        unique_links = []
        for link in transcript_links:
            if link not in seen:
                seen.add(link)
                unique_links.append(link)

        if not unique_links:
            result["status"]["success"] = False
            result["status"]["error"] = "No transcript links found"
            return result

        most_recent_link = unique_links[0]

        # Extract quarter from URL
        quarter_match = re.search(
            r'(\d+)-(q\d+)-(\d{4})',
            most_recent_link,
            flags=re.IGNORECASE
        )
        if quarter_match:
            result["quarter"] = (
                f"{quarter_match.group(2).upper()} "
                f"{quarter_match.group(3)}"
            )

        # --- Step 3: Fetch transcript page ---
        transcript_url = base_url + most_recent_link
        result["status"]["transcript_url"] = transcript_url

        transcript_response = session.get(
            transcript_url,
            headers={**headers, "Referer": index_url},
            timeout=10
        )

        if transcript_response.status_code != 200:
            result["status"]["success"] = False
            result["status"]["error"] = (
                f"Transcript page returned "
                f"{transcript_response.status_code}"
            )
            return result

        # --- Step 4: Extract text ---
        soup = BeautifulSoup(transcript_response.text, "html.parser")

        for tag in soup(["script", "style"]):
            tag.decompose()

        paragraphs = soup.find_all("p")
        transcript_text = " ".join([
            p.get_text(strip=True)
            for p in paragraphs
            if len(p.get_text(strip=True)) > 20
        ])

        if not transcript_text or len(transcript_text) < 500:
            result["status"]["success"] = False
            result["status"]["error"] = (
                "Transcript text too short — likely blocked"
            )
            return result

        result["transcript_text"] = transcript_text[:50_000]
        result["status"]["char_count"] = len(transcript_text)
        result["status"]["success"] = True

    except Exception as e:
        result["status"]["success"] = False
        result["status"]["error"] = str(e)

    return result