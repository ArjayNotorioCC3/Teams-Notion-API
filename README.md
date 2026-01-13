# Teams-Middleware-FastAPI

A FastAPI middleware for automating ticket creation in Notion from Microsoft Teams. When specific users react to a Teams channel message with a ticket emoji (🎫), a ticket is automatically created in Notion with all relevant information.

## Features

- **Microsoft Graph Webhook Integration**: Subscribes to Teams channel message events
- **Emoji Reaction Detection**: Monitors for ticket emoji reactions from allowed users
- **Notion Ticket Creation**: Automatically creates tickets with comprehensive information
- **Duplicate Prevention**: Prevents duplicate tickets using Teams Message ID
- **User Authorization**: Only specified users can trigger ticket creation
- **Subscription Management**: API endpoints for managing webhook subscriptions

## Architecture

The middleware handles the following flow:

1. Subscribes to Microsoft Graph webhooks for Teams channel messages
2. Receives webhook notifications when messages are created/updated
3. Checks if a ticket emoji (🎫) reaction was added by an allowed user
4. Fetches full message details including reactions
5. Creates a ticket in Notion with all required properties

## Prerequisites

- Python 3.8 or higher
- Microsoft Azure App Registration with Graph API permissions
- Notion workspace with a database and integration token
- Public URL for receiving webhooks (or use a tunneling service like ngrok for development)

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the project root with the following variables:

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
WEBHOOK_NOTIFICATION_URL=https://your-domain.com/webhook/notification
WEBHOOK_CLIENT_STATE=your_secret_client_state_here

# Optional: Default ticket status
DEFAULT_TICKET_STATUS=New

# Optional: Source identifier
TICKET_SOURCE=Teams
```

### 3. Microsoft Azure App Registration

1. Go to [Azure Portal](https://portal.azure.com) → Azure Active Directory → App registrations
2. Create a new registration or use an existing one
3. Note the **Application (client) ID** and **Directory (tenant) ID**
4. Create a client secret under "Certificates & secrets"
5. Under "API permissions", add the following Microsoft Graph permissions:
   - `ChannelMessage.Read.All` (Application permission)
   - `Team.ReadBasic.All` (Application permission)
   - `User.Read.All` (Application permission)
   - `Subscription.ReadWrite.All` (Application permission)
6. Grant admin consent for all permissions

### 4. Notion Setup

1. Create a Notion database with the following properties:
   - **Task Title** (Title)
   - **Description** (Rich Text)
   - **Status** (Select)
   - **Requester** (Rich Text)
   - **Teams Message ID** (Rich Text) - Used for duplicate prevention
   - **Teams Channel** (Rich Text)
   - **Attachments (URL)** (Rich Text)
   - **Approved By** (Rich Text)
   - **Approved At** (Date)
   - **Source** (Rich Text)
   - **Last Synced** (Date)

2. Create a Notion integration:
   - Go to [Notion Integrations](https://www.notion.so/my-integrations)
   - Click "New integration"
   - Give it a name and select your workspace
   - Copy the **Internal Integration Token**
   - Share your database with the integration (click "..." on the database → "Connections" → select your integration)

3. Get your database ID:
   - Open your database in Notion
   - The URL will be: `https://www.notion.so/{workspace}/{database_id}?v=...`
   - Copy the `database_id` (32 characters, with hyphens)

### 5. Webhook URL Setup

