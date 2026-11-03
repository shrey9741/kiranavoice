"use client";

import { useEffect, useRef, useState } from "react";
import LedgerOrder, { type Proposal } from "@/components/LedgerOrder";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const BARS = 28;

const T = {
  bn: {
    title: "কিরানাভয়েস",
    tag: "বলুন, আমি খাতায় তুলে রাখি",
    speak: "বলুন",
    stop: "থামান",
    listening: "শুনছি…",
    working: "বুঝছি…",
    empty: "মাইকের বোতাম চেপে অর্ডার বলুন",
    heard: "আপনি বললেন",
    order: "অর্ডার",
    total: "মোট",
    confirmed: "নিশ্চিত",
    micBlocked: "মাইক চালু করা যায়নি। ব্রাউজারে মাইকের অনুমতি দিন।",
    failed: "বুঝতে পারিনি। আবার বলুন।",
    soon: "শীঘ্রই আসছে",
    confirmBtn: "নিশ্চিত করুন",
    cancelBtn: "বাতিল",
    nav: ["বলুন", "অর্ডার", "স্টক", "যাচাই"],
    other: "EN",
  },
  en: {
    title: "KiranaVoice",
    tag: "Say it, I'll write it in the khata",
    speak: "Speak",
    stop: "Stop",
    listening: "Listening…",
    working: "Understanding…",
    empty: "Press the mic and say an order",
    heard: "You said",
    order: "Order",
    total: "Total",
    confirmed: "Confirmed",
    micBlocked:
      "Couldn't start the mic. Allow microphone access in your browser.",
    failed: "Couldn't understand that. Please try again.",
    soon: "Coming soon",
    confirmBtn: "Confirm",
    cancelBtn: "Cancel",
    nav: ["Voice", "Orders", "Stock", "Accuracy"],
    other: "বাং",
  },
} as const;

type UiLang = keyof typeof T;
type Phase = "idle" | "recording" | "working";

type ApiLine = {
  name: string;
  qty: number | null;
  unit: string | null;
  amount: number | null;
};
type ApiOrder = {
  transcript: string;
  lines: ApiLine[];
  total: number;
  questions: string[];
  can_confirm: boolean;
  status: string;
  proposal_id: string | null;
  spoken: string;
  timings?: Record<string, number>;
};

const UNIT_BN: Record<string, string> = {
  kg: "কেজি",
  g: "গ্রাম",
  litre: "লিটার",
  ml: "মিলি",
  piece: "পিস",
  packet: "প্যাকেট",
  dozen: "ডজন",
};

function toProposal(o: ApiOrder): Proposal | null {
  if (!o.lines.length) return null;
  return {
    lines: o.lines.map((l) => ({
      name: l.name,
      qty:
        l.qty === null
          ? "—"
          : `${l.qty} ${l.unit ? (UNIT_BN[l.unit] ?? l.unit) : ""}`.trim(),
      amount: l.amount,
    })),
    total: o.total,
    status:
      o.status === "committed" || o.status === "already_committed"
        ? "confirmed"
        : "proposed",
    questions: o.questions,
  };
}

// Sample data shown only with ?demo or ?demo=confirmed so you can review the design.
const DEMO_TRANSCRIPT = "কালকে দু কিলো আটা আর এক লিটার তেল অর্ডার করে রাখো";
const DEMO: Proposal = {
  lines: [
    { name: "আটা", qty: "2 কেজি", amount: 90 },
    { name: "তেল", qty: "1 লিটার", amount: null },
  ],
  total: 90,
  status: "proposed",
  questions: ["সরষের না সানফ্লাওয়ার?"],
};

