# EllenAI Instagram/Messenger Sales Assistant MVP

Minimal FastAPI backend that:

- Receives messages from Meta webhook
- Runs intent extraction via OpenAI
- Applies strict Python state/cart/order logic
- Rewrites replies in Banglish shop tone
- Sends final reply back via Graph API

## Features

- Intent extraction: `detect_intent(message)`
- Reply style rewrite: `rewrite_reply(text, allow_upsell=False, tone="default")`
- State machine: new -> cart/price -> location -> payment -> confirmed
- Cart with quantity, per-item color, and deterministic total pricing
- Question handling with owner notification split from order flow
- Owner notification for confirmed orders
- Webhook verification and message handling

## Endpoints

- `GET /` health check
- `POST /test` local simulation endpoint
- `GET /webhook` Meta verification endpoint
- `POST /webhook` Meta message event endpoint
- `POST /admin/reload-products` reload `products.json` without restart (requires `X-Admin-Token`)

## Install

```powershell
pip install -r requirements.txt
```

## Configure Environment Variables

Copy `.env.example` values into your deployment environment (or set locally in shell):

- `OPENAI_API_KEY`
- `PAGE_ACCESS_TOKEN`
- `PAGE_ID`
- `VERIFY_TOKEN`
- `APP_SECRET`
- `PRODUCTS_FILE_PATH` (optional, default `products.json`)
- `ADMIN_TOKEN` (required to enable admin reload endpoint)

Optional reliability tuning knobs (recommended for production-like testing):

- `OPENAI_RETRY_ATTEMPTS` (default `3`)
- `OPENAI_RETRY_MIN_SECONDS` (default `1`)
- `OPENAI_RETRY_MAX_SECONDS` (default `8`)
- `INTENT_CACHE_MAX_SIZE` (default `10000`)
- `REWRITE_CACHE_MAX_SIZE` (default `10000`)
- `SESSION_CACHE_MAX_SIZE` (default `5000`)
- `USER_RATE_LIMIT_COUNT` (default `8`)
- `USER_RATE_LIMIT_WINDOW_SECONDS` (default `20`)
- `WEBHOOK_RATE_LIMIT_COUNT` (default `60`)
- `WEBHOOK_RATE_LIMIT_WINDOW_SECONDS` (default `10`)

Local PowerShell example:

```powershell
$env:OPENAI_API_KEY="your_openai_key"
$env:PAGE_ACCESS_TOKEN="your_page_access_token"
$env:PAGE_ID="your_page_id"
$env:VERIFY_TOKEN="your_verify_token"
$env:APP_SECRET="your_meta_app_secret"
$env:PRODUCTS_FILE_PATH="products.json"
$env:ADMIN_TOKEN="your_strong_admin_token"
```

## Product Catalog From JSON

Create a `products.json` file (or set `PRODUCTS_FILE_PATH`) using normalized post URLs as keys:

```json
{
	"instagram.com/p/ABC123": {
		"name": "Oversized Hoodie",
		"price": 2500,
		"currency": "BDT",
		"delivery": "3-5 days"
	},
	"facebook.com/posts/XYZ456": {
		"name": "Silver Earrings",
		"price": 1200,
		"currency": "BDT",
		"delivery": "2-4 days"
	}
}
```

Full links are normalized internally by removing protocol (`http://`, `https://`), `www.`, query params, and trailing slash.
Canonical examples:

- `https://www.instagram.com/p/ABC123/?igsh=xyz` -> `instagram.com/p/ABC123`
- `https://www.facebook.com/manifesto.ei/posts/123456789` -> `facebook.com/posts/123456789`

When a shared attachment URL normalizes to a key in `products.json`, that product is used automatically.
If a shared URL is not mapped, bot replies: `This item is not available right now apu 😢`.

Use the simple script `manage_products.py` to add/update products quickly:

```powershell
python manage_products.py
```

Or call directly in Python:

```python
from product_store import add_product

add_product(
    full_url="https://www.instagram.com/p/ABC123/?igsh=xyz",
    name="Silver Earrings",
    price=1200,
    currency="BDT",
    delivery="2-4 days",
)
```

Reload products without restart:

```powershell
curl -X POST http://127.0.0.1:8000/admin/reload-products -H "X-Admin-Token: your_strong_admin_token"
```

## Run Locally

```powershell
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Test Request

```powershell
curl -X POST http://127.0.0.1:8000/test -H "Content-Type: application/json" -d '{"user_id":"123","message":"I want 2 black hoodies"}'
```

## Meta Setup Notes

Set these environment variables in your host:

- `PAGE_ACCESS_TOKEN`
- `PAGE_ID`
- `VERIFY_TOKEN`
- `APP_SECRET`

Then configure your Meta webhook callback URL to:

- `https://<your-domain>/webhook`

and use the same `VERIFY_TOKEN` during webhook verification.

`POST /webhook` also validates `X-Hub-Signature-256` using HMAC SHA256 and `APP_SECRET`.

## Attachment Testing

`POST /test` accepts:

```json
{
	"user_id": "123",
	"message": "this one",
	"attachments_count": 2
}
```

Each attachment is treated as one product item when applicable.

Use attachment types to simulate screenshot proof:

```json
{
  "user_id": "123",
  "message": "",
  "attachments_count": 1,
  "attachment_types": ["image"]
}
```

Test product URL detection with `attachment_urls`:

```json
{
	"user_id": "123",
	"message": "",
	"attachment_urls": ["https://www.instagram.com/p/ABC123/?igsh=xyz"]
}
```

## Payment Proof Behavior

- In payment stage (`state = 3`), bot asks for screenshot proof before final confirmation.
- Payment text only (no image) does not lock order.
- Image-only message in payment stage is accepted as screenshot proof.
- Image + non-payment text does not auto-confirm.

## Final Integration Checklist

1. Set real environment variable values:
	- `OPENAI_API_KEY`
	- `PAGE_ACCESS_TOKEN`
	- `PAGE_ID`
	- `VERIFY_TOKEN`
	- `APP_SECRET`
2. Deploy the app (Railway or Render).
3. Confirm health endpoint:
	- `GET https://<your-domain>/`
4. In Meta App Dashboard:
	- Add webhook callback URL: `https://<your-domain>/webhook`
	- Add verify token: same value as `VERIFY_TOKEN`
	- Subscribe the page to messaging events.
5. Send a DM from test account and verify:
	- Replies arrive with ~5 second delay.
	- Order summary appears before payment.
	- Payment is confirmed only after screenshot proof.

## Deploy on Railway

1. Push project to GitHub.
2. Create new Railway project from repo.
3. Set Start Command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

4. Ensure runtime installs from `requirements.txt`.
5. Deploy and copy generated public URL.

## Deploy on Render

1. Create a new Web Service from repo.
2. Build Command:

```bash
pip install -r requirements.txt
```

3. Start Command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

4. Deploy and copy generated public URL.

## Operational Notes

- `fetch_recent_messages_from_graph()` is implemented and only used on session creation to rebuild state.
- Graph API limits/rate limits apply; avoid forcing rebuild on every webhook call.
- Secrets are now read from environment variables; do not hardcode them in source files.
- If any key was previously exposed in code history, rotate it immediately.
- Incoming webhook events are persisted before acknowledgment, then processed from SQLite-backed queue records.
- App startup attempts to recover pending/retry events automatically.
- Session saves use version-checked updates to reduce stale overwrite risks.
