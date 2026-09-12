import { BellRing } from "lucide-react";

import type { Alert } from "../types";
import { formatTime } from "../components/format";
import { EmptyState } from "../components/ui";
import { PageTitle } from "./Products";

export function AlertsPage({ alerts }: { alerts: Alert[] }) {
  return <section><PageTitle title="Alerts" detail="Only favorable state transitions produce deduplicated events; delivery failures never roll back stock truth." />{alerts.length === 0 ? <EmptyState title="No alerts yet—and that can be healthy" detail="Alerts appear after a watched product moves from unavailable or unknown into pre-order or in-stock. The first observation is only a baseline." /> : <div className="alert-list">{alerts.map((alert) => <article className="alert-row" key={alert.id}><span className="alert-row__icon"><BellRing size={18} /></span><div><h3>{alert.product_name}</h3><p>{alert.event_type.replaceAll("_", " ")} · {formatTime(alert.created_at)}</p></div><span className={`delivery delivery--${alert.delivery_status.toLowerCase()}`}>{alert.delivery_status}</span>{alert.error && <p className="alert-row__error">{alert.error}</p>}</article>)}</div>}</section>;
}
