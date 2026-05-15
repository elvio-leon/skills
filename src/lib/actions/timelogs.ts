"use server"

import { prisma } from "@/lib/prisma"
import { revalidatePath } from "next/cache"

export async function getTimeLogs() {
  return prisma.timeLog.findMany({
    include: { client: true, project: true },
    orderBy: { date: "desc" },
  })
}

export async function createTimeLog(data: {
  date: string
  hours: number
  description?: string
  projectId?: string
  clientId: string
}) {
  await prisma.timeLog.create({
    data: { ...data, date: new Date(data.date) },
  })
  revalidatePath("/time-tracking")
}

export async function updateTimeLog(
  id: string,
  data: {
    date?: string
    hours?: number
    description?: string
    projectId?: string
    clientId?: string
  }
) {
  await prisma.timeLog.update({
    where: { id },
    data: {
      ...data,
      date: data.date ? new Date(data.date) : undefined,
    },
  })
  revalidatePath("/time-tracking")
}

export async function deleteTimeLog(id: string) {
  await prisma.timeLog.delete({ where: { id } })
  revalidatePath("/time-tracking")
}
