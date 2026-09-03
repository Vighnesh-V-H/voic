import Link from "next/link";

import { PayPalPaymentForm } from "@/components/paypal-payment-form";

export default function PayPalPaymentPage() {
  return (
    <main className="dashboard-page shell">
      <header className="site-header">
        <Link className="wordmark" href="/">voic<span>.</span></Link>
        <Link className="text-link" href="/settings/integrations">Back to integrations</Link>
      </header>
      <section className="integration-main">
        <div className="integration-heading">
          <p className="eyebrow">Development payment</p>
          <h1>Test the flow.</h1>
          <p className="hero-copy">This page creates and captures a PayPal Sandbox order. It is not a production checkout.</p>
        </div>
        <PayPalPaymentForm />
      </section>
    </main>
  );
}
