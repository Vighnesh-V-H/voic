import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type { Identity, Payment, PaymentEvent, StripeConnection, StripePrice, StripeProduct } from "@/lib/api";

function backendUrl() {
  return process.env.BACKEND_URL ?? "http://localhost:8000";
}

async function backendFetch<T>(path: string, cookieHeader: string): Promise<T> {
  const response = await fetch(`${backendUrl()}${path}`, {
    headers: { cookie: cookieHeader },
    cache: "no-store",
  });
  if (response.status === 401) redirect("/auth/login");
  if (!response.ok) throw new Error(`Request failed: ${path}`);
  return response.json() as Promise<T>;
}

/**
 * Load identity plus Stripe data in parallel.
 *
 * Catalog calls are optional: when Stripe is not connected the backend
 * returns 409, which maps to empty lists so the dashboard still renders
 * real payment metrics.
 */
export async function loadDashboardData() {
  const cookieHeader = (await cookies()).toString();
  const identityPromise = backendFetch<Identity>("/api/v1/auth/me", cookieHeader);
  const paymentsPromise = backendFetch<Payment[]>("/api/v1/payments", cookieHeader).catch(() => [] as Payment[]);
  const connectionPromise = backendFetch<StripeConnection>("/api/v1/stripe/connection", cookieHeader).catch(
    () => ({ provider: "stripe", connected: false, status: "disconnected" }) as StripeConnection,
  );

  const [identity, payments, connection] = await Promise.all([identityPromise, paymentsPromise, connectionPromise]);

  let products: StripeProduct[] = [];
  let prices: StripePrice[] = [];
  let events: PaymentEvent[] = [];
  if (connection.connected) {
    const [nextProducts, nextPrices, nextEvents] = await Promise.all([
      backendFetch<StripeProduct[]>("/api/v1/stripe/products", cookieHeader).catch(() => [] as StripeProduct[]),
      backendFetch<StripePrice[]>("/api/v1/stripe/prices", cookieHeader).catch(() => [] as StripePrice[]),
      backendFetch<PaymentEvent[]>("/api/v1/webhooks/payment-events", cookieHeader).catch(
        () => [] as PaymentEvent[],
      ),
    ]);
    products = nextProducts;
    prices = nextPrices;
    events = nextEvents;
  }

  return { identity, payments, connection, products, prices, events };
}

export async function loadStripeCatalog() {
  const cookieHeader = (await cookies()).toString();
  const connection = await backendFetch<StripeConnection>("/api/v1/stripe/connection", cookieHeader).catch(
    () => ({ provider: "stripe", connected: false, status: "disconnected" }) as StripeConnection,
  );
  if (!connection.connected) {
    return { connection, products: [] as StripeProduct[], prices: [] as StripePrice[], payments: [] as Payment[], events: [] as PaymentEvent[] };
  }
  const [products, prices, payments, events] = await Promise.all([
    backendFetch<StripeProduct[]>("/api/v1/stripe/products", cookieHeader).catch(() => [] as StripeProduct[]),
    backendFetch<StripePrice[]>("/api/v1/stripe/prices", cookieHeader).catch(() => [] as StripePrice[]),
    backendFetch<Payment[]>("/api/v1/payments", cookieHeader).catch(() => [] as Payment[]),
    backendFetch<PaymentEvent[]>("/api/v1/webhooks/payment-events", cookieHeader).catch(
      () => [] as PaymentEvent[],
    ),
  ]);
  return { connection, products, prices, payments, events };
}
