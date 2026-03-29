import { updateOrderStatusSchema } from "@/lib/validation/schemas";
import { updateOrderStatus } from "@/lib/services/orders";
import { requireAuthenticatedUser } from "@/lib/services/shops";
import { apiError, apiOk } from "@/lib/utils/api";

export async function PATCH(
  request: Request,
  context: { params: { shopId: string; orderId: string } }
) {
  try {
    const user = await requireAuthenticatedUser();
    const body = await request.json();
    const parsed = updateOrderStatusSchema.safeParse(body);

    if (!parsed.success) {
      return apiError("Invalid payload.", 400, parsed.error.flatten());
    }

    const order = await updateOrderStatus({
      orderId: context.params.orderId,
      shopId: context.params.shopId,
      userId: user.id,
      status: parsed.data.status
    });

    return apiOk(order);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to update order.";
    return apiError(message, message === "Authentication required." ? 401 : 500);
  }
}
