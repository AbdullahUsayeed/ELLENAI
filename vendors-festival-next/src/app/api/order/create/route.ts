import { createOrderSchema } from "@/lib/validation/schemas";
import { createOrder } from "@/lib/services/orders";
import { uploadPaymentReceipt } from "@/lib/services/storage";
import { apiError, apiOk } from "@/lib/utils/api";

export async function POST(request: Request) {
  try {
    const contentType = request.headers.get("content-type") || "";
    let file: File | null = null;
    let body: Record<string, unknown>;

    if (contentType.includes("multipart/form-data")) {
      const formData = await request.formData();
      file = formData.get("payment_screenshot") instanceof File ? (formData.get("payment_screenshot") as File) : null;
      body = {
        product_id: formData.get("product_id"),
        shop_id: formData.get("shop_id"),
        buyer_name: formData.get("buyer_name"),
        buyer_phone: formData.get("buyer_phone"),
        address: formData.get("address") ?? formData.get("delivery_address"),
        transaction_id: formData.get("transaction_id")
      };
    } else {
      body = (await request.json()) as Record<string, unknown>;
    }

    let paymentScreenshotUrl: string | undefined;
    if (file) {
      paymentScreenshotUrl = await uploadPaymentReceipt(String(body.shop_id ?? ""), file);
    }

    const parsed = createOrderSchema.safeParse({
      ...body,
      payment_screenshot_url: paymentScreenshotUrl
    });

    if (!parsed.success) {
      return apiError("Invalid order payload.", 400, parsed.error.flatten());
    }

    const order = await createOrder({
      productId: parsed.data.product_id,
      shopId: parsed.data.shop_id,
      buyerName: parsed.data.buyer_name,
      buyerPhone: parsed.data.buyer_phone,
      address: parsed.data.address,
      transactionId: parsed.data.transaction_id,
      paymentScreenshotUrl: parsed.data.payment_screenshot_url
    });

    return apiOk(order, { status: 201 });
  } catch (error) {
    return apiError(error instanceof Error ? error.message : "Unable to create order.", 500);
  }
}