For production, use a public URL. For development, you can use [ngrok](https://ngrok.com):

```bash
ngrok http 8000
```

Use the ngrok URL as your `WEBHOOK_NOTIFICATION_URL` (e.g., `https://abc123.ngrok.io/webhook/notification`)

## Running the Application

```bash
# Development
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Webhook Endpoints

- `GET /webhook/validation` - Webhook validation endpoint (called by Microsoft Graph)
- `POST /webhook/notification` - Receives webhook notifications from Microsoft Graph

### Subscription Management

- `GET /subscription/list` - List all active subscriptions
- `POST /subscription/create` - Create a new subscription
  ```json
  {
    "resource": "teams/{teamId}/channels/{channelId}/messages",
    "change_types": ["created", "updated"],
    "expiration_days": 3
  }
  ```
- `POST /subscription/renew/{subscription_id}` - Renew a subscription
- `DELETE /subscription/delete/{subscription_id}` - Delete a subscription
- `POST /subscription/renew-all` - Renew all active subscriptions

### Health Check

- `GET /health` - Health check endpoint
- `GET /` - API information

## Usage

### 1. Create a Webhook Subscription

After starting the application, create a subscription for a Teams channel:

```bash
curl -X POST "http://localhost:8000/subscription/create" \
  -H "Content-Type: application/json" \
  -d '{
    "resource": "teams/{teamId}/channels/{channelId}/messages",
    "change_types": ["created", "updated"],
    "expiration_days": 3
  }'
```

Replace `{teamId}` and `{channelId}` with your actual Team and Channel IDs.

### 2. Monitor Subscriptions

Microsoft Graph subscriptions expire after 3 days (maximum). Use the renew endpoints to keep them active:

```bash
# Renew all subscriptions
curl -X POST "http://localhost:8000/subscription/renew-all" \
  -H "Content-Type: application/json" \
  -d '{"expiration_days": 3}'
```

### 3. How It Works

1. A user posts a message in a Teams channel
2. An allowed user reacts to the message with the ticket emoji (🎫)
3. The webhook receives a notification
4. The middleware:
   - Fetches the full message details
   - Verifies the reacting user is allowed
   - Extracts all relevant information
   - Creates a ticket in Notion
   - Prevents duplicates using Teams Message ID

## Notion Ticket Properties

Each ticket created in Notion includes:

- **Task Title**: Extracted from message subject or first line
- **Description**: Full message body content
- **Status**: Default status (configurable)
- **Requester**: Original message author
- **Teams Message ID**: Unique identifier (used for duplicate prevention)
- **Teams Channel**: Channel where message was posted
- **Attachments (URL)**: URLs of any message attachments
- **Approved By**: User who added the ticket emoji reaction
- **Approved At**: Timestamp when emoji was added
- **Source**: Source identifier (default: "Teams")
- **Last Synced**: Timestamp when ticket was created

## Troubleshooting

### Webhook Validation Timeout (Common Local Development Issue)

**Symptoms:** Microsoft Graph returns "validation timed out" when creating subscription.

**Root Causes:**
- Webhook endpoint responding too slowly (> 2 seconds)
- Clock synchronization issues between local machine and Microsoft servers
- Incorrect datetime formatting in subscription payload
- Network latency through ngrok tunnel

**Solutions:**

1. **Test endpoints locally first:**
   ```bash
   # Run the server
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   
   # In another terminal, run the local test suite
   python3 test_local.py
   
   # Test with a specific resource
   python3 test_local.py --resource "teams/{teamId}/channels/{channelId}/messages"
   ```

2. **Check diagnostics:**
   ```bash
   # Comprehensive health check
   curl http://localhost:8000/diagnostics/health
   
   # View configuration
   curl http://localhost:8000/diagnostics/config
   
   # List subscriptions with status
   curl http://localhost:8000/diagnostics/subscriptions
   
   # Test subscription payload without creating it
   curl -X POST "http://localhost:8000/diagnostics/test-subscription-payload" \
     -H "Content-Type: application/json" \
     -d '{"resource": "teams/{teamId}/channels/{channelId}/messages"}'
   ```

3. **Ensure ngrok is configured correctly:**
   ```bash
   # Start ngrok
   ngrok http 8000
   
   # Update .env with the ngrok URL
   WEBHOOK_NOTIFICATION_URL=https://your-ngrok-url.ngrok.io/webhook/notification
   WEBHOOK_CLIENT_STATE=your_secret_client_state_here
   
   # Restart the server after updating .env
   ```

4. **Verify datetime format:**
   - The code now uses `datetime.now(timezone.utc)` consistently
   - All timestamps are formatted with 'Z' suffix (UTC)
   - Add 30-second buffer for clock skew during subscription creation

5. **For Teams messages specifically:**
   - Maximum expiration is 1 hour (enforced by code)
   - `lifecycleNotificationUrl` is REQUIRED
   - Only `changeType="created"` is supported
   - The normalization function handles these automatically

### Webhook Not Receiving Notifications

1. Verify your webhook URL is publicly accessible
2. Check that the subscription is active: `GET /subscription/list`
3. Ensure the subscription hasn't expired (renew if needed)
4. Check application logs for errors

### Tickets Not Being Created

1. Verify the reacting user's email is in `ALLOWED_USERS`
2. Check that the emoji used is exactly 🎫 (ticket emoji)
3. Verify Notion API token and database ID are correct
4. Check that the Notion integration has access to the database
5. Review application logs for detailed error messages

### Authentication Errors

1. Verify Microsoft Graph credentials are correct
2. Ensure all required API permissions are granted and consented
3. Check that the client secret hasn't expired

## Local Development Guide

### Prerequisites

1. **Python 3.8+** with virtual environment
2. **ngrok** for tunneling (or use ngrok-free alternatives)
3. **Microsoft Azure App Registration** with Graph API permissions
4. **Notion Workspace** with database and integration

### Setup Steps

1. **Clone and install dependencies:**
   ```bash
   cd Teams-Middleware-FastAPI
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   ```bash
   cp ".env example" .env
   # Edit .env with your actual credentials
   ```

