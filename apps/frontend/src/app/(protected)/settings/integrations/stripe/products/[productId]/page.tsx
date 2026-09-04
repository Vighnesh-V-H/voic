import { notFound } from "next/navigation";

import { ArrowUpRightIcon } from "lucide-react";

import { AppBreadcrumbs } from "@/components/app-breadcrumbs";
import { ProductPaymentsPanel } from "@/components/product-payments-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { stripeProductUrl } from "@/lib/format";
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

      <ProductPaymentsPanel
        productName={product.name}
        productPrices={productPrices}
        initialPayments={productPayments}
        priceLabels={priceLabels}
      />
    </section>
  );
}
