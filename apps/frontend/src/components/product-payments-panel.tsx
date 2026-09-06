"use client";

import { useState } from "react";
import Link from "next/link";

import type { Payment, StripePrice } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { PaymentsTable } from "@/components/payments-table";
import { ProductPaymentForm } from "@/components/product-payment-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

/**
 * Prices, create-payment actions, and the product's payments table in one
 * client island, so a freshly created Payment Link or PaymentIntent appears
 * in the table below instantly without a server round-trip or reload.
 */
export function ProductPaymentsPanel({
  productName,
  productPrices,
  initialPayments,
  priceLabels,
}: {
  productName: string;
  productPrices: StripePrice[];
  initialPayments: Payment[];
  priceLabels: Record<string, { name: string; productId: string | null }>;
}) {
  const [payments, setPayments] = useState<Payment[]>(initialPayments);

  function handleCreated(payment: Payment) {
    setPayments((current) => [payment, ...current.filter((item) => item.id !== payment.id)]);
  }

  return (
    <>
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
            <ProductPaymentForm productName={productName} prices={productPrices} onCreated={handleCreated} />
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Payments for {productName}</CardTitle>
          <CardDescription>
            {payments.length === 0
              ? "No Voic payments created from this product yet."
              : `${payments.length} ${payments.length === 1 ? "payment" : "payments"} created from this product.`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <PaymentsTable payments={payments} priceLabels={priceLabels} compact />
          <p className="mt-3 text-sm text-muted-foreground">
            <Link href="/dashboard" className="font-medium text-primary underline-offset-4 hover:underline">
              View all payments on the dashboard
            </Link>
          </p>
        </CardContent>
      </Card>
    </>
  );
}
