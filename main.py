from __future__ import annotations

import asyncio
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
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from openai import APIError, OpenAI
from pydantic import BaseModel, Field


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("ellenai")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
PAGE_ID = os.getenv("PAGE_ID", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "ANY_STRING")
APP_SECRET = os.getenv("APP_SECRET", "")

STATE_DB_PATH = Path(os.getenv("STATE_DB_PATH", "ellenai_state.db"))
MESSAGE_SEND_DELAY_SECONDS = float(os.getenv("MESSAGE_SEND_DELAY_SECONDS", "5"))
ENABLE_REPLY_REWRITE = os.getenv("ENABLE_REPLY_REWRITE", "1") == "1"
REWRITE_CACHE_TTL_SECONDS = int(os.getenv("REWRITE_CACHE_TTL_SECONDS", "900"))
INTENT_CACHE_TTL_SECONDS = int(os.getenv("INTENT_CACHE_TTL_SECONDS", "300"))

PRODUCT = {
    "name": "Oversized Hoodie",
    "price": 2500,
    "currency": "BDT",
    "delivery": "3-5 days",
}

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
delivery 3-5 days lagbe apu
niben naki? ami confirm kore rakhi?
"""

INTENTS = {"price", "order", "add_item", "location", "payment", "question", "other", "unknown"}
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


class TestRequest(BaseModel):
    user_id: str
    message: str
    attachments_count: int = 0
    attachment_types: list[str] = Field(default_factory=list)
    attachment_urls: list[str] = Field(default_factory=list)


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
                updated_at TEXT NOT NULL
            )
            """
        )
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
    logger.info("State DB initialized at %s", STATE_DB_PATH)


@app.on_event("startup")
async def startup_event() -> None:
    await asyncio.to_thread(init_db)


def _new_session() -> dict[str, Any]:
    return {
        "state": 0,
        "location": None,
        "upsell_used": False,
        "bargain_timestamps": [],
        "payment_proof_received": False,
        "unknown_count": 0,
        "cart": {
            "items": [],
            "total_price": 0,
        },
    }


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

    if "shared_post" in text:
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
price | order | add_item | location | payment | question | other | unknown

Message:
{message}
"""

    if client is None:
        result = _normalize_intent(_fallback_detect(message))
        intent_cache[cache_key] = (time.time(), dict(result))
        _prune_cache(intent_cache, INTENT_CACHE_TTL_SECONDS)
        return result

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        result = _normalize_intent(parsed if isinstance(parsed, dict) else {})
    except (APIError, json.JSONDecodeError, ValueError) as exc:
        logger.exception("Intent detection failed: %s", exc)
        result = _normalize_intent(_fallback_detect(message))

    intent_cache[cache_key] = (time.time(), dict(result))
    _prune_cache(intent_cache, INTENT_CACHE_TTL_SECONDS)
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
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Keep numeric totals exactly unchanged."},
                {"role": "user", "content": rewrite_prompt},
            ],
            temperature=0.6,
        )
        rewritten = (response.choices[0].message.content or "").strip()
        final_text = rewritten if rewritten else text
    except APIError as exc:
        logger.exception("Reply rewrite failed: %s", exc)
        final_text = text

    rewrite_cache[cache_key] = (time.time(), final_text)
    _prune_cache(rewrite_cache, REWRITE_CACHE_TTL_SECONDS)
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
        response = client.chat.completions.create(
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


def _recalc_total(session: dict[str, Any]) -> None:
    total = 0
    for item in session["cart"]["items"]:
        total += int(item["quantity"]) * PRODUCT["price"]
    session["cart"]["total_price"] = total


def _add_or_update_item(session: dict[str, Any], quantity: int, color: str | None) -> None:
    target_color = color.lower() if color else None
    items = session["cart"]["items"]

    for item in items:
        if item["product"] == PRODUCT["name"] and item.get("color") == target_color:
            item["quantity"] += quantity
            _recalc_total(session)
            return

    items.append(
        {
            "product": PRODUCT["name"],
            "quantity": quantity,
            "color": target_color,
        }
    )
    _recalc_total(session)


def _safe_default_reply() -> str:
    return "Oops apu, ami buste parini, kindly bolben ki niben?"


def _super_confused_reply() -> str:
    return "Lemme confirm from Ellen and get back to you right away apu"


def db_save_session(user_id: str, session: dict[str, Any]) -> None:
    payload = json.dumps(session, ensure_ascii=True)
    with sqlite3.connect(STATE_DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO sessions(user_id, session_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                session_json=excluded.session_json,
                updated_at=excluded.updated_at
            """,
            (user_id, payload, _utc_now_iso()),
        )


