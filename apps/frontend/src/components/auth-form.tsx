"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { apiRequest, Identity } from "@/lib/api";

type AuthFormProps = {
  mode: "login" | "signup";
};

export function AuthForm({ mode }: AuthFormProps) {
  const router = useRouter();
  const isSignup = mode === "signup";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [merchantName, setMerchantName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

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
    <>
      <form className="form" onSubmit={handleSubmit}>
        {isSignup && (
          <div className="field">
            <label htmlFor="merchant-name">Business name</label>
            <input
              id="merchant-name"
              name="merchant_name"
              value={merchantName}
              onChange={(event) => setMerchantName(event.target.value)}
              placeholder="Acme Store"
              required
            />
          </div>
        )}
        <div className="field">
          <label htmlFor="email">Email address</label>
          <input
            id="email"
            name="email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@company.com"
            autoComplete="email"
            required
          />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input
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
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="button button-primary" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Working..." : isSignup ? "Create account" : "Log in"}
        </button>
      </form>
      <p className="auth-switch">
        {isSignup ? "Already have an account? " : "New to Voic? "}
        <Link className="text-link" href={isSignup ? "/auth/login" : "/auth/signup"}>
          {isSignup ? "Log in" : "Create an account"}
        </Link>
      </p>
    </>
  );
}
