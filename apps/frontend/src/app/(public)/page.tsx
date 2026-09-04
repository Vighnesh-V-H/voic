import Link from "next/link";

import {
  ArrowRightIcon,
  BellRingIcon,
  ChartLineIcon,
  PlugZapIcon,
  ShieldCheckIcon,
  WebhookIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Reveal } from "@/components/reveal";
import { SiteHeader } from "@/components/site-header";

const STATUS_ROWS = [
  { label: "Completed", detail: "Settled in Stripe", tone: "bg-emerald-500" },
  { label: "Pending", detail: "Awaiting confirmation", tone: "bg-amber-500" },
  { label: "Failed", detail: "Needs follow-up", tone: "bg-red-500" },
] as const;

const STEPS = [
  {
    index: "01",
    title: "Connect Stripe",
    body: "Authorize your existing Stripe account. Products and prices sync automatically.",
  },
  {
    index: "02",
    title: "Track every payment",
    body: "Each checkout lands in one dashboard with a clear status, from created to completed.",
  },
  {
    index: "03",
    title: "Follow up on failures",
    body: "See what failed and why, then reach out while the customer still wants to pay.",
  },
] as const;

const STRIP_ITEMS = [
  { icon: PlugZapIcon, label: "Stripe Connect" },
  { icon: WebhookIcon, label: "Live webhook sync" },
  { icon: ShieldCheckIcon, label: "Merchant-scoped data" },
] as const;

/**
 * Home page for the Voic marketing site.
 *
 * @returns The landing page with product messaging and a single signup intent.
 */
