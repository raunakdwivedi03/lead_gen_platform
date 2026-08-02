# Intelligent Lead Generation Platform

Ananta Cloud Engineering Case Study — submitted by Raunak Dwivedi.

Takes a plain-language request (e.g. *"Find companies that may need cybersecurity
services"*) and returns a ranked, source-backed, explained list of potential leads.
Works across industries — nothing is hardcoded to one domain.

---

## Architecture

The platform supports two execution modes:

### Agent Mode (default) — MCP + LLM Tool-Calling

An LLM agent (Groq) dynamically orchestrates the pipeline by calling tools
exposed via the **Model Context Protocol (MCP)**. Instead of a fixed sequence,
the agent decides what to search, when to verify, and how to process results.

```
User Query
    │
    ▼
┌──────────────────────────────┐
│   Intent Parser (Groq LLM)   │  ← Turns plain language into structured brief
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│   Agent Orchestrator (Groq)  │  ← LLM with tool-calling decides the sequence
└──────┬───────┬───────┬───────┘
       │       │       │
  tool call  tool call  tool call
       │       │       │
       ▼       ▼       ▼
┌──────────┐ ┌──────────────┐ ┌──────────────┐
│ MCP Tool │ │  MCP Tool    │ │  MCP Tool    │
│ search   │ │  browser     │ │  processing  │
│ (Tavily) │ │ (Playwright) │ │ (dedupe+score│
└──────────┘ └──────────────┘ └──────────────┘
       ▲                              ▲
       └── stdio transport ───────────┘
```

Three MCP tool servers run as subprocesses:
- **`search_server`** — searches Tavily, extracts candidate companies via LLM
- **`browser_server`** — visits company websites via Playwright, checks careers pages
- **`processing_server`** — deduplicates candidates, scores and ranks leads

### Fixed Mode — Hardcoded Pipeline (fallback)

The original sequential pipeline: search → extract → dedupe → verify → score → explain.
Always available as a reliable fallback. If agent mode fails to connect to MCP
servers, the platform automatically switches to fixed mode.

---

## Setup

```bash
cd lead_gen_platform
python -m venv venv && source venv/bin/activate   # or venv\Scripts\activate on Windows
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# then edit .env and add your GROQ_API_KEY and TAVILY_API_KEY
```

## Running

### CLI

```bash
# Default: agent mode (MCP)
python main.py "Find companies in the United States that may need Cloud and DevOps consulting services"

# Explicit mode selection
python main.py "Find companies that need recruitment services" --mode agent
python main.py "Find companies that need recruitment services" --mode fixed
```

Results are printed and saved to `data/results.json`.

### Interactive demo UI (Streamlit)

```bash
streamlit run app.py
```

The UI includes:
- Two preset demo queries (Cloud/DevOps consulting, Recruitment services)
- A sidebar toggle to switch between agent and fixed modes
- Expandable intent analysis, lead cards with scores, sources, and explanations

---

## Pipeline Stages (how the data flows)

1. **Intent understanding** (`src/intent_parser.py`) — a Groq LLM call turns the
   plain-language request into a structured brief: what's being offered, the
   target company profile, likely decision-maker titles, buying signals to look
   for, and a set of concrete search queries. This is the layer that lets the
   same pipeline handle any industry.

2. **Data collection** — two independent, public sources:
   - **Search API (Tavily)** (`src/search_collector.py`) runs the generated
     queries, then an LLM call *extracts* candidate companies strictly from the
     returned snippets (no invention — if a result doesn't clearly name a
     company, it's skipped).
   - **Browser automation (Playwright)** (`src/scrape_collector.py`) visits each
     candidate's own site looking for a careers/jobs page and checks for hiring
     language, both as a second source and as corroboration of the search hit.

3. **Processing**:
   - **Dedup** (`src/dedupe.py`) merges candidates referring to the same company
     by domain match or fuzzy name match (rapidfuzz), combining their evidence.
   - **Scoring** (`src/scoring.py`) computes a 0-100 score from mention count,
     independent careers-page corroboration, and matched buying signals, and
     assigns a Low/Medium/High confidence based on how many *independent*
     source types back the lead.
   - **Explanation** (`src/pipeline.py`) generates a one-sentence "why this
     company" explanation, grounded only in the collected evidence.

Every lead carries its source URLs, collection timestamp, and verification
status, per the case study's accuracy requirements.

---

## MCP Architecture Detail

The MCP integration uses **stdio transport** — each tool server is launched as
a subprocess by the MCP client, communicating via stdin/stdout with the MCP
protocol. This avoids the complexity of HTTP servers while maintaining clean
tool separation.

```
agent/
├── mcp_client.py     # Connects to all 3 MCP servers, aggregates tools
└── orchestrator.py   # Groq tool-calling loop, drives the agent

mcp_servers/
├── search_server.py     # FastMCP server wrapping Tavily search
├── browser_server.py    # FastMCP server wrapping Playwright verification
└── processing_server.py # FastMCP server wrapping dedupe + scoring
```

**Why MCP?**
- Genuine tool-calling — the LLM agent decides the execution order, not
  hardcoded `if/then` logic
- Clean separation — each data source is an independent, testable server
- Extensible — adding a third source (e.g. a news API) means registering
  one more MCP tool, not rewriting the pipeline
- Graceful fallback — if MCP servers can't start, the fixed pipeline runs

---

## Technologies

| Component | Technology |
|-----------|-----------|
| LLM | Groq API (Llama 3.3 70B) — intent parsing, extraction, orchestration, explanation |
| Search | Tavily API — web search data source |
| Browser automation | Playwright — careers-page verification (second data source) |
| Tool protocol | MCP (Model Context Protocol) — stdio transport, FastMCP servers |
| Deduplication | rapidfuzz — fuzzy company name matching |
| Demo UI | Streamlit |

## Project Structure

```
lead_gen_platform/
├── main.py               # CLI entry point (--mode agent|fixed)
├── app.py                # Streamlit demo UI with mode toggle
├── requirements.txt
├── .env.example
├── data/                 # Output directory for results.json
├── src/                  # Core business logic (unchanged from v1)
│   ├── config.py         # Environment config
│   ├── intent_parser.py  # NL → structured brief
│   ├── search_collector.py  # Tavily search + LLM extraction
│   ├── scrape_collector.py  # Playwright careers verification
│   ├── dedupe.py         # Fuzzy dedup
│   ├── scoring.py        # 0-100 scoring + confidence
│   ├── lead.py           # Lead/Source dataclasses
│   └── pipeline.py       # Orchestrates both modes
├── mcp_servers/          # MCP tool servers (NEW)
│   ├── search_server.py
│   ├── browser_server.py
│   └── processing_server.py
└── agent/                # Agent orchestrator (NEW)
    ├── mcp_client.py     # MCP client connecting to all servers
    └── orchestrator.py   # LLM tool-calling loop
```

## Known Limitations

- Coverage depends on what Tavily's index surfaces and what's crawlable within
  a request; very obscure or brand-new companies may be missed.
- Careers-page verification relies on a small set of common URL patterns
  (`/careers`, `/jobs`, etc.) and will miss companies using non-standard ATS
  subdomains (e.g. `boards.greenhouse.io/...`) — a future version should follow
  those links when found instead of only checking the root domain.
- Confidence scoring is source-count based, not a calibrated probability — it's
  a useful ranking signal, not a guarantee of accuracy.
- No persistent company database or entity-resolution across runs; every run
  starts fresh.
- Rate limits on both Tavily and the target sites cap how many candidates can
  be verified per run (currently capped at the top 12 by mention count).
- MCP agent mode depends on Groq's tool-calling reliability — if the LLM makes
  unusual tool-call sequences, results may vary (the fixed fallback is always
  available).

## Future Work

- Follow ATS links (Greenhouse, Lever, Workday) discovered during scraping.
- Add a third source (e.g. a public company/news dataset) for extra corroboration.
- Persist results so repeated runs build a growing, deduplicated lead database.
- Add continuous monitoring so signals (like a new job posting) trigger a
  re-score instead of only running on demand.
- SSE/HTTP transport for MCP servers to support distributed deployment.
- LangGraph integration for multi-agent workflows with memory and branching.
