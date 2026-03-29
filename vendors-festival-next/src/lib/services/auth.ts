import { createSupabaseAdminClient } from "@/lib/supabase/admin";
import { createSupabaseServerClient } from "@/lib/supabase/server";
import { DEFAULT_TENT_THEME } from "@/lib/constants/tent-themes";
import { createOrUpdateShopForUser } from "@/lib/services/shops";

function defaultShopName(fullName: string) {
  const firstName = fullName.trim().split(/\s+/)[0] || "Creator";
  return `${firstName}'s Tent`;
}

export async function signUpUser(input: {
  full_name: string;
  email: string;
  password: string;
}) {
  const supabase = await createSupabaseServerClient();
  const admin = createSupabaseAdminClient();

  const { data, error } = await supabase.auth.signUp({
    email: input.email,
    password: input.password,
    options: {
      data: {
        full_name: input.full_name
      }
    }
  });

  if (error || !data.user) {
    throw new Error(error?.message ?? "Unable to sign up.");
  }

  const { error: userError } = await admin.from("users").upsert(
    {
      id: data.user.id,
      full_name: input.full_name,
      email: input.email
    },
    { onConflict: "id" }
  );

  if (userError) {
    throw new Error(userError.message);
  }

  await createOrUpdateShopForUser({
    userId: data.user.id,
    shopName: defaultShopName(input.full_name),
    tentTheme: DEFAULT_TENT_THEME,
    paymentMethods: [],
    logoUrl: undefined
  });

  return data;
}

export async function signInUser(input: { email: string; password: string }) {
  const supabase = await createSupabaseServerClient();
  const { data, error } = await supabase.auth.signInWithPassword(input);

  if (error) {
    throw new Error(error.message);
  }

  return data;
}

export async function signOutUser() {
  const supabase = await createSupabaseServerClient();
  const { error } = await supabase.auth.signOut();

  if (error) {
    throw new Error(error.message);
  }
}
