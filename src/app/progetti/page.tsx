import { getProjects } from "@/lib/actions/projects"
import { getClients } from "@/lib/actions/clients"
import { ProgettiClient } from "./ProgettiClient"

export default async function ProgettiPage() {
  const [projects, clients] = await Promise.all([getProjects(), getClients()])
  return <ProgettiClient projects={projects} clients={clients} />
}
