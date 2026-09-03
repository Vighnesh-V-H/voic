import Link from "next/link";

import { Button } from "@/components/ui/button";
import { SiteHeader } from "@/components/site-header";

/**
 * Layout component for authentication pages (login and signup).
 *
 * @param props - Component props containing children to render.
 * @returns A layout with site header and navigation back to home.
 */
export default function AuthLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 pb-16">
      <SiteHeader>
        <Button
          variant="link"
          nativeButton={false}
          render={<Link href="/">Back to home</Link>}
        />
      </SiteHeader>
      {children}
    </main>
  );
}
