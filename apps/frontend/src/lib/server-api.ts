
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import type {
  Identity,
  Payment,
  PaymentEvent,
  StripeConnection,
  StripePrice,
  StripeProduct,
} from "@/lib/api";

function backendUrl() {
  return process.env.BACKEND_URL ?? "http://localhost:8000";
}

async function backendFetch<T>(path: string, cookieHeader: string): Promise<T> {
  const response = await fetch(`${backendUrl()}${path}`, {
    headers: { cookie: cookieHeader },
    cache: "no-store",
  });

  if (response.status === 401) {
    redirect("/auth/login");
  }

  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }

  return response.json() as Promise<T>;
}

const disconnectedStripe: StripeConnection = {
  provider: "stripe",
  connected: false,
  status: "disconnected",
};

export async function loadDashboardData() {
  const cookieHeader = (await cookies()).toString();

  const [identity, payments, connection] = await Promise.all([
    backendFetch<Identity>("/api/v1/auth/me", cookieHeader),

    // Do not convert payment API failures into an empty array.
    backendFetch<Payment[]>("/api/v1/payments", cookieHeader),

    // A connection lookup failure is different from a real disconnected state.
    backendFetch<StripeConnection>("/api/v1/stripe/connection", cookieHeader),
  ]);

  let products: StripeProduct[] = [];
  let prices: StripePrice[] = [];
  let events: PaymentEvent[] = [];

  if (connection.connected) {
    [products, prices, events] = await Promise.all([
      backendFetch<StripeProduct[]>("/api/v1/stripe/products", cookieHeader),
      backendFetch<StripePrice[]>("/api/v1/stripe/prices", cookieHeader),
      backendFetch<PaymentEvent[]>("/api/v1/webhooks/payment-events", cookieHeader),
    ]);
  }

  return {
    identity,
    payments,
    connection,
    products,
    prices,
    events,
  };
}

export async function loadStripeCatalog() {
  const cookieHeader = (await cookies()).toString();

  const connection = await backendFetch<StripeConnection>(
    "/api/v1/stripe/connection",
    cookieHeader,
  );

  if (!connection.connected) {
    return {
      connection,
      products: [] as StripeProduct[],
      prices: [] as StripePrice[],
      payments: [] as Payment[],
      events: [] as PaymentEvent[],
    };
  }

  const [products, prices, payments, events] = await Promise.all([
    backendFetch<StripeProduct[]>("/api/v1/stripe/products", cookieHeader),
    backendFetch<StripePrice[]>("/api/v1/stripe/prices", cookieHeader),
    backendFetch<Payment[]>("/api/v1/payments", cookieHeader),
    backendFetch<PaymentEvent[]>("/api/v1/webhooks/payment-events", cookieHeader),
  ]);

  return {
    connection,
    products,
    prices,
    payments,
    events,
  };
}
