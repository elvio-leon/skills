import type { Metadata } from "next"
import { Geist } from "next/font/google"
import "./globals.css"
import { SessionProvider } from "next-auth/react"
import { auth } from "@/auth"
import { Sidebar } from "@/components/Sidebar"
import { headers } from "next/headers"
import { redirect } from "next/navigation"

const geist = Geist({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "Freelance Manager",
  description: "Il tuo gestionale freelance personale",
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const headersList = await headers()
  const pathname = headersList.get("x-pathname") ?? "/"
  const isPublic = pathname.startsWith("/login") || pathname.startsWith("/api/auth")

  let session = null
  try {
    session = await auth()
  } catch {
    // auth() can fail if secrets are misconfigured — fail safe
  }

  if (!session && !isPublic) {
    redirect("/login")
  }

  return (
    <html lang="it" className="h-full">
      <body className={`${geist.className} h-full bg-gray-50`}>
        <SessionProvider session={session}>
          {session ? (
            <div className="flex h-full min-h-screen">
              <Sidebar />
              <main className="flex-1 overflow-auto">
                {children}
              </main>
            </div>
          ) : (
            children
          )}
        </SessionProvider>
      </body>
    </html>
  )
}
