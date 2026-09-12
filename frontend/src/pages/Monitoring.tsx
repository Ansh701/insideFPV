import { Activity, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { runMonitor } from "../api/client";
import type { MonitorRun } from "../types";
import { formatTime } from "../components/format";
import { EmptyState, HealthyState } from "../components/ui";
import { PageTitle } from "./Products";

const stages = ["Starting monitor…", "Checking retailers…", "Analyzing changed products…", "Saving snapshots…", "Sending alerts…"];

export function MonitoringPage({ runs, refresh }: { runs: MonitorRun[]; refresh: () => Promise<void> }) {
  const [secret, setSecret] = useState(() => sessionStorage.getItem("rotorwatch-admin-secret") || "");
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  useEffect(() => () => { if (timer.current) window.clearInterval(timer.current); }, []);

  async function run() {
    if (!secret.trim()) return;
    sessionStorage.setItem("rotorwatch-admin-secret", secret); setBusy(true); setStage(0); setMessage(null); setError(null);
    timer.current = window.setInterval(() => setStage((current) => Math.min(current + 1, stages.length - 1)), 1300);
    try { const result = await runMonitor(secret); setMessage(`Monitoring completed: ${result.products_checked} checked, ${result.products_changed} changed, ${result.alerts_created} alerts created.`); await refresh(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Monitoring could not start."); }
    finally { if (timer.current) window.clearInterval(timer.current); timer.current = null; setBusy(false); }
  }

  return <section><PageTitle title="Monitoring runs" detail="The scheduled command, CLI, demo, and this control all reuse one monitoring service." />
    <div className="monitor-control glass-panel"><div><h2><ShieldCheck size={22} /> Run monitor now</h2><p>Checks supported retailers with bounded concurrency. One failed source will not stop the remaining products.</p></div><div className="monitor-control__action"><label htmlFor="admin-secret">Admin secret</label><input id="admin-secret" type="password" value={secret} onChange={(event) => setSecret(event.target.value)} autoComplete="off" /><button className="button button--primary" onClick={() => void run()} disabled={!secret.trim() || busy}>{busy ? stages[stage] : "Run monitor now"}{busy && <Activity className="pulse" size={17} />}</button></div></div>
    <div className="notice-stack" aria-live="polite">{message && <p className="success-message">{message}</p>}{error && <p className="inline-error">{error} Confirm the admin secret and backend status, then retry.</p>}</div>
    {runs.length === 0 ? <EmptyState title="No monitor runs yet" detail="Run the first check to establish baselines. Products already in stock will not generate fake restock alerts." /> : <div className="run-list"><div className="run-list__heading"><h2>Run history</h2>{runs[0].errors_count === 0 && <HealthyState detail="The latest run completed without product-check failures." />}</div>{runs.map((run) => <article className="run-row" key={run.id}><div className={`run-marker ${run.errors_count ? "run-marker--warn" : ""}`} /><div><strong>{run.trigger}</strong><span>{formatTime(run.started_at)}</span></div><dl><div><dt>Checked</dt><dd>{run.products_checked}</dd></div><div><dt>Changed</dt><dd>{run.products_changed}</dd></div><div><dt>Alerts</dt><dd>{run.alerts_created}</dd></div><div><dt>Errors</dt><dd>{run.errors_count}</dd></div></dl></article>)}</div>}
  </section>;
}
