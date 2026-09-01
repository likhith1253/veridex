"""
Project Sentinel — AI Finance Controller Dashboard (Razorpay Track 04).

Complete Enterprise Financial Operations & Reconciliation Control Center:
1. Executive Overview
2. Reconciliation Operations
3. Exception Queue
4. Exception Workspace & Actions
5. Settlement & Accounting
6. Refunds & Duplicates
7. Cash Position & Forecast
8. Source Health
9. Finance AI Q&A
10. AI Finance Copilot
11. Audit Trail & Ingestion
12. Benchmark & Model Evaluation
"""

import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

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


def get_selected_run_id() -> str | None:
    return st.session_state.get("selected_run_id") or None


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


def format_date(value, *, fallback="Pending"):
    if not value:
        return fallback
    try:
        s = str(value)
        if "T" in s:
            return s.split("T")[0]
        return s[:10]
    except Exception:
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

    try:
        runs_payload = api.list_runs(limit=20)
        run_options = runs_payload.get("runs", [])
    except Exception:
        run_options = []

    if run_options:
        labels = [f"{r.get('run_id')} | {r.get('status')} | {r.get('gateway_count', 0)+r.get('ledger_count', 0)+r.get('bank_count', 0)} txns" for r in run_options]
        default_idx = 0
        if st.session_state.get("selected_run_id"):
            for idx, run in enumerate(run_options):
                if run.get("run_id") == st.session_state.get("selected_run_id"):
                    default_idx = idx
                    break
        selected_idx = st.sidebar.selectbox("Run Scope", list(range(len(run_options))), format_func=lambda i: labels[i], index=default_idx)
        st.session_state["selected_run_id"] = run_options[selected_idx].get("run_id")
    else:
        st.sidebar.caption("No reconciliation runs found yet.")

    navigation_options = [
        "1. Executive Overview",
        "2. Reconciliation Operations",
        "3. Exception Queue",
        "4. Exception Workspace & Actions",
        "5. Transactions",
        "6. Settlement & Accounting",
        "7. Refunds & Duplicates",
        "8. Cash Position & Forecast",
        "9. Source Health",
        "10. Finance AI Q&A",
        "11. AI Finance Copilot",
        "12. Audit Trail & Ingestion",
        "13. Benchmark & Model Evaluation",
    ]

    selected_view = st.sidebar.radio("Navigation", navigation_options)
    st.sidebar.divider()
    st.sidebar.info("Razorpay AI Buildathon 2026\nTrack 04: AI Finance Controller\nStatus: Production Live")
    return selected_view


