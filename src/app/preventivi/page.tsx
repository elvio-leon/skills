import { getQuotes } from "@/lib/actions/quotes"
import { getClients } from "@/lib/actions/clients"
import { PreventiviClient } from "./PreventiviClient"

export default async function PreventiviPage() {
  const [quotes, clients] = await Promise.all([getQuotes(), getClients()])
  return <PreventiviClient quotes={quotes} clients={clients} />
}
