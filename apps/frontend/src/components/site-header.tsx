import Link from "next/link";

import { cn } from "@/lib/utils";

const PRODUCT_LINKS = [
  { label: "How it works", href: "/#how" },
  { label: "Recovery", href: "/#recovery" },
  { label: "Security", href: "/#security" },
] as const;

/**
 * Public site header: sticky single-line nav with product anchors and actions.
 *
 * @param props - Optional product nav toggle, className, and right-side actions.
 * @returns A sticky header that stays on one line at desktop widths.
 */
export function SiteHeader({
  className,
  children,
  showNav = false,
}: Readonly<{
  className?: string;
  children?: React.ReactNode;
  showNav?: boolean;
}>) {
  return (
    <header
      className={cn(
        "sticky top-0 z-40 border-b bg-background/85 backdrop-blur",
        className,
      )}
    >
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4 px-5">
        <Link
          href="/"
          className="shrink-0 text-xl font-bold tracking-tight"
          aria-label="Voic home"
        >
          voic<span className="text-muted-foreground">.</span>
        </Link>
        {showNav ? (
          <nav
            className="hidden items-center gap-7 md:flex"
            aria-label="Product"
          >
            {PRODUCT_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                {link.label}
              </Link>
            ))}
          </nav>
        ) : null}
        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
          {children}
        </div>
      </div>
    </header>
  );
}
