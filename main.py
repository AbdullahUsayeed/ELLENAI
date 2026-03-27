from __future__ import annotations

import asyncio
from collections import deque
import hashlib
import hmac
import json
import logging
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from openai import APIError, OpenAI
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from product_store import load_products, normalize_product_url


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ellenai")

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
PAGE_ID = os.getenv("PAGE_ID", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "ANY_STRING")
APP_SECRET = os.getenv("APP_SECRET", "")
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

STATE_DB_PATH = Path(os.getenv("STATE_DB_PATH", "ellenai_state.db"))
MESSAGE_SEND_DELAY_SECONDS = float(os.getenv("MESSAGE_SEND_DELAY_SECONDS", "5"))
ENABLE_REPLY_REWRITE = os.getenv("ENABLE_REPLY_REWRITE", "1") == "1"
REWRITE_CACHE_TTL_SECONDS = int(os.getenv("REWRITE_CACHE_TTL_SECONDS", "900"))
INTENT_CACHE_TTL_SECONDS = int(os.getenv("INTENT_CACHE_TTL_SECONDS", "300"))
INTENT_CACHE_MAX_SIZE = int(os.getenv("INTENT_CACHE_MAX_SIZE", "10000"))
REWRITE_CACHE_MAX_SIZE = int(os.getenv("REWRITE_CACHE_MAX_SIZE", "10000"))
SESSION_CACHE_MAX_SIZE = int(os.getenv("SESSION_CACHE_MAX_SIZE", "5000"))

OPENAI_RETRY_ATTEMPTS = int(os.getenv("OPENAI_RETRY_ATTEMPTS", "3"))
OPENAI_RETRY_MIN_SECONDS = float(os.getenv("OPENAI_RETRY_MIN_SECONDS", "1"))
OPENAI_RETRY_MAX_SECONDS = float(os.getenv("OPENAI_RETRY_MAX_SECONDS", "8"))

USER_RATE_LIMIT_COUNT = int(os.getenv("USER_RATE_LIMIT_COUNT", "8"))
USER_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("USER_RATE_LIMIT_WINDOW_SECONDS", "20"))
WEBHOOK_RATE_LIMIT_COUNT = int(os.getenv("WEBHOOK_RATE_LIMIT_COUNT", "60"))
WEBHOOK_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("WEBHOOK_RATE_LIMIT_WINDOW_SECONDS", "10"))
PRODUCTS_FILE_PATH = Path(os.getenv("PRODUCTS_FILE_PATH", "products.json"))
BKASH_NUMBER = os.getenv("BKASH_NUMBER", "01942776220")
ADVANCE_PERCENT = float(os.getenv("ADVANCE_PERCENT", "0.60"))
MIN_ORDER_TOTAL = int(os.getenv("MIN_ORDER_TOTAL", "600"))
OWNER_DM_ID = os.getenv("OWNER_DM_ID", "")
OWNER_DM_MESSENGER_ID = os.getenv("OWNER_DM_MESSENGER_ID", "")
OWNER_DM_INSTAGRAM_ID = os.getenv("OWNER_DM_INSTAGRAM_ID", "")

PRODUCT = {
    "name": "Oversized Hoodie",
    "price": 2500,
    "currency": "BDT",
    "delivery": "20-25 days",
}
PRODUCT_MAP: dict[str, list[dict[str, Any]]] = {}

PAYMENT_CONFIRMATION_TEXT = "To confirm your order, please send 60% in bKash. Remaining 40% cash on delivery."
DELIVERY_CHARGE_TEXT = "Delivery charge: Inside Dhaka 85 tk, Outside Dhaka 150 tk."
DELIVERY_TIME_TEXT = "20-25 days"

BARGAIN_WINDOW_SECONDS = 120
BARGAIN_CAP_AFTER_COUNT = 3

