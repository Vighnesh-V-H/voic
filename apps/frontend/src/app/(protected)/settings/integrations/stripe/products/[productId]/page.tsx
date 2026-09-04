import Link from "next/link";
import { notFound } from "next/navigation";

import { ArrowUpRightIcon } from "lucide-react";

import { AppBreadcrumbs } from "@/components/app-breadcrumbs";
import { PaymentsTable } from "@/components/payments-table";
import { ProductPaymentForm } from "@/components/product-payment-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatMoney, stripeProductUrl } from "@/lib/format";
import { loadStripeCatalog } from "@/lib/server-api";

/**
 * Single Stripe product: prices, payment creation, and its payments.
 */
export default async function StripeProductPage({
  params,
}: {
  params: Promise<{ productId: string }>;
}) {
  const { productId } = await params;
  const { connection, products, prices, payments } = await loadStripeCatalog();

  if (!connection.connected) notFound();

  const product = products.find((item) => item.id === productId);
  if (!product) notFound();

  const productPrices = prices.filter((price) => price.product_id === product.id);
  const productPriceIds = new Set(productPrices.map((price) => price.id));
  const productPayments = payments.filter((payment) => productPriceIds.has(payment.provider_price_id));
  const priceLabels: Record<string, { name: string; productId: string | null }> = {};
  for (const price of prices) {
    priceLabels[price.id] = { name: product.name, productId: price.product_id ?? null };
  }

  return (
    <section className="flex flex-col py-2">
      <AppBreadcrumbs
        items={[
          { label: "Integrations", href: "/settings/integrations" },
          { label: "Stripe", href: "/settings/integrations/stripe" },
          { label: product.name },
        ]}
      />
      <div className="mb-6">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">{product.name}</h1>
          <Badge variant={product.active ? "success" : "secondary"}>
            {product.active ? "Active" : "Inactive"}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            nativeButton={false}
            render={
              <a href={stripeProductUrl(product.id, connection.mode)} target="_blank" rel="noreferrer">
                Open in Stripe
                <ArrowUpRightIcon data-icon="inline-end" />
              </a>
            }
          />
        </div>
        <p className="mt-2 font-mono text-xs break-all text-muted-foreground">{product.id}</p>
        {product.description ? (
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">{product.description}</p>
        ) : null}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Prices</CardTitle>
            <CardDescription>
              {productPrices.length === 0
                ? "No active prices for this product."
                : `${productPrices.length} ${productPrices.length === 1 ? "price" : "prices"} available for checkout.`}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {productPrices.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Add a price in Stripe to enable Payment Links.
              </p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Amount</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Price ID</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {productPrices.map((price) => (
                    <TableRow key={price.id}>
                      <TableCell className="font-mono font-semibold tabular-nums">
                        {formatMoney(price.unit_amount, price.currency)}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {price.type === "recurring" ? "Recurring" : price.type === "one_time" ? "One-time" : (price.type ?? "—")}
                      </TableCell>
                      <TableCell className="font-mono text-xs break-all text-muted-foreground">
                        {price.id}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Create checkout</CardTitle>
            <CardDescription>Payment Links and PaymentIntents use this product&apos;s prices.</CardDescription>
          </CardHeader>
          <CardContent>
            <ProductPaymentForm productName={product.name} prices={productPrices} />
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Payments for {product.name}</CardTitle>
          <CardDescription>
            {productPayments.length === 0
              ? "No Voic payments created from this product yet."
              : `${productPayments.length} ${productPayments.length === 1 ? "payment" : "payments"} created from this product.`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PaymentsTable payments={productPayments} priceLabels={priceLabels} compact />
          <p className="mt-3 text-sm text-muted-foreground">
            <Link
              href="/dashboard"
              className="font-medium text-primary underline-offset-4 hover:underline"
            >
              View all payments on the dashboard
            </Link>
          </p>
        </CardContent>
      </Card>
    </section>
  );
}
