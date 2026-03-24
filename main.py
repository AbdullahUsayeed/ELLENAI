from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from typing import Any

import requests
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from openai import OpenAI
from pydantic import BaseModel, Field


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN", "")
PAGE_ID = os.getenv("PAGE_ID", "")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "ANY_STRING")
APP_SECRET = os.getenv("APP_SECRET", "")

PRODUCT = {
    "name": "Oversized Hoodie",
    "price": 2500,
    "currency": "BDT",
    "delivery": "3-5 days",
}

ORNAMENT_COMPLIMENTS = {
    "necklace": "eta porle apnar look ta onek elegant and classy dekhabe",
    "earrings": "eta apnar face-cut ke onek beautifully highlight korbe",
    "ring": "eta apnar hand look ke super premium feel dibe",
    "bracelet": "eta apnar outfit er sathe onek chic vibe dibe",
    "anklet": "eta apnar style e onek soft and graceful touch add korbe",
}

BARGAIN_WINDOW_SECONDS = 120
BARGAIN_CAP_AFTER_COUNT = 3

STYLE_PROMPT = """
You are a friendly Instagram shop girl.

Tone:

* Slightly girly
* Bangla + English mix (Banglish)
* Casual, fun
* Use emojis (😍😊✨)

Rules:

* Short replies (1-2 lines)
* Natural and human
* Never change price or totals
"""