# 1. Executive Overview
def view_overview():
    st.title("📊 Executive Finance Controller Overview")
    st.caption("Authoritative multi-feed reconciliation KPIs, cash exposure, and throughput metrics.")

    run_id = get_selected_run_id()
    try:
        kpis = api.get_summary(run_id=run_id)
        funnel = api.get_funnel(run_id=run_id)
        cash = api.get_cash_position(run_id=run_id)
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
        st.metric(
            "Total Processed",
            format_number(kpis.get("total_records_processed", 0)) + " records",
            delta=f"{kpis.get('total_logical_transactions', 0):,} txns",
        )
    with col2:
        m_rate = kpis.get("match_rate", 0.0)
        st.metric(
            "Reconciliation Rate",
            format_percent(m_rate, decimals=1),
            delta="Deterministic + ML",
        )
    with col3:
        st.metric("ML Recovered", f"{kpis.get('ml_recovered_matches', 0):,} matches")
    with col4:
        st.metric(
            "Expected Net Settlement",
            format_money(cash.get("expected_net_settlement", cash.get("expected_amount", 0.0))),
            delta=f"Gross {format_money(cash.get('expected_gross', cash.get('expected_amount', 0.0)))}",
        )
    with col5:
        st.metric(
            "Unreconciled Exposure",
            format_money(kpis.get("unresolved_monetary_exposure_inr", 0.0)),
            delta_color="inverse",
        )
    with col6:
        tps = kpis.get("processing_throughput_tps")
        lat = kpis.get("average_processing_latency_ms")
        tps_str = f"{float(tps):.0f} tps" if tps is not None else "—"
        lat_str = f"{float(lat):.2f} ms lat" if lat is not None else None
        st.metric("Throughput", tps_str, delta=lat_str)

    st.divider()

    # Two-Column Funnel and Exposure Layout
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
                funnel.get("incoming_records", 0),
                funnel.get("deterministic_matches", 0),
                funnel.get("ml_recovered", 0),
                funnel.get("manual_reviews", 0),
                funnel.get("unresolved", 0),
            ],
        }
        df_funnel = pd.DataFrame(funnel_data)
        st.bar_chart(df_funnel.set_index("Stage"), width="stretch")

    with c2:
        st.subheader("💰 Treasury Cash & Risk Exposure")
        cc1, cc2, cc3 = st.columns(3)
        cc1.metric("Received Bank Credits", format_money(cash.get("received_amount", 0)))
        cc2.metric("Pending In Window", format_money(cash.get("pending_amount", 0)))
        cc3.metric("High-Risk Discrepancy", format_money(cash.get("at_risk_amount", 0)), delta_color="inverse")

        cat_breakdown = cash.get("breakdown_by_category", {})
        if cat_breakdown:
            st.write("**Exposure by Exception Category:**")
            df_cat = pd.DataFrame(list(cat_breakdown.items()), columns=["Category", "Exposure INR"])
            st.bar_chart(df_cat.set_index("Category"))
        else:
            st.info("No active exception categories with financial exposure.")


# 2. Reconciliation Operations
def view_reconciliation():
    st.title("🔀 Reconciliation Operations")
    st.caption("Detailed deterministic rule evaluation, ML candidate recovery, and matching metrics.")

    run_id = get_selected_run_id()
    try:
        kpis = api.get_summary(run_id=run_id)
        funnel = api.get_funnel(run_id=run_id)
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
    dec_df = pd.DataFrame(
        {
            "Decision Type": [
                "Deterministic Exact Match",
                "ML Scored Match (XGBoost)",
                "Manual Review Required",
                "Unresolved Exception",
            ],
            "Count": [
                kpis.get("deterministic_matches", 0),
                kpis.get("ml_recovered_matches", 0),
                kpis.get("manual_reviews", 0),
                kpis.get("unresolved_transactions", 0),
            ],
            "Confidence Gate": [">= 0.95", ">= 0.90", "0.70 - 0.90", "< 0.70"],
            "Action Policy": [
                "Auto-Commit",
                "Auto-Commit",
                "Flag for Controller",
                "Quarantine to Exception Queue",
            ],
        }
    )
    st.dataframe(dec_df, width="stretch")


