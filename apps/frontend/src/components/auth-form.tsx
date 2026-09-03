"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { TriangleAlertIcon } from "lucide-react";

import { apiRequest, Identity } from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";

type AuthFormProps = {
  mode: "login" | "signup";
};

/**
 * Authentication form component for login or signup.
 *
 * @param props - Component props containing the mode (login or signup).
 * @returns A form for user authentication.
 */
export function AuthForm({ mode }: AuthFormProps) {
  const router = useRouter();
  const isSignup = mode === "signup";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [merchantName, setMerchantName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  /**
   * Handle form submission for login or signup.
   *
   * @param event - The form submit event.
   */
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      if (isSignup) {
        await apiRequest<Identity>("/api/v1/auth/signup", {
          method: "POST",
          body: JSON.stringify({ email, password, merchant_name: merchantName }),
        });
        router.push("/auth/login?created=1");
      } else {
        await apiRequest<Identity>("/api/v1/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        router.push("/dashboard");
        router.refresh();
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "The request failed.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={handleSubmit}>
        <FieldGroup>
          {isSignup ? (
            <Field>
              <FieldLabel htmlFor="merchant-name">Business name</FieldLabel>
              <Input
                id="merchant-name"
                name="merchant_name"
                value={merchantName}
                onChange={(event) => setMerchantName(event.target.value)}
                placeholder="Acme Store"
                required
              />
            </Field>
          ) : null}
          <Field>
            <FieldLabel htmlFor="email">Email address</FieldLabel>
            <Input
              id="email"
              name="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@company.com"
              autoComplete="email"
              required
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="password">Password</FieldLabel>
            <Input
              id="password"
              name="password"
              type="password"
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="At least 8 characters"
              autoComplete={isSignup ? "new-password" : "current-password"}
              required
            />
          </Field>
          {error ? (
            <Alert variant="destructive">
              <TriangleAlertIcon />
              <AlertTitle>Couldn&apos;t complete this step</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          <Button className="w-full" type="submit" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <Spinner data-icon="inline-start" />
                Working...
              </>
            ) : isSignup ? (
              "Create account"
            ) : (
              "Log in"
            )}
          </Button>
        </FieldGroup>
      </form>
      <p className="text-center text-sm text-muted-foreground">
        {isSignup ? "Already have an account? " : "New to Voic? "}
        <Button
          variant="link"
          className="h-auto p-0 text-sm"
          render={
            <Link href={isSignup ? "/auth/login" : "/auth/signup"}>
              {isSignup ? "Log in" : "Create an account"}
            </Link>
          }
        />
      </p>
    </div>
  );
}