STYLE_EXAMPLES = """
apu eta onek cute, ami nijeyo use kortesi 😍
price 2500, quality onek bhalo trust me
delivery 3-5 days lagbe apu 😊
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

# In-memory session store for MVP.
user_sessions: dict[str, dict[str, Any]] = {}
user_message_history: dict[str, list[dict[str, Any]]] = {}


class TestRequest(BaseModel):
    user_id: str
    message: str
    attachments_count: int = 0
    attachment_types: list[str] = Field(default_factory=list)


def _new_session() -> dict[str, Any]:
    return {
        "state": 0,
        "location": None,
        "upsell_used": False,
        "bargain_timestamps": [],
        "payment_proof_received": False,
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
    if color == "null" or color == "none":
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


def _extract_ornament_name(message: str) -> str | None:
    text = message.lower()
    names = ["necklace", "earrings", "ring", "bracelet", "anklet", "chain", "pendant"]
    for name in names:
        if re.search(rf"\b{re.escape(name)}\b", text):
            return name
    return None


def _is_price_argument(message: str) -> bool:
    text = message.lower()
    markers = [
        "kom", "less", "discount", "best price", "final price", "reduce", "dam kom", "too much", "expensive",
        "aro kom", "price ta koman", "can you lower", "nego", "negotiable",
    ]
    return any(m in text for m in markers)


def detect_intent(message: str) -> dict[str, Any]:
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
        return _normalize_intent(_fallback_detect(message))

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
        parsed = json.loads(response.choices[0].message.content or "{}")
        if parsed is None:
            return _normalize_intent(_fallback_detect(message))
        return _normalize_intent(parsed)
    except Exception:
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


def rewrite_reply(text: str, allow_upsell: bool = False, tone: str = "default") -> str:
    del tone

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

    if client is None:
        return text

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
        return rewritten if rewritten else text
    except Exception:
        return text


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
    return "Oops apu 😅 ami buste parini, kindly bolben ki niben?"


def _super_confused_reply() -> str:
    return "Lemme confirm from Ellen and get back to you right away apu 😊"


def _append_history(user_id: str, message: str, attachments_count: int, attachment_types: list[str] | None = None) -> None:
    history = user_message_history.setdefault(user_id, [])
    history.append(
        {
            "text": message,
            "attachments_count": max(0, attachments_count),
            "attachment_types": attachment_types or [],
        }
    )
    if len(history) > 20:
        del history[:-20]


def _detect_payment_proof(message: str, attachment_types: list[str], state: int) -> bool:
    if state != 3:
        return False

    normalized_types = {str(t).lower().strip() for t in attachment_types if str(t).strip()}
    has_image = "image" in normalized_types

    text = message.lower().strip()
    proof_words = ["paid", "payment", "trx", "bkash", "nagad", "rocket", "screenshot", "ss", "proof"]
    mentions_payment = any(w in text for w in proof_words)

    # Accept proof when an image is attached and either:
    # - text is empty (image-only screenshot), or
    # - payment-related text is present.
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
        "🚨 NEW ORDER\n"
        f"User: {user_id}\n"
        "Items:\n"
        f"{'\n'.join(item_lines)}\n"
        f"Total: {session['cart']['total_price']} {PRODUCT['currency']}\n"
        f"Location: {session.get('location') or 'Not provided'}\n"
        "Payment: CONFIRMED (recheck manually)\n"
        f"Delivery: {PRODUCT['delivery']}"
    )
    print(notification)


def notify_owner_doubt(user_id: str, text: str) -> None:
    notification = (
        "⚠️ CUSTOMER QUESTION\n"
        f"User: {user_id}\n"
        f"Message: {text}"
    )
    print(notification)


def handle_message(
    user_id: str,
    intent_data: dict[str, Any],
    session: dict[str, Any] | None = None,
    payment_proof_detected: bool = False,
) -> tuple[str, bool]:
    if session is None:
        session = user_sessions.setdefault(user_id, _new_session())

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
            reply += " Which color do you want? 😊"

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


def fetch_recent_messages_from_graph(user_id: str, limit: int = 10) -> list[dict[str, Any]]:
    if not PAGE_ACCESS_TOKEN or not PAGE_ID:
        return []

    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/conversations"
    params = {
        "access_token": PAGE_ACCESS_TOKEN,
        "fields": f"participants,messages.limit({max(1, limit)}){{id,from,message,text,created_time,attachments}}",
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code >= 400:
            print(f"[fetch_recent_messages_from_graph] Graph API error: {response.status_code} {response.text}")
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
                    "created_time": msg.get("created_time"),
                }
            )

        user_messages.sort(key=lambda m: str(m.get("created_time") or ""))
        return user_messages[-limit:]

    except Exception as exc:
        print(f"[fetch_recent_messages_from_graph] Exception: {exc}")
        return []


def rebuild_state_from_history(messages: list[dict[str, Any]]) -> dict[str, Any]:
    rebuilt = _new_session()
    if not messages:
        return rebuilt

    for entry in messages[-10:]:
        text = str(entry.get("text", "")).strip()
        attachments_count = int(entry.get("attachments_count", 0) or 0)
        attachment_types = [str(t).lower() for t in (entry.get("attachment_types") or [])]

        intent_data = detect_intent(text)
        payment_proof_detected = _detect_payment_proof(text, attachment_types, rebuilt["state"])
        if payment_proof_detected:
            intent_data["intent"] = "payment"
            intent_data["payment_detected"] = True

        intent_data = apply_attachment_rules(
            intent_data,
            text,
            attachments_count,
            current_state=rebuilt["state"],
            payment_proof_detected=payment_proof_detected,
        )

        if intent_data.get("is_question"):
            continue

        handle_message("rebuild", intent_data, session=rebuilt, payment_proof_detected=payment_proof_detected)

    return rebuilt


def ensure_user_session(user_id: str) -> dict[str, Any]:
    existing = user_sessions.get(user_id)
    if existing is not None:
        return existing

    history = user_message_history.get(user_id)
    if not history:
        history = fetch_recent_messages_from_graph(user_id, limit=10)

    rebuilt = rebuild_state_from_history(history or [])
    user_sessions[user_id] = rebuilt
    return rebuilt


def apply_attachment_rules(
    intent_data: dict[str, Any],
    message: str,
    attachments_count: int,
    current_state: int,
    payment_proof_detected: bool,
) -> dict[str, Any]:
    result = dict(intent_data)
    if attachments_count <= 0:
        return result

    text = message.strip().lower()
    base_qty = 0 if not text else int(result.get("quantity", 1))
    current_intent = str(result.get("intent", "unknown")).lower()

    # If attachment is sent without text, treat each attachment as a product add.
    if not text:
        # In payment stage, an image-only message is treated as screenshot proof.
        if current_state == 3 and payment_proof_detected:
            result["intent"] = "payment"
            result["payment_detected"] = True
            return result

        result["intent"] = "add_item"
        result["quantity"] = attachments_count
        return result

    # In payment stage, do not convert arbitrary attachments into new cart items.
    if current_state == 3 and not payment_proof_detected:
        return result

    # Keep explicit user intents (payment/location/question/order) when text is clear.
    if current_intent in {"payment", "location", "question", "order"}:
        result["attachment_items"] = attachments_count
        return result

    # Otherwise, attachment implies product add and should combine with detected quantity.
    result["intent"] = "add_item"
    result["quantity"] = max(attachments_count, base_qty + attachments_count if base_qty > 0 else attachments_count)
    return result


def process_message(
    user_id: str,
    message: str,
    attachments_count: int = 0,
    attachment_types: list[str] | None = None,
    auto_send: bool = False,
) -> str:
    attachment_types = [str(t).lower().strip() for t in (attachment_types or [])]
    session = ensure_user_session(user_id)

    # 1. Call AI intent detection.
    intent_data = detect_intent(message)
    payment_proof_detected = _detect_payment_proof(message, attachment_types, session["state"])
    if payment_proof_detected:
        intent_data["intent"] = "payment"
        intent_data["payment_detected"] = True

    intent_data = apply_attachment_rules(
        intent_data,
        message,
        attachments_count,
        current_state=session["state"],
        payment_proof_detected=payment_proof_detected,
    )

    price_argument = _is_price_argument(message)
    if price_argument:
        intent_data["intent"] = "price"
        intent_data["is_question"] = False

    # 2. Extract structured fields.
    intent = intent_data["intent"]
    quantity = intent_data["quantity"]
    color = intent_data["color"]
    location = intent_data["location"]
    payment_detected = intent_data["payment_detected"]
    is_question = intent_data["is_question"]
    _ = (intent, quantity, color, location)

    previous_state = session["state"]

    # 4. Early handling for doubts/questions.
    if is_question:
        notify_owner_doubt(user_id, message)
        final_question_reply = rewrite_reply("I'll confirm and let you know shortly 😊", allow_upsell=False)
        if auto_send:
            time.sleep(5)
            send_message(user_id, final_question_reply)
        return final_question_reply

    # Price bargaining should not modify cart/state.
    if price_argument:
        ornament_name = _extract_ornament_name(message)
        compliment = None
        if ornament_name and ornament_name in ORNAMENT_COMPLIMENTS:
            compliment = ORNAMENT_COMPLIMENTS[ornament_name]

        bargaining_capped = _register_bargain_and_is_capped(session)
        fixed_price_reply = (
            f"I totally understand apu 💛 but price fixed at {PRODUCT['price']} {PRODUCT['currency']}. "
            "Ami best quality maintain kortesi, tai price change kora possible na."
        )
        if bargaining_capped:
            fixed_price_reply = (
                f"Apu bujhte parchi 💛 price fixed {PRODUCT['price']} {PRODUCT['currency']} and eta ar change kora possible na. "
                "Chaile ami order ta confirm kore dei now."
            )
        if compliment:
            fixed_price_reply += f" Ar honestly {compliment}."

        final_price_reply = rewrite_reply(fixed_price_reply, allow_upsell=False)
        if auto_send:
            time.sleep(5)
            send_message(user_id, final_price_reply)
        return final_price_reply

    # 3. Backend logic from structured data.
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

    # 5. Notify owner when payment is detected in state 3.
    if payment_detected and payment_proof_detected and previous_state == 3:
        notify_owner_order(user_id, session)

    # 6. Rewrite reply for style.
    final_reply = rewrite_reply(reply, allow_upsell)

    # Optional send for webhook pipeline.
    if auto_send:
        time.sleep(5)
        send_message(user_id, final_reply)

    # 7. Return final text.
    return final_reply


def send_message(user_id: str, text: str) -> dict[str, Any]:
    url = f"https://graph.facebook.com/v18.0/{PAGE_ID}/messages"
    payload = {
        "recipient": {"id": user_id},
        "message": {"text": text},
    }
    params = {"access_token": PAGE_ACCESS_TOKEN}

    try:
        response = requests.post(url, params=params, json=payload, timeout=20)
        if response.status_code >= 400:
            print(f"[send_message] Graph API error for user {user_id}: {response.status_code} {response.text}")
            return {"ok": False, "status_code": response.status_code, "error": response.text}
        return {"ok": True, "data": response.json()}
    except Exception as exc:
        print(f"[send_message] Exception for user {user_id}: {exc}")
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

            if not user_id:
                continue

            if text or attachments_count > 0:
                events.append(
                    {
                        "user_id": user_id,
                        "message": text,
                        "attachments_count": attachments_count,
                        "attachment_types": attachment_types,
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
                if user_id and (text or attachments_count > 0):
                    events.append(
                        {
                            "user_id": user_id,
                            "message": text,
                            "attachments_count": attachments_count,
                            "attachment_types": attachment_types,
                        }
                    )

    return events


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
    if not verify_meta_signature(raw_body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}") from exc

    events = _extract_webhook_events(payload)

    processed = 0
    for event in events:
        user_id = event["user_id"]
        message = event["message"]
        attachments_count = int(event.get("attachments_count", 0))
        attachment_types = [str(t).lower() for t in (event.get("attachment_types") or [])]

        _append_history(user_id, message, attachments_count, attachment_types)
        process_message(
            user_id,
            message,
            attachments_count=attachments_count,
            attachment_types=attachment_types,
            auto_send=True,
        )
        processed += 1

    return {"status": "ok", "processed": processed}


@app.post("/test")
def test_endpoint(body: TestRequest) -> dict[str, str]:
    _append_history(body.user_id, body.message, body.attachments_count, body.attachment_types)
    time.sleep(5)
    reply = process_message(
        body.user_id,
        body.message,
        attachments_count=body.attachments_count,
        attachment_types=body.attachment_types,
        auto_send=False,
    )
    return {"reply": reply}


@app.get("/")
def health() -> dict[str, str]:
    return {"status": "running"}
