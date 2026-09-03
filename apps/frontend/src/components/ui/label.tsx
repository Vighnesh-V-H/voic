"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * Label component for form fields with accessibility support.
 *
 * @param props - Component props including className and standard label attributes.
 * @returns A label element with appropriate styling and disabled states.
 */
function Label({ className, ...props }: React.ComponentProps<"label">) {
  return (
    <label
      data-slot="label"
      className={cn(
        "flex items-center gap-2 text-sm leading-none font-medium select-none group-data-[disabled=true]:pointer-events-none group-data-[disabled=true]:opacity-50 peer-disabled:cursor-not-allowed peer-disabled:opacity-50",
        className
      )}
      {...props}
    />
  )
}

export { Label }
