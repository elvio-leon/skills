"use client"

import { useState } from "react"
import { createQuote, updateQuote, deleteQuote } from "@/lib/actions/quotes"
import { Badge, proposalStatusBadge } from "@/components/ui/Badge"
import { Modal } from "@/components/ui/Modal"
import { formatDate, formatCurrency } from "@/lib/utils"

type Client = { id: string; name: string; company: string | null; email: string | null }
type QuoteItem = { id: string; description: string; quantity: number; unitPrice: number; total: number }
type Quote = {
  id: string
  title: string
  clientId: string
  client: Client
  status: string
  notes: string | null
  subtotal: number
  tax: number
  total: number
  items: QuoteItem[]
  createdAt: Date
}

type LineItem = { description: string; quantity: number; unitPrice: number; total: number }

function QuoteForm({
  initial,
  clients,
  onSave,
  onCancel,
}: {
  initial?: Partial<Quote>
  clients: Client[]
  onSave: (data: Record<string, unknown>) => void
  onCancel: () => void
}) {
  const [items, setItems] = useState<LineItem[]>(
    initial?.items?.map((i) => ({ description: i.description, quantity: i.quantity, unitPrice: i.unitPrice, total: i.total })) ??
      [{ description: "", quantity: 1, unitPrice: 0, total: 0 }]
  )
  const [tax, setTax] = useState(initial?.tax ?? 22)
  const [loading, setLoading] = useState(false)

  const subtotal = items.reduce((s, i) => s + i.total, 0)
  const total = subtotal * (1 + tax / 100)

  function updateItem(index: number, field: keyof LineItem, value: string | number) {
    setItems((prev) => {
      const next = [...prev]
      const item = { ...next[index], [field]: value }
      if (field === "quantity" || field === "unitPrice") {
        item.total = item.quantity * item.unitPrice
      }
      next[index] = item
      return next
    })
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setLoading(true)
    const form = e.currentTarget
    const get = (name: string) => (form.elements.namedItem(name) as HTMLInputElement)?.value
    await onSave({
      title: get("title"),
      clientId: get("clientId"),
      status: get("status"),
      tax,
      notes: get("notes") || undefined,
      items,
    })
    setLoading(false)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="grid grid-cols-2 gap-4">
        <div className="col-span-2">
          <label className="block text-sm font-medium text-gray-700 mb-1">Titolo preventivo *</label>
          <input name="title" required defaultValue={initial?.title} className="input" placeholder="es. Sviluppo sito web aziendale" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Cliente *</label>
          <select name="clientId" required defaultValue={initial?.clientId} className="input">
            <option value="">Seleziona cliente</option>
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}{c.company ? ` (${c.company})` : ""}</option>)}
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
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium text-gray-700">Voci del preventivo</label>
          <button
            type="button"
            onClick={() => setItems((p) => [...p, { description: "", quantity: 1, unitPrice: 0, total: 0 }])}
            className="text-sm text-indigo-600 hover:text-indigo-800 font-medium"
          >
            + Aggiungi voce
          </button>
        </div>
        <div className="space-y-2">
          <div className="grid grid-cols-12 gap-2 text-xs text-gray-500 px-1">
            <span className="col-span-5">Descrizione</span>
            <span className="col-span-2 text-right">Qtà</span>
            <span className="col-span-2 text-right">Prezzo unitario</span>
            <span className="col-span-2 text-right">Totale</span>
            <span className="col-span-1"></span>
          </div>
          {items.map((item, i) => (
            <div key={i} className="grid grid-cols-12 gap-2 items-center">
              <input
                className="input col-span-5 text-sm"
                placeholder="es. Progettazione UI"
                value={item.description}
                onChange={(e) => updateItem(i, "description", e.target.value)}
              />
              <input
                className="input col-span-2 text-sm text-right"
                type="number"
                min="0"
                step="0.01"
                value={item.quantity}
                onChange={(e) => updateItem(i, "quantity", parseFloat(e.target.value) || 0)}
              />
              <input
                className="input col-span-2 text-sm text-right"
                type="number"
                min="0"
                step="0.01"
                value={item.unitPrice}
                onChange={(e) => updateItem(i, "unitPrice", parseFloat(e.target.value) || 0)}
              />
              <p className="col-span-2 text-sm font-medium text-right">{formatCurrency(item.total)}</p>
              <button
                type="button"
                onClick={() => setItems((p) => p.filter((_, idx) => idx !== i))}
                disabled={items.length === 1}
                className="col-span-1 text-gray-400 hover:text-red-500 disabled:opacity-30"
              >
                <svg className="w-4 h-4 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          ))}
        </div>

        <div className="mt-4 pt-4 border-t border-gray-100">
          <div className="flex items-center justify-end gap-4 mb-3">
            <label className="text-sm text-gray-600">IVA %</label>
            <input
              type="number"
              value={tax}
              onChange={(e) => setTax(parseFloat(e.target.value) || 0)}
              className="input w-24 text-right text-sm"
            />
          </div>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between text-gray-600"><span>Subtotale</span><span>{formatCurrency(subtotal)}</span></div>
            <div className="flex justify-between text-gray-600"><span>IVA {tax}%</span><span>{formatCurrency(subtotal * tax / 100)}</span></div>
            <div className="flex justify-between font-bold text-gray-900 text-base pt-1 border-t border-gray-200 mt-2"><span>Totale</span><span>{formatCurrency(total)}</span></div>
          </div>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Note / Condizioni</label>
        <textarea name="notes" rows={3} defaultValue={initial?.notes ?? ""} className="input resize-none" placeholder="Termini di pagamento, validità del preventivo, ecc." />
      </div>

      <div className="flex gap-3 pt-2">
        <button type="submit" disabled={loading} className="btn-primary">{loading ? "Salvataggio..." : "Salva preventivo"}</button>
        <button type="button" onClick={onCancel} className="btn-secondary">Annulla</button>
      </div>
    </form>
  )
}

function QuoteDetail({ quote }: { quote: Quote }) {
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-4 p-4 bg-gray-50 rounded-xl text-sm">
        <div><span className="text-gray-500">Cliente:</span> <span className="font-medium">{quote.client.name}</span></div>
        {quote.client.company && <div><span className="text-gray-500">Azienda:</span> <span>{quote.client.company}</span></div>}
        {quote.client.email && <div><span className="text-gray-500">Email:</span> <span>{quote.client.email}</span></div>}
        <div><span className="text-gray-500">Data:</span> <span>{formatDate(quote.createdAt)}</span></div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Voci del preventivo</h3>
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left px-3 py-2 font-medium text-gray-600 rounded-l-lg">Descrizione</th>
              <th className="text-right px-3 py-2 font-medium text-gray-600">Qtà</th>
              <th className="text-right px-3 py-2 font-medium text-gray-600">Prezzo</th>
              <th className="text-right px-3 py-2 font-medium text-gray-600 rounded-r-lg">Totale</th>
            </tr>
          </thead>
          <tbody>
            {quote.items.map((item, i) => (
              <tr key={item.id} className="border-t border-gray-100">
                <td className="px-3 py-2.5">{item.description}</td>
                <td className="px-3 py-2.5 text-right text-gray-600">{item.quantity}</td>
                <td className="px-3 py-2.5 text-right text-gray-600">{formatCurrency(item.unitPrice)}</td>
                <td className="px-3 py-2.5 text-right font-medium">{formatCurrency(item.total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="border-t border-gray-200 pt-4 space-y-1.5 text-sm">
        <div className="flex justify-between text-gray-600"><span>Subtotale</span><span>{formatCurrency(quote.subtotal)}</span></div>
        <div className="flex justify-between text-gray-600"><span>IVA {quote.tax}%</span><span>{formatCurrency(quote.subtotal * quote.tax / 100)}</span></div>
        <div className="flex justify-between font-bold text-gray-900 text-lg pt-2 border-t border-gray-200 mt-2"><span>Totale</span><span>{formatCurrency(quote.total)}</span></div>
      </div>

      {quote.notes && (
        <div className="p-4 bg-amber-50 rounded-xl">
          <p className="text-xs font-semibold text-amber-700 mb-1">Note</p>
          <p className="text-sm text-amber-900">{quote.notes}</p>
        </div>
      )}
    </div>
  )
}

export function PreventiviClient({ quotes, clients }: { quotes: Quote[]; clients: Client[] }) {
  const [showCreate, setShowCreate] = useState(false)
  const [editItem, setEditItem] = useState<Quote | null>(null)
  const [viewItem, setViewItem] = useState<Quote | null>(null)
  const [filter, setFilter] = useState("all")

  const filtered = quotes.filter((q) => filter === "all" || q.status === filter)

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Preventivi</h1>
          <p className="text-gray-500 text-sm mt-1">{quotes.length} totali</p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Nuovo preventivo
        </button>
      </div>

      <div className="flex gap-2 mb-6">
        {[
          { value: "all", label: "Tutti" },
          { value: "bozza", label: "Bozze" },
          { value: "inviata", label: "Inviati" },
          { value: "accettata", label: "Accettati" },
          { value: "rifiutata", label: "Rifiutati" },
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
            <p>Nessun preventivo trovato</p>
          </div>
        )}
        {filtered.map((q) => {
          const b = proposalStatusBadge(q.status)
          return (
            <div key={q.id} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 hover:border-indigo-200 transition-colors">
              <div className="flex items-start justify-between mb-3">
                <Badge variant={b.variant}>{b.label}</Badge>
                <div className="flex gap-2">
                  <button onClick={() => setViewItem(q)} className="text-gray-400 hover:text-indigo-600 transition-colors" title="Visualizza">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                  </button>
                  <button onClick={() => setEditItem(q)} className="text-gray-400 hover:text-indigo-600 transition-colors" title="Modifica">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                  </button>
                  <button
                    onClick={async () => { if (confirm("Eliminare questo preventivo?")) await deleteQuote(q.id) }}
                    className="text-gray-400 hover:text-red-600 transition-colors"
                    title="Elimina"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </div>
              <h3 className="font-semibold text-gray-900 mb-1">{q.title}</h3>
              <p className="text-sm text-indigo-600 mb-3">{q.client.name}</p>
              <div className="flex items-center justify-between pt-3 border-t border-gray-50">
                <span className="text-xs text-gray-400">{q.items.length} voci</span>
                <span className="text-lg font-bold text-gray-900">{formatCurrency(q.total)}</span>
              </div>
            </div>
          )
        })}
      </div>

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Nuovo preventivo" size="xl">
        <QuoteForm
          clients={clients}
          onSave={async (data) => { await createQuote(data as Parameters<typeof createQuote>[0]); setShowCreate(false) }}
          onCancel={() => setShowCreate(false)}
        />
      </Modal>

      <Modal open={!!editItem} onClose={() => setEditItem(null)} title="Modifica preventivo" size="xl">
        {editItem && (
          <QuoteForm
            initial={editItem}
            clients={clients}
            onSave={async (data) => { await updateQuote(editItem.id, data as Parameters<typeof updateQuote>[1]); setEditItem(null) }}
            onCancel={() => setEditItem(null)}
          />
        )}
      </Modal>

      <Modal open={!!viewItem} onClose={() => setViewItem(null)} title={viewItem?.title ?? "Preventivo"} size="lg">
        {viewItem && <QuoteDetail quote={viewItem} />}
      </Modal>
    </div>
  )
}