STYLE_PROMPT = """
You are a friendly Instagram shop girl.

Tone:

* Slightly girly
* Bangla + English mix (Banglish)
* Casual, fun

Rules:

* Short replies (1-2 lines)
* Natural and human
* Never change price or totals
* Do not invent discounts
* If user negotiates price, stay polite but firm
"""

STYLE_EXAMPLES = """
apu eta onek cute, ami nijeyo use kortesi
price 2500, quality onek bhalo trust me
delivery 20-25 days lagbe apu
niben naki? ami confirm kore rakhi?
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


class TestRequest(BaseModel):
    user_id: str
    message: str
    source: str = "unknown"
    attachments_count: int = 0
    attachment_types: list[str] = Field(default_factory=list)
    attachment_urls: list[str] = Field(default_factory=list)


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
    else:
        logger.warning("APP_SECRET is empty; webhook signature verification is disabled")

    logger.info(
        "Runtime config source env_loaded=%s rewrite=%s delay=%s state_db=%s products_file=%s",
        Path(".env").exists(),
        ENABLE_REPLY_REWRITE,
        MESSAGE_SEND_DELAY_SECONDS,
        STATE_DB_PATH,
        PRODUCTS_FILE_PATH,
    )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    STATE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(STATE_DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                user_id TEXT PRIMARY KEY,
                session_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        session_cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        if "version" not in session_cols:
            conn.execute("ALTER TABLE sessions ADD COLUMN version INTEGER NOT NULL DEFAULT 0")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS message_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                text TEXT NOT NULL,
                attachments_count INTEGER NOT NULL,
                attachment_types_json TEXT NOT NULL,
                attachment_urls_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_history_user ON message_history(user_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS incoming_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_incoming_events_status ON incoming_events(status)")
    logger.info("State DB initialized at %s", STATE_DB_PATH)


# Track background processing tasks so shutdown can wait for them.
_active_tasks: set[asyncio.Task] = set()


def _spawn_task(coro) -> asyncio.Task:
    """Create a tracked asyncio task that removes itself on completion."""
    task = asyncio.create_task(coro)
    _active_tasks.add(task)
    task.add_done_callback(_active_tasks.discard)
    return task


@app.on_event("startup")
async def startup_event() -> None:
    log_startup_configuration()
    await asyncio.to_thread(init_db)
    await asyncio.to_thread(load_post_product_map)
    _spawn_task(recover_pending_events())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    if _active_tasks:
        logger.info("Shutdown: waiting for %s active task(s) to complete", len(_active_tasks))
        await asyncio.gather(*_active_tasks, return_exceptions=True)
        logger.info("Shutdown: all tasks finished")


def _new_session() -> dict[str, Any]:
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
        "unknown_count": 0,
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
    lines = ["Apu ei post e multiple options ache. Kon ta niben? Reply number diye den:"]
    for idx, option in enumerate(options, start=1):
        name = str(option.get("name") or "Item")
        price = int(option.get("price") or 0)
        currency = str(option.get("currency") or "BDT")
        lines.append(f"{idx}) {name} - {price} {currency}")
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
        "nose ring",
        "lip ring",
    ]
    return any(marker in q for marker in markers)


def _format_catalog_matches_reply(query: str, source: str, matches: list[tuple[str, dict[str, Any]]]) -> str:
    if not matches:
        return "Apu ei item ta ekhon stock e nai. Onno kono style dekhte chaile bolen, ami links dei."

    lines = ["Apu egula available ache, dekhun:"]
    for key, variant in matches:
        name = str(variant.get("name") or "Item")
        price = int(variant.get("price") or 0)
        currency = str(variant.get("currency") or "tk")
        lines.append(f"- {name}: {price} {currency} | {_canonical_full_link(key)}")
    lines.append("Kon ta niben bolen, ami order confirm korte help kori.")
    return "\n".join(lines)


def _min_order_message(session: dict[str, Any], source: str) -> str:
    subtotal = int(session.get("cart", {}).get("total_price", 0) or 0)
    need_more = max(0, MIN_ORDER_TOTAL - subtotal)
    suggestions = _search_catalog_products("accessories budget", source, limit=3)
    lines = [
        f"Apu minimum order {MIN_ORDER_TOTAL} tk. Ekhon cart {subtotal} tk.",
        f"Order confirm korte aro {need_more} tk add korte hobe.",
    ]
    if suggestions:
        lines.append("Quick add-on ideas:")
        for key, variant in suggestions:
            lines.append(
                f"- {variant.get('name', 'Item')} - {int(variant.get('price') or 0)} {variant.get('currency') or 'tk'} | {_canonical_full_link(key)}"
            )
    return "\n".join(lines)


def _payment_and_delivery_policy_lines() -> list[str]:
    return [
        PAYMENT_CONFIRMATION_TEXT,
        DELIVERY_CHARGE_TEXT,
        f"bKash (send money): {BKASH_NUMBER}",
        f"Delivery time: {DELIVERY_TIME_TEXT}",
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
    if client is None or not image_url:
        return False

    prompt = (
        "You are checking whether an image is a payment proof screenshot for ecommerce. "
        "Respond only JSON: {\"is_payment_proof\": true|false, \"reason\": \"short text\"}. "
        "Mark false for random photos, memes, product shots, or social posts. "
        f"User text context: {message}"
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
        return bool(parsed.get("is_payment_proof", False))
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
    Returns {"product_type": str | None, "is_product_inquiry": bool}."""
    if client is None or not image_url:
        return {"product_type": None, "is_product_inquiry": False}

    product_names: list[str] = []
    for variants in PRODUCT_MAP.values():
        for product in variants:
            name = str(product.get("name") or "").strip()
            if name:
                product_names.append(name)
    catalog_hint = ", ".join(product_names) if product_names else "various fashion items"

    prompt = (
        "You are a product recognition assistant for an online fashion store. "
        "Look at the image and identify what type of product is shown (e.g. 'glasses', 'earrings', 'hoodie', 'dress', 'bag', etc.). "
        "Also decide if the user is asking about product availability. "
        f"Our store catalog includes: {catalog_hint}. "
        f"User text: {message or '(no text)'}. "
        'Respond ONLY with JSON: {"product_type": "short product category in English", "is_product_inquiry": true|false}. '
        "Set is_product_inquiry to true if the user is asking whether this product is available. "
        "Set product_type to null if you cannot identify a product."
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
        return {
            "product_type": str(parsed.get("product_type") or "").strip().lower() or None,
            "is_product_inquiry": bool(parsed.get("is_product_inquiry", True)),
        }
    except (APIError, json.JSONDecodeError, ValueError) as exc:
        logger.exception("Product image identification failed: %s", exc)
        return {"product_type": None, "is_product_inquiry": False}


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


def _safe_default_reply() -> str:
    return "Oops apu, ami buste parini, kindly bolben ki niben?"


def _super_confused_reply() -> str:
    return "Lemme confirm from Ellen and get back to you right away apu"


def db_save_session(user_id: str, session: dict[str, Any]) -> bool:
    session_payload = {k: v for k, v in session.items() if k != "_version"}
    payload = json.dumps(session_payload, ensure_ascii=True)
    expected_version = int(session.get("_version", 0) or 0)
    with sqlite3.connect(STATE_DB_PATH) as conn:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            """
            UPDATE sessions
            SET session_json = ?, updated_at = ?, version = version + 1
            WHERE user_id = ? AND version = ?
            """,
            (payload, _utc_now_iso(), user_id, expected_version),
        )
        if cursor.rowcount == 1:
            session["_version"] = expected_version + 1
            return True

        existing = conn.execute("SELECT version FROM sessions WHERE user_id = ?", (user_id,)).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO sessions(user_id, session_json, updated_at, version)
                VALUES (?, ?, ?, 0)
                """,
                (user_id, payload, _utc_now_iso()),
            )
            session["_version"] = 0
            return True

    return False


def db_get_session(user_id: str) -> dict[str, Any] | None:
    with sqlite3.connect(STATE_DB_PATH) as conn:
        row = conn.execute("SELECT session_json, version FROM sessions WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        return None
    try:
        parsed = json.loads(str(row[0]))
        if isinstance(parsed, dict):
            parsed["_version"] = int(row[1] or 0)
            return parsed
        return None
    except json.JSONDecodeError:
        logger.exception("Corrupt session for user %s", user_id)
        return None


def db_insert_incoming_event(event: dict[str, Any]) -> int:
    user_id = str(event.get("user_id", "")).strip()
    payload = json.dumps(event, ensure_ascii=True)
    now_iso = _utc_now_iso()
    with sqlite3.connect(STATE_DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO incoming_events(user_id, payload_json, status, attempts, last_error, created_at, updated_at)
            VALUES (?, ?, 'pending', 0, NULL, ?, ?)
            """,
            (user_id, payload, now_iso, now_iso),
        )
        return int(cursor.lastrowid)


