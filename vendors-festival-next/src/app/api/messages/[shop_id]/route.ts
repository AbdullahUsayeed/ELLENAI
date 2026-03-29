import { getShopMessages } from "@/lib/services/messages";
import { apiError, apiOk } from "@/lib/utils/api";

export async function GET(_request: Request, context: { params: { shop_id: string } }) {
  try {
    const messages = await getShopMessages(context.params.shop_id);
    return apiOk(messages);
  } catch (error) {
    return apiError(error instanceof Error ? error.message : "Unable to fetch messages.", 500);
  }
}