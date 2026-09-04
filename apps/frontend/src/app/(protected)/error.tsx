"use client";

import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

/**
 * Error state for protected routes. Offers a retry first, navigation second.
 *
 * @param props - The reset action that re-attempts the failed segment.
 * @returns A recovery card in the product voice.
 */
export default function ProtectedError({
  reset,
}: Readonly<{ reset: () => void }>) {
  return (
    <section className="flex flex-col items-center py-16">
      <Card className="w-full max-w-md text-center">
        <CardHeader>
          <CardTitle className="text-2xl">This page could not load</CardTitle>
          <CardDescription>
            The workspace data did not arrive. Your payments in Stripe are
            unaffected.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Button onClick={reset}>Try again</Button>
          <Button
            variant="outline"
            nativeButton={false}
            render={<Link href="/dashboard">Back to dashboard</Link>}
          />
        </CardContent>
      </Card>
    </section>
  );
}
