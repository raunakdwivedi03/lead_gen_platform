"""
Streamlit demo UI for the Intelligent Lead Generation Platform.

Run with: streamlit run app.py
"""
import streamlit as st
from src.pipeline import run_pipeline

# ── Page config ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Intelligent Lead Generation Platform",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme toggle (dark / light) ─────────────────────────────────────────
if "theme" not in st.session_state:
    st.session_state.theme = "dark"


def toggle_theme():
    st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"


is_dark = st.session_state.theme == "dark"

# ── CSS ──────────────────────────────────────────────────────────────────
if is_dark:
    bg = "#0e1117"
    bg_secondary = "#161b22"
    text = "#e6edf3"
    text_muted = "#8b949e"
    accent = "#58a6ff"
    border = "#30363d"
    card_bg = "#161b22"
    score_bg = "#1c2432"
    verified_color = "#3fb950"
    unverified_color = "#8b949e"
else:
    bg = "#ffffff"
    bg_secondary = "#f6f8fa"
    text = "#1f2328"
    text_muted = "#656d76"
    accent = "#0969da"
    border = "#d0d7de"
    card_bg = "#ffffff"
    score_bg = "#ddf4ff"
    verified_color = "#1a7f37"
    unverified_color = "#656d76"

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

    /* Global */
    .stApp {{
        background-color: {bg};
        color: {text};
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }}

    /* Sidebar */
    section[data-testid="stSidebar"] {{
        background-color: {bg_secondary};
        border-right: 1px solid {border};
    }}
    section[data-testid="stSidebar"] * {{
        color: {text} !important;
    }}

    /* Main heading */
    .main-title {{
        font-family: 'Inter', sans-serif;
        font-weight: 900;
        font-size: 2.6rem;
        letter-spacing: -0.03em;
        color: {text};
        margin-bottom: 0.15rem;
        line-height: 1.15;
    }}
    .main-subtitle {{
        font-family: 'Inter', sans-serif;
        font-weight: 400;
        font-size: 1.05rem;
        color: {text_muted};
        margin-bottom: 2rem;
    }}

    /* Lead cards */
    .lead-card {{
        background: {card_bg};
        border: 1px solid {border};
        border-radius: 10px;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }}
    .lead-company {{
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        font-size: 1.25rem;
        color: {text};
        margin: 0;
    }}
    .lead-score {{
        display: inline-block;
        background: {score_bg};
        color: {accent};
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        font-size: 0.95rem;
        padding: 0.25rem 0.75rem;
        border-radius: 6px;
    }}
    .lead-confidence {{
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        font-size: 0.9rem;
    }}
    .lead-confidence.high {{ color: {verified_color}; }}
    .lead-confidence.medium {{ color: #d29922; }}
    .lead-confidence.low {{ color: #f85149; }}
    .lead-label {{
        font-family: 'Inter', sans-serif;
        font-weight: 600;
        font-size: 0.85rem;
        color: {text_muted};
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-top: 0.8rem;
        margin-bottom: 0.25rem;
    }}
    .lead-text {{
        font-family: 'Inter', sans-serif;
        font-weight: 400;
        font-size: 0.95rem;
        color: {text};
        line-height: 1.5;
    }}
    .source-tag {{
        font-family: 'Inter', sans-serif;
        font-size: 0.82rem;
        padding: 0.15rem 0.5rem;
        border-radius: 4px;
        margin-right: 0.3rem;
    }}
    .source-verified {{
        background: {bg_secondary};
        color: {verified_color};
        border: 1px solid {verified_color};
    }}
    .source-unverified {{
        background: {bg_secondary};
        color: {unverified_color};
        border: 1px solid {border};
    }}

    /* Theme toggle button */
    .theme-btn {{
        font-family: 'Inter', sans-serif;
        font-weight: 500;
        font-size: 0.85rem;
        cursor: pointer;
    }}

    /* Hide default streamlit header decorations */
    header[data-testid="stHeader"] {{
        background-color: {bg};
    }}

    /* Input styling */
    .stTextInput input {{
        font-family: 'Inter', sans-serif;
        background-color: {bg_secondary};
        color: {text};
        border: 1px solid {border};
    }}
    .stSelectbox > div > div {{
        background-color: {bg_secondary};
        color: {text};
    }}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ──────────────────────────────────────────────────────────────
DEMO_QUERIES = {
    "Cloud & DevOps": "Find companies in the United States that may need Cloud and DevOps consulting services.",
    "Recruitment": "Find companies that may need help recruiting software engineers.",
    "AI & Machine Learning": "Find companies that are looking to adopt AI and machine learning solutions for their business.",
    "Cybersecurity": "Find companies that may need cybersecurity services or have recently faced security breaches.",
    "SDE Hiring": "Find companies that are actively hiring software development engineers and may need staffing support.",
    "Service-Based Startups": "Find service-based startups that may need technology consulting or IT outsourcing partners.",
    "Data Engineering": "Find companies that need data engineering, data pipeline, or data warehouse consulting services.",
    "Mobile App Development": "Find companies that are looking to build or modernize their mobile applications.",
    "UI/UX Design": "Find companies that may need UI/UX design services for their digital products.",
    "ERP & SAP Consulting": "Find companies that are implementing or migrating ERP and SAP systems and may need consulting help.",
    "Digital Marketing": "Find companies that may need digital marketing, SEO, or social media marketing services.",
    "Healthcare IT": "Find healthcare companies that may need IT modernization or electronic health record solutions.",
}

with st.sidebar:
    st.markdown(f"<p style='font-family:Inter;font-weight:700;font-size:1.1rem;color:{text}'>Settings</p>", unsafe_allow_html=True)

    # Theme toggle
    theme_label = "Switch to Light Mode" if is_dark else "Switch to Dark Mode"
    st.button(theme_label, on_click=toggle_theme, use_container_width=True)

    st.markdown("---")

    # Pipeline mode
    st.markdown(f"<p style='font-family:Inter;font-weight:600;font-size:0.9rem;color:{text_muted}'>PIPELINE MODE</p>", unsafe_allow_html=True)
    mode = st.radio(
        "Execution mode:",
        ["agent", "fixed"],
        index=0,
        captions=[
            "LLM agent decides tool order via MCP",
            "Original hardcoded sequence (fallback)",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown(
        f"<p style='font-family:Inter;font-size:0.82rem;color:{text_muted}'>"
        "Agent mode uses the Model Context Protocol to connect to search, browser, "
        "and processing tool servers. Falls back to fixed mode automatically if MCP is unavailable."
        "</p>",
        unsafe_allow_html=True,
    )

# ── Header ───────────────────────────────────────────────────────────────
st.markdown("<p class='main-title'>Intelligent Lead Generation</p>", unsafe_allow_html=True)
st.markdown(
    "<p class='main-subtitle'>"
    "Describe what you are offering in plain language. The platform will find and rank potential leads."
    "</p>",
    unsafe_allow_html=True,
)

# ── Input ────────────────────────────────────────────────────────────────
col1, col2 = st.columns([3, 1])
with col1:
    query = st.text_input(
        "Your request",
        placeholder="e.g. Find companies that may need cybersecurity services",
        label_visibility="collapsed",
    )
with col2:
    demo_choice = st.selectbox(
        "Demo",
        ["Select a demo query..."] + list(DEMO_QUERIES.keys()),
        label_visibility="collapsed",
    )
    if demo_choice != "Select a demo query...":
        query = DEMO_QUERIES[demo_choice]
        st.text_input("Loaded", value=query, disabled=True, label_visibility="collapsed")

# ── Run ──────────────────────────────────────────────────────────────────
if st.button("Find Leads", type="primary", use_container_width=False):
    if not query or not query.strip():
        st.warning("Enter a request first.")
    else:
        progress = st.empty()
        with st.spinner(f"Running {mode} pipeline..."):
            try:
                results = run_pipeline(
                    query,
                    mode=mode,
                    progress_callback=lambda msg: progress.info(msg),
                )
            except Exception as e:
                st.error(f"Pipeline failed: {e}")
                results = None

        progress.empty()

        if results:
            actual_mode = results.get("mode", "unknown")
            st.markdown(
                f"<p style='font-family:Inter;font-size:0.85rem;color:{text_muted};margin-bottom:1rem'>"
                f"Completed using <strong>{actual_mode}</strong> pipeline</p>",
                unsafe_allow_html=True,
            )

            with st.expander("Parsed Intent", expanded=False):
                st.json(results["intent"])

            leads = results.get("leads", [])
            st.markdown(
                f"<p style='font-family:Inter;font-weight:700;font-size:1.3rem;color:{text};margin:1.5rem 0 1rem'>"
                f"{len(leads)} leads found</p>",
                unsafe_allow_html=True,
            )

            if not leads:
                st.info("No leads found. Try broadening the query.")

            for lead in leads:
                confidence = lead.get("confidence", "Low")
                conf_class = confidence.lower()
                score = lead.get("lead_score", 0)

                # Card start
                card_html = f"<div class='lead-card'>"
                card_html += f"<div style='display:flex;align-items:center;justify-content:space-between;margin-bottom:0.6rem'>"
                card_html += f"<p class='lead-company'>{lead['company']}</p>"
                card_html += f"<div><span class='lead-score'>{score}/100</span>"
                card_html += f"  <span class='lead-confidence {conf_class}'>{confidence}</span></div>"
                card_html += f"</div>"

                # Website
                website = lead.get("website", "")
                if website:
                    card_html += f"<p class='lead-label'>Website</p>"
                    card_html += f"<p class='lead-text'><a href='{website}' style='color:{accent}'>{website}</a></p>"

                # Why relevant
                why = lead.get("why_relevant", "")
                if why:
                    card_html += f"<p class='lead-label'>Why Relevant</p>"
                    card_html += f"<p class='lead-text'>{why}</p>"

                # Decision maker
                person = lead.get("relevant_person", "Not identified")
                role = lead.get("role", "Not identified")
                if person != "Not identified" or role != "Not identified":
                    card_html += f"<p class='lead-label'>Decision Maker</p>"
                    card_html += f"<p class='lead-text'>{person} — {role}</p>"

                # Signals
                signals = lead.get("opportunity_signals", [])
                if signals:
                    card_html += f"<p class='lead-label'>Opportunity Signals</p>"
                    card_html += f"<p class='lead-text'>{', '.join(signals)}</p>"

                # Sources
                sources = lead.get("sources", [])
                if sources:
                    card_html += f"<p class='lead-label'>Sources</p>"
                    for s in sources:
                        url = s.get("url", "#")
                        stype = s.get("type", "unknown")
                        if s.get("verified"):
                            card_html += f"<span class='source-tag source-verified'>verified</span>"
                        else:
                            card_html += f"<span class='source-tag source-unverified'>unverified</span>"
                        card_html += f"<a href='{url}' style='font-family:Inter;font-size:0.82rem;color:{accent};margin-right:1rem'>{stype}</a>"
                else:
                    card_html += f"<p style='font-family:Inter;font-size:0.82rem;color:{text_muted}'>No independently verified sources for this lead.</p>"

                card_html += "</div>"
                st.markdown(card_html, unsafe_allow_html=True)
