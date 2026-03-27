#!/usr/bin/env python3
"""
Test script to simulate webhook events for EllenAI bot.
Run this after starting the bot with: python main.py
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"
WEBHOOK_URL = f"{BASE_URL}/webhook"

# Test configurations
MESSENGER_SENDER_ID = "12345"  # Simulated customer ID
INSTAGRAM_SENDER_ID = "67890"   # Simulated Instagram user ID
OWNER_MESSENGER_ID = "100000000000000"  # Your owner ID (will receive alerts)

def log_test(name, method, data=None):
    """Print test info"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{timestamp}] TEST: {name}")
    print(f"  Method: {method}")
    if data:
        print(f"  Data: {json.dumps(data, indent=2)}")

def send_webhook(event_data, platform="messenger"):
    """Send a webhook event to the bot"""
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature": "sha1=test"  # Mock signature
    }
    
    try:
        response = requests.post(WEBHOOK_URL, json=event_data, headers=headers, timeout=5)
        print(f"  Status: {response.status_code}")
        if response.text:
            try:
                print(f"  Response: {json.dumps(response.json(), indent=2)}")
            except (ValueError, json.JSONDecodeError):
                print(f"  Response: {response.text}")
        return response
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None

# ============================================
# TEST 1: Text Product Search (Messenger)
# ============================================
def test_text_search_messenger():
    event_data = {
        "object": "page",
        "entry": [
            {
                "id": "123456789",
                "time": int(datetime.now().timestamp() * 1000),
                "messaging": [
                    {
                        "sender": {"id": MESSENGER_SENDER_ID},
                        "recipient": {"id": "12345"},
                        "timestamp": int(datetime.now().timestamp() * 1000),
                        "message": {
                            "mid": "msg_1",
                            "text": "Nosepin collection gulo ektu dekhan"
                        }
                    }
                ]
            }
        ]
    }
    log_test("Text Search - Nose Ring Products (Messenger)", "POST", event_data)
    return send_webhook(event_data)

# ============================================
# TEST 2: Text Product Search (Instagram)
# ============================================
def test_text_search_instagram():
    event_data = {
        "object": "instagram",
        "entry": [
            {
                "id": "987654321",
                "time": int(datetime.now().timestamp() * 1000),
                "messaging": [
                    {
                        "sender": {"id": INSTAGRAM_SENDER_ID},
                        "recipient": {"id": "12345"},
                        "timestamp": int(datetime.now().timestamp() * 1000),
                        "message": {
                            "mid": "msg_2",
                            "text": "Flower earring price koto?"
                        }
                    }
                ]
            }
        ]
    }
    log_test("Text Search - Flower Earrings (Instagram)", "POST", event_data)
    return send_webhook(event_data)

# ============================================
# TEST 3: Add to Cart (Price Query)
# ============================================
def test_price_query():
    event_data = {
        "object": "page",
        "entry": [
            {
                "id": "123456789",
                "time": int(datetime.now().timestamp() * 1000),
                "messaging": [
                    {
                        "sender": {"id": MESSENGER_SENDER_ID},
                        "recipient": {"id": "12345"},
                        "timestamp": int(datetime.now().timestamp() * 1000),
                        "message": {
                            "mid": "msg_3",
                            "text": "Single Flower Per Piece price?"
                        }
                    }
                ]
            }
        ]
    }
    log_test("Price Query - Add to Cart", "POST", event_data)
    return send_webhook(event_data)

# ============================================
# TEST 4: Order Confirmation (Triggers Owner Alert)
# ============================================
def test_order_confirmation():
    event_data = {
        "object": "page",
        "entry": [
            {
                "id": "123456789",
                "time": int(datetime.now().timestamp() * 1000),
                "messaging": [
                    {
                        "sender": {"id": MESSENGER_SENDER_ID},
                        "recipient": {"id": "12345"},
                        "timestamp": int(datetime.now().timestamp() * 1000),
                        "message": {
                            "mid": "msg_4",
                            "text": "confirm"
                        }
                    }
                ]
            }
        ]
    }
    log_test("Order Confirmation (Should trigger OWNER ALERT)", "POST", event_data)
    return send_webhook(event_data)

# ============================================
# TEST 5: Image Inquiry
# ============================================
def test_image_inquiry():
    event_data = {
        "object": "page",
        "entry": [
            {
                "id": "123456789",
                "time": int(datetime.now().timestamp() * 1000),
                "messaging": [
                    {
                        "sender": {"id": MESSENGER_SENDER_ID},
                        "recipient": {"id": "12345"},
                        "timestamp": int(datetime.now().timestamp() * 1000),
                        "message": {
                            "mid": "msg_5",
                            "text": "ei ta ki? price koto?",
                            "attachments": [
                                {
                                    "type": "image",
                                    "payload": {
                                        "url": "https://example.com/image.jpg"
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    log_test("Image Inquiry - Product Price Check", "POST", event_data)
    return send_webhook(event_data)

# ============================================
# TEST 6: Unmatched Query (Should trigger OWNER ALERT)
# ============================================
def test_unmatched_query():
    event_data = {
        "object": "page",
        "entry": [
            {
                "id": "123456789",
                "time": int(datetime.now().timestamp() * 1000),
                "messaging": [
                    {
                        "sender": {"id": MESSENGER_SENDER_ID},
                        "recipient": {"id": "12345"},
                        "timestamp": int(datetime.now().timestamp() * 1000),
                        "message": {
                            "mid": "msg_6",
                            "text": "something that doesn't match any product"
                        }
                    }
                ]
            }
        ]
    }
    log_test("Unmatched Query (Should trigger OWNER ALERT)", "POST", event_data)
    return send_webhook(event_data)

# ============================================
# MAIN TEST RUNNER
# ============================================
def main():
    print("=" * 70)
    print("EllenAI Webhook Test Suite")
    print("=" * 70)
    print(f"\nBase URL: {BASE_URL}")
    print(f"Webhook URL: {WEBHOOK_URL}")
    print("\nMake sure bot is running: python main.py")
    print("\n" + "=" * 70)
    
    tests = [
        ("Text Search - Messenger", test_text_search_messenger),
        ("Text Search - Instagram", test_text_search_instagram),
        ("Price Query", test_price_query),
        ("Image Inquiry", test_image_inquiry),
        ("Unmatched Query (Owner Alert)", test_unmatched_query),
        ("Order Confirmation (Owner Alert)", test_order_confirmation),
    ]
    
    results = []
    for i, (name, test_func) in enumerate(tests, 1):
        try:
            response = test_func()
            results.append((name, response.status_code if response else None))
        except Exception as e:
            results.append((name, f"ERROR: {e}"))
        
        if i < len(tests):
            input("\nPress ENTER to continue to next test...")
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    for name, status in results:
        status_str = f"✓ {status}" if isinstance(status, int) and 200 <= status < 300 else f"✗ {status}"
        print(f"{name:40s} {status_str}")
    
    print("\n" + "=" * 70)
    print("OWNER ALERT CHECKS:")
    print("=" * 70)
    print("After running tests, check:")
    print("1. Owner DM on Messenger (ID: {})".format(OWNER_MESSENGER_ID))
    print("2. Owner DM on Instagram")
    print("   - Should receive alerts for: 'Unmatched Query' test + 'Order Confirmation' test")
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
