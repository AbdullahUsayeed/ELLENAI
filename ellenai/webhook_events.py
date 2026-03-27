from __future__ import annotations

import hashlib
import hmac
from typing import Any


def verify_meta_signature(
    raw_body: bytes,
    signature_header: str | None,
    app_secret: str,
    allow_insecure: bool = False,
) -> bool:
    if not app_secret:
        return allow_insecure

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
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
        for candidate in candidates:
            value = str(candidate).strip() if candidate else ""
            if value and value.startswith("http"):
                urls.append(value)
    return urls


def extract_webhook_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for entry in payload.get("entry", []):
        for msg_event in entry.get("messaging", []):
            sender = msg_event.get("sender", {})
            message_obj = msg_event.get("message", {})

            # Ignore echoes of messages sent by the page itself.
            if message_obj.get("is_echo"):
                continue

            user_id = str(sender.get("id", "")).strip()
            text = str(message_obj.get("text", "")).strip()
            attachments = message_obj.get("attachments", []) or []
            attachments_count = _count_supported_attachments(attachments)
            attachment_types = _extract_attachment_types(attachments)
            attachment_urls = _extract_attachment_urls(attachments)

            if user_id and (text or attachments_count > 0):
                events.append(
                    {
                        "external_event_id": str(message_obj.get("mid") or "").strip() or None,
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
                            "external_event_id": str(msg.get("id") or "").strip() or None,
                            "user_id": user_id,
                            "source": source,
                            "message": text,
                            "attachments_count": attachments_count,
                            "attachment_types": attachment_types,
                            "attachment_urls": attachment_urls,
                        }
                    )

    return events
