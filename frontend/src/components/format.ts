export function formatPrice(price: string | null, currency = "INR") {
  if (price === null) return "Price unavailable";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(Number(price));
}

export function formatTime(value: string | null) {
  if (!value) return "Not checked yet";
  return new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Kolkata",
  }).format(new Date(value));
}
