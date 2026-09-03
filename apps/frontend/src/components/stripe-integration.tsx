"use client";

import { useEffect, useState, useTransition } from "react";

import {
  apiBaseUrl,
  apiRequest,
  Payment,
  PaymentEvent,
  StripeConnection,
  StripePrice,
  StripeProduct,
} from "@/lib/api";

function formatMoney(amount: number | null | undefined, currency: string | null | undefined) {
  if (amount === null || amount === undefined || !currency) return "Amount unavailable";
  return new Intl.NumberFormat(undefined, { style: "currency", currency: currency.toUpperCase() }).format(amount / 100);
}

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

  function connectStripe() {
    window.open(`${apiBaseUrl()}/api/v1/stripe/connect`, "_self");
  }

  async function disconnectStripe() {
    setError(null);
    setNotice(null);
    try {
      await apiRequest<void>("/api/v1/stripe/connection", { method: "DELETE" });
      setNotice("Stripe has been disconnected. Historical payments remain available.");
      await loadIntegration();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Stripe could not be disconnected.");
    }
  }

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

  if (isLoading) return <p className="loading-copy">Loading Stripe connection...</p>;

  return (
    <div className="integration-stack">
      {error && <p className="form-error" role="alert">{error}</p>}
      {notice && <p className="form-notice" role="status">{notice}</p>}
      <section className="integration-hero">
        <div>
          <p className="eyebrow">Provider connection</p>
          <h2>Stripe, connected to your signal.</h2>
          <p className="hero-copy">Stripe owns your catalog. Voic owns the payment trail that helps you act on it.</p>
        </div>
        <div className="connection-actions">
          {connection?.connected ? (
            <button className="button button-secondary" type="button" onClick={disconnectStripe} disabled={isPending}>
              Disconnect Stripe
            </button>
          ) : (
            <button className="button button-primary" type="button" onClick={connectStripe}>
              Connect Stripe
            </button>
          )}
          <span className={connection?.connected ? "status" : "status status-muted"}>
            {connection?.connected ? "Connected" : "Not connected"}
          </span>
        </div>
      </section>

      {connection?.connected ? (
        <>
          <section className="dashboard-grid integration-grid">
            <article className="dashboard-card">
              <p className="card-kicker">Connected account</p>
              <h3>{connection.provider_account_id}</h3>
              <p className="muted-copy">{connection.mode} mode · {connection.scope}</p>
            </article>
            <article className="dashboard-card">
              <p className="card-kicker">Catalog</p>
              <h3>{products.length} products</h3>
              <p className="muted-copy">{prices.length} active one-time prices read from Stripe.</p>
              {products.length > 0 && <ul className="catalog-list">{products.slice(0, 4).map((product) => <li key={product.id}><strong>{product.name}</strong><span>{product.description || product.id}</span></li>)}</ul>}
            </article>
          </section>

          <section className="dashboard-card payment-builder">
            <div>
              <p className="card-kicker">Create from Stripe catalog</p>
              <h3>Choose a price, then let Stripe collect.</h3>
            </div>
            <form className="payment-form" onSubmit={(event) => { event.preventDefault(); void createPayment("link"); }}>
              <div className="field">
                <label htmlFor="stripe-price">One-time price</label>
                <select id="stripe-price" value={selectedPrice} onChange={(event) => setSelectedPrice(event.target.value)} required>
                  <option value="" disabled>Select a Stripe price</option>
                  {prices.map((price) => (
                    <option key={price.id} value={price.id}>
                      {formatMoney(price.unit_amount, price.currency)} · {price.id}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field quantity-field">
                <label htmlFor="stripe-quantity">Quantity</label>
                <input id="stripe-quantity" type="number" min="1" value={quantity} onChange={(event) => setQuantity(Number(event.target.value))} />
              </div>
              <div className="payment-actions">
                <button className="button button-primary" type="submit" disabled={!selectedPrice || isPending || isCreating}>Create Payment Link</button>
                <button className="button button-secondary" type="button" disabled={!selectedPrice || isPending || isCreating} onClick={() => void createPayment("payment")}>Create PaymentIntent</button>
              </div>
            </form>
            {lastPaymentLink && <p className="form-notice">Payment Link ready: <a className="text-link" href={lastPaymentLink} target="_blank" rel="noreferrer">Open Stripe checkout</a></p>}
            {clientSecret && <div className="client-secret"><p className="card-kicker">PaymentIntent client secret</p><code>{clientSecret}</code><p className="muted-copy">Use this with Stripe.js to confirm the PaymentIntent in a customer checkout.</p></div>}
          </section>

          <section className="dashboard-grid integration-grid">
            <article className="dashboard-card">
              <div className="card-heading"><p className="card-kicker">Recent payments</p><span className="status">Voic-owned</span></div>
              {payments.length === 0 ? <p className="muted-copy">No payments created yet.</p> : <ul className="event-list">{payments.slice(0, 5).map((payment) => <li key={payment.id}><strong>{formatMoney(payment.amount, payment.currency)}</strong><span>{payment.status} · {payment.provider_payment_link_id ? <>{payment.url ? <a className="text-link" href={payment.url} target="_blank" rel="noreferrer">Payment Link</a> : "Payment Link"}</> : "PaymentIntent"}</span></li>)}</ul>}
            </article>
            <article className="dashboard-card">
              <div className="card-heading"><p className="card-kicker">Recent events</p><span className="status">Verified</span></div>
              {events.length === 0 ? <p className="muted-copy">No webhook events received yet.</p> : <ul className="event-list">{events.slice(0, 5).map((event) => <li key={event.id}><strong>{event.event_type}</strong><span>{event.provider_payment_id ?? "Account event"}</span></li>)}</ul>}
            </article>
          </section>
        </>
      ) : (
        <section className="dashboard-card empty-state"><p className="card-kicker">Next step</p><h3>Connect an existing Stripe account.</h3><p className="muted-copy">Your products, Payment Links, and verified payment events will appear here after authorization.</p></section>
      )}
    </div>
  );
}
