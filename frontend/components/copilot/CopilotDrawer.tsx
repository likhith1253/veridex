"use client";

import React, { useState } from "react";
import { X, Send, Brain, Loader2, Database, ShieldCheck, CheckCircle2 } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import type { CopilotQueryResponse } from "@/types/controller";

interface CopilotDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export function CopilotDrawer({ isOpen, onClose }: CopilotDrawerProps) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<
    Array<{
      role: "user" | "assistant";
      text: string;
      data?: CopilotQueryResponse;
    }>
  >([
    {
      role: "assistant",
      text: "VERIDEX Financial Copilot active. Inquire regarding multi-source reconciliation parity, monetary exposure, fee deductions, or exception root causes.",
    },
  ]);

  const queryMutation = useMutation({
    mutationFn: (q: string) => controllerApi.queryCopilot({ question: q }),
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: data.direct_answer || data.answer || data.interpretation || "Query completed.",
          data: data,
        },
      ]);
    },
    onError: (err: Error) => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `Query error: ${err.message}`,
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
    "What is the total unreconciled financial exposure?",
    "What is the overall reconciliation match rate?",
    "Explain the top exception root cause.",
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
            <h2 className="text-xs font-bold text-[#eceae6]">
              Controller Copilot
            </h2>
            <p className="text-[10px] text-[#8e96a0]">
              Authoritative Financial Analyst Layer
            </p>
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
          <div
            key={idx}
            className={`p-3.5 rounded-xs border ${
              m.role === "user"
                ? "ml-6 text-[#eceae6]"
                : "mr-2 text-[#eceae6]"
            }`}
            style={{
              borderColor: m.role === "user" ? "var(--border-standard)" : "var(--border-subtle)",
              background: m.role === "user" ? "var(--surface-3)" : "var(--surface-2)",
            }}
          >
            <div className="flex items-center justify-between gap-2 mb-2 text-[10px] text-[#8e96a0] uppercase font-semibold">
              <span>{m.role === "user" ? "Controller Operator" : "VERIDEX Assessment"}</span>
              {m.data?.confidence !== undefined && m.data.confidence !== null && (
                <span className="text-[#6ecba0] font-mono font-bold">
                  {(m.data.confidence * 100).toFixed(0)}% Confidence
                </span>
              )}
            </div>

            {/* Answer Section */}
            <div className="leading-relaxed whitespace-pre-wrap text-xs text-[#eceae6]">
              {m.text}
            </div>

            {/* Structured Findings (ANSWER -> FINANCIAL FACTS -> EVIDENCE -> INTERPRETATION -> RECOMMENDATION) */}
            {m.data && (
              <div className="mt-3 pt-2.5 space-y-2 border-t text-[11px]" style={{ borderColor: "var(--border-subtle)" }}>
                {/* Interpretation */}
                {m.data.interpretation && m.data.interpretation !== m.text && (
                  <div>
                    <span className="text-[9px] uppercase font-semibold text-[#8e96a0] block tracking-wider">Interpretation:</span>
                    <p className="text-[#8e96a0] text-xs mt-0.5 leading-snug">{m.data.interpretation}</p>
                  </div>
                )}

                {/* Grounded Financial Facts (Source: Authoritative records, NOT vendor names) */}
                {m.data.sql_facts_used && m.data.sql_facts_used.length > 0 && (
                  <div className="pt-1.5 space-y-1">
                    <div className="flex items-center gap-1 text-[9px] text-[#c9a96e] uppercase font-semibold tracking-wider">
                      <Database className="h-3 w-3" /> Authoritative Financial Facts:
                    </div>
                    {m.data.sql_facts_used.map((fact, fIdx) => (
                      <div
                        key={fIdx}
                        className="text-[#eceae6] p-1.5 rounded-xs border text-[10px] font-mono"
                        style={{
                          borderColor: "var(--border-standard)",
                          background: "var(--surface-3)",
                        }}
                      >
                        {fact}
                      </div>
                    ))}
                  </div>
                )}

                {/* Policy Recommendation */}
                {m.data.recommendation && (
                  <div
                    className="p-2 rounded-xs border text-[11px] mt-2"
                    style={{
                      borderColor: "var(--accent-border)",
                      background: "var(--accent-dim)",
                      color: "var(--accent)",
                    }}
                  >
                    <span className="font-bold mr-1.5">▶ Policy Recommendation:</span>
                    <span>{m.data.recommendation}</span>
                  </div>
                )}
              </div>
            )}
          </div>
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
          Standard Financial Inquiries
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
          placeholder="Query authoritative financial state..."
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
