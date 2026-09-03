"use client";

import { useEffect, useState, useTransition } from "react";

import {
  InfoIcon,
  PlugZapIcon,
  TriangleAlertIcon,
  UnplugIcon,
} from "lucide-react";

import {
  apiBaseUrl,
  apiRequest,
  Payment,
  PaymentEvent,
  StripeConnection,
  StripePrice,
  StripeProduct,
} from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";

/**
 * Format a money amount in the smallest currency unit (e.g., cents) to a localized currency string.
 *
 * @param amount - The amount in cents (or smallest unit).
 * @param currency - The three-letter ISO currency code.
 * @returns A formatted currency string or "Amount unavailable" if inputs are invalid.
 */
function formatMoney(amount: number | null | undefined, currency: string | null | undefined) {
  if (amount === null || amount === undefined || !currency) return "Amount unavailable";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: currency.toUpperCase() }).format(amount / 100);
}

/**
 * Stripe integration component for managing connections, products, prices, and payments.
 *
 * @returns A comprehensive UI for Stripe connection and payment operations.
 */
export function StripeIntegration() {
  const [connection, setConnection] = useState<StripeConnection | null>(null);
  const [products, setProducts] = useState<StripeProduct[]>([]);
  const [prices, setPrices] = useState<StripePrice[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [events, setEvents] = useState<PaymentEvent[]>([]);
  const [selectedPrice, setSelectedPrice] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return new URLSearchParams(window.location.search).get("stripe") === "connected"
      ? "Stripe connected. Showing current connection status."
      : null;
  });
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [lastPaymentLink, setLastPaymentLink] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [isPending, startTransition] = useTransition();

  /**
   * Load Stripe connection, products, prices, payments, and events from the API.
   */
  async function loadIntegration() {
    setIsLoading(true);
    setError(null);
    try {
      const nextConnection = await apiRequest<StripeConnection>("/api/v1/stripe/connection");
      setConnection(nextConnection);
      if (!nextConnection.connected) {
        setProducts([]);
        setPrices([]);
        setPayments([]);
        setEvents([]);
        return;
      }
      const [nextProducts, nextPrices, nextPayments, nextEvents] = await Promise.all([
        apiRequest<StripeProduct[]>("/api/v1/stripe/products"),
        apiRequest<StripePrice[]>("/api/v1/stripe/prices"),
        apiRequest<Payment[]>("/api/v1/payments"),
        apiRequest<PaymentEvent[]>("/api/v1/webhooks/payment-events"),
      ]);
      setProducts(nextProducts);
      setPrices(nextPrices);
      setPayments(nextPayments);
      setEvents(nextEvents);
      setSelectedPrice((current) => current || nextPrices[0]?.id || "");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The Stripe data could not be loaded.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("stripe") === "connected") {
      params.delete("stripe");
      const nextSearch = params.toString();
      window.history.replaceState(null, "", `${window.location.pathname}${nextSearch ? `?${nextSearch}` : ""}`);
    }
    const loadTask = window.setTimeout(() => void loadIntegration(), 0);
    return () => window.clearTimeout(loadTask);
  }, []);

  /**
   * Redirect the user to the Stripe OAuth authorization page.
   */
  function connectStripe() {
    window.open(`${apiBaseUrl()}/api/v1/stripe/connect`, "_self");
  }

  /**
   * Disconnect the merchant's Stripe account and reload integration data.
   */
  async function disconnectStripe() {
    setError(null);
    setNotice(null);
    if (
      !window.confirm(
        "Disconnecting Stripe will permanently remove all Stripe connections, payments, and webhook events from Voic. You will stay logged in. Continue?",
      )
    ) {
      return;
    }
    try {
      await apiRequest<void>("/api/v1/stripe/connection", { method: "DELETE" });
      setNotice("Stripe has been disconnected and all Stripe data has been removed from Voic.");
      await loadIntegration();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Stripe could not be disconnected.");
    }
  }

  /**
   * Create a PaymentIntent or Payment Link using the selected price and quantity.
   *
   * @param kind - The type of payment to create: "payment" for PaymentIntent or "link" for Payment Link.
   */
  async function createPayment(kind: "payment" | "link") {
    setError(null);
    setNotice(null);
    setIsCreating(true);
    try {
      const result = await apiRequest<Payment>(`/api/v1/${kind === "link" ? "payment-links" : "payments"}`, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({ price_id: selectedPrice, quantity }),
      });
      setNotice(kind === "link" ? "Payment Link created." : "PaymentIntent created.");
      setClientSecret(kind === "payment" ? result.client_secret ?? null : null);
      setLastPaymentLink(kind === "link" ? result.url ?? null : null);
      startTransition(() => {
        void loadIntegration();
      });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The payment request failed.");
    } finally {
      setIsCreating(false);
    }
  }

  if (isLoading) {
    return (
      <div className="flex flex-col gap-4" aria-label="Loading Stripe connection">
        <Skeleton className="h-44" />
        <div className="grid gap-4 sm:grid-cols-2">
          <Skeleton className="h-36" />
          <Skeleton className="h-36" />
        </div>
        <Skeleton className="h-56" />
      </div>
    );
  }

  const isConnected = connection?.connected === true;
  const controlsDisabled = !selectedPrice || isPending || isCreating;

  return (
    <div className="flex flex-col gap-4">
      {error ? (
        <Alert variant="destructive">
          <TriangleAlertIcon />
          <AlertTitle>Stripe request failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      {notice ? (
        <Alert>
          <InfoIcon />
          <AlertTitle>Stripe update</AlertTitle>
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      ) : null}

      <Card className="border-transparent bg-foreground text-background">
        <CardContent className="flex flex-col gap-7 p-6 sm:p-8 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="mb-4 text-xs font-extrabold tracking-[0.14em] text-background/60 uppercase">
              Provider connection
            </p>
            <h2 className="mb-3 max-w-xl text-3xl font-extrabold tracking-tight text-balance sm:text-4xl">
              Stripe, connected to your signal.
            </h2>
            <p className="max-w-xl leading-relaxed text-background/70">
              Stripe owns your catalog. Voic owns the payment trail that helps
              you act on it.
            </p>
          </div>
          <div className="flex shrink-0 flex-col gap-3.5 lg:items-end">
            {isConnected ? (
              <Button variant="secondary" type="button" onClick={disconnectStripe} disabled={isPending}>
                <UnplugIcon data-icon="inline-start" />
                Disconnect Stripe
              </Button>
            ) : (
              <Button type="button" onClick={connectStripe}>
                <PlugZapIcon data-icon="inline-start" />
                Connect Stripe
              </Button>
            )}
            <Badge variant={isConnected ? "secondary" : "default"}>
              <span className="size-1.5 rounded-full bg-chart-2" />
              {isConnected ? "Connected" : "Not connected"}
            </Badge>
          </div>
        </CardContent>
      </Card>

      {isConnected ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader>
                <CardDescription>Connected account</CardDescription>
                <CardTitle className="truncate text-2xl" title={connection?.provider_account_id ?? undefined}>
                  {connection?.provider_account_id}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {connection?.mode} mode · {connection?.scope}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardDescription>Catalog</CardDescription>
                <CardTitle className="text-2xl">
                  {products.length} {products.length === 1 ? "product" : "products"}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground">
                  {prices.length} active one-time {prices.length === 1 ? "price" : "prices"} read from Stripe.
                </p>
                {products.length > 0 ? (
                  <ul className="mt-4 flex flex-col divide-y divide-border">
                    {products.slice(0, 4).map((product) => (
                      <li key={product.id} className="flex flex-col gap-0.5 py-2.5 first:pt-0 last:pb-0">
                        <span className="font-semibold">{product.name}</span>
                        <span className="truncate text-sm text-muted-foreground">
                          {product.description || product.id}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardDescription>Create from Stripe catalog</CardDescription>
              <CardTitle>Choose a price, then let Stripe collect.</CardTitle>
            </CardHeader>
            <CardContent>
              {prices.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No active one-time prices were found in the connected Stripe
                  account. Add a product with a one-time price in Stripe, then
                  reload this view.
                </p>
              ) : (
                <form
                  className="grid gap-3.5 sm:grid-cols-[1fr_100px]"
                  onSubmit={(event) => {
                    event.preventDefault();
                    void createPayment("link");
                  }}
                >
                  <Field>
                    <FieldLabel htmlFor="stripe-price">One-time price</FieldLabel>
                    <Select value={selectedPrice} onValueChange={(value) => setSelectedPrice(value ?? "")}>
                      <SelectTrigger id="stripe-price" className="w-full">
                        <SelectValue placeholder="Select a Stripe price" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectGroup>
                          <SelectLabel>One-time prices</SelectLabel>
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
                    <FieldLabel htmlFor="stripe-quantity">Quantity</FieldLabel>
                    <Input
                      id="stripe-quantity"
                      type="number"
                      min="1"
                      value={quantity}
                      onChange={(event) => setQuantity(Number(event.target.value))}
                    />
                  </Field>
                  <div className="flex flex-wrap gap-2.5 sm:col-span-2">
                    <Button type="submit" disabled={controlsDisabled}>
                      {isCreating ? <Spinner data-icon="inline-start" /> : null}
                      Create Payment Link
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      disabled={controlsDisabled}
                      onClick={() => void createPayment("payment")}
                    >
                      Create PaymentIntent
                    </Button>
                  </div>
                </form>
              )}
              {lastPaymentLink ? (
                <Alert className="mt-4">
                  <InfoIcon />
                  <AlertTitle>Payment Link ready</AlertTitle>
                  <AlertDescription>
                    <a href={lastPaymentLink} target="_blank" rel="noreferrer">
                      Open Stripe checkout
                    </a>
                  </AlertDescription>
                </Alert>
              ) : null}
              {clientSecret ? (
                <div className="mt-5 border-t border-border pt-4">
                  <p className="mb-2 text-xs font-extrabold tracking-[0.13em] text-primary uppercase">
                    PaymentIntent client secret
                  </p>
                  <code className="block overflow-auto rounded-md bg-muted p-3 font-mono text-xs break-all">
                    {clientSecret}
                  </code>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Use this with Stripe.js to confirm the PaymentIntent in a
                    customer checkout.
                  </p>
                </div>
              ) : null}
            </CardContent>
          </Card>

          <div className="grid gap-4 sm:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Recent payments</CardTitle>
                <CardAction>
                  <Badge variant="secondary">Voic-owned</Badge>
                </CardAction>
              </CardHeader>
              <CardContent>
                {payments.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No payments created yet.</p>
                ) : (
                  <ul className="flex flex-col divide-y divide-border">
                    {payments.slice(0, 5).map((payment) => (
                      <li key={payment.id} className="flex items-center justify-between gap-3.5 py-3.5 first:pt-0 last:pb-0">
                        <span className="font-semibold">
                          {formatMoney(payment.amount, payment.currency)}
                        </span>
                        <span className="flex items-center gap-2 text-right text-sm text-muted-foreground">
                          <Badge variant="outline">{payment.status}</Badge>
                          {payment.provider_payment_link_id ? (
                            payment.url ? (
                              <a
                                className="font-medium text-primary underline-offset-4 hover:underline"
                                href={payment.url}
                                target="_blank"
                                rel="noreferrer"
                              >
                                Payment Link
                              </a>
                            ) : (
                              "Payment Link"
                            )
                          ) : (
                            "PaymentIntent"
                          )}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Recent events</CardTitle>
                <CardAction>
                  <Badge variant="secondary">Verified</Badge>
                </CardAction>
              </CardHeader>
              <CardContent>
                {events.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No webhook events received yet.</p>
                ) : (
                  <ul className="flex flex-col divide-y divide-border">
                    {events.slice(0, 5).map((event) => (
                      <li key={event.id} className="flex items-center justify-between gap-3.5 py-3.5 first:pt-0 last:pb-0">
                        <span className="font-semibold">{event.event_type}</span>
                        <span className="truncate text-right text-sm text-muted-foreground">
                          {event.provider_payment_id ?? "Account event"}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>
        </>
      ) : (
        <Card>
          <CardHeader>
            <CardDescription>Next step</CardDescription>
            <CardTitle className="text-2xl">Connect an existing Stripe account.</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground">
              Your products, Payment Links, and verified payment events will
              appear here after authorization.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
