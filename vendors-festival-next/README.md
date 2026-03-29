# VENDORS Marketplace (Next.js + Supabase)

VENDORS is a Next.js 14 App Router marketplace with:

- Supabase auth, database, and storage
- Seller dashboard for shop, products, orders, and inbox
- Buyer-facing immersive shop pages
- Payment screenshot upload flow
- AI-assisted product context and mascot replies (optional OpenAI key)

## 1. Environment setup

Create `.env.local` from `.env.example` and set values:

```
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
OPENAI_API_KEY=
```

`OPENAI_API_KEY` is optional. Without it, mascot replies use fallback logic.

## 2. Supabase setup

Run migrations in this order from Supabase SQL Editor:

1. `supabase/migrations/20260328_vendors_mvp.sql`
2. `supabase/migrations/20260328_order_status_and_storage_policies.sql`
3. `supabase/migrations/20260329_marketplace_ai_messages.sql`

After running, verify:

- Tables: `users`, `shops`, `products`, `orders`, `messages`
- Buckets: `product-images`, `shop-logos`, `payment-receipts`

## 3. Run locally

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## 4. Validate before deploy

```bash
npm run check-env
npm run verify
```

This runs:

- Required environment checks (`npm run check-env`)
- TypeScript checks (`npm run typecheck`)
- Production build (`npm run build`)

## 5. Deploy

Deploy this folder (`vendors-festival-next`) to your host (for example Vercel).

Set the same env vars in production, then add your deployed domain in Supabase Auth URL settings.

## 6. Live flow checklist

1. Sign up seller account
2. Create/update shop
3. Add products
4. Open public shop (`/shop/[slug]`)
5. Send buyer message in storefront drawer
6. Confirm seller receives message in dashboard inbox
7. Place order with payment screenshot
8. Confirm order from seller dashboard

## Notes

- Messages are currently shop-scoped. For strict per-buyer threads, add a conversation/thread key in the `messages` schema.
