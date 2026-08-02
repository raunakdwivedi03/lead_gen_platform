"""
MCP tool server: lead processing (deduplication + scoring).

Tools:
  - deduplicate_candidates: fuzzy-match and merge duplicate companies
  - score_and_rank_leads: score by mention count, verification, signal matches
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from src.dedupe import dedupe_candidates
from src.scoring import score_and_rank
from src.lead import now_iso

mcp = FastMCP("lead-gen-processing")


@mcp.tool()
def deduplicate_candidates(candidates_json: str) -> str:
    """Deduplicate candidate leads by matching company names (fuzzy) and domains. Merges evidence from duplicates. Takes and returns JSON strings."""
    try:
        candidates = json.loads(candidates_json)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON input for candidates"})

    deduped = dedupe_candidates(candidates)
    return json.dumps(deduped, default=str)


@mcp.tool()
def score_and_rank_leads(candidates_json: str, careers_results_json: str, buying_signals: list[str]) -> str:
    """Score and rank deduplicated leads using mention count, independent careers-page verification, and buying signal matches. Returns scored leads sorted by relevance with full provenance."""
    try:
        candidates = json.loads(candidates_json)
        careers_results = json.loads(careers_results_json)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON input"})

    # Build a lookup: domain → verification result
    careers_dict = {}
    for entry in careers_results:
        domain = entry.get("domain", "")
        vr = entry.get("verification_result", {})
        if domain and isinstance(vr, dict) and "error" not in vr:
            careers_dict[domain] = vr

    collected_at = now_iso()
    scored_leads = []

    for candidate in candidates:
        domain = candidate.get("domain", "")
        careers_result = careers_dict.get(domain, {"found": False})

        # Count only buying-signal matches (not general hiring keywords)
        # verify_company returns matched_keywords = general_keywords + specific_keywords.
        # The intersection with buying_signals isolates the real signal matches.
        careers_keywords = careers_result.get("matched_keywords", [])
        signal_matches = [
            s for s in buying_signals
            if s.lower() in [kw.lower() for kw in careers_keywords]
        ]
        matched_signal_count = len(signal_matches)

        score, confidence = score_and_rank(candidate, careers_result, matched_signal_count)

        # Build evidence from dedupe's internal fields
        evidence_list = candidate.get("_evidence_list", [])
        if not evidence_list:
            ev = candidate.get("evidence", "")
            evidence_list = [ev] if ev else []

        source_urls = candidate.get("_source_urls", [])
        if not source_urls:
            su = candidate.get("source_url", "")
            source_urls = [su] if su else []

        # Build proper source entries
        sources = []
        for url in source_urls:
            if url:
                sources.append({
                    "type": "search_api",
                    "url": url,
                    "collected_at": candidate.get("collected_at", collected_at),
                    "verified": False,
                })
        if careers_result.get("found") and careers_result.get("url"):
            sources.append({
                "type": "careers_page",
                "url": careers_result["url"],
                "collected_at": careers_result.get("collected_at", collected_at),
                "verified": True,
            })

        scored_leads.append({
            "company": candidate.get("company", "Unknown"),
            "domain": domain,
            "website": f"https://{domain}" if domain else "",
            "lead_score": score,
            "confidence": confidence,
            "why_relevant": "",  # filled by the orchestrator LLM in its final step
            "opportunity_signals": signal_matches or buying_signals[:2],
            "careers_verified": careers_result.get("found", False),
            "evidence_list": [e for e in evidence_list if e],
            "sources": sources,
            "collected_at": collected_at,
        })

    scored_leads.sort(key=lambda x: x["lead_score"], reverse=True)
    return json.dumps(scored_leads, default=str)


if __name__ == "__main__":
    mcp.run()
