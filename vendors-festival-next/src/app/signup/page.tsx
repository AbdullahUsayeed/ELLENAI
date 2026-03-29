import Link from "next/link";
import { Suspense } from "react";
import { AuthForm } from "@/components/auth/AuthForm";

export default function SignupPage() {
  return (
    <main className="min-h-screen bg-[#070B18] px-4 py-12 text-[#E8D8A8]">
      <div className="mx-auto max-w-md">
        <div className="mb-8 text-center">
          <p className="text-xs font-bold uppercase tracking-[0.28em] text-[#D8BF86]/70">VENDORS</p>
          <h1 className="festival-title mt-3 text-4xl font-black text-[#F5E4BD]">Create your tent</h1>
          <p className="mt-3 text-sm text-[#C8B68E]/70">Sign up and get a public tent shop instantly.</p>
        </div>
        <Suspense fallback={<div className="rounded-[28px] border border-white/10 bg-white/[0.04] p-6 text-sm text-[#C8B68E]/70">Loading signup form...</div>}>
          <AuthForm mode="signup" />
        </Suspense>
        <p className="mt-4 text-center text-sm text-[#C8B68E]/70">
          Already have an account? <Link href="/login" className="font-semibold text-[#FFB647]">Log in</Link>
        </p>
      </div>
    </main>
  );
}
