import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const alertVariants = cva(
  "group/alert relative grid w-full gap-0.5 rounded-lg border px-3 py-2.5 text-left text-sm shadow-none has-data-[slot=alert-action]:relative has-data-[slot=alert-action]:pr-18 has-[>svg]:grid-cols-[auto_1fr] has-[>svg]:gap-x-2 *:[svg]:row-span-2 *:[svg]:translate-y-0.5 *:[svg]:text-current *:[svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "border-border bg-card text-card-foreground *:data-[slot=alert-description]:text-muted-foreground",
        destructive:
          "border-pastel-red-border bg-pastel-red-bg text-pastel-red-text *:data-[slot=alert-description]:text-pastel-red-text *:[svg]:text-current",
        success:
          "border-pastel-green-border bg-pastel-green-bg text-pastel-green-text *:data-[slot=alert-description]:text-pastel-green-text",
        info: "border-pastel-blue-border bg-pastel-blue-bg text-pastel-blue-text *:data-[slot=alert-description]:text-pastel-blue-text",
        warning:
          "border-pastel-yellow-border bg-pastel-yellow-bg text-pastel-yellow-text *:data-[slot=alert-description]:text-pastel-yellow-text",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

/**
 * Alert component for displaying contextual messages with optional variants.
 *
 * @param props - Component props including className, variant, and standard div attributes.
 * @returns An alert div with role="alert".
 */
function Alert({
  className,
  variant,
  ...props
}: React.ComponentProps<"div"> & VariantProps<typeof alertVariants>) {
  return (
    <div
      data-slot="alert"
      role="alert"
      className={cn(alertVariants({ variant }), className)}
      {...props}
    />
  )
}

/**
 * Alert title subcomponent for displaying the main alert heading.
 *
 * @param props - Component props including className and standard div attributes.
 * @returns A div for the alert title.
 */
function AlertTitle({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-title"
      className={cn(
        "font-medium group-has-[>svg]/alert:col-start-2 [&_a]:underline [&_a]:underline-offset-3 [&_a]:hover:text-foreground",
        className
      )}
      {...props}
    />
  )
}

/**
 * Alert description subcomponent for displaying detailed alert content.
 *
 * @param props - Component props including className and standard div attributes.
 * @returns A div for the alert description.
 */
function AlertDescription({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-description"
      className={cn(
        "text-sm text-balance text-current opacity-80 md:text-pretty [&_a]:underline [&_a]:underline-offset-3 [&_a]:hover:text-foreground [&_p:not(:last-child)]:mb-4",
        className
      )}
      {...props}
    />
  )
}

/**
 * Alert action subcomponent for displaying action buttons or icons in the top-right corner.
 *
 * @param props - Component props including className and standard div attributes.
 * @returns A div for the alert action.
 */
function AlertAction({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="alert-action"
      className={cn("absolute top-2 right-2", className)}
      {...props}
    />
  )
}

export { Alert, AlertTitle, AlertDescription, AlertAction }
