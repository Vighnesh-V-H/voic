"use client";

import { useEffect, useMemo, useState } from "react";

import { RevenueChart } from "@/components/revenue-chart";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { bucketVolumeByRange, formatMoney, type TrendPoint } from "@/lib/format";
import { cn } from "@/lib/utils";

const PRESETS = [
  { key: "7", label: "7D", days: 7 },
  { key: "14", label: "14D", days: 14 },
  { key: "30", label: "30D", days: 30 },
  { key: "all", label: "All", days: null },
] as const;

type PresetKey = (typeof PRESETS)[number]["key"] | "custom";

const MAX_SPAN_DAYS = 90;

function toInputValue(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function parseInputValue(value: string) {
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(year, (month ?? 1) - 1, day);
  return Number.isNaN(date.getTime()) ? null : date;
}

/**
 * Completed-volume trend with a date-range selector.
 *
 * Presets cover the last 7 / 14 / 30 days or everything on record; editing
 * either date field switches to a custom range. Filtering is client-side —
 * no refetching — and ranges clamp to 90 days so daily bars stay readable.
 */
export function RevenueTrendChart({
  payments,
  currency,
}: {
  payments: TrendPoint[];
  currency: string | null;
}) {
  const today = useMemo(() => {
    const date = new Date();
    date.setHours(0, 0, 0, 0);
    return date;
  }, []);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // Mount guard: "today" and the date inputs are inherently local, so the
    // selector renders after mount to keep SSR HTML identical.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);
  const defaultStart = useMemo(() => {
    const date = new Date(today);
    date.setDate(date.getDate() - 13);
    return date;
  }, [today]);

  const [mode, setMode] = useState<PresetKey>("14");
  const [from, setFrom] = useState(toInputValue(defaultStart));
  const [to, setTo] = useState(toInputValue(today));

  const range = useMemo(() => {
    if (mode === "custom") {
      const fromDate = parseInputValue(from);
      const toDate = parseInputValue(to);
      if (!fromDate || !toDate) return null;
      const start = fromDate <= toDate ? fromDate : toDate;
      const end = fromDate <= toDate ? toDate : fromDate;
      const span = Math.round((end.getTime() - start.getTime()) / 86400000) + 1;
      if (span > MAX_SPAN_DAYS) {
        const clamped = new Date(end);
        clamped.setDate(clamped.getDate() - (MAX_SPAN_DAYS - 1));
        return { start: clamped, end };
      }
      return { start, end };
    }
    if (mode === "all") {
      let earliest: Date | null = null;
      for (const payment of payments) {
        if (!payment.created_at) continue;
        const date = new Date(payment.created_at);
        if (Number.isNaN(date.getTime())) continue;
        if (!earliest || date < earliest) earliest = date;
      }
      const floor = new Date(today);
      floor.setDate(floor.getDate() - (MAX_SPAN_DAYS - 1));
      const start = earliest && earliest > floor ? earliest : floor;
      return { start, end: today };
    }
    const preset = PRESETS.find((item) => item.key === mode);
    const days = preset?.days ?? 14;
    const start = new Date(today);
    start.setDate(start.getDate() - (days - 1));
    return { start, end: today };
  }, [from, mode, payments, to, today]);

  const buckets = useMemo(
    () => (range ? bucketVolumeByRange(payments, range.start, range.end) : []),
    [payments, range],
  );
  const total = useMemo(() => buckets.reduce((sum, bucket) => sum + bucket.value, 0), [buckets]);
  const activeDays = useMemo(() => buckets.filter((bucket) => bucket.value > 0).length, [buckets]);

  if (payments.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No payments yet. Completed volume will trend here once checkout starts.
      </p>
    );
  }

  if (!mounted) {
    return (
      <div className="flex flex-col gap-4" aria-label="Loading payment trend">
        <Skeleton className="h-9 w-48" />
        <Skeleton className="h-54" />
        <Skeleton className="h-8 w-full" />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="font-mono text-3xl font-semibold tabular-nums">{formatMoney(total, currency)}</p>
        <p className="text-xs text-muted-foreground">
          completed · {activeDays} {activeDays === 1 ? "day" : "days"} active
        </p>
      </div>
      {range ? (
        <RevenueChart buckets={buckets} currency={currency} />
      ) : (
        <p className="text-sm text-muted-foreground">Enter a valid date range to see the trend.</p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <div
          className="inline-flex rounded-lg border border-border bg-card p-0.5"
          role="group"
          aria-label="Date range presets"
        >
          {PRESETS.map((preset) => (
            <button
              key={preset.key}
              type="button"
              onClick={() => setMode(preset.key)}
              aria-pressed={mode === preset.key}
              className={cn(
                "h-7 rounded-md px-2.5 text-xs font-medium transition-colors outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                mode === preset.key
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {preset.label}
            </button>
          ))}
        </div>
        <div className="flex flex-1 flex-wrap items-center gap-2 sm:justify-end">
          <label htmlFor="trend-from" className="sr-only">
            From date
          </label>
          <Input
            id="trend-from"
            type="date"
            aria-label="From date"
            className="h-8 w-auto text-xs"
            value={from}
            max={to}
            onChange={(event) => {
              setFrom(event.target.value);
              setMode("custom");
            }}
          />
          <span aria-hidden="true" className="text-xs text-muted-foreground">
            →
          </span>
          <label htmlFor="trend-to" className="sr-only">
            To date
          </label>
          <Input
            id="trend-to"
            type="date"
            aria-label="To date"
            className="h-8 w-auto text-xs"
            value={to}
            min={from}
            max={toInputValue(today)}
            onChange={(event) => {
              setTo(event.target.value);
              setMode("custom");
            }}
          />
        </div>
      </div>
    </div>
  );
}
