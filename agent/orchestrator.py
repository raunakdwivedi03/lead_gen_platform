"""
Agent orchestrator: LLM-driven tool-calling loop using Groq.

Architecture choice: the orchestrator manages intermediate data between
tool calls. The LLM decides WHICH tool to call and provides high-level
parameters (like search queries and buying signals), but the orchestrator
passes large data blobs (candidate lists, verification results) internally.
This avoids the Groq tool-calling limitation where large JSON strings in
tool arguments cause 400 errors.
"""
import os
import sys
import json
from datetime import datetime, timezone

from groq import Groq

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.config import GROQ_API_KEY, GROQ_MODEL
from agent.mcp_client import LeadGenMCPClient


# ── System prompt ─────────────────────────────────────────────────────────

ORCHESTRATOR_PROMPT = """You are a B2B lead-generation agent. You will receive a structured intent describing:
- what service is being offered
- the target company profile
- buying signals to look for
- search queries to use

You have these tools available:

1. `search_for_companies(queries, max_results_per_query)` — Search public sources.
2. `deduplicate_candidates()` — Deduplicate the search results. (No arguments needed; the system passes data automatically.)
3. `verify_batch(buying_signals)` — Verify company websites for hiring/careers pages. Only pass the buying_signals list.
4. `score_and_rank_leads(buying_signals)` — Score and rank the leads. Only pass the buying_signals list.
5. `generate_final_report()` — Generate the final report. Call this last.

Execute them in order: search → deduplicate → verify → score → report.

Call exactly ONE tool per turn. After each tool result, call the next tool.
When you call `generate_final_report`, you are done.
"""


class AgentOrchestrator:
    """
    Orchestrates the lead generation pipeline via LLM-driven tool selection.

    The LLM decides which tool to call; the orchestrator manages the data
    passing between tools (search results, deduped candidates, etc.) so
    the LLM never has to embed large JSON blobs in tool arguments.
    """

    # Virtual tool schemas that the LLM sees
    TOOL_SCHEMAS = [
        {
            "type": "function",
            "function": {
                "name": "search_for_companies",
                "description": "Search public sources for candidate companies. Returns a list of candidates.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "queries": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Search queries to find companies",
                        },
                        "max_results_per_query": {
                            "type": "integer",
                            "description": "Max results per query (default 5)",
                            "default": 5,
                        },
                    },
                    "required": ["queries"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "deduplicate_candidates",
                "description": "Deduplicate the search results by fuzzy-matching company names and domains. No arguments needed — uses the search results from the previous step.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "verify_batch",
                "description": "Verify company websites by checking for careers/hiring pages as independent confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "buying_signals": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Buying signals / keywords to look for on company websites",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "score_and_rank_leads",
                "description": "Score and rank the verified leads based on evidence strength, verification, and signal matches.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "buying_signals": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Buying signals used for scoring",
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_final_report",
                "description": "Generate the final lead report with explanations. Call this after scoring is done.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]

    def __init__(self, mcp_client: LeadGenMCPClient, progress_callback=None):
        self.mcp_client = mcp_client
        self.progress_callback = progress_callback
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = GROQ_MODEL

        # Intermediate state — managed by the orchestrator, not the LLM
        self._search_results: str = "[]"
        self._deduped: str = "[]"
        self._verification: str = "[]"
        self._scored: str = "[]"

    def _update(self, msg: str):
        if self.progress_callback:
            self.progress_callback(msg)

    async def run(self, intent: dict, user_request: str) -> list[dict]:
        """Run the agent loop: LLM picks tools, orchestrator manages data."""

        user_content = (
            f"User request: {user_request}\n\n"
            f"Structured intent:\n{json.dumps(intent, indent=2)}\n\n"
            f"Execute the tools in order now. Start with search_for_companies."
        )

        messages = [
            {"role": "system", "content": ORCHESTRATOR_PROMPT},
            {"role": "user", "content": user_content},
        ]

        max_iterations = 12
        for i in range(max_iterations):
            self._update(f"Agent reasoning (step {i + 1})...")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.TOOL_SCHEMAS,
                tool_choice="auto",
            )

            message = response.choices[0].message

            if message.tool_calls:
                messages.append(message.model_dump(exclude_none=True))

                for tc in message.tool_calls:
                    fn_name = tc.function.name
                    self._update(f"Calling tool: {fn_name}")

                    try:
                        args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except json.JSONDecodeError:
                        args = {}

                    result = await self._dispatch_tool(fn_name, args)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": fn_name,
                        "content": result,
                    })
                continue

            # No tool calls — the LLM is done
            self._update("Agent finished.")
            break

        # Parse scored leads from internal state
        return self._build_final_leads(intent)

    async def _dispatch_tool(self, tool_name: str, args: dict) -> str:
        """
        Route tool calls. The LLM provides small args (queries, signals);
        the orchestrator injects the large data blobs from internal state.
        """
        try:
            if tool_name == "search_for_companies":
                result = await self.mcp_client.call_tool("search_for_companies", {
                    "queries": args.get("queries", []),
                    "max_results_per_query": args.get("max_results_per_query", 5),
                })
                self._search_results = result
                count = len(json.loads(result)) if result else 0
                return f"Found {count} candidate companies from search."

            elif tool_name == "deduplicate_candidates":
                result = await self.mcp_client.call_tool("deduplicate_candidates", {
                    "candidates_json": self._search_results,
                })
                self._deduped = result
                count = len(json.loads(result)) if result else 0
                return f"Deduplicated to {count} unique candidates."

            elif tool_name == "verify_batch":
                signals = args.get("buying_signals", [])
                result = await self.mcp_client.call_tool("verify_batch", {
                    "candidates_json": self._deduped,
                    "buying_signals": signals or None,
                })
                self._verification = result
                return f"Verified websites for candidates."

            elif tool_name == "score_and_rank_leads":
                signals = args.get("buying_signals", [])
                result = await self.mcp_client.call_tool("score_and_rank_leads", {
                    "candidates_json": self._deduped,
                    "careers_results_json": self._verification,
                    "buying_signals": signals,
                })
                self._scored = result
                count = len(json.loads(result)) if result else 0
                return f"Scored and ranked {count} leads."

            elif tool_name == "generate_final_report":
                return "Final report ready. You can now respond with your summary."

            else:
                return f"Unknown tool: {tool_name}"

        except Exception as e:
            return f"Error in {tool_name}: {e}"

    def _build_final_leads(self, intent: dict) -> list[dict]:
        """Parse the scored leads from internal state and add explanations."""
        try:
            leads = json.loads(self._scored)
            if isinstance(leads, dict) and "error" in leads:
                return []
            return leads if isinstance(leads, list) else []
        except (json.JSONDecodeError, TypeError):
            return []


# ── Public convenience entry point ────────────────────────────────────────


async def run_agent_pipeline(user_request: str, progress_callback=None) -> dict:
    """High-level entry: parse intent -> connect MCP servers -> run agent -> return results."""
    from src.intent_parser import parse_intent

    if progress_callback:
        progress_callback("Parsing your request...")

    intent = parse_intent(user_request)

    if progress_callback:
        progress_callback(f"Understood: looking for leads needing {intent.get('offering', 'the service')}")

    client = LeadGenMCPClient()
    try:
        await client.connect()
        orchestrator = AgentOrchestrator(client, progress_callback)
        leads = await orchestrator.run(intent, user_request)
        return {
            "request": user_request,
            "intent": intent,
            "leads": leads,
            "mode": "agent",
        }
    finally:
        await client.close()
