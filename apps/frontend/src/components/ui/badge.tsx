import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "group/badge inline-flex h-5 w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-full border border-transparent px-2 py-0.5 text-xs font-medium whitespace-nowrap transition-all focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 [&>svg]:pointer-events-none [&>svg]:size-3!",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground [a]:hover:bg-primary/80",
        secondary:
          "bg-secondary text-secondary-foreground [a]:hover:bg-secondary/80",
        destructive:
          "bg-destructive/10 text-destructive focus-visible:ring-destructive/20 dark:bg-destructive/20 dark:focus-visible:ring-destructive/40 [a]:hover:bg-destructive/20",
        outline:
          "border-border text-foreground [a]:hover:bg-muted [a]:hover:text-muted-foreground",
        ghost:
          "hover:bg-muted hover:text-muted-foreground dark:hover:bg-muted/50",
        link: "text-primary underline-offset-4 hover:underline",
        success:
          "border-pastel-green-border bg-pastel-green-bg font-semibold text-pastel-green-text text-[11px] tracking-[0.05em] uppercase",
        info: "border-pastel-blue-border bg-pastel-blue-bg font-semibold text-pastel-blue-text text-[11px] tracking-[0.05em] uppercase",
        warning:
          "border-pastel-yellow-border bg-pastel-yellow-bg font-semibold text-pastel-yellow-text text-[11px] tracking-[0.05em] uppercase",
        error:
          "border-pastel-red-border bg-pastel-red-bg font-semibold text-pastel-red-text text-[11px] tracking-[0.05em] uppercase",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

/**
 * Badge component for displaying status or labels with different variants.
 *
 * @param props - Component props including className, variant, render function, and standard span attributes.
 * @returns A badge span element with the specified variant styling.
 */
function Badge({
  className,
  variant = "default",
  render,
  ...props
}: useRender.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return useRender({
    defaultTagName: "span",
    props: mergeProps<"span">(
      {
        className: cn(badgeVariants({ variant }), className),
      },
      props
    ),
    render,
    state: {
      slot: "badge",
      variant,
    },
  })
}

export { Badge, badgeVariants }
