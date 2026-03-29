import { getSellerOrders } from "@/lib/services/orders";
import { requireAuthenticatedUser } from "@/lib/services/shops";
import { apiError, apiOk } from "@/lib/utils/api";

export async function GET(_request: Request, context: { params: { shopId: string } }) {
  try {
    const user = await requireAuthenticatedUser();
    const orders = await getSellerOrders(context.params.shopId, user.id);
    return apiOk(orders);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to fetch orders.";
    return apiError(message, message === "Authentication required." ? 401 : 500);
  }
}
