import { formatMoney, type DayBucket } from "@/lib/format";

/**
 * Completed-volume bar chart for the last 14 days.
 *
 * Pure server-rendered bars (no client JS): height is proportional to the
 * peak day. Amounts stay in the primary currency.
 */
export function RevenueChart({
  buckets,
  currency,
}: {
  buckets: DayBucket[];
  currency: string | null;
}) {
  const peak = Math.max(0, ...buckets.map((bucket) => bucket.value));
  const hasVolume = peak > 0;

  return (
    <div>
      <div
        className="flex h-36 items-end gap-1.5"
        role="img"
        aria-label={
          hasVolume
            ? `Completed payments by day, peak ${formatMoney(peak, currency)}`
            : "No completed payments in the last 14 days"
        }
      >
        {buckets.map((bucket) => {
          const height = hasVolume ? Math.max(4, Math.round((bucket.value / peak) * 100)) : 4;
          return (
            <div key={bucket.key} className="flex min-w-0 flex-1 flex-col items-center gap-2 self-stretch">
              <div className="flex w-full flex-1 items-end">
                <div
                  title={`${bucket.label}: ${formatMoney(bucket.value, currency)}`}
                  className={
                    bucket.value > 0
                      ? "w-full rounded-sm bg-primary"
                      : "w-full rounded-sm bg-border"
                  }
                  style={{ height: `${height}%` }}
                />
              </div>
              <span className="hidden truncate text-[10px] text-muted-foreground sm:block">
                {bucket.label}
              </span>
            </div>
          );
        })}
      </div>
      <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
        <span>{buckets[0]?.label}</span>
        <span className="font-mono">
          Peak {formatMoney(peak, currency)}
        </span>
        <span>{buckets[buckets.length - 1]?.label}</span>
      </div>
    </div>
  );
}
