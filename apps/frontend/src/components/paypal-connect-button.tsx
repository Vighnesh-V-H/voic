"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { apiRequest } from "@/lib/api";

export function PayPalConnectButton() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [isConnecting, setIsConnecting] = useState(false);

  async function connect() {
    setError(null);
    setIsConnecting(true);
    try {
      await apiRequest("/api/v1/integrations/paypal/connect", { method: "POST" });
      router.refresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "PayPal could not be connected.");
    } finally {
      setIsConnecting(false);
    }
  }

  return (
    <div className="integration-button-stack">
      <button className="button button-primary" type="button" onClick={connect} disabled={isConnecting}>
        {isConnecting ? "Connecting..." : "Connect PayPal Sandbox"}
      </button>
      {error && <p className="form-error" role="alert">{error}</p>}
    </div>
  );
}
