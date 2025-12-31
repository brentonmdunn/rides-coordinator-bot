import { useState } from "react"
import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Custom hook for copying text to clipboard with temporary feedback
 * @param timeout - Duration in milliseconds to show the copied state (default: 2000ms)
 * @returns Object with copiedText state and copyToClipboard function
 */
export function useCopyToClipboard(timeout = 2000) {
  const [copiedText, setCopiedText] = useState<string | null>(null)

  const copyToClipboard = async (text: string | null) => {
    if (!text) return

    try {
      await navigator.clipboard.writeText(text)
      setCopiedText(text)
      setTimeout(() => setCopiedText(null), timeout)
    } catch (error) {
      console.error('Failed to copy to clipboard:', error)
    }
  }

  return { copiedText, copyToClipboard }
}
