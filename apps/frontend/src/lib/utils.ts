import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

/**
 * Merge Tailwind CSS class names using clsx and tailwind-merge.
 *
 * @param inputs - Class values to merge (strings, objects, arrays).
 * @returns A merged class name string with conflicting Tailwind classes resolved.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
