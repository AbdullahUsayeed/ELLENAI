export function slugifyShopName(value: string) {
  const slug = value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/[\s_-]+/g, "-")
    .replace(/^-+|-+$/g, "");

  return slug || "tent-shop";
}

export async function generateUniqueShopSlug(
  shopName: string,
  slugExists: (slug: string) => Promise<boolean>
) {
  const baseSlug = slugifyShopName(shopName);

  if (!(await slugExists(baseSlug))) {
    return baseSlug;
  }

  for (let attempt = 0; attempt < 12; attempt += 1) {
    const suffix = Math.floor(1000 + Math.random() * 9000).toString();
    const candidate = `${baseSlug}-${suffix}`;
    if (!(await slugExists(candidate))) {
      return candidate;
    }
  }

  throw new Error("Unable to generate a unique shop slug.");
}
