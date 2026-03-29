import { NextResponse } from "next/server";
import { getShopBySlug } from "@/lib/services/shops";

export async function GET(_request: Request, context: { params: { shop_slug: string } }) {
  const shopData = await getShopBySlug(context.params.shop_slug);

  if (!shopData) {
    return NextResponse.json({ error: "Shop not found." }, { status: 404 });
  }

  return NextResponse.json(
    shopData.products.map((product) => ({
      id: product.id,
      name: product.name,
      description: product.description,
      price: product.price,
      stock: product.stock,
      image_url: product.image_url,
      ai_context: product.ai_context
    }))
  );
}