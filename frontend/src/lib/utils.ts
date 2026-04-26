import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { toast } from "sonner"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export async function copyToClipboard(text: string | null) {
  if (!text) return

  try {
    await navigator.clipboard.writeText(text)
    toast.success('Copied to clipboard')
  } catch (error) {
    console.error('Failed to copy to clipboard:', error)
    toast.error('Failed to copy to clipboard')
  }
}

/**
 * Determine the automatic day based on current day/time.
 * - Saturday, Sunday, or Friday after 10pm → 'sunday'
 * - Otherwise → 'friday'
 *
 * Used by DriverReactions, ReactionDetails, and RouteBuilder.
 */
export function getAutomaticDay(): 'friday' | 'sunday' {
  const now = new Date()
  const day = now.getDay()
  const hour = now.getHours()

  if (day === 6 || day === 0 || (day === 5 && hour >= 22)) {
    return 'sunday'
  }
  return 'friday'
}

// Friday after noon — show warning that Friday rides need drivers
export function isFridayWarningWindow(): boolean {
  const now = new Date()
  return now.getDay() === 5 && now.getHours() >= 12
}

// Saturday after 5 PM — show warning that Sunday rides need drivers
export function isSundayWarningWindow(): boolean {
  const now = new Date()
  return now.getDay() === 6 && now.getHours() >= 17
}
