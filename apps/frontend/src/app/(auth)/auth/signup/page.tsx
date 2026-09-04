import { CircleCheckIcon } from "lucide-react";

import { AuthForm } from "@/components/auth-form";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const SIGNUP_POINTS = [
  "Connect your existing Stripe account",
  "Payments, products, and prices sync in",
  "Failed checkouts keep their full history",
] as const;

/**
 * Signup page for creating new merchant accounts.
 *
 * @returns A page with signup form and setup expectations.
 */
export default function SignupPage() {
  return (
    <section className="grid items-center gap-12 py-14 lg:grid-cols-[1fr_420px] lg:gap-16 lg:py-20">
      <div>
        <h1 className="font-editorial max-w-xl text-4xl text-balance sm:text-5xl">
          See every payment status in minutes.
        </h1>
        <p className="mt-4 max-w-xl text-lg leading-relaxed text-muted-foreground">
          Create your account, connect Stripe, and your dashboard fills itself
          in.
        </p>
        <ol className="mt-8 flex max-w-xl flex-col gap-3.5">
          {SIGNUP_POINTS.map((point, index) => (
            <li key={point} className="flex items-start gap-3 text-sm">
              <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-muted font-mono text-[11px] font-semibold text-muted-foreground">
                {index + 1}
              </span>
              <span className="leading-relaxed">{point}</span>
            </li>
          ))}
        </ol>
        <p className="mt-8 flex items-center gap-2 text-sm text-muted-foreground">
          <CircleCheckIcon
            className="size-4 shrink-0 text-emerald-600 dark:text-emerald-400"
            aria-hidden="true"
          />
          No catalog rebuild. Your Stripe products stay where they are.
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl">Create your account</CardTitle>
          <CardDescription>
            One account per business to start. Takes about a minute.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AuthForm mode="signup" />
        </CardContent>
      </Card>
    </section>
  );
}
