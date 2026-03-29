import fs from "node:fs";
import path from "node:path";

const envPath = path.resolve(process.cwd(), ".env.local");
if (fs.existsSync(envPath)) {
  const raw = fs.readFileSync(envPath, "utf8");
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }

    const index = trimmed.indexOf("=");
    if (index === -1) {
      continue;
    }

    const key = trimmed.slice(0, index).trim();
    const value = trimmed.slice(index + 1).trim();
    if (key && !process.env[key]) {
      process.env[key] = value;
    }
  }
}

const required = [
  "NEXT_PUBLIC_SUPABASE_URL",
  "NEXT_PUBLIC_SUPABASE_ANON_KEY",
  "SUPABASE_SERVICE_ROLE_KEY"
];

const optional = ["OPENAI_API_KEY"];

const missing = required.filter((name) => {
  const value = process.env[name];
  return !value || !value.trim();
});

if (missing.length > 0) {
  console.error("Missing required environment variables:");
  for (const name of missing) {
    console.error(`- ${name}`);
  }
  console.error("\nCreate .env.local from .env.example and set these values before build/deploy.");
  process.exit(1);
}

console.log("Environment check passed for required variables.");

for (const name of optional) {
  const value = process.env[name];
  if (!value || !value.trim()) {
    console.log(`Optional variable not set: ${name} (fallback behavior will be used)`);
  }
}
