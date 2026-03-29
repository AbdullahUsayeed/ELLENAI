import { signOutUser } from "@/lib/services/auth";
import { apiError, apiOk } from "@/lib/utils/api";

export async function POST() {
  try {
    await signOutUser();
    return apiOk({ loggedOut: true });
  } catch (error) {
    return apiError(error instanceof Error ? error.message : "Unable to log out.", 500);
  }
}
