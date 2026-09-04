import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { SiteHeader } from "@/components/site-header";

/**
 * Product 404 page for unknown routes.
 *
 * @returns A not-found card pointing back to known surfaces.
 */
export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader>
        <Button
          variant="ghost"
          nativeButton={false}
          render={<Link href="/">Back to home</Link>}
        />
      </SiteHeader>
      <main className="mx-auto flex w-full max-w-6xl flex-1 items-center justify-center px-5">
        <Card className="w-full max-w-md text-center">
          <CardHeader>
            <CardTitle className="font-editorial text-4xl">
              Nothing here
            </CardTitle>
            <CardDescription>
              This page does not exist or you do not have access to it.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <Button nativeButton={false} render={<Link href="/">Go home</Link>} />
            <Button
              variant="outline"
              nativeButton={false}
              render={<Link href="/dashboard">Open dashboard</Link>}
            />
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
