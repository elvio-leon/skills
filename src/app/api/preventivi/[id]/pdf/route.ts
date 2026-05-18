import { prisma } from "@/lib/prisma"
import { revalidatePath } from "next/cache"
import { NextResponse } from "next/server"

export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const formData = await request.formData()
  const file = formData.get("pdf") as File | null
  if (!file) return NextResponse.json({ error: "Nessun file" }, { status: 400 })

  const bytes = await file.arrayBuffer()
  const buffer = Buffer.from(bytes)

  await prisma.quote.update({
    where: { id },
    data: { pdfData: buffer, pdfFileName: file.name },
  })

  revalidatePath("/preventivi")
  return NextResponse.json({ ok: true })
}

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const quote = await prisma.quote.findUnique({
    where: { id },
    select: { pdfData: true, pdfFileName: true },
  })

  if (!quote?.pdfData) return new Response("Non trovato", { status: 404 })

  return new Response(quote.pdfData, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="${quote.pdfFileName ?? "preventivo.pdf"}"`,
    },
  })
}
