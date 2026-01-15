# Local Testing Guide

Quick guide to test the application locally before deploying to Azure VM.

## Prerequisites

- Python 3.8 or higher
- Git (to clone the repository)
- Microsoft Azure App Registration credentials
- Notion API credentials

## Step 1: Clone and Setup

```bash
# Clone the repository (if not already done)
git clone <your-repo-url>
cd teams-notion-api-dev

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

## Step 2: Configure Environment Variables

Create a `.env` file in the project root:

```bash
# On Windows
notepad .env

# On Linux/macOS
nano .env
```

Add the following (replace with your actual values):

```env
# Microsoft Graph API Credentials
MICROSOFT_CLIENT_ID=your_client_id_here
MICROSOFT_CLIENT_SECRET=your_client_secret_here
MICROSOFT_TENANT_ID=your_tenant_id_here

# Notion API Credentials
NOTION_API_TOKEN=your_notion_integration_token_here
NOTION_DATABASE_ID=your_notion_database_id_here

# Allowed Users (comma-separated email list)
ALLOWED_USERS=user1@example.com,user2@example.com

# Webhook Configuration
# For local testing, you'll need a public URL (see Step 3)
WEBHOOK_NOTIFICATION_URL=https://your-public-url.com/webhook/notification
WEBHOOK_CLIENT_STATE=your_random_secret_string_here

# Optional: Default ticket status
DEFAULT_TICKET_STATUS=New

# Optional: Source identifier
TICKET_SOURCE=Teams
```

## Step 3: Get a Public URL for Webhooks

Microsoft Graph requires a public HTTPS URL for webhooks. For local testing, you have a few options:

### Option A: Use ngrok (Recommended for Testing)

1. **Install ngrok:**
   - Download from [ngrok.com](https://ngrok.com/download)
   - Or install via package manager:
     ```bash
     # macOS
     brew install ngrok
     
     # Windows
     # Download from ngrok.com and add to PATH
     ```

2. **Start ngrok tunnel:**
   ```bash
   ngrok http 8000
   ```

3. **Copy the HTTPS URL** (e.g., `https://abc123.ngrok.io`)

4. **Update `.env` file:**
   ```env
   WEBHOOK_NOTIFICATION_URL=https://abc123.ngrok.io/webhook/notification
   ```

### Option B: Use Cloudflare Tunnel (Alternative)

```bash
# Install cloudflared
# macOS: brew install cloudflared
# Or download from: https://github.com/cloudflare/cloudflared

# Start tunnel
cloudflared tunnel --url http://localhost:8000
```

### Option C: Use LocalTunnel (Alternative)

```bash
# Install
npm install -g localtunnel

# Start tunnel
lt --port 8000
```

## Step 4: Run the Application

```bash
# Make sure virtual environment is activated
# Then run:
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

You should see output like:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

## Step 5: Test the Application

### Test Health Endpoint

Open a new terminal and run:

```bash
# Test health endpoint
curl http://localhost:8000/health

# Expected response: {"status":"healthy"}
```

Or open in browser: `http://localhost:8000/health`

### Test Root Endpoint

```bash
curl http://localhost:8000/

# Expected response: {"name":"Teams-Notion Webhook Middleware","version":"1.0.0","status":"running"}
```

Or open in browser: `http://localhost:8000/`

### View API Documentation

Open in browser:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Test Diagnostics Endpoints

```bash
# Health check
curl http://localhost:8000/diagnostics/health

# View configuration (sensitive values masked)
curl http://localhost:8000/diagnostics/config

# List subscriptions
curl http://localhost:8000/diagnostics/subscriptions
```

### Test Webhook Validation Endpoint

```bash
# Test validation endpoint (simulates Microsoft Graph validation)
curl "http://localhost:8000/webhook/notification?validationToken=test123"

# Expected response: test123
```

**Important**: This should respond very quickly (< 100ms). If it's slow, there may be an issue.

## Step 6: Create a Test Subscription

**Note**: This requires your ngrok/tunnel URL to be accessible from the internet.

