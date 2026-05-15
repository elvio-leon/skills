import { PrismaClient } from "@prisma/client"
import { PrismaBetterSqlite3 } from "@prisma/adapter-better-sqlite3"
import bcrypt from "bcryptjs"
import path from "path"

const dbPath = path.resolve(process.cwd(), "dev.db")
const adapter = new PrismaBetterSqlite3({ url: dbPath })
const prisma = new PrismaClient({ adapter })

async function main() {
  console.log("Seeding database...")

  // Create admin user
  const hashedPassword = await bcrypt.hash("admin123", 10)
  const user = await prisma.user.upsert({
    where: { email: "admin@freelance.com" },
    update: {},
    create: {
      email: "admin@freelance.com",
      password: hashedPassword,
      name: "Admin",
    },
  })
  console.log("✓ User created:", user.email)

  // Create clients
  const client1 = await prisma.client.upsert({
    where: { id: "client-1" },
    update: {},
    create: {
      id: "client-1",
      name: "Marco Rossi",
      company: "Rossi SRL",
      email: "marco@rossi.it",
      phone: "+39 333 1234567",
      status: "active",
      notes: "Cliente storico, ottimo pagatore",
    },
  })

  const client2 = await prisma.client.upsert({
    where: { id: "client-2" },
    update: {},
    create: {
      id: "client-2",
      name: "Giulia Bianchi",
      company: "Studio Bianchi",
      email: "giulia@bianchi.com",
      phone: "+39 347 9876543",
      status: "active",
      notes: "Lavora nel settore moda",
    },
  })

  const client3 = await prisma.client.upsert({
    where: { id: "client-3" },
    update: {},
    create: {
      id: "client-3",
      name: "Luca Ferri",
      company: "Ferri Tech",
      email: "luca@ferritech.io",
      status: "lead",
      stage: "proposta_inviata",
      notes: "Interessato a sviluppo app mobile",
    },
  })

  console.log("✓ Clients created")

  // Create projects
  const project1 = await prisma.project.upsert({
    where: { id: "project-1" },
    update: {},
    create: {
      id: "project-1",
      name: "Sito web aziendale",
      description: "Redesign completo del sito web con CMS",
      status: "in_corso",
      startDate: new Date("2024-02-01"),
      endDate: new Date("2024-04-30"),
      budget: 3500,
      clientId: client1.id,
    },
  })

  const project2 = await prisma.project.upsert({
    where: { id: "project-2" },
    update: {},
    create: {
      id: "project-2",
      name: "E-commerce moda",
      description: "Sviluppo negozio online con Shopify",
      status: "in_corso",
      startDate: new Date("2024-03-01"),
      budget: 5200,
      clientId: client2.id,
    },
  })

  const project3 = await prisma.project.upsert({
    where: { id: "project-3" },
    update: {},
    create: {
      id: "project-3",
      name: "Brand identity",
      description: "Logo, colori e linee guida brand",
      status: "completato",
      startDate: new Date("2024-01-10"),
      endDate: new Date("2024-02-15"),
      budget: 1800,
      clientId: client1.id,
    },
  })

  console.log("✓ Projects created")

  // Create time logs
  const timeLogs = [
    { date: new Date("2024-03-01"), hours: 4, description: "Setup progetto e wireframe", projectId: project1.id, clientId: client1.id },
    { date: new Date("2024-03-05"), hours: 6, description: "Sviluppo homepage", projectId: project1.id, clientId: client1.id },
    { date: new Date("2024-03-08"), hours: 3, description: "Integrazione CMS", projectId: project1.id, clientId: client1.id },
    { date: new Date("2024-03-10"), hours: 5, description: "Setup Shopify e theme", projectId: project2.id, clientId: client2.id },
    { date: new Date("2024-03-12"), hours: 4, description: "Configurazione prodotti", projectId: project2.id, clientId: client2.id },
    { date: new Date("2024-03-15"), hours: 2, description: "Call di aggiornamento", clientId: client1.id },
  ]

  for (const log of timeLogs) {
    await prisma.timeLog.create({ data: log })
  }

  console.log("✓ Time logs created")

  // Create invoices
  const invoice1 = await prisma.invoice.create({
    data: {
      number: "2024-001",
      clientId: client1.id,
      status: "pagata",
      issueDate: new Date("2024-02-28"),
      dueDate: new Date("2024-03-28"),
      subtotal: 1800,
      tax: 22,
      total: 1800 * 1.22,
      notes: "Brand identity - saldo",
      items: {
        create: [
          { description: "Progettazione logo", quantity: 1, unitPrice: 800, total: 800 },
          { description: "Linee guida brand", quantity: 1, unitPrice: 600, total: 600 },
          { description: "Materiali grafici", quantity: 1, unitPrice: 400, total: 400 },
        ],
      },
    },
  })

  const invoice2 = await prisma.invoice.create({
    data: {
      number: "2024-002",
      clientId: client1.id,
      status: "inviata",
      issueDate: new Date("2024-03-15"),
      dueDate: new Date("2024-04-15"),
      subtotal: 1750,
      tax: 22,
      total: 1750 * 1.22,
      notes: "SAL 50% - Sito web aziendale",
      items: {
        create: [
          { description: "Sviluppo sito web - acconto 50%", quantity: 1, unitPrice: 1750, total: 1750 },
        ],
      },
    },
  })

  const invoice3 = await prisma.invoice.create({
    data: {
      number: "2024-003",
      clientId: client2.id,
      status: "bozza",
      issueDate: new Date("2024-03-20"),
      dueDate: new Date("2024-04-20"),
      subtotal: 2600,
      tax: 22,
      total: 2600 * 1.22,
      items: {
        create: [
          { description: "E-commerce - acconto 50%", quantity: 1, unitPrice: 2600, total: 2600 },
        ],
      },
    },
  })

  console.log("✓ Invoices created")

  // Create proposals
  await prisma.proposal.create({
    data: {
      title: "App mobile iOS/Android",
      clientId: client3.id,
      status: "inviata",
      amount: 12000,
      expiryDate: new Date("2024-04-30"),
      notes: "Include design, sviluppo e 3 mesi di supporto",
    },
  })

  await prisma.proposal.create({
    data: {
      title: "Gestione social media Q2",
      clientId: client2.id,
      status: "accettata",
      amount: 900,
      notes: "Pacchetto trimestrale - Instagram e Facebook",
    },
  })

  console.log("✓ Proposals created")

  // Create quotes
  await prisma.quote.create({
    data: {
      title: "Sviluppo App Mobile",
      clientId: client3.id,
      status: "inviata",
      tax: 22,
      subtotal: 9836,
      total: 9836 * 1.22,
      notes: "Validità 30 giorni. Pagamento: 30% acconto, 40% SAL, 30% consegna.",
      items: {
        create: [
          { description: "Progettazione UX/UI", quantity: 1, unitPrice: 2500, total: 2500 },
          { description: "Sviluppo backend API", quantity: 1, unitPrice: 3500, total: 3500 },
          { description: "Sviluppo app iOS", quantity: 1, unitPrice: 2000, total: 2000 },
          { description: "Sviluppo app Android", quantity: 1, unitPrice: 1500, total: 1500 },
          { description: "Test e QA", quantity: 1, unitPrice: 336, total: 336 },
        ],
      },
    },
  })

  console.log("✓ Quotes created")
  console.log("\n✅ Database seeded successfully!")
  console.log("Login: admin@freelance.com / admin123")
}

main()
  .catch(console.error)
  .finally(() => prisma.$disconnect())
