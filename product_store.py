from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

DEFAULT_PRODUCTS_FILE = Path("products.json")


def normalize_product_url(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return ""

    # Messenger/FB often wraps links as l.facebook.com/l.php?u=<real-url>
    parsed = urlparse(text)
    host = parsed.netloc.lower().replace("www.", "")
    if host.endswith("l.facebook.com") and parsed.path.lower().startswith("/l.php"):
        query = parse_qs(parsed.query)
        wrapped_url = (query.get("u") or [""])[0]
        if wrapped_url:
            text = unquote(wrapped_url)

    text = text.split("?", 1)[0]
    text = text.split("#", 1)[0]
    text = re.sub(r"^https?://", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^www\.", "", text, flags=re.IGNORECASE)
    text = text.rstrip("/")

    parts = [p for p in text.split("/") if p]
    if not parts:
        return ""

    host = parts[0].lower()
    path_parts = parts[1:]

    if host.endswith("instagram.com") and len(path_parts) >= 2 and path_parts[0].lower() in {"p", "reel", "tv"}:
        return f"instagram.com/{path_parts[0].lower()}/{path_parts[1]}"

    if host.endswith("facebook.com"):
        lowered = [p.lower() for p in path_parts]
        if "posts" in lowered:
            idx = lowered.index("posts")
            if idx + 1 < len(path_parts):
                return f"facebook.com/posts/{path_parts[idx + 1]}"
        if "permalink" in lowered:
            idx = lowered.index("permalink")
            if idx + 1 < len(path_parts):
                return f"facebook.com/permalink/{path_parts[idx + 1]}"

    return text


def _clean_product_record(raw_product: dict[str, Any]) -> dict[str, Any] | None:
    name = str(raw_product.get("name", "")).strip()
    if not name:
        return None

    try:
        price = int(raw_product.get("price", 0))
    except (TypeError, ValueError):
        return None
    if price <= 0:
        return None

    currency = str(raw_product.get("currency") or "BDT").strip() or "BDT"
    delivery = str(raw_product.get("delivery") or "20-25 days").strip() or "20-25 days"
    return {
        "name": name,
        "price": price,
        "currency": currency,
        "delivery": delivery,
    }


def load_products(products_file: str | Path = DEFAULT_PRODUCTS_FILE) -> dict[str, list[dict[str, Any]]]:
    path = Path(products_file)
    if not path.exists():
        return {}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(payload, dict):
        return {}

    cleaned: dict[str, list[dict[str, Any]]] = {}
    for raw_url, raw_product in payload.items():
        normalized = normalize_product_url(str(raw_url))
        if not normalized:
            continue

        variants: list[dict[str, Any]] = []
        if isinstance(raw_product, dict):
            cleaned_one = _clean_product_record(raw_product)
            if cleaned_one is not None:
                variants.append(cleaned_one)
        elif isinstance(raw_product, list):
            for item in raw_product:
                if not isinstance(item, dict):
                    continue
                cleaned_one = _clean_product_record(item)
                if cleaned_one is not None:
                    variants.append(cleaned_one)

        if variants:
            cleaned[normalized] = variants

    return cleaned


def add_product(
    full_url: str,
    name: str,
    price: int,
    currency: str,
    delivery: str,
    products_file: str | Path = DEFAULT_PRODUCTS_FILE,
) -> str:
    normalized = normalize_product_url(full_url)
    if not normalized:
        raise ValueError("Invalid product URL")

    clean_name = str(name).strip()
    if not clean_name:
        raise ValueError("Product name is required")

    unit_price = int(price)
    if unit_price <= 0:
        raise ValueError("Price must be positive")

    clean_currency = str(currency).strip() or "BDT"
    clean_delivery = str(delivery).strip() or "20-25 days"

    path = Path(products_file)
    products = load_products(path)
    existing = products.get(normalized, [])
    candidate = {
        "name": clean_name,
        "price": unit_price,
        "currency": clean_currency,
        "delivery": clean_delivery,
    }
    if not any(
        p.get("name") == candidate["name"]
        and int(p.get("price", 0)) == candidate["price"]
        and p.get("currency") == candidate["currency"]
        and p.get("delivery") == candidate["delivery"]
        for p in existing
    ):
        existing.append(candidate)
    products[normalized] = existing

    path.write_text(json.dumps(products, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return normalized


def add_product_links(
    links: list[str],
    name: str,
    price: int,
    currency: str,
    delivery: str,
    products_file: str | Path = DEFAULT_PRODUCTS_FILE,
) -> list[str]:
    """Save one product once and map it to multiple links.
    Returns list of normalized keys that were saved."""
    if not links:
        raise ValueError("At least one product link is required")

    clean_name = str(name).strip()
    if not clean_name:
        raise ValueError("Product name is required")

    unit_price = int(price)
    if unit_price <= 0:
        raise ValueError("Price must be positive")

    clean_currency = str(currency).strip() or "BDT"
    clean_delivery = str(delivery).strip() or "20-25 days"

    path = Path(products_file)
    products = load_products(path)

    normalized_keys: list[str] = []
    for link in links:
        normalized = normalize_product_url(link)
        if not normalized:
            continue
        existing = products.get(normalized, [])
        candidate = {
            "name": clean_name,
            "price": unit_price,
            "currency": clean_currency,
            "delivery": clean_delivery,
        }
        if not any(
            p.get("name") == candidate["name"]
            and int(p.get("price", 0)) == candidate["price"]
            and p.get("currency") == candidate["currency"]
            and p.get("delivery") == candidate["delivery"]
            for p in existing
        ):
            existing.append(candidate)
        products[normalized] = existing
        normalized_keys.append(normalized)

    if not normalized_keys:
        raise ValueError("No valid product links were provided")

    path.write_text(json.dumps(products, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return normalized_keys
