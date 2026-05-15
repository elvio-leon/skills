"use client"

import { useState } from "react"
import { createInvoice, updateInvoiceStatus, deleteInvoice } from "@/lib/actions/invoices"
import { Badge, invoiceStatusBadge } from "@/components/ui/Badge"
import { Modal } from "@/components/ui/Modal"
import { formatDate, formatCurrency, formatDateInput } from "@/lib/utils"

type Client = { id: string; name: string }
type InvoiceItem = { id: string; description: string; quantity: number; unitPrice: number; total: number }
type Invoice = {
  id: string
  number: string
  clientId: string
  client: Client
  status: string
  issueDate: Date
  dueDate: Date | null
  subtotal: number
  tax: number
  total: number
  notes: string | null
  items: InvoiceItem[]
}

type LineItem = { description: string; quantity: number; unitPrice: number; total: number }

function InvoiceForm({
  clients,
  nextNumber,
  onSave,
  onCancel,
}: {
  clients: Client[]
  nextNumber: string
  onSave: (data: Parameters<typeof createInvoice>[0]) => void
  onCancel: () => void
}) {
  const [items, setItems] = useState<LineItem[]>([{ description: "", quantity: 1, unitPrice: 0, total: 0 }])
  const [tax, setTax] = useState(22)
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

  function addItem() {
    setItems((prev) => [...prev, { description: "", quantity: 1, unitPrice: 0, total: 0 }])
  }

  function removeItem(index: number) {
    setItems((prev) => prev.filter((_, i) => i !== index))
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setLoading(true)
    const form = e.currentTarget
    const get = (name: string) => (form.elements.namedItem(name) as HTMLInputElement)?.value
    await onSave({
      number: get("number"),
      clientId: get("clientId"),
      status: get("status"),
      issueDate: get("issueDate"),
      dueDate: get("dueDate") || undefined,
      tax,
      notes: get("notes") || undefined,
      items,
    })
    setLoading(false)
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">N° Fattura *</label>
          <input name="number" required defaultValue={nextNumber} className="input" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Cliente *</label>
          <select name="clientId" required className="input">
            <option value="">Seleziona</option>
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Data emissione</label>
          <input name="issueDate" type="date" defaultValue={formatDateInput(new Date())} className="input" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Scadenza</label>
          <input name="dueDate" type="date" className="input" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Stato</label>
          <select name="status" defaultValue="bozza" className="input">
            <option value="bozza">Bozza</option>
            <option value="inviata">Inviata</option>
            <option value="pagata">Pagata</option>
            <option value="scaduta">Scaduta</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">IVA %</label>
          <input type="number" value={tax} onChange={(e) => setTax(parseFloat(e.target.value) || 0)} className="input" />
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm font-medium text-gray-700">Voci</label>
          <button type="button" onClick={addItem} className="text-sm text-indigo-600 hover:text-indigo-800 font-medium">+ Aggiungi voce</button>
        </div>
        <div className="space-y-2">
          <div className="grid grid-cols-12 gap-2 text-xs text-gray-500 px-1">
            <span className="col-span-5">Descrizione</span>
            <span className="col-span-2 text-right">Qtà</span>
            <span className="col-span-2 text-right">Prezzo</span>
            <span className="col-span-2 text-right">Totale</span>
            <span className="col-span-1"></span>
          </div>
          {items.map((item, i) => (
            <div key={i} className="grid grid-cols-12 gap-2 items-center">
              <input
                className="input col-span-5 text-sm"
                placeholder="Descrizione"
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
              <button type="button" onClick={() => removeItem(i)} disabled={items.length === 1} className="col-span-1 text-gray-400 hover:text-red-500 disabled:opacity-30">
                <svg className="w-4 h-4 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          ))}
        </div>
        <div className="mt-4 pt-4 border-t border-gray-100 space-y-1 text-sm">
          <div className="flex justify-between text-gray-600">
            <span>Subtotale</span><span>{formatCurrency(subtotal)}</span>
          </div>
          <div className="flex justify-between text-gray-600">
            <span>IVA {tax}%</span><span>{formatCurrency(subtotal * tax / 100)}</span>
          </div>
          <div className="flex justify-between font-bold text-gray-900 text-base pt-1">
            <span>Totale</span><span>{formatCurrency(total)}</span>
          </div>
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Note</label>
        <textarea name="notes" rows={2} className="input resize-none" />
      </div>

      <div className="flex gap-3 pt-2">
        <button type="submit" disabled={loading} className="btn-primary">{loading ? "Salvataggio..." : "Crea fattura"}</button>
        <button type="button" onClick={onCancel} className="btn-secondary">Annulla</button>
      </div>
    </form>
  )
}

export function FattureClient({
  invoices,
  clients,
  nextNumber,
}: {
  invoices: Invoice[]
  clients: Client[]
  nextNumber: string
}) {
  const [showCreate, setShowCreate] = useState(false)
  const [filter, setFilter] = useState("all")
  const [viewInvoice, setViewInvoice] = useState<Invoice | null>(null)

  const filtered = invoices.filter((i) => filter === "all" || i.status === filter)
  const totalPaid = invoices.filter((i) => i.status === "pagata").reduce((s, i) => s + i.total, 0)
  const totalPending = invoices.filter((i) => i.status === "inviata").reduce((s, i) => s + i.total, 0)

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Fatture</h1>
          <p className="text-gray-500 text-sm mt-1">
            Pagate: {formatCurrency(totalPaid)} · In attesa: {formatCurrency(totalPending)}
          </p>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Nuova fattura
        </button>
      </div>

      <div className="flex gap-2 mb-6">
        {[
          { value: "all", label: "Tutte" },
          { value: "bozza", label: "Bozze" },
          { value: "inviata", label: "Inviate" },
          { value: "pagata", label: "Pagate" },
          { value: "scaduta", label: "Scadute" },
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
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">N° Fattura</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Cliente</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Emissione</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Scadenza</th>
                <th className="text-left px-6 py-3 text-xs font-medium text-gray-500 uppercase">Stato</th>
                <th className="text-right px-6 py-3 text-xs font-medium text-gray-500 uppercase">Totale</th>
                <th className="px-6 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {filtered.map((inv) => {
                const b = invoiceStatusBadge(inv.status)
                const overdue = inv.status === "inviata" && inv.dueDate && new Date(inv.dueDate) < new Date()
                return (
                  <tr key={inv.id} className={`hover:bg-gray-50 transition-colors ${overdue ? "bg-red-50/30" : ""}`}>
                    <td className="px-6 py-4 text-sm font-medium text-gray-900">{inv.number}</td>
                    <td className="px-6 py-4 text-sm text-gray-700">{inv.client.name}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">{formatDate(inv.issueDate)}</td>
                    <td className="px-6 py-4 text-sm text-gray-500">
                      <span className={overdue ? "text-red-600 font-medium" : ""}>{formatDate(inv.dueDate)}</span>
                    </td>
                    <td className="px-6 py-4">
                      <select
                        value={inv.status}
                        onChange={(e) => updateInvoiceStatus(inv.id, e.target.value)}
                        className="text-xs border border-gray-200 rounded-md px-2 py-1 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                      >
                        <option value="bozza">Bozza</option>
                        <option value="inviata">Inviata</option>
                        <option value="pagata">Pagata</option>
                        <option value="scaduta">Scaduta</option>
                      </select>
                    </td>
                    <td className="px-6 py-4 text-sm font-semibold text-right text-gray-900">{formatCurrency(inv.total)}</td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2 justify-end">
                        <button onClick={() => setViewInvoice(inv)} className="text-gray-400 hover:text-indigo-600 transition-colors">
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                        </button>
                        <button
                          onClick={async () => { if (confirm("Eliminare questa fattura?")) await deleteInvoice(inv.id) }}
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

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title="Nuova fattura" size="lg">
        <InvoiceForm
          clients={clients}
          nextNumber={nextNumber}
          onSave={async (data) => { await createInvoice(data); setShowCreate(false) }}
          onCancel={() => setShowCreate(false)}
        />
      </Modal>

      <Modal open={!!viewInvoice} onClose={() => setViewInvoice(null)} title={`Fattura ${viewInvoice?.number}`} size="lg">
        {viewInvoice && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><span className="text-gray-500">Cliente:</span> <span className="font-medium">{viewInvoice.client.name}</span></div>
              <div><span className="text-gray-500">Stato:</span> <Badge variant={invoiceStatusBadge(viewInvoice.status).variant}>{invoiceStatusBadge(viewInvoice.status).label}</Badge></div>
              <div><span className="text-gray-500">Emissione:</span> <span>{formatDate(viewInvoice.issueDate)}</span></div>
              <div><span className="text-gray-500">Scadenza:</span> <span>{formatDate(viewInvoice.dueDate)}</span></div>
            </div>
            <table className="w-full text-sm mt-4">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-3 py-2 font-medium text-gray-600">Descrizione</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-600">Qtà</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-600">Prezzo</th>
                  <th className="text-right px-3 py-2 font-medium text-gray-600">Totale</th>
                </tr>
              </thead>
              <tbody>
                {viewInvoice.items.map((item) => (
                  <tr key={item.id} className="border-t border-gray-100">
                    <td className="px-3 py-2">{item.description}</td>
                    <td className="px-3 py-2 text-right">{item.quantity}</td>
                    <td className="px-3 py-2 text-right">{formatCurrency(item.unitPrice)}</td>
                    <td className="px-3 py-2 text-right font-medium">{formatCurrency(item.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="border-t border-gray-200 pt-3 space-y-1 text-sm">
              <div className="flex justify-between text-gray-600"><span>Subtotale</span><span>{formatCurrency(viewInvoice.subtotal)}</span></div>
              <div className="flex justify-between text-gray-600"><span>IVA {viewInvoice.tax}%</span><span>{formatCurrency(viewInvoice.subtotal * viewInvoice.tax / 100)}</span></div>
              <div className="flex justify-between font-bold text-gray-900 text-base pt-1"><span>Totale</span><span>{formatCurrency(viewInvoice.total)}</span></div>
            </div>
            {viewInvoice.notes && <p className="text-sm text-gray-500 italic">{viewInvoice.notes}</p>}
          </div>
        )}
      </Modal>
    </div>
  )
}
