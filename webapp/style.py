"""
ATLAS Webapp — Custom CSS
=========================
Polished visual style that goes beyond Streamlit's defaults.
Inspired by the HTML report aesthetics (orange/blue/green color system).
"""

CUSTOM_CSS = """
<style>
/* ---------- Global typography ---------- */
.main .block-container {
    padding-top: 2rem;
    max-width: 1100px;
}

h1, h2, h3 {
    font-weight: 700 !important;
    letter-spacing: -0.01em;
}

/* ---------- Hero title with gradient ---------- */
.atlas-hero {
    text-align: center;
    padding: 1.5rem 0 0.5rem 0;
}
.atlas-hero-title {
    font-size: 3.2rem;
    font-weight: 800;
    background: linear-gradient(135deg, #f97316, #c2410c);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.03em;
    margin: 0;
    line-height: 1;
}
.atlas-hero-subtitle {
    font-size: 1.05rem;
    color: #64748b;
    margin-top: 0.5rem;
    font-weight: 500;
}
.atlas-hero-tagline {
    font-size: 0.85rem;
    color: #94a3b8;
    margin-top: 0.3rem;
    font-style: italic;
}

/* ---------- Pill badges (under hero) ---------- */
.atlas-badges {
    display: flex;
    justify-content: center;
    gap: 0.6rem;
    margin-top: 1rem;
    flex-wrap: wrap;
}
.atlas-badge {
    background: #f1f5f9;
    color: #475569;
    padding: 0.3rem 0.85rem;
    border-radius: 999px;
    font-size: 0.85rem;
    font-weight: 500;
    border: 1px solid #e2e8f0;
}

/* ---------- Pretty result cards ---------- */
.result-card {
    background: linear-gradient(145deg, #fff7ed, #ffe4c4);
    border-left: 5px solid #f97316;
    border-radius: 12px;
    padding: 1.5rem 1.8rem;
    margin: 1rem 0;
    box-shadow: 0 4px 14px rgba(249, 115, 22, 0.08);
}
.result-card-title {
    font-size: 0.85rem;
    color: #c2410c;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 700;
    margin-bottom: 0.4rem;
}
.result-card-value {
    font-size: 1.6rem;
    color: #1f2937;
    font-weight: 700;
}

/* ---------- Score badge (big, bold) ---------- */
.score-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.5rem 1.2rem;
    border-radius: 14px;
    font-size: 1.4rem;
    font-weight: 700;
    color: white;
    box-shadow: 0 4px 12px rgba(34, 197, 94, 0.25);
}
.score-high   { background: linear-gradient(135deg, #22c55e, #16a34a); }
.score-mid    { background: linear-gradient(135deg, #f59e0b, #d97706); }
.score-low    { background: linear-gradient(135deg, #ef4444, #b91c1c); }

/* ---------- Agent step indicator ---------- */
.agent-step {
    background: #f0f7ff;
    border-left: 4px solid #2196f3;
    padding: 0.6rem 1rem;
    border-radius: 8px;
    margin: 0.4rem 0;
    font-size: 0.95rem;
}
.agent-step.done {
    background: #f0fdf4;
    border-left-color: #22c55e;
}

/* ---------- Sidebar polish ---------- */
[data-testid="stSidebar"] {
    background: #fafbfc;
    border-right: 1px solid #e5e7eb;
}
[data-testid="stSidebar"] h2 {
    font-size: 1rem !important;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ---------- Buttons: pop ---------- */
.stButton > button {
    border-radius: 10px;
    font-weight: 600;
    transition: all 0.15s ease;
}
.stButton > button[kind="primary"] {
    box-shadow: 0 4px 12px rgba(249, 115, 22, 0.25);
}
.stButton > button:hover {
    transform: translateY(-1px);
}

/* ---------- Tabs: bigger, clearer ---------- */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.4rem;
}
.stTabs [data-baseweb="tab"] {
    height: 3rem;
    padding: 0 1.2rem;
    background: #f8fafc;
    border-radius: 10px 10px 0 0;
    font-size: 1rem;
    font-weight: 500;
}
.stTabs [aria-selected="true"] {
    background: white !important;
    color: #f97316 !important;
    font-weight: 700 !important;
}

/* ---------- Hide Streamlit's default footer ---------- */
footer { visibility: hidden; }
#MainMenu { visibility: hidden; }

/* ---------- Subtle hover for expanders ---------- */
.streamlit-expanderHeader:hover {
    color: #f97316;
}
</style>
"""
