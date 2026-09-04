import Link from "next/link";

import { ArrowLeftIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { SiteHeader } from "@/components/site-header";

/**
 * Layout component for authentication pages (login and signup).
 *
 * @param props - Component props containing children to render.
 * @returns A layout with the shared site header and centered auth content.
 */
export default function AuthLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="flex min-h-screen flex-col">
      <SiteHeader>
        <Button
          variant="ghost"
          nativeButton={false}
          render={
            <Link href="/">
              <ArrowLeftIcon data-icon="inline-start" />
              Back to home
            </Link>
          }
        />
      </SiteHeader>
      <main className="mx-auto w-full max-w-6xl flex-1 px-5">{children}</main>
    </div>
  );
}
