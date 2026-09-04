import Link from "next/link";

import { ArrowUpRightIcon } from "lucide-react";

import { AppBreadcrumbs } from "@/components/app-breadcrumbs";
import { PaymentFlowChart } from "@/components/payment-flow-chart";
import { PaymentsTable } from "@/components/payments-table";
import { RecoveryPieChart } from "@/components/recovery-pie-chart";
import { RevenueTrendChart } from "@/components/revenue-trend-chart";
import { StatCard } from "@/components/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatMoney, summarizePayments } from "@/lib/format";
import { loadDashboardData } from "@/lib/server-api";

/**
 * Merchant dashboard: real payment metrics, charts, and every payment.
 */
export default async function DashboardPage() {
  const { identity, payments, connection, products, prices } = await loadDashboardData();
  const summary = summarizePayments(payments);
  const trendPayments = payments.map((payment) => ({
    created_at: payment.created_at,
    amount: payment.amount,
    currency: payment.currency,
    status: payment.status,
  }));

  const productNames = new Map(products.map((product) => [product.id, product.name]));
  const priceLabels: Record<string, { name: string; productId: string | null }> = {};
  for (const price of prices) {
    const productName = (price.product_id && productNames.get(price.product_id)) || "Unknown product";
    priceLabels[price.id] = { name: productName, productId: price.product_id ?? null };
  }

  return (
    <section className="flex flex-col py-2">
      <AppBreadcrumbs items={[{ label: "Dashboard" }]} />
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">Dashboard</h1>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
            Live payments for {identity.merchant.name}. Amounts settle in Stripe; Voic tracks status here.
          </p>
        </div>
        <Button
          variant="outline"
          nativeButton={false}
          render={
            <Link href="/settings/integrations">
              Manage integrations
              <ArrowUpRightIcon data-icon="inline-end" />
            </Link>
          }
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Total received"
          value={formatMoney(summary.completedVolume, summary.primaryCurrency)}
          hint={
            summary.primaryCurrency
              ? `Completed · ${summary.primaryCurrency}${summary.mixedCurrencies ? " · mixed currencies" : ""}`
              : "No payments yet"
          }
        />
        <StatCard
          label="Payments"
          value={String(summary.total)}
          hint={`${summary.completed} completed · ${summary.pending} pending`}
        />
        <StatCard
          label="Success rate"
          value={`${summary.successRate}%`}
          hint={summary.total === 0 ? "No attempts yet" : `${summary.completed} of ${summary.total} completed`}
        />
        <StatCard
          label="Failed"
          value={String(summary.failed)}
          hint={summary.failed === 0 ? "No failures recorded" : "Review failed rows below"}
          action={
            summary.failed > 0 ? <Badge variant="error">Action</Badge> : undefined
          }
        />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Payment trend</CardTitle>
            <CardDescription>Completed volume per day for the selected range</CardDescription>
          </CardHeader>
          <CardContent>
            <RevenueTrendChart payments={trendPayments} currency={summary.primaryCurrency} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Payment flow</CardTitle>
            <CardDescription>Every created payment flowing into its outcome</CardDescription>
          </CardHeader>
          <CardContent>
            <PaymentFlowChart summary={summary} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Money recovery</CardTitle>
            <CardDescription>Recovered vs awaiting vs failed volume</CardDescription>
          </CardHeader>
          <CardContent>
            <RecoveryPieChart summary={summary} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Status breakdown</CardTitle>
            <CardDescription>Every payment grouped by Voic status</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col divide-y divide-border">
              {(
                [
                  ["COMPLETED", summary.completed, "success"],
                  ["PENDING + CREATED", summary.pending, "warning"],
                  ["FAILED", summary.failed, "error"],
                  ["CANCELLED", summary.cancelled, "secondary"],
                ] as const
              ).map(([label, count, variant]) => (
                <li key={label} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                  <Badge variant={variant}>{label}</Badge>
                  <span className="font-mono text-lg tabular-nums">{count}</span>
                </li>
              ))}
            </ul>
            {!connection.connected ? (
              <p className="mt-4 text-sm text-muted-foreground">
                Stripe is not connected.{" "}
                <Link href="/settings/integrations" className="font-medium text-primary underline-offset-4 hover:underline">
                  Connect
                </Link>{" "}
                to sync products.
              </p>
            ) : (
              <p className="mt-4 text-sm text-muted-foreground">
                {products.length} {products.length === 1 ? "product" : "products"} · {prices.length}{" "}
                {prices.length === 1 ? "price" : "prices"} synced from Stripe.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>All payments</CardTitle>
          <CardDescription>
            {payments.length === 0
              ? "Created, pending, completed, failed, and cancelled payments will list here."
              : "Every payment with product names, status filters, sorting, and pagination."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PaymentsTable payments={payments} priceLabels={priceLabels} />
        </CardContent>
      </Card>
    </section>
  );
}
