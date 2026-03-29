import { addProductSchema } from "@/lib/validation/schemas";
import { addProductForShop } from "@/lib/services/products";
import { requireAuthenticatedUser } from "@/lib/services/shops";
import { apiError, apiOk } from "@/lib/utils/api";

export async function POST(request: Request) {
  try {
    const user = await requireAuthenticatedUser();
    const body = await request.json();
    const parsed = addProductSchema.safeParse(body);

    if (!parsed.success) {
      return apiError("Invalid product payload.", 400, parsed.error.flatten());
    }

    const product = await addProductForShop({
      userId: user.id,
      shopId: parsed.data.shop_id,
      name: parsed.data.name,
      description: parsed.data.description,
      price: parsed.data.price,
      imageUrl: parsed.data.image_url,
      stock: parsed.data.stock
    });

    return apiOk(product, { status: 201 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to add product.";
    return apiError(message, message === "Authentication required." ? 401 : 500);
  }
}
