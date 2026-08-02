"""
Full pipeline: plain-language request -> ranked, explained, source-backed leads.

Supports two execution modes:
  - "agent" (default): LLM-driven tool-calling via MCP servers.
    The agent decides which tools to invoke and in what order.
  - "fixed": Original hardcoded sequence for reliability / fallback.
    Runs search -> dedupe -> verify -> score -> explain in a fixed order.

If agent mode fails to connect to MCP servers, the pipeline automatically
falls back to the fixed mode so there is always a working path.
"""
import json
import sys
import asyncio
import threading
from datetime import datetime, timezone

# Fix Windows event loop policy for Playwright subprocess support
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from groq import Groq
from src.config import GROQ_API_KEY, GROQ_MODEL
from src.intent_parser import parse_intent
from src.search_collector import run_searches, extract_candidates
from src.scrape_collector import verify_company
from src.dedupe import dedupe_candidates
from src.scoring import score_and_rank
from src.lead import Lead, Source, now_iso

_groq = Groq(api_key=GROQ_API_KEY)

_EXPLAIN_PROMPT = """You write a one-sentence, plain-English explanation of why a
company is a relevant lead, using ONLY the evidence provided. Do not add facts,
job titles, or events that are not in the evidence. If the evidence is thin,
say so honestly in the sentence rather than inflating it."""


