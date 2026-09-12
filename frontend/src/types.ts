export type ProductStatus = "IN_STOCK" | "OUT_OF_STOCK" | "PREORDER" | "UNKNOWN";

export interface LastRun {
  id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  products_checked: number;
  errors_count: number;
}

export interface Summary {
  watched_products: number;
  in_stock: number;
  preorders: number;
  unknown_or_problems: number;
  last_run: LastRun | null;
}

export interface Product {
  id: string;
  name: string;
  retailer: string;
  retailer_domain?: string;
  canonical_url: string;
  manufacturer: string | null;
  category: string;
  status: ProductStatus;
  price: string | null;
  currency: string;
  attributes: Record<string, unknown>;
  last_checked_at: string | null;
}

export interface ProductPage {
  items: Product[];
  total: number;
  limit: number;
  offset: number;
  suggestion: string | null;
}

export interface Watch {
  id: string;
  product_id: string;
  product_name: string;
  retailer: string;
  status: ProductStatus;
  price: string | null;
  canonical_url: string;
  enabled: boolean;
  created_at: string;
}

export interface MonitorRun extends LastRun {
  trigger: string;
  products_changed: number;
  alerts_created: number;
  error_summary: string | null;
}

export interface Alert {
  id: string;
  product_id: string;
  product_name: string;
  event_type: string;
  delivery_status: string;
  created_at: string;
  delivered_at: string | null;
  error: string | null;
}

export interface Snapshot {
  id: string;
  status: ProductStatus;
  price: string | null;
  currency: string;
  classification_source: string;
  classification_provider: string | null;
  confidence: number | null;
  checked_at: string;
  error: string | null;
}

export interface ConsoleData {
  summary: Summary;
  products: ProductPage;
  watches: Watch[];
  runs: MonitorRun[];
  alerts: Alert[];
}
