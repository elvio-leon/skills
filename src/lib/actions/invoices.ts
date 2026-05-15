"use server"

import { prisma } from "@/lib/prisma"
import { revalidatePath } from "next/cache"

export async function getInvoices() {
  return prisma.invoice.findMany({
    include: { client: true, items: true },
    orderBy: { createdAt: "desc" },
  })
}

export async function getInvoice(id: string) {
  return prisma.invoice.findUnique({
    where: { id },
    include: { client: true, items: true },
  })
}

export async function createInvoice(data: {
  number: string
  clientId: string
  status: string
  issueDate: string
  dueDate?: string
  tax: number
  notes?: string
  items: { description: string; quantity: number; unitPrice: number; total: number }[]
}) {
  const subtotal = data.items.reduce((s, i) => s + i.total, 0)
  const total = subtotal * (1 + data.tax / 100)
  await prisma.invoice.create({
    data: {
      number: data.number,
      clientId: data.clientId,
      status: data.status,
      issueDate: new Date(data.issueDate),
      dueDate: data.dueDate ? new Date(data.dueDate) : undefined,
      tax: data.tax,
      subtotal,
      total,
      notes: data.notes,
      items: { create: data.items },
    },
  })
  revalidatePath("/fatture")
}

export async function updateInvoiceStatus(id: string, status: string) {
  await prisma.invoice.update({ where: { id }, data: { status } })
  revalidatePath("/fatture")
}

export async function updateInvoice(
  id: string,
  data: {
    number?: string
    clientId?: string
    status?: string
    issueDate?: string
    dueDate?: string
    tax?: number
    notes?: string
    items?: { description: string; quantity: number; unitPrice: number; total: number }[]
  }
) {
  const subtotal = data.items ? data.items.reduce((s, i) => s + i.total, 0) : undefined
  const total = subtotal !== undefined ? subtotal * (1 + (data.tax ?? 22) / 100) : undefined

  await prisma.$transaction(async (tx) => {
    if (data.items) {
      await tx.invoiceItem.deleteMany({ where: { invoiceId: id } })
    }
    await tx.invoice.update({
      where: { id },
      data: {
        ...(data.number && { number: data.number }),
        ...(data.clientId && { clientId: data.clientId }),
        ...(data.status && { status: data.status }),
        ...(data.issueDate && { issueDate: new Date(data.issueDate) }),
        ...(data.dueDate !== undefined && { dueDate: data.dueDate ? new Date(data.dueDate) : null }),
        ...(data.tax !== undefined && { tax: data.tax }),
        ...(subtotal !== undefined && { subtotal }),
        ...(total !== undefined && { total }),
        ...(data.notes !== undefined && { notes: data.notes }),
        ...(data.items && { items: { create: data.items } }),
      },
    })
  })
  revalidatePath("/fatture")
}

export async function deleteInvoice(id: string) {
  await prisma.invoice.delete({ where: { id } })
  revalidatePath("/fatture")
}

export async function getNextInvoiceNumber(): Promise<string> {
  const latest = await prisma.invoice.findFirst({ orderBy: { createdAt: "desc" } })
  if (!latest) {
    const year = new Date().getFullYear()
    return `${year}-001`
  }
  const parts = latest.number.split("-")
  const year = new Date().getFullYear().toString()
  const num = parseInt(parts[parts.length - 1] || "0") + 1
  return `${year}-${String(num).padStart(3, "0")}`
}
