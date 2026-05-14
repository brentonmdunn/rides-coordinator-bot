import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { toast } from "sonner"
import {
  DAY_SUNDAY,
  DAY_FRIDAY,
  DAY_SATURDAY,
  SUNDAY_WIDGET_START_HOUR,
  SUNDAY_WIDGET_END_HOUR,
  FRIDAY_WARNING_HOUR,
  SUNDAY_WARNING_HOUR,
} from './constants'

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

  // Sunday widget: Saturday 4PM or later, or Sunday before 1PM
  if ((day === DAY_SATURDAY && hour >= SUNDAY_WIDGET_START_HOUR) || (day === DAY_SUNDAY && hour < SUNDAY_WIDGET_END_HOUR)) {
    return 'sunday'
  }
  return 'friday'
}

// Friday after noon — show warning that Friday rides need drivers
export function isFridayWarningWindow(): boolean {
  const now = new Date()
  return now.getDay() === DAY_FRIDAY && now.getHours() >= FRIDAY_WARNING_HOUR
}

// Saturday after 5 PM — show warning that Sunday rides need drivers
export function isSundayWarningWindow(): boolean {
  const now = new Date()
  return now.getDay() === DAY_SATURDAY && now.getHours() >= SUNDAY_WARNING_HOUR
}
