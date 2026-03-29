const vendors = [
  {
    id: "tent-1",
    name: "Jhumur Loom Tent",
    tagline: "Handmade fabrics and street-ready fits",
    zone: "North Alley",
    category: "Fashion",
    rating: 4.9,
    palette: ["#d26c3b", "#d8a140", "#915a31"],
    products: [
      { title: "Printed Shawl", price: "1,450 BDT", desc: "Soft weave, 5 color variants" },
      { title: "Kurti Set", price: "2,300 BDT", desc: "Lightweight daily wear" },
      { title: "Canvas Tote", price: "850 BDT", desc: "Reinforced handle" }
    ]
  },
  {
    id: "tent-2",
    name: "Spice & Clay Corner",
    tagline: "Kitchen craft, spice kits, hand-thrown jars",
    zone: "Center Circle",
    category: "Home",
    rating: 4.8,
    palette: ["#2f7f71", "#74b2a8", "#295d55"],
    products: [
      { title: "Spice Starter Kit", price: "1,200 BDT", desc: "12 curated mixes" },
      { title: "Clay Jar Set", price: "1,900 BDT", desc: "Food-safe glazed finish" },
      { title: "Bamboo Tray", price: "780 BDT", desc: "Fold edge handcrafted" }
    ]
  },
  {
    id: "tent-3",
    name: "Orbit Gadget Tent",
    tagline: "Tiny tech, charging tools, travel gear",
    zone: "East Row",
    category: "Tech",
    rating: 4.6,
    palette: ["#1f2f4a", "#5379b7", "#2e4977"],
    products: [
      { title: "Mini Power Bank", price: "1,650 BDT", desc: "10,000 mAh compact build" },
      { title: "Travel Adapter", price: "1,050 BDT", desc: "Multi-country compatible" },
      { title: "Cable Kit", price: "680 BDT", desc: "Type-C + Lightning combo" }
    ]
  },
  {
    id: "tent-4",
    name: "Petal Note Studio",
    tagline: "Art paper, stickers, journals, desk joy",
    zone: "Sun Lane",
    category: "Lifestyle",
    rating: 4.7,
    palette: ["#ba4f5b", "#e1909b", "#8a3342"],
    products: [
      { title: "Planner Pack", price: "1,150 BDT", desc: "Monthly + weekly inserts" },
      { title: "Sticker Stack", price: "420 BDT", desc: "70+ illustrated pieces" },
      { title: "Sketch Journal", price: "980 BDT", desc: "180gsm bleed-resistant" }
    ]
  },
  {
    id: "tent-5",
    name: "Moonlight Trinkets",
    tagline: "Rings, pendants, and tiny stories",
    zone: "River Walk",
    category: "Accessories",
    rating: 4.9,
    palette: ["#4a3f7f", "#8c7bce", "#2d245a"],
    products: [
      { title: "Star Pendant", price: "990 BDT", desc: "Polished alloy finish" },
      { title: "Minimal Ring", price: "740 BDT", desc: "Adjustable fit" },
      { title: "Charm Set", price: "1,280 BDT", desc: "3-piece mix and match" }
    ]
  },
  {
    id: "tent-6",
    name: "Green Root Organics",
    tagline: "Tea blends, skincare bars, clean ingredients",
    zone: "West Pocket",
    category: "Wellness",
    rating: 4.5,
    palette: ["#4a7a39", "#92bc7a", "#315226"],
    products: [
      { title: "Herbal Tea Box", price: "860 BDT", desc: "12 calming sachets" },
      { title: "Soap Trio", price: "690 BDT", desc: "Cold-processed bars" },
      { title: "Face Oil", price: "1,350 BDT", desc: "Evening hydration blend" }
    ]
  }
];

const categories = ["All", ...new Set(vendors.map((vendor) => vendor.category))];

