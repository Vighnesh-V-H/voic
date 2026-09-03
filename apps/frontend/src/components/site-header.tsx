import Link from "next/link";

import { cn } from "@/lib/utils";

export function SiteHeader({
  className,
  children,
}: Readonly<{
  className?: string;
  children?: React.ReactNode;
}>) {
  return (
    <header className={cn("flex items-center justify-between py-7", className)}>
      <Link href="/" className="text-xl font-extrabold tracking-tighter">
        voic<span className="text-primary">.</span>
      </Link>
      <div className="flex items-center gap-2 sm:gap-4">{children}</div>
    </header>
  );
}
