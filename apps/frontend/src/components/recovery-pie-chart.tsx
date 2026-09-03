"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

import { formatMoney, type PaymentSummary } from "@/lib/format";
import { cn } from "@/lib/utils";

const LIGHT_FILLS = {
  recovered: "#067647",
  awaiting: "#dc6803",
  failed: "#b42318",
  cancelled: "#98a2b3",
};

const DARK_FILLS = {
  recovered: "#6ce9a6",
  awaiting: "#fdb022",
  failed: "#f97066",
  cancelled: "#98a2b3",
};

type Slice = {
  key: keyof typeof LIGHT_FILLS;
  name: string;
  value: number;
};

/**
 * Money-recovery donut: recovered vs awaiting vs failed volume.
 *
 * Rendered with Recharts. Fills follow the active theme (resolved after
 * mount, same guard as the theme toggle) so slices stay vivid in both
 * light and dark modes.
 */
export function RecoveryPieChart({ summary }: { summary: PaymentSummary }) {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    // Mount guard for client-only theme resolution.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);

  const fills = mounted && resolvedTheme === "dark" ? DARK_FILLS : LIGHT_FILLS;

  const slices: Slice[] = (
    [
      { key: "recovered", name: "Recovered", value: summary.completedVolume },
      { key: "awaiting", name: "Awaiting", value: summary.pendingVolume },
      { key: "failed", name: "Failed", value: summary.failedVolume },
      { key: "cancelled", name: "Cancelled", value: summary.cancelledVolume },
    ] as Slice[]
  ).filter((slice) => slice.value > 0);

  const totalVolume = slices.reduce((sum, slice) => sum + slice.value, 0);

  if (summary.total === 0 || totalVolume === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No payment volume yet. Recovered money will chart here.
      </p>
    );
  }

  const recoveredPct = Math.round((summary.completedVolume / totalVolume) * 100);

  return (
    <div className="flex flex-col gap-4">
      <div className="relative mx-auto w-full max-w-70">
        <ResponsiveContainer width="100%" height={220}>
          <PieChart role="img" aria-label={`Money recovery: ${recoveredPct}% recovered`}>
            <Tooltip
              formatter={(value) => formatMoney(Number(value), summary.primaryCurrency)}
              contentStyle={{
                background: "var(--card)",
                border: "1px solid var(--border)",
                borderRadius: 8,
                fontSize: 12,
              }}
            />
            <Pie
              data={slices}
              dataKey="value"
              nameKey="name"
              innerRadius="64%"
              outerRadius="88%"
              paddingAngle={3}
              cornerRadius={6}
              strokeWidth={0}
            >
              {slices.map((slice) => (
                <Cell key={slice.key} fill={fills[slice.key]} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono text-2xl font-semibold tabular-nums">{recoveredPct}%</span>
          <span className="text-xs text-muted-foreground">recovered</span>
        </div>
      </div>
      <ul className="flex flex-col divide-y divide-border">
        {slices.map((slice) => (
          <li key={slice.key} className="flex items-center gap-2.5 py-2 first:pt-0 last:pb-0">
            <span
              aria-hidden="true"
              className={cn("size-2.5 shrink-0 rounded-full")}
              style={{ background: fills[slice.key] }}
            />
            <span className="text-sm font-medium">{slice.name}</span>
            <span className="ml-auto font-mono text-sm tabular-nums">
              {formatMoney(slice.value, summary.primaryCurrency)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
