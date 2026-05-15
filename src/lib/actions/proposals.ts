"use server"

import { prisma } from "@/lib/prisma"
import { revalidatePath } from "next/cache"

export async function getProposals() {
  return prisma.proposal.findMany({
    include: { client: true },
    orderBy: { createdAt: "desc" },
  })
}

export async function createProposal(data: {
  title: string
  clientId: string
  status: string
  amount?: number
  expiryDate?: string
  notes?: string
}) {
  await prisma.proposal.create({
    data: {
      ...data,
      expiryDate: data.expiryDate ? new Date(data.expiryDate) : undefined,
    },
  })
  revalidatePath("/proposte")
}

export async function updateProposal(
  id: string,
  data: {
    title?: string
    clientId?: string
    status?: string
    amount?: number
    expiryDate?: string
    notes?: string
  }
) {
  await prisma.proposal.update({
    where: { id },
    data: {
      ...data,
      expiryDate: data.expiryDate ? new Date(data.expiryDate) : undefined,
    },
  })
  revalidatePath("/proposte")
}

export async function deleteProposal(id: string) {
  await prisma.proposal.delete({ where: { id } })
  revalidatePath("/proposte")
}
