create extension if not exists pgcrypto;

create table if not exists public.users (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null,
  email text not null unique,
  created_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.shops (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references public.users(id) on delete cascade,
  shop_name text not null,
  slug text not null unique,
  tent_theme text not null default 'fashion-edit',
  bkash_number text,
  logo_url text,
  is_verified boolean not null default false,
  created_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.products (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid not null references public.shops(id) on delete cascade,
  name text not null,
  description text not null,
  price integer not null check (price > 0),
  image_url text,
  stock integer not null default 1 check (stock >= 0),
  created_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.orders (
  id uuid primary key default gen_random_uuid(),
  product_id uuid not null references public.products(id) on delete cascade,
  shop_id uuid not null references public.shops(id) on delete cascade,
  buyer_name text not null,
  buyer_phone text not null,
  delivery_address text not null,
  transaction_id text not null,
  status text not null default 'pending',
  created_at timestamptz not null default timezone('utc', now())
);

create index if not exists idx_shops_user_id on public.shops(user_id);
create index if not exists idx_products_shop_id on public.products(shop_id);
create index if not exists idx_orders_shop_id on public.orders(shop_id);
create index if not exists idx_orders_product_id on public.orders(product_id);

alter table public.users enable row level security;
alter table public.shops enable row level security;
alter table public.products enable row level security;
alter table public.orders enable row level security;

drop policy if exists "Users can view their profile" on public.users;
create policy "Users can view their profile"
on public.users for select
using (auth.uid() = id);

drop policy if exists "Users can insert their profile" on public.users;
create policy "Users can insert their profile"
on public.users for insert
with check (auth.uid() = id);

drop policy if exists "Users can update their profile" on public.users;
create policy "Users can update their profile"
on public.users for update
using (auth.uid() = id);

drop policy if exists "Shops are public readable" on public.shops;
create policy "Shops are public readable"
on public.shops for select
using (true);

drop policy if exists "Owners can create their shop" on public.shops;
create policy "Owners can create their shop"
on public.shops for insert
with check (auth.uid() = user_id);

drop policy if exists "Owners can update their shop" on public.shops;
create policy "Owners can update their shop"
on public.shops for update
using (auth.uid() = user_id);

drop policy if exists "Products are public readable" on public.products;
create policy "Products are public readable"
on public.products for select
using (true);

drop policy if exists "Owners can create products" on public.products;
create policy "Owners can create products"
on public.products for insert
with check (
  exists (
    select 1
    from public.shops
    where public.shops.id = shop_id and public.shops.user_id = auth.uid()
  )
);

drop policy if exists "Owners can update products" on public.products;
create policy "Owners can update products"
on public.products for update
using (
  exists (
    select 1
    from public.shops
    where public.shops.id = shop_id and public.shops.user_id = auth.uid()
  )
);

drop policy if exists "Owners can delete products" on public.products;
create policy "Owners can delete products"
on public.products for delete
using (
  exists (
    select 1
    from public.shops
    where public.shops.id = shop_id and public.shops.user_id = auth.uid()
  )
);

drop policy if exists "Anyone can create orders" on public.orders;
create policy "Anyone can create orders"
on public.orders for insert
with check (true);

drop policy if exists "Owners can view their shop orders" on public.orders;
create policy "Owners can view their shop orders"
on public.orders for select
using (
  exists (
    select 1
    from public.shops
    where public.shops.id = shop_id and public.shops.user_id = auth.uid()
  )
);

insert into storage.buckets (id, name, public)
values
  ('product-images', 'product-images', true),
  ('shop-logos', 'shop-logos', true)
on conflict (id) do nothing;

drop policy if exists "Public can read product images" on storage.objects;
create policy "Public can read product images"
on storage.objects for select
using (bucket_id = 'product-images');

drop policy if exists "Public can read shop logos" on storage.objects;
create policy "Public can read shop logos"
on storage.objects for select
using (bucket_id = 'shop-logos');

drop policy if exists "Authenticated can upload product images" on storage.objects;
create policy "Authenticated can upload product images"
on storage.objects for insert
to authenticated
with check (bucket_id = 'product-images');

drop policy if exists "Authenticated can upload shop logos" on storage.objects;
create policy "Authenticated can upload shop logos"
on storage.objects for insert
to authenticated
with check (bucket_id = 'shop-logos');
