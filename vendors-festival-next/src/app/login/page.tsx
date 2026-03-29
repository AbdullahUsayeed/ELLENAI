import Link from "next/link";
import { Suspense } from "react";
import { AuthForm } from "@/components/auth/AuthForm";

export default function LoginPage() {
  return (
    <main className="min-h-screen bg-[#070B18] px-4 py-12 text-[#E8D8A8]">
      <div className="mx-auto max-w-md">
        <div className="mb-8 text-center">
          <p className="text-xs font-bold uppercase tracking-[0.28em] text-[#D8BF86]/70">VENDORS</p>
          <h1 className="festival-title mt-3 text-4xl font-black text-[#F5E4BD]">Seller login</h1>
          <p className="mt-3 text-sm text-[#C8B68E]/70">Access your tent, products, and customer orders.</p>
        </div>
        <Suspense fallback={<div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-6 text-sm text-[#C8B68E]/70">Loading login form...</div>}>
          <AuthForm mode="login" />
        </Suspense>
        <p className="mt-4 text-center text-sm text-[#C8B68E]/70">
          Need an account? <Link href="/signup" className="font-semibold text-[#FFB647]">Create one</Link>
        </p>
      </div>
    </main>
  );
}