3. **Start ngrok tunnel:**
   ```bash
   ngrok http 8000
   # Note the HTTPS URL (e.g., https://abc123.ngrok.io)
   ```

4. **Update .env with ngrok URL:**
   ```env
   WEBHOOK_NOTIFICATION_URL=https://abc123.ngrok.io/webhook/notification
   WEBHOOK_CLIENT_STATE=your_random_secret_string
   ```

5. **Run the server:**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

6. **Test locally before creating subscription:**
   ```bash
   python3 test_local.py
   ```

7. **Create subscription:**
   ```bash
   curl -X POST "http://localhost:8000/subscription/create" \
     -H "Content-Type: application/json" \
     -d '{
       "resource": "teams/{teamId}/channels/{channelId}/messages",
       "change_types": ["created", "updated"],
       "expiration_days": 1
     }'
   ```

### Common Local Development Issues

**Issue:** "validation timed out" when creating subscription

**Fix:**
1. Run `python3 test_local.py` to verify webhook validation endpoints
2. Check response times are < 100ms
3. Ensure ngrok tunnel is stable
4. Verify clock is synchronized: `timedatectl status` (Linux) or sync with NTP

**Issue:** Subscription expires immediately

**Fix:**
1. Use `/diagnostics/subscriptions` to check expiration times
2. Ensure system clock is accurate (sync with NTP)
3. Check if timezone is causing issues (should be UTC)

**Issue:** Notion tickets not created

**Fix:**
1. Verify Notion database properties match requirements
2. Check Notion integration is shared with the database
3. Review logs for API errors
4. Test Notion API directly: `GET /diagnostics/health`

### Debugging Tips

1. **Enable detailed logging:**
   ```python
   # In main.py, change logging level to DEBUG
   logging.basicConfig(level=logging.DEBUG, ...)
   ```

2. **Test payload before creating subscription:**
   ```bash
   curl -X POST "http://localhost:8000/diagnostics/test-subscription-payload" \
     -H "Content-Type: application/json" \
     -d '{"resource": "teams/{teamId}/channels/{channelId}/messages"}'
   ```

