create extension if not exists pgcrypto;

alter table if exists public.users
  add column if not exists avatar_url text;

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public' and table_name = 'shops' and column_name = 'shop_name'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public' and table_name = 'shops' and column_name = 'name'
  ) then
    alter table public.shops rename column shop_name to name;
  end if;
end $$;

alter table if exists public.shops
  add column if not exists name text,
  add column if not exists payment_methods jsonb not null default '[]'::jsonb,
  add column if not exists rating double precision not null default 4.5;

update public.shops
set name = coalesce(nullif(name, ''), 'Untitled Shop')
where name is null or trim(name) = '';

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public' and table_name = 'shops' and column_name = 'bkash_number'
  ) then
    update public.shops
    set payment_methods = case
      when coalesce(trim(bkash_number), '') = '' then coalesce(payment_methods, '[]'::jsonb)
      when jsonb_typeof(coalesce(payment_methods, '[]'::jsonb)) = 'array' and jsonb_array_length(coalesce(payment_methods, '[]'::jsonb)) > 0 then payment_methods
      else jsonb_build_array(jsonb_build_object('type', 'bKash', 'number', bkash_number))
    end;
  end if;
end $$;

alter table if exists public.shops
  alter column name set not null,
  alter column rating set default 4.5,
  alter column rating set not null,
  alter column is_verified set default false,
  alter column is_verified set not null;

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public' and table_name = 'shops' and column_name = 'tent_theme'
  ) then
    alter table public.shops
      alter column tent_theme drop default;

    alter table public.shops
      alter column tent_theme type jsonb
      using case
        when tent_theme is null then jsonb_build_object('key', 'fashion-edit')
        else jsonb_build_object('key', trim(both '"' from tent_theme::text))
      end;

    alter table public.shops
      alter column tent_theme set default jsonb_build_object('key', 'fashion-edit');
  else
    alter table public.shops add column tent_theme jsonb not null default jsonb_build_object('key', 'fashion-edit');
  end if;
end $$;

update public.shops
set tent_theme = jsonb_build_object('key', 'fashion-edit')
where tent_theme is null or tent_theme = '{}'::jsonb;

alter table if exists public.products
  add column if not exists ai_context text not null default '';

update public.products
set ai_context = trim(concat_ws(' | ', name, description, concat(price, ' BDT')))
where coalesce(ai_context, '') = '';

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public' and table_name = 'orders' and column_name = 'delivery_address'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public' and table_name = 'orders' and column_name = 'address'
  ) then
    alter table public.orders rename column delivery_address to address;
  end if;
end $$;

alter table if exists public.orders
  add column if not exists address text,
  add column if not exists payment_screenshot_url text;

update public.orders
set address = coalesce(nullif(address, ''), 'Address not provided')
where address is null or trim(address) = '';

update public.orders
set status = 'pending'
where coalesce(status, '') not in ('pending', 'confirmed');

alter table if exists public.orders
  alter column address set not null,
  alter column status set default 'pending',
  drop constraint if exists orders_status_check,
  add constraint orders_status_check check (status in ('pending', 'confirmed'));

create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  shop_id uuid references public.shops(id) on delete cascade,
  sender_name text,
  message text,
  is_from_seller boolean default false,
  is_read boolean default false,
  created_at timestamptz default timezone('utc', now())
);

alter table if exists public.messages
  add column if not exists id uuid default gen_random_uuid(),
  add column if not exists shop_id uuid references public.shops(id) on delete cascade,
  add column if not exists sender_name text,
  add column if not exists message text,
  add column if not exists is_from_seller boolean default false,
  add column if not exists is_read boolean default false,
  add column if not exists created_at timestamptz default timezone('utc', now());

update public.messages
set is_from_seller = coalesce(is_from_seller, false),
    is_read = coalesce(is_read, false),
    created_at = coalesce(created_at, timezone('utc', now()))
where is_from_seller is null or is_read is null or created_at is null;

do $$
begin
  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'messages' and column_name = 'sender_name'
  ) then
    execute 'update public.messages set sender_name = ''Unknown'' where sender_name is null';
    execute 'alter table public.messages alter column sender_name set not null';
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'messages' and column_name = 'message'
  ) then
    execute 'update public.messages set message = '''' where message is null';
    execute 'alter table public.messages alter column message set not null';
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'messages' and column_name = 'is_from_seller'
  ) then
    execute 'alter table public.messages alter column is_from_seller set not null';
    execute 'alter table public.messages alter column is_from_seller set default false';
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'messages' and column_name = 'is_read'
  ) then
    execute 'alter table public.messages alter column is_read set not null';
    execute 'alter table public.messages alter column is_read set default false';
  end if;

  if exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'messages' and column_name = 'created_at'
  ) then
    execute 'alter table public.messages alter column created_at set not null';
    execute 'alter table public.messages alter column created_at set default timezone(''utc'', now())';
  end if;
end $$;

create index if not exists idx_messages_shop_id on public.messages(shop_id);

alter table public.messages enable row level security;

drop policy if exists "Messages are public readable" on public.messages;
create policy "Messages are public readable"
on public.messages for select
using (true);

drop policy if exists "Anyone can create messages" on public.messages;
create policy "Anyone can create messages"
on public.messages for insert
with check (true);

drop policy if exists "Owners can update message read state" on public.messages;
create policy "Owners can update message read state"
on public.messages for update
using (
  exists (
    select 1
    from public.shops
    where public.shops.id = public.messages.shop_id and public.shops.user_id = auth.uid()
  )
);

insert into storage.buckets (id, name, public)
values ('payment-receipts', 'payment-receipts', true)
on conflict (id) do nothing;

drop policy if exists "Public can read payment receipts" on storage.objects;
create policy "Public can read payment receipts"
on storage.objects for select
using (bucket_id = 'payment-receipts');

drop policy if exists "Anyone can upload payment receipts" on storage.objects;
create policy "Anyone can upload payment receipts"
on storage.objects for insert
with check (bucket_id = 'payment-receipts');

drop policy if exists "Authenticated can update payment receipts" on storage.objects;
create policy "Authenticated can update payment receipts"
on storage.objects for update
to authenticated
using (bucket_id = 'payment-receipts');