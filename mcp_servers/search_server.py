import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from src.search_collector import run_searches, extract_candidates

mcp = FastMCP("lead-gen-search")

@mcp.tool()
def search_for_companies(queries: list[str], max_results_per_query: int = 5) -> str:
    """Search public sources using Tavily and extract candidate company leads. Returns a JSON list of candidates with keys: company, domain, evidence, source_url, collected_at, source_type."""
    raw_results = run_searches(queries, max_results_per_query)
    candidates = extract_candidates(raw_results)
    return json.dumps(candidates, default=str)

if __name__ == '__main__':
    mcp.run()
