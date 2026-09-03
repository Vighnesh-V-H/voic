import type { ReactNode } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Single dashboard metric: label, monospaced value, and supporting hint.
 */
export function StatCard({
  label,
  value,
  hint,
  action,
}: {
  label: string;
  value: string;
  hint: string;
  action?: ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardDescription>{label}</CardDescription>
        <CardTitle className="font-mono text-2xl tabular-nums">{value}</CardTitle>
      </CardHeader>
      <CardContent className="flex items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">{hint}</p>
        {action}
      </CardContent>
    </Card>
  );
}
