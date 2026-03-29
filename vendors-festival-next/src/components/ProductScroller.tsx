"use client";

import { motion } from "framer-motion";
import type { Product } from "@/data/vendors";

type ProductScrollerProps = {
  products: Product[];
};

export function ProductScroller({ products }: ProductScrollerProps) {
  return (
    <div className="custom-scroll mt-4 flex gap-3 overflow-x-auto pb-2">
      {products.map((product) => (
        <motion.div
          key={product.id}
          whileHover={{ y: -4, scale: 1.03 }}
          className="min-w-[155px] rounded-2xl border border-white/50 bg-white/80 p-2 shadow-sm"
        >
          <img
            src={product.image}
            alt={product.name}
            className="h-24 w-full rounded-xl object-cover"
            loading="lazy"
          />
          <p className="mt-2 text-sm font-semibold text-cacao">{product.name}</p>
          <p className="text-xs font-medium text-cacao/70">{product.price}</p>
        </motion.div>
      ))}
    </div>
  );
}
