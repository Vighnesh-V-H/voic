import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";

import { Identity } from "@/lib/api";
import { StripeIntegration } from "@/components/stripe-integration";

async function getIdentity(): Promise<Identity> {
  const cookieHeader = (await cookies()).toString();
  const response = await fetch(
    `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/v1/auth/me`,
    { headers: { cookie: cookieHeader }, cache: "no-store" },
  );

  if (response.status === 401) {
    redirect("/auth/login");
  }

  if (!response.ok) {
    throw new Error("The backend could not verify this session.");
  }

  return response.json() as Promise<Identity>;
}

export default async function DashboardPage() {
  const identity = await getIdentity();

  return (
    <main className="dashboard-page shell">
      <header className="site-header">
        <Link className="wordmark" href="/">voic<span>.</span></Link>
        <span className="status">Authenticated</span>
      </header>
      <section className="dashboard-main">
        <div className="dashboard-heading">
          <div>
            <p className="eyebrow">Merchant account</p>
            <h1>{identity.merchant.name}</h1>
          </div>
          <p>{identity.user.email}</p>
        </div>
        <div className="dashboard-grid">
          <article className="dashboard-card">
            <h2>Identity</h2>
            <span className="status">Session verified by the backend</span>
            <p className="identity-value">{identity.user.email}</p>
          </article>
          <article className="dashboard-card">
            <h2>Merchant boundary</h2>
            <span className="status">Ready for integrations</span>
            <p className="identity-value">{identity.merchant.name}</p>
          </article>
        </div>
        <StripeIntegration />
      </section>
    </main>
  );
}
