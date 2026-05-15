import { getClients } from "@/lib/actions/clients"
import { ClientiClient } from "./ClientiClient"

export default async function ClientiPage() {
  const clients = await getClients()
  return <ClientiClient clients={clients} />
}
