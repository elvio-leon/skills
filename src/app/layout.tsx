import type { Metadata } from "next"
import { Geist } from "next/font/google"
import "./globals.css"
import { SessionProvider } from "next-auth/react"
import { auth } from "@/auth"
import { Sidebar } from "@/components/Sidebar"

const geist = Geist({ subsets: ["latin"] })

export const metadata: Metadata = {
  title: "Freelance Manager",
  description: "Il tuo gestionale freelance personale",
}

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const session = await auth()
  const isLoginPage = false // middleware handles redirects

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
