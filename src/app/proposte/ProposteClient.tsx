"use client"

import { useState } from "react"
import { createProposal, updateProposal, deleteProposal } from "@/lib/actions/proposals"
import { Badge, proposalStatusBadge } from "@/components/ui/Badge"
import { Modal } from "@/components/ui/Modal"
import { formatDate, formatCurrency, formatDateInput } from "@/lib/utils"

type Client = { id: string; name: string }
type Proposal = {
  id: string
  title: string
  clientId: string
  client: Client
  status: string
  amount: number | null
  expiryDate: Date | null
  notes: string | null
  createdAt: Date
}

function ProposalForm({
  initial,
  clients,
  onSave,
  onCancel,
}: {
  initial?: Partial<Proposal>
  clients: Client[]
  onSave: (data: Record<string, unknown>) => void
  onCancel: () => void
}) {
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setLoading(true)
    const form = e.currentTarget
    const get = (name: string) => (form.elements.namedItem(name) as HTMLInputElement)?.value || undefined
    await onSave({
      title: get("title"),
      clientId: get("clientId"),
      status: get("status"),
      amount: get("amount") ? parseFloat(get("amount")!) : undefined,
      expiryDate: get("expiryDate"),
      notes: get("notes"),
    })
    setLoading(false)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1">Titolo *</label>
          <input name="title" required defaultValue={initial?.title} className="input" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Cliente *</label>
          <select name="clientId" required defaultValue={initial?.clientId} className="input">
            <option value="">Seleziona</option>
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Stato</label>
          <select name="status" defaultValue={initial?.status ?? "bozza"} className="input">
            <option value="bozza">Bozza</option>
            <option value="inviata">Inviata</option>
            <option value="accettata">Accettata</option>
            <option value="rifiutata">Rifiutata</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Importo (€)</label>
          <input name="amount" type="number" step="0.01" defaultValue={initial?.amount ?? ""} className="input" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Scadenza</label>
          <input name="expiryDate" type="date" defaultValue={formatDateInput(initial?.expiryDate)} className="input" />
        </div>
        <div className="col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1">Note</label>
          <textarea name="notes" rows={3} defaultValue={initial?.notes ?? ""} className="input resize-none" />
        </div>
      </div>
      <div className="flex gap-3 pt-2">
        <button type="submit" disabled={loading} className="btn-primary">{loading ? "Salvataggio..." : "Salva"}</button>
        <button type="button" onClick={onCancel} className="btn-secondary">Annulla</button>
      </div>
    </form>
  )
}

export function ProposteClient({ proposals, clients }: { proposals: Proposal[]; clients: Client[] }) {
  const [showCreate, setShowCreate] = useState(false)
  const [editItem, setEditItem] = useState<Proposal | null>(null)
  const [filter, setFilter] = useState("all")

  const filtered = proposals.filter((p) => filter === "all" || p.status === filter)

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Proposte commerciali</h1>
          <p className="text-gray-500 text-sm mt-1">{proposals.length} totali</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Nuova proposta
        </button>
      </div>

      <div className="flex gap-2 mb-6">
        {[
          { value: "all", label: "Tutte" },
          { value: "bozza", label: "Bozze" },
          { value: "inviata", label: "Inviate" },
          { value: "accettata", label: "Accettate" },
          { value: "rifiutata", label: "Rifiutate" },
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
            <p>Nessuna proposta trovata</p>
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Titolo</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Cliente</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Stato</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Scadenza</th>
                <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase">Importo</th>
                <th className="px-6 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map((p) => {
                const b = proposalStatusBadge(p.status)
                const expired = p.status === "inviata" && p.expiryDate && new Date(p.expiryDate) < new Date()
                return (
                  <tr key={p.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4">
                      <p className="text-sm font-medium text-gray-900">{p.title}</p>
                      <p className="text-xs text-gray-500">{formatDate(p.createdAt)}</p>
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-700">{p.client.name}</td>
                    <td className="px-6 py-4"><Badge variant={b.variant}>{b.label}</Badge></td>
                    <td className="px-6 py-4 text-sm">
                      <span className={expired ? "text-red-600 font-medium" : "text-gray-500"}>{formatDate(p.expiryDate)}</span>
                    </td>
                    <td className="px-6 py-4 text-sm font-semibold text-right">{p.amount ? formatCurrency(p.amount) : "-"}</td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2 justify-end">
                        <button onClick={() => setEditItem(p)} className="text-gray-400 hover:text-indigo-600 transition-colors">
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </button>
                        <button
                          onClick={async () => { if (confirm("Eliminare?")) await deleteProposal(p.id) }}
                          className="text-gray-400 hover:text-red-600 transition-colors"
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

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Nuova proposta">
        <ProposalForm
          clients={clients}
          onSave={async (data) => { await createProposal(data as Parameters<typeof createProposal>[0]); setShowCreate(false) }}
          onCancel={() => setShowCreate(false)}
        />
      </Modal>

      <Modal open={!!editItem} onClose={() => setEditItem(null)} title="Modifica proposta">
        {editItem && (
          <ProposalForm
            initial={editItem}
            clients={clients}
            onSave={async (data) => { await updateProposal(editItem.id, data as Parameters<typeof updateProposal>[1]); setEditItem(null) }}
            onCancel={() => setEditItem(null)}
          />
        )}
      </Modal>
    </div>
  )
}
