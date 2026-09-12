import { Activity, ArrowUpRight, Check, Eye, PackageCheck, RadioTower, TriangleAlert } from "lucide-react";

import type { ConsoleData } from "../types";
import { formatPrice, formatTime } from "../components/format";
import { HealthyState, SourceLink, StatusBadge } from "../components/ui";

export function DashboardPage({ data, goTo }: { data: ConsoleData; goTo: (page: string) => void }) {
  const metrics = [
    { label: "Watched products", value: data.summary.watched_products, icon: Eye, key: "watched" },
    { label: "Currently in stock", value: data.summary.in_stock, icon: PackageCheck, key: "in-stock" },
    { label: "Pre-orders", value: data.summary.preorders, icon: RadioTower, key: "preorders" },
    { label: "Unknown / problems", value: data.summary.unknown_or_problems, icon: TriangleAlert, key: "unknown" },
  ];
  const latest = data.summary.last_run;

  return <>
    <section className="hero glass-panel">
      <div className="hero__copy">
        <h1><span className="hero__lead">Parts intelligence,</span><br /><span>ready for takeoff.</span></h1>
        <p className="hero__lede">Monitor scarce flight hardware, preserve its history, and act when stock changes—without treating stale data as live truth.</p>
        <div className="hero__actions"><button className="button button--primary" onClick={() => goTo("monitoring")}>Run monitor <ArrowUpRight size={17} /></button><button className="button button--ghost" onClick={() => goTo("watchlist")}>Manage watchlist</button></div>
      </div>
      <div className="pulse-card">
        <div className="pulse-card__top"><span>System pulse</span><Activity size={18} aria-hidden="true" /></div>
        <strong>{latest?.status === "COMPLETED" ? "Operational" : latest ? latest.status : "Ready"}</strong>
        <div className="signal-lines" aria-hidden="true"><i /><i /><i /><i /><i /><i /><i /><i /></div>
        <dl><div><dt>Last sweep</dt><dd>{formatTime(latest?.finished_at ?? null)}</dd></div><div><dt>Products checked</dt><dd>{latest?.products_checked ?? 0}</dd></div></dl>
      </div>
    </section>

    <section aria-labelledby="inventory-heading">
      <div className="section-heading"><h2 id="inventory-heading">Inventory signal at a glance</h2></div>
      <div className="metric-grid">{metrics.map(({ label, value, icon: Icon, key }) => <article className="metric-card" key={key}><span className="metric-card__icon"><Icon size={19} /></span><p>{label}</p><strong data-metric={key}>{value}</strong></article>)}</div>
    </section>

    <section className="dashboard-grid">
      <article className="panel">
        <div className="panel__header"><h2>Latest product states</h2><button className="text-button" onClick={() => goTo("products")}>View all <ArrowUpRight size={15} /></button></div>
        <div className="product-stack">{data.products.items.slice(0, 4).map((product) => <div className="product-line" key={product.id}><div className="product-monogram" aria-hidden="true">{product.name.slice(0, 2).toUpperCase()}</div><div className="product-line__name"><strong>{product.name}</strong><span>{product.retailer} · {product.category}</span></div><div className="product-line__state"><StatusBadge status={product.status} /><span>{formatPrice(product.price, product.currency)}</span></div><SourceLink href={product.canonical_url} label="Open" /></div>)}</div>
      </article>
      <aside className="panel panel--compact">
        <h2>Monitoring health</h2>
        {(!latest || latest.errors_count === 0) ? <HealthyState /> : <div className="warning-state"><TriangleAlert size={18} /><div><strong>{latest.errors_count} checks need attention</strong><p>Open Monitoring for the latest run details.</p></div></div>}
        <div className="onboarding"><p>Getting started</p><ol><li className="done"><CheckIcon /> Application ready</li><li className={data.summary.watched_products ? "done" : ""}><CheckIcon /> Track your first product</li><li className={latest ? "done" : ""}><CheckIcon /> Run an availability check</li><li className={data.alerts.length ? "done" : ""}><CheckIcon /> Receive an alert</li></ol></div>
      </aside>
    </section>
  </>;
}

function CheckIcon() { return <span aria-hidden="true"><Check size={12} /></span>; }
