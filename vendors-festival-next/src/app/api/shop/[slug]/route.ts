import { getShopBySlug, requireAuthenticatedUser, updateShopProfile } from "@/lib/services/shops";
import { updateShopSchema } from "@/lib/validation/schemas";
import type { TentTheme } from "@/lib/constants/tent-themes";
import { apiError, apiOk } from "@/lib/utils/api";

export async function GET(_request: Request, context: { params: { slug: string } }) {
  try {
    const shop = await getShopBySlug(context.params.slug);
    if (!shop) {
      return apiError("Shop not found.", 404);
    }
    return apiOk(shop);
  } catch (error) {
    return apiError(error instanceof Error ? error.message : "Unable to fetch shop.", 500);
  }
}

export async function PATCH(request: Request, context: { params: { slug: string } }) {
  try {
    const user = await requireAuthenticatedUser();
    const shopData = await getShopBySlug(context.params.slug);

    if (!shopData) {
      return apiError("Shop not found.", 404);
    }

    if (shopData.shop.user_id !== user.id) {
      return apiError("You do not have permission to update this shop.", 403);
    }

    const body = await request.json();
    const parsed = updateShopSchema.safeParse(body);

    if (!parsed.success) {
      return apiError("Invalid shop payload.", 400, parsed.error.flatten());
    }

    const updated = await updateShopProfile(shopData.shop.id, user.id, {
      name: parsed.data.name,
      tent_theme: parsed.data.tent_theme as TentTheme | undefined
    });
    return apiOk(updated);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to update shop.";
    return apiError(message, message === "Authentication required." ? 401 : 500);
  }
}

