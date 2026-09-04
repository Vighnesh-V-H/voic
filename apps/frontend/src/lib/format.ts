import type { Payment } from "@/lib/api";

/**
 * Fixed formatting locale for every user-visible number and date.
 *
 * The server (Node) and the browser resolve the default locale differently
 * (e.g. "Aug 22" vs "22 Aug"), which breaks hydration. Pinning one locale
 * keeps SSR HTML identical to the first client render.
 */
const APP_LOCALE = "en-US";

export function formatMoney(amount: number | null | undefined, currency: string | null | undefined) {
  if (amount === null || amount === undefined || !currency) return "—";
  try {
    return new Intl.NumberFormat(APP_LOCALE, {
      style: "currency",
      currency: currency.toUpperCase(),
    }).format(amount / 100);
  } catch {
    return `${(amount / 100).toFixed(2)} ${currency.toUpperCase()}`;
  }
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(APP_LOCALE, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatMoneyCompact(amount: number | null | undefined, currency: string | null | undefined) {
  if (amount === null || amount === undefined || !currency) return "—";
  try {
    return new Intl.NumberFormat(APP_LOCALE, {
      style: "currency",
      currency: currency.toUpperCase(),
      notation: "compact",
    }).format(amount / 100);
  } catch {
    return formatMoney(amount, currency);
  }
}

export function paymentStatusVariant(status: string) {
  switch (status) {
    case "COMPLETED":
      return "success" as const;
    case "FAILED":
      return "error" as const;
    case "PENDING":
    case "CREATED":
      return "warning" as const;
    case "CANCELLED":
    default:
      return "secondary" as const;
  }
}

export function isPendingStatus(status: string) {
  return status === "PENDING" || status === "CREATED";
}

export type PaymentSummary = {
  total: number;
  completed: number;
  pending: number;
  failed: number;
  cancelled: number;
  completedVolume: number;
  totalVolume: number;
  pendingVolume: number;
  failedVolume: number;
  cancelledVolume: number;
  successRate: number;
  primaryCurrency: string | null;
  mixedCurrencies: boolean;
};

export function summarizePayments(payments: Payment[]): PaymentSummary {
  const total = payments.length;
  let completed = 0;
  let pending = 0;
  let failed = 0;
  let cancelled = 0;

  const currencyCounts = new Map<string, number>();
  for (const payment of payments) {
    if (payment.status === "COMPLETED") completed += 1;
    else if (isPendingStatus(payment.status)) pending += 1;
    else if (payment.status === "FAILED") failed += 1;
    else if (payment.status === "CANCELLED") cancelled += 1;
    const code = payment.currency?.toUpperCase();
    if (code) currencyCounts.set(code, (currencyCounts.get(code) ?? 0) + 1);
  }

  let primaryCurrency: string | null = null;
  let best = 0;
  for (const [code, count] of currencyCounts) {
    if (count > best) {
      best = count;
      primaryCurrency = code;
    }
  }

  let completedVolume = 0;
  let totalVolume = 0;
  let pendingVolume = 0;
  let failedVolume = 0;
  let cancelledVolume = 0;
  if (primaryCurrency) {
    for (const payment of payments) {
      if (payment.currency?.toUpperCase() !== primaryCurrency) continue;
      totalVolume += payment.amount;
      if (payment.status === "COMPLETED") completedVolume += payment.amount;
      else if (isPendingStatus(payment.status)) pendingVolume += payment.amount;
      else if (payment.status === "FAILED") failedVolume += payment.amount;
      else if (payment.status === "CANCELLED") cancelledVolume += payment.amount;
    }
  }

  return {
    total,
    completed,
    pending,
    failed,
    cancelled,
    completedVolume,
    totalVolume,
    pendingVolume,
    failedVolume,
    cancelledVolume,
    successRate: total === 0 ? 0 : Math.round((completed / total) * 100),
    primaryCurrency,
    mixedCurrencies: currencyCounts.size > 1,
  };
}

export type DayBucket = { key: string; label: string; value: number };

export type TrendPoint = {
  created_at?: string | null;
  amount: number;
  currency: string;
  status: string;
};

function startOfDay(date: Date) {
  const day = new Date(date);
  day.setHours(0, 0, 0, 0);
  return day;
}

function dayKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

/**
 * Bucket completed volume per day across an explicit date range (inclusive).
 *
 * Only the most common currency is counted so mixed-currency merchants get
 * one honest series. Ranges over 90 days are clamped by the caller.
 */
export function bucketVolumeByRange(payments: TrendPoint[], start: Date, end: Date): DayBucket[] {
  const first = startOfDay(start);
  const last = startOfDay(end);
  const buckets = new Map<string, number>();
  const labels = new Map<string, string>();
  for (let cursor = new Date(first); cursor <= last; cursor.setDate(cursor.getDate() + 1)) {
    const key = dayKey(cursor);
    buckets.set(key, 0);
    labels.set(
      key,
      new Intl.DateTimeFormat(APP_LOCALE, { day: "numeric", month: "short" }).format(cursor),
    );
  }

  const primary = mostCommonCurrency(payments);
  for (const payment of payments) {
    if (payment.status !== "COMPLETED" || !payment.created_at) continue;
    if (primary && payment.currency?.toUpperCase() !== primary) continue;
    const date = new Date(payment.created_at);
    if (Number.isNaN(date.getTime())) continue;
    const key = dayKey(date);
    if (buckets.has(key)) buckets.set(key, (buckets.get(key) ?? 0) + payment.amount);
  }

  return [...buckets.entries()].map(([key, value]) => ({
    key,
    label: labels.get(key) ?? key,
    value,
  }));
}

function mostCommonCurrency(payments: { currency: string }[]): string | null {
  const counts = new Map<string, number>();
  for (const payment of payments) {
    const code = payment.currency?.toUpperCase();
    if (code) counts.set(code, (counts.get(code) ?? 0) + 1);
  }
  let best: string | null = null;
  let bestCount = 0;
  for (const [code, count] of counts) {
    if (count > bestCount) {
      bestCount = count;
      best = code;
    }
  }
  return best;
}

export function shortId(id: string, visible = 8) {
  if (id.length <= visible + 3) return id;
  return `${id.slice(0, visible)}…`;
}

/**
 * Build the Stripe Dashboard URL for a product.
 *
 * Test-mode accounts live under /test/, live accounts do not.
 */
export function stripeProductUrl(productId: string, mode?: string | null) {
  const prefix = mode === "live" ? "https://dashboard.stripe.com/products" : "https://dashboard.stripe.com/test/products";
  return `${prefix}/${encodeURIComponent(productId)}`;
}
