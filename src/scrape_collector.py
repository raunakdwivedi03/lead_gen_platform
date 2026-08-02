"""
Data Collection Method #2: Browser automation (Playwright).

For each candidate surfaced by the search layer, this tries to visit a
likely careers/jobs page on the company's own site and pull real job-posting
text. This both (a) adds a second, independent public source and (b) serves
as verification/corroboration for the search-based candidate.

Respects Responsible Use constraints: no login, no CAPTCHA bypassing, only
publicly reachable pages. If a page can't be reached normally, it's simply
skipped (found=False) rather than forced.
"""
import sys
import asyncio
import threading
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from src.lead import now_iso

_CAREERS_PATHS = ["/careers", "/jobs", "/careers/", "/about/careers", "/join-us"]
_HIRING_KEYWORDS = [
    "we're hiring", "we are hiring", "open positions", "open roles",
    "join our team", "current openings", "job openings",
]


def _verify_company_impl(domain: str, keywords: list[str] | None = None, timeout_ms: int = 8000) -> dict:
    """
    Internal implementation: visit a careers-style page on the given domain
    and check for hiring-related content.
    """
    keywords = keywords or []
    base = domain if domain.startswith("http") else f"https://{domain}"

    result = {
        "found": False,
        "url": None,
        "snippet": "",
        "matched_keywords": [],
        "collected_at": now_iso(),
        "source_type": "careers_page",
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent="Mozilla/5.0 (LeadGenBot; +responsible-use)")
        try:
            for path in _CAREERS_PATHS:
                url = base.rstrip("/") + path
                try:
                    page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                except PWTimeout:
                    continue
                except Exception:
                    continue

                if page.url and "404" in page.url:
                    continue

                text = (page.inner_text("body") or "").lower()
                if not text.strip():
                    continue

                found_general = [kw for kw in _HIRING_KEYWORDS if kw in text]
                found_specific = [kw for kw in keywords if kw.lower() in text]

                if found_general or found_specific:
                    result["found"] = True
                    result["url"] = url
                    result["matched_keywords"] = found_general + found_specific
                    result["snippet"] = text[:400]
                    break
        finally:
            browser.close()

    return result


def verify_company(domain: str, keywords: list[str] | None = None, timeout_ms: int = 8000) -> dict:
    """
    Try to load a careers-style page on the given domain and check for
    hiring-related content. Returns a dict describing what was found.
    Never raises on a failed fetch - a miss is a normal, expected outcome.

    Runs Playwright in a dedicated thread with its own event loop to avoid
    conflicts with Streamlit's event loop on Windows.
    """
    # On Windows inside Streamlit, the default event loop is not a
    # ProactorEventLoop, which Playwright needs for subprocess support.
    # Running in a dedicated thread with its own loop fixes this.
    if sys.platform == "win32":
        result_container = {}
        error_container = {}

        def _run():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result_container["data"] = _verify_company_impl(domain, keywords, timeout_ms)
                finally:
                    loop.close()
            except Exception as e:
                error_container["error"] = e

        thread = threading.Thread(target=_run)
        thread.start()
        thread.join()

        if "error" in error_container:
            # Don't raise — a miss is normal
            return {
                "found": False, "url": None, "snippet": "",
                "matched_keywords": [], "collected_at": now_iso(),
                "source_type": "careers_page",
            }
        return result_container.get("data", {
            "found": False, "url": None, "snippet": "",
            "matched_keywords": [], "collected_at": now_iso(),
            "source_type": "careers_page",
        })
    else:
        return _verify_company_impl(domain, keywords, timeout_ms)

