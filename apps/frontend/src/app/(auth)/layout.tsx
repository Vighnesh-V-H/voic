import Link from "next/link";

import { Button } from "@/components/ui/button";
import { SiteHeader } from "@/components/site-header";

export default function AuthLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 pb-16">
      <SiteHeader>
        <Button variant="link" render={<Link href="/">Back to home</Link>} />
      </SiteHeader>
      {children}
    </main>
  );
}
