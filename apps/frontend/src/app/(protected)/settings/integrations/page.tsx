import Link from "next/link";

import { StripeIntegration } from "@/components/stripe-integration";

export default function IntegrationsPage() {
  return (
    <main className="dashboard-page shell">
      <header className="site-header">
        <Link className="wordmark" href="/">
          voic<span>.</span>
        </Link>
        <Link className="text-link" href="/dashboard">
          Back to dashboard
        </Link>
      </header>
      <section className="dashboard-main">
        <StripeIntegration />
      </section>
    </main>
  );
}
