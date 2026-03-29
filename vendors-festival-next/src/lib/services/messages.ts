import type { MessageRecord } from "@/lib/types/marketplace";
import { createSupabaseAdminClient } from "@/lib/supabase/admin";
import { getCurrentSellerShop } from "@/lib/services/shops";
import { normalizeMessageRecord } from "@/lib/utils/marketplace-normalizers";

export async function sendShopMessage(input: {
  shopId: string;
  senderName: string;
  message: string;
  isFromSeller: boolean;
  isRead?: boolean;
  userId?: string;
}) {
  if (input.isFromSeller) {
    if (!input.userId) {
      throw new Error("Authentication required.");
    }

    const sellerShop = await getCurrentSellerShop(input.userId);
    if (!sellerShop || sellerShop.id !== input.shopId) {
      throw new Error("You do not have access to this shop.");
    }
  }

  const admin = createSupabaseAdminClient();
  const { data, error } = await admin
    .from("messages")
    .insert({
      shop_id: input.shopId,
      sender_name: input.senderName,
      message: input.message,
      is_from_seller: input.isFromSeller,
      is_read: input.isRead ?? input.isFromSeller
    })
    .select("*")
    .single();

  if (error || !data) {
    throw new Error(error?.message ?? "Unable to send message.");
  }

  return normalizeMessageRecord(data);
}

export async function getShopMessages(shopId: string, limit = 100): Promise<MessageRecord[]> {
  const admin = createSupabaseAdminClient();
  const { data, error } = await admin
    .from("messages")
    .select("*")
    .eq("shop_id", shopId)
    .order("created_at", { ascending: true })
    .limit(limit);

  if (error) {
    throw new Error(error.message);
  }

  return (data ?? []).map((row) => normalizeMessageRecord(row));
}