import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { AppSidebar } from "@/components/app-sidebar";
import { ThemeToggle } from "@/components/theme-toggle";
import type { Identity } from "@/lib/api";
import { Separator } from "@/components/ui/separator";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";

/**
 * Fetch the authenticated user's identity from the backend.
 *
 * @returns The user's identity containing user and merchant details.
 */
async function getIdentity(): Promise<Identity> {
  const cookieHeader = (await cookies()).toString();
  const response = await fetch(
    `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/v1/auth/me`,
    { headers: { cookie: cookieHeader }, cache: "no-store" },
  );

  if (response.status === 401) {
    redirect("/auth/login");
  }

  if (!response.ok) {
    throw new Error("The backend could not verify this session.");
  }

  return response.json() as Promise<Identity>;
}

/**
 * Protected routes layout providing the app sidebar to all authenticated pages.
 *
 * @param props - Component props containing children to render.
 * @returns A sidebar shell with header controls and page content.
 */
export default async function ProtectedLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const identity = await getIdentity();

  return (
    <SidebarProvider>
      <AppSidebar userEmail={identity.user.email} merchantName={identity.merchant.name} />
      <SidebarInset>
        <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
          <SidebarTrigger />
          <Separator orientation="vertical" className="mr-2 h-4" />
          <p className="truncate text-sm font-semibold sm:text-base">
            {identity.merchant.name}
          </p>
          <div className="ml-auto flex items-center gap-1">
            <Link
              href="/"
              className="hidden rounded-md px-2.5 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground sm:block"
            >
              View site
            </Link>
            <ThemeToggle />
          </div>
        </header>
        <div className="flex flex-1 flex-col px-4 py-6 sm:px-6">
          <div className="mx-auto w-full max-w-5xl">{children}</div>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
