import { Clock3, Search, X } from "lucide-react";
import { useState } from "react";

import { loadHistory, searchProducts } from "../api/client";
import type { Product, ProductPage, Snapshot } from "../types";
import { formatPrice, formatTime } from "../components/format";
import { EmptyState, SourceLink, StatusBadge } from "../components/ui";

export function ProductsPage({ initial }: { initial: ProductPage }) {
  const [products, setProducts] = useState(initial);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [retailer, setRetailer] = useState("");
  const [minPrice, setMinPrice] = useState("");
  const [maxPrice, setMaxPrice] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<{ product: Product; rows: Snapshot[] } | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault(); setError(null);
    if (minPrice && maxPrice && Number(minPrice) > Number(maxPrice)) {
      setError("Minimum price must not exceed maximum price."); return;
    }
    setBusy(true);
    try { setProducts(await searchProducts({ query, status, category, retailer, minPrice, maxPrice })); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Search failed."); }
    finally { setBusy(false); }
  }

  async function showHistory(product: Product) {
    setBusy(true); setError(null);
    try { setHistory({ product, rows: await loadHistory(product.id) }); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "History could not be loaded."); }
    finally { setBusy(false); }
  }

  return <section>
    <PageTitle title="Product intelligence" detail="Search the latest normalized state and open the immutable observation trail." />
    <form className="filter-bar" onSubmit={submit}><label className="search-field"><Search size={17} /><span className="sr-only">Search products</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search Pixhawk, Raspberry Pi…" maxLength={200} /></label><label><span className="sr-only">Availability</span><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All states</option><option value="IN_STOCK">In stock</option><option value="OUT_OF_STOCK">Out of stock</option><option value="PREORDER">Pre-order</option><option value="UNKNOWN">Unknown</option></select></label><label><span className="sr-only">Category</span><select value={category} onChange={(event) => setCategory(event.target.value)}><option value="">All relevant categories</option><option>Flight Controllers</option><option>Companion Computers</option><option>HATs &amp; Carrier Boards</option><option>Other</option></select></label><label><span className="sr-only">Retailer</span><select value={retailer} onChange={(event) => setRetailer(event.target.value)}><option value="">All retailers</option><option>Robu</option><option>ThinkRobotics</option><option>Zbotic</option><option>Evelta</option></select></label><label><span className="sr-only">Minimum price</span><input type="number" min="0" step="0.01" value={minPrice} onChange={(event) => setMinPrice(event.target.value)} placeholder="Min ₹" /></label><label><span className="sr-only">Maximum price</span><input type="number" min="0" step="0.01" value={maxPrice} onChange={(event) => setMaxPrice(event.target.value)} placeholder="Max ₹" /></label><button className="button button--primary" disabled={busy}>{busy ? "Searching…" : "Apply filters"}</button></form>
    {error && <p className="inline-error" role="alert">{error} Try again shortly.</p>}
    {products.suggestion && <button className="suggestion" onClick={() => setQuery(products.suggestion ?? "")}>Did you mean <strong>{products.suggestion}</strong>?</button>}
    {products.items.length === 0 ? <EmptyState title={`No exact result${query ? ` for “${query}”` : ""}`} detail="Try a broader name, remove a filter, or add a supported retailer URL to the watchlist." /> : <div className="catalog-grid">{products.items.map((product) => <ProductCard key={product.id} product={product} history={() => void showHistory(product)} />)}</div>}
    {history && <HistoryDrawer data={history} close={() => setHistory(null)} />}
  </section>;
}

function ProductCard({ product, history }: { product: Product; history: () => void }) {
  return <article className="product-card"><div className="product-card__top"><span>{product.retailer}</span><StatusBadge status={product.status} /></div><h3>{product.name}</h3><p>{product.manufacturer || "Manufacturer unavailable"} · {product.category}</p><strong className="price">{formatPrice(product.price, product.currency)}</strong><div className="product-card__meta"><span><Clock3 size={14} />{product.status === "UNKNOWN" ? "Last attempt" : "Last checked"}: {formatTime(product.last_checked_at)}</span>{product.latest_check_error && <p className="check-reason">{product.latest_check_error}</p>}</div><div className="product-card__actions"><button className="button button--secondary" onClick={history}>View history</button><SourceLink href={product.canonical_url} /></div></article>;
}

function HistoryDrawer({ data, close }: { data: { product: Product; rows: Snapshot[] }; close: () => void }) {
  return <div className="drawer-backdrop" role="presentation" onMouseDown={(event) => { if (event.currentTarget === event.target) close(); }}><aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="history-title"><button className="icon-button drawer__close" onClick={close} aria-label="Close history"><X /></button><h2 id="history-title">{data.product.name}</h2><p>Immutable product snapshots</p>{data.rows.length === 0 ? <EmptyState title="No observations yet" detail="Run the monitor to establish the first baseline. The first observation never creates a false restock alert." /> : <ol className="timeline">{data.rows.map((row) => <li key={row.id}><i /><div><StatusBadge status={row.status} /><strong>{formatPrice(row.price, row.currency)}</strong><p>{formatTime(row.checked_at)} · {row.classification_source}{row.classification_provider ? ` / ${row.classification_provider}` : ""}</p>{row.error && <span>{row.error}</span>}</div></li>)}</ol>}</aside></div>;
}

export function PageTitle({ title, detail }: { title: string; detail: string }) { return <header className="page-title"><h1>{title}</h1><p>{detail}</p></header>; }
