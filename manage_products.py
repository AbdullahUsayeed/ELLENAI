from __future__ import annotations

import argparse
import sys

from product_store import DEFAULT_PRODUCTS_FILE, add_product_links


def _build_links(product: dict[str, object]) -> list[str]:
    ig = str(product.get("instagram_link") or "").strip()
    fb = str(product.get("facebook_link") or "").strip()
    return [link for link in [ig, fb] if link]


def _save_product(product: dict[str, object], idx_label: str) -> None:
    links = _build_links(product)
    if not links:
        print(f"[{idx_label}] Skipped: no valid links")
        return

    normalized_keys = add_product_links(
        links=links,
        name=str(product.get("name") or "").strip(),
        price=int(product.get("price") or 0),
        currency=str(product.get("currency") or "BDT").strip() or "BDT",
        delivery=str(product.get("delivery") or "20-25 days").strip() or "20-25 days",
    )
    print(f"[{idx_label}] Saved product for: {', '.join(normalized_keys)}")


def _clear_products_file() -> None:
    DEFAULT_PRODUCTS_FILE.write_text("{}\n", encoding="utf-8")
    print(f"Cleared existing products from {DEFAULT_PRODUCTS_FILE}")


def _run_interactive_mode(target_count: int | None = None) -> None:
    print("Interactive Product Entry (press Enter on product name to finish)")
    print("Tip: you can leave Facebook link empty if you don't have it yet.")
    if target_count is not None:
        print(f"Target: add {target_count} product(s).")

    count = 0
    while True:
        if target_count is not None and count >= target_count:
            break

        next_label = count + 1
        if target_count is None:
            print(f"\n--- New Product #{next_label:02d} ---")
        else:
            print(f"\n--- New Product #{next_label:02d} of {target_count:02d} ---")

        name = input("Product name: ").strip()
        if not name:
            break

        instagram_link = input("Instagram link: ").strip()
        facebook_link = input("Facebook/Messenger link (optional): ").strip()

        while True:
            price_text = input("Price (number): ").strip()
            try:
                price = int(price_text)
                if price <= 0:
                    raise ValueError()
                break
            except ValueError:
                print("Please enter a valid positive number, e.g. 1800")

        currency = input("Currency [BDT]: ").strip() or "BDT"
        delivery = input("Delivery [20-25 days]: ").strip() or "20-25 days"

        product = {
            "instagram_link": instagram_link,
            "facebook_link": facebook_link,
            "name": name,
            "price": price,
            "currency": currency,
            "delivery": delivery,
        }
        count += 1
        _save_product(product, f"I{count:02d}")

    print(f"\nInteractive mode finished. Added {count} product(s).")





if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage EllenAI manual product entries")
    parser.add_argument(
        "--mode",
        choices=["interactive"],
        default="interactive",
        help="add products one by one (interactive mode)",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="remove all existing products before adding new ones",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="stop interactive entry after this many products",
    )
    args = parser.parse_args()

    if args.count is not None and args.count <= 0:
        print("--count must be a positive number")
        raise SystemExit(1)

    if args.clear:
        _clear_products_file()

    if not sys.stdin.isatty():
        print("Interactive mode needs a real terminal. Run this in Terminal, not Output/Debug Console.")
        raise SystemExit(1)
    _run_interactive_mode(args.count)
