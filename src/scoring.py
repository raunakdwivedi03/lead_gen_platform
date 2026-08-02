"""
Lead scoring and confidence assignment.

Score (0-100) is built from:
  - number of independent search-result mentions (signal strength)
  - whether a careers-page match independently corroborated it
  - how many distinct buying signals were matched

Confidence is derived from how many INDEPENDENT source types back the lead:
  - 2+ independent source types (search + careers page)  -> High
  - 1 source type but multiple corroborating mentions      -> Medium
  - single, unverified mention                             -> Low
"""


def score_and_rank(candidate: dict, careers_result: dict, matched_signal_count: int) -> tuple[int, str]:
    score = 0

    mention_count = len([e for e in candidate.get("_evidence_list", []) if e])
    score += min(mention_count, 3) * 10          # up to 30 for repeated search mentions

    if careers_result and careers_result.get("found"):
        score += 40                               # independent corroboration is worth a lot

    score += min(matched_signal_count, 3) * 10    # up to 30 for matching known buying signals

    score = min(score, 100)

    independent_sources = 1 if mention_count else 0
    if careers_result and careers_result.get("found"):
        independent_sources += 1

    if independent_sources >= 2:
        confidence = "High"
    elif independent_sources == 1 and mention_count >= 2:
        confidence = "Medium"
    else:
        confidence = "Low"

    return score, confidence
