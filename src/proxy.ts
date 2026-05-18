import { NextResponse } from "next/server"
import type { NextRequest } from "next/server"
import { cookies } from "next/headers"

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Allow public paths through
  if (pathname.startsWith("/login") || pathname.startsWith("/api/auth")) {
    return NextResponse.next()
  }

  // Check for NextAuth session cookie
  const sessionCookie =
    request.cookies.get("authjs.session-token") ||
    request.cookies.get("__Secure-authjs.session-token") ||
    request.cookies.get("next-auth.session-token") ||
    request.cookies.get("__Secure-next-auth.session-token")

  if (!sessionCookie) {
    return NextResponse.redirect(new URL("/login", request.url))
  }

  return NextResponse.next()
}

export default proxy

export const config = {
  matcher: ["/((?!api/auth|_next/static|_next/image|favicon.ico).*)"],
}
