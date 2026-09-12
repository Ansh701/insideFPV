import type { Alert, ConsoleData, MonitorRun, ProductPage, Snapshot, Summary, Watch } from "../types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message: string, public readonly status: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const body = (await response.json().catch(() => null)) as
    | { error?: { message?: string }; detail?: string }
    | null;
  if (!response.ok) {
    throw new ApiError(body?.error?.message || body?.detail || "The server could not complete this request.", response.status);
  }
  return body as T;
}

function listFrom<T>(value: T[] | { items: T[] }): T[] {
  return Array.isArray(value) ? value : value.items;
}

export async function loadConsole(): Promise<ConsoleData> {
  const [summary, products, watches, runs, alerts] = await Promise.all([
    request<Summary>("/api/dashboard/summary"),
    request<ProductPage>("/api/products?limit=50"),
    request<Watch[] | { items: Watch[] }>("/api/watchlist"),
    request<{ items: MonitorRun[] }>("/api/monitor/runs"),
    request<{ items: Alert[] }>("/api/alerts"),
  ]);
  return { summary, products, watches: listFrom(watches), runs: runs.items, alerts: alerts.items };
}

export async function addWatch(target: string): Promise<Watch> {
  const isUrl = /^https?:\/\//i.test(target.trim());
  return request<Watch>("/api/watchlist", {
    method: "POST",
    body: JSON.stringify({ telegram_user_id: 0, [isUrl ? "url" : "product_name"]: target.trim() }),
  });
}

export async function removeWatch(id: string): Promise<void> {
  await request(`/api/watchlist/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function runMonitor(adminSecret: string) {
  return request<{ products_checked: number; products_changed: number; alerts_created: number; errors_count: number }>(
    "/api/admin/monitor/run",
    { method: "POST", headers: { "X-Admin-Secret": adminSecret } },
  );
}

export async function loadHistory(productId: string): Promise<Snapshot[]> {
  const result = await request<{ items: Snapshot[] }>(`/api/products/${encodeURIComponent(productId)}/history`);
  return result.items;
}

export async function searchProducts(query: string, status: string, category: string): Promise<ProductPage> {
  const params = new URLSearchParams({ limit: "50" });
  if (query.trim()) params.set("query", query.trim());
  if (status) params.set("availability", status);
  if (category) params.set("category", category);
  return request<ProductPage>(`/api/products?${params}`);
}
