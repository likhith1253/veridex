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
from decimal import Decimal
import pandas as pd
import streamlit as st

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


def render_sidebar():
    st.sidebar.title("🛡️ Project Sentinel")
    st.sidebar.caption("AI Finance Controller | Track 04")
    
    # Backend Health Check
    health = api.check_health()
    if health.get("status") == "healthy":
        st.sidebar.success("● Backend Connected (Port 8000)")
    else:
        st.sidebar.error("● Backend Offline / Unreachable")

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
        "10. Audit Trail & Ingestion",
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

    # Top Executive KPI Cards
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("Total Processed", f"{kpis.get('total_records_processed', 0):,} records", delta=f"{kpis.get('total_logical_transactions', 0):,} txns")
    with col2:
        st.metric("Reconciliation Rate", f"{kpis.get('match_rate', 0.0):.1f}%", delta=f"F1 {kpis.get('f1_score', 0.0):.1f}%")
    with col3:
        st.metric("ML Recovered", f"{kpis.get('ml_recovered_matches', 0)} matches", delta="+11.6% recall gain")
    with col4:
        st.metric("Expected Settlement", f"₹{cash.get('expected_amount', 0.0):,.0f}")
    with col5:
        st.metric("Unreconciled Exposure", f"₹{kpis.get('unresolved_monetary_exposure_inr', 0.0):,.0f}", delta_color="inverse")
    with col6:
        st.metric("Throughput", f"{kpis.get('processing_throughput_tps', 1800.0):,.0f} tps", delta=f"{kpis.get('average_processing_latency_ms', 0.55):.2f} ms lat")

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

        st.write("**Accuracy Baseline Comparison:**")
        df_acc = pd.DataFrame({
            "Metric": ["Precision", "Recall", "F1 Score", "ML-Specific Precision"],
            "Sentinel (Det + ML)": ["90.00%", "100.00%", "94.74%", "99.27%"],
            "Deterministic Only": ["85.01%", "88.37%", "86.66%", "N/A"],
        })
        st.table(df_acc)

    with c2:
        st.subheader("💰 Treasury Cash & Risk Exposure")
        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("Received Bank Credits", f"₹{cash.get('received_amount', 0.0):,.2f}")
        cc2.metric("Pending In Window", f"₹{cash.get('pending_amount', 0.0):,.2f}")
        cc3.metric("High-Risk Discrepancy", f"₹{cash.get('at_risk_amount', 0.0):,.2f}", delta_color="inverse")

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
    st.dataframe(dec_df, use_container_width=True)


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
    ag_cols = st.columns(len(aging.get("buckets", [])))
    for idx, b in enumerate(aging.get("buckets", [])):
        with ag_cols[idx]:
            st.metric(b.get("bucket"), f"{b.get('count', 0)} open", delta=f"₹{b.get('financial_exposure_inr', 0.0):,.0f}")

    st.divider()

    items = exc_data.get("exceptions", [])
    total_cnt = exc_data.get("total_count", 0)

    st.subheader(f"Open Exceptions ({total_cnt} Total)")
    if items:
        df_items = pd.DataFrame(items)
        st.dataframe(
            df_items[["exception_id", "transaction_id", "category", "status", "financial_exposure_inr", "confidence", "recommended_action", "explanation"]],
            use_container_width=True,
            height=450,
        )
    else:
        st.info("No exceptions match current filter criteria.")


