# EllenAI Deployment Guide

## Deployment Status
**✓ All systems ready for production**

## Quick Deployment (Railway.app)

### Step 1: Push to GitHub
```bash
cd e:\Startupt\EllenAI
git add .
git commit -m "Ready for production deployment"
git push origin main
```

### Step 2: Deploy to Railway
1. Go to [railway.app](https://railway.app)
2. Sign up / Log in with GitHub
3. Click **New Project**
4. Select **Deploy from GitHub repo** → Choose your EllenAI repo
5. Railway auto-detects the Procfile and deploys

### Step 3: Configure Environment Variables
In Railway dashboard → Variables → Add:

**Required (Critical):**
```
OPENAI_API_KEY=sk-...your-key...
PAGE_ACCESS_TOKEN=EAAR6...your-token...
PAGE_ID=your-page-id
APP_SECRET=your-meta-app-secret
ADMIN_TOKEN=generate-strong-random-string
```

**Bot Configuration (Optional - defaults provided):**
```
BKASH_NUMBER=01942776220
ADVANCE_PERCENT=0.60
MIN_ORDER_TOTAL=600
OWNER_DM_MESSENGER_ID=your-messenger-user-id
OWNER_DM_INSTAGRAM_ID=your-instagram-user-id
```

**Performance Tuning (Optional):**
```
OPENAI_RETRY_ATTEMPTS=3
USER_RATE_LIMIT_COUNT=8
WEBHOOK_RATE_LIMIT_COUNT=60
```

### Step 4: Configure Messenger Webhook
1. Go to Meta App Dashboard → Your App → Messenger
2. **Webhook URL**: `https://your-railway-url/webhook`
   - Get URL from Railway → Deployments → Domain
3. **Verify Token**: Match your `VERIFY_TOKEN` value (default: `ANY_STRING`)
4. Subscribe to: `messages`, `messaging_postbacks`

### Step 5: Connect Instagram (Optional)
1. Facebook App → Settings → Instagram
2. **Webhook URL**: Same as Messenger (Messenger and Instagram share the endpoint)
3. Subscribe to: `messages`, `messaging_postbacks`

### Step 6: Test Live
- Send message on Messenger or Instagram
- Bot should reply within 2-3 seconds
- Check owner DMs if you configured OWNER_DM_IDs

---

## Local Testing

### Start Bot
```powershell
cd e:\Startupt\EllenAI
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Run Test Suite
```powershell
python test_webhook.py
```

### Reload Products (No Restart)
```bash
curl -X POST http://localhost:8000/admin/reload-products \
  -H "X-Admin-Token: your_admin_token"
```

---

## File Checklist

| File | Status | Purpose |
|------|--------|---------|
| main.py | ✓ Ready | FastAPI bot server |
| product_store.py | ✓ Ready | Product catalog loader |
| manage_products.py | ✓ Ready | CLI for adding products |
| requirements.txt | ✓ Ready | Python dependencies |
| products.json | ✓ Ready | 38 products, 52 variants |
| .env | ✓ Ready | Your secret config (gitignored) |
| .env.example | ✓ Ready | Template for team |
| Procfile | ✓ Ready | Railway deployment config |
| .railwayignore | ✓ Ready | Files to skip on deploy |
| README.md | ✓ Ready | User documentation |
| TEST_GUIDE.md | ✓ Ready | Local testing instructions |

---

## Environment Variables (28 Total)

### Authentication (Must set)
- `OPENAI_API_KEY` → Your OpenAI API key
- `PAGE_ACCESS_TOKEN` → Meta Page token
- `PAGE_ID` → Your Facebook Page ID
- `APP_SECRET` → Meta App secret
- `VERIFY_TOKEN` → Webhook verify token (can be any string)
- `ADMIN_TOKEN` → For admin endpoints

### Bot Configuration
- `BKASH_NUMBER` (default: 01942776220)
- `ADVANCE_PERCENT` (default: 0.60 = 60%)
- `MIN_ORDER_TOTAL` (default: 600 tk)
- `OWNER_DM_ID` → Owner's Facebook ID
- `OWNER_DM_MESSENGER_ID` → Owner's Messenger user ID
- `OWNER_DM_INSTAGRAM_ID` → Owner's Instagram user ID

### Caching & Performance
- `INTENT_CACHE_MAX_SIZE` (default: 10000)
- `INTENT_CACHE_TTL_SECONDS` (default: 3600)
- `REWRITE_CACHE_MAX_SIZE` (default: 10000)
- `REWRITE_CACHE_TTL_SECONDS` (default: 3600)
- `SESSION_CACHE_MAX_SIZE` (default: 5000)

### Rate Limiting
- `USER_RATE_LIMIT_COUNT` (default: 8 msg/user)
- `USER_RATE_LIMIT_WINDOW_SECONDS` (default: 20 sec)
- `WEBHOOK_RATE_LIMIT_COUNT` (default: 60 events)
- `WEBHOOK_RATE_LIMIT_WINDOW_SECONDS` (default: 10 sec)

### Retry & Reliability
- `OPENAI_RETRY_ATTEMPTS` (default: 3)
- `OPENAI_RETRY_MIN_SECONDS` (default: 1)
- `OPENAI_RETRY_MAX_SECONDS` (default: 8)

### Paths & Misc
- `PRODUCTS_FILE_PATH` (default: products.json)
- `STATE_DB_PATH` (default: ellenai_state.db)
- `MESSAGE_SEND_DELAY_SECONDS` (default: 5)
- `ENABLE_REPLY_REWRITE` (default: 1 = enabled)

---

## Troubleshooting

### Bot Not Responding
1. Check Railway logs: `Deployments → View Logs`
2. Verify `PAGE_ACCESS_TOKEN` is correct
3. Verify webhook URL matches Rail way domain
4. Check `VERIFY_TOKEN` matches Messenger webhook setting

### Products Not Found
1. Reload: `POST /admin/reload-products` with `X-Admin-Token` header
2. Verify `products.json` is valid JSON
3. Check product link format (should be normalized)

### Owner Alerts Not Arriving
1. Confirm `OWNER_DM_MESSENGER_ID` or `OWNER_DM_INSTAGRAM_ID` set
2. Verify IDs are correct (should be long numbers)
3. Test via CLI: `python -c "import main; main.asyncio.run(main.send_owner_alert('messenger', 'Test'))"`

### Performance Degradation
1. Increase cache sizes
2. Increase rate limits if needed
3. Check Railway resource usage

---

## Production Checklist

- [ ] All 6 required env vars set in Railway
- [ ] Webhook URL configured in Meta dashboard
- [ ] VERIFY_TOKEN matches
- [ ] APP_SECRET configured
- [ ] Bot responds to test message
- [ ] Owner alerts working
- [ ] Product search working
- [ ] Order flow complete (add → location → payment → confirm)
- [ ] Payment breakdown correct
- [ ] Minimum order enforced

---

## Support

For issues, check:
1. Railway logs
2. .env.example for missing variables
3. products.json structure (all entries must be lists)
4. Webhook signature verification (APP_SECRET must match)

---

**Deployed:** March 27, 2026
**Status:** Production Ready