export default function Home() {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader showNav>
        <Button
          variant="ghost"
          nativeButton={false}
          render={<Link href="/auth/login">Log in</Link>}
        />
        <Button
          nativeButton={false}
          render={
            <Link href="/auth/signup">
              Get started
              <ArrowRightIcon data-icon="inline-end" />
            </Link>
          }
        />
      </SiteHeader>

      <main className="mx-auto w-full max-w-6xl flex-1 px-5">
        {/* Hero: headline + subtext + CTAs, product panel at right */}
        <section className="grid items-center gap-12 pt-16 pb-16 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16 lg:pt-24 lg:pb-20">
          <Reveal>
            <h1 className="font-editorial max-w-xl text-4xl text-balance md:text-5xl lg:text-6xl">
              Turn failed payments into recovered revenue.
            </h1>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-muted-foreground">
              Voic connects Stripe, tracks every payment, and helps you follow
              up before revenue slips away.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Button
                size="lg"
                nativeButton={false}
                render={<Link href="/auth/signup">Get started</Link>}
              />
              <Button
                size="lg"
                variant="outline"
                nativeButton={false}
                render={<Link href="/#how">See how it works</Link>}
              />
            </div>
          </Reveal>
          <Reveal index={1}>
            <Card aria-label="Payment status preview">
              <CardHeader>
                <CardTitle>Payment status, at a glance</CardTitle>
                <CardDescription>
                  Every checkout in one place, synced from Stripe.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="flex flex-col divide-y divide-border">
                  {STATUS_ROWS.map((row) => (
                    <li
                      key={row.label}
                      className="flex items-center gap-3.5 py-3.5 first:pt-0 last:pb-0"
                    >
                      <span
                        className={`size-2 shrink-0 rounded-full ${row.tone}`}
                        aria-hidden="true"
                      />
                      <div className="flex flex-1 items-center justify-between gap-3">
                        <div>
                          <p className="font-semibold">{row.label}</p>
                          <p className="text-sm text-muted-foreground">
                            {row.detail}
                          </p>
                        </div>
                        <span className="font-mono text-lg tabular-nums text-muted-foreground">
                          00
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
                <div className="mt-4 flex items-center justify-between border-t pt-4">
                  <p className="text-sm text-muted-foreground">
                    Sample layout. Your data appears after connect.
                  </p>
                  <Badge variant="secondary">Preview</Badge>
                </div>
              </CardContent>
            </Card>
          </Reveal>
        </section>

        {/* Trust strip: separate section below the hero */}
        <section
          aria-label="Built for Stripe merchants"
          className="border-y py-6"
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm font-medium text-muted-foreground">
              Built for Stripe merchants
            </p>
            <ul className="flex flex-wrap items-center gap-x-7 gap-y-3">
              {STRIP_ITEMS.map((item) => (
                <li
                  key={item.label}
                  className="flex items-center gap-2 text-sm font-medium"
                >
                  <item.icon
                    className="size-4 text-muted-foreground"
                    aria-hidden="true"
                  />
                  {item.label}
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* How it works: numbered steps */}
        <section id="how" className="scroll-mt-20 py-16 lg:py-24">
          <Reveal>
            <p className="text-[11px] font-semibold tracking-[0.18em] text-muted-foreground uppercase">
              How it works
            </p>
            <h2 className="font-editorial mt-3 max-w-xl text-3xl text-balance sm:text-4xl">
              From Stripe connection to clear follow-up
            </h2>
          </Reveal>
          <ol className="mt-10 grid gap-px overflow-hidden rounded-lg border bg-border sm:grid-cols-1 md:grid-cols-3">
            {STEPS.map((step, index) => (
              <li key={step.index} className="bg-card p-7">
                <Reveal index={index}>
                  <p className="font-mono text-sm text-muted-foreground">
                    {step.index}
                  </p>
                  <h3 className="mt-3 text-lg font-semibold">{step.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                    {step.body}
                  </p>
                </Reveal>
              </li>
            ))}
          </ol>
        </section>

        {/* Recovery: asymmetric bento, exactly 3 cells */}
        <section id="recovery" className="scroll-mt-20 pb-16 lg:pb-24">
          <Reveal>
            <h2 className="font-editorial max-w-xl text-3xl text-balance sm:text-4xl">
              Know exactly which payments need you
            </h2>
            <p className="mt-3 max-w-xl leading-relaxed text-muted-foreground">
              The dashboard separates signal from noise so failed payments get
              attention first.
            </p>
          </Reveal>
          <div className="mt-10 grid gap-4 md:grid-cols-5">
            <Reveal className="md:col-span-3">
              <Card className="h-full bg-muted/60">
                <CardHeader>
                  <BellRingIcon
                    className="size-5 text-muted-foreground"
                    aria-hidden="true"
                  />
                  <CardTitle className="mt-3">
                    Failed payments surface first
                  </CardTitle>
                  <CardDescription>
                    Failures are flagged with context, so you can act the same
                    day instead of discovering them at month end.
                  </CardDescription>
                </CardHeader>
              </Card>
            </Reveal>
            <div className="grid gap-4 md:col-span-2">
              <Reveal index={1}>
                <Card className="h-full">
                  <CardHeader>
                    <ChartLineIcon
                      className="size-5 text-muted-foreground"
                      aria-hidden="true"
                    />
                    <CardTitle className="mt-3 text-lg">
                      Volume and trend stay visible
                    </CardTitle>
                    <CardDescription>
                      Completed revenue and attempt counts update with every
                      webhook.
                    </CardDescription>
                  </CardHeader>
                </Card>
              </Reveal>
              <Reveal index={2}>
                <Card className="h-full">
                  <CardHeader>
                    <PlugZapIcon
                      className="size-5 text-muted-foreground"
                      aria-hidden="true"
                    />
                    <CardTitle className="mt-3 text-lg">
                      Your catalog comes along
                    </CardTitle>
                    <CardDescription>
                      Products and prices sync from Stripe, so rows show real
                      names, not IDs.
                    </CardDescription>
                  </CardHeader>
                </Card>
              </Reveal>
            </div>
          </div>
        </section>

        {/* Security: single checklist band, no inversion */}
        <section
          id="security"
          className="scroll-mt-20 rounded-lg border bg-card px-7 py-10 lg:px-12 lg:py-14"
        >
          <div className="grid gap-8 lg:grid-cols-[1fr_1fr] lg:gap-14">
            <Reveal>
              <h2 className="font-editorial text-3xl text-balance sm:text-4xl">
                Your data stays inside your merchant boundary
              </h2>
              <p className="mt-3 leading-relaxed text-muted-foreground">
                Sessions are HTTP-only cookies, every request is scoped to your
                merchant, and Stripe data is read through official OAuth.
              </p>
              <div className="mt-7">
                <Button
                  variant="outline"
                  nativeButton={false}
                  render={<Link href="/auth/signup">Get started</Link>}
                />
              </div>
            </Reveal>
            <Reveal index={1}>
              <ul className="flex flex-col divide-y divide-border">
                {[
                  "One merchant per account in Phase 1",
                  "Disconnect removes the Stripe connection",
                  "Failed checkouts keep their full history",
                ].map((item) => (
                  <li
                    key={item}
                    className="flex items-start gap-3 py-3.5 first:pt-0 last:pb-0"
                  >
                    <ShieldCheckIcon
                      className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400"
                      aria-hidden="true"
                    />
                    <span className="text-sm leading-relaxed">{item}</span>
                  </li>
                ))}
              </ul>
            </Reveal>
          </div>
        </section>

        {/* Final call to action */}
        <section className="py-16 text-center lg:py-24">
          <Reveal>
            <h2 className="font-editorial mx-auto max-w-xl text-3xl text-balance sm:text-4xl">
              Stop guessing which payments failed
            </h2>
            <p className="mx-auto mt-3 max-w-md leading-relaxed text-muted-foreground">
              Connect Stripe and see every payment status in minutes.
            </p>
            <div className="mt-7 flex justify-center">
              <Button
                size="lg"
                nativeButton={false}
                render={
                  <Link href="/auth/signup">
                    Get started
                    <ArrowRightIcon data-icon="inline-end" />
                  </Link>
                }
              />
            </div>
            <p className="mt-4 text-sm text-muted-foreground">
              Already have an account?{" "}
              <Link
                href="/auth/login"
                className="font-medium text-foreground underline-offset-4 hover:underline"
              >
                Log in
              </Link>
            </p>
          </Reveal>
        </section>
      </main>

      <footer className="border-t">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 px-5 py-7 sm:flex-row sm:items-center sm:justify-between">
          <Link
            href="/"
            className="text-lg font-bold tracking-tight"
            aria-label="Voic home"
          >
            voic<span className="text-muted-foreground">.</span>
          </Link>
          <nav
            className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground"
            aria-label="Footer"
          >
            <Link href="/#how" className="transition-colors hover:text-foreground">
              How it works
            </Link>
            <Link
              href="/#recovery"
              className="transition-colors hover:text-foreground"
            >
              Recovery
            </Link>
            <Link href="/auth/login" className="transition-colors hover:text-foreground">
              Log in
            </Link>
            <Link
              href="/auth/signup"
              className="font-medium text-foreground underline-offset-4 hover:underline"
            >
              Get started
            </Link>
          </nav>
          <p className="text-sm text-muted-foreground">
            Payment recovery infrastructure
          </p>
        </div>
      </footer>
    </div>
  );
}