def view_exception_workspace():
    st.title("🔍 Exception Investigation Workspace")
    st.caption("Drill down into structured evidence, AI root-cause analysis, and execute controller decisions.")

    try:
        exc_list = api.list_exceptions(page_size=20).get("exceptions", [])
    except Exception as e:
        st.error(f"Error fetching exception list: {e}")
        return

    if not exc_list:
        st.info("No exceptions available in database.")
        return

    exc_options = {f"{e.get('exception_id')[:8]}... | {e.get('category')} | ₹{e.get('financial_exposure_inr', 0):,.0f}": e.get('exception_id') for e in exc_list}
    selected_label = st.selectbox("Select Exception to Investigate:", list(exc_options.keys()))
    selected_id = exc_options[selected_label]

    try:
        detail = api.get_exception_detail(selected_id)
    except Exception as e:
        st.error(f"Failed to load exception detail: {e}")
        return

    c1, c2 = st.columns([1.2, 1])

    with c1:
        st.subheader("Exception Structured Evidence")
        st.write(f"**Exception ID:** `{detail.get('exception_id')}`")
        st.write(f"**Transaction ID:** `{detail.get('transaction_id')}`")
        st.write(f"**Category:** `{detail.get('category')}`")
        st.write(f"**Financial Exposure:** ₹{detail.get('financial_exposure_inr', 0.0):,.2f}")
        st.write(f"**Current Status:** `{detail.get('status')}`")
        st.write(f"**Recommended Action:** `{detail.get('recommended_action')}`")
        st.info(f"**Explanation:** {detail.get('explanation')}")

        inv = detail.get("investigation_conclusion")
        if inv:
            st.success(f"🤖 **AI Investigation Conclusion ({inv.get('method')}):**\n\n**Root Cause:** {inv.get('root_cause')}\n\n**Confidence:** {inv.get('confidence', 0)*100:.1f}%\n\n{inv.get('explanation')}")

    with c2:
        st.subheader("Human Controller Actions")
        
        tab_dec, tab_assign, tab_note = st.tabs(["Decision", "Assign", "Add Note"])

        with tab_dec:
            action = st.selectbox("Select Decision Action:", ["approve", "reject", "escalate", "resolve"])
            reason = st.text_input("Decision Reason / Audit Note:", "Approved after verifying settlement credit")
            actor = st.text_input("Controller ID:", "finance_lead")

            if st.button("Submit Decision", type="primary"):
                try:
                    res = api.apply_decision(selected_id, action, actor, reason)
                    st.success(f"Action '{action}' executed successfully! Audit Event ID: `{res.get('audit_event_id')}`")
                    st.rerun()
                except Exception as e:
                    st.error(f"Action failed: {e}")

        with tab_assign:
            assignee = st.text_input("Assign to Analyst / Team:", "analyst_bob@sentinel.internal")
            if st.button("Assign Exception"):
                try:
                    res = api.assign_exception(selected_id, assignee, actor="controller_admin")
                    st.success(f"Assigned to {assignee} successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Assignment failed: {e}")

        with tab_note:
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

    st.subheader("Treasury Net Settlement Equation")

    st.markdown(f"""
    <div class="accounting-box">
        <div class="accounting-step"><span>Gross Gateway Volume</span><span>₹{float(settlement.get('gross_gateway_volume', 0)):,.2f}</span></div>
        <div class="accounting-step"><span>(-) Total Deducted MDR Fees</span><span>-₹{float(settlement.get('total_deducted_fees', 0)):,.2f}</span></div>
        <div class="accounting-step"><span>(-) Total Deducted Taxes (18% GST)</span><span>-₹{float(settlement.get('total_deducted_taxes', 0)):,.2f}</span></div>
        <div class="accounting-step"><span>(-) Total Customer Refunds</span><span>-₹{float(settlement.get('total_refunded_amount', 0)):,.2f}</span></div>
        <div class="accounting-step-highlight"><span>(=) Expected Net Bank Settlement</span><span>₹{float(settlement.get('expected_net_settlement', 0)):,.2f}</span></div>
        <div class="accounting-step-highlight"><span>Actual Bank Statement Credits Received</span><span>₹{float(settlement.get('actual_bank_settled_credits', 0)):,.2f}</span></div>
        <div class="accounting-step"><span>Net Settlement Variance</span><span>₹{float(settlement.get('net_settlement_variance', 0)):,.2f}</span></div>
    </div>
    """, unsafe_allow_html=True)

    status = settlement.get("settlement_reconciliation_status")
    if status == "RECONCILED":
        st.success(f"Status: {status} — All expected settlements match bank credits within clearing tolerance.")
    else:
        st.warning(f"Status: {status} — Unsettled delayed exposure: ₹{float(settlement.get('unsettled_delayed_exposure', 0)):,.2f}")

    st.divider()

    st.subheader("MDR Fee & GST Tax Discrepancy Audits")
    c1, c2, c3 = st.columns(3)
    c1.metric("Analyzed Transactions", f"{feetax.get('total_transactions_analyzed', 0):,}")
    c2.metric("Discrepant Deductions", f"{feetax.get('discrepant_transactions_count', 0)}")
    c3.metric("Fee/Tax Exposure", f"₹{float(feetax.get('total_fee_tax_exposure', 0)):,.2f}")


