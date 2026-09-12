import { ExternalLink, Trash2 } from "lucide-react";
import { useState } from "react";

import { addWatch, removeWatch } from "../api/client";
import { formatPrice } from "../components/format";
import { EmptyState, StatusBadge } from "../components/ui";
import type { Watch } from "../types";
import { PageTitle } from "./Products";

export function WatchlistPage({ watches, refresh }: { watches: Watch[]; refresh: () => Promise<void> }) {
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const valid = target.trim().length >= 2 && target.length <= 2048;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!valid) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await addWatch(target);
      setTarget("");
      setMessage("Product added to your watchlist.");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The watch could not be added.");
    } finally {
      setBusy(false);
    }
  }

  async function remove(item: Watch) {
    setBusy(true);
    setError(null);
    try {
      await removeWatch(item.id);
      setMessage("Watch removed.");
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The watch could not be removed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <PageTitle title="Watchlist" detail="Add any known product or a product URL from Robu, ThinkRobotics, Zbotic, or Evelta." />
      <form className="watch-form panel" onSubmit={submit} noValidate>
        <div>
          <label htmlFor="watch-target">Product name or supported URL <span aria-hidden="true">Required</span></label>
          <input id="watch-target" aria-label="Product name or supported URL" value={target} onChange={(event) => { setTarget(event.target.value); setError(null); }} maxLength={2048} placeholder="Raspberry Pi 5 or https://…" aria-describedby="watch-help watch-count" />
          <div className="field-notes"><span id="watch-help">Tracking persists without a code change or redeploy.</span><span id="watch-count">{target.length} / 2048</span></div>
        </div>
        <button className="button button--primary" disabled={!valid || busy}>{busy ? "Saving…" : "Add watch"}</button>
      </form>
      <div className="notice-stack" aria-live="polite">{message && <p className="success-message">{message}</p>}{error && <p className="inline-error">{error} Your existing watches are unchanged.</p>}</div>
      {watches.length === 0 ? (
        <EmptyState title="No products are being watched yet" detail="Track a product and RotorWatch will notify the connected Telegram user when availability improves." />
      ) : (
        <div className="watch-grid">{watches.map((watch) => <article className="watch-card" key={watch.id}><div><p>{watch.retailer}</p><h3>{watch.product_name}</h3></div><StatusBadge status={watch.status} /><strong>{formatPrice(watch.price)}</strong><div className="watch-card__actions"><a className="icon-button" href={watch.canonical_url} target="_blank" rel="noreferrer" aria-label={`Open ${watch.product_name} source`}><ExternalLink /></a><button className="icon-button icon-button--danger" onClick={() => void remove(watch)} disabled={busy} aria-label={`Remove ${watch.product_name} watch`}><Trash2 /></button></div></article>)}</div>
      )}
    </section>
  );
}
