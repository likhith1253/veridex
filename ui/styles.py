"""
Design System and Styling Tokens for Project Sentinel AI Finance Controller.
"""

FINTECH_CSS = """
<style>
    /* Global Styles */
    .stApp {
        background-color: #0E131F;
        color: #E2E8F0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Executive KPI Cards */
    .kpi-container {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px;
        margin-bottom: 20px;
    }
    .kpi-card {
        background: #181E2E;
        border: 1px solid #28334E;
        border-radius: 8px;
        padding: 14px 18px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
    }
    .kpi-title {
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94A3B8;
        margin-bottom: 6px;
    }
    .kpi-val {
        font-size: 22px;
        font-weight: 700;
        color: #F8FAFC;
    }
    .kpi-sub {
        font-size: 11px;
        color: #64748B;
        margin-top: 4px;
    }
    
    /* Semantic Status Badges */
    .badge-reconciled {
        background-color: #064E3B;
        color: #34D399;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-pending {
        background-color: #78350F;
        color: #FBBF24;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-anomaly {
        background-color: #7F1D1D;
        color: #F87171;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-ai {
        background-color: #1E3A8A;
        color: #60A5FA;
        padding: 3px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        display: inline-block;
    }
    
    /* Accounting Equation Grid */
    .accounting-box {
        background: #131927;
        border: 1px solid #232D42;
        border-radius: 8px;
        padding: 18px;
        margin-bottom: 16px;
    }
    .accounting-step {
        font-size: 14px;
        color: #CBD5E1;
        padding: 8px 0;
        border-bottom: 1px solid #1E2738;
        display: flex;
        justify-content: space-between;
    }
    .accounting-step-highlight {
        font-size: 16px;
        font-weight: 700;
        color: #38BDF8;
        padding: 10px 0;
        display: flex;
        justify-content: space-between;
    }
</style>
"""
