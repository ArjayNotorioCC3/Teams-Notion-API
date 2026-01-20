# Teams-Notion Webhook Middleware

A FastAPI middleware for automating ticket creation in Notion from Microsoft Teams. When specific users react to a Teams channel message with a ticket emoji (🎫), a ticket is automatically created in Notion with all relevant information.

## Features

- **Microsoft Graph Webhook Integration**: Subscribes to Teams channel message events
- **Emoji Reaction Detection**: Monitors for ticket emoji reactions from allowed users
- **Notion Ticket Creation**: Automatically creates tickets with comprehensive information
- **Duplicate Prevention**: Prevents duplicate tickets using Teams Message ID
- **User Authorization**: Only specified users can trigger ticket creation
- **Subscription Management**: API endpoints for managing webhook subscriptions
- **Background Polling**: Automatically detects reactions even when Graph doesn't send "updated" notifications

## Architecture

The middleware handles the following flow:

1. Subscribes to Microsoft Graph webhooks for Teams channel messages
2. Receives webhook notifications when messages are created/updated
3. Checks if a ticket emoji (🎫) reaction was added by an allowed user
4. Fetches full message details including reactions
5. Creates a ticket in Notion with all required properties
6. Background polling task checks recent messages for reactions (handles Graph API limitations)

## Prerequisites

- Python 3.8+ or Docker
- Microsoft Azure App Registration with Graph API permissions
- Notion workspace with a database and integration token
- Public URL for receiving webhooks (for production)

## Quick Start with Docker Compose

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd teams-notion-api-dev
```

### 2. Configure Environment Variables

Copy the example environment file:

```bash
cp ".env example" .env
```

Edit `.env` with your credentials:

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

### 3. Run with Docker Compose

```bash
# Build and start the application
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the application
docker-compose down
```

The application will be available at `http://localhost:8000`

## Local Development (Without Docker)

### 1. Install Dependencies

```bash
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

### 2. Configure Environment Variables

Create a `.env` file (see Quick Start section above).

### 3. Run the Application

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Setup Instructions

### Microsoft Azure App Registration

1. Go to [Azure Portal](https://portal.azure.com) → Azure Active Directory → App registrations
2. Create a new registration or use an existing one
3. Note the **Application (client) ID** and **Directory (tenant) ID**
4. Create a client secret under "Certificates & secrets"
5. Under "API permissions", add the following Microsoft Graph permissions:
   - `ChannelMessage.Read.All` (Application permission)
   - `Team.ReadBasic.All` (Application permission)
   - `User.Read.All` (Application permission)
   - `Subscription.ReadWrite.All` (Application permission)
6. **Grant admin consent** for all permissions (click "Grant admin consent for [your tenant]")

**Important**: For subscription creation, you need an **Application** token (client credentials flow), not a user token. Ensure your app registration has `Subscription.ReadWrite.All` as an **Application** permission (not Delegated).

### Notion Setup

1. **Create a Notion database** with the following properties:
   - **Task Title** (Title)
   - **Description** (Rich Text)
   - **Status** (Status) - Note: Must be a Status property, not Select
   - **Requester** (People) - Note: Must be a People property
   - **Teams Message ID** (Rich Text) - Used for duplicate prevention
   - **Teams Channel** (Rich Text)
   - **Attachments** (URL) - Note: Must be a URL property
   - **Approved By** (People) - Note: Must be a People property
   - **Approved At** (Date)
   - **Source** (Rich Text)
   - **Last Synced** (Date)

2. **Create a Notion integration**:
   - Go to [Notion Integrations](https://www.notion.so/my-integrations)
   - Click "New integration"
   - Give it a name and select your workspace
   - Copy the **Internal Integration Token**
   - Share your database with the integration (click "..." on the database → "Connections" → select your integration)

3. **Get your database ID**:
   - Open your database in Notion
   - The URL will be: `https://www.notion.so/{workspace}/{database_id}?v=...`
   - Copy the `database_id` (32 characters, with hyphens)

**Important**: Users must be added to your Notion workspace for the "Requester" and "Approved By" people properties to work correctly. The system will search for users by email address (case-insensitive).

## API Endpoints

### Webhook Endpoints

- `GET /graph/validate` - Ultra-fast validation endpoint for Microsoft Graph (bypasses middleware)
- `POST /graph/validate` - Handles validation and forwards notifications
- `GET /webhook/validation` - Webhook validation endpoint (legacy)
- `POST /webhook/notification` - Receives webhook notifications from Microsoft Graph
- `POST /webhook/lifecycle` - Handles subscription lifecycle events

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

