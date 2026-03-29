"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

type AuthFormProps = {
  mode: "login" | "signup";
};

export function AuthForm({ mode }: AuthFormProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const redirectTo = searchParams.get("redirectTo") || "/dashboard";

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const response = await fetch(`/api/auth/${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          mode === "signup"
            ? { full_name: fullName, email, password }
            : { email, password }
        )
      });

      const payload = await response.json();
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || `Unable to ${mode}.`);
      }

      router.push(redirectTo);
      router.refresh();
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : `Unable to ${mode}.`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-4 rounded-[28px] border border-white/10 bg-white/[0.04] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.35)] backdrop-blur-sm">
      {mode === "signup" && (
        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-[#E8D8A8]">Full name</span>
          <input value={fullName} onChange={(event) => setFullName(event.target.value)} className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-[#F5E4BD] outline-none" required />
        </label>
      )}
      <label className="block">
        <span className="mb-2 block text-sm font-semibold text-[#E8D8A8]">Email</span>
        <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-[#F5E4BD] outline-none" required />
      </label>
      <label className="block">
        <span className="mb-2 block text-sm font-semibold text-[#E8D8A8]">Password</span>
        <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-[#F5E4BD] outline-none" required />
      </label>

      {error && <p className="rounded-2xl border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-200">{error}</p>}

      <button disabled={loading} className="w-full rounded-2xl bg-gradient-to-r from-[#FFB647] to-[#C8941A] px-4 py-3 text-sm font-bold text-[#1f1408] disabled:opacity-60">
        {loading ? "Please wait..." : mode === "signup" ? "Create account" : "Log in"}
      </button>
    </form>
  );
}
