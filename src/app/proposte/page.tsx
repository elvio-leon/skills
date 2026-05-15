import { getProposals } from "@/lib/actions/proposals"
import { getClients } from "@/lib/actions/clients"
import { ProposteClient } from "./ProposteClient"

export default async function PropostePage() {
  const [proposals, clients] = await Promise.all([getProposals(), getClients()])
  return <ProposteClient proposals={proposals} clients={clients} />
}
