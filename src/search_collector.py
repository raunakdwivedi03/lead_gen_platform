"""
Data Collection Method #1: Search API (Tavily).

Runs the search queries produced by the intent parser, then uses the LLM
in a strictly EXTRACTIVE mode (grounded only in the returned snippets) to
pull out candidate company names, domains, and the evidence snippet that
justifies including them. Nothing is invented - if the search results don't
mention a company clearly, it isn't included.
"""
import json
from urllib.parse import urlparse
from tavily import TavilyClient
from groq import Groq
from src.config import TAVILY_API_KEY, GROQ_API_KEY, GROQ_MODEL
from src.lead import now_iso

_tavily = TavilyClient(api_key=TAVILY_API_KEY)
_groq = Groq(api_key=GROQ_API_KEY)

_EXTRACTION_PROMPT = """You are extracting factual candidate leads from search
results. You will be given a JSON list of search results (title, url, content
snippet). Output STRICT JSON (no prose) with key "candidates": a list of objects:

- "company": company name, EXACTLY as it appears in the source text. If no
  clear company name is present in a result, skip that result entirely.
- "domain": the domain from the result's url
- "evidence": a short (<25 words) quote-free paraphrase of why this result
  suggests the company is a fit, grounded only in the provided content
- "source_url": the url of the result this came from

CRITICAL: Do not invent companies, people, or facts that are not present in
the provided search results. If nothing usable is found, return an empty list.
"""


def run_searches(queries: list[str], max_results_per_query: int = 5) -> list[dict]:
    """Hit the Tavily search API for each generated query."""
    raw_results = []
    for q in queries:
        try:
            resp = _tavily.search(query=q, max_results=max_results_per_query, search_depth="advanced")
        except Exception as e:
            print(f"[search_collector] Tavily search failed for '{q}': {e}")
            continue
        for r in resp.get("results", []):
            raw_results.append({
                "query": q,
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:600],
            })
    return raw_results


def extract_candidates(raw_results: list[dict]) -> list[dict]:
    """Ask the LLM to extract only companies actually present in the search text."""
    if not raw_results:
        return []

    trimmed = [
        {"title": r["title"], "url": r["url"], "content": r["content"]}
        for r in raw_results
    ]

    response = _groq.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.0,
        messages=[
            {"role": "system", "content": _EXTRACTION_PROMPT},
            {"role": "user", "content": json.dumps(trimmed)},
        ],
        response_format={"type": "json_object"},
    )
    try:
        parsed = json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        return []

    candidates = parsed.get("candidates", [])
    collected_at = now_iso()
    for c in candidates:
        if not c.get("domain") and c.get("source_url"):
            c["domain"] = urlparse(c["source_url"]).netloc
        c["collected_at"] = collected_at
        c["source_type"] = "search_api"
    return candidates