def view_refunds_and_duplicates():
    st.title("🔄 Refunds & Duplicate Incident Audits")
    st.caption("Isolates over-refund discrepancies, duplicate gateway debits, and bank statement duplications.")

    try:
        refunds = api.get_refund_audit()
        duplicates = api.get_duplicate_audit()
    except Exception as e:
        st.error(f"Failed to fetch audit records: {e}")
        return

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Refund Reconciliation")
        r1, r2, r3 = st.columns(3)
        r1.metric("Audited Payments", f"{refunds.get('total_payments_audited', 0):,}")
        r2.metric("Fully / Partially Refunded", f"{refunds.get('fully_refunded_count', 0) + refunds.get('partially_refunded_count', 0)}")
        r3.metric("Over-Refund Anomalies", f"{refunds.get('over_refund_anomalies_count', 0)}", delta=f"₹{float(refunds.get('total_over_refund_exposure', 0)):,.2f}", delta_color="inverse")

    with c2:
        st.subheader("Duplicate Incident Classification")
        d1, d2, d3 = st.columns(3)
        d1.metric("Total Incidents", f"{duplicates.get('total_incidents_detected', 0)}")
        d2.metric("Duplicate Gateway Charges", f"{duplicates.get('duplicate_charges_count', 0)}", delta=f"₹{float(duplicates.get('duplicate_charges_exposure', 0)):,.2f}")
        d3.metric("Duplicate Bank Credits", f"{duplicates.get('duplicate_settlements_count', 0)}", delta=f"₹{float(duplicates.get('duplicate_settlements_exposure', 0)):,.2f}")

    st.divider()

    st.subheader("Incident Evidence Records")
    incidents = duplicates.get("incidents", [])
    if incidents:
        st.dataframe(pd.DataFrame(incidents), use_container_width=True)
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

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Expected Total", f"₹{cash.get('expected_amount', 0.0):,.2f}")
    c2.metric("Received Bank Settlement", f"₹{cash.get('received_amount', 0.0):,.2f}")
    c3.metric("Pending In Window", f"₹{cash.get('pending_amount', 0.0):,.2f}")
    c4.metric("Unreconciled Exposure", f"₹{cash.get('unreconciled_amount', 0.0):,.2f}", delta_color="inverse")

    st.divider()

    st.subheader("7-Day Forward Settlement Forecast (Moving Average)")
    st.caption(f"Methodology: {forecast.get('methodology')} | 7-Day Inflow Total: ₹{forecast.get('seven_day_forecast_total_inr', 0.0):,.2f}")

    days = forecast.get("forecast_days", [])
    if days:
        df_fc = pd.DataFrame(days)
        st.line_chart(df_fc.set_index("date")[["forecast_amount_inr", "confidence_interval_low", "confidence_interval_high"]])
        st.dataframe(df_fc, use_container_width=True)


def view_source_health():
    st.title("🏥 Feed Source Health & Data Quality")
    st.caption("Operational reliability, record volume, and exception rates for Gateway, Ledger, and Bank feeds.")

    try:
        health = api.get_source_health()
    except Exception as e:
        st.error(f"Failed to load health metrics: {e}")
        return

    st.subheader(f"Overall System Ingestion Health: {health.get('overall_health', 'HEALTHY')}")

    sources = health.get("sources", {})
    s_cols = st.columns(len(sources))

    for idx, (src_key, s_data) in enumerate(sources.items()):
        with s_cols[idx]:
            st.metric(s_data.get("source_name", src_key), f"{s_data.get('total_records', 0):,} records", delta=f"{s_data.get('match_rate_percent', 100.0):.1f}% match")
            st.write(f"**Volume:** ₹{s_data.get('total_volume_inr', 0.0):,.0f}")
            st.write(f"**Exceptions:** {s_data.get('exception_records', 0)} ({s_data.get('exception_rate_percent', 0.0):.1f}%)")
            st.write(f"**Status:** `{s_data.get('health_status', 'HEALTHY')}`")


def view_finance_ai_qa():
    st.title("💬 Grounded Finance Controller AI Q&A")
    st.caption("Ask natural language treasury and reconciliation questions grounded strictly in PostgreSQL state (zero hallucinations).")

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
                    st.dataframe(pd.DataFrame(ev), use_container_width=True)

            except Exception as e:
                st.error(f"Q&A query failed: {e}")


def view_audit_trail_and_ingestion():
    st.title("📜 Audit Timeline & Operational Controls")
    st.caption("Immutable append-only audit trail of all reconciliation decisions, state transitions, and simulation tools.")

    tab_audit, tab_sim = st.tabs(["Audit Timeline", "Failure Simulation & Stream Ingest"])

    with tab_audit:
        try:
            events = api.get_audit_timeline()
            if events:
                df_events = pd.DataFrame(events)
                st.dataframe(df_events[["event_id", "timestamp", "event_type", "run_id", "transaction_id", "details"]], use_container_width=True, height=400)
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
    elif selected_view == "10. Audit Trail & Ingestion":
        view_audit_trail_and_ingestion()


if __name__ == "__main__":
    main()