# 3. Exception Queue
def view_exception_queue():
    st.title("⚠️ Honest Exception Queue")
    st.caption("Transparent, honest list of unresolved financial discrepancies requiring controller attention.")

    run_id = get_selected_run_id()
    # Filter Toolbar
    with st.expander("Filter Exception Queue", expanded=True):
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            status_filter = st.selectbox(
                "Status",
                ["All", "open", "investigating", "pending_review", "escalated", "approved", "resolved", "rejected"],
            )
        with col_f2:
            cat_filter = st.selectbox(
                "Category",
                [
                    "All",
                    "missing_record",
                    "amount_mismatch",
                    "timing_mismatch",
                    "duplicate_record",
                    "delayed_settlement",
                    "fee_mismatch",
                    "unexplained",
                ],
            )
        with col_f3:
            min_exp = st.number_input("Min Exposure (INR)", value=0.0, step=1000.0)
        with col_f4:
            page_num = st.number_input("Page", min_value=1, value=1, step=1)

    stat_val = None if status_filter == "All" else status_filter
    cat_val = None if cat_filter == "All" else cat_filter
    min_val = None if min_exp == 0.0 else min_exp

    try:
        exc_data = api.list_exceptions(
            status=stat_val, category=cat_val, min_exposure=min_val, run_id=run_id, page=page_num, page_size=25
        )
        aging = api.get_exception_aging(run_id=run_id)
    except Exception as e:
        st.error(f"Failed to fetch exceptions: {e}")
        return

    # Aging Summary Bar
    st.write("**Exception Aging Distribution:**")
    buckets = aging.get("buckets", [])
    ag_cols = st.columns(len(buckets) if buckets else 1)
    for idx, b in enumerate(buckets):
        with ag_cols[idx]:
            st.metric(
                b.get("bucket"),
                f"{b.get('count', 0)} open",
                delta=f"₹{b.get('financial_exposure_inr', 0.0):,.0f}",
            )

    if buckets:
        df_aging = pd.DataFrame(buckets)
        st.bar_chart(df_aging.set_index("bucket")[["financial_exposure_inr"]], width="stretch")

    st.divider()

    items = exc_data.get("exceptions", [])
    total_cnt = exc_data.get("total_count", 0)

    st.subheader(f"Open Exceptions ({total_cnt} Total)")
    if items:
        df_items = pd.DataFrame(items)
        cols_to_show = [
            c
            for c in [
                "exception_id",
                "transaction_id",
                "category",
                "status",
                "financial_exposure_inr",
                "confidence",
                "recommended_action",
                "explanation",
            ]
            if c in df_items.columns
        ]
        st.dataframe(df_items[cols_to_show], width="stretch", height=450)
    else:
        st.info("No exceptions match the current filter criteria. The live exception queue is clear for this view.")


# 4. Exception Investigation Workspace & Actions
def view_exception_workspace():
    st.title("🔍 Exception Investigation Workspace")
    st.caption("Complete investigation workflow: understand why, assess impact, and decide.")

    run_id = get_selected_run_id()
    try:
        exc_list = api.list_exceptions(run_id=run_id, page_size=50).get("exceptions", [])
    except Exception as e:
        st.error(f"Error fetching exception list: {e}")
        return

    if not exc_list:
        render_empty_state("Exception workspace", "No exception records are currently available for investigation.")
        return

    exc_options = {
        f"{e.get('exception_id')[:8]}... | {e.get('category')} | ₹{float(e.get('financial_exposure_inr') or 0):,.0f}": e.get(
            "exception_id"
        )
        for e in exc_list
    }
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
    conf_pct = decision_boundary.get("confidence", 0) * 100

    if boundary_category == "AUTO_SAFE":
        st.success(f"🟢 **AUTO-SAFE** | Confidence: {conf_pct:.1f}% | {decision_boundary.get('reason', '')}")
    elif boundary_category == "AI_SUGGESTED":
        st.warning(f"🟡 **AI-SUGGESTED** | Confidence: {conf_pct:.1f}% | {decision_boundary.get('reason', '')}")
    else:
        st.error(f"🔴 **HUMAN REVIEW REQUIRED** | Confidence: {conf_pct:.1f}% | {decision_boundary.get('reason', '')}")

    st.divider()

    # Identity Section
    st.subheader("IDENTITY")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Exception ID", inv_view.get("exception_id", "—")[:8] + "...")
    with col2:
        txn_id = inv_view.get("transaction_id")
        st.metric("Transaction ID", txn_id[:8] + "..." if txn_id else "—")
    with col3:
        src = inv_view.get("source")
        st.metric("Source", src.upper() if src else "—")
    with col4:
        st.metric("Status", inv_view.get("status", "—").upper())

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
        fee_diff = financial.get("fee_difference")
        st.metric("Fee Difference", format_money(fee_diff, fallback="—"))
    with fcol4:
        tax_diff = financial.get("tax_difference")
        st.metric("Tax Difference", format_money(tax_diff, fallback="—"))

    st.divider()

    # WHY THIS EXCEPTION Section
    st.subheader("WHY THIS EXCEPTION WAS FLAGGED")
    st.markdown(f"**Primary Reason:** {inv_view.get('root_cause') or inv_view.get('explanation') or 'No root cause established'}")
    st.markdown(f"**Financial Impact:** {format_money(financial.get('monetary_exposure'))}")

    st.markdown("**Evidence:**")
    matching = inv_view.get("matching_evidence", {})
    if matching.get("deterministic_match_result"):
        st.write(f"• Deterministic match result: `{matching.get('deterministic_match_result')}`")
    if matching.get("ml_match_result"):
        st.write(f"• ML match result: `{matching.get('ml_match_result')}`")
    for mismatch in matching.get("mismatch_fields", []):
        st.write(f"• Mismatch field: `{mismatch}`")

    st.markdown(f"**Confidence:** {inv_view.get('confidence', 0)*100:.1f}%")
    risk_bucket = inv_view.get("risk_bucket", "UNKNOWN").upper()
    st.markdown(f"**Risk:** {risk_bucket}")
    st.markdown(f"**Recommended Action:** `{inv_view.get('recommended_action', 'escalate_manual')}`")

    human_review = decision_boundary.get("requires_human_review", False)
    st.markdown(f"**Human Review:** {'REQUIRED' if human_review else 'NOT REQUIRED'}")

    st.divider()

    # Timeline Section
    st.subheader("TIMELINE")
    timeline = inv_view.get("timeline", {})
    tcol1, tcol2, tcol3, tcol4 = st.columns(4)
    with tcol1:
        st.metric("Exception Created", format_date(timeline.get("exception_created")))
    with tcol2:
        st.metric("Investigation Started", format_date(timeline.get("investigation_started"), fallback="Rule Evaluated"))
    with tcol3:
        st.metric("Human Decision", format_date(timeline.get("human_decision"), fallback="Pending"))
    with tcol4:
        st.metric("Resolved", format_date(timeline.get("resolved"), fallback="In Progress"))

    st.divider()

    # Decision Panel
    st.subheader("DECISION")
    resolved = inv_view.get("resolved", False)

    if resolved:
        st.success(f"✅ This exception has been resolved as of {inv_view.get('resolved_at', '—')}")
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


