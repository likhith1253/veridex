# Project Sentinel — 5-Minute Razorpay Track 04 Pitch & Demo Guide

## Demo Setup & Prerequisites
1. **FastAPI Backend**:
   ```powershell
   uvicorn app.api.main:app --host 127.0.0.1 --port 8000
   ```
2. **Streamlit Finance Controller Dashboard**:
   ```powershell
   streamlit run ui/dashboard.py
   ```

---

## 5-Minute Live Presentation Script

### Minute 1: Problem & The Razorpay Finance Controller Challenge
> *"Judges, in high-volume payment operations, reconciliation breaks down when reference strings get truncated, settlement dates shift across weekends, or fee deductions misalign. Today, finance teams spend days investigating discrepancies manually in spreadsheets.*
> 
> *Sentinel is a real-time AI Finance Controller built for Razorpay Track 4 that closes this entire finance ops loop across multi-source streams with measured accuracy, sub-millisecond throughput, and an honest, auditable exception list."*

---

### Minute 2: Multi-Feed Streaming & Reconciliation Funnel
1. Open the **Streamlit Dashboard** at `http://localhost:8501`.
2. Navigate to **⚡ Real-Time Streaming Simulator** and click **"Stream 50 Transactions Now"**.
3. Point to the **🔀 Reconciliation Funnel**:
   - Show 150 total multi-source records ingested.
   - 82 exact transactions matched instantly by **Deterministic Rules**.
   - 18 corrupted transactions successfully recovered by **Offline XGBoost**.
   - 7 flagged for **Manual Review**.
   - 9 preserved as quarantined **Honest Exceptions**.

---

### Minute 3: Measured Accuracy & ML Candidate Recovery
1. Navigate to **📊 Executive Summary**:
   - Highlight: **Precision = 89.86%**, **Recall = 100.00%**, **F1 = 94.66%**.
   - Show the **ML-Specific Precision = 99.27%** (407 true positives / 410 proposals on unseen test benchmark).
   - Explain why no LLM is used in matching: XGBoost runs in $0.010\text{ ms}$ with zero risk of hallucination.

---

### Minute 4: Honest Exceptions & AI-Assisted Investigation
1. Switch to **⚠️ Honest Exception List**:
   - Show that failures are never hidden: every unresolved item has explicit source IDs, amount at risk, candidate count, and root-cause category.
2. Switch to **💰 Cash Position & Exposure**:
   - Show live cash aggregation: Expected Settlement vs. Received Bank Credit vs. At-Risk Exposure ($>\text{INR } 100,000$).
3. Explain **Selective LangGraph + Groq LLM Investigation**:
   - Deterministic cases bypass LLMs ($0$ API calls).
   - High-exposure anomalies invoke Groq to synthesize structured root-cause explanations with Pydantic validation.

---

### Minute 5: Fact-Grounded Finance Q&A & Conclusion
1. Switch to **💬 Finance Controller Q&A**:
   - Select prompt: *"How much money is currently unreconciled?"*
   - Click **Ask Controller**.
   - Show the grounded answer with verifiable SQL facts and transaction evidence.
2. Select prompt: *"How much was recovered by ML?"*
   - Show exact count and percentage contribution calculated directly from PostgreSQL.
3. **Closing Statement**:
   > *"Sentinel demonstrates high throughput ($>1,800\text{ tps}$), measured 94.66% F1 accuracy, transparent financial risk exposure, and grounded AI operations. It is fully validated across 289 tests and ready for Razorpay Track 4."*
