"use client";

import React, { useState } from "react";
import {
  X,
  Send,
  Brain,
  Loader2,
  Database,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileCode,
  ShieldAlert,
  ArrowRight,
} from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import type { CopilotQueryResponse } from "@/types/controller";
import { TechnicalReference } from "@/components/common/TechnicalReference";

interface CopilotDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

interface StructuredCopilotMessage {
  role: "user" | "assistant";
  text: string;
  answer?: string;
  facts?: Array<{ label: string; value: string }>;
  evidenceItems?: Array<{ label: string; value: string }>;
  interpretation?: string;
  recommendation?: string;
  confidence?: number | null;
  rawJson?: unknown;
}

function parseAssistantResponse(data: CopilotQueryResponse, rawText?: string): StructuredCopilotMessage {
  let answer = data.direct_answer || data.answer || "";
  let interpretation = data.interpretation || "";
  const recommendation = data.recommendation || "";
  const confidence = data.confidence;
  let rawJson: unknown = data;

  // If answer itself is JSON formatted string, parse it cleanly
  if (typeof answer === "string" && answer.trim().startsWith("{") && answer.trim().endsWith("}")) {
    try {
      const parsed = JSON.parse(answer);
      rawJson = parsed;
      answer = parsed.answer || parsed.direct_answer || parsed.summary || parsed.message || answer;
      if (!interpretation && parsed.interpretation) interpretation = parsed.interpretation;
    } catch {
      // Keep original answer
    }
  }

  // Parse financial facts from fact_summary or sql_facts_used
  const facts: Array<{ label: string; value: string }> = [];
  const factObj = (data as any).fact_summary || (data as any).facts;
  if (factObj && typeof factObj === "object") {
    Object.entries(factObj).forEach(([k, v]) => {
      if (v !== null && v !== undefined) {
        const label = k.replace(/_/g, " ");
        let valStr = String(v);
        if (typeof v === "number" && k.toLowerCase().includes("inr")) {
          valStr = `₹${v.toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
        } else if (typeof v === "number" && k.toLowerCase().includes("percent")) {
          valStr = `${v.toFixed(1)}%`;
        }
        facts.push({ label, value: valStr });
      }
    });
  } else if (data.sql_facts_used && Array.isArray(data.sql_facts_used)) {
    data.sql_facts_used.forEach((item) => {
      if (typeof item === "string" && item.includes(":")) {
        const [l, ...rest] = item.split(":");
        facts.push({ label: l.trim(), value: rest.join(":").trim() });
      } else {
        facts.push({ label: "Verified Fact", value: typeof item === "object" ? JSON.stringify(item) : String(item) });
      }
    });
  }

  // Parse evidence references
  const evidenceItems: Array<{ label: string; value: string }> = [];
  const rawEv = (data as any).evidence;
  if (Array.isArray(rawEv)) {
    rawEv.forEach((item, idx) => {
      if (typeof item === "object" && item !== null) {
        const id = item.exception_id || item.transaction_id || item.payment_id || item.order_id || `item_${idx + 1}`;
        const desc = item.category || item.explanation || item.status || "Verified record";
        evidenceItems.push({ label: desc, value: id });
      } else if (typeof item === "string") {
        evidenceItems.push({ label: "Record Reference", value: item });
      }
    });
  }

  return {
    role: "assistant",
    text: answer || rawText || "Query completed.",
    answer: answer || rawText || "Query completed.",
    facts,
    evidenceItems,
    interpretation,
    recommendation,
    confidence,
    rawJson,
  };
}

export function CopilotDrawer({ isOpen, onClose }: CopilotDrawerProps) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<StructuredCopilotMessage[]>([
    {
      role: "assistant",
      text: "VERIDEX Financial Copilot active. Inquire regarding multi-source reconciliation parity, monetary exposure, fee deductions, or exception root causes.",
      answer: "VERIDEX Financial Copilot active. Inquire regarding multi-source reconciliation parity, monetary exposure, fee deductions, or exception root causes.",
    },
  ]);

  const queryMutation = useMutation({
    mutationFn: (q: string) => controllerApi.queryCopilot({ question: q }),
    onSuccess: (data) => {
      const parsedMsg = parseAssistantResponse(data);
      setMessages((prev) => [...prev, parsedMsg]);
    },
    onError: (err: Error) => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `Query could not complete: ${err.message}`,
          answer: `Query could not complete: ${err.message}`,
        },
      ]);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || queryMutation.isPending) return;

    const userText = question.trim();
    setMessages((prev) => [...prev, { role: "user", text: userText }]);
    setQuestion("");
    queryMutation.mutate(userText);
  };

  const sampleQuestions = [
    "What is the current reconciliation rate?",
    "How many exceptions are open?",
    "Where is the highest monetary exposure?",
    "Are there any tax line discrepancies on settlements?",
  ];

  if (!isOpen) return null;

  return (
    <aside
      className="fixed inset-y-0 right-0 z-50 w-96 shadow-2xl flex flex-col text-[#eceae6] select-none"
      style={{
        borderLeft: "1px solid var(--border-subtle)",
        background: "var(--surface-1)",
      }}
    >
      {/* Header */}
      <div
        className="h-14 px-4 flex items-center justify-between"
        style={{ borderBottom: "1px solid var(--border-subtle)" }}
      >
        <div className="flex items-center gap-2.5">
          <div
            className="p-1.5 rounded-xs border text-[#c9a96e]"
            style={{
              borderColor: "var(--accent-border)",
              background: "var(--accent-dim)",
            }}
          >
            <Brain className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-xs font-bold text-[#eceae6]">Controller Copilot</h2>
            <p className="text-[10px] text-[#8e96a0]">Authoritative Financial Grounding</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded text-[#8e96a0] hover:text-[#eceae6] transition-micro"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Messages Feed */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs scrollbar-none">
        {messages.map((m, idx) => (
          <CopilotMessageItem key={idx} message={m} />
        ))}

        {queryMutation.isPending && (
          <div
            className="flex items-center gap-2 p-3 rounded-xs border text-xs"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-2)",
              color: "var(--text-secondary)",
            }}
          >
            <Loader2 className="h-3.5 w-3.5 animate-spin text-[#c9a96e]" />
            <span>Analyzing authoritative financial records...</span>
          </div>
        )}
      </div>

      {/* Suggested Inquiries */}
      <div
        className="px-4 py-3 space-y-1.5"
        style={{
          borderTop: "1px solid var(--border-subtle)",
          background: "var(--surface-2)",
        }}
      >
        <div className="text-[9px] uppercase font-semibold text-[#8e96a0] tracking-wider">
          Grounded Financial Queries
        </div>
        <div className="flex flex-wrap gap-1">
          {sampleQuestions.map((sq, i) => (
            <button
              key={i}
              onClick={() => setQuestion(sq)}
              className="text-[10px] px-2 py-1 rounded-xs border truncate max-w-full text-left transition-micro text-[#8e96a0] hover:text-[#eceae6]"
              style={{
                borderColor: "var(--border-subtle)",
                background: "var(--surface-1)",
              }}
            >
              {sq}
            </button>
          ))}
        </div>
      </div>

      {/* Query Input */}
      <form
        onSubmit={handleSubmit}
        className="p-3 flex gap-2"
        style={{
          borderTop: "1px solid var(--border-subtle)",
          background: "var(--surface-1)",
        }}
      >
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Query verified reconciliation state..."
          className="flex-1 rounded-xs border px-3 py-1.5 text-xs text-[#eceae6] placeholder-[#545e6a] focus:outline-hidden transition-micro"
          style={{
            borderColor: "var(--border-standard)",
            background: "var(--surface-2)",
          }}
        />
        <button
          type="submit"
          disabled={!question.trim() || queryMutation.isPending}
          className="px-3 py-1.5 rounded-xs text-xs font-semibold flex items-center gap-1 transition-micro disabled:opacity-50"
          style={{
            color: "#080a0c",
            background: "var(--accent)",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-hover)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "var(--accent)")}
        >
          <Send className="h-3 w-3" />
        </button>
      </form>
    </aside>
  );
}

function CopilotMessageItem({ message }: { message: StructuredCopilotMessage }) {
  const [showTechnical, setShowTechnical] = useState(false);
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div
        className="ml-6 p-3 rounded-xs border text-xs text-[#eceae6]"
        style={{
          borderColor: "var(--border-standard)",
          background: "var(--surface-3)",
        }}
      >
        <div className="text-[10px] text-[#8e96a0] uppercase font-semibold mb-1">
          Controller Operator
        </div>
        <div>{message.text}</div>
      </div>
    );
  }

  return (
    <div
      className="mr-2 p-3.5 rounded-xs border text-xs text-[#eceae6] space-y-3"
      style={{
        borderColor: "var(--border-subtle)",
        background: "var(--surface-2)",
      }}
    >
      <div className="flex items-center justify-between text-[10px] text-[#8e96a0] uppercase font-semibold">
        <span>VERIDEX Financial Assessment</span>
        {message.confidence !== undefined && message.confidence !== null && (
          <span className="text-[#6ecba0] font-mono font-bold">
            {(message.confidence * 100).toFixed(0)}% Confidence
          </span>
        )}
      </div>

      {/* ANSWER SECTION */}
      <div>
        <div className="text-[9px] uppercase font-bold text-[#c9a96e] tracking-wider mb-1">
          Answer
        </div>
        <p className="text-xs leading-relaxed text-[#eceae6] whitespace-pre-wrap">
          {message.answer || message.text}
        </p>
      </div>

      {/* FINANCIAL FACTS */}
      {message.facts && message.facts.length > 0 && (
        <div className="pt-2 border-t border-[#22272e]">
          <div className="text-[9px] uppercase font-bold text-[#8e96a0] tracking-wider mb-1.5 flex items-center gap-1">
            <Database className="h-3 w-3 text-[#c9a96e]" />
            Financial Facts
          </div>
          <div className="space-y-1">
            {message.facts.map((f, i) => (
              <div
                key={i}
                className="flex items-center justify-between text-[10.5px] font-mono p-1.5 rounded-xs bg-[#111418] border border-[#22272e]"
              >
                <span className="text-[#8e96a0] capitalize">{f.label}:</span>
                <span className="text-[#eceae6] font-semibold">{f.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* EVIDENCE SUMMARY */}
      {Boolean(message.evidenceItems && message.evidenceItems.length > 0) && (
        <div className="pt-2 border-t border-[#22272e]">
          <div className="text-[9px] uppercase font-bold text-[#8e96a0] tracking-wider mb-1.5">
            Evidence Provenance
          </div>
          <div className="space-y-1">
            {message.evidenceItems!.map((ev, i) => (
              <div
                key={i}
                className="flex items-center justify-between text-[10.5px] font-mono p-1 rounded-xs"
              >
                <span className="text-[#8e96a0] capitalize">{ev.label}:</span>
                <TechnicalReference id={ev.value} maxVisible={20} inline />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* INTERPRETATION */}
      {message.interpretation && (
        <div className="pt-2 border-t border-[#22272e]">
          <div className="text-[9px] uppercase font-bold text-[#8e96a0] tracking-wider mb-1">
            Interpretation
          </div>
          <p className="text-[11px] text-[#8e96a0] leading-snug">{message.interpretation}</p>
        </div>
      )}

      {/* RECOMMENDATION */}
      {message.recommendation && (
        <div
          className="p-2.5 rounded-xs border text-[11px]"
          style={{
            borderColor: "var(--accent-border)",
            background: "var(--accent-dim)",
            color: "var(--accent)",
          }}
        >
          <span className="font-bold mr-1.5">Policy Recommendation:</span>
          <span>{message.recommendation}</span>
        </div>
      )}

      {/* PROGRESSIVE DISCLOSURE: RAW TECHNICAL EVIDENCE */}
      {Boolean(message.rawJson) && (
        <div className="pt-2 border-t border-[#22272e]">
          <button
            onClick={() => setShowTechnical((v) => !v)}
            className="flex items-center gap-1 text-[9px] font-mono text-[#8e96a0] hover:text-[#c9a96e] transition-colors uppercase"
          >
            <FileCode className="h-2.5 w-2.5" />
            {showTechnical ? <ChevronUp className="h-2.5 w-2.5" /> : <ChevronDown className="h-2.5 w-2.5" />}
            {showTechnical ? "Hide Raw Response" : "Show Technical Details"}
          </button>
          {showTechnical && (
            <pre className="mt-2 p-2 rounded-xs border border-[#22272e] bg-[#0c0e12] text-[10px] font-mono text-[#8e96a0] overflow-x-auto max-h-40 leading-relaxed">
              {JSON.stringify(message.rawJson, null, 2)}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
