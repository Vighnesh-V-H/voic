"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LogOutIcon } from "lucide-react";

import { apiRequest } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

/**
 * Sign-out button clearing the HTTP-only session via the backend.
 *
 * @returns A sidebar footer button that signs the user out.
 */
export function SignOutButton() {
  const router = useRouter();
  const [isSigningOut, setIsSigningOut] = useState(false);

  async function handleSignOut() {
    if (isSigningOut) return;
    setIsSigningOut(true);
    try {
      await apiRequest<void>("/api/v1/auth/logout", { method: "POST" });
    } catch {
      // Even if the request fails, send the user to login; proxy guards routes.
    } finally {
      router.push("/auth/login");
      router.refresh();
    }
  }

  return (
    <Button
      variant="ghost"
      size="sm"
      type="button"
      className="w-full justify-start text-muted-foreground hover:text-foreground group-data-[collapsible=icon]:justify-center group-data-[collapsible=icon]:px-0"
      disabled={isSigningOut}
      onClick={() => void handleSignOut()}
      title="Sign out"
    >
      {isSigningOut ? (
        <Spinner data-icon="inline-start" />
      ) : (
        <LogOutIcon data-icon="inline-start" />
      )}
      <span className="group-data-[collapsible=icon]:hidden">
        {isSigningOut ? "Signing out..." : "Sign out"}
      </span>
    </Button>
  );
}
