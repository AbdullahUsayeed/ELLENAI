import { uploadProductImage } from "@/lib/services/storage";
import { requireAuthenticatedUser, getCurrentSellerShop } from "@/lib/services/shops";
import { apiError, apiOk } from "@/lib/utils/api";

export async function POST(request: Request) {
  try {
    const user = await requireAuthenticatedUser();
    const shop = await getCurrentSellerShop(user.id);

    if (!shop) {
      return apiError("You do not have a shop.", 403);
    }

    const formData = await request.formData();
    const file = formData.get("file");

    if (!(file instanceof File)) {
      return apiError("A file is required.", 400);
    }

    const allowedTypes = ["image/jpeg", "image/png", "image/webp", "image/gif"];
    if (!allowedTypes.includes(file.type)) {
      return apiError("Only JPEG, PNG, WebP, and GIF images are allowed.", 400);
    }

    const maxBytes = 5 * 1024 * 1024; // 5 MB
    if (file.size > maxBytes) {
      return apiError("Image must be smaller than 5 MB.", 400);
    }

    const url = await uploadProductImage(shop.id, file);
    return apiOk({ url }, { status: 201 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to upload image.";
    return apiError(message, message === "Authentication required." ? 401 : 500);
  }
}
