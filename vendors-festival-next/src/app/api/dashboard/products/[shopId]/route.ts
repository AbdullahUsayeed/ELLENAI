import { getSellerProducts } from "@/lib/services/products";
import { requireAuthenticatedUser } from "@/lib/services/shops";
import { apiError, apiOk } from "@/lib/utils/api";

export async function GET(_request: Request, context: { params: { shopId: string } }) {
  try {
    const user = await requireAuthenticatedUser();
    const products = await getSellerProducts(context.params.shopId, user.id);
    return apiOk(products);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to fetch products.";
    return apiError(message, message === "Authentication required." ? 401 : 500);
  }
}
