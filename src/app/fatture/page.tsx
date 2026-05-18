export const dynamic = "force-dynamic"

import { getInvoices } from "@/lib/actions/invoices"
import { getClients } from "@/lib/actions/clients"
import { FattureClient } from "./FattureClient"

export default async function FatturePage() {
  const [invoices, clients] = await Promise.all([getInvoices(), getClients()])
  return <FattureClient invoices={invoices} clients={clients} />
}
