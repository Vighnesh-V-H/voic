import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { PayPalConnectButton } from "@/components/paypal-connect-button";

type ConnectionStatus = {
  provider: string;
  connected: boolean;
};

async function getPayPalStatus(): Promise<ConnectionStatus> {
  const cookieHeader = (await cookies()).toString();
  const response = await fetch(
    `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/v1/integrations/paypal/status`,
    { headers: { cookie: cookieHeader }, cache: "no-store" },
  );

  if (response.status === 401) {
    redirect("/auth/login");
  }
  if (!response.ok) {
    throw new Error("The backend could not load PayPal status.");
  }
  return response.json() as Promise<ConnectionStatus>;
}

export default async function IntegrationsPage() {
  const connection = await getPayPalStatus();

  return (
    <main className="dashboard-page shell">
      <header className="site-header">
        <Link className="wordmark" href="/">voic<span>.</span></Link>
        <Link className="text-link" href="/dashboard">Back to dashboard</Link>
      </header>
      <section className="integration-main">
        <div className="integration-heading">
          <p className="eyebrow">Development connection</p>
          <h1>PayPal Sandbox.</h1>
          <p className="hero-copy">
            Connect the PayPal REST app used for development payments. Credentials stay on the Voic backend.
          </p>
        </div>
        <article className="integration-card">
          <div>
            <p className="eyebrow">Payment provider</p>
            <h2>PayPal</h2>
            <p className="integration-description">
              Voic uses the standard Sandbox client-credentials flow and PayPal Orders API for this test environment.
            </p>
          </div>
          <div className="integration-action">
            <span className={connection.connected ? "status" : "status status-disconnected"}>
              {connection.connected ? "Connected" : "Not connected"}
            </span>
            {!connection.connected && <PayPalConnectButton />}
          </div>
        </article>
        {connection.connected && (
          <Link className="button button-secondary integration-payment-link" href="/payments/paypal">
            Open payment tester
          </Link>
        )}
      </section>
    </main>
  );
}
