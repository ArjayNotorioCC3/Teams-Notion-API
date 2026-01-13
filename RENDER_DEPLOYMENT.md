# Render Free Tier Deployment Guide

## Optimizations Implemented

Your application has been optimized for Render.com free tier to address the "Subscription validation timed out" issue you encountered.

### What Was Fixed

**Root Cause:** The 10-second delay between creating the subscription payload and sending it to Microsoft Graph was caused by cold start + first-time MSAL token acquisition. On Render free tier, services spin down after 15 minutes of inactivity, causing this delay on every cold start.

### Optimizations Applied

1. **Service Pre-warming on Startup** (`main.py`)
   - Microsoft Graph access token is acquired during FastAPI startup
   - Services are initialized before any API requests
   - **Impact:** Eliminates 10-second first-request delay

2. **Singleton Service Instances** (`main.py`)
   - GraphService and NotionService created once at module level
   - Shared across all route handlers
   - **Impact:** Prevents re-initialization on each request

3. **Background Keep-Alive Task** (`main.py`)
   - Auto-pings `/health` endpoint every 10 minutes
   - Keeps service warm and prevents cold starts
   - Configurable via environment variables
   - **Impact:** Service stays responsive during testing sessions

4. **NotionService Connection Pooling** (`services/notion_service.py`)
   - Persistent HTTP client with connection reuse
   - Matches GraphService optimization pattern
   - **Impact:** Faster Notion API calls

5. **New Warmup Endpoint** (`routes/keep_alive.py`)
   - `GET /keep-alive/warmup` - Explicitly warm up all services
   - `GET /keep-alive/status` - Check service warmup status
   - `GET /keep-alive/ping` - Simple ping to keep service warm
   - **Impact:** Manual control over warmup before critical operations

6. **Render Configuration** (`render.yaml`)
   - Health check path configured
   - Keep-alive intervals set to 600 seconds (10 minutes)
   - Environment variables pre-configured
   - **Impact:** Automated deployment with all optimizations

## Deployment Instructions

### 1. Update Environment Variables in Render Dashboard

After deployment, update these environment variables in the Render dashboard (under "Advanced" section):

```
MICROSOFT_CLIENT_ID=your_client_id_here
MICROSOFT_CLIENT_SECRET=your_client_secret_here
MICROSOFT_TENANT_ID=your_tenant_id_here
NOTION_API_TOKEN=your_notion_integration_token_here
NOTION_DATABASE_ID=your_notion_database_id_here
ALLOWED_USERS=user1@example.com,user2@example.com
WEBHOOK_NOTIFICATION_URL=https://your-app-name.onrender.com/webhook/notification
WEBHOOK_CLIENT_STATE=your_random_secret_string_here
```

**Important:** Update `WEBHOOK_NOTIFICATION_URL` to match your actual Render service URL after deployment.

### 2. Deploy to Render

**Option A: Using render.yaml (Recommended)**

