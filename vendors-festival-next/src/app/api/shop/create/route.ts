import { createShopSchema } from "@/lib/validation/schemas";
import type { TentTheme } from "@/lib/constants/tent-themes";
import { apiError, apiOk } from "@/lib/utils/api";
import { createOrUpdateShopForUser, requireAuthenticatedUser } from "@/lib/services/shops";

export async function POST(request: Request) {
  try {
    const user = await requireAuthenticatedUser();
    const body = await request.json();
    const parsed = createShopSchema.safeParse(body);

    if (!parsed.success) {
      return apiError("Invalid shop payload.", 400, parsed.error.flatten());
    }

    const shop = await createOrUpdateShopForUser({
      userId: user.id,
      shopName: parsed.data.name,
      tentTheme: parsed.data.tent_theme as TentTheme,
      paymentMethods: parsed.data.payment_methods,
      logoUrl: parsed.data.logo_url
    });

    return apiOk(shop, { status: 201 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to save shop.";
    return apiError(message, message === "Authentication required." ? 401 : 500);
  }
}
