import Link from "next/link";

import { ArrowRightIcon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { SiteHeader } from "@/components/site-header";

const SIGNAL_ROWS = [
  {
    title: "Identity verified",
    description: "Merchant boundary established",
  },
  {
    title: "Provider-ready",
    description: "Provider connection comes next",
  },
  {
    title: "Events have a home",
    description: "Every payment event belongs somewhere",
  },
] as const;

/**
 * Home page for the Voic marketing site.
 *
 * @returns The landing page with product messaging and call-to-action buttons.
 */
export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 pb-16">
      <SiteHeader>
        <nav className="flex items-center gap-2 sm:gap-4" aria-label="Main navigation">
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
        </nav>
      </SiteHeader>
      <section className="grid flex-1 items-center gap-11 py-12 lg:grid-cols-[1.15fr_0.85fr] lg:gap-20">
        <div>
          <p className="mb-5 text-xs font-extrabold tracking-[0.14em] text-primary uppercase">
            Payment recovery infrastructure
          </p>
          <h1 className="mb-6 max-w-2xl text-5xl leading-[0.95] font-extrabold tracking-tighter text-balance sm:text-6xl lg:text-7xl">
            Turn failed payments into a second chance.
          </h1>
          <p className="max-w-xl text-lg leading-relaxed text-muted-foreground">
            Voic gives merchants a reliable foundation for connecting payment
            data, understanding what failed, and building a more thoughtful
            recovery flow.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button
              size="lg"
              nativeButton={false}
              render={<Link href="/auth/signup">Create your workspace</Link>}
            />
            <Button
              size="lg"
              variant="outline"
              nativeButton={false}
              render={<Link href="/auth/login">I already have an account</Link>}
            />
          </div>
        </div>
        <Card
          className="shadow-[18px_18px_0_0_var(--secondary)]"
          aria-label="Voic integration status preview"
        >
          <CardHeader>
            <CardTitle>Workspace signal</CardTitle>
            <CardAction>
              <Badge variant="secondary">Phase 01</Badge>
            </CardAction>
          </CardHeader>
          <CardContent>
            {SIGNAL_ROWS.map((row, index) => (
              <div key={row.title}>
                {index > 0 ? <Separator className="my-4" /> : null}
                <div className="flex items-center gap-3.5">
                  <span className="size-2.5 shrink-0 rounded-full bg-primary" />
                  <div>
                    <p className="font-semibold">{row.title}</p>
                    <p className="text-sm text-muted-foreground">
                      {row.description}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
