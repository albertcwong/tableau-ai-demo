import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function extractErrorMessage(err: unknown, fallback = "An error occurred"): string {
  const e = err as { response?: { data?: { detail?: string; message?: string } | string }; message?: string }
  const data = e?.response?.data
  if (typeof data === "string") return data
  return data?.detail ?? data?.message ?? e?.message ?? fallback
}
