import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";

import App from "./App";

const summary = {
  watched_products: 2,
  in_stock: 1,
  preorders: 0,
  unknown_or_problems: 1,
  last_run: null,
};

const products = {
  items: [
    {
      id: "p1",
      name: "Holybro Pixhawk 6X",
      retailer: "Zbotic",
      retailer_domain: "zbotic.in",
      canonical_url: "https://zbotic.in/product/pixhawk",
      manufacturer: "Holybro",
      category: "Flight Controllers",
      status: "IN_STOCK",
      price: "25198.95",
      currency: "INR",
      attributes: {},
      last_checked_at: "2026-09-11T10:00:00Z",
      latest_check_error: null,
    },
    {
      id: "p2",
      name: "Raspberry Pi Compute Module",
      retailer: "ThinkRobotics",
      retailer_domain: "thinkrobotics.com",
      canonical_url: "https://thinkrobotics.com/products/raspberry-pi-compute-module",
      manufacturer: "Raspberry Pi",
      category: "Companion Computers",
      status: "UNKNOWN",
      price: null,
      currency: "INR",
      attributes: {},
      last_checked_at: "2026-09-11T10:00:00Z",
      latest_check_error: "The retailer blocked the automated request (HTTP 403).",
    },
  ],
  total: 1,
  limit: 25,
  offset: 0,
  suggestion: null,
};

function response(data: unknown, ok = true): Promise<Response> {
  return Promise.resolve({ ok, status: ok ? 200 : 503, json: () => Promise.resolve(data) } as Response);
}

beforeEach(() => {
  window.history.replaceState({}, "", "/");
  localStorage.clear();
  sessionStorage.clear();
  vi.stubGlobal(
    "fetch",
    vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("dashboard/summary")) return response(summary);
      if (url.includes("/api/products")) return response(products);
      return response({ items: [] });
    }),
  );
});
test("renders authoritative summary and product data", async () => {
  render(<App />);
  expect(await screen.findByText("Holybro Pixhawk 6X")).toBeInTheDocument();
  expect(screen.getByText("1", { selector: "[data-metric='in-stock']" })).toBeInTheDocument();
  expect(screen.getByText("Everything looks healthy")).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledWith(
    "/api/dashboard/summary",
    expect.objectContaining({ headers: { "Content-Type": "application/json" } }),
  );
});

test("opens a directly entered frontend route and preserves it during navigation", async () => {
  const user = userEvent.setup();
  window.history.replaceState({}, "", "/products");

  render(<App />);

  expect(await screen.findByRole("heading", { name: "Product intelligence" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Watchlist" }));
  expect(window.location.pathname).toBe("/watchlist");
});

test("persists an intentional dark theme", async () => {
  const user = userEvent.setup();
  render(<App />);
  await user.click(screen.getByRole("button", { name: /switch to dark theme/i }));
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(localStorage.getItem("rotorwatch-theme")).toBe("dark");
});

test("shows a recoverable API error instead of an infinite loader", async () => {
  vi.mocked(fetch).mockImplementation(() => response({ error: { message: "Database unavailable" } }, false));
  render(<App />);
  expect(await screen.findByText("We couldn’t load the console")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
});

test("validates and submits a watch without losing useful input", async () => {
  const user = userEvent.setup();
  render(<App />);
  await screen.findByText("Holybro Pixhawk 6X");
  await user.click(screen.getByRole("button", { name: "Watchlist" }));
  const input = screen.getByLabelText("Product name or supported URL");
  expect(screen.getByRole("button", { name: "Add watch" })).toBeDisabled();
  await user.type(input, "Raspberry Pi 5");
  await user.click(screen.getByRole("button", { name: "Add watch" }));
  await waitFor(() => expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/watchlist"), expect.objectContaining({ method: "POST" })));
  expect(await screen.findByText("Product added to your watchlist.")).toBeInTheDocument();
});

test("defaults to relevant products and sends practical catalog filters", async () => {
  const user = userEvent.setup();
  window.history.replaceState({}, "", "/products");
  render(<App />);

  expect(await screen.findByDisplayValue("All relevant categories")).toBeInTheDocument();
  expect(screen.getByText("The retailer blocked the automated request (HTTP 403).")).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Retailer"), "ThinkRobotics");
  await user.type(screen.getByLabelText("Minimum price"), "5000");
  await user.type(screen.getByLabelText("Maximum price"), "15000");
  await user.click(screen.getByRole("button", { name: "Apply filters" }));

  await waitFor(() => expect(fetch).toHaveBeenCalledWith(
    expect.stringMatching(/\/api\/products\?.*retailer=ThinkRobotics.*min_price=5000.*max_price=15000/),
    expect.objectContaining({ headers: { "Content-Type": "application/json" } }),
  ));
});
