import { uploadShopLogo } from "@/lib/services/storage";
import { requireAuthenticatedUser } from "@/lib/services/shops";
import { apiError, apiOk } from "@/lib/utils/api";

export async function POST(request: Request) {
  try {
    const user = await requireAuthenticatedUser();

    const formData = await request.formData();
    const file = formData.get("file");

    if (!(file instanceof File)) {
      return apiError("A file is required.", 400);
    }

    const allowedTypes = ["image/jpeg", "image/png", "image/webp", "image/gif"];
    if (!allowedTypes.includes(file.type)) {
      return apiError("Only JPEG, PNG, WebP, and GIF images are allowed.", 400);
    }

    const maxBytes = 2 * 1024 * 1024; // 2 MB
    if (file.size > maxBytes) {
      return apiError("Logo must be smaller than 2 MB.", 400);
    }

    const url = await uploadShopLogo(user.id, file);
    return apiOk({ url }, { status: 201 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to upload logo.";
    return apiError(message, message === "Authentication required." ? 401 : 500);
  }
}
