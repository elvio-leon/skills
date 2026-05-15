import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"
import { format } from "date-fns"
import { it } from "date-fns/locale"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat("it-IT", {
    style: "currency",
    currency: "EUR",
  }).format(amount)
}

export function formatDate(date: Date | string | null | undefined): string {
  if (!date) return "-"
  return format(new Date(date), "dd/MM/yyyy", { locale: it })
}

export function formatDateInput(date: Date | string | null | undefined): string {
  if (!date) return ""
  return format(new Date(date), "yyyy-MM-dd")
}
