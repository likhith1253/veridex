"use client";

import React, { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * The backend runs on Render's free tier, which spins down after
 * inactivity — the first request after a while can take 30-60s+ to wake up.
 * Without this, an evaluator opening the live link mid-cold-start would see
 * a blank or broken app for that whole window and likely bounce before it
 * ever loads. This gates rendering behind a real health check against the
 * actual backend (through the same proxy every page uses), shows an honest
 * reason for the wait, and only reveals the app once it's genuinely ready.
 */

const POLL_INTERVAL_MS = 2500;
const SLOW_THRESHOLD_MS = 12000;
const LONG_THRESHOLD_MS = 30000;
const MAX_WAIT_MS = 90000;

export function BackendWakeGate({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<"checking" | "ready" | "timedOut">("checking");
  const [elapsedMs, setElapsedMs] = useState(0);
  const startRef = useRef(Date.now());
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;
    startRef.current = Date.now();

    const tick = setInterval(() => {
      setElapsedMs(Date.now() - startRef.current);
    }, 250);

    async function poll() {
      while (!cancelledRef.current) {
        const elapsed = Date.now() - startRef.current;
        if (elapsed > MAX_WAIT_MS) {
          setStatus("timedOut");
          return;
        }
        try {
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), POLL_INTERVAL_MS - 200);
          const res = await fetch("/api/proxy/health", {
            signal: controller.signal,
            cache: "no-store",
          });
          clearTimeout(timeoutId);
          if (res.ok) {
            if (!cancelledRef.current) setStatus("ready");
            return;
          }
        } catch {
          // Backend still waking up — keep polling.
        }
        await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
      }
    }

    poll();
    return () => {
      cancelledRef.current = true;
      clearInterval(tick);
    };
  }, []);

  if (status === "ready") return <>{children}</>;

  const isSlow = elapsedMs > SLOW_THRESHOLD_MS;
  const isLong = elapsedMs > LONG_THRESHOLD_MS;
  const seconds = Math.floor(elapsedMs / 1000);

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center"
      style={{ background: "#0d0f12" }}
    >
      <div className="flex flex-col items-center gap-6 px-6 text-center max-w-md">
        {/* Spinner */}
        <div className="relative h-16 w-16">
          <div
            className="absolute inset-0 rounded-full border-4"
            style={{ borderColor: "#22272e" }}
          />
          <div
            className="absolute inset-0 rounded-full border-4 border-transparent animate-spin"
            style={{
              borderTopColor: "#c9a96e",
              borderRightColor: "#c9a96e",
              animationDuration: "0.9s",
            }}
          />
        </div>

        <div>
          <div className="flex items-center justify-center gap-2 mb-1">
            <span className="text-[10px] font-bold uppercase tracking-[0.14em]" style={{ color: "#c9a96e" }}>
              VERIDEX
            </span>
          </div>
          <h1 className="text-base font-bold text-white">
            {status === "timedOut" ? "Still waking up the backend…" : "Waking up the backend…"}
          </h1>
        </div>

        <p className="text-sm leading-relaxed" style={{ color: "#9aa5b2" }}>
          {!isSlow && (
            <>This app runs on a free hosting tier that goes to sleep when idle. It's starting up now — this usually takes under a minute.</>
          )}
          {isSlow && !isLong && (
            <>Still starting up — free-tier servers take a little longer to wake from a cold start. Thanks for your patience, it's almost there.</>
          )}
          {isLong && status !== "timedOut" && (
            <>This is taking longer than usual. The server is still coming online — hang tight a little longer.</>
          )}
          {status === "timedOut" && (
            <>The backend is taking unusually long to respond. It may still be starting up — you can keep waiting or try reloading.</>
          )}
        </p>

        <span className="font-mono text-[11px] tabular-nums" style={{ color: "#545e6a" }}>
          {seconds}s elapsed
        </span>

        {status === "timedOut" && (
          <button
            onClick={() => {
              startRef.current = Date.now();
              setElapsedMs(0);
              setStatus("checking");
            }}
            className="px-4 py-2 rounded-xs text-xs font-bold transition-micro"
            style={{ color: "#080a0c", background: "#c9a96e" }}
          >
            Retry now
          </button>
        )}
      </div>
    </div>
  );
}
