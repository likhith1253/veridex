"""
Project Sentinel — AI Finance Controller Dashboard (Razorpay Track 04).

Complete Enterprise Financial Operations & Reconciliation Control Center:
1. Executive Overview
2. Reconciliation Operations
3. Honest Exception Queue
4. Exception Investigation Workspace & Actions
5. Settlement & Accounting Control
6. Refunds & Duplicates Auditing
7. Cash Position & 7-Day Forecast
8. Feed Source Health
9. Grounded Finance AI Q&A
10. Audit Timeline & Real-Time Controls
"""

import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import streamlit as st

from ui.api_client import FinanceControllerAPIClient
from decimal import Decimal, InvalidOperation
from ui.api_client import FinanceControllerAPIClient
from ui.styles import FINTECH_CSS

# Page Configuration
st.set_page_config(
    page_title="Project Sentinel | AI Finance Controller",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply Styling
st.markdown(FINTECH_CSS, unsafe_allow_html=True)

# Initialize API Client
api = FinanceControllerAPIClient()


def format_money(value, *, fallback="N/A — unavailable from live data"):
    if value is None:
        return fallback
    try:
        dec = Decimal(str(value))
        return f"₹{dec:,.2f}"
    except (TypeError, ValueError, InvalidOperation):
        return fallback


def format_number(value, *, decimals=0, fallback="N/A — unavailable from live data"):
    if value is None:
        return fallback
    try:
        dec = Decimal(str(value))
        if decimals == 0:
            return f"{dec:,.0f}"
        return f"{dec:,.{decimals}f}"
    except (TypeError, ValueError, InvalidOperation):
        return fallback


def format_percent(value, *, decimals=1, fallback="N/A — unavailable from live data"):
    if value is None:
        return fallback
    try:
        dec = Decimal(str(value))
        return f"{dec:.{decimals}f}%"
    except (TypeError, ValueError, InvalidOperation):
        return fallback


def render_empty_state(label: str, message: str = "No live data is available for this section right now."):
    st.info(f"**{label}**\n\n{message}")


def render_sidebar():
    st.sidebar.title("🛡️ Project Sentinel")
    st.sidebar.caption("AI Finance Controller | Track 04")

    # Backend Health Check
    health = api.check_health()
    if health.get("status") == "healthy":
        st.sidebar.success("● Live API connected on port 8000")
    else:
        st.sidebar.error("● Backend offline / unreachable")

    st.sidebar.divider()

    navigation_options = [
        "1. Executive Overview",
        "2. Reconciliation Operations",
        "3. Exception Queue",
        "4. Exception Workspace & Actions",
        "5. Settlement & Accounting",
        "6. Refunds & Duplicates",
        "7. Cash Position & Forecast",
        "8. Source Health",
        "9. Finance AI Q&A",
        "10. AI Finance Copilot",
        "11. Audit Trail & Ingestion",
        "12. Benchmark & Model Evaluation",
    ]

    selected_view = st.sidebar.radio("Navigation", navigation_options)
    st.sidebar.divider()
    st.sidebar.info("Razorpay AI Buildathon 2026\nTrack 04: AI Finance Controller\nStatus: Backend Frozen")
    return selected_view


def view_overview():
    st.title("📊 Executive Finance Controller Overview")
    st.caption("Authoritative multi-feed reconciliation KPIs, cash exposure, and throughput metrics.")

    try:
        kpis = api.get_summary()
        funnel = api.get_funnel()
        cash = api.get_cash_position()
        health = api.get_source_health()
    except Exception as e:
        st.error(f"Failed to load executive metrics: {e}")
        return

    if not kpis and not funnel and not cash:
        render_empty_state("Executive overview", "No live data has been loaded yet from the controller APIs.")
        return

    # Top Executive KPI Cards
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("Total Processed", format_number(kpis.get('total_records_processed', 0), fallback="N/A") + " records", delta=f"{kpis.get('total_logical_transactions', 0):,} txns")
    with col2:
        f1_val = kpis.get('f1_score')
        f1_str = f"F1 {float(f1_val):.1f}%" if f1_val is not None else "N/A — unavailable from live data"
        st.metric("Reconciliation Rate", format_percent(kpis.get('match_rate', 0.0), decimals=1), delta=f1_str)
    with col3:
        st.metric("ML Recovered", f"{kpis.get('ml_recovered_matches', 0):,} matches")
    with col4:
        st.metric(
            "Expected Net Settlement",
            format_money(cash.get("expected_net_settlement", cash.get("expected_amount", 0.0))),
            delta=f"Gross {format_money(cash.get('expected_gross', cash.get('expected_amount', 0.0)))}",
        )
    with col5:
        st.metric("Unreconciled Exposure", format_money(kpis.get('unresolved_monetary_exposure_inr', 0.0)), delta_color="inverse")
    with col6:
        tps = kpis.get('processing_throughput_tps')
        lat = kpis.get('average_processing_latency_ms')
        tps_str = format_number(tps, decimals=0, fallback="N/A — unavailable from live data") + " tps" if tps is not None else "N/A — unavailable from live data"
        lat_str = f"{float(lat):.2f} ms lat" if lat is not None else None
        st.metric("Throughput", tps_str, delta=lat_str)

    st.divider()

    # Two-Column Layout
    c1, c2 = st.columns([1, 1])

    with c1:
        st.subheader("🔀 Multi-Stage Reconciliation Funnel")
        f1, f2, f3, f4, f5 = st.columns(5)
        f1.metric("1. Ingested", f"{funnel.get('incoming_records', 0):,}")
        f2.metric("2. Deterministic", f"{funnel.get('deterministic_matches', 0):,}")
        f3.metric("3. ML Recovered", f"{funnel.get('ml_recovered', 0):,}")
        f4.metric("4. Manual Review", f"{funnel.get('manual_reviews', 0):,}")
        f5.metric("5. Unresolved", f"{funnel.get('unresolved', 0):,}")

        st.write("**Reconciliation Pipeline Drop-off:**")
        funnel_data = {
            "Stage": ["Ingested", "Deterministic Matches", "ML Recovered", "Manual Review", "Unresolved"],
            "Records": [
                funnel.get('incoming_records', 0),
                funnel.get('deterministic_matches', 0),
                funnel.get('ml_recovered', 0),
                funnel.get('manual_reviews', 0),
                funnel.get('unresolved', 0)
            ]
        }
        df_funnel = pd.DataFrame(funnel_data)
        st.bar_chart(df_funnel.set_index("Stage"), width='stretch')

    with c2:
        st.subheader("💰 Treasury Cash & Risk Exposure")
        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("Received Bank Credits", format_money(cash.get('received_amount', 0)))
        cc2.metric("Pending In Window", format_money(cash.get('pending_amount', 0)))
        cc3.metric("High-Risk Discrepancy", format_money(cash.get('at_risk_amount', 0)), delta_color="inverse")

        cat_breakdown = cash.get("breakdown_by_category", {})
        if cat_breakdown:
            st.write("**Exposure by Exception Category:**")
            df_cat = pd.DataFrame(list(cat_breakdown.items()), columns=["Category", "Exposure INR"])
            st.bar_chart(df_cat.set_index("Category"))


def view_reconciliation():
    st.title("🔀 Reconciliation Operations")
    st.caption("Detailed deterministic rule evaluation, ML candidate recovery, and matching metrics.")

    try:
        kpis = api.get_summary()
        funnel = api.get_funnel()
    except Exception as e:
        st.error(f"Failed to load reconciliation data: {e}")
        return

    if not kpis and not funnel:
        render_empty_state("Reconciliation operations", "No reconciliation data is available from the controller API yet.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Deterministic Matches", f"{kpis.get('deterministic_matches', 0):,}")
    c2.metric("ML Recovered Matches", f"{kpis.get('ml_recovered_matches', 0):,}")
    c3.metric("Manual Reviews Flagged", f"{kpis.get('manual_reviews', 0):,}")
    c4.metric("Unresolved Quarantined", f"{kpis.get('unresolved_transactions', 0):,}")

    st.divider()

    st.subheader("Decision Policy Breakdown")
    dec_df = pd.DataFrame({
        "Decision Type": ["Deterministic Exact Match", "ML Scored Match (XGBoost)", "Manual Review Required", "Unresolved Exception"],
        "Count": [kpis.get('deterministic_matches', 0), kpis.get('ml_recovered_matches', 0), kpis.get('manual_reviews', 0), kpis.get('unresolved_transactions', 0)],
        "Confidence Gate": [">= 0.95", ">= 0.90", "0.70 - 0.90", "< 0.70"],
        "Action Policy": ["Auto-Commit", "Auto-Commit", "Flag for Controller", "Quarantine to Exception Queue"]
    })
    st.dataframe(dec_df, width='stretch')


def view_exception_queue():
    st.title("⚠️ Honest Exception Queue")
    st.caption("Transparent, honest list of unresolved financial discrepancies requiring controller attention.")

    # Filter Toolbar
    with st.expander("Filter Exception Queue", expanded=True):
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            status_filter = st.selectbox("Status", ["All", "open", "investigating", "pending_review", "escalated", "approved", "resolved", "rejected"])
        with col_f2:
            cat_filter = st.selectbox("Category", ["All", "missing_record", "amount_mismatch", "timing_mismatch", "duplicate_record", "delayed_settlement", "fee_mismatch", "unexplained"])
        with col_f3:
            min_exp = st.number_input("Min Exposure (INR)", value=0.0, step=1000.0)
        with col_f4:
            page_num = st.number_input("Page", min_value=1, value=1, step=1)

    stat_val = None if status_filter == "All" else status_filter
    cat_val = None if cat_filter == "All" else cat_filter
    min_val = None if min_exp == 0.0 else min_exp

    try:
        exc_data = api.list_exceptions(status=stat_val, category=cat_val, min_exposure=min_val, page=page_num, page_size=25)
        aging = api.get_exception_aging()
    except Exception as e:
        st.error(f"Failed to fetch exceptions: {e}")
        return

    # Aging Summary Bar
    st.write("**Exception Aging Distribution:**")
    buckets = aging.get("buckets", [])
    ag_cols = st.columns(len(buckets) if buckets else 1)
    for idx, b in enumerate(buckets):
        with ag_cols[idx]:
            st.metric(b.get("bucket"), f"{b.get('count', 0)} open", delta=f"₹{b.get('financial_exposure_inr', 0.0):,.0f}")
            
    if buckets:
        df_aging = pd.DataFrame(buckets)
        st.bar_chart(df_aging.set_index("bucket")[["financial_exposure_inr"]], width='stretch')

    st.divider()

    items = exc_data.get("exceptions", [])
    total_cnt = exc_data.get("total_count", 0)

    st.subheader(f"Open Exceptions ({total_cnt} Total)")
    if items:
        df_items = pd.DataFrame(items)
        st.dataframe(
            df_items[["exception_id", "transaction_id", "category", "status", "financial_exposure_inr", "confidence", "recommended_action", "explanation"]],
            width='stretch',
            height=450,
        )
    else:
        st.info("No exceptions match the current filter criteria. The live exception queue is empty for this view.")


def view_exception_workspace():
    st.title("🔍 Exception Investigation Workspace")
    st.caption("Complete investigation workflow: understand why, assess impact, and decide.")

    try:
        exc_list = api.list_exceptions(page_size=20).get("exceptions", [])
    except Exception as e:
        st.error(f"Error fetching exception list: {e}")
        return

    if not exc_list:
        render_empty_state("Exception workspace", "No exception records are available from the live controller API for investigation.")
        return

    exc_options = {f"{e.get('exception_id')[:8]}... | {e.get('category')} | ₹{e.get('financial_exposure_inr', 0):,.0f}": e.get('exception_id') for e in exc_list}
    selected_label = st.selectbox("Select Exception to Investigate:", list(exc_options.keys()))
    selected_id = exc_options[selected_label]

    try:
        inv_view = api.get_exception_investigation_view(selected_id)
    except Exception as e:
        st.error(f"Failed to load investigation view: {e}")
        return

    # Decision Boundary Banner
    decision_boundary = inv_view.get("decision_boundary", {})
    boundary_category = decision_boundary.get("category", "UNKNOWN")
    
    if boundary_category == "AUTO_SAFE":
        st.success(f"🟢 **AUTO-SAFE** | Confidence: {decision_boundary.get('confidence', 0)*100:.1f}% | {decision_boundary.get('reason', '')}")
    elif boundary_category == "AI_SUGGESTED":
        st.warning(f"🟡 **AI-SUGGESTED** | Confidence: {decision_boundary.get('confidence', 0)*100:.1f}% | {decision_boundary.get('reason', '')}")
    else:
        st.error(f"🔴 **HUMAN REVIEW REQUIRED** | Confidence: {decision_boundary.get('confidence', 0)*100:.1f}% | {decision_boundary.get('reason', '')}")

    st.divider()

    # Identity Section
    st.subheader("IDENTITY")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Exception ID", inv_view.get("exception_id", "N/A")[:8] + "...")
    with col2:
        st.metric("Transaction ID", inv_view.get("transaction_id", "N/A")[:8] + "..." if inv_view.get("transaction_id") else "N/A")
    with col3:
        st.metric("Source", inv_view.get("source", "N/A").upper() if inv_view.get("source") else "N/A")
    with col4:
        st.metric("Status", inv_view.get("status", "N/A").upper())

    st.divider()

    # Financial Impact Section
    st.subheader("FINANCIAL IMPACT")
    financial = inv_view.get("financial_impact", {})
    fcol1, fcol2, fcol3, fcol4 = st.columns(4)
    with fcol1:
        st.metric("Transaction Amount", format_money(financial.get("transaction_amount")))
    with fcol2:
        st.metric("Monetary Exposure", format_money(financial.get("monetary_exposure")))
    with fcol3:
        st.metric("Fee Difference", format_money(financial.get("fee_difference")))
    with fcol4:
        st.metric("Tax Difference", format_money(financial.get("tax_difference")))

    st.divider()

    # WHY THIS EXCEPTION Section (Most Important)
    st.subheader("WHY THIS EXCEPTION WAS FLAGGED")
    
    st.markdown(f"**Primary Reason:** {inv_view.get('root_cause', inv_view.get('explanation', 'No root cause established'))}")
    
    st.markdown(f"**Financial Impact:** {format_money(financial.get('monetary_exposure'))}")
    
    st.markdown("**Evidence:**")
    matching = inv_view.get("matching_evidence", {})
    if matching.get("deterministic_match_result"):
        st.write(f"• Deterministic match result: {matching.get('deterministic_match_result')}")
    if matching.get("ml_match_result"):
        st.write(f"• ML match result: {matching.get('ml_match_result')}")
    for mismatch in matching.get("mismatch_fields", []):
        st.write(f"• Mismatch field: {mismatch}")
    
    st.markdown(f"**Confidence:** {inv_view.get('confidence', 0)*100:.1f}%")
    
    risk_bucket = inv_view.get("risk_bucket", "UNKNOWN").upper()
    st.markdown(f"**Risk:** {risk_bucket}")
    
    st.markdown(f"**Recommended Action:** {inv_view.get('recommended_action', 'No recommendation')}")
    
    human_review = decision_boundary.get("requires_human_review", False)
    st.markdown(f"**Human Review:** {'REQUIRED' if human_review else 'NOT REQUIRED'}")

    st.divider()

    # Timeline Section
    st.subheader("TIMELINE")
    timeline = inv_view.get("timeline", {})
    tcol1, tcol2, tcol3, tcol4 = st.columns(4)
    with tcol1:
        st.metric("Exception Created", timeline.get("exception_created", "N/A")[:10] if timeline.get("exception_created") else "N/A")
    with tcol2:
        st.metric("Investigation Started", timeline.get("investigation_started", "N/A")[:10] if timeline.get("investigation_started") else "N/A")
    with tcol3:
        st.metric("Human Decision", timeline.get("human_decision", "N/A")[:10] if timeline.get("human_decision") else "N/A")
    with tcol4:
        st.metric("Resolved", timeline.get("resolved", "N/A")[:10] if timeline.get("resolved") else "N/A")

    st.divider()

    # Decision Panel
    st.subheader("DECISION")
    
    current_status = inv_view.get("status", "open")
    resolved = inv_view.get("resolved", False)
    
    if resolved:
        st.success(f"✅ This exception has been resolved as of {inv_view.get('resolved_at', 'N/A')}")
    else:
        col_dec1, col_dec2, col_dec3 = st.columns(3)
        
        with col_dec1:
            if st.button("APPROVE", type="primary"):
                try:
                    res = api.apply_decision(selected_id, "approve", "finance_controller", "Approved after investigation")
                    st.success(f"Approved! Audit Event ID: `{res.get('audit_event_id')}`")
                    st.rerun()
                except Exception as e:
                    st.error(f"Approval failed: {e}")
        
        with col_dec2:
            if st.button("REJECT"):
                try:
                    res = api.apply_decision(selected_id, "reject", "finance_controller", "Rejected after investigation")
                    st.success(f"Rejected! Audit Event ID: `{res.get('audit_event_id')}`")
                    st.rerun()
                except Exception as e:
                    st.error(f"Rejection failed: {e}")
        
        with col_dec3:
            if st.button("ESCALATE"):
                try:
                    res = api.apply_decision(selected_id, "escalate", "finance_controller", "Escalated to senior team")
                    st.success(f"Escalated! Audit Event ID: `{res.get('audit_event_id')}`")
                    st.rerun()
                except Exception as e:
                    st.error(f"Escalation failed: {e}")
        
        st.divider()
        
        reason = st.text_input("Decision Reason / Audit Note:", "Investigated and verified")
        actor = st.text_input("Controller ID:", "finance_controller")
        
        col_dec4, col_dec5 = st.columns(2)
        with col_dec4:
            if st.button("RESOLVE"):
                try:
                    res = api.apply_decision(selected_id, "resolve", actor, reason)
                    st.success(f"Resolved! Audit Event ID: `{res.get('audit_event_id')}`")
                    st.rerun()
                except Exception as e:
                    st.error(f"Resolution failed: {e}")
        
        with col_dec5:
            if st.button("INVESTIGATE"):
                try:
                    res = api.apply_decision(selected_id, "investigate", actor, reason)
                    st.success(f"Marked for investigation! Audit Event ID: `{res.get('audit_event_id')}`")
                    st.rerun()
                except Exception as e:
                    st.error(f"Investigation flag failed: {e}")

    st.divider()

    # Additional Actions
    st.subheader("ADDITIONAL ACTIONS")
    col_add1, col_add2 = st.columns(2)
    
    with col_add1:
        assignee = st.text_input("Assign to Analyst / Team:", "analyst_bob@sentinel.internal")
        if st.button("Assign Exception"):
            try:
                res = api.assign_exception(selected_id, assignee, actor="controller_admin")
                st.success(f"Assigned to {assignee} successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Assignment failed: {e}")
    
    with col_add2:
        note_text = st.text_area("Review Note:")
        if st.button("Attach Note"):
            try:
                res = api.add_exception_note(selected_id, note_text, actor="finance_reviewer")
                st.success("Note attached to audit trail.")
                st.rerun()
            except Exception as e:
                st.error(f"Note attachment failed: {e}")


def view_settlement_accounting():
    st.title("⚖️ Unified Settlement & Accounting Control")
    st.caption("Audits the authoritative treasury accounting equation against core bank statement settlements.")

    try:
        settlement = api.get_settlement_accounting()
        feetax = api.get_fee_tax_control()
    except Exception as e:
        st.error(f"Failed to fetch settlement data: {e}")
        return

    if not settlement and not feetax:
        render_empty_state("Settlement accounting", "No accounting data has been returned by the controller API.")
        return

    st.subheader("Treasury Net Settlement Equation")

    st.markdown(f"""
    <div class="accounting-box">
        <div class="accounting-step"><span>Gross Gateway Volume</span><span>{format_money(settlement.get('gross_gateway_volume', 0))}</span></div>
        <div class="accounting-step"><span>(-) Total Deducted MDR Fees</span><span>-{format_money(settlement.get('total_deducted_fees', 0))}</span></div>
        <div class="accounting-step"><span>(-) Total Deducted Taxes (18% GST)</span><span>-{format_money(settlement.get('total_deducted_taxes', 0))}</span></div>
        <div class="accounting-step"><span>(-) Total Customer Refunds</span><span>-{format_money(settlement.get('total_refunded_amount', 0))}</span></div>
        <div class="accounting-step-highlight"><span>(=) Expected Net Bank Settlement</span><span>{format_money(settlement.get('expected_net_settlement', 0))}</span></div>
        <div class="accounting-step-highlight"><span>Actual Bank Statement Credits Received</span><span>{format_money(settlement.get('actual_bank_settled_credits', 0))}</span></div>
        <div class="accounting-step"><span>Net Settlement Variance</span><span>{format_money(settlement.get('net_settlement_variance', 0))}</span></div>
    </div>
    """, unsafe_allow_html=True)

    status = settlement.get("settlement_reconciliation_status")
    if status == "RECONCILED":
        st.success(f"Status: {status} — All expected settlements match bank credits within clearing tolerance.")
    else:
        st.warning(f"Status: {status} — Unsettled delayed exposure: {format_money(settlement.get('unsettled_delayed_exposure', 0))}")

    st.divider()

    st.subheader("MDR Fee & GST Tax Discrepancy Audits")
    c1, c2, c3 = st.columns(3)
    c1.metric("Analyzed Transactions", f"{feetax.get('total_transactions_analyzed', 0):,}")
    c2.metric("Discrepant Deductions", f"{feetax.get('discrepant_transactions_count', 0)}")
    c3.metric("Fee/Tax Exposure", format_money(feetax.get('total_fee_tax_exposure', 0)))


def view_refunds_and_duplicates():
    st.title("🔄 Refunds & Duplicate Incident Audits")
    st.caption("Isolates over-refund discrepancies, duplicate gateway debits, and bank statement duplications.")

    try:
        refunds = api.get_refund_audit()
        duplicates = api.get_duplicate_audit()
    except Exception as e:
        st.error(f"Failed to fetch audit records: {e}")
        return

    if not refunds and not duplicates:
        render_empty_state("Refund and duplicate audits", "No refund or duplicate audit results are available from the live API.")
        return

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Refund Reconciliation")
        r1, r2, r3 = st.columns(3)
        r1.metric("Audited Payments", f"{refunds.get('total_payments_audited', 0):,}")
        r2.metric("Fully / Partially Refunded", f"{refunds.get('fully_refunded_count', 0) + refunds.get('partially_refunded_count', 0)}")
        r3.metric("Over-Refund Anomalies", f"{refunds.get('over_refund_anomalies_count', 0)}", delta=f"{format_money(refunds.get('total_over_refund_exposure', 0))}", delta_color="inverse")

    with c2:
        st.subheader("Duplicate Incident Classification")
        d1, d2, d3 = st.columns(3)
        d1.metric("Total Incidents", f"{duplicates.get('total_incidents_detected', 0)}")
        d2.metric("Duplicate Gateway Charges", f"{duplicates.get('duplicate_charges_count', 0)}", delta=f"{format_money(duplicates.get('duplicate_charges_exposure', 0))}")
        d3.metric("Duplicate Bank Credits", f"{duplicates.get('duplicate_settlements_count', 0)}", delta=f"{format_money(duplicates.get('duplicate_settlements_exposure', 0))}")

    st.divider()

    st.subheader("Incident Evidence Records")
    incidents = duplicates.get("incidents", [])
    if incidents:
        st.dataframe(pd.DataFrame(incidents), width='stretch')
    else:
        st.info("No active duplicate payment incidents detected.")


def view_cash_position_and_forecast():
    st.title("💰 Cash Position & 7-Day Settlement Forecast")
    st.caption("Current multi-source liquidity position and transparent forward settlement projections.")

    try:
        cash = api.get_cash_position()
        forecast = api.get_forecast()
    except Exception as e:
        st.error(f"Failed to load cash data: {e}")
        return

    if not cash and not forecast:
        render_empty_state("Cash position and forecast", "No live cash or forecast data is available from the controller API.")
        return

    try:
        fee_dec = Decimal(str(cash.get("total_deducted_fees", 0) or 0))
        tax_dec = Decimal(str(cash.get("total_deducted_taxes", 0) or 0))
        deductions_str = f"-{format_money(fee_dec + tax_dec)} deductions"
    except Exception:
        deductions_str = None

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Gross Gateway Volume", format_money(cash.get("expected_gross", cash.get("expected_amount", 0.0))))
    c2.metric("Expected Net Settlement", format_money(cash.get("expected_net_settlement", 0.0)), delta=deductions_str)
    c3.metric("Received Bank Credits", format_money(cash.get("received_bank_credits", cash.get("received_amount", 0.0))))
    c4.metric("Net Settlement Variance", format_money(cash.get("settlement_variance", 0.0)), delta_color="inverse")
    c5.metric("Unreconciled Exposure", format_money(cash.get("unreconciled_amount", 0.0)), delta_color="inverse")

    st.caption("Accounting Invariant: Gross Volume - MDR Fees - GST - Refunds = Expected Net Bank Settlement | Actual Bank Credits - Expected Net = Net Settlement Variance")

    st.divider()

    st.subheader("7-Day Forward Settlement Forecast (Moving Average)")
    st.caption(f"Methodology: {forecast.get('methodology')} | 7-Day Inflow Total: {format_money(forecast.get('seven_day_forecast_total_inr', 0))}")

    if not forecast.get("historical_data_sufficient", True) and forecast.get("distinct_historical_days", 0) > 0:
        st.warning("⚠️ Baseline Projection: Limited historical dates available (< 3 days). As additional batches are ingested, empirical volatility bounds will automatically refine.")

    days = forecast.get("forecast_days", [])
    if days:
        df_fc = pd.DataFrame(days)
        st.line_chart(df_fc.set_index("date")[["forecast_amount_inr", "confidence_interval_low", "confidence_interval_high"]])
        st.dataframe(df_fc, width='stretch')
    else:
        st.info("No transaction history available to compute settlement projections.")


def view_source_health():
    st.title("🏥 Feed Source Health & Data Quality")
    st.caption("Operational reliability, record volume, clean reconciliation, and exception rates for Gateway, Ledger, and Bank feeds.")

    try:
        health = api.get_source_health()
    except Exception as e:
        st.error(f"Failed to load health metrics: {e}")
        return

    if not health:
        render_empty_state("Source health", "No source health data is available from the live controller API.")
        return

    st.subheader(f"Overall System Ingestion Health: {health.get('overall_health', 'HEALTHY')}")
    st.caption("ℹ️ Feed metrics reflect real PostgreSQL ingestion records. Transactions can be matched across feeds while carrying exceptions (e.g., fee discrepancies). Clean Match indicates records reconciled without any exceptions.")

    sources = health.get("sources", {})
    s_cols = st.columns(len(sources))

    for idx, (src_key, s_data) in enumerate(sources.items()):
        with s_cols[idx]:
            clean_pct = s_data.get('clean_match_rate_percent', s_data.get('match_rate_percent', 100.0))
            st.metric(
                s_data.get("source_name", src_key),
                f"{s_data.get('total_records', 0):,} records",
                delta=f"{clean_pct:.1f}% clean match",
            )
            st.write(f"**Volume:** {format_money(s_data.get('total_volume_inr', 0))}")
            st.write(f"**Matched in Clusters:** {s_data.get('matched_records', 0)} ({s_data.get('match_rate_percent', 0.0):.1f}%)")
            st.write(f"**Flagged Exceptions:** {s_data.get('exception_records', 0)} ({s_data.get('exception_rate_percent', 0.0):.1f}%)")
            st.write(f"**Status:** `{s_data.get('health_status', 'HEALTHY')}`")


def view_benchmark_evaluation():
    st.title("📊 Benchmark & Model Evaluation")
    st.caption("Evaluation-only benchmark run. This view is intentionally isolated from live PostgreSQL state and does not mutate the production controller data.")

    col1, col2, col3 = st.columns(3)
    with col1:
        num_transactions = st.number_input("Logical transactions", min_value=10, max_value=5000, value=100, step=10)
    with col2:
        seed = st.number_input("Seed", min_value=0, max_value=999999, value=42, step=1)
    with col3:
        st.write("")
        st.write("")
        if st.button("Run benchmark", type="primary"):
            try:
                benchmark = api.get_benchmark(num_transactions=int(num_transactions), seed=int(seed))
                st.session_state["benchmark_result"] = benchmark
            except Exception as e:
                st.error(f"Benchmark evaluation failed: {e}")

    benchmark = st.session_state.get("benchmark_result")
    if not benchmark:
        st.info("No benchmark has been run yet. Use the controls above to execute a deterministic evaluation snapshot.")
        return

    b = benchmark.get("benchmark", {})
    r = benchmark.get("result", {})
    st.success(f"Scope: {benchmark.get('scope')} | Dataset: {b.get('dataset_name')}")
    st.json({
        "num_transactions": b.get("num_transactions"),
        "seed": b.get("seed"),
        "currency": b.get("currency"),
        "dataset_name": b.get("dataset_name"),
    })

    overall = r.get("overall", {})
    if overall:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Precision", f"{overall.get('precision', 0):.4f}")
        c2.metric("Recall", f"{overall.get('recall', 0):.4f}")
        c3.metric("F1", f"{overall.get('f1_score', 0):.4f}")
        c4.metric("False match rate", f"{overall.get('false_match_rate', 0):.4f}")

    scenario_summary = r.get("scenarios", {})
    if scenario_summary:
        st.subheader("Scenario Breakdown")
        sc_df = pd.DataFrame(list(scenario_summary.values()))
        st.dataframe(sc_df[["scenario", "total_records", "precision", "recall", "f1_score", "unresolved_records"]], width='stretch')

    st.subheader("Full Evaluation JSON")
    st.json(r)


def view_finance_ai_qa():
    st.title("💬 Grounded Finance Controller AI Q&A")
    st.caption("Ask natural language treasury and reconciliation questions grounded strictly in PostgreSQL state (zero hallucinations).")

    st.markdown("<div class='section-card'>", unsafe_allow_html=True)

    preset = st.selectbox(
        "Suggested Controller Prompts:",
        [
            "Custom Query...",
            "What is the total unresolved financial exposure?",
            "How much money was recovered by ML candidate scoring?",
            "What is the breakdown of open exceptions by category?",
            "Which exceptions have the highest monetary exposure?",
            "Why is there a discrepancy in today's settlement?",
        ]
    )
    question = st.text_input("Enter Finance Operations Question:", value="" if preset == "Custom Query..." else preset)

    if st.button("Analyze with Controller AI", type="primary") and question:
        with st.spinner("Executing verifiable SQL metric aggregation and reasoning..."):
            try:
                qa_res = api.ask_qa(question)
                st.success(f"**Controller Direct Answer:**\n\n{qa_res.get('direct_answer')}")

                c1, c2 = st.columns(2)
                with c1:
                    st.write("**Key Grounded Financial Metrics:**")
                    st.json(qa_res.get("key_metrics", {}))

                with c2:
                    st.write("**Verifiable SQL Facts Used:**")
                    for f in qa_res.get("sql_facts_used", []):
                        st.code(f)

                ev = qa_res.get("evidence_records", [])
                if ev:
                    st.write("**Verifiable Evidence Records:**")
                    st.dataframe(pd.DataFrame(ev), width='stretch')
                else:
                    st.info("The controller returned no evidence records for this query.")

            except Exception as e:
                st.error(f"Q&A query failed: {e}")

    st.markdown("</div>", unsafe_allow_html=True)


def view_ai_finance_copilot():
    st.title("🧠 AI Finance Brief & Copilot")
    st.caption("Grounded finance-control assistant for risk triage, exception explanation, and evidence-first operator guidance.")

    try:
        brief = api.get_daily_brief()
    except Exception as exc:
        st.error(f"Failed to load finance brief: {exc}")
        return

    status = brief.get("status", "Stable")
    status_color = "#34D399" if status == "Stable" else "#FBBF24" if status == "Attention Required" else "#F87171"
    st.markdown(
        f"<div class='section-card'><div class='brief-header'>TODAY'S FINANCE BRIEF</div>"
        f"<div class='brief-status' style='color:{status_color};'>{status}</div>"
        f"<div class='brief-grid'>"
        f"<div><strong>Money at Risk</strong><div>{format_money(brief.get('money_at_risk_inr'))}</div></div>"
        f"<div><strong>Reconciliation</strong><div>{format_percent(brief.get('reconciliation_match_rate_percent'), decimals=1)}</div></div>"
        f"<div><strong>Top Risk</strong><div>{brief.get('highest_risk_exception') or 'No material exception'}</div></div>"
        f"</div>"
        f"<div class='brief-body'><p><strong>Why:</strong> {brief.get('why', 'No material issue flagged.')}</p>"
        f"<p><strong>Recommended Action:</strong> {brief.get('recommended_action', 'Monitor the controller queue')}</p>"
        f"<p><strong>Human Review:</strong> {'Required' if brief.get('human_review_required') else 'Not required'}</p></div></div>",
        unsafe_allow_html=True,
    )

    with st.expander("Evidence", expanded=True):
        st.json(brief.get("evidence", []))

    st.divider()
    st.subheader("Finance Copilot Decision Assistant")

    default_prompts = [
        "What needs my attention right now?",
        "Where is the highest monetary exposure?",
        "Why are these transactions unresolved?",
        "Show me the highest-risk exception.",
        "Which source is unhealthy?",
        "What can I safely auto-resolve?",
        "What requires human review?",
        "Explain today's reconciliation performance.",
        "Why was this exception created?",
        "What evidence supports this exception?",
        "What is the financial impact of this exception?",
        "What should I do with this exception?",
        "Does this exception require human review?",
        "Explain the matching failure for this exception.",
    ]

    if "copilot_question" not in st.session_state:
        st.session_state["copilot_question"] = default_prompts[0]

    for prompt in default_prompts:
        if st.button(prompt, key=f"copilot_prompt_{prompt}"):
            st.session_state["copilot_question"] = prompt

    question = st.text_area("Ask the controller", value=st.session_state["copilot_question"])

    if st.button("Run grounded assessment", type="primary") and question.strip():
        try:
            result = api.ask_copilot(question.strip())
            st.success(f"**Answer:** {result.get('answer')}")
            st.markdown(f"**Interpretation:** {result.get('interpretation')}")
            st.markdown(f"**Recommendation:** {result.get('recommendation')}")

            decision_state = "HUMAN REVIEW" if result.get("needs_human_review") else ("AUTO-SAFE" if result.get("source") == "deterministic" else "AI-SUGGESTED")
            st.caption(f"Decision boundary: **{decision_state}**")

            with st.expander("Fact summary", expanded=True):
                st.json(result.get("fact_summary", {}))

            with st.expander("Evidence", expanded=False):
                st.json(result.get("evidence", []))
        except Exception as exc:
            st.error(f"Copilot query failed: {exc}")

    st.divider()
    try:
        exception_payload = api.list_exceptions(page_size=10)
        exception_rows = exception_payload.get("exceptions", [])
    except Exception:
        exception_rows = []

    if exception_rows:
        selected_exception = st.selectbox("Why this exception was flagged", [exc.get("exception_id") for exc in exception_rows])
        try:
            intel = api.get_exception_intelligence(selected_exception)
            st.markdown("**WHY WAS THIS FLAGGED?**")
            reasons = intel.get("why_it_happened") or intel.get("root_cause") or "No structured root cause recorded."
            st.write(reasons)
            if intel.get("what_evidence_supports_this"):
                for fact in intel.get("what_evidence_supports_this", []):
                    st.caption(f"{fact.get('label')}: {fact.get('value')}")
        except Exception as exc:
            st.caption(f"Exception explanation unavailable: {exc}")


def view_audit_trail_and_ingestion():
    st.title("📜 Audit Timeline & Operational Controls")
    st.caption("Immutable append-only audit trail of all reconciliation decisions, state transitions, and simulation tools.")

    tab_audit, tab_sim = st.tabs(["Audit Timeline", "Failure Simulation & Stream Ingest"])

    with tab_audit:
        try:
            events = api.get_audit_timeline()
            if events:
                df_events = pd.DataFrame(events)
                st.dataframe(df_events[["event_id", "timestamp", "event_type", "run_id", "transaction_id", "details"]], width='stretch', height=400)
            else:
                st.info("No audit events recorded yet.")
        except Exception as e:
            st.error(f"Failed to fetch audit timeline: {e}")

    with tab_sim:
        st.subheader("Operational Failure Scenarios")
        scenario = st.selectbox("Select Scenario:", ["corrupted_utr", "delayed_settlement", "duplicate", "groq_unavailable"])
        sim_amt = st.number_input("Test Scenario Amount (INR):", value=50000.0, step=5000.0)

        if st.button("Trigger Failure Simulation", type="primary"):
            try:
                sim_res = api.simulate_failure(scenario, sim_amt)
                st.success(f"Scenario '{scenario}' executed successfully!")
                st.json(sim_res)
            except Exception as e:
                st.error(f"Simulation failed: {e}")


def main():
    selected_view = render_sidebar()

    if selected_view == "1. Executive Overview":
        view_overview()
    elif selected_view == "2. Reconciliation Operations":
        view_reconciliation()
    elif selected_view == "3. Exception Queue":
        view_exception_queue()
    elif selected_view == "4. Exception Workspace & Actions":
        view_exception_workspace()
    elif selected_view == "5. Settlement & Accounting":
        view_settlement_accounting()
    elif selected_view == "6. Refunds & Duplicates":
        view_refunds_and_duplicates()
    elif selected_view == "7. Cash Position & Forecast":
        view_cash_position_and_forecast()
    elif selected_view == "8. Source Health":
        view_source_health()
    elif selected_view == "9. Finance AI Q&A":
        view_finance_ai_qa()
    elif selected_view == "10. AI Finance Copilot":
        view_ai_finance_copilot()
    elif selected_view == "11. Audit Trail & Ingestion":
        view_audit_trail_and_ingestion()
    elif selected_view == "12. Benchmark & Model Evaluation":
        view_benchmark_evaluation()


if __name__ == "__main__":
    main()
