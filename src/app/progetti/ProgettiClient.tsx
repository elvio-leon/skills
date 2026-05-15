"use client"

import { useState } from "react"
import { createProject, updateProject, deleteProject } from "@/lib/actions/projects"
import { Badge, projectStatusBadge } from "@/components/ui/Badge"
import { Modal } from "@/components/ui/Modal"
import { formatDate, formatCurrency, formatDateInput } from "@/lib/utils"

type Client = { id: string; name: string; company: string | null }
type Project = {
  id: string
  name: string
  description: string | null
  status: string
  startDate: Date | null
  endDate: Date | null
  budget: number | null
  clientId: string
  client: Client
  createdAt: Date
}

function ProjectForm({
  initial,
  clients,
  onSave,
  onCancel,
}: {
  initial?: Partial<Project>
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
      name: get("name"),
      description: get("description"),
      status: get("status"),
      startDate: get("startDate"),
      endDate: get("endDate"),
      budget: get("budget") ? parseFloat(get("budget")!) : undefined,
      clientId: get("clientId"),
    })
    setLoading(false)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1">Nome progetto *</label>
          <input name="name" required defaultValue={initial?.name} className="input" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Cliente *</label>
          <select name="clientId" required defaultValue={initial?.clientId} className="input">
            <option value="">Seleziona cliente</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>{c.name}{c.company ? ` (${c.company})` : ""}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Stato</label>
          <select name="status" defaultValue={initial?.status ?? "in_corso"} className="input">
            <option value="in_corso">In corso</option>
            <option value="completato">Completato</option>
            <option value="in_pausa">In pausa</option>
            <option value="annullato">Annullato</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Data inizio</label>
          <input name="startDate" type="date" defaultValue={formatDateInput(initial?.startDate)} className="input" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Data fine prevista</label>
          <input name="endDate" type="date" defaultValue={formatDateInput(initial?.endDate)} className="input" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Budget (€)</label>
          <input name="budget" type="number" step="0.01" defaultValue={initial?.budget ?? ""} className="input" />
        </div>
        <div className="col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1">Descrizione</label>
          <textarea name="description" rows={3} defaultValue={initial?.description ?? ""} className="input resize-none" />
        </div>
      </div>
      <div className="flex gap-3 pt-2">
        <button type="submit" disabled={loading} className="btn-primary">{loading ? "Salvataggio..." : "Salva"}</button>
        <button type="button" onClick={onCancel} className="btn-secondary">Annulla</button>
      </div>
    </form>
  )
}

export function ProgettiClient({ projects, clients }: { projects: Project[]; clients: Client[] }) {
  const [showCreate, setShowCreate] = useState(false)
  const [editItem, setEditItem] = useState<Project | null>(null)
  const [filter, setFilter] = useState("all")

  const filtered = projects.filter((p) => filter === "all" || p.status === filter)

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Progetti</h1>
          <p className="text-gray-500 text-sm mt-1">{projects.length} totali</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Nuovo progetto
        </button>
      </div>

      <div className="flex gap-2 mb-6">
        {[
          { value: "all", label: "Tutti" },
          { value: "in_corso", label: "In corso" },
          { value: "completato", label: "Completati" },
          { value: "in_pausa", label: "In pausa" },
          { value: "annullato", label: "Annullati" },
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

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {filtered.length === 0 && (
          <div className="col-span-3 text-center py-16 text-gray-400">
            <p>Nessun progetto trovato</p>
          </div>
        )}
        {filtered.map((p) => {
          const b = projectStatusBadge(p.status)
          return (
            <div key={p.id} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
              <div className="flex items-start justify-between mb-3">
                <Badge variant={b.variant}>{b.label}</Badge>
                <div className="flex gap-2">
                  <button onClick={() => setEditItem(p)} className="text-gray-400 hover:text-indigo-600 transition-colors">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                  </button>
                  <button
                    onClick={async () => {
                      if (confirm("Eliminare questo progetto?")) await deleteProject(p.id)
                    }}
                    className="text-gray-400 hover:text-red-600 transition-colors"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </div>
              <h3 className="font-semibold text-gray-900 mb-1">{p.name}</h3>
              <p className="text-sm text-indigo-600 mb-2">{p.client.name}</p>
              {p.description && <p className="text-xs text-gray-500 mb-3 line-clamp-2">{p.description}</p>}
              <div className="flex items-center justify-between text-xs text-gray-500 mt-3 pt-3 border-t border-gray-50">
                <span>{p.startDate ? formatDate(p.startDate) : "—"} → {p.endDate ? formatDate(p.endDate) : "—"}</span>
                {p.budget && <span className="font-medium text-gray-700">{formatCurrency(p.budget)}</span>}
              </div>
            </div>
          )
        })}
      </div>

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Nuovo progetto">
        <ProjectForm
          clients={clients}
          onSave={async (data) => { await createProject(data as Parameters<typeof createProject>[0]); setShowCreate(false) }}
          onCancel={() => setShowCreate(false)}
        />
      </Modal>

      <Modal open={!!editItem} onClose={() => setEditItem(null)} title="Modifica progetto">
        {editItem && (
          <ProjectForm
            initial={editItem}
            clients={clients}
            onSave={async (data) => { await updateProject(editItem.id, data as Parameters<typeof updateProject>[1]); setEditItem(null) }}
            onCancel={() => setEditItem(null)}
          />
        )}
      </Modal>
    </div>
  )
}
