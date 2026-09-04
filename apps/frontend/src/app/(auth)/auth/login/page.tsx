import { CircleCheckIcon } from "lucide-react";

import { AuthForm } from "@/components/auth-form";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const LOGIN_POINTS = [
  "See every payment status in one dashboard",
  "Failed checkouts flagged with full history",
  "Products and prices synced from Stripe",
] as const;

/**
 * Login page for existing merchant accounts.
 *
 * @param props - Route props carrying optional search params (e.g. account-created notice).
 * @returns A page with login form and supporting product context.
 */
export default async function LoginPage({
  searchParams,
}: Readonly<{ searchParams?: Promise<{ created?: string }> }>) {
  const params = searchParams ? await searchParams : undefined;
  const justCreated = params?.created === "1";

  return (
    <section className="grid items-center gap-12 py-14 lg:grid-cols-[1fr_420px] lg:gap-16 lg:py-20">
      <div>
        <h1 className="font-editorial max-w-xl text-4xl text-balance sm:text-5xl">
          Pick up where your payments left off.
        </h1>
        <p className="mt-4 max-w-xl text-lg leading-relaxed text-muted-foreground">
          Log in to see what completed, what is pending, and what needs a
          follow-up today.
        </p>
        <ul className="mt-8 flex max-w-xl flex-col gap-3.5">
          {LOGIN_POINTS.map((point) => (
            <li key={point} className="flex items-start gap-3 text-sm">
              <CircleCheckIcon
                className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400"
                aria-hidden="true"
              />
              <span className="leading-relaxed">{point}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="flex flex-col gap-4">
        {justCreated ? (
          <Alert variant="success" role="status">
            <AlertTitle>Account created</AlertTitle>
            <AlertDescription>
              Log in with the credentials you just chose.
            </AlertDescription>
          </Alert>
        ) : null}
        <Card>
          <CardHeader>
            <CardTitle className="text-2xl">Log in</CardTitle>
            <CardDescription>
              Use the email and password for your account.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <AuthForm mode="login" />
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
