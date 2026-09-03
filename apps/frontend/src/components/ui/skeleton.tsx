import { cn } from "@/lib/utils"

/**
 * Skeleton component for loading placeholders with pulse animation.
 *
 * @param props - Component props including className and standard div attributes.
 * @returns A skeleton div with pulse animation.
 */
function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="skeleton"
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  )
}

export { Skeleton }
