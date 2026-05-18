"use server"

import { prisma } from "@/lib/prisma"
import { revalidatePath } from "next/cache"

export async function getQuotes() {
  return prisma.quote.findMany({
    select: {
      id: true, title: true, clientId: true, status: true, notes: true,
      subtotal: true, tax: true, total: true, pdfFileName: true,
      createdAt: true, updatedAt: true,
      client: true,
      items: true,
    },
    orderBy: { createdAt: "desc" },
  })
}

export async function getQuote(id: string) {
  return prisma.quote.findUnique({
    where: { id },
    include: { client: true, items: true },
  })
}

export async function createQuote(data: {
  title: string
  clientId: string
  status: string
  tax: number
  notes?: string
  items: { description: string; quantity: number; unitPrice: number; total: number }[]
}) {
  const subtotal = data.items.reduce((s, i) => s + i.total, 0)
  const total = subtotal * (1 + data.tax / 100)
  await prisma.quote.create({
    data: {
      title: data.title,
      clientId: data.clientId,
      status: data.status,
      tax: data.tax,
      subtotal,
      total,
      notes: data.notes,
      items: { create: data.items },
    },
  })
  revalidatePath("/preventivi")
}

export async function updateQuote(
  id: string,
  data: {
    title?: string
    clientId?: string
    status?: string
    tax?: number
    notes?: string
    items?: { description: string; quantity: number; unitPrice: number; total: number }[]
  }
) {
  const subtotal = data.items ? data.items.reduce((s, i) => s + i.total, 0) : undefined
  const total = subtotal !== undefined ? subtotal * (1 + (data.tax ?? 22) / 100) : undefined

  await prisma.$transaction(async (tx) => {
    if (data.items) {
      await tx.quoteItem.deleteMany({ where: { quoteId: id } })
    }
    await tx.quote.update({
      where: { id },
      data: {
        ...(data.title && { title: data.title }),
        ...(data.clientId && { clientId: data.clientId }),
        ...(data.status && { status: data.status }),
        ...(data.tax !== undefined && { tax: data.tax }),
        ...(subtotal !== undefined && { subtotal }),
        ...(total !== undefined && { total }),
        ...(data.notes !== undefined && { notes: data.notes }),
        ...(data.items && { items: { create: data.items } }),
      },
    })
  })
  revalidatePath("/preventivi")
}

export async function deleteQuote(id: string) {
  await prisma.quote.delete({ where: { id } })
  revalidatePath("/preventivi")
}
