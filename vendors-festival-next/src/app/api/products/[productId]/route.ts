import { deleteProduct } from "@/lib/services/products";
import { requireAuthenticatedUser } from "@/lib/services/shops";
import { apiError, apiOk } from "@/lib/utils/api";

export async function DELETE(_request: Request, context: { params: { productId: string } }) {
  try {
    const user = await requireAuthenticatedUser();
    await deleteProduct(context.params.productId, user.id);
    return apiOk({ deleted: true });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to delete product.";
    return apiError(message, message === "Authentication required." ? 401 : 500);
  }
}
