-- Allow shop owners to update the status of their own orders
drop policy if exists "Owners can update order status" on public.orders;
create policy "Owners can update order status"
on public.orders for update
using (
  exists (
    select 1
    from public.shops
    where public.shops.id = shop_id and public.shops.user_id = auth.uid()
  )
);

-- Allow shop owners to upsert storage objects in their product-images folder
drop policy if exists "Owners can update product images" on storage.objects;
create policy "Owners can update product images"
on storage.objects for update
to authenticated
using (bucket_id = 'product-images');

drop policy if exists "Owners can update shop logos" on storage.objects;
create policy "Owners can update shop logos"
on storage.objects for update
to authenticated
using (bucket_id = 'shop-logos');
