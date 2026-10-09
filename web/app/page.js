"use client";

import { useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

const SAMPLES = [
  "What was total revenue in 2025-Q3?",
  "Why did European margins drop last quarter?",
  "Show margin by region for Europe last quarter",
];

export default function Home() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function ask(e) {
    e.preventDefault();
    const question = input.trim();
    if (!question || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", content: question }]);
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      if (!res.ok) throw new Error(`API responded ${res.status}`);
      const data = await res.json();
      setMessages((m) => [
        ...m,
        { role: "assistant", content: data.answer || "(no answer)", trace: data.trace || [] },
      ]);
    } catch (err) {
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          error: true,
          content: `Could not reach the agent at ${API_URL}. Make sure the semantic layer (:4000) and agent API (:8001) are running. [${err.message}]`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="wrap">
      <header className="top">
        <div className="brand">
          <span className="dot" />
          MetricMind
        </div>
        <div className="sub">Agentic Semantic BI · the LLM never writes SQL</div>
      </header>

      <section className="chat">
        {messages.length === 0 && (
          <div className="empty">
            <p className="empty-title">Ask a governed business question.</p>
            <div className="samples">
              {SAMPLES.map((s) => (
                <button key={s} type="button" className="sample" onClick={() => setInput(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <Message key={i} m={m} />
        ))}

        {loading && (
          <div className="msg assistant">
            <div className="bubble typing">Querying the semantic layer…</div>
          </div>
        )}
      </section>

      <form className="composer" onSubmit={ask}>
        <input
          className="field"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about revenue, margin, costs…"
          aria-label="Ask a question"
        />
        <button className="send" type="submit" disabled={loading || !input.trim()}>
          Ask
        </button>
      </form>
    </main>
  );
}

function Message({ m }) {
  const [open, setOpen] = useState(false);
  const hasTrace = Array.isArray(m.trace) && m.trace.length > 0;
  return (
    <div className={`msg ${m.role}`}>
      <div className={`bubble ${m.error ? "error" : ""}`}>
        <div className="content">{m.content}</div>
        {hasTrace && (
          <div className="trace">
            <button type="button" className="toggle" onClick={() => setOpen((o) => !o)}>
              {open ? "Hide" : "View"} API call ({m.trace.length})
            </button>
            {open && (
              <div className="trace-body">
                {m.trace.map((t, i) => (
                  <div key={i} className="trace-item">
                    <div className="trace-tool">{t.tool}</div>
                    <pre>{JSON.stringify(t.query, null, 2)}</pre>
                    <pre className="trace-result">
                      {JSON.stringify(t.result?.data ?? t.result, null, 2)}
                    </pre>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
