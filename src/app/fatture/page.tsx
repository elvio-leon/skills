export const dynamic = "force-dynamic"

import { getInvoices, getNextInvoiceNumber } from "@/lib/actions/invoices"
import { getClients } from "@/lib/actions/clients"
import { FattureClient } from "./FattureClient"

export default async function FatturePage() {
  const [invoices, clients, nextNumber] = await Promise.all([getInvoices(), getClients(), getNextInvoiceNumber()])
  return <FattureClient invoices={invoices} clients={clients} nextNumber={nextNumber} />
}
