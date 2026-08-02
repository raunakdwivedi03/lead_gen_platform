"""Fuzzy deduplication of candidate leads by company name / domain."""
from rapidfuzz import fuzz


def _normalize(name: str) -> str:
    return (
        name.lower()
        .replace("inc.", "").replace("inc", "")
        .replace("llc", "").replace("ltd", "")
        .replace(",", "").replace(".", "")
        .strip()
    )


def dedupe_candidates(candidates: list[dict], threshold: int = 88) -> list[dict]:
    """
    Merge candidates that clearly refer to the same company (same domain,
    or fuzzy-matching name), combining their evidence instead of dropping it.
    """
    merged: list[dict] = []

    for cand in candidates:
        name_norm = _normalize(cand.get("company", ""))
        domain = (cand.get("domain") or "").lower()
        match = None

        for m in merged:
            m_domain = (m.get("domain") or "").lower()
            if domain and m_domain and domain == m_domain:
                match = m
                break
            m_name_norm = _normalize(m.get("company", ""))
            if name_norm and m_name_norm and fuzz.ratio(name_norm, m_name_norm) >= threshold:
                match = m
                break

        if match:
            match.setdefault("_evidence_list", [match.get("evidence", "")])
            match["_evidence_list"].append(cand.get("evidence", ""))
            match.setdefault("_source_urls", [match.get("source_url", "")])
            match["_source_urls"].append(cand.get("source_url", ""))
        else:
            cand["_evidence_list"] = [cand.get("evidence", "")]
            cand["_source_urls"] = [cand.get("source_url", "")]
            merged.append(cand)

    return merged