# 5. Transactions
def view_transactions():
    st.title("📄 Transaction Ledger")
    st.caption("Run-scoped transaction rows exactly as persisted by the backend.")

    current_run = get_selected_run_id() or ""
    run_id = st.text_input("Run ID", value=current_run)
    limit = st.number_input("Limit", min_value=1, max_value=1000, value=100, step=10)

    try:
        payload = api.list_transactions(run_id=run_id or None, limit=int(limit))
    except Exception as e:
        st.error(f"Failed to fetch transactions: {e}")
        return

    txns = payload.get("transactions", [])
    st.metric("Transactions", f"{payload.get('total_count', len(txns)):,}")
    if txns:
        df = pd.DataFrame(txns)
        cols = [
            c
            for c in [
                "domain_transaction_id",
                "source",
                "order_id",
                "reference_number",
                "amount",
                "currency",
                "timestamp",
                "status",
            ]
            if c in df.columns
        ]
        st.dataframe(df[cols], width="stretch", height=450)
    else:
        render_empty_state("Transactions", "No transactions are available for the selected run.")


# 5. Settlement & Accounting Control
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

    st.markdown(
        f"""
    <div class="accounting-box">
        <div class="accounting-step"><span>Gross Gateway Volume</span><span>{format_money(settlement.get('gross_gateway_volume', 0))}</span></div>
        <div class="accounting-step"><span>(-) Total Deducted MDR Fees</span><span>-{format_money(settlement.get('total_deducted_fees', 0))}</span></div>
        <div class="accounting-step"><span>(-) Total Deducted Taxes (18% GST)</span><span>-{format_money(settlement.get('total_deducted_taxes', 0))}</span></div>
        <div class="accounting-step"><span>(-) Total Customer Refunds</span><span>-{format_money(settlement.get('total_refunded_amount', 0))}</span></div>
        <div class="accounting-step-highlight"><span>(=) Expected Net Bank Settlement</span><span>{format_money(settlement.get('expected_net_settlement', 0))}</span></div>
        <div class="accounting-step-highlight"><span>Actual Bank Statement Credits Received</span><span>{format_money(settlement.get('actual_bank_settled_credits', 0))}</span></div>
        <div class="accounting-step"><span>Net Settlement Variance</span><span>{format_money(settlement.get('net_settlement_variance', 0))}</span></div>
    </div>
    """,
        unsafe_allow_html=True,
    )

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
    c3.metric("Fee/Tax Exposure", format_money(feetax.get("total_fee_tax_exposure", 0)))


