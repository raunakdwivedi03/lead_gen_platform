import sys
import os
import json
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from src.scrape_collector import verify_company

mcp = FastMCP("lead-gen-browser")
logger = logging.getLogger(__name__)

@mcp.tool()
def verify_company_website(domain: str, buying_signals: list[str] | None = None) -> str:
    """Visit a company website via browser automation and check for careers/hiring pages as independent verification. Returns a JSON object with found status, URL, matched keywords, and snippet."""
    result = verify_company(domain, keywords=buying_signals)
    return json.dumps(result, default=str)

@mcp.tool()
def verify_batch(candidates_json: str, buying_signals: list[str] | None = None) -> str:
    """Verify multiple company websites in batch. Takes a JSON string of candidates (each with a "domain" key) and checks each for careers pages."""
    try:
        candidates = json.loads(candidates_json)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON input"})
    
    results = []
    # Limit to 12 candidates
    for candidate in candidates[:12]:
        domain = candidate.get("domain")
        if not domain:
            continue
        try:
            res = verify_company(domain, keywords=buying_signals)
            results.append({"domain": domain, "verification_result": res})
        except Exception as e:
            logger.error(f"Error verifying {domain}: {e}")
            results.append({"domain": domain, "verification_result": {"error": str(e)}})
            
    return json.dumps(results, default=str)

if __name__ == '__main__':
    mcp.run()
