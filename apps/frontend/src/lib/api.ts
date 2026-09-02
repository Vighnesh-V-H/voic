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

function apiBaseUrl() {
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