def db_get_incoming_event(event_id: int) -> dict[str, Any] | None:
    with sqlite3.connect(STATE_DB_PATH) as conn:
        row = conn.execute(
            "SELECT payload_json, status, attempts FROM incoming_events WHERE id = ?",
            (event_id,),
        ).fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(str(row[0]))
        if not isinstance(payload, dict):
            return None
        payload["_db_status"] = str(row[1])
        payload["_db_attempts"] = int(row[2] or 0)
        return payload
    except json.JSONDecodeError:
        logger.exception("Corrupt incoming event payload id=%s", event_id)
        return None


def db_mark_incoming_event(event_id: int, status: str, error: str | None = None, increment_attempt: bool = False) -> None:
    safe_error = (error or "")[:2000] if error else None
    with sqlite3.connect(STATE_DB_PATH) as conn:
        if increment_attempt:
            conn.execute(
                """
                UPDATE incoming_events
                SET status = ?, attempts = attempts + 1, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, safe_error, _utc_now_iso(), event_id),
            )
        else:
            conn.execute(
                """
                UPDATE incoming_events
                SET status = ?, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, safe_error, _utc_now_iso(), event_id),
            )


def db_fetch_pending_event_ids(limit: int = 200) -> list[int]:
    with sqlite3.connect(STATE_DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT id
            FROM incoming_events
            WHERE status IN ('pending', 'retry')
            ORDER BY id ASC
            LIMIT ?
            """,
            (max(1, limit),),
        ).fetchall()
    return [int(r[0]) for r in rows]


def db_append_history(
    user_id: str,
    message: str,
    attachments_count: int,
    attachment_types: list[str],
    attachment_urls: list[str],
) -> None:
    with sqlite3.connect(STATE_DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO message_history(
                user_id, text, attachments_count, attachment_types_json, attachment_urls_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                message,
                max(0, attachments_count),
                json.dumps(attachment_types, ensure_ascii=True),
                json.dumps(attachment_urls, ensure_ascii=True),
                _utc_now_iso(),
            ),
        )


def db_recent_history(user_id: str, limit: int = 20) -> list[dict[str, Any]]:
    with sqlite3.connect(STATE_DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT text, attachments_count, attachment_types_json, attachment_urls_json, created_at
            FROM message_history
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, max(1, limit)),
        ).fetchall()
    result: list[dict[str, Any]] = []
    for text, cnt, types_json, urls_json, created_at in reversed(rows):
        try:
            types = json.loads(str(types_json))
        except json.JSONDecodeError:
            types = []
        try:
            urls = json.loads(str(urls_json))
        except json.JSONDecodeError:
            urls = []
        result.append(
            {
                "text": str(text),
                "attachments_count": int(cnt),
                "attachment_types": [str(t).lower() for t in (types or [])],
                "attachment_urls": [str(u) for u in (urls or [])],
                "created_time": str(created_at),
            }
        )
    return result


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
    if state != 3:
        return False
    normalized_types = {str(t).lower().strip() for t in attachment_types if str(t).strip()}
    has_image = "image" in normalized_types
    if not has_image:
        return False
    text = message.lower().strip()
    proof_words = ["paid", "payment", "trx", "bkash", "nagad", "rocket", "screenshot", "ss", "proof"]
    mentions_payment = any(w in text for w in proof_words)
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
        return "Aight, cart cleared! Onno kisu nite chao?", False

    if intent == "price":
        product = selected_product or PRODUCT
        name = str(product.get("name") or PRODUCT["name"])
        price = int(product.get("price") or PRODUCT["price"])
        currency = str(product.get("currency") or PRODUCT["currency"])
        return f"Apu, {name} er price {price} {currency}! Nite chaile bolen, order confirm kore dei. 😊", False

    if intent == "add_item":
        _add_or_update_item(session, quantity, color, product=selected_product)
        session["state"] = 1

        item_count = sum(item["quantity"] for item in session["cart"]["items"])
        reply = (
            f"Items in cart: {item_count}. "
            f"Total: {session['cart']['total_price']} {_session_currency(session)}. "
            + " ".join(_payment_and_delivery_policy_lines())
        )

        if color is None:
            reply += " Which color do you want?"

        if not session["upsell_used"]:
            allow_upsell = True
            session["upsell_used"] = True
        return reply, allow_upsell

    if intent == "order":
        if not session["cart"]["items"]:
            _add_or_update_item(session, quantity, color, product=selected_product)

        if int(session["cart"].get("total_price", 0) or 0) <= MIN_ORDER_TOTAL:
            return _min_order_message(session, source), False

        if color and session["cart"]["items"]:
            session["cart"]["items"][-1]["color"] = color

        session["state"] = 2
        return "Please share your delivery location.", False

    if intent == "location" or (session["state"] == 2 and location):
        if location:
            session["location"] = location
        if not session["location"]:
            return "Please share your full delivery location.", False

        if int(session["cart"].get("total_price", 0) or 0) <= MIN_ORDER_TOTAL:
            return _min_order_message(session, source), False

        session["state"] = 3
        summary = _build_order_summary(session)
        reply = summary + "\nPlease send your bKash screenshot to confirm."
        return reply, False

    if intent == "payment" or (session["state"] == 3 and payment_detected):
        if session["state"] != 3:
            return "Please share your location first so I can prepare your order summary.", False
        breakdown = _payment_breakdown(session, session.get("location"))
        currency = _session_currency(session)
        if not payment_proof_detected:
            return (
                f"Thanks apu. Please send {breakdown['advance']} {currency} on bKash ({BKASH_NUMBER}) with screenshot to confirm. "
                f"Total with delivery {breakdown['grand_total']} {currency}; remaining {breakdown['remaining']} {currency} cash on delivery."
            ), False
        session["payment_proof_received"] = True
        session["state"] = 4
        return (
            "Payment noted. Your order is confirmed. "
            f"Total {breakdown['grand_total']} {currency}. "
            f"Advance paid {breakdown['advance']} {currency}. "
            f"Remaining {breakdown['remaining']} {currency} cash on delivery. "
            f"bKash number: {BKASH_NUMBER}. "
            f"Delivery time: {DELIVERY_TIME_TEXT}."
        ), False

    if session["state"] == 4:
        return "Your order is already confirmed. Thank you.", False

    if not session["cart"]["items"]:
        return f"{PRODUCT['name']} price is {PRODUCT['price']} {_session_currency(session)}.", False

    return (
        f"Current total: {session['cart']['total_price']} {_session_currency(session)}. "
        "Tell me quantity, color, or say confirm order."
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
            return "Apu ektu slow korun please, onek fast message ashtese. 10-20 sec por abar try korun.", False

        session = await ensure_user_session(user_id)
        previous_state = int(session["state"])
        selected_product = None
        clean_message = message.strip()
        lower_message = clean_message.lower()

        if clean_message and session.get("state") in {0, 1} and _is_catalog_query(clean_message):
            matches = _search_catalog_products(clean_message, source=source, limit=5)
            if matches:
                return _format_catalog_matches_reply(clean_message, source, matches), False
            await send_owner_alert(
                source,
                f"CUSTOMER QUERY (no match)\nSource: {source}\nUser: {user_id}\nText: {clean_message}",
            )
            return "Apu eta check kore owner ke janacchi, little wait koren please.", False

        pending_options = session.get("pending_product_options")
        if isinstance(pending_options, list) and pending_options:
            chosen = _pick_product_option_from_text(message, pending_options)
            if chosen is not None:
                session["pending_product_options"] = []
                selected_product = chosen
            else:
                return _format_product_options_message(pending_options), False

        if selected_product is None and attachment_urls:
            product_candidates = _resolve_product_candidates_from_attachments(attachment_urls)
            if len(product_candidates) == 1:
                selected_product = product_candidates[0]
            elif len(product_candidates) > 1:
                session["pending_product_options"] = product_candidates
                return _format_product_options_message(product_candidates), False

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
                    matches = _search_catalog_products(product_type, source=source, limit=5)
                    if matches:
                        lines = [f"Haa apu, {product_type} related options ache! Ekhane dekhun:"]
                        ask_price = any(w in lower_message for w in ["price", "koto", "dam"])
                        for key, prod in matches[:3]:
                            name = str(prod.get("name") or product_type)
                            price = int(prod.get("price") or 0)
                            currency = str(prod.get("currency") or "tk")
                            if ask_price:
                                lines.append(f"- {name}: {price} {currency} | {_canonical_full_link(key)}")
                            else:
                                lines.append(f"- {name}: {_canonical_full_link(key)}")
                        lines.append("Interested hole bolen, ami order confirm korte help kori.")
                        return "\n".join(lines), False
                    else:
                        await send_owner_alert(
                            source,
                            f"CUSTOMER IMAGE QUERY (no match)\nSource: {source}\nUser: {user_id}\nText: {clean_message}",
                        )
                        reply = (
                            f"Sorry apu, ekhon amader kache {product_type} nai 😢 "
                            "Notun product asle janabo! Onno kono product dekhte chai?"
                        )
                        return reply, False

            return "This item is not available right now apu 😢", False

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
                f"I totally understand apu but price fixed at {base_price} {_session_currency(session)}. "
                "Ami best quality maintain kortesi, tai price change kora possible na."
            )
            if bargaining_capped:
                fixed_price_reply = (
                    f"Apu bujhte parchi, price fixed {base_price} {_session_currency(session)} and eta ar change kora possible na. "
                    "Chaile ami order ta confirm kore dei now."
                )
            final_price_reply = await rewrite_reply(fixed_price_reply, allow_upsell=False)
            saved = await asyncio.to_thread(db_save_session, user_id, session)
            if not saved:
                logger.warning("Session version conflict while saving bargain flow user=%s", user_id)
            return final_price_reply, False

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

        if payment_detected and payment_proof_detected and previous_state == 3:
            notify_owner_order(user_id, session)
            summary = _build_order_summary(session)
            await send_owner_alert(
                source,
                f"CONFIRMED ORDER\nSource: {source}\nUser: {user_id}\n{summary}\nLocation: {session.get('location') or 'n/a'}",
            )

        final_reply = await rewrite_reply(reply, allow_upsell)

        saved = await asyncio.to_thread(db_save_session, user_id, session)
        if not saved:
            logger.warning("Session version conflict while saving user=%s", user_id)
        _set_session_cache(user_id, session)
        return final_reply, True


async def send_message(user_id: str, text: str) -> dict[str, Any]:
    if not PAGE_ACCESS_TOKEN or not PAGE_ID:
        logger.warning("send_message skipped, token/page not configured")
        return {"ok": False, "error": "Missing PAGE_ACCESS_TOKEN or PAGE_ID"}

    if MESSAGE_SEND_DELAY_SECONDS > 0:
        await asyncio.sleep(MESSAGE_SEND_DELAY_SECONDS)

    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/messages"
    payload = {
        "recipient": {"id": user_id},
        "message": {"text": text},
    }
    params = {"access_token": PAGE_ACCESS_TOKEN}

    try:
        async with httpx.AsyncClient(timeout=20) as client_http:
            response = await client_http.post(url, params=params, json=payload)
        if response.status_code >= 400:
            logger.warning("send_message Graph API error user=%s status=%s body=%s", user_id, response.status_code, response.text)
            return {"ok": False, "status_code": response.status_code, "error": response.text}
        return {"ok": True, "data": response.json()}
    except httpx.HTTPError as exc:
        logger.exception("send_message HTTP failure user=%s err=%s", user_id, exc)
        return {"ok": False, "error": str(exc)}


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


def verify_meta_signature(raw_body: bytes, signature_header: str | None) -> bool:
    if not APP_SECRET:
        # Allow local development when secret is not configured.
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(APP_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _count_supported_attachments(attachments: list[dict[str, Any]]) -> int:
    supported = {"image", "video", "share"}
    return sum(1 for att in attachments if str(att.get("type", "")).lower() in supported)


def _extract_attachment_types(attachments: list[dict[str, Any]]) -> list[str]:
    return [str(att.get("type", "")).lower() for att in attachments if str(att.get("type", "")).strip()]


def _extract_attachment_urls(attachments: list[dict[str, Any]]) -> list[str]:
    urls: list[str] = []
    for att in attachments:
        payload = att.get("payload", {}) if isinstance(att, dict) else {}
        image_obj = payload.get("image", {}) if isinstance(payload.get("image"), dict) else {}
        candidates = [
            payload.get("url"),
            payload.get("src"),
            image_obj.get("url"),
            image_obj.get("link"),
        ]
        for c in candidates:
            value = str(c).strip() if c else ""
            if value and value.startswith("http"):
                urls.append(value)
    return urls


def _extract_webhook_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for entry in payload.get("entry", []):
        for msg_event in entry.get("messaging", []):
            sender = msg_event.get("sender", {})
            message_obj = msg_event.get("message", {})

            # Skip echo events (the page's own sent messages echoed back by Meta).
            if message_obj.get("is_echo"):
                continue

            user_id = str(sender.get("id", "")).strip()
            text = str(message_obj.get("text", "")).strip()
            attachments = message_obj.get("attachments", []) or []
            attachments_count = _count_supported_attachments(attachments)
            attachment_types = _extract_attachment_types(attachments)
            attachment_urls = _extract_attachment_urls(attachments)

            if not user_id:
                continue

            if text or attachments_count > 0:
                events.append(
                    {
                        "user_id": user_id,
                        "source": "messenger",
                        "message": text,
                        "attachments_count": attachments_count,
                        "attachment_types": attachment_types,
                        "attachment_urls": attachment_urls,
                    }
                )

        for change in entry.get("changes", []):
            value = change.get("value", {})
            source = str(value.get("messaging_product") or "instagram").strip().lower()
            messages = value.get("messages", [])
            for msg in messages:
                user_id = str(msg.get("from", "")).strip()
                text = str(msg.get("text", {}).get("body", "")).strip()
                attachments = msg.get("attachments", []) or []
                attachments_count = _count_supported_attachments(attachments)
                attachment_types = _extract_attachment_types(attachments)
                attachment_urls = _extract_attachment_urls(attachments)
                if user_id and (text or attachments_count > 0):
                    events.append(
                        {
                            "user_id": user_id,
                            "source": source,
                            "message": text,
                            "attachments_count": attachments_count,
                            "attachment_types": attachment_types,
                            "attachment_urls": attachment_urls,
                        }
                    )

    return events


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
        await send_message(user_id, final_reply)


async def process_event_by_id(event_id: int) -> None:
    await asyncio.to_thread(db_mark_incoming_event, event_id, "processing", None, True)
    event = await asyncio.to_thread(db_get_incoming_event, event_id)
    if event is None:
        await asyncio.to_thread(db_mark_incoming_event, event_id, "failed", "missing event payload", False)
        return

    try:
        await process_event(event)
        await asyncio.to_thread(db_mark_incoming_event, event_id, "done", None, False)
    except Exception as exc:
        logger.exception("Failed processing event id=%s err=%s", event_id, exc)
        # Keep failed items retriable up to 3 attempts.
        attempts = int(event.get("_db_attempts", 0))
        status = "retry" if attempts < 3 else "failed"
        await asyncio.to_thread(db_mark_incoming_event, event_id, status, str(exc), False)


async def recover_pending_events() -> None:
    pending_ids = await asyncio.to_thread(db_fetch_pending_event_ids, 200)
    if not pending_ids:
        return
    logger.info("Recovering %s pending webhook events", len(pending_ids))
    for event_id in pending_ids:
        await process_event_by_id(event_id)


async def schedule_event_processing(event: dict[str, Any]) -> None:
    await process_event(event)


async def schedule_event_processing_by_ids(event_ids: list[int]) -> None:
    for event_id in event_ids:
        await process_event_by_id(event_id)


@app.get("/webhook", response_class=PlainTextResponse)
def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
) -> str:
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN and hub_challenge:
        return hub_challenge
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def webhook(request: Request) -> dict[str, Any]:
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    logger.info(
        "WEBHOOK POST received content_length=%s signature_present=%s",
        len(raw_body),
        bool(signature),
    )
    if not verify_meta_signature(raw_body, signature):
        logger.warning("WEBHOOK POST rejected invalid signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}") from exc

    events = _extract_webhook_events(payload)
    logger.info("WEBHOOK POST parsed events=%s object=%s", len(events), payload.get("object"))

    if not await _allow_webhook_batch(len(events)):
        logger.warning("WEBHOOK POST rate limited events=%s", len(events))
        raise HTTPException(status_code=429, detail="Webhook rate limit exceeded")

    # Persist first, then acknowledge webhook to avoid losing tasks on restart.
    event_ids: list[int] = []
    for event in events:
        event_id = await asyncio.to_thread(db_insert_incoming_event, event)
        event_ids.append(event_id)

    if event_ids:
        _spawn_task(schedule_event_processing_by_ids(event_ids))

    logger.info("WEBHOOK POST queued stored=%s", len(event_ids))

    return {"status": "ok", "queued": len(events), "stored": len(event_ids)}


@app.post("/test")
async def test_endpoint(body: TestRequest) -> dict[str, str]:
    await append_history(body.user_id, body.message, body.attachments_count, body.attachment_types, body.attachment_urls)
    reply, _ = await process_message(
        body.user_id,
        body.message,
        source=body.source,
        attachments_count=body.attachments_count,
        attachment_types=body.attachment_types,
        attachment_urls=body.attachment_urls,
    )
    return {"reply": reply}


@app.post("/admin/reload-products")
async def admin_reload_products(request: Request) -> dict[str, Any]:
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="Admin endpoint disabled: set ADMIN_TOKEN")

    provided_token = request.headers.get("X-Admin-Token", "")
    if provided_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")

    await asyncio.to_thread(load_post_product_map)
    return {
        "status": "ok",
        "products_loaded": len(PRODUCT_MAP),
        "products_file": str(PRODUCTS_FILE_PATH),
    }


@app.get("/")
def health() -> dict[str, str]:
    return {"status": "running"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
