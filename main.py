from __future__ import annotations

import asyncio
from collections import deque
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from openai import APIError, OpenAI
from dotenv import load_dotenv
from ellenai.routes import RouteDeps, build_router
from ellenai.settings import load_settings
from ellenai.state_store import StateStore
from ellenai.task_supervisor import TaskSupervisor
from ellenai.webhook_events import extract_webhook_events, verify_meta_signature
from product_store import load_products, normalize_product_url


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ellenai")

load_dotenv()

settings = load_settings()

OPENAI_API_KEY = settings.openai_api_key
PAGE_ACCESS_TOKEN = settings.page_access_token
PAGE_ID = settings.page_id
VERIFY_TOKEN = settings.verify_token
APP_SECRET = settings.app_secret
ADMIN_TOKEN = settings.admin_token

STATE_DB_PATH = settings.state_db_path
MESSAGE_SEND_DELAY_SECONDS = settings.message_send_delay_seconds
ENABLE_REPLY_REWRITE = settings.enable_reply_rewrite
REWRITE_CACHE_TTL_SECONDS = settings.rewrite_cache_ttl_seconds
INTENT_CACHE_TTL_SECONDS = settings.intent_cache_ttl_seconds
INTENT_CACHE_MAX_SIZE = settings.intent_cache_max_size
REWRITE_CACHE_MAX_SIZE = settings.rewrite_cache_max_size
SESSION_CACHE_MAX_SIZE = settings.session_cache_max_size

OPENAI_RETRY_ATTEMPTS = settings.openai_retry_attempts
OPENAI_RETRY_MIN_SECONDS = settings.openai_retry_min_seconds
OPENAI_RETRY_MAX_SECONDS = settings.openai_retry_max_seconds

USER_RATE_LIMIT_COUNT = settings.user_rate_limit_count
USER_RATE_LIMIT_WINDOW_SECONDS = settings.user_rate_limit_window_seconds
WEBHOOK_RATE_LIMIT_COUNT = settings.webhook_rate_limit_count
WEBHOOK_RATE_LIMIT_WINDOW_SECONDS = settings.webhook_rate_limit_window_seconds
PRODUCTS_FILE_PATH = settings.products_file_path
BKASH_NUMBER = settings.bkash_number
ADVANCE_PERCENT = settings.advance_percent
MIN_ORDER_TOTAL = settings.min_order_total
OWNER_DM_ID = settings.owner_dm_id
OWNER_DM_MESSENGER_ID = settings.owner_dm_messenger_id
OWNER_DM_INSTAGRAM_ID = settings.owner_dm_instagram_id
ALLOW_INSECURE_WEBHOOK_SIGNATURES = settings.allow_insecure_webhook_signatures
BURST_COALESCE_WINDOW_MS = settings.burst_coalesce_window_ms
BURST_MIN_MESSAGES_TO_TRIGGER = settings.burst_min_messages_to_trigger
IDLE_TIMEOUT_AFTER_CART_SECONDS = settings.idle_timeout_after_cart_seconds
IDLE_TIMEOUT_AFTER_ADDRESS_SECONDS = settings.idle_timeout_after_address_seconds
SESSION_EXPIRY_DAYS = settings.session_expiry_days
BURST_MAX_SIZE_HARDCAP = settings.burst_max_size_hardcap
ENABLE_IDLE_REMINDERS = settings.enable_idle_reminders
COMPLIANCE_SAFE_MODE = settings.compliance_safe_mode
DISCLOSE_AUTOMATION_ON_FIRST_REPLY = settings.disclose_automation_on_first_reply
SUPPRESS_LINKS_ON_FIRST_TOUCH = settings.suppress_links_on_first_touch
MAX_AUTO_REPLIES_BEFORE_HANDOFF = settings.max_auto_replies_before_handoff

PRODUCT = {
    "name": "Oversized Hoodie",
    "price": 2500,
    "currency": "BDT",
    "delivery": "20-25 days",
}
PRODUCT_MAP: dict[str, list[dict[str, Any]]] = {}

PAYMENT_CONFIRMATION_TEXT = "To confirm: send 60% to bKash. Remaining 40% cash on delivery. Secure checkout."
DELIVERY_CHARGE_TEXT = "Dhaka: 85 tk | Outside: 150 tk | Delivery: 20-25 days"
DELIVERY_TIME_TEXT = "20-25 days (guaranteed)"
AUTOMATION_DISCLOSURE_TEXT = "Heads up: this is EllenAI, our automated shop assistant. If you want a person, just say 'human' or 'help'."

BARGAIN_WINDOW_SECONDS = 120
BARGAIN_CAP_AFTER_COUNT = 3

STYLE_PROMPT = """
You are a professional, confident sales assistant.

Tone:

* Direct and clear
* Bangla + English mix (Banglish)
* Friendly but focused on closing sales

Rules:

* Short, punchy replies (1-2 lines max)
* Stay helpful and calm
* Always include clear next step/CTA
* Never apologize for price - it's fair value
* If price negotiation: acknowledge but stay firm
* End with action-oriented language ("niben naki?", "confirm korbo?", "ready?")
"""

STYLE_EXAMPLES = """
Yes, this is available. 2500 tk. If you want, I can help you choose color and quantity.
Size: M available. Niben naki? I'll process your order right away.
Payment 60% bKash, 40% COD. If you're ready, I can guide you through the next step.
This design is available now. If you want it, I can confirm the order flow.
It's premium quality and the price is fixed. If you want, I can help with the order.
"""

INTENTS = {"price", "order", "add_item", "deny", "location", "payment", "question", "other", "unknown"}
COLOR_WORDS = {
    "black",
    "white",
    "red",
    "blue",
    "green",
    "pink",
    "grey",
    "gray",
    "brown",
    "beige",
}

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
app = FastAPI(title="EllenAI Sales Assistant")

# In-memory caches to reduce OpenAI call frequency.
intent_cache: dict[str, tuple[float, dict[str, Any]]] = {}
rewrite_cache: dict[str, tuple[float, str]] = {}
session_cache: dict[str, dict[str, Any]] = {}
user_locks: dict[str, asyncio.Lock] = {}
lock_registry_guard = asyncio.Lock()

user_rate_buckets: dict[str, deque[float]] = {}
webhook_rate_bucket: deque[float] = deque()
rate_limit_guard = asyncio.Lock()

# Message burst coalescing: collect rapid messages and process as one
burst_pending: dict[str, dict[str, Any]] = {}  # user_id -> {"events": [...], "first_arrival_time": float}
burst_timers: dict[str, asyncio.Task[Any]] = {}  # user_id -> coalesce timer task
burst_guard = asyncio.Lock()

GRAPH_SEND_RETRY_ATTEMPTS = 3
GRAPH_SEND_RETRY_BASE_SECONDS = 1.0
BURST_EARLY_FLUSH_SIZE = 5


def log_startup_configuration() -> None:
    required_env = {
        "OPENAI_API_KEY": OPENAI_API_KEY,
        "PAGE_ACCESS_TOKEN": PAGE_ACCESS_TOKEN,
        "PAGE_ID": PAGE_ID,
        "VERIFY_TOKEN": VERIFY_TOKEN,
    }
    missing = [key for key, value in required_env.items() if not str(value).strip()]
    if missing:
        logger.warning("Missing required environment values: %s", ", ".join(missing))
    else:
        logger.info("Required environment values present: %s", ", ".join(required_env.keys()))

    if APP_SECRET:
        logger.info("Webhook signature verification is enabled")
    elif ALLOW_INSECURE_WEBHOOK_SIGNATURES:
        logger.warning("Webhook signature verification is NOT enforced (ALLOW_INSECURE_WEBHOOK_SIGNATURES=1)")
    else:
        logger.error("APP_SECRET is empty and insecure mode is disabled; webhook requests will be rejected")

    logger.info(
        "Runtime config source env_loaded=%s rewrite=%s delay=%s state_db=%s products_file=%s",
        Path(".env").exists(),
        ENABLE_REPLY_REWRITE,
        MESSAGE_SEND_DELAY_SECONDS,
        STATE_DB_PATH,
        PRODUCTS_FILE_PATH,
    )

def init_db() -> None:
    state_store.init_db()
    logger.info("State DB initialized at %s", STATE_DB_PATH)


task_supervisor = TaskSupervisor()
state_store = StateStore(STATE_DB_PATH)


@app.on_event("startup")
async def startup_event() -> None:
    log_startup_configuration()
    await asyncio.to_thread(init_db)
    await asyncio.to_thread(load_post_product_map)
    task_supervisor.spawn(recover_pending_events())
    task_supervisor.spawn(cleanup_dead_sessions())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    if task_supervisor.active_count:
        logger.info("Shutdown: waiting for %s active task(s) to complete", task_supervisor.active_count)
        finished = await task_supervisor.shutdown_wait()
        logger.info("Shutdown: all tasks finished count=%s", finished)


def _new_session() -> dict[str, Any]:
    now = time.time()
    return {
        "_version": 0,
        "state": 0,
        "location": None,
        "pending_product_options": [],
        "currency": PRODUCT["currency"],
        "delivery": PRODUCT["delivery"],
        "upsell_used": False,
        "bargain_timestamps": [],
        "payment_proof_received": False,
        "owner_pack_last_signature": None,
        "unknown_count": 0,
        "created_at": now,
        "last_activity_at": now,
        "state_2_reached_at": None,
        "state_3_reached_at": None,
        "last_idle_reminder_at": None,
        "automation_disclosure_sent": False,
        "auto_reply_count": 0,
        "human_handoff_requested": False,
        "cart": {
            "items": [],
            "total_price": 0,
        },
    }


def load_post_product_map() -> None:
    global PRODUCT_MAP

    loaded = load_products(PRODUCTS_FILE_PATH)
    if not loaded and not PRODUCTS_FILE_PATH.exists():
        logger.warning("products file missing at %s; using default product only", PRODUCTS_FILE_PATH)

    PRODUCT_MAP = loaded
    variant_count = sum(len(v) for v in PRODUCT_MAP.values())
    logger.info("Loaded %s product links (%s variants) from %s", len(PRODUCT_MAP), variant_count, PRODUCTS_FILE_PATH)


def _extract_shortcode_from_url(url: str) -> str | None:
    text = normalize_product_url(url)
    if not text:
        return None

    parts = [p for p in text.split("/") if p]
    if not parts:
        return None

    for idx, part in enumerate(parts):
        marker = part.lower()
        if marker in {"p", "reel", "tv"} and idx + 1 < len(parts):
            candidate = parts[idx + 1].strip().lower()
            if candidate:
                return candidate

    fallback = parts[-1].strip().lower()
    return fallback or None


