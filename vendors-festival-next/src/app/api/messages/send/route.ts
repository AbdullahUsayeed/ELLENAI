import { generateMascotReply } from "@/lib/services/ai";
import { getShopMessages, sendShopMessage } from "@/lib/services/messages";
import { getShopWithProductsById, requireAuthenticatedUser } from "@/lib/services/shops";
import { sendMessageSchema } from "@/lib/validation/schemas";
import { apiError, apiOk } from "@/lib/utils/api";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const parsed = sendMessageSchema.safeParse(body);

    if (!parsed.success) {
      return apiError("Invalid message payload.", 400, parsed.error.flatten());
    }

    let userId: string | undefined;
    if (parsed.data.is_from_seller) {
      const user = await requireAuthenticatedUser();
      userId = user.id;
    }

    const message = await sendShopMessage({
      shopId: parsed.data.shop_id,
      senderName: parsed.data.sender_name,
      message: parsed.data.message,
      isFromSeller: parsed.data.is_from_seller,
      isRead: parsed.data.is_read,
      userId
    });

    let autoReply = null;
    if (!parsed.data.is_from_seller) {
      const shopData = await getShopWithProductsById(parsed.data.shop_id);
      if (shopData) {
        const history = await getShopMessages(parsed.data.shop_id, 20);
        const reply = await generateMascotReply({
          shop: shopData.shop,
          products: shopData.products,
          userMessage: parsed.data.message,
          history
        });

        autoReply = await sendShopMessage({
          shopId: parsed.data.shop_id,
          senderName: `${shopData.shop.name} Mascot`,
          message: reply,
          isFromSeller: true,
          isRead: false,
          userId: shopData.shop.user_id
        }).catch(async () =>
          sendShopMessage({
            shopId: parsed.data.shop_id,
            senderName: `${shopData.shop.name} Mascot`,
            message: reply,
            isFromSeller: false,
            isRead: false
          })
        );
      }
    }

    return apiOk({ message, autoReply }, { status: 201 });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to send message.";
    return apiError(message, message === "Authentication required." ? 401 : 500);
  }
}