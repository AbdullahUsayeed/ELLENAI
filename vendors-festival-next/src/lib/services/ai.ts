import { env } from "@/lib/env";
import type { MessageRecord, ProductRecord, ShopRecord } from "@/lib/types/marketplace";

function buildProductPrompt(products: ProductRecord[]) {
  return products
    .map((product) => `- ${product.ai_context}`)
    .join("\n");
}

function buildPaymentPrompt(shop: ShopRecord) {
  if (shop.payment_methods.length === 0) {
    return "No payment methods configured yet.";
  }

  return shop.payment_methods
    .map((method) => `${method.type}: ${method.number}`)
    .join(" | ");
}

function fallbackMascotReply(input: {
  shop: ShopRecord;
  products: ProductRecord[];
  userMessage: string;
}) {
  const query = input.userMessage.toLowerCase();
  const match = input.products.find((product) => product.ai_context.toLowerCase().includes(query)) ?? input.products[0];

  if (match) {
    return `${match.name} is available for ${match.price} BDT. ${match.description.slice(0, 120)}${match.description.length > 120 ? "..." : ""}`;
  }

  return `${input.shop.name} is here to help. Ask about products, stock, or payment and I will guide you.`;
}

export async function generateMascotReply(input: {
  shop: ShopRecord;
  products: ProductRecord[];
  userMessage: string;
  history: MessageRecord[];
}) {
  if (!env.openaiApiKey) {
    return fallbackMascotReply(input);
  }

  const recentHistory = input.history
    .slice(-8)
    .map((message) => ({
      role: message.is_from_seller ? "assistant" : "user",
      content: `${message.sender_name}: ${message.message}`
    }));

  try {
    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${env.openaiApiKey}`
      },
      body: JSON.stringify({
        model: "gpt-4.1-mini",
        temperature: 0.5,
        messages: [
          {
            role: "system",
            content: [
              "You are the VENDORS mascot assistant for a marketplace shop.",
              "Be concise, warm, product-aware, and action-oriented.",
              "Use the available catalog only. Do not invent products or prices.",
              `Shop: ${input.shop.name}`,
              `Payment methods: ${buildPaymentPrompt(input.shop)}`,
              `Catalog:\n${buildProductPrompt(input.products)}`
            ].join("\n")
          },
          ...recentHistory,
          { role: "user", content: input.userMessage }
        ]
      })
    });

    if (!response.ok) {
      throw new Error(`OpenAI request failed with status ${response.status}`);
    }

    const payload = (await response.json()) as {
      choices?: Array<{ message?: { content?: string } }>;
    };

    const content = payload.choices?.[0]?.message?.content?.trim();
    return content || fallbackMascotReply(input);
  } catch {
    return fallbackMascotReply(input);
  }
}