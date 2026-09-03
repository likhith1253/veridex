"""
Design System and Styling Tokens for Veridex — AI Financial Control & Reconciliation Engine.
"""

FINTECH_CSS = """
<style>
    /* Global Application Theme */
    .stApp {
        background-color: #0B0F19;
        color: #E2E8F0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2.5rem;
        max-width: 1400px;
    }

    /* Streamlit Native Metric Cards - Crisp, Non-Truncating */
    [data-testid="stMetric"] {
        background: #131A2A;
        border: 1px solid #1E293B;
        border-radius: 8px;
        padding: 12px 14px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    }

    [data-testid="stMetricLabel"] {
        font-size: 0.75rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.06em !important;
        color: #94A3B8 !important;
        margin-bottom: 4px !important;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.25rem !important;
        font-weight: 700 !important;
        color: #F8FAFC !important;
        white-space: normal !important;
        word-break: break-word !important;
        line-height: 1.2 !important;
    }

    [data-testid="stMetricDelta"] {
        font-size: 0.75rem !important;
        font-weight: 500 !important;
        margin-top: 4px !important;
    }

    /* Sidebar Navigation Enhancement */
    [data-testid="stSidebar"] {
        background-color: #080C14 !important;
        border-right: 1px solid #1E293B;
    }

    [data-testid="stSidebar"] div[role="radiogroup"] > label {
        padding: 8px 12px !important;
        margin-bottom: 4px !important;
        border-radius: 6px !important;
        background-color: transparent !important;
        transition: all 0.15s ease-in-out !important;
        font-size: 0.88rem !important;
        color: #94A3B8 !important;
    }

    [data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
        background-color: #1E293B !important;
        color: #F8FAFC !important;
    }

    [data-testid="stSidebar"] div[role="radiogroup"] > label[data-checked="true"],
    [data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
        background-color: #1E3A8A !important;
        color: #60A5FA !important;
        font-weight: 600 !important;
    }

    /* Section Cards & Panels */
    .section-card {
        background: #111827;
        border: 1px solid #1F2937;
        border-radius: 10px;
        padding: 18px 20px;
        margin: 10px 0 20px 0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
    }

    .section-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #F1F5F9;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    /* Semantic Status Badges */
    .badge-reconciled {
        background-color: rgba(6, 78, 59, 0.6);
        border: 1px solid #059669;
        color: #34D399;
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        display: inline-block;
    }

    .badge-pending {
        background-color: rgba(120, 53, 15, 0.6);
        border: 1px solid #D97706;
        color: #FBBF24;
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        display: inline-block;
    }

    .badge-anomaly {
        background-color: rgba(127, 29, 29, 0.6);
        border: 1px solid #DC2626;
        color: #F87171;
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        display: inline-block;
    }

    .badge-ai {
        background-color: rgba(30, 58, 138, 0.6);
        border: 1px solid #2563EB;
        color: #60A5FA;
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        display: inline-block;
    }

    /* Executive Brief */
    .brief-header {
        font-size: 11px;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #94A3B8;
        margin-bottom: 6px;
        font-weight: 600;
    }

    .brief-status {
        font-size: 24px;
        font-weight: 700;
        margin-bottom: 14px;
    }

    .brief-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px;
        margin: 12px 0 16px;
    }

    .brief-grid > div {
        background: #182234;
        border: 1px solid #24324D;
        border-radius: 8px;
        padding: 12px 14px;
    }

    .brief-grid strong {
        display: block;
        font-size: 10px;
        text-transform: uppercase;
        color: #94A3B8;
        letter-spacing: 0.08em;
        margin-bottom: 4px;
    }

    .brief-body {
        color: #E2E8F0;
        font-size: 14px;
        line-height: 1.6;
    }

    /* Accounting Equation Grid */
    .accounting-box {
        background: #111827;
        border: 1px solid #1F2937;
        border-radius: 8px;
        padding: 18px 22px;
        margin-bottom: 16px;
    }

    .accounting-step {
        font-size: 14px;
        color: #CBD5E1;
        padding: 10px 0;
        border-bottom: 1px solid #1E293B;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .accounting-step-highlight {
        font-size: 15px;
        font-weight: 700;
        color: #38BDF8;
        padding: 12px 0;
        border-bottom: 1px solid #1E293B;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    /* Grounded AI Direct Answer Box */
    .qa-answer-box {
        background: #131D31;
        border-left: 4px solid #3B82F6;
        border-radius: 0 8px 8px 0;
        padding: 14px 18px;
        margin: 12px 0;
        font-size: 14px;
        line-height: 1.6;
        color: #F8FAFC;
    }
</style>
"""
