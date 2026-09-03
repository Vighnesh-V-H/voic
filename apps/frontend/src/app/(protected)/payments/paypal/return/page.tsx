import Link from "next/link";

import { PayPalCaptureStatus } from "@/components/paypal-capture-status";

type PayPalReturnPageProps = {
  searchParams: Promise<{ token?: string; cancelled?: string }>;
};

export default async function PayPalReturnPage({ searchParams }: PayPalReturnPageProps) {
  const params = await searchParams;
  return (
    <main className="dashboard-page shell">
      <header className="site-header">
        <Link className="wordmark" href="/">voic<span>.</span></Link>
        <Link className="text-link" href="/payments/paypal">Back to payment tester</Link>
      </header>
      <section className="integration-main">
        <div className="integration-heading">
          <p className="eyebrow">PayPal Sandbox</p>
          <h1>Payment result.</h1>
        </div>
        <PayPalCaptureStatus orderId={params.token ?? null} cancelled={params.cancelled === "1"} />
      </section>
    </main>
  );
}