# 6. Refunds & Duplicates Auditing
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
        r2.metric(
            "Fully / Partially Refunded",
            f"{refunds.get('fully_refunded_count', 0) + refunds.get('partially_refunded_count', 0)}",
        )
        r3.metric(
            "Over-Refund Anomalies",
            f"{refunds.get('over_refund_anomalies_count', 0)}",
            delta=f"{format_money(refunds.get('total_over_refund_exposure', 0))}",
            delta_color="inverse",
        )

    with c2:
        st.subheader("Duplicate Incident Classification")
        d1, d2, d3 = st.columns(3)
        d1.metric("Total Incidents", f"{duplicates.get('total_incidents_detected', 0)}")
        d2.metric(
            "Duplicate Gateway Charges",
            f"{duplicates.get('duplicate_charges_count', 0)}",
            delta=f"{format_money(duplicates.get('duplicate_charges_exposure', 0))}",
        )
        d3.metric(
            "Duplicate Bank Credits",
            f"{duplicates.get('duplicate_settlements_count', 0)}",
            delta=f"{format_money(duplicates.get('duplicate_settlements_exposure', 0))}",
        )

    st.divider()

    st.subheader("Incident Evidence Records")
    incidents = duplicates.get("incidents", [])
    if incidents:
        st.dataframe(pd.DataFrame(incidents), width="stretch")
    else:
        st.info("No active duplicate payment incidents detected.")


# 7. Cash Position & Forecast
def view_cash_position_and_forecast():
    st.title("💰 Cash Position & 7-Day Settlement Forecast")
    st.caption("Current multi-source liquidity position and transparent forward settlement projections.")

    run_id = get_selected_run_id()
    try:
        cash = api.get_cash_position(run_id=run_id)
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

    st.caption(
        "Accounting Invariant: Gross Volume - MDR Fees - GST - Refunds = Expected Net Bank Settlement | Actual Bank Credits - Expected Net = Net Settlement Variance"
    )

    st.divider()

    st.subheader("7-Day Forward Settlement Forecast (Moving Average)")
    st.caption(
        f"Methodology: {forecast.get('methodology')} | 7-Day Inflow Total: {format_money(forecast.get('seven_day_forecast_total_inr', 0))}"
    )

    if not forecast.get("historical_data_sufficient", True) and forecast.get("distinct_historical_days", 0) > 0:
        st.warning(
            "⚠️ Baseline Projection: Limited historical dates available (< 3 days). As additional batches are ingested, empirical volatility bounds will automatically refine."
        )

    days = forecast.get("forecast_days", [])
    if days:
        df_fc = pd.DataFrame(days)
        st.line_chart(df_fc.set_index("date")[["forecast_amount_inr", "confidence_interval_low", "confidence_interval_high"]])
        st.dataframe(df_fc, width="stretch")
    else:
        st.info("No transaction history available to compute settlement projections.")


