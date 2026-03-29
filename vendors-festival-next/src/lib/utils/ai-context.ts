type ProductForAIContext = {
  name: string;
  description?: string | null;
  price: number;
};

export function generateAIContext(product: ProductForAIContext) {
  return [
    `Name: ${product.name.trim()}`,
    `Description: ${(product.description ?? "").trim()}`,
    `Price: ${product.price} BDT`
  ]
    .filter((part) => !part.endsWith(": "))
    .join(" | ");
}