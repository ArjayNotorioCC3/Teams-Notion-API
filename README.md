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
- Public URL for receiving webhooks (Azure VM with public IP or domain)

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

Set `WEBHOOK_NOTIFICATION_URL` to your public endpoint. For Azure VM deployment, see [AZURE_VM_DEPLOYMENT.md](AZURE_VM_DEPLOYMENT.md) for complete setup instructions.

## Running the Application

### Local Testing

For detailed local testing instructions, see **[LOCAL_TESTING.md](LOCAL_TESTING.md)**.

Quick start:
```bash
# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create .env file with your credentials (see LOCAL_TESTING.md)

# Run development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Note**: For webhook testing, you'll need a public URL. See [LOCAL_TESTING.md](LOCAL_TESTING.md) for options (ngrok, Cloudflare Tunnel, etc.).

### Production (Azure VM)

See [AZURE_VM_DEPLOYMENT.md](AZURE_VM_DEPLOYMENT.md) for complete deployment instructions. The application runs as a systemd service on Azure VM.

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

## Deployment

### Azure VM Deployment

For production deployment on Azure Virtual Machine, see the complete guide:

**[AZURE_VM_DEPLOYMENT.md](AZURE_VM_DEPLOYMENT.md)**

This guide includes:
- Azure VM setup and configuration
- Systemd service configuration
- Nginx reverse proxy setup
- SSL certificate installation (Let's Encrypt)
- Environment variables configuration
- Monitoring and troubleshooting

## Troubleshooting

### Webhook Validation Timeout

**Symptoms:** Microsoft Graph returns "validation timed out" when creating subscription.

**Root Causes:**
- Webhook endpoint responding too slowly (> 2 seconds)
- Network latency between Microsoft Graph and your endpoint
- Incorrect `WEBHOOK_NOTIFICATION_URL` configuration

**Solutions:**

1. **Verify webhook endpoint is accessible:**
   ```bash
   # Test validation endpoint
   curl "https://your-domain.com/webhook/notification?validationToken=test123"
   # Should return: test123
   ```

2. **Check diagnostics:**
   ```bash
   # Comprehensive health check
   curl https://your-domain.com/diagnostics/health
   
   # View configuration
   curl https://your-domain.com/diagnostics/config
   
   # List subscriptions with status
   curl https://your-domain.com/diagnostics/subscriptions
   ```

3. **Verify configuration:**
   - Ensure `WEBHOOK_NOTIFICATION_URL` is correctly set to your public endpoint
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

### Debugging Tips

1. **Check service logs (Azure VM):**
   ```bash
   # View real-time logs
   sudo journalctl -u teams-notion-api.service -f
   
   # View last 100 lines
   sudo journalctl -u teams-notion-api.service -n 100
   ```

2. **Test endpoints:**
   ```bash
   # Health check
   curl https://your-domain.com/health
   
   # Diagnostics
   curl https://your-domain.com/diagnostics/health
   curl https://your-domain.com/diagnostics/config
   ```

3. **Monitor subscriptions:**
   ```bash
   # List subscriptions with detailed status
   curl https://your-domain.com/diagnostics/subscriptions
   
   # Renew expiring subscriptions
   curl -X POST "https://your-domain.com/subscription/renew-all" \
     -H "Content-Type: application/json" \
     -d '{"expiration_days": 3}'
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
│   ├── subscription.py   # Subscription management
│   └── diagnostics.py   # Diagnostics and monitoring
├── utils/                 # Utility functions
│   ├── auth.py           # Authentication helpers
│   ├── validation.py     # User authorization
│   └── graph_subscriptions.py  # Subscription normalization
├── systemd/               # Systemd service configuration
│   └── teams-notion-api.service
├── deploy/                # Deployment scripts
│   └── deploy.sh         # Deployment automation script
├── requirements.txt       # Python dependencies
├── README.md             # This file
└── AZURE_VM_DEPLOYMENT.md # Azure VM deployment guide
```

## License

This project is provided as-is for integration purposes.
