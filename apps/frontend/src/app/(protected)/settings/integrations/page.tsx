import Link from "next/link";

import { StripeIntegration } from "@/components/stripe-integration";
import { Button } from "@/components/ui/button";
import { SiteHeader } from "@/components/site-header";

/**
 * Integrations settings page for managing provider connections.
 *
 * @returns A page displaying the Stripe integration interface.
 */
export default function IntegrationsPage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 pb-16">
      <SiteHeader>
        <Button variant="link" render={<Link href="/dashboard">Back to dashboard</Link>} />
      </SiteHeader>
      <section className="flex flex-col gap-4 py-10">
        <StripeIntegration />
      </section>
    </main>
  );
}