# 8. Feed Source Health
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
    st.caption(
        "ℹ️ Feed metrics reflect real PostgreSQL ingestion records. Transactions can be matched across feeds while carrying exceptions (e.g., fee discrepancies). Clean Match indicates records reconciled without any exceptions."
    )

    sources = health.get("sources", {})
    s_cols = st.columns(len(sources) if sources else 1)

    for idx, (src_key, s_data) in enumerate(sources.items()):
        with s_cols[idx]:
            clean_pct = s_data.get("clean_match_rate_percent", s_data.get("match_rate_percent", 100.0))
            st.metric(
                s_data.get("source_name", src_key),
                f"{s_data.get('total_records', 0):,} records",
                delta=f"{clean_pct:.1f}% clean match",
            )
            st.write(f"**Volume:** {format_money(s_data.get('total_volume_inr', 0))}")
            st.write(
                f"**Matched in Clusters:** {s_data.get('matched_records', 0)} ({s_data.get('match_rate_percent', 0.0):.1f}%)"
            )
            st.write(
                f"**Flagged Exceptions:** {s_data.get('exception_records', 0)} ({s_data.get('exception_rate_percent', 0.0):.1f}%)"
            )
            st.write(f"**Status:** `{s_data.get('health_status', 'HEALTHY')}`")


# 9. Grounded Finance AI Q&A
def view_finance_ai_qa():
    st.title("💬 Grounded Finance Controller AI Q&A")
    st.caption("Ask natural language treasury and reconciliation questions grounded strictly in PostgreSQL state (zero hallucinations).")

    run_id = get_selected_run_id()
    prompts = [
        "What is the total unresolved financial exposure?",
        "How much money was recovered by ML candidate scoring?",
        "What is the breakdown of open exceptions by category?",
        "Which exceptions have the highest monetary exposure?",
        "Why is there a discrepancy in today's settlement?",
        "Custom query...",
    ]

    selected_prompt = st.selectbox("Suggested Controller Questions:", prompts)
    default_q = "" if selected_prompt == "Custom query..." else selected_prompt
    question = st.text_input("Enter Finance Operations Question:", value=default_q)

    if st.button("Analyze with Controller AI", type="primary") and question.strip():
        with st.spinner("Executing verifiable SQL metric aggregation and reasoning..."):
            try:
                qa_res = api.ask_qa(question.strip(), run_id=run_id)
                st.markdown(
                    f"<div class='qa-answer-box'><strong>Direct Controller Answer:</strong><br>{qa_res.get('direct_answer')}</div>",
                    unsafe_allow_html=True,
                )

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
                    st.dataframe(pd.DataFrame(ev), width="stretch")
                else:
                    st.info("The controller returned no evidence records for this query.")

            except Exception as e:
                st.error(f"Q&A query failed: {e}")