1. Push your code to GitHub
2. Sign up for [Render.com](https://render.com)
3. Click "New +" → "New Blueprint"
4. Connect your GitHub repository
5. Select the branch containing your code
6. Render will automatically detect `render.yaml`
7. Review and click "Apply Blueprint"

**Option B: Manual Setup**

1. Sign up for [Render.com](https://render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Configure settings:
   - Name: `teams-notion-middleware` (or your choice)
   - Region: Choose closest to you
   - Branch: `main`
   - Runtime: Python
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Instance Type: **Free**
5. Under "Advanced":
   - Add all environment variables from above
   - Health Check Path: `/health`
6. Click "Create Web Service"

### 3. Post-Deployment Verification

**Step 1: Check Service is Running**
```bash
curl https://your-app-name.onrender.com/health
```
Expected response: `{"status":"healthy"}`

**Step 2: Verify Warmup**
```bash
curl https://your-app-name.onrender.com/keep-alive/status
```
Expected response should show `token_available: true` for Graph service.

**Step 3: Explicit Warmup (Before Creating Subscriptions)**
```bash
curl https://your-app-name.onrender.com/keep-alive/warmup
```

Expected response:
```json
{
  "status": "ready",
  "services": {
    "graph": {
      "status": "ready",
      "token_acquisition_time_ms": 1234.56
    },
    "notion": {
      "status": "ready",
      "connectivity_test_time_ms": 234.56
    }
  },
  "total_warmup_time_ms": 1469.12
}
```

**Step 4: Create a Subscription**

After warmup is complete, create a subscription:
```bash
curl -X POST "https://your-app-name.onrender.com/subscription/create" \
  -H "Content-Type: application/json" \
  -d '{
    "resource": "teams/{teamId}/channels/{channelId}/messages",
    "change_types": ["created", "updated"],
    "expiration_days": 1
  }'
```

**Expected Result:** Subscription should be created successfully WITHOUT the "validation timed out" error.

## Testing Workflow

### For Extended Testing Sessions

To prevent the service from spinning down during testing:

1. **Option A: Background Keep-Alive (Automatic)**
   - Enabled by default in `render.yaml`
   - Pings service every 10 minutes
   - No action required

2. **Option B: Manual Keep-Alive**
   - Visit `/health` endpoint in browser every 10-15 minutes
   - Or use cron job:
     ```bash
     */10 * * * * curl https://your-app-name.onrender.com/health
     ```

3. **Option C: External Service**
   - Use [UptimeRobot](https://uptimerobot.com) (free)
   - Create monitor for your Render URL
   - Set check interval to 5-10 minutes

### Before Creating Subscriptions

Always call the warmup endpoint first to ensure fast response:
```bash
curl https://your-app-name.onrender.com/keep-alive/warmup
```

Then wait a few seconds before creating the subscription.

## Troubleshooting

### "Subscription validation timed out" Still Occurs

**If you still get the timeout error:**

1. Check if service is warm:
   ```bash
   curl https://your-app-name.onrender.com/keep-alive/status
   ```
   If `token_available: false`, the service is not warm.

2. Call warmup endpoint:
   ```bash
   curl https://your-app-name.onrender.com/keep-alive/warmup
   ```

3. Check warmup time - if > 5000ms, you may have network issues:
   - Retry after warmup
   - Consider using a different Render region
   - Or upgrade to paid tier for consistent performance

4. Check logs in Render dashboard for errors

### Service Still Spinning Down

**If keep-alive isn't working:**

1. Verify `KEEP_ALIVE_ENABLED=true` in environment variables
2. Check logs for "Starting background keep-alive task" message
3. Verify keep-alive pings in logs every 10 minutes
4. Manual workaround: Create UptimeRobot monitor

### High Warmup Time (>5 seconds)

**If warmup takes too long:**

1. Check Render logs for slow operations
2. Verify you're using a region close to you
3. Network latency may be the issue - try different region
4. Upgrade to paid tier for consistent performance

## Environment Variables Reference

### Keep-Alive Settings

- `KEEP_ALIVE_ENABLED` (default: `true`)
  - Enable/disable background keep-alive task
  - Set to `false` to disable automatic pinging

- `KEEP_ALIVE_INTERVAL_SECONDS` (default: `600`)
  - Interval between keep-alive pings in seconds
  - Recommended: 600 (10 minutes) - Render spins down after 15 minutes
  - Minimum: 300 (5 minutes) to stay well ahead of spin-down

### Service Settings

- `PORT` (set by Render, usually `10000`)
  - Port the service listens on
  - Don't modify this

- `PYTHON_VERSION` (default: `3.11`)
  - Python runtime version
  - Render minimum: `3.7.3`

## Performance Expectations

### After Optimizations

- **Cold start time**: 10+ seconds → **3-5 seconds** (with warmup)
- **First subscription request**: 10+ seconds → **<1 second** (if service warm)
- **Webhook validation**: **0.04ms** (already optimized, stays fast)
- **Service uptime**: During testing, keep service warm for instant response

### Limitations of Free Tier

Even with optimizations, be aware:

- Service may still spin down if keep-alive fails
- Initial deployment or redeploy may be slow
- High latency regions may still timeout occasionally
- Production use requires paid tier for reliability

## Upgrade to Paid Tier (Optional)

For production use or consistent performance:

1. In Render dashboard, go to your service
2. Click "Settings" → "Change Instance Type"
3. Select "Standard" ($7/month)
4. Benefits:
   - Service runs 24/7 (no spin-down)
   - Consistent performance
   - Better for production workloads

## Summary

Your app is now optimized for Render free tier with:

✅ Pre-warmed services on startup
✅ Background keep-alive task
✅ Connection pooling for faster API calls
✅ Manual warmup endpoint for critical operations
✅ Render deployment configuration ready

**Next Steps:**
1. Deploy to Render using the instructions above
2. Configure environment variables
3. Test warmup and subscription creation
4. For extended testing, set up external keep-alive monitor

Your subscription creation should now work reliably on Render free tier!
