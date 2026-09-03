import { NextRequest, NextResponse } from "next/server";

export async function proxy(request: NextRequest) {
  const cookieHeader = request.headers.get("cookie");
  if (cookieHeader) {
    try {
      const response = await fetch(
        `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/v1/auth/me`,
        { headers: { cookie: cookieHeader }, cache: "no-store" },
      );
      if (response.ok) {
        return NextResponse.next();
      }
    } catch {
      // The protected page performs the same validation and reports backend errors.
    }
  }

  const loginUrl = new URL("/auth/login", request.url);
  loginUrl.searchParams.set("next", request.nextUrl.pathname);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/dashboard/:path*", "/settings/integrations/:path*"],
};
