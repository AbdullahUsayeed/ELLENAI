import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        cream: "#FBF5E9",
        cacao: "#2B1D15",
        mint: "#67D7C4",
        peach: "#FFB47B",
        berry: "#D76BA9",
        sun: "#FFD966"
      },
      boxShadow: {
        festival: "0 18px 45px rgba(43, 29, 21, 0.22)",
        glow: "0 0 0 1px rgba(255,255,255,.14), 0 0 30px rgba(255, 190, 120, .35)"
      },
      animation: {
        drift: "drift 16s ease-in-out infinite",
        shimmer: "shimmer 3s ease-in-out infinite"
      },
      keyframes: {
        drift: {
          "0%, 100%": { transform: "translateY(0px) translateX(0px)" },
          "50%": { transform: "translateY(-10px) translateX(8px)" }
        },
        shimmer: {
          "0%, 100%": { opacity: "0.65" },
          "50%": { opacity: "1" }
        }
      }
    }
  },
  plugins: []
};

export default config;
