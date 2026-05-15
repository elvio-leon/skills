"use server"

import { prisma } from "@/lib/prisma"
import { revalidatePath } from "next/cache"

export async function getProjects() {
  return prisma.project.findMany({
    include: { client: true },
    orderBy: { createdAt: "desc" },
  })
}

export async function createProject(data: {
  name: string
  description?: string
  status: string
  startDate?: string
  endDate?: string
  budget?: number
  clientId: string
}) {
  await prisma.project.create({
    data: {
      ...data,
      startDate: data.startDate ? new Date(data.startDate) : undefined,
      endDate: data.endDate ? new Date(data.endDate) : undefined,
    },
  })
  revalidatePath("/progetti")
}

export async function updateProject(
  id: string,
  data: {
    name?: string
    description?: string
    status?: string
    startDate?: string
    endDate?: string
    budget?: number
    clientId?: string
  }
) {
  await prisma.project.update({
    where: { id },
    data: {
      ...data,
      startDate: data.startDate ? new Date(data.startDate) : undefined,
      endDate: data.endDate ? new Date(data.endDate) : undefined,
    },
  })
  revalidatePath("/progetti")
}

export async function deleteProject(id: string) {
  await prisma.project.delete({ where: { id } })
  revalidatePath("/progetti")
}
