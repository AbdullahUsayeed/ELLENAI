import { signupSchema } from "@/lib/validation/schemas";
import { signUpUser } from "@/lib/services/auth";
import { apiError, apiOk } from "@/lib/utils/api";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const parsed = signupSchema.safeParse(body);

    if (!parsed.success) {
      return apiError("Invalid signup payload.", 400, parsed.error.flatten());
    }

    const result = await signUpUser(parsed.data);
    return apiOk({ user: result.user, session: result.session }, { status: 201 });
  } catch (error) {
    return apiError(error instanceof Error ? error.message : "Unable to sign up.", 500);
  }
}
