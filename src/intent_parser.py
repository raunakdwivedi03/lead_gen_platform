"""
Intent Understanding Layer.

Takes a plain-language lead-generation request and turns it into a
structured brief: what's being offered, who might need it, likely
decision-maker titles, buying signals to look for, and a set of
concrete search queries to feed into the data collection layer.

This is what makes the platform generalize across industries instead
of being hardcoded to one domain.
"""
import json
from groq import Groq
from src.config import GROQ_API_KEY, GROQ_MODEL

_client = Groq(api_key=GROQ_API_KEY)

_SYSTEM_PROMPT = """You are a B2B lead-generation strategist. Given a plain-language
request describing a product or service, produce a STRICT JSON object (no prose,
no markdown fences) with these keys:

- "offering": short description of what is being sold/offered
- "target_company_profile": description of the kind of company that would need this
- "decision_maker_titles": list of 3-6 job titles who would evaluate/buy this
- "buying_signals": list of 4-6 concrete, observable signals that indicate a
  company might need this right now (e.g. hiring for a specific role, a news
  event, a technology in their job postings)
- "search_queries": list of 4-6 concrete web-search queries (each a short
  phrase, not a sentence) that would surface companies matching this profile
  right now. Vary them - some job-posting focused, some news focused.

Only output valid JSON. Do not invent specific company names here - this is
about the general profile and search strategy only.
"""


def parse_intent(user_request: str) -> dict:
    """Call the LLM to turn a plain-language request into a structured brief."""
    response = _client.chat.completions.create(
        model=GROQ_MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_request.strip()},
        ],
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Intent parser did not return valid JSON: {raw}") from e

    parsed.setdefault("decision_maker_titles", [])
    parsed.setdefault("buying_signals", [])
    parsed.setdefault("search_queries", [user_request])
    return parsed
