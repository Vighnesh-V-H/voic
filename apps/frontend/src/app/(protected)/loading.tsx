import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

/**
 * Loading state for protected routes. Mirrors the dashboard shape so the
 * layout does not jump when real data arrives.
 *
 * @returns A skeleton matching the dashboard stat, chart, and table layout.
 */
export default function ProtectedLoading() {
  return (
    <section className="flex flex-col py-2" aria-label="Loading workspace">
      <Skeleton className="mb-6 h-4 w-32" />
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-2">
          <Skeleton className="h-9 w-48" />
          <Skeleton className="h-4 w-72 max-w-full" />
        </div>
        <Skeleton className="h-8 w-44" />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-hidden="true">
        {["total", "payments", "rate", "failed"].map((key) => (
          <Card key={key}>
            <CardHeader>
              <Skeleton className="h-3.5 w-24" />
              <Skeleton className="h-8 w-20" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-4 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2" aria-hidden="true">
        {["trend", "flow"].map((key) => (
          <Card key={key}>
            <CardHeader>
              <Skeleton className="h-5 w-32" />
              <Skeleton className="h-4 w-56 max-w-full" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-44 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  );
}
