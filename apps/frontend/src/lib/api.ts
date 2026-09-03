export type Identity = {
  user: {
    id: string;
    email: string;
  };
  merchant: {
    id: string;
    name: string;
  };
};

export type StripeConnection = {
  provider: "stripe";
  connected: boolean;
  provider_account_id?: string | null;
  scope?: string | null;
  mode?: string | null;
  status: string;
};

export type StripeProduct = {
  id: string;
  name: string;
  description?: string | null;
  active: boolean;
  default_price?: string | null;
};

export type StripePrice = {
  id: string;
  product_id?: string | null;
  unit_amount?: number | null;
  currency?: string | null;
  active?: boolean | null;
  type?: string | null;
};

export type Payment = {
  id: string;
  provider_payment_id?: string | null;
  provider_payment_link_id?: string | null;
  provider_price_id: string;
  amount: number;
  currency: string;
  status: string;
  client_secret?: string | null;
  url?: string | null;
};

export type PaymentEvent = {
  id: string;
  provider_event_id: string;
  event_type: string;
  provider_payment_id?: string | null;
  amount?: number | null;
  currency?: string | null;
  occurred_at: string;
};

export function apiBaseUrl() {
  if (typeof window === "undefined") {
    return process.env.BACKEND_URL ?? "http://localhost:8000";
  }

  return process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  const body = (await response.json().catch(() => null)) as { detail?: string } | T | null;
  if (!response.ok) {
    const detail = body && typeof body === "object" && "detail" in body ? body.detail : undefined;
    throw new Error(detail ?? "The request could not be completed.");
  }

  return body as T;
}
