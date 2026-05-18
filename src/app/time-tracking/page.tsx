export const dynamic = "force-dynamic"

import { getTimeLogs } from "@/lib/actions/timelogs"
import { getClients } from "@/lib/actions/clients"
import { getProjects } from "@/lib/actions/projects"
import { TimeTrackingClient } from "./TimeTrackingClient"

export default async function TimeTrackingPage() {
  const [timeLogs, clients, projects] = await Promise.all([getTimeLogs(), getClients(), getProjects()])
  return <TimeTrackingClient timeLogs={timeLogs} clients={clients} projects={projects} />
}