export default function Home() {
  const [ui, setUi] = useState<UiLang>("bn");
  const [speechLang, setSpeechLang] = useState("bn-IN");
  const [phase, setPhase] = useState<Phase>("idle");
  const [transcript, setTranscript] = useState("");
  const [latency, setLatency] = useState<number | null>(null);
  const [timings, setTimings] = useState<Record<string, number> | null>(null);
  const [error, setError] = useState("");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [proposalId, setProposalId] = useState<string | null>(null);
  const [canConfirm, setCanConfirm] = useState(false);
  const [acting, setActing] = useState(false);

  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const bars = useRef<(HTMLSpanElement | null)[]>([]);
  const raf = useRef(0);
  const audioCtx = useRef<AudioContext | null>(null);
  const streamPromise = useRef<Promise<MediaStream> | null>(null);
  const sessionId = useRef("");

  const t = T[ui];

  // Open the mic once and reuse it, so there is no hardware warm-up gap
  // between pressing the button and the first spoken words.
  function getStream() {
    if (!streamPromise.current) {
      const p = navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
        },
      });
      p.catch(() => {
        streamPromise.current = null;
      });
      streamPromise.current = p;
    }
    return streamPromise.current;
  }

  useEffect(() => {
    getStream().catch(() => {});
  }, []);

  useEffect(() => {
    const demo = new URLSearchParams(window.location.search).get("demo");
    if (demo !== null) {
      setTranscript(DEMO_TRANSCRIPT);
      setProposal({
        ...DEMO,
        status: demo === "confirmed" ? "confirmed" : "proposed",
      });
    }
  }, []);

  function stopMeter() {
    cancelAnimationFrame(raf.current);
    bars.current.forEach((el) => el && (el.style.transform = "scaleY(0.1)"));
    audioCtx.current?.close();
    audioCtx.current = null;
  }

  async function start() {
    setError("");
    try {
      const stream = await getStream();

      const ctx = new AudioContext();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 128;
      ctx.createMediaStreamSource(stream).connect(analyser);
      audioCtx.current = ctx;
      const buf = new Uint8Array(analyser.frequencyBinCount);
      const tick = () => {
        analyser.getByteFrequencyData(buf);
        bars.current.forEach((el, i) => {
          if (!el) return;
          const idx = Math.min(
            buf.length - 1,
            1 + Math.floor((i * buf.length * 0.6) / BARS),
          );
          el.style.transform = `scaleY(${0.1 + (buf[idx] / 255) * 0.9})`;
        });
        raf.current = requestAnimationFrame(tick);
      };
      tick();

      const rec = new MediaRecorder(stream);
      chunks.current = [];
      rec.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      // Show "recording" only once the recorder has really started.
      rec.onstart = () => {
        // A finished (stamped) order is cleared for the next customer;
        // a pending one stays visible while the shopkeeper answers a question.
        setProposal((p) => (p?.status === "confirmed" ? null : p));
        setPhase("recording");
      };
      rec.onstop = () => {
        stopMeter();
        // The stream stays open on purpose; do not stop its tracks here.
        send(new Blob(chunks.current, { type: rec.mimeType }));
      };
      recorder.current = rec;
      rec.start();
    } catch {
      setError(t.micBlocked);
    }
  }

  function stop() {
    recorder.current?.stop();
    setPhase("working");
  }

  async function speak(text: string) {
    if (!text) return;
    try {
      const form = new FormData();
      form.append("text", text);
      const res = await fetch(`${API}/api/speak`, { method: "POST", body: form });
      if (!res.ok) return;
      const url = URL.createObjectURL(await res.blob());
      const audio = new Audio(url);
      audio.onended = () => URL.revokeObjectURL(url);
      await audio.play();
    } catch {
      // Speaking is a bonus; the order is already visible on screen.
    }
  }

  function getSession() {
    if (!sessionId.current) sessionId.current = crypto.randomUUID();
    return sessionId.current;
  }

  function applyReply(o: ApiOrder) {
    if (o.transcript) setTranscript(o.transcript);
    setProposal(toProposal(o));
    const open = o.status === "pending" || o.status === "rejected";
    setProposalId(open ? o.proposal_id : null);
    setCanConfirm(open && o.can_confirm);
    if (o.timings) setTimings(o.timings);
    void speak(o.spoken);
  }

  async function send(blob: Blob) {
    const t0 = performance.now();
    try {
      const form = new FormData();
      form.append("audio", blob, "speech.webm");
      form.append("language_code", speechLang);
      form.append("session_id", getSession());
      const res = await fetch(`${API}/api/voice-order`, {
        method: "POST",
        body: form,
      });
      const data = await res.json();
      if (!res.ok)
        throw new Error(typeof data.detail === "string" ? data.detail : "");
      applyReply(data as ApiOrder);
      setLatency((performance.now() - t0) / 1000);
    } catch (e) {
      setError(
        `${t.failed}${e instanceof Error && e.message ? ` (${e.message})` : ""}`,
      );
    } finally {
      setPhase("idle");
    }
  }

  async function act(action: "confirm" | "cancel") {
    if (acting) return;
    setActing(true);
    setError("");
    try {
      const form = new FormData();
      form.append("session_id", getSession());
      if (action === "confirm" && proposalId) form.append("proposal_id", proposalId);
      const res = await fetch(`${API}/api/${action}`, { method: "POST", body: form });
      const data = await res.json();
      if (!res.ok)
        throw new Error(typeof data.detail === "string" ? data.detail : "");
      applyReply(data as ApiOrder);
    } catch (e) {
      setError(e instanceof Error && e.message ? e.message : t.failed);
    } finally {
      setActing(false);
    }
  }

  const label =
    phase === "recording" ? t.stop : phase === "working" ? t.working : t.speak;
  const status =
    phase === "recording" ? t.listening : phase === "working" ? t.working : "";

  return (
    <div className="mx-auto flex min-h-dvh max-w-2xl flex-col bg-[var(--paper)] shadow-sm">
      <header className="flex items-start justify-between gap-3 px-5 pb-3 pt-5">
        <div>
          <h1 className="font-hand text-3xl leading-tight">{t.title}</h1>
          <p className="text-sm text-[var(--ink-soft)]">{t.tag}</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={speechLang}
            onChange={(e) => setSpeechLang(e.target.value)}
            aria-label="Speech language"
            className="rounded-md border border-[var(--rule)] bg-white px-2 py-1.5 text-sm"
          >
            <option value="bn-IN">বাংলা / Benglish</option>
            <option value="hi-IN">हिन्दी / Hinglish</option>
            <option value="en-IN">English</option>
          </select>
          <button
            onClick={() => setUi(ui === "bn" ? "en" : "bn")}
            aria-label="Switch interface language"
            className="rounded-md border border-[var(--rule)] bg-white px-2.5 py-1.5 text-sm"
          >
            {t.other}
          </button>
        </div>
      </header>

      <nav
        aria-label="Sections"
        className="flex gap-1 border-b border-[var(--rule)] px-4"
      >
        {t.nav.map((name, i) => (
          <span
            key={name}
            aria-current={i === 0 ? "page" : undefined}
            aria-disabled={i !== 0}
            title={i !== 0 ? t.soon : undefined}
            className={`px-3 py-2 text-sm ${
              i === 0
                ? "border-b-2 border-[var(--ink)] font-semibold"
                : "text-[var(--ink-soft)] opacity-60"
            }`}
          >
            {name}
          </span>
        ))}
      </nav>

      <main
        className="ledger font-hand flex-1 pb-6 pl-[4.25rem] pr-4 pt-[40px]"
        aria-live="polite"
      >
        {transcript ? (
          <>
            <div className="row font-[family-name:var(--font-ui)] text-sm text-[var(--ink-soft)]">
              {t.heard}
              {latency !== null && ` · ${latency.toFixed(1)}s`}
              {timings &&
                ` (STT ${timings.stt.toFixed(1)} · LLM ${timings.llm.toFixed(1)})`}
            </div>
            <p className="text-2xl" style={{ lineHeight: "40px" }}>
              {transcript}
            </p>
          </>
        ) : (
          <p
            className="text-xl italic text-[var(--ink-soft)]"
            style={{ lineHeight: "40px" }}
          >
            {t.empty}
          </p>
        )}

        {proposal && (
          <LedgerOrder
            p={proposal}
            labels={{ order: t.order, total: t.total, confirmed: t.confirmed }}
          />
        )}

        {error && (
          <p
            role="alert"
            className="mt-[40px] text-lg text-[var(--danger)]"
            style={{ lineHeight: "40px" }}
          >
            {error}
          </p>
        )}
      </main>

      <footer className="sticky bottom-0 flex flex-col items-center gap-2 border-t border-[var(--rule)] bg-[var(--paper)] px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3">
        {proposal && proposal.status === "proposed" && proposalId && (
          <div className="flex w-full max-w-md gap-3">
            <button
              onClick={() => act("cancel")}
              disabled={acting || phase !== "idle"}
              className="flex-1 rounded-md border border-[var(--ink)] px-4 py-3 text-lg disabled:opacity-50"
            >
              {t.cancelBtn}
            </button>
            <button
              onClick={() => act("confirm")}
              disabled={!canConfirm || acting || phase !== "idle"}
              className="flex-1 rounded-md bg-[var(--ink)] px-4 py-3 text-lg text-[var(--paper)] disabled:opacity-40"
            >
              {t.confirmBtn}
            </button>
          </div>
        )}
        <div className="flex h-10 items-center gap-[3px]" aria-hidden="true">
          {Array.from({ length: BARS }).map((_, i) => (
            <span
              key={i}
              ref={(el) => {
                bars.current[i] = el;
              }}
              className="h-full w-[3px] rounded-full bg-[var(--ink)]"
              style={{
                transform: "scaleY(0.1)",
                opacity: phase === "recording" ? 1 : 0.25,
              }}
            />
          ))}
        </div>

        <button
          onClick={phase === "recording" ? stop : start}
          disabled={phase === "working"}
          aria-label={label}
          className={`flex h-24 w-24 items-center justify-center rounded-full text-[var(--ink)] disabled:opacity-50 ${
            phase === "recording"
              ? "mic-live bg-[var(--ink)] text-[var(--turmeric)]"
              : "bg-[var(--turmeric)]"
          }`}
        >
          {phase === "recording" ? (
            <svg
              width="30"
              height="30"
              viewBox="0 0 24 24"
              fill="currentColor"
              aria-hidden="true"
            >
              <rect x="5" y="5" width="14" height="14" rx="2" />
            </svg>
          ) : (
            <svg
              width="34"
              height="34"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              aria-hidden="true"
            >
              <rect
                x="9"
                y="3"
                width="6"
                height="11"
                rx="3"
                fill="currentColor"
              />
              <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
            </svg>
          )}
        </button>

        <p className="h-5 text-sm text-[var(--ink-soft)]">{status || label}</p>
      </footer>
    </div>
  );
}
