#!/usr/bin/env python3
"""
Local test script for EllenAI bot.
Runs against POST /test so local development does not depend on Meta webhook signatures.
"""

from __future__ import annotations

import json
from datetime import datetime

import requests

BASE_URL = "http://localhost:8000"
TEST_URL = f"{BASE_URL}/test"

MESSENGER_SENDER_ID = "12345"
INSTAGRAM_SENDER_ID = "67890"


def log_test(name: str, method: str, data: dict[str, object] | None = None) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{timestamp}] TEST: {name}")
    print(f"  Method: {method}")
    if data:
        print(f"  Data: {json.dumps(data, indent=2)}")


def send_test(payload: dict[str, object]):
    try:
        response = requests.post(TEST_URL, json=payload, timeout=10)
        print(f"  Status: {response.status_code}")
        if response.text:
            try:
                print(f"  Response: {json.dumps(response.json(), indent=2)}")
            except (ValueError, json.JSONDecodeError):
                print(f"  Response: {response.text}")
        return response
    except requests.RequestException as exc:
        print(f"  Error: {exc}")
        return None


def test_text_search_messenger():
    payload = {
        "user_id": MESSENGER_SENDER_ID,
        "source": "messenger",
        "message": "Nosepin collection gulo ektu dekhan",
    }
    log_test("Text Search - Messenger", "POST", payload)
    return send_test(payload)


def test_text_search_instagram():
    payload = {
        "user_id": INSTAGRAM_SENDER_ID,
        "source": "instagram",
        "message": "Flower earring price koto?",
    }
    log_test("Text Search - Instagram", "POST", payload)
    return send_test(payload)


def test_price_query():
    payload = {
        "user_id": MESSENGER_SENDER_ID,
        "source": "messenger",
        "message": "Single Flower Per Piece price?",
    }
    log_test("Price Query", "POST", payload)
    return send_test(payload)


def test_image_inquiry():
    payload = {
        "user_id": MESSENGER_SENDER_ID,
        "source": "messenger",
        "message": "ei ta ki? price koto?",
        "attachments_count": 1,
        "attachment_types": ["image"],
        "attachment_urls": ["https://example.com/image.jpg"],
    }
    log_test("Image Inquiry", "POST", payload)
    return send_test(payload)


def test_unmatched_query():
    payload = {
        "user_id": MESSENGER_SENDER_ID,
        "source": "messenger",
        "message": "something that doesn't match any product",
    }
    log_test("Unmatched Query", "POST", payload)
    return send_test(payload)


def test_order_confirmation():
    payload = {
        "user_id": MESSENGER_SENDER_ID,
        "source": "messenger",
        "message": "confirm",
    }
    log_test("Order Confirmation", "POST", payload)
    return send_test(payload)


def main() -> None:
    print("=" * 70)
    print("EllenAI Local Test Suite")
    print("=" * 70)
    print(f"\nBase URL: {BASE_URL}")
    print(f"Test URL: {TEST_URL}")
    print("\nMake sure bot is running: python main.py")
    print("\n" + "=" * 70)

    tests = [
        ("Text Search - Messenger", test_text_search_messenger),
        ("Text Search - Instagram", test_text_search_instagram),
        ("Price Query", test_price_query),
        ("Image Inquiry", test_image_inquiry),
        ("Unmatched Query", test_unmatched_query),
        ("Order Confirmation", test_order_confirmation),
    ]

    results = []
    for index, (name, test_func) in enumerate(tests, start=1):
        try:
            response = test_func()
            results.append((name, response.status_code if response else None))
        except Exception as exc:  # pragma: no cover - manual helper script
            results.append((name, f"ERROR: {exc}"))

        if index < len(tests):
            input("\nPress ENTER to continue to next test...")

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    for name, status in results:
        status_str = f"[OK] {status}" if isinstance(status, int) and 200 <= status < 300 else f"[FAIL] {status}"
        print(f"{name:40s} {status_str}")

    print("\nThis script validates local bot behavior through /test.")
    print("Use real Messenger/Instagram messages plus Railway logs to validate Meta webhook delivery.")


if __name__ == "__main__":
    main()
