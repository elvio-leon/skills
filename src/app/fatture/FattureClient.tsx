"use client"

import { useState } from "react"
import { createInvoice, updateInvoice, updateInvoiceStatus, deleteInvoice } from "@/lib/actions/invoices"
import { Modal } from "@/components/ui/Modal"
import { formatDate, formatCurrency } from "@/lib/utils"

type Client = { id: string; name: string }
type Invoice = {
  id: string
  clientId: string
  client: Client
  description: string
  amount: number
  dueDate: Date | null
  status: string
  notes: string | null
  createdAt: Date
}

type InvoiceFormData = {
  clientId: string
  description: string
  amount: number
  dueDate?: string
  notes?: string
}

function statusBadge(status: string) {
  if (status === "fatturata") return "bg-green-100 text-green-800"
  return "bg-amber-100 text-amber-800"
}

function statusLabel(status: string) {
  if (status === "fatturata") return "Fatturata"
  return "Da fatturare"
}

function InvoiceForm({
  clients,
  initial,
  onSave,
  onCancel,
}: {
  clients: Client[]
  initial?: Partial<Invoice>
  onSave: (data: InvoiceFormData) => Promise<void>
  onCancel: () => void
}) {
  const [loading, setLoading] = useState(false)

  function formatDateInput(d: Date | null | undefined) {
    if (!d) return ""
    const date = new Date(d)
    return date.toISOString().split("T")[0]
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setLoading(true)
    const form = e.currentTarget
    const get = (name: string) => (form.elements.namedItem(name) as HTMLInputElement)?.value
    await onSave({
      clientId: get("clientId"),
      description: get("description"),
      amount: parseFloat(get("amount")) || 0,
      dueDate: get("dueDate") || undefined,
      notes: get("notes") || undefined,
    })
    setLoading(false)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Cliente *</label>
        <select name="clientId" required defaultValue={initial?.clientId ?? ""} className="input">
          <option value="">Seleziona cliente</option>
          {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Descrizione *</label>
        <input name="description" required defaultValue={initial?.description ?? ""} className="input" placeholder="es. Sviluppo sito web" />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Importo (€) *</label>
          <input name="amount" type="number" min="0" step="0.01" required defaultValue={initial?.amount ?? ""} className="input" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Scadenza</label>
          <input name="dueDate" type="date" defaultValue={formatDateInput(initial?.dueDate)} className="input" />
        </div>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Note</label>
        <textarea name="notes" rows={2} defaultValue={initial?.notes ?? ""} className="input resize-none" />
      </div>
      <div className="flex gap-3 pt-2">
        <button type="submit" disabled={loading} className="btn-primary">{loading ? "Salvataggio..." : "Salva"}</button>
        <button type="button" onClick={onCancel} className="btn-secondary">Annulla</button>
      </div>
    </form>
  )
}

export function FattureClient({ invoices, clients }: { invoices: Invoice[]; clients: Client[] }) {
  const [showCreate, setShowCreate] = useState(false)
  const [editItem, setEditItem] = useState<Invoice | null>(null)
  const [filter, setFilter] = useState("all")

  const filtered = invoices.filter((i) => filter === "all" || i.status === filter)
  const totalDa = invoices.filter((i) => i.status === "da_fatturare").reduce((s, i) => s + i.amount, 0)
  const totalFatt = invoices.filter((i) => i.status === "fatturata").reduce((s, i) => s + i.amount, 0)

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Fatture</h1>
          <p className="text-gray-500 text-sm mt-1">
            Da fatturare: {formatCurrency(totalDa)} · Fatturate: {formatCurrency(totalFatt)}
          </p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Nuova
        </button>
      </div>

      <div className="flex gap-2 mb-6">
        {[
          { value: "all", label: "Tutte" },
          { value: "da_fatturare", label: "Da fatturare" },
          { value: "fatturata", label: "Fatturate" },
        ].map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
              filter === f.value
                ? "bg-indigo-600 text-white"
                : "bg-white text-gray-600 hover:bg-gray-100 border border-gray-200"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        {filtered.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <p>Nessuna fattura trovata</p>
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Cliente</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Descrizione</th>
                <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase">Importo</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Scadenza</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Stato</th>
                <th className="px-6 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map((inv) => {
                const overdue = inv.status === "da_fatturare" && inv.dueDate && new Date(inv.dueDate) < new Date()
                return (
                  <tr key={inv.id} className={`hover:bg-gray-50 transition-colors ${overdue ? "bg-red-50/40" : ""}`}>
                    <td className="px-6 py-4 text-sm font-medium text-gray-900">{inv.client.name}</td>
                    <td className="px-6 py-4 text-sm text-gray-600 max-w-xs truncate">{inv.description}</td>
                    <td className="px-6 py-4 text-sm font-semibold text-right text-gray-900">{formatCurrency(inv.amount)}</td>
                    <td className="px-6 py-4 text-sm">
                      <span className={overdue ? "text-red-600 font-medium" : "text-gray-500"}>
                        {inv.dueDate ? formatDate(inv.dueDate) : "—"}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium ${statusBadge(inv.status)}`}>
                        {statusLabel(inv.status)}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2 justify-end">
                        {inv.status === "da_fatturare" ? (
                          <button
                            onClick={() => updateInvoiceStatus(inv.id, "fatturata")}
                            className="text-xs px-3 py-1 rounded-md bg-green-100 text-green-700 hover:bg-green-200 font-medium transition-colors"
                          >
                            Fatturata
                          </button>
                        ) : (
                          <button
                            onClick={() => updateInvoiceStatus(inv.id, "da_fatturare")}
                            className="text-xs px-3 py-1 rounded-md bg-gray-100 text-gray-600 hover:bg-gray-200 font-medium transition-colors"
                          >
                            Riapri
                          </button>
                        )}
                        <button onClick={() => setEditItem(inv)} className="text-gray-400 hover:text-indigo-600 transition-colors" title="Modifica">
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </button>
                        <button
                          onClick={async () => { if (confirm("Eliminare questa fattura?")) await deleteInvoice(inv.id) }}
                          className="text-gray-400 hover:text-red-600 transition-colors"
                          title="Elimina"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Nuova fattura">
        <InvoiceForm
          clients={clients}
          onSave={async (data) => { await createInvoice(data); setShowCreate(false) }}
          onCancel={() => setShowCreate(false)}
        />
      </Modal>

      <Modal open={!!editItem} onClose={() => setEditItem(null)} title="Modifica fattura">
        {editItem && (
          <InvoiceForm
            clients={clients}
            initial={editItem}
            onSave={async (data) => { await updateInvoice(editItem.id, data); setEditItem(null) }}
            onCancel={() => setEditItem(null)}
          />
        )}
      </Modal>
    </div>
  )
}