```bash
# Replace {teamId} and {channelId} with your actual Teams IDs
curl -X POST "http://localhost:8000/subscription/create?pre_warmup=true" \
  -H "Content-Type: application/json" \
  -d '{
    "resource": "teams/{teamId}/channels/{channelId}/messages",
    "change_types": ["created"],
    "expiration_days": 0.04
  }'
```

**Important**: 
- Replace `{teamId}` and `{channelId}` with your actual Teams team and channel IDs
- Make sure your `WEBHOOK_NOTIFICATION_URL` in `.env` matches your ngrok/tunnel URL
- The subscription will expire in ~1 hour (0.04 days) for Teams messages

### Get Your Teams IDs

1. **Team ID**: 
   - Go to Teams → Right-click team name → "Get team link"
   - The URL contains the team ID: `https://teams.microsoft.com/l/team/19%3a...%40thread.tacv2/...`
   - Extract the ID between `/team/` and `@thread`

2. **Channel ID**:
   - Go to the channel in Teams
   - Right-click channel name → "Get link to channel"
   - The URL contains the channel ID: `https://teams.microsoft.com/l/channel/19%3a...%40thread.tacv2/...`
   - Extract the ID between `/channel/` and `@thread`

## Step 7: Test Webhook Notifications

1. **Post a message** in your Teams channel
2. **React with ticket emoji (🎫)** as an allowed user
3. **Check application logs** for webhook processing
4. **Check Notion database** for the created ticket

## Troubleshooting

### Issue: "Module not found" errors

**Solution:**
```bash
# Make sure virtual environment is activated
# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: "Configuration error" on startup

**Solution:**
- Check that `.env` file exists in project root
- Verify all required environment variables are set
- Check for typos in variable names

### Issue: Webhook validation timeout

**Symptoms**: "Subscription validation request timed out" error

**Solutions:**
1. Ensure ngrok/tunnel is running and stable
2. Verify `WEBHOOK_NOTIFICATION_URL` matches your tunnel URL exactly
3. Test validation endpoint responds quickly:
   ```bash
   curl "http://localhost:8000/webhook/notification?validationToken=test123"
   ```
4. Check that your tunnel URL is accessible from the internet

### Issue: Service won't start

**Check logs:**
- Look at the terminal output for error messages
- Common issues:
  - Missing environment variables
  - Port 8000 already in use
  - Invalid credentials

**Solution:**
```bash
# Check if port is in use
# On Windows:
netstat -ano | findstr :8000

# On Linux/macOS:
lsof -i :8000

# Use a different port if needed:
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

### Issue: Notion tickets not created

**Solutions:**
1. Verify Notion API token is correct
2. Check that Notion integration has access to the database
3. Verify database ID is correct
4. Check application logs for errors
5. Ensure reacting user's email is in `ALLOWED_USERS`

### Issue: Authentication errors

**Solutions:**
1. Verify Microsoft Graph credentials are correct
2. Check that all required API permissions are granted
3. Ensure admin consent is granted for all permissions
4. Verify client secret hasn't expired

## Quick Test Checklist

- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `.env` file created with all required variables
- [ ] ngrok/tunnel running and URL copied
- [ ] `WEBHOOK_NOTIFICATION_URL` updated in `.env`
- [ ] Application starts without errors
- [ ] Health endpoint responds: `curl http://localhost:8000/health`
- [ ] API docs accessible: `http://localhost:8000/docs`
- [ ] Validation endpoint responds quickly: `curl "http://localhost:8000/webhook/notification?validationToken=test123"`
- [ ] Can create subscription (if Teams IDs available)
- [ ] Webhook notifications work (test with Teams message + emoji)

## Next Steps

Once local testing is successful:

1. Review [AZURE_VM_DEPLOYMENT.md](AZURE_VM_DEPLOYMENT.md) for production deployment
2. Set up Azure VM
3. Deploy using the provided deployment script
4. Configure systemd service
5. Set up Nginx and SSL

## Tips

- **Keep ngrok running** while testing webhooks
- **Check logs** in the terminal where uvicorn is running
- **Use `/docs` endpoint** to explore and test all API endpoints interactively
- **Test validation endpoint first** before creating subscriptions
- **Verify Teams IDs** are correct before creating subscriptions
