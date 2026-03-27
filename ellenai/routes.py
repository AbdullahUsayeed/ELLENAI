from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field


class TestRequest(BaseModel):
    user_id: str
    message: str
    source: str = "unknown"
    attachments_count: int = 0
    attachment_types: list[str] = Field(default_factory=list)
    attachment_urls: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class RouteDeps:
    verify_token: str
    admin_token: str
    products_file_path: Path
    logger: logging.Logger
    verify_signature: Callable[[bytes, str | None], bool]
    extract_events: Callable[[dict[str, Any]], list[dict[str, Any]]]
    allow_webhook_batch: Callable[[int], Awaitable[bool]]
    insert_event: Callable[[dict[str, Any]], int]
    spawn_processing_by_ids: Callable[[list[int]], None]
    append_history: Callable[[str, str, int, list[str], list[str]], Awaitable[None]]
    process_message: Callable[[str, str, str, int, list[str], list[str]], Awaitable[tuple[str, bool]]]
    reload_products: Callable[[], None]
    products_loaded: Callable[[], int]


def build_router(deps: RouteDeps) -> APIRouter:
    router = APIRouter()

    @router.get("/webhook", response_class=PlainTextResponse)
    def verify_webhook(
        hub_mode: str | None = Query(default=None, alias="hub.mode"),
        hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
        hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    ) -> str:
        if hub_mode == "subscribe" and hub_verify_token == deps.verify_token and hub_challenge:
            return hub_challenge
        raise HTTPException(status_code=403, detail="Verification failed")

    @router.post("/webhook")
    async def webhook(request: Request) -> dict[str, Any]:
        raw_body = await request.body()
        signature = request.headers.get("X-Hub-Signature-256")
        deps.logger.info(
            "WEBHOOK POST received content_length=%s signature_present=%s",
            len(raw_body),
            bool(signature),
        )
        if not deps.verify_signature(raw_body, signature):
            deps.logger.warning("WEBHOOK POST rejected invalid signature")
            raise HTTPException(status_code=403, detail="Invalid signature")

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}") from exc

        events = deps.extract_events(payload)
        deps.logger.info("WEBHOOK POST parsed events=%s object=%s", len(events), payload.get("object"))

        if not await deps.allow_webhook_batch(len(events)):
            deps.logger.warning("WEBHOOK POST rate limited events=%s", len(events))
            raise HTTPException(status_code=429, detail="Webhook rate limit exceeded")

        event_ids: list[int] = []
        duplicate_count = 0
        for event in events:
            stored_id = await asyncio.to_thread(deps.insert_event, event)
            if stored_id > 0:
                event_ids.append(stored_id)
            else:
                duplicate_count += 1

        if event_ids:
            deps.spawn_processing_by_ids(event_ids)

        deps.logger.info("WEBHOOK POST queued stored=%s duplicates=%s", len(event_ids), duplicate_count)
        return {"status": "ok", "queued": len(events), "stored": len(event_ids)}

    @router.post("/test")
    async def test_endpoint(body: TestRequest) -> dict[str, str]:
        await deps.append_history(
            body.user_id,
            body.message,
            body.attachments_count,
            body.attachment_types,
            body.attachment_urls,
        )
        reply, _ = await deps.process_message(
            body.user_id,
            body.message,
            body.source,
            body.attachments_count,
            body.attachment_types,
            body.attachment_urls,
        )
        return {"reply": reply}

    @router.post("/admin/reload-products")
    async def admin_reload_products(request: Request) -> dict[str, Any]:
        if not deps.admin_token:
            raise HTTPException(status_code=503, detail="Admin endpoint disabled: set ADMIN_TOKEN")

        provided_token = request.headers.get("X-Admin-Token", "")
        if provided_token != deps.admin_token:
            raise HTTPException(status_code=403, detail="Invalid admin token")

        await asyncio.to_thread(deps.reload_products)
        return {
            "status": "ok",
            "products_loaded": deps.products_loaded(),
            "products_file": str(deps.products_file_path),
        }

    @router.get("/")
    def health() -> dict[str, str]:
        return {"status": "running"}

    return router
