# Local Testing Guide for EllenAI Bot

## Quick Start

### Step 1: Set Owner IDs (Required for Owner Alert Tests)
Edit `.env` and add your test owner IDs:
```
OWNER_DM_MESSENGER_ID=your_messenger_id
OWNER_DM_INSTAGRAM_ID=your_instagram_id
```

### Step 2: Start the Bot
```powershell
python main.py
```
Wait for message: `Uvicorn running on http://0.0.0.0:8000`

### Step 3: Run Local Tests in Another Terminal
```powershell
Set-Location e:\Startupt\EllenAI
python test_webhook.py
```
The script will guide you through each test interactively.
It now uses `POST /test`, so local development does not depend on Meta webhook signatures.

### Step 4: Test Real Meta Delivery Separately
- Use Messenger or Instagram to send a real message to the deployed bot.
- Watch Railway logs for `WEBHOOK POST received` lines.

---

## What Gets Tested

| Test | Purpose | Expected Result |
|------|---------|-----------------|
| Text Search - Messenger | Find products by keyword | Returns nose ring options with Facebook links |
| Text Search - Instagram | Find products by keyword | Returns nose ring options with Instagram links |
| Price Query | Get price of specific product | Shows price + links |
| Image Inquiry | Price check with image | Identifies product + shows price |
| Unmatched Query | Catch unknown requests | → **OWNER ALERT** sent to DM |
| Order Confirmation | Complete purchase | → **OWNER ALERT** sent to DM |

---

## What to Check

### ✓ Bot Responses
- Open browser: http://localhost:8000/docs (Swagger UI)
- Each test will print response status + content in terminal

### ✓ Owner Alerts
After running tests, check:
1. **Messenger DM** - Should have alert messages for unmatched query + confirmed order
2. **Instagram DM** - Same alerts if ID configured

### ✓ Link Preferences
- Messenger tests → Should return Facebook links
- Instagram tests → Should return Instagram links

---

## Environment Variables (For Testing)

Your `.env` file needs these for full testing:
```
OPENAI_API_KEY=sk-...
PAGE_ACCESS_TOKEN=EAAR...
PAGE_ID=717918618079380
VERIFY_TOKEN=ANY_STRING
APP_SECRET=...
BKASH_NUMBER=01942776220
ADVANCE_PERCENT=0.60
MIN_ORDER_TOTAL=600
OWNER_DM_MESSENGER_ID=123456789  ← Your test owner ID
OWNER_DM_INSTAGRAM_ID=987654321   ← Your test owner ID
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Connection refused | Bot not running. Start with `python main.py` or `uvicorn main:app --host 0.0.0.0 --port 8000` |
| No owner alerts | Owner IDs not set in `.env` |
| Wrong links returned | Platform detection issue - check source field |
| Product not found | Keyword doesn't match catalog |

---

## Next: Deploy to Railway

Once local tests pass:
1. Push code to GitHub
2. Connect Railway to repo
3. Add `OWNER_DM_*` IDs to Railway environment variables
4. Deploy and test with real Messenger/Instagram
