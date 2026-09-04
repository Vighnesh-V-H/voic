import { formatMoney, formatMoneyCompact, type DayBucket } from "@/lib/format";

const VIEW_W = 560;
const VIEW_H = 216;
const PAD = { top: 24, right: 12, bottom: 26, left: 46 };

type Point = {
  x: number;
  y: number;
};

function round(value: number) {
  return Math.round(value * 10) / 10;
}

function smoothLine(points: Point[], minY: number, maxY: number) {
  if (points.length < 2) return "";

  if (points.length === 2) {
    return `M ${round(points[0].x)} ${round(points[0].y)} L ${round(
      points[1].x,
    )} ${round(points[1].y)}`;
  }

  let path = `M ${round(points[0].x)} ${round(points[0].y)}`;

  for (let i = 0; i < points.length - 1; i += 1) {
    const p0 = points[Math.max(0, i - 1)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(points.length - 1, i + 2)];

    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = Math.max(
      minY,
      Math.min(maxY, p1.y + (p2.y - p0.y) / 6),
    );

    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = Math.max(
      minY,
      Math.min(maxY, p2.y - (p3.y - p1.y) / 6),
    );

    path += ` C ${round(c1x)} ${round(c1y)}, ${round(c2x)} ${round(
      c2y,
    )}, ${round(p2.x)} ${round(p2.y)}`;
  }

  return path;
}

export function RevenueChart({
  buckets,
  currency,
}: {
  buckets: DayBucket[];
  currency: string | null;
}) {
  const peak = Math.max(0, ...buckets.map((bucket) => bucket.value));
  const hasVolume = peak > 0;

  const plotW = VIEW_W - PAD.left - PAD.right;
  const plotH = VIEW_H - PAD.top - PAD.bottom;
  const baseY = PAD.top + plotH;

  if (buckets.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Enter a valid date range to see the trend.
      </p>
    );
  }

  const step =
    buckets.length === 1 ? 0 : plotW / (buckets.length - 1);

  const points: Point[] = buckets.map((bucket, index) => ({
    x:
      PAD.left +
      (buckets.length === 1 ? plotW / 2 : index * step),
    y: hasVolume
      ? PAD.top + plotH * (1 - bucket.value / peak)
      : baseY,
  }));

  const line = smoothLine(points, PAD.top, baseY);

  const area = line
    ? `${line} L ${round(
        points[points.length - 1].x,
      )} ${baseY} L ${round(points[0].x)} ${baseY} Z`
    : "";

  const peakIndex = buckets.findIndex(
    (bucket) => bucket.value === peak,
  );

  const tickIndexes = [
    ...new Set([
      0,
      Math.floor((buckets.length - 1) / 3),
      Math.floor((2 * (buckets.length - 1)) / 3),
      buckets.length - 1,
    ]),
  ];

  const gridValues = [0, peak / 2, peak];

  return (
    <div
      role="img"
      aria-label={
        hasVolume
          ? `Completed payments by day, peak ${formatMoney(
              peak,
              currency,
            )}`
          : "No completed payments in the selected range"
      }
    >
      <svg
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        className="w-full"
        role="presentation"
      >
        {gridValues.map((value, index) => {
          const y = hasVolume
            ? PAD.top + plotH * (1 - value / peak)
            : baseY;

          return (
            <g key={`grid-${index}`}>
              <line
                x1={PAD.left}
                x2={VIEW_W - PAD.right}
                y1={round(y)}
                y2={round(y)}
                stroke="var(--border)"
                strokeDasharray="3 4"
              />

              <text
                x={PAD.left - 8}
                y={round(y) + 3.5}
                textAnchor="end"
                className="fill-muted-foreground font-mono text-[10px] tabular-nums"
              >
                {formatMoneyCompact(value, currency)}
              </text>
            </g>
          );
        })}

        {area ? (
          <>
            <path
              d={area}
              fill="var(--primary)"
              fillOpacity={0.08}
            />

            <path
              d={line}
              fill="none"
              stroke="var(--primary)"
              strokeWidth={1.5}
              vectorEffect="non-scaling-stroke"
              strokeLinecap="round"
            />
          </>
        ) : null}

        <line
          x1={PAD.left}
          x2={VIEW_W - PAD.right}
          y1={baseY}
          y2={baseY}
          stroke="var(--border)"
        />

        {tickIndexes.map((index) => (
          <text
            key={buckets[index].key}
            x={round(points[index].x)}
            y={VIEW_H - 8}
            textAnchor="middle"
            className="fill-muted-foreground text-[10px]"
          >
            {buckets[index].label}
          </text>
        ))}

        {hasVolume && peakIndex >= 0 ? (
          <g>
            <circle
              cx={round(points[peakIndex].x)}
              cy={round(points[peakIndex].y)}
              r={3.5}
              fill="var(--primary)"
            />

            <text
              x={Math.min(
                Math.max(points[peakIndex].x, PAD.left + 30),
                VIEW_W - PAD.right - 30,
              )}
              y={round(points[peakIndex].y) - 9}
              textAnchor="middle"
              className="fill-foreground font-mono text-[11px] font-semibold tabular-nums"
            >
              {formatMoney(peak, currency)}
            </text>
          </g>
        ) : null}

        {buckets.map((bucket, index) => {
          const half =
            buckets.length === 1 ? plotW / 2 : step / 2;

          return (
            <g key={bucket.key} className="group">
              <rect
                x={round(
                  Math.max(
                    PAD.left,
                    points[index].x - half,
                  ),
                )}
                y={PAD.top}
                width={round(
                  Math.min(
                    points[index].x + half,
                    VIEW_W - PAD.right,
                  ) -
                    Math.max(
                      PAD.left,
                      points[index].x - half,
                    ),
                )}
                height={plotH}
                fill="transparent"
              />

              <circle
                cx={round(points[index].x)}
                cy={round(points[index].y)}
                r={4}
                fill="var(--card)"
                stroke="var(--primary)"
                strokeWidth={2}
                className="opacity-0 transition-opacity group-hover:opacity-100"
              />
            </g>
          );
        })}
      </svg>
    </div>
  );
}
