import { redirect } from "next/navigation";
import { SellerDashboard } from "@/components/dashboard/SellerDashboard";
import { getShopMessages } from "@/lib/services/messages";
import { getSellerOrders } from "@/lib/services/orders";
import { getSellerProducts } from "@/lib/services/products";
import { getCurrentAuthenticatedUser, getCurrentSellerShop } from "@/lib/services/shops";

export default async function DashboardPage() {
  const user = await getCurrentAuthenticatedUser();
  if (!user) {
    redirect("/login");
  }

  const shop = await getCurrentSellerShop(user.id);
  if (!shop) {
    redirect("/signup");
  }

  const [products, orders, initialMessages] = await Promise.all([
    getSellerProducts(shop.id, user.id),
    getSellerOrders(shop.id, user.id),
    getShopMessages(shop.id)
  ]);

  return (
    <main className="min-h-screen bg-[#070B18] px-4 py-8 text-[#E8D8A8] sm:px-6 lg:px-10">
      <div className="mx-auto max-w-7xl">
        <div className="mb-8">
          <p className="text-xs font-bold uppercase tracking-[0.28em] text-[#D8BF86]/70">Seller workspace</p>
          <h1 className="festival-title mt-3 text-4xl font-black text-[#F5E4BD]">{shop.shop_name}</h1>
          <p className="mt-2 text-sm text-[#C8B68E]/72">Public link: /shop/{shop.slug}</p>
        </div>
        <SellerDashboard shop={shop} products={products} orders={orders} initialMessages={initialMessages} />
      </div>
    </main>
  );
}
