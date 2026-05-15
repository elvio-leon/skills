"use client"

import { useState } from "react"
import { createTimeLog, updateTimeLog, deleteTimeLog } from "@/lib/actions/timelogs"
import { Modal } from "@/components/ui/Modal"
import { formatDate, formatDateInput } from "@/lib/utils"
import { format, startOfMonth, endOfMonth } from "date-fns"
import { it } from "date-fns/locale"

type Client = { id: string; name: string }
type Project = { id: string; name: string; clientId: string }
type TimeLog = {
  id: string
  date: Date
  hours: number
  description: string | null
  projectId: string | null
  clientId: string
  client: Client
  project: Project | null
}

function TimeLogForm({
  initial,
  clients,
  projects,
  onSave,
  onCancel,
}: {
  initial?: Partial<TimeLog>
  clients: Client[]
  projects: Project[]
  onSave: (data: Record<string, unknown>) => void
  onCancel: () => void
}) {
  const [selectedClient, setSelectedClient] = useState(initial?.clientId ?? "")
  const [loading, setLoading] = useState(false)
  const clientProjects = projects.filter((p) => p.clientId === selectedClient)

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setLoading(true)
    const form = e.currentTarget
    const get = (name: string) => (form.elements.namedItem(name) as HTMLInputElement)?.value || undefined
    await onSave({
      date: get("date"),
      hours: parseFloat(get("hours") ?? "0"),
      description: get("description"),
      clientId: selectedClient,
      projectId: get("projectId") || undefined,
    })
    setLoading(false)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Data *</label>
          <input name="date" type="date" required defaultValue={formatDateInput(initial?.date) || formatDateInput(new Date())} className="input" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Ore *</label>
          <input name="hours" type="number" step="0.25" min="0.25" required defaultValue={initial?.hours} className="input" placeholder="es. 2.5" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Cliente *</label>
          <select required value={selectedClient} onChange={(e) => setSelectedClient(e.target.value)} className="input">
            <option value="">Seleziona cliente</option>
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Progetto</label>
          <select name="projectId" defaultValue={initial?.projectId ?? ""} className="input" disabled={!selectedClient}>
            <option value="">Nessun progetto</option>
            {clientProjects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
        </div>
        <div className="col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1">Attività svolta</label>
          <input name="description" defaultValue={initial?.description ?? ""} className="input" placeholder="es. Sviluppo feature login" />
        </div>
      </div>
      <div className="flex gap-3 pt-2">
        <button type="submit" disabled={loading} className="btn-primary">{loading ? "Salvataggio..." : "Salva"}</button>
        <button type="button" onClick={onCancel} className="btn-secondary">Annulla</button>
      </div>
    </form>
  )
}

export function TimeTrackingClient({
  timeLogs,
  clients,
  projects,
}: {
  timeLogs: TimeLog[]
  clients: Client[]
  projects: Project[]
}) {
  const [showCreate, setShowCreate] = useState(false)
  const [editItem, setEditItem] = useState<TimeLog | null>(null)
  const [filterClient, setFilterClient] = useState("all")

  const now = new Date()
  const monthStart = startOfMonth(now)
  const monthEnd = endOfMonth(now)

  const filtered = timeLogs.filter((t) => filterClient === "all" || t.clientId === filterClient)
  const totalHours = filtered.reduce((s, t) => s + t.hours, 0)
  const monthHours = filtered
    .filter((t) => new Date(t.date) >= monthStart && new Date(t.date) <= monthEnd)
    .reduce((s, t) => s + t.hours, 0)

  const byClient = clients.map((c) => ({
    ...c,
    hours: timeLogs.filter((t) => t.clientId === c.id).reduce((s, t) => s + t.hours, 0),
  })).filter((c) => c.hours > 0)

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Time Tracking</h1>
          <p className="text-gray-500 text-sm mt-1">Totale: {totalHours.toFixed(1)}h · Questo mese: {monthHours.toFixed(1)}h</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Registra ore
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-6">
        <div className="lg:col-span-3">
          <div className="flex gap-2 mb-4">
            <select value={filterClient} onChange={(e) => setFilterClient(e.target.value)} className="input max-w-xs">
              <option value="all">Tutti i clienti</option>
              {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>

          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            {filtered.length === 0 ? (
              <div className="text-center py-16 text-gray-400">
                <svg className="w-12 h-12 mx-auto mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p>Nessuna registrazione</p>
              </div>
            ) : (
              <table className="w-full">
                <thead className="bg-gray-50 border-b border-gray-100">
                  <tr>
                    <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Data</th>
                    <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Cliente</th>
                    <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Progetto</th>
                    <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Attività</th>
                    <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase tracking-wider">Ore</th>
                    <th className="px-6 py-3"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {filtered.map((t) => (
                    <tr key={t.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-3 text-sm text-gray-600">{formatDate(t.date)}</td>
                      <td className="px-6 py-3 text-sm font-medium text-gray-900">{t.client.name}</td>
                      <td className="px-6 py-3 text-sm text-gray-600">{t.project?.name ?? "-"}</td>
                      <td className="px-6 py-3 text-sm text-gray-600">{t.description ?? "-"}</td>
                      <td className="px-6 py-3 text-sm font-semibold text-right text-indigo-700">{t.hours}h</td>
                      <td className="px-6 py-3">
                        <div className="flex items-center gap-2 justify-end">
                          <button onClick={() => setEditItem(t)} className="text-gray-400 hover:text-indigo-600 transition-colors">
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          <button
                            onClick={async () => { if (confirm("Eliminare?")) await deleteTimeLog(t.id) }}
                            className="text-gray-400 hover:text-red-600 transition-colors"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">Ore per cliente</h3>
            {byClient.length === 0 ? (
              <p className="text-xs text-gray-400">Nessun dato</p>
            ) : (
              <div className="space-y-2">
                {byClient.sort((a, b) => b.hours - a.hours).map((c) => (
                  <div key={c.id} className="flex items-center justify-between">
                    <p className="text-xs text-gray-600 truncate flex-1">{c.name}</p>
                    <p className="text-xs font-semibold text-indigo-700 ml-2">{c.hours.toFixed(1)}h</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Registra ore">
        <TimeLogForm
          clients={clients}
          projects={projects}
          onSave={async (data) => { await createTimeLog(data as Parameters<typeof createTimeLog>[0]); setShowCreate(false) }}
          onCancel={() => setShowCreate(false)}
        />
      </Modal>

      <Modal open={!!editItem} onClose={() => setEditItem(null)} title="Modifica registrazione">
        {editItem && (
          <TimeLogForm
            initial={editItem}
            clients={clients}
            projects={projects}
            onSave={async (data) => { await updateTimeLog(editItem.id, data as Parameters<typeof updateTimeLog>[1]); setEditItem(null) }}
            onCancel={() => setEditItem(null)}
          />
        )}
      </Modal>
    </div>
  )
}
