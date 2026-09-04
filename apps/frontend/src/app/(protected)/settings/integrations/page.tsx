import Link from "next/link";

import { ArrowUpRightIcon, CreditCardIcon, PlugZapIcon } from "lucide-react";

import { AppBreadcrumbs } from "@/components/app-breadcrumbs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { loadStripeCatalog } from "@/lib/server-api";

/**
 * Integrations index: every provider in one place.
 *
 * Stripe is live. Razorpay is reserved as coming soon so the grid already
 * communicates where the next provider will land.
 */
export default async function IntegrationsPage() {
  const { connection } = await loadStripeCatalog();
  const stripeConnected = connection.connected === true;

  return (
    <section className="flex flex-col py-2">
      <AppBreadcrumbs items={[{ label: "Integrations" }]} />
      <div className="mb-6">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Integrations</h1>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-muted-foreground">
          Connect a payment provider to sync its catalog and track payments in Voic.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardDescription>Payment provider</CardDescription>
            <CardTitle className="flex items-center justify-between gap-2">
              Stripe
              <Badge variant={stripeConnected ? "success" : "secondary"}>
                {stripeConnected ? "Connected" : "Available"}
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              {stripeConnected && connection.provider_account_id ? (
                <>
                  Connected as <code className="font-mono text-xs">{connection.provider_account_id}</code> ·{" "}
                  {connection.mode ?? "test"} mode.
                </>
              ) : (
                "Sync products and prices, create Payment Links, and receive verified webhooks."
              )}
            </p>
            <div>
              <Button
                nativeButton={false}
                render={
                  <Link href="/settings/integrations/stripe">
                    {stripeConnected ? "Manage" : "View"}
                    <ArrowUpRightIcon data-icon="inline-end" />
                  </Link>
                }
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardDescription>Payment provider</CardDescription>
            <CardTitle className="flex items-center justify-between gap-2">
              Razorpay
              <Badge variant="secondary">Coming soon</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              Razorpay support is planned. The connection flow will appear here when it ships.
            </p>
            <div>
              <Button variant="outline" type="button" disabled>
                <PlugZapIcon data-icon="inline-start" />
                Notify me
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {!stripeConnected ? (
        <Empty className="mt-4">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <CreditCardIcon />
            </EmptyMedia>
            <EmptyTitle>No provider connected</EmptyTitle>
            <EmptyDescription>Connect Stripe to start syncing products and payments.</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : null}
    </section>
  );
}
