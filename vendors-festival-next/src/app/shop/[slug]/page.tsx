import { notFound } from "next/navigation";
import { getShopBySlug } from "@/lib/services/shops";
import { ShopInteriorImmersive } from "@/components/ShopInteriorImmersive";

export default async function PublicShopPage({ params }: { params: { slug: string } }) {
  const data = await getShopBySlug(params.slug);
  if (!data) {
    notFound();
  }

  return <ShopInteriorImmersive shop={data.shop} products={data.products} />;
}