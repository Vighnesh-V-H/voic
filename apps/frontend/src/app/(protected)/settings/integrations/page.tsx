import Link from "next/link";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";

type ConnectionStatus = {
  provider: string;
  connected: boolean;
};

type IntegrationsPageProps = {
  searchParams: Promise<{ status?: string }>;
};

async function getRazorpayStatus(): Promise<ConnectionStatus> {
  const cookieHeader = (await cookies()).toString();
  const response = await fetch(
    `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/v1/integrations/razorpay/status`,
    { headers: { cookie: cookieHeader }, cache: "no-store" },
  );

  if (response.status === 401) {
    redirect("/auth/login");
  }

  if (!response.ok) {
    throw new Error("The backend could not load integration status.");
  }

  return response.json() as Promise<ConnectionStatus>;
}

function callbackMessage(status: string | undefined): string | null {
  switch (status) {
    case "connected":
      return "Razorpay is connected. Voic can now read payment information securely.";
    case "oauth_access_denied":
      return "Razorpay authorization was cancelled. No connection was changed.";
    case "oauth_state_invalid":
      return "That authorization link expired or is no longer valid. Start again to connect Razorpay.";
    case "oauth_exchange_failed":
      return "Razorpay could not complete the connection. Check your setup and try again.";
    case "oauth_session_invalid":
      return "Your session expired. Sign in again before connecting Razorpay.";
    default:
      return null;
  }
}

export default async function IntegrationsPage({ searchParams }: IntegrationsPageProps) {
  const [connection, params] = await Promise.all([getRazorpayStatus(), searchParams]);
  const message = callbackMessage(params.status);
  const browserApiUrl =
    process.env.NEXT_PUBLIC_API_URL ?? process.env.BACKEND_URL ?? "http://localhost:8000";

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
      <section className="integration-main">
        <div className="integration-heading">
          <p className="eyebrow">Connections</p>
          <h1>Payment providers.</h1>
          <p className="hero-copy">
            Connect the payment account that Voic will use to understand payment activity.
          </p>
        </div>
        {message && <p className="integration-message" role="status">{message}</p>}
        <article className="integration-card">
          <div>
            <p className="eyebrow">Payment provider</p>
            <h2>Razorpay</h2>
            <p className="integration-description">
              Read-only access to payment information. Your Razorpay credentials stay on the Voic backend.
            </p>
          </div>
          <div className="integration-action">
            <span className={connection.connected ? "status" : "status status-disconnected"}>
              {connection.connected ? "Connected" : "Not connected"}
            </span>
            {!connection.connected && (
              <a
                className="button button-primary"
                href={`${browserApiUrl}/api/v1/integrations/razorpay/connect`}
              >
                Connect Razorpay
              </a>
            )}
          </div>
        </article>
      </section>
    </main>
  );
}