3. **Monitor subscription lifecycle:**
   ```bash
   # List subscriptions with detailed status
   curl http://localhost:8000/diagnostics/subscriptions
   
   # Renew expiring subscriptions
   curl -X POST "http://localhost:8000/subscription/renew-all" \
     -H "Content-Type: application/json" \
     -d '{"expiration_days": 1}'
   
   # Clean up expired subscriptions
   curl -X POST "http://localhost:8000/diagnostics/cleanup-expired"
   ```

4. **Simulate webhook notification:**
   ```bash
   # Test validation endpoint
   curl "http://localhost:8000/webhook/notification?validationToken=test123"
   
   # Should return the token immediately
   ```

## Project Structure

```
.
├── main.py                 # FastAPI application entry point
├── config.py              # Configuration management
├── models/                # Pydantic models
│   └── webhook_models.py  # Webhook payload models
├── services/              # Business logic
│   ├── graph_service.py  # Microsoft Graph API service
│   └── notion_service.py # Notion API service
├── routes/                # API endpoints
│   ├── webhooks.py       # Webhook notification handlers
│   └── subscription.py   # Subscription management
├── utils/                 # Utility functions
│   ├── auth.py           # Authentication helpers
│   └── validation.py     # User authorization
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## License

This project is provided as-is for integration purposes.

### Ngrok Domain Issues

**Problem:** Free ngrok domains (ngrok-free.dev) often have high latency and routing issues that cause validation timeouts.

**Solutions:**

1. **Use Standard Ngrok Domain:**
   \`\`\`bash
   # Free tier - better routing than ngrok-free.dev
   ngrok http 8000
   
   # This gives URL like: https://abc123.ngrok.io
   # Update .env with this URL
   WEBHOOK_NOTIFICATION_URL=https://abc123.ngrok.io/webhook/notification
   \`\`\`

2. **Use Paid Ngrok Reserved Domain:**
   \`\`\`bash
   # \$10/month - reserved domain, no connection drops
   # Sign up at: https://ngrok.com/pricing
   # After reserved domain:
   ngrok http 8000 --domain=your-reserved-domain.ngrok.io
   \`\`\`

3. **Use Cloudflare Tunnel (Alternative):**
   \`\`\`bash
   # Install cloudflared
   brew install cloudflared  # macOS
   # or download from: https://github.com/cloudflare/cloudflared
   
   # Start tunnel
   cloudflared tunnel --url http://localhost:8000
   
   # Typically has better routing and lower latency than ngrok free
   \`\`\`

4. **Use LocalTunnel (Alternative):**
   \`\`\`bash
   # Install
   npm install -g localtunnel
   
   # Start tunnel
   localtunnel --port 8000
   \`\`\`

**Recommendations:**
- **For local development:** Use standard ngrok free tier (\`.ngrok.io\`)
- **For consistent testing:** Consider paid ngrok reserved domain (\$10/month)
- **If ngrok is unstable:** Try Cloudflare Tunnel or LocalTunnel
- **Best option for production:** Deploy to Azure with public endpoint

### Pre-Validation Testing

Before creating a Microsoft Graph subscription, test your webhook endpoint's actual round-trip time:

\`\`\`bash
# Test validation response time (simulates Microsoft Graph validation)
curl "http://localhost:8000/pre-validation/test?validationToken=test123"

# Check response time in headers
curl -I "http://localhost:8000/pre-validation/test?validationToken=test123"

# Simulate full Microsoft Graph validation request
curl "http://localhost:8000/pre-validation/simulate?base_url=http://localhost:8000"
\`\`\`

**Response Time Benchmarks:**
- **< 50ms:** Excellent - Should work with any tunnel
- **50-100ms:** Good - Should work with decent tunnel
- **100-200ms:** Warning - May timeout with some tunnels
- **> 200ms:** Critical - Will likely timeout with Microsoft Graph

If response time > 100ms locally, it will definitely timeout through tunneling. Consider:
- Using a better tunnel (standard ngrok, Cloudflare Tunnel)
- Deploying to Azure with public endpoint
- Using faster machine/network connection
