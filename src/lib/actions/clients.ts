"use server"

import { prisma } from "@/lib/prisma"
import { revalidatePath } from "next/cache"

export async function getClients() {
  return prisma.client.findMany({ orderBy: { createdAt: "desc" } })
}

export async function getClient(id: string) {
  return prisma.client.findUnique({
    where: { id },
    include: { projects: true, invoices: true, proposals: true, quotes: true, timeLogs: true },
  })
}

export async function createClient(data: {
  name: string
  company?: string
  email?: string
  phone?: string
  notes?: string
  status: string
  stage?: string
}) {
  await prisma.client.create({ data })
  revalidatePath("/clienti")
}

export async function updateClient(
  id: string,
  data: {
    name?: string
    company?: string
    email?: string
    phone?: string
    notes?: string
    status?: string
    stage?: string
  }
) {
  await prisma.client.update({ where: { id }, data })
  revalidatePath("/clienti")
}

export async function deleteClient(id: string) {
  await prisma.client.delete({ where: { id } })
  revalidatePath("/clienti")
}