const tentsGrid = document.getElementById("tentsGrid");
const shopPanel = document.getElementById("shopPanel");
const searchInput = document.getElementById("searchInput");
const categoryRow = document.getElementById("categoryRow");
const tentTemplate = document.getElementById("tentCardTemplate");
const productTemplate = document.getElementById("productCardTemplate");
const scrollButton = document.getElementById("scrollToMarket");

let activeCategory = "All";
let activeVendorId = null;

function colorBand(palette) {
  return `linear-gradient(90deg, ${palette[0]} 0, ${palette[1]} 55%, ${palette[2]} 100%)`;
}

function filteredVendors() {
  const q = searchInput.value.trim().toLowerCase();
  return vendors.filter((vendor) => {
    const categoryOk = activeCategory === "All" || vendor.category === activeCategory;
    if (!categoryOk) return false;

    if (!q) return true;
    const blob = [
      vendor.name,
      vendor.tagline,
      vendor.category,
      vendor.zone,
      ...vendor.products.map((product) => `${product.title} ${product.desc}`)
    ].join(" ").toLowerCase();

    return blob.includes(q);
  });
}

function renderCategories() {
  categoryRow.innerHTML = "";

  categories.forEach((category) => {
    const btn = document.createElement("button");
    btn.className = `category-pill ${category === activeCategory ? "active" : ""}`;
    btn.textContent = category;
    btn.addEventListener("click", () => {
      activeCategory = category;
      renderCategories();
      renderTents();
    });
    categoryRow.appendChild(btn);
  });
}

function renderTents() {
  const list = filteredVendors();
  tentsGrid.innerHTML = "";

  if (!list.length) {
    tentsGrid.innerHTML = `<p style="margin:0;color:#6d5c45;">No tents found. Try another keyword.</p>`;
    return;
  }

  list.forEach((vendor, i) => {
    const node = tentTemplate.content.firstElementChild.cloneNode(true);
    node.style.animationDelay = `${i * 45}ms`;
    node.querySelector(".tent-tag").textContent = vendor.category;
    node.querySelector(".vendor-rating").textContent = `★ ${vendor.rating}`;
    node.querySelector(".tent-banner").style.background = colorBand(vendor.palette);
    node.querySelector(".tent-name").textContent = vendor.name;
    node.querySelector(".tent-blurb").textContent = vendor.tagline;
    node.querySelector(".location-chip").textContent = vendor.zone;
    node.querySelector(".items-chip").textContent = `${vendor.products.length} items`;

    if (activeVendorId === vendor.id) {
      node.classList.add("active");
    }

    node.addEventListener("click", () => {
      activeVendorId = vendor.id;
      renderTents();
      renderShop(vendor);
    });

    tentsGrid.appendChild(node);
  });

  if (!activeVendorId && list[0]) {
    activeVendorId = list[0].id;
    renderShop(list[0]);
  }
}

function renderShop(vendor) {
  shopPanel.innerHTML = "";

  const title = document.createElement("h3");
  title.textContent = vendor.name;

  const summary = document.createElement("p");
  summary.className = "shop-summary";
  summary.textContent = `${vendor.tagline} • ${vendor.zone} • Rated ${vendor.rating}`;

  const banner = document.createElement("div");
  banner.className = "banner-preview";
  banner.style.background = colorBand(vendor.palette);

  const grid = document.createElement("div");
  grid.className = "product-grid";

  vendor.products.forEach((product) => {
    const card = productTemplate.content.firstElementChild.cloneNode(true);
    card.querySelector(".product-image").style.background = colorBand(vendor.palette);
    card.querySelector(".product-title").textContent = product.title;
    card.querySelector(".product-desc").textContent = product.desc;
    card.querySelector(".price").textContent = product.price;
    grid.appendChild(card);
  });

  shopPanel.append(title, summary, banner, grid);
}

scrollButton.addEventListener("click", () => {
  document.getElementById("market").scrollIntoView({ behavior: "smooth" });
});

searchInput.addEventListener("input", () => {
  activeVendorId = null;
  renderTents();
});

renderCategories();
renderTents();