# 10. AI Finance Brief & Copilot
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

    with st.expander("Evidence Facts", expanded=False):
        st.json(brief.get("evidence", []))

    st.divider()
    st.subheader("Finance Copilot Decision Assistant")

    copilot_prompts = [
        "What needs my attention right now?",
        "Where is the highest monetary exposure?",
        "Why are these transactions unresolved?",
        "Show me the highest-risk exception.",
        "Which source is unhealthy?",
        "What can I safely auto-resolve?",
        "What requires human review?",
        "Explain today's reconciliation performance.",
        "Custom query...",
    ]

    selected_cp_prompt = st.selectbox("Quick Copilot Queries:", copilot_prompts)
    cp_default = "" if selected_cp_prompt == "Custom query..." else selected_cp_prompt
    question = st.text_input("Ask the controller:", value=cp_default)

    if st.button("Run Grounded Assessment", type="primary") and question.strip():
        with st.spinner("Analyzing real-time reconciliation state and policy boundaries..."):
            try:
                result = api.ask_copilot(question.strip())
                st.markdown(
                    f"<div class='qa-answer-box'><strong>Controller Answer:</strong><br>{result.get('answer')}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(f"**Interpretation:** {result.get('interpretation')}")
                st.markdown(f"**Recommendation:** `{result.get('recommendation')}`")

                decision_state = (
                    "HUMAN REVIEW"
                    if result.get("needs_human_review")
                    else ("AUTO-SAFE" if result.get("source") == "deterministic" else "AI-SUGGESTED")
                )
                st.caption(f"Decision boundary: **{decision_state}**")

                with st.expander("Fact summary", expanded=True):
                    st.json(result.get("fact_summary", {}))

                with st.expander("Evidence", expanded=False):
                    st.json(result.get("evidence", []))
            except Exception as exc:
                st.error(f"Copilot query failed: {exc}")

    st.divider()
    try:
        exception_payload = api.list_exceptions(run_id=run_id, page_size=20)
        exception_rows = exception_payload.get("exceptions", [])
    except Exception:
        exception_rows = []

    if exception_rows:
        st.subheader("Explainable Exception Intelligence")
        selected_exception = st.selectbox(
            "Select Exception to Explain:",
            [
                f"{exc.get('exception_id')[:8]}... | {exc.get('category')} | ₹{float(exc.get('financial_exposure_inr') or 0):,.0f}"
                for exc in exception_rows
            ],
        )
        chosen_id = selected_exception.split("...")[0]
        full_id = next((e.get("exception_id") for e in exception_rows if e.get("exception_id", "").startswith(chosen_id)), None)

        if full_id:
            try:
                intel = api.get_exception_intelligence(full_id)
                st.markdown(f"**Root Cause:** {intel.get('why_it_happened') or intel.get('root_cause') or 'No structured root cause recorded.'}")
                st.markdown(f"**Recommended Action:** `{intel.get('recommended_action', 'escalate_manual')}`")
                
                how_serious = intel.get("how_serious", {})
                if how_serious:
                    st.caption(f"Risk Bucket: **{how_serious.get('risk_bucket', '—').upper()}** | Score: **{how_serious.get('risk_score', 0):.2f}** | Exposure: **₹{how_serious.get('financial_exposure_inr', 0):,.2f}**")
                
                if intel.get("what_evidence_supports_this"):
                    st.write("**Supporting Facts:**")
                    for fact in intel.get("what_evidence_supports_this", []):
                        st.caption(f"• {fact.get('label')}: {fact.get('value')}")
            except Exception as exc:
                st.caption(f"Exception explanation unavailable: {exc}")


# 11. Audit Trail & Ingestion
def view_audit_trail_and_ingestion():
    st.title("📜 Audit Timeline & Operational Controls")
    st.caption("Immutable append-only audit trail of all reconciliation decisions, state transitions, and simulation tools.")

    tab_audit, tab_sim = st.tabs(["Audit Timeline", "Operational Scenarios & Ingestion"])

    with tab_audit:
        try:
            events = api.get_audit_timeline()
            if events:
                df_events = pd.DataFrame(events)
                cols = [c for c in ["event_id", "timestamp", "event_type", "run_id", "transaction_id", "details"] if c in df_events.columns]
                st.dataframe(df_events[cols], width="stretch", height=450)
            else:
                st.info("No audit events recorded yet.")
        except Exception as e:
            st.error(f"Failed to fetch audit timeline: {e}")

    with tab_sim:
        st.subheader("Simulate Failure Scenarios")
        st.caption("Inject edge-case failures to audit system resilience, anomaly detection, and automated isolation.")

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            scenario = st.selectbox(
                "Select Operational Scenario:",
                ["corrupted_utr", "delayed_settlement", "duplicate", "fee_mismatch", "groq_unavailable"],
            )
            sim_amt = st.number_input("Test Scenario Amount (INR):", value=50000.0, step=5000.0)

            if st.button("Trigger Failure Simulation", type="primary"):
                try:
                    sim_res = api.simulate_failure(scenario, sim_amt)
                    st.success(f"Scenario '{scenario}' executed successfully!")
                    st.json(sim_res)
                    st.rerun()
                except Exception as e:
                    st.error(f"Simulation failed: {e}")

        with col_s2:
            st.subheader("Re-seed Full Diverse Dataset")
            st.caption("Ingests a fresh batch of 60+ multi-feed transactions spanning all scenarios (normal, fee mismatch, delayed, duplicate, wrong ref, ambiguous).")
            if st.button("Ingest Diverse Benchmark Batch"):
                try:
                    import random
                    from datetime import datetime, timezone, timedelta
                    from simulator.generator import DataGenerator, GeneratorConfig
                    from app.models.transaction import Transaction, TransactionSource, TransactionStatus
                    
                    cfg = GeneratorConfig(num_transactions=50, seed=random.randint(1, 99999), date_range_days=5)
                    gen = DataGenerator(cfg)
                    gw_recs, ld_recs, bk_recs, _ = gen.generate()
                    
                    now = datetime.now(timezone.utc)
                    gw_txns = [
                        {
                            "txn_id": r.settlement_id,
                            "amount": float(r.gross_amount),
                            "currency": r.currency,
                            "timestamp": (now - timedelta(days=random.randint(0, 3), hours=random.randint(1, 12))).isoformat(),
                            "order_id": r.order_id,
                            "reference_number": r.utr,
                            "fee": float(r.fee) if r.fee else None,
                            "tax": float(r.tax) if r.tax else None,
                        } for r in gw_recs if r is not None
                    ]
                    ld_txns = [
                        {
                            "txn_id": f"LD_{r.order_id}",
                            "amount": float(r.transaction_amount),
                            "currency": r.currency,
                            "timestamp": (now - timedelta(days=random.randint(0, 3), hours=random.randint(1, 12))).isoformat(),
                            "order_id": r.order_id,
                            "reference_number": r.internal_reference,
                        } for r in ld_recs if r is not None
                    ]
                    bk_txns = [
                        {
                            "txn_id": r.bank_transaction_id,
                            "amount": float(r.credit_amount),
                            "currency": r.currency,
                            "timestamp": (now - timedelta(days=random.randint(0, 3), hours=random.randint(1, 12))).isoformat(),
                            "reference_number": r.utr,
                            "narration": r.narration,
                        } for r in bk_recs if r is not None
                    ]
                    
                    import httpx
                    with httpx.Client(timeout=30.0) as client:
                        resp = client.post(
                            "http://127.0.0.1:8000/api/v1/controller/ingest/batch",
                            json={
                                "gateway_records": gw_txns,
                                "ledger_records": ld_txns,
                                "bank_records": bk_txns,
                                "batch_id": f"ui_batch_{random.randint(100, 999)}",
                            }
                        )
                        resp.raise_for_status()
                        st.success("Diverse batch ingested and reconciled successfully!")
                        st.json(resp.json())
                        st.rerun()
                except Exception as e:
                    st.error(f"Ingestion failed: {e}")


# 12. Benchmark & Model Evaluation
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
    st.json(
        {
            "num_transactions": b.get("num_transactions"),
            "seed": b.get("seed"),
            "currency": b.get("currency"),
            "dataset_name": b.get("dataset_name"),
        }
    )

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
        cols = [c for c in ["scenario", "total_records", "precision", "recall", "f1_score", "unresolved_records"] if c in sc_df.columns]
        st.dataframe(sc_df[cols], width="stretch")

    st.subheader("Full Evaluation JSON")
    st.json(r)


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
    elif selected_view == "5. Transactions":
        view_transactions()
    elif selected_view == "6. Settlement & Accounting":
        view_settlement_accounting()
    elif selected_view == "7. Refunds & Duplicates":
        view_refunds_and_duplicates()
    elif selected_view == "8. Cash Position & Forecast":
        view_cash_position_and_forecast()
    elif selected_view == "9. Source Health":
        view_source_health()
    elif selected_view == "10. Finance AI Q&A":
        view_finance_ai_qa()
    elif selected_view == "11. AI Finance Copilot":
        view_ai_finance_copilot()
    elif selected_view == "12. Audit Trail & Ingestion":
        view_audit_trail_and_ingestion()
    elif selected_view == "13. Benchmark & Model Evaluation":
        view_benchmark_evaluation()


if __name__ == "__main__":
    main()
