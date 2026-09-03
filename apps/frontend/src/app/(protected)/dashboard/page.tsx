import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { Identity } from "@/lib/api";
import { Reveal } from "@/components/reveal";
import { StripeIntegration } from "@/components/stripe-integration";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

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
    <section className="flex flex-col py-2">
      <Reveal>
        <div className="mb-8 flex flex-wrap items-end justify-between gap-5">
          <div>
            <p className="mb-5 text-xs font-semibold tracking-[0.14em] text-muted-foreground uppercase">
              Merchant account
            </p>
            <h1 className="font-editorial text-5xl text-balance sm:text-6xl">
              {identity.merchant.name}
            </h1>
          </div>
          <p className="pb-2 font-mono text-sm text-muted-foreground">{identity.user.email}</p>
        </div>
      </Reveal>
        <div className="grid gap-4 sm:grid-cols-2">
          <Reveal index={1}>
            <Card className="card-hover h-full">
              <CardHeader>
                <CardTitle>Identity</CardTitle>
                <CardDescription>Session verified by the backend</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-xl font-semibold">{identity.user.email}</p>
              </CardContent>
            </Card>
          </Reveal>
          <Reveal index={2}>
            <Card className="card-hover h-full">
              <CardHeader>
                <CardTitle>Merchant boundary</CardTitle>
                <CardDescription>Ready for integrations</CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-xl font-semibold">{identity.merchant.name}</p>
              </CardContent>
            </Card>
          </Reveal>
        </div>
        <div className="mt-4 flex flex-col gap-4">
          <StripeIntegration />
        </div>
    </section>
  );
}
