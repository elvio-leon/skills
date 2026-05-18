"use server"

import { prisma } from "@/lib/prisma"
import { revalidatePath } from "next/cache"

export async function getInvoices() {
  return prisma.invoice.findMany({
    include: { client: true },
    orderBy: { createdAt: "desc" },
  })
}

export async function createInvoice(data: {
  clientId: string
  description: string
  amount: number
  dueDate?: string
  notes?: string
}) {
  await prisma.invoice.create({
    data: {
      clientId: data.clientId,
      description: data.description,
      amount: data.amount,
      dueDate: data.dueDate ? new Date(data.dueDate) : undefined,
      notes: data.notes,
    },
  })
  revalidatePath("/fatture")
}

export async function updateInvoice(
  id: string,
  data: {
    clientId?: string
    description?: string
    amount?: number
    dueDate?: string | null
    status?: string
    notes?: string
  }
) {
  await prisma.invoice.update({
    where: { id },
    data: {
      ...(data.clientId && { clientId: data.clientId }),
      ...(data.description !== undefined && { description: data.description }),
      ...(data.amount !== undefined && { amount: data.amount }),
      ...(data.dueDate !== undefined && { dueDate: data.dueDate ? new Date(data.dueDate) : null }),
      ...(data.status && { status: data.status }),
      ...(data.notes !== undefined && { notes: data.notes }),
    },
  })
  revalidatePath("/fatture")
}

export async function updateInvoiceStatus(id: string, status: string) {
  await prisma.invoice.update({ where: { id }, data: { status } })
  revalidatePath("/fatture")
}

export async function deleteInvoice(id: string) {
  await prisma.invoice.delete({ where: { id } })
  revalidatePath("/fatture")
}
