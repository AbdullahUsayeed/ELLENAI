import { loginSchema } from "@/lib/validation/schemas";
import { signInUser } from "@/lib/services/auth";
import { apiError, apiOk } from "@/lib/utils/api";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const parsed = loginSchema.safeParse(body);

    if (!parsed.success) {
      return apiError("Invalid login payload.", 400, parsed.error.flatten());
    }

    const result = await signInUser(parsed.data);
    return apiOk({ user: result.user, session: result.session });
  } catch (error) {
    return apiError(error instanceof Error ? error.message : "Unable to log in.", 500);
  }
}
