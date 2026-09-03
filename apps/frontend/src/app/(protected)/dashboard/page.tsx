import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { Identity } from "@/lib/api";
import { StripeIntegration } from "@/components/stripe-integration";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { SiteHeader } from "@/components/site-header";

/**
 * Fetch the authenticated user's identity from the backend.
 *
 * @returns The user's identity containing user and merchant details.
 * @throws Redirects to login if unauthenticated or throws error if verification fails.
 */
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

/**
 * Dashboard page showing merchant account details and Stripe integration.
 *
 * @returns A server-rendered dashboard page with authenticated merchant information.
 */
export default async function DashboardPage() {
  const identity = await getIdentity();

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 pb-16">
      <SiteHeader>
        <Badge variant="secondary">
          <span className="size-1.5 rounded-full bg-chart-2" />
          Authenticated
        </Badge>
      </SiteHeader>
      <section className="py-10">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-5">
          <div>
            <p className="mb-5 text-xs font-extrabold tracking-[0.14em] text-primary uppercase">
              Merchant account
            </p>
            <h1 className="text-5xl font-extrabold tracking-tighter text-balance sm:text-6xl">
              {identity.merchant.name}
            </h1>
          </div>
          <p className="pb-2 text-muted-foreground">{identity.user.email}</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Identity</CardTitle>
              <CardDescription>Session verified by the backend</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-xl font-bold">{identity.user.email}</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Merchant boundary</CardTitle>
              <CardDescription>Ready for integrations</CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-xl font-bold">{identity.merchant.name}</p>
            </CardContent>
          </Card>
        </div>
        <div className="mt-4 flex flex-col gap-4">
          <StripeIntegration />
        </div>
      </section>
    </main>
  );
}