def _resolve_product_candidates_from_attachments(attachment_urls: list[str]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    def _append_candidates(key: str, variants: list[dict[str, Any]]) -> None:
        for variant in variants:
            selected = dict(variant)
            selected["product_id"] = key
            candidates.append(selected)

    for url in attachment_urls:
        normalized = normalize_product_url(url)
        if normalized:
            products = PRODUCT_MAP.get(normalized)
            if products:
                _append_candidates(normalized, products)
                return candidates

    # Backward compatibility for shortcode-keyed JSON entries.
    for url in attachment_urls:
        code = _extract_shortcode_from_url(url)
        if not code:
            continue
        products = PRODUCT_MAP.get(code)
        if products:
            _append_candidates(code, products)
            return candidates
    return []


def _format_product_options_message(options: list[dict[str, Any]]) -> str:
    lines = [
        "🛍️ This post has multiple options - which one do you want?\n"
        "You can:",
        "  📌 Reply with the number (1, 2, 3, etc.)",
        "  🔍 Tell me which slide (slide 1, slide 2...)",
        "  ⭕ Circle/highlight the product & send a screenshot",
        "\nHere's what we have:"
    ]
    for idx, option in enumerate(options, start=1):
        name = str(option.get("name") or "Item")
        price = int(option.get("price") or 0)
        currency = str(option.get("currency") or "BDT")
        lines.append(f"  {idx}) {name} → {price} {currency}")
    return "\n".join(lines)


def _pick_product_option_from_text(text: str, options: list[dict[str, Any]]) -> dict[str, Any] | None:
    cleaned = str(text or "").strip().lower()
    if not cleaned or not options:
        return None

    index_match = re.search(r"\b(\d{1,2})\b", cleaned)
    if index_match:
        chosen_idx = int(index_match.group(1))
        if 1 <= chosen_idx <= len(options):
            return dict(options[chosen_idx - 1])

    for option in options:
        name = str(option.get("name") or "").strip().lower()
        if name and name in cleaned:
            return dict(option)

        price_text = str(option.get("price") or "").strip()
        if price_text and re.search(rf"\b{re.escape(price_text)}\b", cleaned):
            return dict(option)
    return None


def _resolve_product_from_attachments(attachment_urls: list[str]) -> dict[str, Any] | None:
    candidates = _resolve_product_candidates_from_attachments(attachment_urls)
    if len(candidates) == 1:
        return candidates[0]
    return None


def add_product_from_url(session: dict[str, Any], url: str, quantity: int, color: str | None = None) -> bool:
    selected_product = _resolve_product_from_attachments([url])
    if not selected_product:
        return False
    _add_or_update_item(session, max(1, int(quantity)), color, product=selected_product)
    return True


def _session_currency(session: dict[str, Any]) -> str:
    return str(session.get("currency") or PRODUCT["currency"])


def _session_delivery(session: dict[str, Any]) -> str:
    del session
    return DELIVERY_TIME_TEXT


def _platform_from_key(link_key: str) -> str:
    key = str(link_key or "").lower()
    if key.startswith("instagram.com/"):
        return "instagram"
    if key.startswith("facebook.com/"):
        return "messenger"
    return "unknown"


def _preferred_platform(source: str | None) -> str:
    value = str(source or "").strip().lower()
    if value in {"instagram", "messenger"}:
        return value
    return "unknown"


def _canonical_full_link(link_key: str) -> str:
    return f"https://www.{link_key}"


def _is_inside_dhaka(location: str | None) -> bool:
    text = str(location or "").lower()
    if not text:
        return False
    inside_markers = [
        "dhaka",
        "mirpur",
        "uttara",
        "banani",
        "dhanmondi",
        "mohammadpur",
        "bashundhara",
        "badda",
        "farmgate",
        "motijheel",
        "gulshan",
    ]
    return any(marker in text for marker in inside_markers)


def _delivery_charge_for_location(location: str | None) -> int:
    return 85 if _is_inside_dhaka(location) else 150


def _payment_breakdown(session: dict[str, Any], location: str | None = None) -> dict[str, int]:
    subtotal = int(session.get("cart", {}).get("total_price", 0) or 0)
    delivery = _delivery_charge_for_location(location)
    grand_total = subtotal + delivery
    advance = int(round(grand_total * ADVANCE_PERCENT))
    remaining = max(0, grand_total - advance)
    return {
        "subtotal": subtotal,
        "delivery": delivery,
        "grand_total": grand_total,
        "advance": advance,
        "remaining": remaining,
    }


def _find_alternate_link_for_product(
    product: dict[str, Any],
    target_platform: str,
) -> str | None:
    name = str(product.get("name") or "").strip().lower()
    price = int(product.get("price") or 0)
    for key, variants in PRODUCT_MAP.items():
        if _platform_from_key(key) != target_platform:
            continue
        for variant in variants:
            if str(variant.get("name") or "").strip().lower() == name and int(variant.get("price") or 0) == price:
                return key
    return None


def _normalize_catalog_query(text: str) -> str:
    normalized = str(text or "").lower()
    replacements = {
        "nosepin": "nose ring",
        "nose pin": "nose ring",
        "lip piercing": "lip ring",
        "lip-piercing": "lip ring",
        "ear ring": "earring",
        "ear rings": "earrings",
        "non piercing earring": "without piercing earrings",
        "collection gulo": "collection",
    }
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    return normalized


def _search_catalog_products(query: str, source: str, limit: int = 5) -> list[tuple[str, dict[str, Any]]]:
    text = _normalize_catalog_query(query)
    keywords = [k for k in re.findall(r"[a-z0-9]+", text) if len(k) >= 3]
    if not keywords:
        return []

    preferred = _preferred_platform(source)
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for key, variants in PRODUCT_MAP.items():
        platform = _platform_from_key(key)
        platform_bias = 2 if preferred != "unknown" and platform == preferred else 0
        for variant in variants:
            name = str(variant.get("name") or "")
            hay = f"{name} {key}".lower()
            score = platform_bias + sum(1 for kw in keywords if kw in hay)
            if score > 0:
                scored.append((score, key, variant))

    scored.sort(key=lambda row: (-row[0], int(row[2].get("price") or 0), str(row[2].get("name") or "")))
    output: list[tuple[str, dict[str, Any]]] = []
    seen: set[tuple[str, int]] = set()
    for _, key, variant in scored:
        sig = (str(variant.get("name") or "").strip().lower(), int(variant.get("price") or 0))
        if sig in seen:
            continue
        seen.add(sig)
        final_key = key
        if preferred in {"messenger", "instagram"} and _platform_from_key(key) != preferred:
            alt = _find_alternate_link_for_product(variant, preferred)
            if alt:
                final_key = alt
        output.append((final_key, variant))
        if len(output) >= max(1, limit):
            break
    return output


def _is_catalog_query(text: str) -> bool:
    q = _normalize_catalog_query(text)
    markers = [
        "collection",
        "dekhan",
        "show",
        "ache",
        "do you have",
        "price koto",
        "price",
        "dam",
        "koto",
        "earring",
        "earrings",
        "without piercing earrings",
        "non piercing earrings",
        "nose ring",
        "lip ring",
    ]
    return any(marker in q for marker in markers)


def _format_catalog_matches_reply(query: str, source: str, matches: list[tuple[str, dict[str, Any]]]) -> str:
    if not matches:
        return "That exact item isn't in stock right now apu 😢 But we have similar styles! What else can I show you?"

    lines = ["✨ Great news! We have these available:"]
    for idx, (key, variant) in enumerate(matches[:5], start=1):
        name = str(variant.get("name") or "Item")
        price = int(variant.get("price") or 0)
        currency = str(variant.get("currency") or "tk")
        lines.append(f"{idx}) {name}")
        lines.append(f"   💰 {price} {currency}")
    lines.append("\n👉 Reply with the number you want. If you need the exact post link, say 'link'.")
    return "\n".join(lines)


def _min_order_message(session: dict[str, Any], source: str) -> str:
    subtotal = int(session.get("cart", {}).get("total_price", 0) or 0)
    need_more = max(0, MIN_ORDER_TOTAL - subtotal)
    suggestions = _search_catalog_products("accessories budget", source, limit=3)
    lines = [
        f"📦 Minimum order: {MIN_ORDER_TOTAL} tk | Your current cart: {subtotal} tk",
        f"You need just {need_more} tk more to place your order! 🎯",
        "💡 Perfect add-ons:",
    ]
    if suggestions:
        for idx, (key, variant) in enumerate(suggestions[:3], start=1):
            lines.append(
                f"{idx}) {variant.get('name', 'Item')} → {int(variant.get('price') or 0)} {variant.get('currency') or 'tk'}"
            )
        lines.append("\n👉 Add one & complete your order. Reply with the item number if you want it.")
    return "\n".join(lines)


def _payment_and_delivery_policy_lines() -> list[str]:
    return [
        "💳 " + PAYMENT_CONFIRMATION_TEXT,
        "📦 " + DELIVERY_CHARGE_TEXT,
        f"🏦 bKash: {BKASH_NUMBER}",
    ]


def _normalize_intent(data: dict[str, Any]) -> dict[str, Any]:
    intent = str(data.get("intent", "unknown")).strip().lower()
    if intent not in INTENTS:
        intent = "other"

    quantity_raw = data.get("quantity", 1)
    try:
        quantity = int(quantity_raw)
    except (TypeError, ValueError):
        quantity = 1
    quantity = max(1, quantity)

    color_raw = data.get("color")
    color = str(color_raw).strip().lower() if color_raw else None
    if color in {"null", "none", ""}:
        color = None

    location_raw = data.get("location")
    location = str(location_raw).strip() if location_raw else None

    payment_detected = bool(data.get("payment_detected", False))
    is_question = bool(data.get("is_question", False))

    return {
        "intent": intent,
        "quantity": quantity,
        "color": color,
        "location": location,
        "payment_detected": payment_detected,
        "is_question": is_question,
    }


def _fallback_detect(message: str) -> dict[str, Any]:
    text = message.lower()

    qty_match = re.search(r"(\d+)\s*(x|pcs|pieces|piece)?", text)
    quantity = int(qty_match.group(1)) if qty_match else 1

    color = None
    for c in COLOR_WORDS:
        if re.search(rf"\b{re.escape(c)}\b", text):
            color = c
            break

    question_markers = ["?", "quality", "cotton", "shrink", "kemon", "fabric"]
    is_question = any(m in text for m in question_markers)

    location = None
    if any(k in text for k in ["dhaka", "chittagong", "sylhet", "address", "location"]):
        location = message.strip()

    payment_detected = any(k in text for k in ["paid", "payment", "trx", "bkash", "nagad", "rocket", "screenshot"])

    if any(k in text for k in ["chacchina", "nibo na", "chaina", "cancel", "clear cart", "start over", "reset", "don't want", "do not want", "interested na", "lagbe na"]):
        intent = "deny"
    elif "shared_post" in text:
        intent = "add_item"
    elif any(k in text for k in ["order", "confirm", "nibo", "niben", "this one", "eta lagbe"]):
        intent = "order"
    elif location and any(k in text for k in ["address", "location", "road", "house", "flat", "dhaka", "chittagong", "sylhet"]):
        intent = "location"
    elif payment_detected:
        intent = "payment"
    elif any(k in text for k in ["price", "dam", "koto", "cost"]):
        intent = "price"
    elif any(k in text for k in ["piece", "pcs", "x", "black", "white", "red", "blue"]):
        intent = "add_item"
    elif is_question:
        intent = "question"
    else:
        intent = "unknown"

    return {
        "intent": intent,
        "quantity": max(1, quantity),
        "color": color,
        "location": location,
        "payment_detected": payment_detected,
        "is_question": is_question,
    }


def _is_price_argument(message: str) -> bool:
    text = message.lower()
    markers = [
        "kom", "less", "discount", "best price", "final price", "reduce", "dam kom", "too much", "expensive",
        "aro kom", "price ta koman", "can you lower", "nego", "negotiable",
    ]
    return any(m in text for m in markers)


def _prune_cache(cache: dict[str, tuple[float, Any]], ttl_seconds: int) -> None:
    now = time.time()
    stale = [k for k, (ts, _) in cache.items() if now - ts > ttl_seconds]
    for k in stale:
        cache.pop(k, None)


def _cache_put(cache: dict[str, tuple[float, Any]], key: str, value: Any, ttl_seconds: int, max_size: int) -> None:
    cache[key] = (time.time(), value)
    _prune_cache(cache, ttl_seconds)
    while len(cache) > max(1, max_size):
        oldest_key = next(iter(cache))
        cache.pop(oldest_key, None)


def _set_session_cache(user_id: str, session: dict[str, Any]) -> None:
    session_cache[user_id] = session
    while len(session_cache) > max(1, SESSION_CACHE_MAX_SIZE):
        oldest_key = next(iter(session_cache))
        if oldest_key == user_id and len(session_cache) == 1:
            break
        session_cache.pop(oldest_key, None)


def _with_openai_retry(callable_op: Any, operation_name: str) -> Any:
    delay = max(0.0, OPENAI_RETRY_MIN_SECONDS)
    attempt = 1
    while True:
        try:
            return callable_op()
        except APIError as exc:
            if attempt >= max(1, OPENAI_RETRY_ATTEMPTS):
                raise
            sleep_for = min(OPENAI_RETRY_MAX_SECONDS, delay if delay > 0 else OPENAI_RETRY_MIN_SECONDS)
            logger.warning(
                "%s failed on attempt %s/%s: %s. Retrying in %.2fs",
                operation_name,
                attempt,
                OPENAI_RETRY_ATTEMPTS,
                exc,
                sleep_for,
            )
            time.sleep(sleep_for)
            delay = max(OPENAI_RETRY_MIN_SECONDS, delay * 2 if delay > 0 else OPENAI_RETRY_MIN_SECONDS)
            attempt += 1


async def _get_user_lock(user_id: str) -> asyncio.Lock:
    async with lock_registry_guard:
        lock = user_locks.get(user_id)
        if lock is None:
            lock = asyncio.Lock()
            user_locks[user_id] = lock
        return lock


def _cleanup_rate_bucket(bucket: deque[float], now: float, window_seconds: int) -> None:
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()


async def _consume_rate_limit(user_id: str) -> bool:
    now = time.time()
    async with rate_limit_guard:
        bucket = user_rate_buckets.setdefault(user_id, deque())
        _cleanup_rate_bucket(bucket, now, max(1, USER_RATE_LIMIT_WINDOW_SECONDS))
        if len(bucket) >= max(1, USER_RATE_LIMIT_COUNT):
            return False
        bucket.append(now)
        if len(user_rate_buckets) > 50000:
            stale_keys = [k for k, v in user_rate_buckets.items() if not v]
            for stale in stale_keys:
                user_rate_buckets.pop(stale, None)
        return True


async def _allow_webhook_batch(event_count: int) -> bool:
    now = time.time()
    async with rate_limit_guard:
        _cleanup_rate_bucket(webhook_rate_bucket, now, max(1, WEBHOOK_RATE_LIMIT_WINDOW_SECONDS))
        if len(webhook_rate_bucket) + max(0, event_count) > max(1, WEBHOOK_RATE_LIMIT_COUNT):
            return False
        for _ in range(max(0, event_count)):
            webhook_rate_bucket.append(now)
        return True


def _fallback_rewrite_reply(original_reply: str) -> str:
    """Graceful fallback when OpenAI API is unavailable. Returns original with safety check."""
    if len(original_reply) > 500:
        return original_reply[:497] + "..."
    return original_reply


def _safe_send_intention_check() -> dict[str, Any]:
    """Check if send is safe and return fallback data if APIs are unreachable."""
    try:
        return {"ready": True, "apis_ok": True}
    except Exception as e:
        logger.warning("Service healthcheck failed: %s", e)
        return {"ready": False, "apis_ok": False, "error": str(e)}


def _merge_intents_from_burst(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge multiple events into a single combined intent, preserving most relevant signals."""
    merged_intent = "unknown"
    quantities: list[int] = []
    colors_found: list[str] = []
    locations_found: list[str] = []
    payment_detected = False
    any_order = False
    any_deny = False
    any_question = False
    combined_text_parts: list[str] = []
    attachment_urls_all: set[str] = set()
    attachment_types_all: set[str] = set()

    for event in events:
        message_text = str(event.get("message", "")).strip()
        intent_data = _fallback_detect(message_text)
        combined_text_parts.append(str(event.get("message", "")).strip())
        
        current_intent = str(intent_data.get("intent", "unknown"))
        if current_intent == "order":
            any_order = True
        elif current_intent == "deny":
            any_deny = True
        elif current_intent == "question":
            any_question = True
        elif current_intent not in {"unknown", "question"}:
            merged_intent = current_intent
        
        if qty := int(intent_data.get("quantity", 0)):
            quantities.append(qty)
        if color := str(intent_data.get("color", "")).strip():
            colors_found.append(color)
        if location := str(intent_data.get("location", "")).strip():
            locations_found.append(location)
        
        payment_detected = payment_detected or bool(intent_data.get("payment_detected", False))
        
        attachment_urls = event.get("attachment_urls", [])
        if isinstance(attachment_urls, list):
            attachment_urls_all.update(u for u in attachment_urls if isinstance(u, str))
        attachment_types = event.get("attachment_types", [])
        if isinstance(attachment_types, list):
            attachment_types_all.update(t for t in attachment_types if isinstance(t, str))

    # Determine final intent based on priority
    if payment_detected:
        merged_intent = "payment"
    elif any_order:
        merged_intent = "order"
    elif any_deny:
        merged_intent = "deny"
    elif merged_intent == "unknown":
        if any_question:
            merged_intent = "question"

    combined_text = " | ".join(p for p in combined_text_parts if p)
    
    return {
        "intent": merged_intent,
        "quantity": max(quantities) if quantities else 0,
        "color": colors_found[-1] if colors_found else None,
        "location": locations_found[-1] if locations_found else None,
        "payment_detected": payment_detected,
        "combined_message": combined_text,
        "burst_size": len(events),
        "attachment_urls": sorted(attachment_urls_all),
        "attachment_types": sorted({str(t).lower() for t in attachment_types_all if str(t).strip()}),
    }


async def _process_burst(user_id: str, events: list[dict[str, Any]]) -> None:
    """Process a burst of events as one cohesive interaction."""
    if not events:
        return

    logger.info("BURST processing user=%s events=%d", user_id, len(events))
    
    # Append all messages to history
    for event in events:
        await append_history(
            user_id,
            event.get("message", ""),
            int(event.get("attachments_count", 0)),
            event.get("attachment_types", []),
            event.get("attachment_urls", []),
        )
    
    # Merge intents from burst
    merged_intent_data = _merge_intents_from_burst(events)
    
    # Use the first message's source and most complete burst for context
    first_event = events[0]
    source = str(first_event.get("source") or "unknown")
    
    # For burst: use combined message and all attachments from the burst.
    combined_message = str(merged_intent_data.get("combined_message", "")).strip()
    attachment_urls = [str(u).strip() for u in merged_intent_data.get("attachment_urls", []) if str(u).strip()]
    attachment_types = [str(t).lower().strip() for t in merged_intent_data.get("attachment_types", []) if str(t).strip()]
    
    final_reply, should_send = await process_message(
        user_id,
        combined_message if combined_message else " ".join(e.get("message", "") for e in events),
        source=source,
        attachments_count=len(attachment_urls),
        attachment_types=attachment_types,
        attachment_urls=attachment_urls,
    )
    if should_send:
        send_result = await send_message(user_id, final_reply)
        if not send_result.get("ok"):
            raise RuntimeError(f"send_message failed: {send_result}")


def _event_retry_status(event: dict[str, Any]) -> str:
    next_attempt = int(event.get("_db_attempts", 0)) + 1
    return "retry" if next_attempt < 3 else "failed"


async def _process_burst_bundle(user_id: str, burst_info: dict[str, Any]) -> None:
    events = list(burst_info.get("events", []))
    event_ids = list(burst_info.get("event_ids", []))
    if not events or not event_ids or len(events) != len(event_ids):
        logger.warning("BURST bundle invalid user=%s events=%s ids=%s", user_id, len(events), len(event_ids))
        return

    for event_id in event_ids:
        await asyncio.to_thread(db_mark_incoming_event, event_id, "processing", None, True)

    try:
        await _process_burst(user_id, events)
        for event_id in event_ids:
            await asyncio.to_thread(db_mark_incoming_event, event_id, "done", None, False)
    except Exception as exc:
        logger.exception("BURST processing failed user=%s ids=%s err=%s", user_id, event_ids, exc)
        for event_id, event in zip(event_ids, events):
            await asyncio.to_thread(db_mark_incoming_event, event_id, _event_retry_status(event), str(exc), False)
        raise


async def _coalesce_burst_with_timeout(user_id: str) -> None:
    """Wait for burst coalesce window, then process all pending events."""
    try:
        await asyncio.sleep(BURST_COALESCE_WINDOW_MS / 1000.0)
        
        async with burst_guard:
            burst_info = burst_pending.pop(user_id, None)
            burst_timers.pop(user_id, None)
        
        if burst_info:
            await _process_burst_bundle(user_id, burst_info)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.exception("Error in burst coalescing for user=%s: %s", user_id, e)


def _detect_intent_sync(message: str) -> dict[str, Any]:
    if not message or not message.strip():
        return _normalize_intent(
            {
                "intent": "unknown",
                "quantity": 1,
                "color": None,
                "location": None,
                "payment_detected": False,
                "is_question": False,
            }
        )

    cache_key = message.strip().lower()
    cached = intent_cache.get(cache_key)
    if cached and (time.time() - cached[0] <= INTENT_CACHE_TTL_SECONDS):
        return dict(cached[1])

    prompt = f"""
Extract structured shopping intent from this message.

Return JSON only with keys:
intent, quantity, color, location, payment_detected, is_question

Allowed intent values:
price | order | add_item | deny | location | payment | question | other | unknown

Use "deny" when the customer is explicitly rejecting, cancelling, or saying they do NOT want a product (e.g. "chacchina", "nibo na", "cancel", "na na", "I don't want", "clear cart", "start over").

Message:
{message}
"""

    if client is None:
        result = _normalize_intent(_fallback_detect(message))
        _cache_put(intent_cache, cache_key, dict(result), INTENT_CACHE_TTL_SECONDS, INTENT_CACHE_MAX_SIZE)
        return result

    try:
        response = _with_openai_retry(
            lambda: client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0,
            ),
            "detect_intent",
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        result = _normalize_intent(parsed if isinstance(parsed, dict) else {})
    except (APIError, json.JSONDecodeError, ValueError) as exc:
        logger.exception("Intent detection failed: %s", exc)
        result = _normalize_intent(_fallback_detect(message))

    _cache_put(intent_cache, cache_key, dict(result), INTENT_CACHE_TTL_SECONDS, INTENT_CACHE_MAX_SIZE)
    return result


async def detect_intent(message: str) -> dict[str, Any]:
    return await asyncio.to_thread(_detect_intent_sync, message)


def _rewrite_reply_sync(text: str, allow_upsell: bool = False, tone: str = "default") -> str:
    del tone
    if not ENABLE_REPLY_REWRITE:
        return text

    # Avoid extra model calls for deterministic system lines.
    if text.startswith("Order Summary:"):
        return text

    cache_key = f"{allow_upsell}|{text}"
    cached = rewrite_cache.get(cache_key)
    if cached and (time.time() - cached[0] <= REWRITE_CACHE_TTL_SECONDS):
        return cached[1]

    if client is None:
        return text

    upsell_rule = "You may gently suggest buying more." if allow_upsell else "Do not upsell in this reply."
    rewrite_prompt = f"""
{STYLE_PROMPT}

Examples:
{STYLE_EXAMPLES}

Rewrite this reply naturally.
{upsell_rule}

Reply text:
{text}
"""

    try:
        response = _with_openai_retry(
            lambda: client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Keep numeric totals exactly unchanged."},
                    {"role": "user", "content": rewrite_prompt},
                ],
                temperature=0.6,
            ),
            "rewrite_reply",
        )
        rewritten = (response.choices[0].message.content or "").strip()
        final_text = rewritten if rewritten else text
    except APIError as exc:
        logger.exception("Reply rewrite failed: %s", exc)
        final_text = text

    _cache_put(rewrite_cache, cache_key, final_text, REWRITE_CACHE_TTL_SECONDS, REWRITE_CACHE_MAX_SIZE)
    return final_text


async def rewrite_reply(text: str, allow_upsell: bool = False, tone: str = "default") -> str:
    return await asyncio.to_thread(_rewrite_reply_sync, text, allow_upsell, tone)


def _analyze_payment_image_sync(image_url: str, message: str) -> bool:
    """Analyze if image is a valid bKash/payment screenshot.
    Must show transaction ID, amount, reference number, or similar payment indicators."""
    if client is None or not image_url:
        return False

    prompt = (
        "You are verifying whether an image is a valid bKash/Nagad/Rocket payment screenshot. "
        "Look for indicators like: transaction ID (TRX ID), reference number, amount sent, merchant name, timestamp, confirmation message. "
        "Respond only JSON: {\"is_payment_proof\": true|false, \"reason\": \"short explanation\"}. "
        "Mark false for: screenshots without transaction details, random phone screens, product photos, or unclear payments. "
        "Mark true only if it clearly shows a completed payment transaction. "
        f"User context: {message}"
    )

    try:
        response = _with_openai_retry(
            lambda: client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0,
            ),
            "analyze_payment_image",
        )
        parsed = json.loads(response.choices[0].message.content or "{}")
        is_valid = bool(parsed.get("is_payment_proof", False))
        logger.info("Payment proof analysis: is_valid=%s reason=%s", is_valid, parsed.get("reason", "N/A"))
        return is_valid
    except (APIError, json.JSONDecodeError, ValueError) as exc:
        logger.exception("Payment image analysis failed: %s", exc)
        return False


async def analyze_payment_images(attachment_types: list[str], attachment_urls: list[str], message: str, state: int) -> bool:
    if state != 3:
        return False
    normalized_types = {str(t).lower().strip() for t in attachment_types if str(t).strip()}
    if "image" not in normalized_types:
        return False
    for url in attachment_urls:
        if await asyncio.to_thread(_analyze_payment_image_sync, url, message):
            return True
    return False


def _identify_product_in_image_sync(image_url: str, message: str) -> dict[str, Any]:
    """Use GPT-4o vision to identify what product type is shown in an image.
    Returns {"product_type": str | None, "is_product_inquiry": bool, "style_hints": list[str]}."""
    if client is None or not image_url:
        return {"product_type": None, "is_product_inquiry": False, "style_hints": []}

    product_names: list[str] = []
    for variants in PRODUCT_MAP.values():
        for product in variants:
            name = str(product.get("name") or "").strip()
            if name:
                product_names.append(name)
    catalog_hint = ", ".join(product_names) if product_names else "various fashion items"

    prompt = (
        "You are a product recognition assistant for an online fashion store. "
        "Look at the image and identify:\n"
        "1. What type of product is shown (e.g. 'earrings', 'glasses', 'hoodie', 'dress', 'bag', 'bracelet', etc.)\n"
        "2. Style descriptors (e.g. 'vintage', 'minimalist', 'bohemian', 'formal', 'casual', 'colorful', 'monochrome')\n"
        "3. Whether the user is asking if this product is available\n\n"
        f"Our store catalog includes: {catalog_hint}. "
        f"User text: {message or '(no text)'}. "
        'Respond ONLY with JSON:\n'
        '{"product_type": "primary product category in English", '
        '"style_hints": ["style1", "style2", ...], '
        '"is_product_inquiry": true|false}\n'
        "Set is_product_inquiry to true if the user is asking whether this product is available. "
        "Set product_type to null if you cannot identify a product. "
        "Include 2-3 style descriptors to help find similar items."
    )

    try:
        response = _with_openai_retry(
            lambda: client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0,
            ),
            "identify_product_image",
        )
        parsed = json.loads(response.choices[0].message.content or "{}")
        product_type = str(parsed.get("product_type") or "").strip().lower() or None
        style_hints = [str(s).strip().lower() for s in (parsed.get("style_hints") or []) if str(s).strip()]
        return {
            "product_type": product_type,
            "is_product_inquiry": bool(parsed.get("is_product_inquiry", True)),
            "style_hints": style_hints,
        }
    except (APIError, json.JSONDecodeError, ValueError) as exc:
        logger.exception("Product image identification failed: %s", exc)
        return {"product_type": None, "is_product_inquiry": False, "style_hints": []}


def _search_product_by_type(product_type: str) -> list[tuple[str, dict[str, Any]]]:
    """Search PRODUCT_MAP by keyword match on product name.
    Returns list of (normalized_url_key, product_dict) tuples."""
    if not product_type or not PRODUCT_MAP:
        return []
    keywords = [k.strip() for k in product_type.lower().split() if k.strip()]
    matches = []
    for key, variants in PRODUCT_MAP.items():
        for prod in variants:
            name_lower = str(prod.get("name", "")).lower()
            if any(kw in name_lower for kw in keywords):
                matches.append((key, prod))
    return matches


def _recalc_total(session: dict[str, Any]) -> None:
    total = 0
    for item in session["cart"]["items"]:
        unit_price = int(item.get("price", PRODUCT["price"]))
        total += int(item["quantity"]) * unit_price
    session["cart"]["total_price"] = total


def _add_or_update_item(
    session: dict[str, Any],
    quantity: int,
    color: str | None,
    product: dict[str, Any] | None = None,
) -> None:
    selected = product or {
        "product_id": None,
        "name": PRODUCT["name"],
        "price": PRODUCT["price"],
        "currency": PRODUCT["currency"],
        "delivery": PRODUCT["delivery"],
    }
    product_name = str(selected.get("name") or PRODUCT["name"])
    try:
        product_price = int(selected.get("price", PRODUCT["price"]))
    except (TypeError, ValueError):
        product_price = int(PRODUCT["price"])
    product_currency = str(selected.get("currency") or PRODUCT["currency"])
    product_delivery = str(selected.get("delivery") or PRODUCT["delivery"])
    product_id = str(selected.get("product_id") or "").strip().lower() or None

    session["currency"] = product_currency
    session["delivery"] = product_delivery

    target_color = color.lower() if color else None
    items = session["cart"]["items"]

    for item in items:
        if (
            item["name"] == product_name
            and int(item.get("price", product_price)) == product_price
            and item.get("color") == target_color
            and (item.get("product_id") or None) == product_id
        ):
            item["quantity"] += quantity
            _recalc_total(session)
            return

    items.append(
        {
            "product_id": product_id,
            "name": product_name,
            "price": product_price,
            "quantity": quantity,
            "color": target_color,
        }
    )
    _recalc_total(session)


def _get_available_product_types() -> list[str]:
    """Extract unique product types/categories from catalog."""
    product_types: set[str] = set()
    for variants in PRODUCT_MAP.values():
        for product in variants:
            name = str(product.get("name", "")).lower()
            # Extract main category keywords
            keywords = {
                "earring": "Earrings",
                "ring": "Rings",
                "glasses": "Glasses",
                "lens": "Lenses",
                "bag": "Bags",
                "boot": "Boots",
                "eyelash": "Eyelashes",
                "lash": "Lashes",
                "flower": "Flowers",
                "jersey": "Jersey",
            }
            for keyword, display_name in keywords.items():
                if keyword in name:
                    product_types.add(display_name)
    return sorted(product_types)


def _safe_default_reply() -> str:
    """Guide confused customer with multiple options to clarify intent."""
    product_types = _get_available_product_types()
    types_list = ", ".join(product_types[:5]) if product_types else "earrings, glasses, bags, etc"
    
    return (
        f"Hmm, I'm not quite sure what you're looking for! 🤔\n\n"
        f"Try one of these:\n"
        f"📸 Share a picture of what you want → I'll find it!\n"
        f"🔗 Share a link from our post if you already have one\n"
        f"💬 Tell me what: {types_list}, and more!\n\n"
        f"What works best apu? 😊"
    )


def _super_confused_reply() -> str:
    """After multiple confusions, offer direct human help."""
    return (
        "I'm having trouble understanding, apu 😅\n\n"
        "💡 Best way to help you:\n"
        "→ Share a picture of what you want OR\n"
        "→ Ask for a specific product (earrings, bags, glasses, etc.)\n\n"
        "Or I'll connect you with Ellen directly! Just say 'help' & we'll sort it out! 🙌"
    )


def _owner_targets() -> set[str]:
    return {
        str(owner_id).strip()
        for owner_id in {OWNER_DM_ID, OWNER_DM_MESSENGER_ID, OWNER_DM_INSTAGRAM_ID}
        if str(owner_id).strip()
    }


def _is_owner_target(user_id: str) -> bool:
    return str(user_id).strip() in _owner_targets()


def _should_disclose_automation(session: dict[str, Any]) -> bool:
    return COMPLIANCE_SAFE_MODE and DISCLOSE_AUTOMATION_ON_FIRST_REPLY and not bool(session.get("automation_disclosure_sent"))


def _should_suppress_links(session: dict[str, Any]) -> bool:
    if not COMPLIANCE_SAFE_MODE or not SUPPRESS_LINKS_ON_FIRST_TOUCH:
        return False
    if int(session.get("state", 0) or 0) >= 1:
        return False
    return int(session.get("auto_reply_count", 0) or 0) < 2


def _sanitize_links_for_compliance(text: str, session: dict[str, Any]) -> str:
    if not _should_suppress_links(session):
        return text
    sanitized = re.sub(r"https?://\S+", "[link available on request]", text)
    sanitized = re.sub(r"\|\s*Link:\s*\[link available on request\]", "", sanitized)
    if sanitized != text and "link available on request" not in sanitized.lower():
        sanitized += "\n\nIf you want the exact product post, reply 'link'."
    elif sanitized != text:
        sanitized += "\n\nIf you want the exact product post, reply 'link'."
    return sanitized


def _apply_customer_compliance(text: str, session: dict[str, Any]) -> str:
    final_text = _sanitize_links_for_compliance(text, session)
    if _should_disclose_automation(session):
        session["automation_disclosure_sent"] = True
        final_text = f"{AUTOMATION_DISCLOSURE_TEXT}\n\n{final_text}"
    return final_text


def _create_urgency_cta(product_name: str = None) -> str:
    """Generate urgency-focused CTA for closing sales."""
    messages = [
        "If you want this one, I can help you confirm it now.",
        "If you're ready, I can move this order to the next step.",
        "If this is your choice, I can help with quantity and address next.",
    ]
    return messages[len(product_name or "") % len(messages)] if product_name else messages[0]


def _create_closing_cta(current_state: int, cart_total: int = 0) -> str:
    """Generate closing-focused call-to-action based on conversation state."""
    if current_state == 0:
        return "Ready to order? Just tell me quantity & color! ✓"
    elif current_state == 1:
        return "Confirm this order now apu? Or add more items?"
    elif current_state == 2:
        return "Just need your address - then we finalize! ✓"
    elif current_state == 3:
        return "Payment screenshot will complete your order. Send now? 💳"
    elif current_state == 4:
        return "Your order is locked in! Tracking details coming soon. 📦"
    return "What's next apu? I'm ready to help! 😊"


def _get_add_on_suggestion(current_total: int, target_min: int) -> str | None:
    """Suggest add-ons when approaching minimum order threshold."""
    if current_total <= 0 or current_total > target_min:
        return None
    
    gap = target_min - current_total
    if gap > 0:
        suggestions = _search_catalog_products("accessories new trending", "messenger", limit=2)
        if suggestions:
            for _key, prod in suggestions:
                price = int(prod.get("price") or 0)
                if 0 < price <= gap + 500:  # Slightly above gap to give options
                    name = str(prod.get("name", "Item"))
                    return f"💡 Add '{name}' ({price} tk) & confirm? Perfect combo!"
    return None


def db_save_session(user_id: str, session: dict[str, Any]) -> bool:
    return state_store.save_session(user_id, session)


def db_get_session(user_id: str) -> dict[str, Any] | None:
    try:
        return state_store.get_session(user_id)
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.exception("Corrupt session for user %s", user_id)
        return None


def db_insert_incoming_event(event: dict[str, Any]) -> int:
    return state_store.insert_incoming_event(event)


def db_get_incoming_event(event_id: int) -> dict[str, Any] | None:
    try:
        return state_store.get_incoming_event(event_id)
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.exception("Corrupt incoming event payload id=%s", event_id)
        return None


def db_mark_incoming_event(event_id: int, status: str, error: str | None = None, increment_attempt: bool = False) -> None:
    state_store.mark_incoming_event(event_id, status, error=error, increment_attempt=increment_attempt)


def db_fetch_pending_event_ids(limit: int = 200) -> list[int]:
    return state_store.fetch_pending_event_ids(limit)


def db_append_history(
    user_id: str,
    message: str,
    attachments_count: int,
    attachment_types: list[str],
    attachment_urls: list[str],
) -> None:
    state_store.append_history(user_id, message, attachments_count, attachment_types, attachment_urls)


def db_recent_history(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    return state_store.recent_history(user_id, limit)


async def append_history(
    user_id: str,
    message: str,
    attachments_count: int,
    attachment_types: list[str] | None = None,
    attachment_urls: list[str] | None = None,
) -> None:
    await asyncio.to_thread(
        db_append_history,
        user_id,
        message,
        attachments_count,
        [str(t).lower().strip() for t in (attachment_types or [])],
        [str(u).strip() for u in (attachment_urls or []) if str(u).strip()],
    )


def _detect_payment_proof_keyword(message: str, attachment_types: list[str], state: int) -> bool:
    """Detect if message contains payment keywords AND has image attachment.
    Only valid if we're in payment state (state 3) and image contains payment proof indicators."""
    if state != 3:
        return False
    normalized_types = {str(t).lower().strip() for t in attachment_types if str(t).strip()}
    has_image = "image" in normalized_types
    if not has_image:
        return False
    text = message.lower().strip()
    # Must mention payment-related keywords when sending screenshot
    proof_words = ["paid", "payment", "sent", "trx", "bkash", "nagad", "rocket", "screenshot", "ss", "proof", "advance", "transferred"]
    mentions_payment = any(w in text for w in proof_words)
    # If no text but has image, could still be valid (checking if image is payment proof)
    # If text exists, it MUST mention payment
    return has_image and ((not text) or mentions_payment)


def _register_bargain_and_is_capped(session: dict[str, Any]) -> bool:
    now = time.time()
    timestamps = session.setdefault("bargain_timestamps", [])
    valid = [t for t in timestamps if now - float(t) <= BARGAIN_WINDOW_SECONDS]
    valid.append(now)
    session["bargain_timestamps"] = valid
    return len(valid) >= BARGAIN_CAP_AFTER_COUNT


def _build_order_summary(session: dict[str, Any]) -> str:
    lines = ["Order Summary:"]
    for item in session["cart"]["items"]:
        color = item.get("color")
        color_part = f" ({color.title()})" if color else ""
        lines.append(f"{item['quantity']} x {item['name']}{color_part}")
    breakdown = _payment_breakdown(session, session.get("location"))
    currency = _session_currency(session)
    lines.append(f"Items subtotal: {breakdown['subtotal']} {currency}")
    lines.append(f"Delivery charge: {breakdown['delivery']} {currency}")
    lines.append(f"Grand total: {breakdown['grand_total']} {currency}")
    lines.append(f"bKash advance ({int(ADVANCE_PERCENT * 100)}%): {breakdown['advance']} {currency}")
    lines.append(f"Cash on delivery ({100 - int(ADVANCE_PERCENT * 100)}%): {breakdown['remaining']} {currency}")
    lines.append(f"bKash (send money): {BKASH_NUMBER}")
    lines.append(f"Delivery time: {DELIVERY_TIME_TEXT}")
    return "\n".join(lines)


def _build_owner_packing_ticket(user_id: str, source: str, session: dict[str, Any], stage: str) -> str:
    breakdown = _payment_breakdown(session, session.get("location"))
    currency = _session_currency(session)
    item_lines: list[str] = []
    total_units = 0
    for item in session.get("cart", {}).get("items", []):
        qty = int(item.get("quantity", 0) or 0)
        total_units += max(0, qty)
        color = item.get("color")
        color_part = f" ({str(color).title()})" if color else ""
        item_lines.append(f"- {qty} x {item.get('name', 'Item')}{color_part}")

    if not item_lines:
        item_lines.append("- No items found")

    if stage == "confirmed":
        header = "PACKING QUEUE - PAYMENT CONFIRMED"
    else:
        header = "PACKING QUEUE - ADDRESS RECEIVED"

    return (
        f"{header}\n"
        f"Source: {source}\n"
        f"Customer: {user_id}\n"
        f"Address: {session.get('location') or 'N/A'}\n"
        f"Items ({total_units} units):\n"
        + "\n".join(item_lines)
        + "\n"
        + f"Subtotal: {breakdown['subtotal']} {currency}\n"
        + f"Delivery: {breakdown['delivery']} {currency}\n"
        + f"Grand total: {breakdown['grand_total']} {currency}\n"
        + f"Advance due ({int(ADVANCE_PERCENT * 100)}%): {breakdown['advance']} {currency}\n"
        + f"COD remaining ({100 - int(ADVANCE_PERCENT * 100)}%): {breakdown['remaining']} {currency}\n"
        + f"bKash: {BKASH_NUMBER}\n"
        + f"Delivery ETA: {DELIVERY_TIME_TEXT}"
    )


def _owner_pack_signature(session: dict[str, Any]) -> str:
    payload = {
        "location": session.get("location"),
        "state": int(session.get("state", 0) or 0),
        "items": [
            {
                "name": str(item.get("name") or ""),
                "qty": int(item.get("quantity", 0) or 0),
                "color": str(item.get("color") or ""),
                "price": int(item.get("price", 0) or 0),
            }
            for item in session.get("cart", {}).get("items", [])
        ],
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def notify_owner_order(user_id: str, session: dict[str, Any]) -> None:
    item_lines = []
    for item in session["cart"]["items"]:
        color = item.get("color")
        color_part = f" ({color})" if color else ""
        item_lines.append(f"- {item['quantity']} x {item['name']}{color_part}")

    notification = (
        "NEW ORDER\n"
        f"User: {user_id}\n"
        "Items:\n"
        + "\n".join(item_lines)
        + "\n"
        + f"Total: {session['cart']['total_price']} {_session_currency(session)}\n"
        + f"Location: {session.get('location') or 'Not provided'}\n"
        + "Payment: CONFIRMED (recheck manually)\n"
        + PAYMENT_CONFIRMATION_TEXT
        + "\n"
        + DELIVERY_CHARGE_TEXT
        + "\n"
        + f"Delivery time: {DELIVERY_TIME_TEXT}"
    )
    logger.info(notification)


def notify_owner_doubt(user_id: str, text: str) -> None:
    logger.info("CUSTOMER QUESTION user=%s text=%s", user_id, text)


def _should_send_idle_reminder(session: dict[str, Any]) -> tuple[bool, str]:
    """Check if customer is idle long enough to warrant a reminder. Returns (should_send, reason)."""
    if not ENABLE_IDLE_REMINDERS:
        return False, "reminders_disabled"
    
    state = int(session.get("state", 0) or 0)
    now = time.time()
    last_activity = float(session.get("last_activity_at", now) or now)
    last_reminder = float(session.get("last_idle_reminder_at", 0) or 0)
    idle_time = now - last_activity
    
    # Only send one reminder per state, with cooldown
    if last_reminder > 0 and (now - last_reminder) < 600:  # 10-min cooldown between reminders
        return False, "cooldown_active"
    
    # State 1: Cart pending (items added but not confirmed)
    if state == 1 and idle_time > IDLE_TIMEOUT_AFTER_CART_SECONDS:
        return True, "cart_abandoned_1h"
    
    # State 2: Address pending (order confirmed but no address)
    if state == 2 and idle_time > IDLE_TIMEOUT_AFTER_CART_SECONDS:
        return True, "address_pending_1h"
    
    # State 3: Payment pending (address provided but no payment proof)
    if state == 3 and idle_time > IDLE_TIMEOUT_AFTER_ADDRESS_SECONDS:
        return True, "payment_pending_1h"
    
    return False, "no_reminder_needed"


def _get_idle_reminder_message(session: dict[str, Any]) -> str:
    """Generate context-aware reminder message for idle customer."""
    state = int(session.get("state", 0) or 0)
    cart_total = int(session.get("cart", {}).get("total_price", 0) or 0)
    currency = _session_currency(session)
    
    if state == 1:
        return (
            f"Hey apu! 👋 We noticed you added items to cart (Total: {cart_total} {currency}) "
            f"but haven't confirmed yet. Ready to move forward or need help? Just say 'order' to proceed! 🛍️"
        )
    elif state == 2:
        return (
            f"Hi apu! 📍 We're ready to process your order (Total: {cart_total} {currency}), "
            f"we just need your delivery address. Where should we send it? 🚚"
        )
    elif state == 3:
        return (
            f"Quick reminder apu! 💳 We have your address ready. Now we need the bKash advance payment "
            f"({int(ADVANCE_PERCENT * 100)}% = {int(cart_total * ADVANCE_PERCENT)} {currency}) to {BKASH_NUMBER}. "
            f"Send it & reply with screenshot! ✓"
        )
    return "Still here apu? Let us know if you need anything! 😊"


def _session_is_dead(session: dict[str, Any]) -> bool:
    """Check if session should be marked abandoned (no activity in N days)."""
    state = int(session.get("state", 0) or 0)
    created_at = float(session.get("created_at", time.time()) or time.time())
    now = time.time()
    age_days = (now - created_at) / 86400
    
    # Only mark incomplete sessions as dead, never mark completed orders
    if state >= 4:  # States 4+ are completed/shipped
        return False
    
    return age_days > SESSION_EXPIRY_DAYS


def handle_message(
    user_id: str,
    intent_data: dict[str, Any],
    source: str = "unknown",
    session: dict[str, Any] | None = None,
    payment_proof_detected: bool = False,
    selected_product: dict[str, Any] | None = None,
) -> tuple[str, bool]:
    if session is None:
        session = session_cache.setdefault(user_id, _new_session())

    intent = intent_data["intent"]
    quantity = intent_data["quantity"]
    color = intent_data["color"]
    location = intent_data["location"]
    payment_detected = intent_data["payment_detected"]

    allow_upsell = False

    if intent == "unknown":
        return _safe_default_reply(), False

    if intent == "deny":
        session["cart"] = {"items": [], "total_price": 0}
        session["state"] = 0
        return "No problem apu! Cart cleared. 🗑️ Anything else you'd like to explore? We have new arrivals!", False

    if intent == "price":
        product = selected_product or PRODUCT
        name = str(product.get("name") or PRODUCT["name"])
        price = int(product.get("price") or PRODUCT["price"])
        currency = str(product.get("currency") or PRODUCT["currency"])
        return f"✓ {name}: {price} {currency} - Premium quality, best price! Ready to add to your order? Just say yes! 😊", False

    if intent == "add_item":
        _add_or_update_item(session, quantity, color, product=selected_product)
        session["state"] = 1

        item_count = sum(item["quantity"] for item in session["cart"]["items"])
        cart_total = session['cart']['total_price']
        currency = _session_currency(session)
        
        # Build concise, action-focused reply
        reply = f"✓ Added to cart! Total now: {cart_total} {currency}"
        
        if color is None:
            reply += " | What color? (Black/White/etc)"
        else:
            reply += f" | {color.upper()} selected"
        
        # Add upsell suggestion if below minimum, otherwise standard CTA
        addon_suggestion = _get_add_on_suggestion(cart_total, MIN_ORDER_TOTAL)
        if addon_suggestion:
            reply += f" | {addon_suggestion}"
        else:
            reply += f" | {_create_closing_cta(1, cart_total)}"

        if not session["upsell_used"]:
            allow_upsell = True
            session["upsell_used"] = True
        return reply, allow_upsell

    if intent == "order":
        if not session["cart"]["items"]:
            _add_or_update_item(session, quantity, color, product=selected_product)

        cart_total = int(session["cart"].get("total_price", 0) or 0)
        if cart_total <= MIN_ORDER_TOTAL:
            need_more = max(MIN_ORDER_TOTAL - cart_total, 1)
            logger.info("ORDER BLOCKED - Below minimum. user total=%s minimum=%s need=%s", cart_total, MIN_ORDER_TOTAL, need_more)
            return _min_order_message(session, source), False

        if color and session["cart"]["items"]:
            session["cart"]["items"][-1]["color"] = color

        session["state"] = 2
        return f"Excellent! 🎯 We're almost there - just need your delivery address apu! Share it now & we'll process today. {_create_closing_cta(2)}", False

    if intent == "location" or (session["state"] == 2 and location):
        if location:
            session["location"] = location
        if not session["location"]:
            return "We need your full address apu - building, street, area, everything! 📍", False

        cart_total = int(session["cart"].get("total_price", 0) or 0)
        if cart_total <= MIN_ORDER_TOTAL:
            return _min_order_message(session, source), False

        session["state"] = 3
        summary = _build_order_summary(session)
        reply = (
            summary + 
            f"\n✅ ORDER TOTAL: {cart_total} {_session_currency(session)}\n"
            f"(Minimum order: {MIN_ORDER_TOTAL} {_session_currency(session)} - Your order qualifies ✓)\n\n"
            f"💳 PAYMENT REQUIRED:\n"
            f"Send to: bKash {BKASH_NUMBER}\n"
            f"{_create_closing_cta(3)}\n"
            f"📸 IMPORTANT: After sending, MUST reply with screenshot to confirm!"
        )
        return reply, False

    if intent == "payment" or (session["state"] == 3 and payment_detected):
        if session["state"] != 3:
            return "I need your address first to finalize! Share it now? 📍", False
        breakdown = _payment_breakdown(session, session.get("location"))
        currency = _session_currency(session)
        if not payment_proof_detected:
            return (
                f"💳 bKash PAYMENT REQUIRED:\n"
                f"Send to: {BKASH_NUMBER}\n"
                f"Amount: {breakdown['advance']} {currency} (advance/60%)\n\n"
                f"💰 Order Breakdown:\n"
                f"• Total: {breakdown['grand_total']} {currency}\n"
                f"• Advance (60%): {breakdown['advance']} {currency} → Send now to bKash\n"
                f"• Cash on delivery (40%): {breakdown['remaining']} {currency}\n\n"
                f"📸 IMPORTANT:\n"
                f"After sending the bKash payment, MUST send a screenshot of the transaction!\n"
                f"Screenshot should show: Transaction ID, Amount, Status (Sent/Received)\n\n"
                f"👉 Send screenshot now to confirm your order! 🎯"
            ), False
        session["payment_proof_received"] = True
        session["state"] = 4
        logger.info("PAYMENT CONFIRMED user=%s amount=%s", session.get("user_id", "unknown"), breakdown['advance'])
        return (
            f"🎉 ORDER CONFIRMED! 🎉\n"
            f"✅ Payment verified - bKash screenshot received!\n\n"
            f"📦 Order Details:\n"
            f"• Total: {breakdown['grand_total']} {currency}\n"
            f"• Advance paid: {breakdown['advance']} {currency} ✓\n"
            f"• COD on delivery: {breakdown['remaining']} {currency}\n"
            f"• Delivery location: {session.get('location', 'N/A')}\n"
            f"• Delivery time: {DELIVERY_TIME_TEXT}\n\n"
            f"Our team will contact you within 1-2 hours with tracking details.\n"
            f"Thank you for your order apu! 🙏"
        ), False

    if session["state"] == 4:
        return f"✓ Your order is confirmed and being processed! You'll get tracking details soon. Thank you apu! 🙏 {_create_closing_cta(4)}", False

    if not session["cart"]["items"]:
        return f"Our bestseller: {PRODUCT['name']} - just {PRODUCT['price']} {_session_currency(session)}! Premium quality. Ready to order? 🛍️", False

    return (
        f"📦 Cart: {session['cart']['total_price']} {_session_currency(session)} | "
        f"{_create_closing_cta(1, session['cart']['total_price'])}"
    ), False


async def fetch_recent_messages_from_graph(user_id: str, limit: int = 10) -> list[dict[str, Any]]:
    if not PAGE_ACCESS_TOKEN or not PAGE_ID:
        return []

    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/conversations"
    params = {
        "access_token": PAGE_ACCESS_TOKEN,
        "fields": f"participants,messages.limit({max(1, limit)}){{id,from,message,text,created_time,attachments}}",
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client_http:
            response = await client_http.get(url, params=params)
        if response.status_code >= 400:
            logger.warning("Graph API history error %s %s", response.status_code, response.text)
            return []

        data = response.json()
        conversations = data.get("data", [])

        matched_conversation: dict[str, Any] | None = None
        for convo in conversations:
            participants = convo.get("participants", {}).get("data", [])
            participant_ids = {str(p.get("id", "")) for p in participants}
            if user_id in participant_ids:
                matched_conversation = convo
                break

        if matched_conversation is None:
            return []

        msgs = matched_conversation.get("messages", {}).get("data", [])
        user_messages: list[dict[str, Any]] = []

        for msg in msgs:
            sender_id = str(msg.get("from", {}).get("id", ""))
            if sender_id != user_id:
                continue

            text = str(msg.get("text") or msg.get("message") or "").strip()
            attachments_raw = msg.get("attachments", {}).get("data", [])
            attachment_types = [str(a.get("type", "")).lower() for a in attachments_raw if str(a.get("type", "")).strip()]

            user_messages.append(
                {
                    "text": text,
                    "attachments_count": len(attachments_raw),
                    "attachment_types": attachment_types,
                    "attachment_urls": [],
                    "created_time": msg.get("created_time"),
                }
            )

        user_messages.sort(key=lambda m: str(m.get("created_time") or ""))
        return user_messages[-limit:]

    except (httpx.HTTPError, ValueError) as exc:
        logger.exception("fetch_recent_messages_from_graph failed: %s", exc)
        return []


def rebuild_state_from_history(messages: list[dict[str, Any]]) -> dict[str, Any]:
    rebuilt = _new_session()
    if not messages:
        return rebuilt

    for entry in messages[-10:]:
        text = str(entry.get("text", "")).strip()
        attachments_count = int(entry.get("attachments_count", 0) or 0)
        attachment_types = [str(t).lower() for t in (entry.get("attachment_types") or [])]

        intent_data = _detect_intent_sync(text)
        payment_proof_detected = _detect_payment_proof_keyword(text, attachment_types, rebuilt["state"])
        if payment_proof_detected:
            intent_data["intent"] = "payment"
            intent_data["payment_detected"] = True

        intent_data = apply_attachment_rules(
            intent_data,
            text,
            attachments_count,
            attachment_types,
            current_state=rebuilt["state"],
            payment_proof_detected=payment_proof_detected,
        )

        if intent_data.get("is_question"):
            continue

        handle_message("rebuild", intent_data, session=rebuilt, payment_proof_detected=payment_proof_detected)

    return rebuilt


async def ensure_user_session(user_id: str) -> dict[str, Any]:
    cached = session_cache.get(user_id)
    if cached is not None:
        return cached

    db_session = await asyncio.to_thread(db_get_session, user_id)
    if db_session is not None:
        _set_session_cache(user_id, db_session)
        return db_session

    history = await asyncio.to_thread(db_recent_history, user_id, 20)
    if not history:
        history = await fetch_recent_messages_from_graph(user_id, limit=10)

    rebuilt = rebuild_state_from_history(history or [])
    _set_session_cache(user_id, rebuilt)
    await asyncio.to_thread(db_save_session, user_id, rebuilt)
    return rebuilt


def apply_attachment_rules(
    intent_data: dict[str, Any],
    message: str,
    attachments_count: int,
    attachment_types: list[str],
    current_state: int,
    payment_proof_detected: bool,
) -> dict[str, Any]:
    result = dict(intent_data)
    if attachments_count <= 0:
        return result

    text = message.strip().lower()
    current_intent = str(result.get("intent", "unknown")).lower()
    normalized_types = {str(t).lower().strip() for t in attachment_types if str(t).strip()}

    if current_state == 3:
        if payment_proof_detected:
            result["intent"] = "payment"
            result["payment_detected"] = True
        return result

    if not text:
        # Only shared post-like attachments imply product add.
        if "share" in normalized_types:
            result["intent"] = "add_item"
            result["quantity"] = max(1, attachments_count)
        return result

    if current_intent in {"payment", "location", "question", "order"}:
        return result

    # Text + shared attachment can imply adding product.
    if "share" in normalized_types and current_intent in {"unknown", "other", "price"}:
        result["intent"] = "add_item"
        result["quantity"] = max(1, int(result.get("quantity", 1)))

    return result


async def process_message(
    user_id: str,
    message: str,
    source: str = "unknown",
    attachments_count: int = 0,
    attachment_types: list[str] | None = None,
    attachment_urls: list[str] | None = None,
) -> tuple[str, bool]:
    attachment_types = [str(t).lower().strip() for t in (attachment_types or [])]
    attachment_urls = [str(u).strip() for u in (attachment_urls or []) if str(u).strip()]
    inferred_attachments_count = attachments_count if attachments_count > 0 else len(attachment_urls)

    user_lock = await _get_user_lock(user_id)
    async with user_lock:
        allowed = await _consume_rate_limit(user_id)
        if not allowed:
            return "Slow down apu! 🚦 Too many messages too fast. Give me 10-20 seconds, then try again. Thanks!", True

        session = await ensure_user_session(user_id)
        previous_state = int(session["state"])
        selected_product = None
        clean_message = message.strip()
        lower_message = clean_message.lower()

        if lower_message in {"help", "human", "agent", "person", "manual", "owner"}:
            session["human_handoff_requested"] = True
            await send_owner_alert(
                source,
                f"HUMAN HANDOFF REQUEST\nSource: {source}\nUser: {user_id}\nText: {clean_message or 'manual handoff requested'}",
            )
            saved = await asyncio.to_thread(db_save_session, user_id, session)
            if not saved:
                logger.warning("Session version conflict while saving handoff request user=%s", user_id)
            _set_session_cache(user_id, session)
            return "A team member will continue with you shortly. Please send the product name, screenshot, or question and we'll handle it manually.", True

        if COMPLIANCE_SAFE_MODE and int(session.get("auto_reply_count", 0) or 0) >= max(1, MAX_AUTO_REPLIES_BEFORE_HANDOFF) and previous_state < 3:
            session["human_handoff_requested"] = True
            await send_owner_alert(
                source,
                f"AUTO HANDOFF TRIGGERED\nSource: {source}\nUser: {user_id}\nState: {previous_state}\nLast text: {clean_message or '(empty)'}",
            )
            saved = await asyncio.to_thread(db_save_session, user_id, session)
            if not saved:
                logger.warning("Session version conflict while saving auto handoff user=%s", user_id)
            _set_session_cache(user_id, session)
            return "I'll hand this conversation to a team member now so we can help you properly.", True

        if clean_message and session.get("state") in {0, 1} and _is_catalog_query(clean_message):
            matches = _search_catalog_products(clean_message, source=source, limit=5)
            if matches:
                return _format_catalog_matches_reply(clean_message, source, matches), True
            await send_owner_alert(
                source,
                f"CUSTOMER QUERY (no match)\nSource: {source}\nUser: {user_id}\nText: {clean_message}",
            )
            return "Let me check with our boss & get back to you in 5 mins with what we have! ✓", True

        pending_options = session.get("pending_product_options")
        if isinstance(pending_options, list) and pending_options:
            chosen = _pick_product_option_from_text(message, pending_options)
            if chosen is not None:
                session["pending_product_options"] = []
                selected_product = chosen
            else:
                return _format_product_options_message(pending_options), True

        if selected_product is None and attachment_urls:
            product_candidates = _resolve_product_candidates_from_attachments(attachment_urls)
            if len(product_candidates) == 1:
                selected_product = product_candidates[0]
            elif len(product_candidates) > 1:
                session["pending_product_options"] = product_candidates
                return _format_product_options_message(product_candidates), True

        if inferred_attachments_count > 0 and selected_product is None and previous_state != 3:
            # If the user sent a plain image (not a product-post URL), try vision product inquiry
            has_image = "image" in attachment_types
            if has_image and attachment_urls:
                identification = await asyncio.to_thread(
                    _identify_product_in_image_sync, attachment_urls[0], message
                )
                product_type = identification.get("product_type")
                is_inquiry = identification.get("is_product_inquiry", True)

                if product_type and is_inquiry:
                    # Try to find matching products, combining product type and style hints
                    search_query = product_type
                    style_hints = identification.get("style_hints", [])
                    if style_hints:
                        search_query = f"{product_type} {' '.join(style_hints[:2])}"
                    
                    matches = _search_catalog_products(search_query, source=source, limit=5)
                    if matches:
                        lines = [f"✨ Great eye! We have {product_type} that match what you showed:\n"]
                        ask_price = any(w in lower_message for w in ["price", "koto", "dam"])
                        for idx, (key, prod) in enumerate(matches[:5], start=1):
                            name = str(prod.get("name") or product_type)
                            price = int(prod.get("price") or 0)
                            currency = str(prod.get("currency") or "tk")
                            link = _canonical_full_link(key)
                            if ask_price:
                                lines.append(f"{idx}) {name} - {price} {currency}\n   🔗 {link}")
                            else:
                                lines.append(f"{idx}) {name}\n   🔗 {link}")
                        lines.append(f"\n👉 Reply with the number to add one to your cart, or visit the link directly! Any of these apu? 😊")
                        return "\n".join(lines), True
                    else:
                        await send_owner_alert(
                            source,
                            f"CUSTOMER IMAGE QUERY (no match)\\nSource: {source}\\nUser: {user_id}\\nText: {clean_message}\\nProduct type: {product_type}\\nStyle hints: {style_hints}",
                        )
                        product_types = _get_available_product_types()
                        types_list = ", ".join(product_types[:6]) if product_types else "earrings, glasses, bags"
                        reply = (
                            f"Great photo! We don't have that exact {product_type} in stock now 😢\n"
                            f"But we have: {types_list} & more!\n\n"
                            f"Want to see what we have instead apu? Just say which one! 🛍️"
                        )
                        return reply, True
                else:
                    # Image sent but no clear product identified
                    product_types = _get_available_product_types()
                    types_list = ", ".join(product_types[:6]) if product_types else "earrings, glasses, bags"
                    return (
                        f"Nice pic! 📸 But I'm not sure what product you're showing apu.\n\n"
                        f"Can you tell me what it is? We have:\n"
                        f"👉 {types_list}\n"
                        f"& more!\n\n"
                        f"Or describe what you see & I'll search for it! 😊"
                    ), True

            return "Tell me what you're looking for apu! 😊 I can help better if you describe it or send a picture.", True

        intent_data = await detect_intent(message)

        if selected_product and intent_data.get("intent") in {"unknown", "other", "price"}:
            intent_data["intent"] = "add_item"
            intent_data["is_question"] = False
            if int(intent_data.get("quantity", 0) or 0) <= 0:
                intent_data["quantity"] = 1

        payment_proof_detected = _detect_payment_proof_keyword(message, attachment_types, session["state"])
        if not payment_proof_detected and session["state"] == 3 and attachment_urls:
            payment_proof_detected = await analyze_payment_images(attachment_types, attachment_urls, message, session["state"])

        if payment_proof_detected:
            intent_data["intent"] = "payment"
            intent_data["payment_detected"] = True

        intent_data = apply_attachment_rules(
            intent_data,
            message,
            inferred_attachments_count,
            attachment_types,
            current_state=session["state"],
            payment_proof_detected=payment_proof_detected,
        )

        price_argument = _is_price_argument(message)
        if price_argument:
            intent_data["intent"] = "price"
            intent_data["is_question"] = False

        intent = intent_data["intent"]
        payment_detected = intent_data["payment_detected"]
        is_question = intent_data["is_question"]

        if is_question:
            notify_owner_doubt(user_id, message)
            await send_owner_alert(
                source,
                f"CUSTOMER QUESTION\nSource: {source}\nUser: {user_id}\nText: {clean_message}",
            )
            final_question_reply = await rewrite_reply("I'll confirm and let you know shortly", allow_upsell=False)
            return final_question_reply, True

        if price_argument:
            bargaining_capped = _register_bargain_and_is_capped(session)
            base_price = int(selected_product.get("price") or PRODUCT["price"]) if selected_product else int(PRODUCT["price"])
            fixed_price_reply = (
                f"I understand apu, but {base_price} {_session_currency(session)} is our best price - we maintain premium quality! "
                "That's why customers keep coming back. Ready to order? 💯"
            )
            if bargaining_capped:
                fixed_price_reply = (
                    f"The price is fixed at {base_price} {_session_currency(session)} - that's final. But it's worth every taka! "
                    "Shall I process your order now? Just send your address! 🎯"
                )
            final_price_reply = await rewrite_reply(fixed_price_reply, allow_upsell=False)
            saved = await asyncio.to_thread(db_save_session, user_id, session)
            if not saved:
                logger.warning("Session version conflict while saving bargain flow user=%s", user_id)
            return final_price_reply, True

        reply, allow_upsell = handle_message(
            user_id,
            intent_data,
            source=source,
            session=session,
            payment_proof_detected=payment_proof_detected,
            selected_product=selected_product,
        )

        if intent == "unknown":
            notify_owner_doubt(user_id, message)
            await send_owner_alert(
                source,
                f"CUSTOMER UNKNOWN\nSource: {source}\nUser: {user_id}\nText: {clean_message}",
            )

        unknown_count = int(session.get("unknown_count", 0))
        if intent == "unknown":
            unknown_count += 1
        else:
            unknown_count = 0
        session["unknown_count"] = unknown_count

        if unknown_count >= 2:
            reply = _super_confused_reply()
            allow_upsell = False

        # Send a consolidated packing ticket as soon as address is captured.
        # Re-send only if address/cart signature changed.
        if session.get("state") == 3 and session.get("location") and session.get("cart", {}).get("items"):
            current_signature = _owner_pack_signature(session)
            if current_signature != session.get("owner_pack_last_signature"):
                ticket = _build_owner_packing_ticket(user_id, source, session, stage="address")
                await send_owner_alert(source, ticket)
                session["owner_pack_last_signature"] = current_signature

        if payment_detected and payment_proof_detected and previous_state == 3:
            notify_owner_order(user_id, session)
            summary = _build_order_summary(session)
            await send_owner_alert(
                source,
                f"CONFIRMED ORDER\nSource: {source}\nUser: {user_id}\n{summary}\nLocation: {session.get('location') or 'n/a'}",
            )
            await send_owner_alert(source, _build_owner_packing_ticket(user_id, source, session, stage="confirmed"))

        final_reply = await rewrite_reply(reply, allow_upsell)

        # Track activity and check for idle timeouts
        session["last_activity_at"] = time.time()
        
        # Check if customer is idle and send reminder (only if we just got a message from them)
        should_send_reminder, reason = _should_send_idle_reminder(session)
        reminder_sent = False
        if should_send_reminder:
            try:
                reminder_msg = _get_idle_reminder_message(session)
                reminder_result = await send_message(user_id, reminder_msg)
                if reminder_result.get("ok"):
                    session["last_idle_reminder_at"] = time.time()
                    reminder_sent = True
                    logger.info("Idle reminder sent user=%s state=%s reason=%s", user_id, session.get("state"), reason)
            except Exception as e:
                logger.warning("Failed to send idle reminder user=%s: %s", user_id, e)

        saved = await asyncio.to_thread(db_save_session, user_id, session)
        if not saved:
            logger.warning("Session version conflict while saving user=%s", user_id)
        _set_session_cache(user_id, session)
        return final_reply, True


async def send_message(user_id: str, text: str) -> dict[str, Any]:
    if not PAGE_ACCESS_TOKEN or not PAGE_ID:
        logger.warning("send_message skipped, token/page not configured")
        return {"ok": False, "error": "Missing PAGE_ACCESS_TOKEN or PAGE_ID"}

    target_id = str(user_id).strip()
    is_owner_message = _is_owner_target(target_id)
    if not is_owner_message:
        session = session_cache.get(target_id)
        if session is not None:
            text = _apply_customer_compliance(text, session)

    if MESSAGE_SEND_DELAY_SECONDS > 0:
        await asyncio.sleep(MESSAGE_SEND_DELAY_SECONDS)

    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/messages"
    payload = {
        "recipient": {"id": user_id},
        "message": {"text": text},
    }
    params = {"access_token": PAGE_ACCESS_TOKEN}

    delay = GRAPH_SEND_RETRY_BASE_SECONDS
    last_error: str | None = None
    for attempt in range(1, max(1, GRAPH_SEND_RETRY_ATTEMPTS) + 1):
        try:
            async with httpx.AsyncClient(timeout=20) as client_http:
                response = await client_http.post(url, params=params, json=payload)

            if response.status_code < 400:
                if not is_owner_message:
                    session = session_cache.get(target_id)
                    if session is not None:
                        session["auto_reply_count"] = int(session.get("auto_reply_count", 0) or 0) + 1
                return {"ok": True, "data": response.json()}

            body = response.text
            retryable = response.status_code == 429 or response.status_code >= 500
            if not retryable or attempt >= GRAPH_SEND_RETRY_ATTEMPTS:
                logger.warning(
                    "send_message Graph API error user=%s status=%s body=%s",
                    user_id,
                    response.status_code,
                    body,
                )
                return {"ok": False, "status_code": response.status_code, "error": body}

            logger.warning(
                "send_message retryable Graph API error user=%s status=%s attempt=%s/%s",
                user_id,
                response.status_code,
                attempt,
                GRAPH_SEND_RETRY_ATTEMPTS,
            )
        except httpx.HTTPError as exc:
            last_error = str(exc)
            if attempt >= GRAPH_SEND_RETRY_ATTEMPTS:
                logger.exception("send_message HTTP failure user=%s err=%s", user_id, exc)
                return {"ok": False, "error": str(exc)}
            logger.warning(
                "send_message retryable HTTP failure user=%s attempt=%s/%s err=%s",
                user_id,
                attempt,
                GRAPH_SEND_RETRY_ATTEMPTS,
                exc,
            )

        await asyncio.sleep(delay)
        delay = min(delay * 2, 8.0)

    return {"ok": False, "error": last_error or "unknown send_message failure"}


def _owner_target_for_source(source: str) -> str:
    preferred = _preferred_platform(source)
    if preferred == "instagram" and OWNER_DM_INSTAGRAM_ID:
        return OWNER_DM_INSTAGRAM_ID
    if preferred == "messenger" and OWNER_DM_MESSENGER_ID:
        return OWNER_DM_MESSENGER_ID
    return OWNER_DM_ID


async def send_owner_alert(source: str, text: str) -> None:
    targets: list[str] = []
    preferred = _owner_target_for_source(source)
    if preferred:
        targets.append(preferred)
    if OWNER_DM_MESSENGER_ID:
        targets.append(OWNER_DM_MESSENGER_ID)
    if OWNER_DM_INSTAGRAM_ID:
        targets.append(OWNER_DM_INSTAGRAM_ID)
    if OWNER_DM_ID:
        targets.append(OWNER_DM_ID)

    dedup_targets = [t for i, t in enumerate(targets) if t and t not in targets[:i]]
    if not dedup_targets:
        logger.info("Owner alert skipped (owner id not configured). source=%s msg=%s", source, text)
        return

    for owner_id in dedup_targets:
        result = await send_message(owner_id, text)
        if not result.get("ok"):
            logger.warning("Owner alert send failed source=%s owner=%s result=%s", source, owner_id, result)


async def process_event(event: dict[str, Any]) -> None:
    user_id = event["user_id"]
    source = str(event.get("source") or "unknown")
    message = event["message"]
    attachments_count = int(event.get("attachments_count", 0))
    attachment_types = [str(t).lower() for t in (event.get("attachment_types") or [])]
    attachment_urls = [str(u) for u in (event.get("attachment_urls") or []) if str(u).strip()]

    await append_history(user_id, message, attachments_count, attachment_types, attachment_urls)
    final_reply, should_send = await process_message(
        user_id,
        message,
        source=source,
        attachments_count=attachments_count,
        attachment_types=attachment_types,
        attachment_urls=attachment_urls,
    )
    if should_send:
        send_result = await send_message(user_id, final_reply)
        if not send_result.get("ok"):
            raise RuntimeError(f"send_message failed: {send_result}")


async def process_event_by_id(event_id: int) -> None:
    event = await asyncio.to_thread(db_get_incoming_event, event_id)
    if event is None:
        await asyncio.to_thread(db_mark_incoming_event, event_id, "failed", "missing event payload", False)
        return

    try:
        user_id = str(event.get("user_id", "")).strip()
        if not user_id:
            await asyncio.to_thread(db_mark_incoming_event, event_id, "failed", "missing user_id", False)
            return
        burst_to_process: dict[str, Any] | None = None
        burst_size = 0
        min_trigger = max(1, BURST_MIN_MESSAGES_TO_TRIGGER)
        
        # Check if burst coalescing should be used
        async with burst_guard:
            if user_id not in burst_pending:
                # First event in potential burst - start coalesce timer
                burst_pending[user_id] = {
                    "events": [event],
                    "first_arrival_time": time.time(),
                    "event_ids": [event_id],
                }
                # If configured to avoid coalescing, process immediately.
                if min_trigger <= 1:
                    burst_to_process = {
                        "events": list(burst_pending[user_id]["events"]),
                        "event_ids": list(burst_pending[user_id]["event_ids"]),
                    }
                    burst_pending.pop(user_id, None)
                else:
                    # Start timeout task under supervisor so shutdown waits for in-flight bursts.
                    timer_task = task_supervisor.spawn(_coalesce_burst_with_timeout(user_id))
                    burst_timers[user_id] = timer_task
                logger.info("BURST started user=%s event_id=%s", user_id, event_id)
            else:
                # Additional event in existing burst
                burst_info = burst_pending[user_id]
                burst_info["events"].append(event)
                burst_info["event_ids"].append(event_id)
                burst_size = len(burst_info["events"])
                logger.info("BURST appended user=%s event_id=%s burst_size=%d", user_id, event_id, burst_size)
                
                # HARDCAP: If burst exceeds maximum, force process immediately (safety limit)
                if burst_size >= BURST_MAX_SIZE_HARDCAP:
                    logger.warning("BURST hardcap reached user=%s burst_size=%d, forcing immediate process", user_id, burst_size)
                    burst_to_process = {
                        "events": list(burst_info["events"]),
                        "event_ids": list(burst_info["event_ids"]),
                    }
                    burst_pending.pop(user_id, None)
                    timer = burst_timers.pop(user_id, None)
                    if timer:
                        timer.cancel()
                # Check if burst is large enough to trigger early processing (but below hardcap)
                elif burst_size >= max(BURST_EARLY_FLUSH_SIZE, min_trigger):
                    logger.info("BURST early flush size reached user=%s burst_size=%d, processing early", user_id, burst_size)
                    burst_to_process = {
                        "events": list(burst_info["events"]),
                        "event_ids": list(burst_info["event_ids"]),
                    }
                    burst_pending.pop(user_id, None)
                    timer = burst_timers.pop(user_id, None)
                    if timer:
                        timer.cancel()

        if burst_to_process is None:
            return

        await _process_burst_bundle(user_id, burst_to_process)
        return
        
    except Exception as exc:
        logger.exception("Failed processing event id=%s err=%s", event_id, exc)
        # Keep failed items retriable up to 3 attempts.
        status = _event_retry_status(event)
        await asyncio.to_thread(db_mark_incoming_event, event_id, status, str(exc), False)


async def recover_pending_events() -> None:
    pending_ids = await asyncio.to_thread(db_fetch_pending_event_ids, 200)
    if not pending_ids:
        return
    logger.info("Recovering %s pending webhook events", len(pending_ids))

    semaphore = asyncio.Semaphore(20)

    async def _recover_one(event_id: int) -> None:
        async with semaphore:
            await process_event_by_id(event_id)

    await asyncio.gather(*[_recover_one(event_id) for event_id in pending_ids], return_exceptions=True)


async def cleanup_dead_sessions() -> None:
    """Mark old sessions as abandoned and notify owner of stuck orders. Runs once on startup."""
    if not ENABLE_IDLE_REMINDERS:
        return
    
    logger.info("Starting cleanup of dead sessions")
    dead_session_count = 0
    try:
        # Scan in-memory session cache for dead sessions and report abandoned orders
        now = time.time()
        abandoned_orders = []
        
        for user_id, session in list(session_cache.items()):
            if _session_is_dead(session):
                state = session.get("state", 0)
                last_activity = session.get("last_activity_at", session.get("created_at", now))
                idle_hours = (now - last_activity) / 3600
                
                # Only alert owner for stuck orders (state 2-3 with items)
                if state in {2, 3} and session.get("cart", {}).get("items"):
                    cart_total = session.get("cart", {}).get("total_price", 0)
                    abandoned_orders.append({
                        "user_id": user_id,
                        "state": ["Initial", "Cart", "Address", "Payment"][min(state, 3)],
                        "total": cart_total,
                        "currency": session.get("currency", "BDT"),
                        "location": session.get("location", "N/A"),
                        "idle_hours": idle_hours,
                    })
                
                dead_session_count += 1
                logger.debug("Marked dead session user=%s state=%s idle=%.1fh", user_id, state, idle_hours)
        
        # Send consolidated abandoned orders report if any
        if abandoned_orders and OWNER_DM_ID:
            report_lines = ["🚨 ABANDONED ORDERS REPORT (7+ days inactive)\n"]
            for order in abandoned_orders[:10]:  # Top 10 only
                report_lines.append(
                    f"❌ {order['user_id']}\n"
                    f"   State: {order['state']} | Total: {order['total']} {order['currency']}\n"
                    f"   Idle: {order['idle_hours']:.1f}h | Address: {order['location']}\n"
                )
            if len(abandoned_orders) > 10:
                report_lines.append(f"\n... and {len(abandoned_orders) - 10} more")
            
            report = "\n".join(report_lines)
            try:
                await send_owner_alert("messenger", report)
            except Exception as e:
                logger.warning("Failed to send abandoned orders report: %s", e)
        
        logger.info("Cleanup complete: %d dead sessions found, %d abandoned orders reported", dead_session_count, len(abandoned_orders))
    except Exception as e:
        logger.warning("Error during session cleanup: %s", e)


async def schedule_event_processing(event: dict[str, Any]) -> None:
    await process_event(event)


async def schedule_event_processing_by_ids(event_ids: list[int]) -> None:
    for event_id in event_ids:
        await process_event_by_id(event_id)


def _verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    return verify_meta_signature(
        raw_body,
        signature_header,
        APP_SECRET,
        allow_insecure=ALLOW_INSECURE_WEBHOOK_SIGNATURES,
    )


def _spawn_processing_by_ids(event_ids: list[int]) -> None:
    unique_ids = [eid for i, eid in enumerate(event_ids) if eid > 0 and eid not in event_ids[:i]]
    if not unique_ids:
        return
    task_supervisor.spawn(schedule_event_processing_by_ids(unique_ids))


def _products_loaded_count() -> int:
    return len(PRODUCT_MAP)


app.include_router(
    build_router(
        RouteDeps(
            verify_token=VERIFY_TOKEN,
            admin_token=ADMIN_TOKEN,
            products_file_path=PRODUCTS_FILE_PATH,
            logger=logger,
            verify_signature=_verify_signature,
            extract_events=extract_webhook_events,
            allow_webhook_batch=_allow_webhook_batch,
            insert_event=db_insert_incoming_event,
            spawn_processing_by_ids=_spawn_processing_by_ids,
            append_history=append_history,
            process_message=process_message,
            reload_products=load_post_product_map,
            products_loaded=_products_loaded_count,
        )
    )
)


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
