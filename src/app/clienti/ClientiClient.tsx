"use client"

import { useState } from "react"
import { createClient, updateClient, deleteClient } from "@/lib/actions/clients"
import { Badge, clientStatusBadge } from "@/components/ui/Badge"
import { Modal } from "@/components/ui/Modal"
import { formatDate } from "@/lib/utils"

type Client = {
  id: string
  name: string
  company: string | null
  email: string | null
  phone: string | null
  notes: string | null
  status: string
  stage: string | null
  createdAt: Date
}

const stages = [
  { value: "nuovo", label: "Nuovo" },
  { value: "contattato", label: "Contattato" },
  { value: "proposta_inviata", label: "Proposta inviata" },
  { value: "negoziazione", label: "Negoziazione" },
  { value: "chiuso_vinto", label: "Chiuso vinto" },
  { value: "chiuso_perso", label: "Chiuso perso" },
]

const stageLabel = (s: string | null) => stages.find((x) => x.value === s)?.label ?? s ?? "-"

function ClientForm({
  initial,
  onSave,
  onCancel,
}: {
  initial?: Partial<Client>
  onSave: (data: Omit<Client, "id" | "createdAt">) => void
  onCancel: () => void
}) {
  const [status, setStatus] = useState(initial?.status ?? "lead")
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setLoading(true)
    const form = e.currentTarget
    const get = (name: string) => (form.elements.namedItem(name) as HTMLInputElement)?.value || undefined
    await onSave({
      name: get("name") ?? "",
      company: get("company") ?? null,
      email: get("email") ?? null,
      phone: get("phone") ?? null,
      notes: get("notes") ?? null,
      status,
      stage: status === "lead" ? (get("stage") ?? null) : null,
    })
    setLoading(false)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1">Nome *</label>
          <input name="name" required defaultValue={initial?.name} className="input" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Azienda</label>
          <input name="company" defaultValue={initial?.company ?? ""} className="input" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Stato</label>
          <select value={status} onChange={(e) => setStatus(e.target.value)} className="input">
            <option value="lead">Lead</option>
            <option value="active">Cliente attivo</option>
            <option value="inactive">Inattivo</option>
          </select>
        </div>
        {status === "lead" && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Fase pipeline</label>
            <select name="stage" defaultValue={initial?.stage ?? "nuovo"} className="input">
              {stages.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
        )}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
          <input name="email" type="email" defaultValue={initial?.email ?? ""} className="input" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Telefono</label>
          <input name="phone" defaultValue={initial?.phone ?? ""} className="input" />
        </div>
        <div className="col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1">Note</label>
          <textarea name="notes" rows={3} defaultValue={initial?.notes ?? ""} className="input resize-none" />
        </div>
      </div>
      <div className="flex gap-3 pt-2">
        <button type="submit" disabled={loading} className="btn-primary">
          {loading ? "Salvataggio..." : "Salva"}
        </button>
        <button type="button" onClick={onCancel} className="btn-secondary">Annulla</button>
      </div>
    </form>
  )
}

export function ClientiClient({ clients }: { clients: Client[] }) {
  const [showCreate, setShowCreate] = useState(false)
  const [editItem, setEditItem] = useState<Client | null>(null)
  const [filter, setFilter] = useState("all")
  const [search, setSearch] = useState("")

  const filtered = clients.filter((c) => {
    if (filter !== "all" && c.status !== filter) return false
    if (search && !`${c.name} ${c.company ?? ""}`.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  async function handleCreate(data: Omit<Client, "id" | "createdAt">) {
    await createClient({ ...data, company: data.company ?? undefined, email: data.email ?? undefined, phone: data.phone ?? undefined, notes: data.notes ?? undefined, stage: data.stage ?? undefined })
    setShowCreate(false)
  }

  async function handleEdit(data: Omit<Client, "id" | "createdAt">) {
    if (!editItem) return
    await updateClient(editItem.id, { ...data, company: data.company ?? undefined, email: data.email ?? undefined, phone: data.phone ?? undefined, notes: data.notes ?? undefined, stage: data.stage ?? undefined })
    setEditItem(null)
  }

  async function handleDelete(id: string) {
    if (!confirm("Eliminare questo cliente?")) return
    await deleteClient(id)
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Clienti & Lead</h1>
          <p className="text-gray-500 text-sm mt-1">{clients.length} totali</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Nuovo
        </button>
      </div>

      <div className="flex gap-4 mb-6">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Cerca per nome o azienda..."
          className="input max-w-xs"
        />
        <select value={filter} onChange={(e) => setFilter(e.target.value)} className="input max-w-xs">
          <option value="all">Tutti</option>
          <option value="lead">Solo lead</option>
          <option value="active">Solo clienti</option>
          <option value="inactive">Inattivi</option>
        </select>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        {filtered.length === 0 ? (
          <div className="text-center py-16 text-gray-400">
            <svg className="w-12 h-12 mx-auto mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <p>Nessun cliente trovato</p>
          </div>
        ) : (
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-100">
              <tr>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Nome</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Email</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Stato</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Fase</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Aggiunto</th>
                <th className="px-6 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map((c) => {
                const b = clientStatusBadge(c.status)
                return (
                  <tr key={c.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-6 py-4">
                      <p className="text-sm font-medium text-gray-900">{c.name}</p>
                      {c.company && <p className="text-xs text-gray-500">{c.company}</p>}
                    </td>
                    <td className="px-6 py-4 text-sm text-gray-600">{c.email ?? "-"}</td>
                    <td className="px-6 py-4"><Badge variant={b.variant}>{b.label}</Badge></td>
                    <td className="px-6 py-4 text-sm text-gray-600">{c.status === "lead" ? stageLabel(c.stage) : "-"}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">{formatDate(c.createdAt)}</td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2 justify-end">
                        <button onClick={() => setEditItem(c)} className="text-gray-400 hover:text-indigo-600 transition-colors">
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </button>
                        <button onClick={() => handleDelete(c.id)} className="text-gray-400 hover:text-red-600 transition-colors">
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

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Nuovo cliente / lead">
        <ClientForm onSave={handleCreate} onCancel={() => setShowCreate(false)} />
      </Modal>

      <Modal open={!!editItem} onClose={() => setEditItem(null)} title="Modifica cliente">
        {editItem && <ClientForm initial={editItem} onSave={handleEdit} onCancel={() => setEditItem(null)} />}
      </Modal>
    </div>
  )
}
