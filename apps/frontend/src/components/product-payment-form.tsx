"use client";

import { useState } from "react";

import { InfoIcon, TriangleAlertIcon } from "lucide-react";

import { apiRequest, type Payment, type StripePrice } from "@/lib/api";
import { formatMoney } from "@/lib/format";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";

/**
 * Create a Payment Link or PaymentIntent for one product's prices.
 *
 * Price options show the product name, amount, and Stripe price ID so the
 * merchant can confirm the exact catalog item.
 */
export function ProductPaymentForm({
  productName,
  prices,
}: {
  productName: string;
  prices: StripePrice[];
}) {
  const [selectedPrice, setSelectedPrice] = useState(prices[0]?.id ?? "");
  const [quantity, setQuantity] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [paymentLink, setPaymentLink] = useState<string | null>(null);
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function createPayment(kind: "payment" | "link") {
    setError(null);
    setNotice(null);
    setPaymentLink(null);
    setClientSecret(null);
    if (!selectedPrice) {
      setError("Select a price first.");
      return;
    }
    setBusy(true);
    try {
      const result = await apiRequest<Payment>(`/api/v1/${kind === "link" ? "payment-links" : "payments"}`, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ price_id: selectedPrice, quantity }),
      });
      setNotice(kind === "link" ? "Payment Link created." : "PaymentIntent created.");
      setPaymentLink(kind === "link" ? (result.url ?? null) : null);
      setClientSecret(kind === "payment" ? (result.client_secret ?? null) : null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The payment request failed.");
    } finally {
      setBusy(false);
    }
  }

  if (prices.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No active one-time prices for this product. Add one in Stripe, then reload.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {error ? (
        <Alert variant="destructive">
          <TriangleAlertIcon />
          <AlertTitle>Payment failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      {notice ? (
        <Alert variant="info">
          <InfoIcon />
          <AlertTitle>{notice}</AlertTitle>
          {paymentLink ? (
            <AlertDescription>
              <a href={paymentLink} target="_blank" rel="noreferrer">
                Open Stripe checkout
              </a>
            </AlertDescription>
          ) : (
            <AlertDescription>Create another link or PaymentIntent below.</AlertDescription>
          )}
        </Alert>
      ) : null}
      <form
        className="grid gap-3 sm:grid-cols-[1fr_110px]"
        onSubmit={(event) => {
          event.preventDefault();
          void createPayment("link");
        }}
      >
        <Field>
          <FieldLabel htmlFor="product-price">Price</FieldLabel>
          <Select value={selectedPrice} onValueChange={(value) => setSelectedPrice(value ?? "")}>
            <SelectTrigger id="product-price" className="w-full">
              <SelectValue placeholder="Select a price" />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectLabel>{productName}</SelectLabel>
                {prices.map((price) => (
                  <SelectItem key={price.id} value={price.id}>
                    {formatMoney(price.unit_amount, price.currency)} · {price.id}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </Field>
        <Field>
          <FieldLabel htmlFor="product-quantity">Qty</FieldLabel>
          <Input
            id="product-quantity"
            type="number"
            min="1"
            value={quantity}
            onChange={(event) => setQuantity(Math.max(1, Number(event.target.value) || 1))}
          />
        </Field>
        <div className="flex flex-wrap gap-2 sm:col-span-2">
          <Button type="submit" disabled={busy || !selectedPrice}>
            {busy ? <Spinner data-icon="inline-start" /> : null}
            Create Payment Link
          </Button>
          <Button
            type="button"
            variant="outline"
            disabled={busy || !selectedPrice}
            onClick={() => void createPayment("payment")}
          >
            Create PaymentIntent
          </Button>
        </div>
      </form>
      {clientSecret ? (
        <div className="border-t border-border pt-3">
          <p className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
            PaymentIntent client secret
          </p>
          <code className="block overflow-auto rounded-md border border-border bg-muted p-3 font-mono text-xs break-all">
            {clientSecret}
          </code>
        </div>
      ) : null}
    </div>
  );
}
