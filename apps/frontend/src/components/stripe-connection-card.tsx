"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PlugZapIcon, UnplugIcon } from "lucide-react";

import { apiBaseUrl, apiRequest, type StripeConnection } from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Concise Stripe connection status with connect / disconnect actions.
 *
 * Copy stays factual: account ID, mode, and scope. No marketing language.
 */
export function StripeConnectionCard({ connection }: { connection: StripeConnection }) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isConnected = connection.connected === true;

  function connectStripe() {
    window.open(`${apiBaseUrl()}/api/v1/stripe/connect`, "_self");
  }

  async function disconnectStripe() {
    setError(null);
    if (
      !window.confirm(
        "Disconnect Stripe? Voic will delete its Stripe connections, payments, and events. You stay signed in.",
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      await apiRequest<void>("/api/v1/stripe/connection", { method: "DELETE" });
      router.refresh();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Stripe could not be disconnected.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardDescription>Stripe connection</CardDescription>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <Badge variant={isConnected ? "success" : "secondary"}>
            {isConnected ? "Connected" : "Not connected"}
          </Badge>
          {isConnected && connection.provider_account_id ? (
            <code className="font-mono text-sm font-normal break-all">{connection.provider_account_id}</code>
          ) : null}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {error ? (
          <Alert variant="destructive">
            <AlertTitle>Disconnect failed</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        ) : null}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">
            {isConnected
              ? `${connection.mode ?? "test"} mode · ${connection.scope ?? "read_write"}`
              : "Connect an existing Stripe account to sync products and collect payments."}
          </p>
          {isConnected ? (
            <Button variant="outline" type="button" onClick={disconnectStripe} disabled={busy}>
              <UnplugIcon data-icon="inline-start" />
              {busy ? "Disconnecting…" : "Disconnect"}
            </Button>
          ) : (
            <Button type="button" onClick={connectStripe}>
              <PlugZapIcon data-icon="inline-start" />
              Connect Stripe
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
