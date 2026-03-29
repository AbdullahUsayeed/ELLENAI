export type Product = {
  id: string;
  name: string;
  price: string;
  image: string;
};

export type Vendor = {
  id: string;
  name: string;
  banner: string;
  tagline: string;
  status: "active" | "offline";
  canopy: [string, string];
  products: Product[];
};

export const vendors: Vendor[] = [
  {
    id: "tent-1",
    name: "Moonthread Atelier",
    banner: "Handpicked eveningwear and statement fabrics",
    tagline: "Signature edits for elevated street style",
    status: "active",
    canopy: ["#FF8E72", "#E8577E"],
    products: [
      { id: "p1", name: "Aurora Cape", price: "BDT 4,200", image: "https://picsum.photos/300/220?random=11" },
      { id: "p2", name: "Velvet Slip", price: "BDT 3,400", image: "https://picsum.photos/300/220?random=12" },
      { id: "p3", name: "Satin Scarf", price: "BDT 1,250", image: "https://picsum.photos/300/220?random=13" }
    ]
  },
  {
    id: "tent-2",
    name: "Citrus Craft Bar",
    banner: "Fresh accessories and joy-colored details",
    tagline: "Playful pieces for every festival look",
    status: "active",
    canopy: ["#FFD66B", "#FF9E5E"],
    products: [
      { id: "p4", name: "Lemon Bucket Hat", price: "BDT 980", image: "https://picsum.photos/300/220?random=21" },
      { id: "p5", name: "Coral Tote", price: "BDT 1,450", image: "https://picsum.photos/300/220?random=22" },
      { id: "p6", name: "Pop Bead Set", price: "BDT 860", image: "https://picsum.photos/300/220?random=23" }
    ]
  },
  {
    id: "tent-3",
    name: "Nila Tech Kiosk",
    banner: "Portable gadgets tuned for city life",
    tagline: "Sharp utility with premium finish",
    status: "offline",
    canopy: ["#6CB4FF", "#5C6EFF"],
    products: [
      { id: "p7", name: "Pocket Charger", price: "BDT 2,150", image: "https://picsum.photos/300/220?random=31" },
      { id: "p8", name: "Travel Dock", price: "BDT 1,780", image: "https://picsum.photos/300/220?random=32" },
      { id: "p9", name: "Mini Speaker", price: "BDT 2,600", image: "https://picsum.photos/300/220?random=33" }
    ]
  },
  {
    id: "tent-4",
    name: "Bloom Rituals",
    banner: "Scent, skincare and slow-living essentials",
    tagline: "Wellness gifts curated in small batches",
    status: "active",
    canopy: ["#7DE0C0", "#4FC3B2"],
    products: [
      { id: "p10", name: "Neroli Mist", price: "BDT 1,390", image: "https://picsum.photos/300/220?random=41" },
      { id: "p11", name: "Tea Duo", price: "BDT 1,120", image: "https://picsum.photos/300/220?random=42" },
      { id: "p12", name: "Body Balm", price: "BDT 1,650", image: "https://picsum.photos/300/220?random=43" }
    ]
  },
  {
    id: "tent-5",
    name: "Amber Trinket House",
    banner: "Jewels and tiny keepsakes with story",
    tagline: "Warm-toned accessories for statement layering",
    status: "active",
    canopy: ["#F5A4C7", "#D76BA9"],
    products: [
      { id: "p13", name: "Nova Pendant", price: "BDT 1,480", image: "https://picsum.photos/300/220?random=51" },
      { id: "p14", name: "Halo Ring", price: "BDT 1,050", image: "https://picsum.photos/300/220?random=52" },
      { id: "p15", name: "Charm Chain", price: "BDT 1,780", image: "https://picsum.photos/300/220?random=53" }
    ]
  },
  {
    id: "tent-6",
    name: "Drift Home Studio",
    banner: "Tableware and decor for cozy hosting",
    tagline: "Artisan objects with a festive twist",
    status: "offline",
    canopy: ["#B6A4FF", "#8D7CFF"],
    products: [
      { id: "p16", name: "Ceramic Set", price: "BDT 2,950", image: "https://picsum.photos/300/220?random=61" },
      { id: "p17", name: "Linen Runner", price: "BDT 1,390", image: "https://picsum.photos/300/220?random=62" },
      { id: "p18", name: "Glass Lantern", price: "BDT 2,100", image: "https://picsum.photos/300/220?random=63" }
    ]
  }
];
