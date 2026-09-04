import type { PaymentSummary } from "@/lib/format";

type FlowSegment = {
  key: string;
  label: string;
  count: number;
  bar: string;
  band: string;
};

const HEIGHT = 260;
const LEFT_X = 96;
const BAR_W = 14;
const RIGHT_X = 512;
const GAP = 10;

/**
 * Sankey-style flow: every created payment on the left, its outcome on the
 * right. Band widths are proportional to payment counts.
 *
 * Pure server-rendered SVG (no client JS). Colors come from theme tokens so
 * both light and dark modes keep working.
 */
export function PaymentFlowChart({ summary }: { summary: PaymentSummary }) {
  if (summary.total === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No payments yet. Created links will flow into their outcomes here.
      </p>
    );
  }

  const segments: FlowSegment[] = [
    {
      key: "completed",
      label: "Completed",
      count: summary.completed,
      bar: "var(--pastel-green-text)",
      band: "var(--pastel-green-text)",
    },
    {
      key: "pending",
      label: "Pending",
      count: summary.pending,
      bar: "var(--pastel-yellow-text)",
      band: "var(--pastel-yellow-text)",
    },
    {
      key: "failed",
      label: "Failed",
      count: summary.failed,
      bar: "var(--pastel-red-text)",
      band: "var(--pastel-red-text)",
    },
    {
      key: "cancelled",
      label: "Cancelled",
      count: summary.cancelled,
      bar: "var(--muted-foreground)",
      band: "var(--muted-foreground)",
    },
  ];

  const totalHeight = HEIGHT;
  const gapsHeight = GAP * (segments.length - 1);
  const unit = (totalHeight - gapsHeight) / summary.total;

  let leftCursor = 0;
  let rightCursor = 0;
  const rows = segments.map((segment) => {
    const height = Math.max(segment.count > 0 ? 2 : 0, segment.count * unit);
    const leftCenter = leftCursor + (segment.count * unit) / 2;
    leftCursor += segment.count * unit;
    const rightCenter = rightCursor + height / 2;
    rightCursor += height + GAP;
    return { ...segment, height, leftCenter, rightCenter };
  });

  const midX = (LEFT_X + BAR_W + RIGHT_X) / 2;
  const ariaSummary = rows.map((row) => `${row.label} ${row.count}`).join(", ");

  return (
    <div
      role="img"
      aria-label={`Payment flow for ${summary.total} created payments: ${ariaSummary}`}
    >
      <svg viewBox={`0 0 640 ${HEIGHT + 8}`} className="w-full" role="presentation">
        {/* Left node: everything created */}
        <rect x={LEFT_X} y={0} width={BAR_W} height={totalHeight} rx={3} fill="var(--primary)" />
        <text x={LEFT_X - 8} y={totalHeight / 2 - 8} textAnchor="end" className="fill-foreground text-[13px] font-semibold">
          Created
        </text>
        <text x={LEFT_X - 8} y={totalHeight / 2 + 10} textAnchor="end" className="fill-muted-foreground font-mono text-[12px] tabular-nums">
          {summary.total}
        </text>

        {/* Flow bands */}
        {rows
          .filter((row) => row.count > 0)
          .map((row) => (
            <path
              key={row.key}
              d={`M ${LEFT_X + BAR_W} ${row.leftCenter} C ${midX} ${row.leftCenter}, ${midX} ${row.rightCenter}, ${RIGHT_X} ${row.rightCenter}`}
              fill="none"
              stroke={row.band}
              strokeOpacity={0.45}
              strokeWidth={row.height}
            />
          ))}

        {/* Right nodes: outcomes */}
        {rows.map((row) => {
          if (row.count === 0) return null;
          return (
            <g key={row.key}>
              <rect
                x={RIGHT_X}
                y={row.rightCenter - row.height / 2}
                width={BAR_W}
                height={row.height}
                rx={3}
                fill={row.bar}
              />
              <text x={RIGHT_X + BAR_W + 8} y={row.rightCenter - 1} className="fill-foreground text-[13px] font-medium">
                {row.label}
              </text>
              <text x={RIGHT_X + BAR_W + 8} y={row.rightCenter + 15} className="fill-muted-foreground font-mono text-[12px] tabular-nums">
                {row.count}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
