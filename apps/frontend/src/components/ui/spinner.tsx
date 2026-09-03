import { cn } from "@/lib/utils"
import { Loader2Icon } from "lucide-react"

/**
 * Spinner component for loading indicators with spin animation.
 *
 * @param props - Component props including className and standard svg attributes.
 * @returns A spinning loader icon with accessibility label.
 */
function Spinner({ className, ...props }: React.ComponentProps<"svg">) {
  return (
    <Loader2Icon data-slot="spinner" role="status" aria-label="Loading" className={cn("size-4 animate-spin", className)} {...props} />
  )
}

export { Spinner }
