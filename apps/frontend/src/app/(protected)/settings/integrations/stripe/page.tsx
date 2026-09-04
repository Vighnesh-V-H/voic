import Link from "next/link";

import { ArrowUpRightIcon, PackageIcon } from "lucide-react";

import { AppBreadcrumbs } from "@/components/app-breadcrumbs";
import { StripeConnectionCard } from "@/components/stripe-connection-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { formatDateTime, formatMoney, paymentStatusVariant, shortId, stripeProductUrl } from "@/lib/format";
import { loadStripeCatalog } from "@/lib/server-api";

/**
 * Stripe management: connection status plus every product as a table.
 *
 * Each product links to its own page for prices, payment creation, and
 * that product's payments.
 */
export default async function StripeManagePage() {
  const { connection, products, prices, payments, events } = await loadStripeCatalog();
  const isConnected = connection.connected === true;

  const pricesByProduct = new Map<string, typeof prices>();
  for (const price of prices) {
    if (!price.product_id) continue;
    const list = pricesByProduct.get(price.product_id) ?? [];
    list.push(price);
    pricesByProduct.set(price.product_id, list);
  }

  const priceToProduct = new Map(prices.map((price) => [price.id, price.product_id ?? null]));
  const productById = new Map(products.map((product) => [product.id, product]));
  const paymentsByProduct = new Map<string, number>();
  for (const payment of payments) {
    const productId = priceToProduct.get(payment.provider_price_id);
    if (productId) paymentsByProduct.set(productId, (paymentsByProduct.get(productId) ?? 0) + 1);
  }

  return (
    <section className="flex flex-col py-2">
      <AppBreadcrumbs
        items={[{ label: "Integrations", href: "/settings/integrations" }, { label: "Stripe" }]}
      />
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Stripe</h1>
          <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
            {isConnected
              ? `${products.length} ${products.length === 1 ? "product" : "products"} · ${prices.length} ${prices.length === 1 ? "price" : "prices"} · ${payments.length} ${payments.length === 1 ? "payment" : "payments"}`
              : "Connect Stripe to sync its catalog."}
          </p>
        </div>
      </div>

      <StripeConnectionCard connection={connection} />

      {!isConnected ? null : products.length === 0 ? (
        <Empty className="mt-4">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <PackageIcon />
            </EmptyMedia>
            <EmptyTitle>No products found</EmptyTitle>
            <EmptyDescription>
              Add a product with an active price in Stripe, then reload this page.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle>Products</CardTitle>
            <CardDescription>Every product synced from Stripe. Open one to create links and view payments.</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead>Prices</TableHead>
                  <TableHead>Payments</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {products.map((product) => {
                  const productPrices = pricesByProduct.get(product.id) ?? [];
                  const paymentCount = paymentsByProduct.get(product.id) ?? 0;
                  const fromAmount = productPrices.find((price) => price.unit_amount != null);
                  return (
                    <TableRow key={product.id}>
                      <TableCell>
                        <div className="flex max-w-65 flex-col">
                          <Link
                            href={`/settings/integrations/stripe/products/${product.id}`}
                            className="truncate font-medium text-primary underline-offset-4 hover:underline"
                          >
                            {product.name}
                          </Link>
                          <span className="truncate font-mono text-xs text-muted-foreground" title={product.id}>
                            {product.id}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className="font-mono tabular-nums">{productPrices.length}</span>{" "}
                        <span className="text-muted-foreground">
                          {fromAmount
                            ? `from ${formatMoney(fromAmount.unit_amount, fromAmount.currency)}`
                            : "no amounts"}
                        </span>
                      </TableCell>
                      <TableCell className="font-mono tabular-nums">{paymentCount}</TableCell>
                      <TableCell>
                        <Badge variant={product.active ? "success" : "secondary"}>
                          {product.active ? "Active" : "Inactive"}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            nativeButton={false}
                            render={
                              <Link href={`/settings/integrations/stripe/products/${product.id}`}>
                                Manage
                              </Link>
                            }
                          />
                          <Button
                            variant="link"
                            size="sm"
                            nativeButton={false}
                            render={
                              <a
                                href={stripeProductUrl(product.id, connection.mode)}
                                target="_blank"
                                rel="noreferrer"
                              >
                                Open in Stripe
                                <ArrowUpRightIcon data-icon="inline-end" />
                              </a>
                            }
                          />
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {!isConnected ? null : (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle>Recent events</CardTitle>
            <CardDescription>Checkout completions and payment failures, newest first</CardDescription>
          </CardHeader>
          <CardContent>
            {events.length === 0 ? (
              <p className="text-sm text-muted-foreground">No webhook events received yet.</p>
            ) : (
              <ul className="flex flex-col divide-y divide-border">
                {events.slice(0, 5).map((event) => {
                  const productId = event.provider_price_id
                    ? (priceToProduct.get(event.provider_price_id) ?? null)
                    : null;
                  const product = productId ? productById.get(productId) : undefined;
                  return (
                  <li
                    key={event.id}
                    className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="truncate font-medium">{event.event_type}</span>
                        {event.payment_status ? (
                          <Badge variant={paymentStatusVariant(event.payment_status)}>{event.payment_status}</Badge>
                        ) : null}
                      </div>
                      <div className="mt-1 flex flex-wrap gap-x-3 text-xs text-muted-foreground">
                        {product ? (
                          <Link
                            href={`/settings/integrations/stripe/products/${product.id}`}
                            className="font-medium text-primary underline-offset-4 hover:underline"
                          >
                            {product.name}
                          </Link>
                        ) : (
                          <span>No linked product</span>
                        )}
                        {event.provider_price_id ? (
                          <span className="font-mono" title={event.provider_price_id}>
                            {event.provider_price_id}
                          </span>
                        ) : null}
                      </div>
                      {event.customer_email || event.customer_phone ? (
                        <div className="mt-1 flex flex-wrap gap-x-3 text-xs text-muted-foreground">
                          {event.customer_email ? <span>{event.customer_email}</span> : null}
                          {event.customer_phone ? <span>{event.customer_phone}</span> : null}
                        </div>
                      ) : null}
                    </div>
                    <div className="flex shrink-0 items-center gap-3 text-xs text-muted-foreground">
                      <span className="truncate font-mono" title={event.provider_payment_id ?? event.id}>
                        {event.provider_payment_id ? shortId(event.provider_payment_id) : "Account event"}
                      </span>
                      <span>{formatDateTime(event.occurred_at)}</span>
                    </div>
                  </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>
      )}
    </section>
  );
}