def db_get_session(user_id: str) -> dict[str, Any] | None:
    with sqlite3.connect(STATE_DB_PATH) as conn:
        row = conn.execute("SELECT session_json FROM sessions WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        return None
    try:
        return json.loads(str(row[0]))
    except json.JSONDecodeError:
        logger.exception("Corrupt session for user %s", user_id)
        return None


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
        lines.append(f"{item['quantity']} x {item['product']}{color_part}")
    lines.append(f"Total: {session['cart']['total_price']} {PRODUCT['currency']}")
    lines.append(f"Delivery: {PRODUCT['delivery']}")
    return "\n".join(lines)


def notify_owner_order(user_id: str, session: dict[str, Any]) -> None:
    item_lines = []
    for item in session["cart"]["items"]:
        color = item.get("color")
        color_part = f" ({color})" if color else ""
        item_lines.append(f"- {item['quantity']} x {item['product']}{color_part}")

    notification = (
        "NEW ORDER\n"
        f"User: {user_id}\n"
        "Items:\n"
        + "\n".join(item_lines)
        + "\n"
        + f"Total: {session['cart']['total_price']} {PRODUCT['currency']}\n"
        + f"Location: {session.get('location') or 'Not provided'}\n"
        + "Payment: CONFIRMED (recheck manually)\n"
        + f"Delivery: {PRODUCT['delivery']}"
    )
    logger.info(notification)


def notify_owner_doubt(user_id: str, text: str) -> None:
    logger.info("CUSTOMER QUESTION user=%s text=%s", user_id, text)


def handle_message(
    user_id: str,
    intent_data: dict[str, Any],
    session: dict[str, Any] | None = None,
    payment_proof_detected: bool = False,
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

    if intent in {"price", "add_item"}:
        _add_or_update_item(session, quantity, color)
        session["state"] = 1

        item_count = sum(item["quantity"] for item in session["cart"]["items"])
        reply = (
            f"Items in cart: {item_count}. "
            f"Total: {session['cart']['total_price']} {PRODUCT['currency']}. "
            f"Delivery: {PRODUCT['delivery']}."
        )

        if color is None:
            reply += " Which color do you want?"

        if not session["upsell_used"]:
            allow_upsell = True
            session["upsell_used"] = True
        return reply, allow_upsell

    if intent == "order":
        if not session["cart"]["items"]:
            _add_or_update_item(session, quantity, color)

        if color and session["cart"]["items"]:
            session["cart"]["items"][-1]["color"] = color

        session["state"] = 2
        return "Please share your delivery location.", False

    if intent == "location" or (session["state"] == 2 and location):
        if location:
            session["location"] = location
        if not session["location"]:
            return "Please share your full delivery location.", False

        session["state"] = 3
        summary = _build_order_summary(session)
        reply = summary + "\nPlease send payment and screenshot to confirm."
        return reply, False

    if intent == "payment" or (session["state"] == 3 and payment_detected):
        if session["state"] != 3:
            return "Please share your location first so I can prepare your order summary.", False
        if not payment_proof_detected:
            return "Thanks apu. Please send your payment screenshot so I can confirm the order.", False
        session["payment_proof_received"] = True
        session["state"] = 4
        return "Payment noted. Your order is confirmed.", False

    if session["state"] == 4:
        return "Your order is already confirmed. Thank you.", False

    if not session["cart"]["items"]:
        return f"{PRODUCT['name']} price is {PRODUCT['price']} {PRODUCT['currency']}.", False

    return (
        f"Current total: {session['cart']['total_price']} {PRODUCT['currency']}. "
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
        session_cache[user_id] = db_session
        return db_session

    history = await asyncio.to_thread(db_recent_history, user_id, 20)
    if not history:
        history = await fetch_recent_messages_from_graph(user_id, limit=10)

    rebuilt = rebuild_state_from_history(history or [])
    session_cache[user_id] = rebuilt
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
    attachments_count: int = 0,
    attachment_types: list[str] | None = None,
    attachment_urls: list[str] | None = None,
) -> tuple[str, bool]:
    attachment_types = [str(t).lower().strip() for t in (attachment_types or [])]
    attachment_urls = [str(u).strip() for u in (attachment_urls or []) if str(u).strip()]

    session = await ensure_user_session(user_id)
    previous_state = int(session["state"])

    intent_data = await detect_intent(message)

    payment_proof_detected = _detect_payment_proof_keyword(message, attachment_types, session["state"])
    if not payment_proof_detected and session["state"] == 3 and attachment_urls:
        payment_proof_detected = await analyze_payment_images(attachment_types, attachment_urls, message, session["state"])

    if payment_proof_detected:
        intent_data["intent"] = "payment"
        intent_data["payment_detected"] = True

    intent_data = apply_attachment_rules(
        intent_data,
        message,
        attachments_count,
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
        final_question_reply = await rewrite_reply("I'll confirm and let you know shortly", allow_upsell=False)
        return final_question_reply, False

    if price_argument:
        bargaining_capped = _register_bargain_and_is_capped(session)
        fixed_price_reply = (
            f"I totally understand apu but price fixed at {PRODUCT['price']} {PRODUCT['currency']}. "
            "Ami best quality maintain kortesi, tai price change kora possible na."
        )
        if bargaining_capped:
            fixed_price_reply = (
                f"Apu bujhte parchi, price fixed {PRODUCT['price']} {PRODUCT['currency']} and eta ar change kora possible na. "
                "Chaile ami order ta confirm kore dei now."
            )
        final_price_reply = await rewrite_reply(fixed_price_reply, allow_upsell=False)
        await asyncio.to_thread(db_save_session, user_id, session)
        return final_price_reply, False

    reply, allow_upsell = handle_message(
        user_id,
        intent_data,
        session=session,
        payment_proof_detected=payment_proof_detected,
    )

    if intent == "unknown":
        notify_owner_doubt(user_id, message)

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

    final_reply = await rewrite_reply(reply, allow_upsell)

    await asyncio.to_thread(db_save_session, user_id, session)
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
                        "message": text,
                        "attachments_count": attachments_count,
                        "attachment_types": attachment_types,
                        "attachment_urls": attachment_urls,
                    }
                )

        for change in entry.get("changes", []):
            value = change.get("value", {})
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
                            "message": text,
                            "attachments_count": attachments_count,
                            "attachment_types": attachment_types,
                            "attachment_urls": attachment_urls,
                        }
                    )

    return events