### Diagnostics

- `GET /health` - Health check endpoint
- `GET /diagnostics/health` - Comprehensive health check
- `GET /diagnostics/config` - View configuration (sensitive values masked)
- `GET /diagnostics/subscriptions` - List subscriptions with detailed status

### Root

- `GET /` - API information
- `GET /docs` - Swagger UI documentation
- `GET /redoc` - ReDoc documentation

## Usage

### 1. Create a Webhook Subscription

After starting the application, create a subscription for a Teams channel:

```bash
curl -X POST "http://localhost:8000/subscription/create" \
  -H "Content-Type: application/json" \
  -d '{
    "resource": "teams/{teamId}/channels/{channelId}/messages",
    "change_types": ["created"],
    "expiration_days": 0.04
  }'
```

Replace `{teamId}` and `{channelId}` with your actual Team and Channel IDs.

**Getting Teams IDs:**
- **Team ID**: Right-click team name → "Get team link" → Extract ID from URL
- **Channel ID**: Right-click channel name → "Get link to channel" → Extract ID from URL

### 2. Monitor Subscriptions

Microsoft Graph subscriptions expire after 3 days (maximum). For Teams messages, the maximum is 1 hour. Use the renew endpoints to keep them active:

```bash
# Renew all subscriptions
curl -X POST "http://localhost:8000/subscription/renew-all" \
  -H "Content-Type: application/json" \
  -d '{"expiration_days": 3}'
```

### 3. How It Works

1. A user posts a message in a Teams channel
2. An allowed user reacts to the message with the ticket emoji (🎫)
3. The webhook receives a notification (or background polling detects the reaction)
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
- **Requester**: Original message author (People property - requires user in Notion workspace)
- **Teams Message ID**: Unique identifier (used for duplicate prevention)
- **Teams Channel**: Channel where message was posted
- **Attachments**: URL of first attachment (if any)
- **Approved By**: User who added the ticket emoji reaction (People property - requires user in Notion workspace)
- **Approved At**: Timestamp when emoji was added
- **Source**: Source identifier (default: "Teams")
- **Last Synced**: Timestamp when ticket was created

## Deployment

### Docker Compose (Recommended)

