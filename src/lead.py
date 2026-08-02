from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Any


@dataclass
class Source:
    source_type: str          # e.g. "search", "careers_page"
    url: str
    collected_at: str
    verified: bool


@dataclass
class Lead:
    company: str
    website: str
    why_relevant: str = ""
    relevant_person: str = ""
    role: str = ""
    opportunity_signals: List[str] = field(default_factory=list)
    lead_score: int = 0
    confidence: str = "Low"       # Low / Medium / High
    sources: List[Source] = field(default_factory=list)
    domain_query: str = ""        # which lead-gen request this came from

    def to_dict(self) -> Dict[str, Any]:
        return {
            "company": self.company,
            "website": self.website,
            "why_relevant": self.why_relevant,
            "relevant_person": self.relevant_person or "Not identified",
            "role": self.role or "Not identified",
            "opportunity_signals": self.opportunity_signals,
            "lead_score": self.lead_score,
            "confidence": self.confidence,
            "sources": [
                {
                    "type": s.source_type,
                    "url": s.url,
                    "collected_at": s.collected_at,
                    "verified": s.verified,
                }
                for s in self.sources
            ],
            "domain_query": self.domain_query,
        }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
