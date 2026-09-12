import "@fontsource-variable/manrope";
import "@fontsource-variable/space-grotesk";
import { Bell, Boxes, Command, Gauge, ListChecks, Moon, Radio, Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { ErrorState, LoadingState } from "./components/ui";
import { useConsoleData } from "./hooks/useConsoleData";
import { AlertsPage } from "./pages/Alerts";
import { DashboardPage } from "./pages/Dashboard";
import { MonitoringPage } from "./pages/Monitoring";
import { ProductsPage } from "./pages/Products";
import { WatchlistPage } from "./pages/Watchlist";
import "./styles.css";

type Page = "dashboard" | "products" | "watchlist" | "monitoring" | "alerts";
type Theme = "light" | "dark";

const nav = [
  { id: "dashboard" as const, label: "Dashboard", icon: Gauge },
  { id: "products" as const, label: "Products", icon: Boxes },
  { id: "watchlist" as const, label: "Watchlist", icon: ListChecks },
  { id: "monitoring" as const, label: "Monitoring", icon: Radio },
  { id: "alerts" as const, label: "Alerts", icon: Bell },
];

function initialTheme(): Theme { return localStorage.getItem("rotorwatch-theme") === "dark" ? "dark" : "light"; }

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const { data, error, loading, stage, refresh } = useConsoleData();

  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem("rotorwatch-theme", theme); }, [theme]);

  function content() {
    if (loading && !data) return stage === "quiet" ? <div className="quiet-loading" aria-live="polite"><span className="sr-only">Loading console</span></div> : <LoadingState skeleton={stage === "skeleton"} />;
    if (error && !data) return <ErrorState detail={error} retry={() => void refresh()} />;
    if (!data) return null;
    if (page === "products") return <ProductsPage initial={data.products} />;
    if (page === "watchlist") return <WatchlistPage watches={data.watches} refresh={refresh} />;
    if (page === "monitoring") return <MonitoringPage runs={data.runs} refresh={refresh} />;
    if (page === "alerts") return <AlertsPage alerts={data.alerts} />;
    return <DashboardPage data={data} goTo={(target) => setPage(target as Page)} />;
  }

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <header className="topbar"><button className="brand" onClick={() => setPage("dashboard")} aria-label="RotorWatch dashboard"><span className="brand__mark"><Command /></span><span><strong>RotorWatch</strong><small>Inventory command</small></span></button><div className="topbar__right"><span className="connection"><i /> Backend linked</span><button className="icon-button" onClick={() => setTheme(theme === "light" ? "dark" : "light")} aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}>{theme === "light" ? <Moon /> : <Sun />}</button></div></header>
    <nav className="nav-rail" aria-label="Primary navigation">{nav.map(({ id, label, icon: Icon }) => <button key={id} className={page === id ? "active" : ""} onClick={() => setPage(id)} aria-current={page === id ? "page" : undefined}><Icon /><span>{label}</span></button>)}</nav>
    <main id="main-content" tabIndex={-1}>{error && data && <p className="stale-banner" role="status">Fresh data could not be loaded. Showing the last successful response. <button onClick={() => void refresh()}>Retry</button></p>}{content()}</main>
    <footer><span>ROT / 01</span><p>Structured product truth for Indian drone builders.</p><span>{new Date().getFullYear()} · IST</span></footer>
  </div>;
}
