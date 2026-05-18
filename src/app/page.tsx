export const dynamic = "force-dynamic"

import { prisma } from "@/lib/prisma"
import { formatCurrency } from "@/lib/utils"
import { Badge, invoiceStatusBadge, projectStatusBadge } from "@/components/ui/Badge"
import { startOfMonth, endOfMonth } from "date-fns"

export default async function DashboardPage() {
  const now = new Date()
  const monthStart = startOfMonth(now)
  const monthEnd = endOfMonth(now)

  const [
    totalClients,
    totalLeads,
    activeProjects,
    monthlyHours,
    monthlyRevenue,
    pendingInvoices,
    overdueInvoices,
    recentInvoices,
    recentProjects,
  ] = await Promise.all([
    prisma.client.count({ where: { status: "active" } }),
    prisma.client.count({ where: { status: "lead" } }),
    prisma.project.count({ where: { status: "in_corso" } }),
    prisma.timeLog.aggregate({
      where: { date: { gte: monthStart, lte: monthEnd } },
      _sum: { hours: true },
    }),
    prisma.invoice.aggregate({
      where: { status: "pagata", issueDate: { gte: monthStart, lte: monthEnd } },
      _sum: { total: true },
    }),
    prisma.invoice.count({ where: { status: "inviata" } }),
    prisma.invoice.count({ where: { status: "scaduta" } }),
    prisma.invoice.findMany({
      take: 5,
      orderBy: { createdAt: "desc" },
      include: { client: true },
    }),
    prisma.project.findMany({
      take: 5,
      where: { status: "in_corso" },
      orderBy: { createdAt: "desc" },
      include: { client: true },
    }),
  ])

  const stats = [
    {
      label: "Clienti attivi",
      value: totalClients,
      sub: `${totalLeads} lead in pipeline`,
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      ),
      color: "bg-indigo-500",
    },
    {
      label: "Progetti attivi",
      value: activeProjects,
      sub: "In corso",
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
        </svg>
      ),
      color: "bg-blue-500",
    },
    {
      label: "Ore questo mese",
      value: (monthlyHours._sum.hours ?? 0).toFixed(1) + "h",
      sub: "Totale registrato",
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      color: "bg-emerald-500",
    },
    {
      label: "Incassato questo mese",
      value: formatCurrency(monthlyRevenue._sum.total ?? 0),
      sub: `${pendingInvoices} in attesa${overdueInvoices > 0 ? `, ${overdueInvoices} scadute` : ""}`,
      icon: (
        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
      color: "bg-amber-500",
    },
  ]

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 mt-1">Benvenuto nel tuo gestionale freelance</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-8">
        {stats.map((stat) => (
          <div key={stat.label} className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
            <div className="flex items-center justify-between mb-4">
              <div className={`w-12 h-12 ${stat.color} rounded-xl flex items-center justify-center text-white`}>
                {stat.icon}
              </div>
            </div>
            <p className="text-2xl font-bold text-gray-900">{stat.value}</p>
            <p className="text-sm font-medium text-gray-600 mt-1">{stat.label}</p>
            <p className="text-xs text-gray-400 mt-0.5">{stat.sub}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-base font-semibold text-gray-900 mb-4">Ultime fatture</h2>
          {recentInvoices.length === 0 ? (
            <p className="text-sm text-gray-400 py-4 text-center">Nessuna fattura ancora</p>
          ) : (
            <div className="space-y-3">
              {recentInvoices.map((inv) => {
                const b = invoiceStatusBadge(inv.status)
                return (
                  <div key={inv.id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                    <div>
                      <p className="text-sm font-medium text-gray-900">{inv.number}</p>
                      <p className="text-xs text-gray-500">{inv.client.name}</p>
                    </div>
                    <div className="text-right flex flex-col items-end gap-1">
                      <p className="text-sm font-semibold text-gray-900">{formatCurrency(inv.total)}</p>
                      <Badge variant={b.variant}>{b.label}</Badge>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
          <h2 className="text-base font-semibold text-gray-900 mb-4">Progetti in corso</h2>
          {recentProjects.length === 0 ? (
            <p className="text-sm text-gray-400 py-4 text-center">Nessun progetto attivo</p>
          ) : (
            <div className="space-y-3">
              {recentProjects.map((proj) => {
                const b = projectStatusBadge(proj.status)
                return (
                  <div key={proj.id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                    <div>
                      <p className="text-sm font-medium text-gray-900">{proj.name}</p>
                      <p className="text-xs text-gray-500">{proj.client.name}</p>
                    </div>
                    <div className="text-right flex flex-col items-end gap-1">
                      {proj.budget && <p className="text-sm font-semibold text-gray-900">{formatCurrency(proj.budget)}</p>}
                      <Badge variant={b.variant}>{b.label}</Badge>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
