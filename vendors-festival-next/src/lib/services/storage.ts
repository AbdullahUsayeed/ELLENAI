import { createSupabaseAdminClient } from "@/lib/supabase/admin";

export const BUCKETS = {
  productImages: "product-images",
  shopLogos: "shop-logos",
  paymentReceipts: "payment-receipts"
} as const;

export async function uploadToSupabase(params: {
  bucket: (typeof BUCKETS)[keyof typeof BUCKETS];
  file: File;
  pathPrefix?: string;
  fileName?: string;
}) {
  const admin = createSupabaseAdminClient();
  const bytes = new Uint8Array(await params.file.arrayBuffer());
  const safeName = (params.fileName ?? params.file.name).replace(/[^a-zA-Z0-9._-]/g, "-");
  const path = [params.pathPrefix?.replace(/^\/+|\/+$/g, ""), `${Date.now()}-${safeName}`]
    .filter(Boolean)
    .join("/");

  const { error } = await admin.storage.from(params.bucket).upload(path, bytes, {
    contentType: params.file.type,
    upsert: true
  });

  if (error) {
    throw new Error(error.message);
  }

  const { data } = admin.storage.from(params.bucket).getPublicUrl(path);
  return data.publicUrl;
}

export async function uploadProductImage(shopId: string, file: File) {
  return uploadToSupabase({ bucket: BUCKETS.productImages, pathPrefix: shopId, file });
}

export async function uploadShopLogo(userId: string, file: File) {
  return uploadToSupabase({ bucket: BUCKETS.shopLogos, pathPrefix: userId, file });
}

export async function uploadPaymentReceipt(shopId: string, file: File) {
  return uploadToSupabase({ bucket: BUCKETS.paymentReceipts, pathPrefix: shopId, file });
}