See [Quick Start with Docker Compose](#quick-start-with-docker-compose) section above.

### Azure VM Deployment

For production deployment on Azure Virtual Machine:

1. **Create Azure VM**:
   - Use Ubuntu Server 22.04 LTS
   - Recommended size: Standard_B2s (2 vCPU, 4GB RAM) for production
   - Ensure ports 80 and 443 are open in Network Security Group

2. **SSH into VM**:
   ```bash
   ssh azureuser@<VM_PUBLIC_IP>
   ```

3. **Install Dependencies**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y python3 python3-pip python3-venv git nginx certbot python3-certbot-nginx
   ```

4. **Clone and Setup Application**:
   ```bash
   sudo mkdir -p /opt/teams-notion-api
   sudo chown $USER:$USER /opt/teams-notion-api
   cd /opt
   git clone <your-repo-url> teams-notion-api
   cd teams-notion-api
   python3 -m venv venv
   source venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

5. **Configure Environment Variables**:
   ```bash
   nano /opt/teams-notion-api/.env
   # Add your credentials (see Quick Start section)
   ```

6. **Setup Systemd Service**:
   ```bash
   sudo cp systemd/teams-notion-api.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable teams-notion-api.service
   sudo systemctl start teams-notion-api.service
   ```

7. **Configure Nginx**:
   ```bash
   sudo cp deploy/nginx-optimized.conf /etc/nginx/sites-available/teams-notion-api
   sudo ln -s /etc/nginx/sites-available/teams-notion-api /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

8. **Setup SSL Certificate** (if you have a domain):
   ```bash
   sudo certbot --nginx -d your-domain.com
   ```

9. **Configure Firewall**:
   ```bash
   sudo ufw allow 22/tcp
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```

10. **Update WEBHOOK_NOTIFICATION_URL** in `.env` to your domain or public IP

### Local Testing with Public URL

For local testing, you need a public HTTPS URL. Options:

- **ngrok**: `ngrok http 8000` (recommended for testing)
- **Cloudflare Tunnel**: `cloudflared tunnel --url http://localhost:8000`
- **LocalTunnel**: `lt --port 8000`

Update `WEBHOOK_NOTIFICATION_URL` in `.env` to your tunnel URL.

## Troubleshooting

### Webhook Validation Timeout

**Symptoms:** Microsoft Graph returns "validation timed out" when creating subscription.

**Solutions:**

1. **Verify webhook endpoint is accessible:**
   ```bash
   curl "https://your-domain.com/graph/validate?validationToken=test123"
   # Should return: test123
   ```

2. **Check diagnostics:**
   ```bash
   curl https://your-domain.com/diagnostics/health
   curl https://your-domain.com/diagnostics/config
   curl https://your-domain.com/diagnostics/subscriptions
   ```

3. **Verify configuration:**
   - Ensure `WEBHOOK_NOTIFICATION_URL` is correctly set
   - Check that the endpoint responds in < 2 seconds
   - Verify firewall/security groups allow HTTP/HTTPS traffic

4. **For Teams messages specifically:**
   - Maximum expiration is 1 hour (enforced by code)
   - `lifecycleNotificationUrl` is REQUIRED
   - Only `changeType="created"` is supported
   - The normalization function handles these automatically

### Webhook Not Receiving Notifications

1. Verify your webhook URL is publicly accessible
2. Check that the subscription is active: `GET /subscription/list`
3. Ensure the subscription hasn't expired (renew if needed)
4. Check application logs for errors
5. Note: Graph API doesn't send "updated" notifications for reactions - the background polling task handles this

### Tickets Not Being Created

1. Verify the reacting user's email is in `ALLOWED_USERS`
2. Check that the emoji used is exactly 🎫 (ticket emoji)
3. Verify Notion API token and database ID are correct
4. Check that the Notion integration has access to the database
5. Ensure users are in Notion workspace for People properties to work
6. Review application logs for detailed error messages

### Authentication Errors

1. Verify Microsoft Graph credentials are correct
2. Ensure all required API permissions are granted and consented
3. Check that the client secret hasn't expired
4. For subscription creation, ensure you're using an **Application** token (not user token)

### Notion People Properties Empty

If "Requester" or "Approved By" fields are empty in Notion:

1. Ensure the user exists in your Notion workspace
2. Verify the email address matches exactly (case-insensitive)
3. Check application logs for warnings about user lookup failures
4. The system will create tickets even if users aren't found, but People properties will be empty

### Debugging Tips

1. **Check service logs (Docker)**:
   ```bash
   docker-compose logs -f
   ```

2. **Check service logs (Azure VM)**:
   ```bash
   sudo journalctl -u teams-notion-api.service -f
   ```

3. **Test endpoints:**
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/diagnostics/health
   ```

4. **Monitor subscriptions:**
   ```bash
   curl http://localhost:8000/diagnostics/subscriptions
   ```

## Performance Optimizations

The application includes several optimizations for fast webhook validation:

- **Ultra-fast validation endpoint** (`/graph/validate`) that bypasses middleware
- **Connection pooling** for Graph and Notion API requests
- **Background polling** for reaction detection (handles Graph API limitations)
- **Optimized Nginx configuration** for minimal latency
- **User ID caching** for Notion people properties

### Validation Endpoint Optimizations

- Root webhook route (`/webhook`) handles validation at root path
- Validation endpoints respond in 0.02-0.04ms
- Query string checked before any async operations
- Immediate response without body reading
- Minimal processing in critical path

### Nginx Optimizations

The optimized Nginx configuration (`deploy/nginx-optimized.conf`) includes:
- HTTP/2 support for faster connections
- Optimized SSL/TLS settings
- Disabled proxy buffering for instant response
- Reduced connection timeouts
- Keepalive optimizations

## Project Structure

```
.
├── main.py                 # FastAPI application entry point
├── config.py              # Configuration management
├── Dockerfile             # Docker image definition
├── docker-compose.yml     # Docker Compose configuration
├── requirements.txt       # Python dependencies
├── models/                # Pydantic models
│   └── webhook_models.py  # Webhook payload models
├── services/              # Business logic
│   ├── graph_service.py  # Microsoft Graph API service
│   └── notion_service.py # Notion API service
├── routes/                # API endpoints
│   ├── webhooks.py       # Webhook notification handlers
│   ├── subscription.py   # Subscription management
│   └── diagnostics.py   # Diagnostics and monitoring
├── utils/                 # Utility functions
│   ├── auth.py           # Authentication helpers
│   ├── validation.py     # User authorization
│   └── graph_subscriptions.py  # Subscription normalization
├── systemd/               # Systemd service configuration
│   └── teams-notion-api.service
└── deploy/                # Deployment scripts
    ├── deploy.sh         # Deployment automation script
    └── nginx-optimized.conf  # Optimized Nginx configuration
```

## License

This project is provided as-is for integration purposes.
