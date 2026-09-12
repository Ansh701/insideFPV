import { AlertTriangle, Check, ExternalLink, LoaderCircle, PackageSearch, RotateCcw } from "lucide-react";
import type { ReactNode } from "react";

import type { ProductStatus } from "../types";

export function StatusBadge({ status }: { status: ProductStatus }) {
  const labels: Record<ProductStatus, string> = {
    IN_STOCK: "In stock",
    OUT_OF_STOCK: "Out of stock",
    PREORDER: "Pre-order",
    UNKNOWN: "Unknown",
  };
  return <span className={`status status--${status.toLowerCase()}`}>{labels[status]}</span>;
}

export function EmptyState({ title, detail, action }: { title: string; detail: string; action?: ReactNode }) {
  return <div className="empty-state"><span className="empty-state__icon" aria-hidden="true"><PackageSearch size={22} /></span><h3>{title}</h3><p>{detail}</p>{action}</div>;
}

export function LoadingState({ skeleton }: { skeleton: boolean }) {
  if (skeleton) return <div className="skeleton-grid" role="status" aria-label="Loading dashboard data">{[0, 1, 2, 3].map((item) => <span className="skeleton" key={item} />)}</div>;
  return <div className="loading-inline" role="status"><LoaderCircle size={18} className="spin" aria-hidden="true" /> Connecting to inventory data…</div>;
}

export function ErrorState({ detail, retry }: { detail: string; retry: () => void }) {
  return <section className="error-state" role="alert"><AlertTriangle aria-hidden="true" /><div><h2>We couldn’t load the console</h2><p>{detail} Check that the FastAPI service and database are running, then retry.</p></div><button className="button button--secondary" onClick={retry}><RotateCcw size={16} /> Try again</button></section>;
}

export function HealthyState({ detail = "No failed product checks in the latest run." }: { detail?: string }) {
  return <div className="healthy-state"><span aria-hidden="true"><Check size={16} /></span><div><strong>Everything looks healthy</strong><p>{detail}</p></div></div>;
}

export function SourceLink({ href, label = "View source" }: { href: string; label?: string }) {
  return <a className="source-link" href={href} target="_blank" rel="noreferrer">{label}<ExternalLink size={14} aria-hidden="true" /></a>;
}
