import type { NextRequest } from "next/server";
import { updateDashboardSession } from "@/lib/supabase/middleware";

export async function middleware(request: NextRequest) {
  return updateDashboardSession(request);
}

export const config = {
  matcher: ["/dashboard/:path*"]
};