def _explain(company: str, evidence: list[str], careers_found: bool) -> str:
    evidence_text = " | ".join([e for e in evidence if e]) or "No detailed evidence available."
    careers_note = (
        "A careers page listing was independently found."
        if careers_found
        else "No independent careers-page confirmation was found."
    )
    user_content = f"Company: {company}\nEvidence: {evidence_text}\n{careers_note}"

    response = _groq.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.3,
        messages=[
            {"role": "system", "content": _EXPLAIN_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    return response.choices[0].message.content.strip()


# ── Fixed pipeline (original logic, unchanged) ───────────────────────────


def _run_fixed_pipeline(user_request: str, max_leads: int = 10, verify_top_n: int = 12,
                        progress_callback=None) -> dict:
    """
    Runs the full pipeline for a single plain-language request.
    Returns a dict with the parsed intent and the final ranked leads.
    """
    def _update(msg):
        if progress_callback:
            progress_callback(msg)

    _update("Parsing your request...")
    intent = parse_intent(user_request)
    _update(f"Understood: looking for leads needing {intent.get('offering', 'the service')}")

    _update("Searching public sources (Tavily)...")
    raw_results = run_searches(intent["search_queries"])
    candidates = extract_candidates(raw_results)
    _update(f"Found {len(candidates)} candidates from search")

    _update("Deduplicating...")
    candidates = dedupe_candidates(candidates)
    _update(f"{len(candidates)} unique candidates after dedup")

    # Only run the (slower) browser-automation check on the top N candidates
    # by initial mention count, to keep runtime reasonable.
    candidates.sort(key=lambda c: len(c.get("_evidence_list", [])), reverse=True)
    to_verify = candidates[:verify_top_n]

    _update("Verifying candidates via their websites (Playwright)...")
    leads: list[Lead] = []
    for cand in to_verify:
        domain = cand.get("domain", "")
        careers_result = verify_company(domain, keywords=intent.get("buying_signals", []))

        matched_signals = careers_result.get("matched_keywords", [])
        score, confidence = score_and_rank(cand, careers_result, len(matched_signals))

        evidence_list = cand.get("_evidence_list", [])
        explanation = _explain(cand.get("company", "Unknown"), evidence_list, careers_result.get("found", False))

        sources = []
        for url in cand.get("_source_urls", []):
            if url:
                sources.append(Source("search_api", url, now_iso(), verified=False))
        if careers_result.get("found"):
            sources.append(Source("careers_page", careers_result["url"], careers_result["collected_at"], verified=True))

        lead = Lead(
            company=cand.get("company", "Unknown"),
            website=f"https://{domain}" if domain else "",
            why_relevant=explanation,
            opportunity_signals=matched_signals or intent.get("buying_signals", [])[:2],
            lead_score=score,
            confidence=confidence,
            sources=sources,
            domain_query=user_request,
        )
        leads.append(lead)

    leads.sort(key=lambda l: l.lead_score, reverse=True)
    top_leads = leads[:max_leads]
    _update(f"Done — {len(top_leads)} leads scored and ranked.")

    return {
        "request": user_request,
        "intent": intent,
        "leads": [l.to_dict() for l in top_leads],
        "mode": "fixed",
    }


# ── Agent pipeline (MCP-based, LLM-driven) ───────────────────────────────


def _normalize_agent_lead(raw: dict) -> dict:
    """
    Normalize a lead from the agent pipeline to match the fixed-mode
    Lead.to_dict() output format. Both modes produce identical JSON.
    """
    # The agent/processing_server already uses lead_score, but the
    # orchestrator LLM might use either key name.
    score = raw.get("lead_score", raw.get("score", 0))

    # Build sources if they aren't already in the right format
    sources = raw.get("sources", [])
    normalized_sources = []
    for s in sources:
        if isinstance(s, dict):
            normalized_sources.append({
                "type": s.get("type", "unknown"),
                "url": s.get("url", ""),
                "collected_at": s.get("collected_at", now_iso()),
                "verified": s.get("verified", False),
            })

    return {
        "company": raw.get("company", "Unknown"),
        "website": raw.get("website", ""),
        "why_relevant": raw.get("why_relevant", raw.get("explanation", "")),
        "relevant_person": raw.get("relevant_person", "Not identified"),
        "role": raw.get("role", "Not identified"),
        "opportunity_signals": raw.get("opportunity_signals", raw.get("matched_signals", [])),
        "lead_score": score,
        "confidence": raw.get("confidence", "Low"),
        "sources": normalized_sources,
        "domain_query": raw.get("domain_query", ""),
    }


def _run_agent_pipeline(user_request: str, progress_callback=None) -> dict:
    """Run the MCP-based agent pipeline and normalize output."""
    from agent.orchestrator import run_agent_pipeline as _agent_run

    # Run async pipeline in a dedicated thread with its own event loop
    # to avoid conflicts with Streamlit's event loop on Windows
    result_container = {}
    error_container = {}

    def _run_in_thread():
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result_container["data"] = loop.run_until_complete(
                    _agent_run(user_request, progress_callback)
                )
            finally:
                loop.close()
        except Exception as e:
            error_container["error"] = e

    thread = threading.Thread(target=_run_in_thread)
    thread.start()
    thread.join()

    if "error" in error_container:
        raise error_container["error"]

    result = result_container["data"]

    # Normalize agent leads to match fixed-mode format
    raw_leads = result.get("leads", [])
    result["leads"] = [_normalize_agent_lead(lead) for lead in raw_leads]

    return result


# ── Public entry point ────────────────────────────────────────────────────


def run_pipeline(user_request: str, mode: str = "agent", max_leads: int = 10,
                 verify_top_n: int = 12, progress_callback=None) -> dict:
    """
    Run the lead generation pipeline.

    Args:
        user_request: Plain-language description of what leads to find.
        mode: "agent" (MCP tool-calling, default) or "fixed" (hardcoded sequence).
        max_leads: Maximum leads to return (fixed mode only).
        verify_top_n: How many candidates to verify via browser (fixed mode only).
        progress_callback: Optional callable(str) for status updates.

    If mode="agent" and MCP servers fail to start, automatically falls back
    to "fixed" mode.
    """
    def _update(msg):
        if progress_callback:
            progress_callback(msg)

    if mode == "agent":
        try:
            _update("Starting agent pipeline (MCP)...")
            return _run_agent_pipeline(user_request, progress_callback)
        except Exception as e:
            _update(f"Agent mode failed ({e}), falling back to fixed pipeline...")
            return _run_fixed_pipeline(user_request, max_leads, verify_top_n, progress_callback)
    else:
        return _run_fixed_pipeline(user_request, max_leads, verify_top_n, progress_callback)


def save_results(results: dict, path: str) -> None:
    with open(path, "w") as f:
        json.dump(results, f, indent=2)
