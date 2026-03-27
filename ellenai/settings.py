from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    page_access_token: str
    page_id: str
    verify_token: str
    app_secret: str
    admin_token: str
    state_db_path: Path
    message_send_delay_seconds: float
    enable_reply_rewrite: bool
    rewrite_cache_ttl_seconds: int
    intent_cache_ttl_seconds: int
    intent_cache_max_size: int
    rewrite_cache_max_size: int
    session_cache_max_size: int
    openai_retry_attempts: int
    openai_retry_min_seconds: float
    openai_retry_max_seconds: float
    user_rate_limit_count: int
    user_rate_limit_window_seconds: int
    webhook_rate_limit_count: int
    webhook_rate_limit_window_seconds: int
    products_file_path: Path
    bkash_number: str
    advance_percent: float
    min_order_total: int
    owner_dm_id: str
    owner_dm_messenger_id: str
    owner_dm_instagram_id: str
    burst_coalesce_window_ms: int
    burst_min_messages_to_trigger: int


def load_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        page_access_token=os.getenv("PAGE_ACCESS_TOKEN", ""),
        page_id=os.getenv("PAGE_ID", ""),
        verify_token=os.getenv("VERIFY_TOKEN", "ANY_STRING"),
        app_secret=os.getenv("APP_SECRET", ""),
        admin_token=os.getenv("ADMIN_TOKEN", ""),
        state_db_path=Path(os.getenv("STATE_DB_PATH", "ellenai_state.db")),
        message_send_delay_seconds=float(os.getenv("MESSAGE_SEND_DELAY_SECONDS", "5")),
        enable_reply_rewrite=os.getenv("ENABLE_REPLY_REWRITE", "1") == "1",
        rewrite_cache_ttl_seconds=int(os.getenv("REWRITE_CACHE_TTL_SECONDS", "900")),
        intent_cache_ttl_seconds=int(os.getenv("INTENT_CACHE_TTL_SECONDS", "300")),
        intent_cache_max_size=int(os.getenv("INTENT_CACHE_MAX_SIZE", "10000")),
        rewrite_cache_max_size=int(os.getenv("REWRITE_CACHE_MAX_SIZE", "10000")),
        session_cache_max_size=int(os.getenv("SESSION_CACHE_MAX_SIZE", "5000")),
        openai_retry_attempts=int(os.getenv("OPENAI_RETRY_ATTEMPTS", "3")),
        openai_retry_min_seconds=float(os.getenv("OPENAI_RETRY_MIN_SECONDS", "1")),
        openai_retry_max_seconds=float(os.getenv("OPENAI_RETRY_MAX_SECONDS", "8")),
        user_rate_limit_count=int(os.getenv("USER_RATE_LIMIT_COUNT", "8")),
        user_rate_limit_window_seconds=int(os.getenv("USER_RATE_LIMIT_WINDOW_SECONDS", "20")),
        webhook_rate_limit_count=int(os.getenv("WEBHOOK_RATE_LIMIT_COUNT", "60")),
        webhook_rate_limit_window_seconds=int(os.getenv("WEBHOOK_RATE_LIMIT_WINDOW_SECONDS", "10")),
        products_file_path=Path(os.getenv("PRODUCTS_FILE_PATH", "products.json")),
        bkash_number=os.getenv("BKASH_NUMBER", "01942776220"),
        advance_percent=float(os.getenv("ADVANCE_PERCENT", "0.60")),
        min_order_total=int(os.getenv("MIN_ORDER_TOTAL", "600")),
        owner_dm_id=os.getenv("OWNER_DM_ID", ""),
        owner_dm_messenger_id=os.getenv("OWNER_DM_MESSENGER_ID", ""),
        owner_dm_instagram_id=os.getenv("OWNER_DM_INSTAGRAM_ID", ""),
        burst_coalesce_window_ms=int(os.getenv("BURST_COALESCE_WINDOW_MS", "2000")),
        burst_min_messages_to_trigger=int(os.getenv("BURST_MIN_MESSAGES_TO_TRIGGER", "2")),
    )
