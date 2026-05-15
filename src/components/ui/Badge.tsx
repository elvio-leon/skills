import { cn } from "@/lib/utils"

type BadgeVariant = "green" | "blue" | "yellow" | "red" | "gray" | "purple"

const variants: Record<BadgeVariant, string> = {
  green: "bg-green-100 text-green-800",
  blue: "bg-blue-100 text-blue-800",
  yellow: "bg-yellow-100 text-yellow-800",
  red: "bg-red-100 text-red-800",
  gray: "bg-gray-100 text-gray-700",
  purple: "bg-purple-100 text-purple-800",
}

export function Badge({ variant = "gray", children }: { variant?: BadgeVariant; children: React.ReactNode }) {
  return (
    <span className={cn("inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium", variants[variant])}>
      {children}
    </span>
  )
}

export function clientStatusBadge(status: string) {
  const map: Record<string, { variant: BadgeVariant; label: string }> = {
    lead: { variant: "yellow", label: "Lead" },
    active: { variant: "green", label: "Cliente attivo" },
    inactive: { variant: "gray", label: "Inattivo" },
  }
  return map[status] ?? { variant: "gray", label: status }
}

export function projectStatusBadge(status: string) {
  const map: Record<string, { variant: BadgeVariant; label: string }> = {
    in_corso: { variant: "blue", label: "In corso" },
    completato: { variant: "green", label: "Completato" },
    in_pausa: { variant: "yellow", label: "In pausa" },
    annullato: { variant: "red", label: "Annullato" },
  }
  return map[status] ?? { variant: "gray", label: status }
}

export function invoiceStatusBadge(status: string) {
  const map: Record<string, { variant: BadgeVariant; label: string }> = {
    bozza: { variant: "gray", label: "Bozza" },
    inviata: { variant: "blue", label: "Inviata" },
    pagata: { variant: "green", label: "Pagata" },
    scaduta: { variant: "red", label: "Scaduta" },
  }
  return map[status] ?? { variant: "gray", label: status }
}

export function proposalStatusBadge(status: string) {
  const map: Record<string, { variant: BadgeVariant; label: string }> = {
    bozza: { variant: "gray", label: "Bozza" },
    inviata: { variant: "blue", label: "Inviata" },
    accettata: { variant: "green", label: "Accettata" },
    rifiutata: { variant: "red", label: "Rifiutata" },
  }
  return map[status] ?? { variant: "gray", label: status }
}