async def process_event(event: dict[str, Any]) -> None:
    user_id = event["user_id"]
    message = event["message"]
    attachments_count = int(event.get("attachments_count", 0))
    attachment_types = [str(t).lower() for t in (event.get("attachment_types") or [])]
    attachment_urls = [str(u) for u in (event.get("attachment_urls") or []) if str(u).strip()]

    await append_history(user_id, message, attachments_count, attachment_types, attachment_urls)
    final_reply, should_send = await process_message(
        user_id,
        message,
        attachments_count=attachments_count,
        attachment_types=attachment_types,
        attachment_urls=attachment_urls,
    )
    if should_send:
        await send_message(user_id, final_reply)


async def schedule_event_processing(event: dict[str, Any]) -> None:
    await process_event(event)


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
async def webhook(request: Request, background_tasks: BackgroundTasks) -> dict[str, Any]:
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_meta_signature(raw_body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}") from exc

    events = _extract_webhook_events(payload)
    for event in events:
        background_tasks.add_task(schedule_event_processing, event)

    return {"status": "ok", "queued": len(events)}


@app.post("/test")
async def test_endpoint(body: TestRequest) -> dict[str, str]:
    await append_history(body.user_id, body.message, body.attachments_count, body.attachment_types, body.attachment_urls)
    reply, _ = await process_message(
        body.user_id,
        body.message,
        attachments_count=body.attachments_count,
        attachment_types=body.attachment_types,
        attachment_urls=body.attachment_urls,
    )
    return {"reply": reply}


@app.get("/")
def health() -> dict[str, str]:
    return {"status": "running"}
