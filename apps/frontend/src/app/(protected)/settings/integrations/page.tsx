import { Reveal } from "@/components/reveal";
import { StripeIntegration } from "@/components/stripe-integration";

/**
 * Integrations settings page for managing provider connections.
 *
 * @returns A page displaying the Stripe integration interface.
 */
export default function IntegrationsPage() {
  return (
    <section className="flex flex-col gap-4 py-2">
      <Reveal>
        <div>
          <p className="mb-5 text-xs font-semibold tracking-[0.14em] text-muted-foreground uppercase">
            Settings
          </p>
          <h1 className="font-editorial text-4xl text-balance sm:text-5xl">
            Integrations
          </h1>
          <p className="mt-3 max-w-xl leading-relaxed text-muted-foreground">
            Manage the provider connections for this merchant.
          </p>
        </div>
      </Reveal>
      <StripeIntegration />
    </section>
  );
}
