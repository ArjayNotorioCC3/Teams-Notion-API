# Validation Timeout Optimizations

## Problem

Microsoft Graph validation requests are arriving ~10 seconds after subscription creation, causing validation timeouts. The endpoint responds quickly (0.02-0.04ms), but network latency between Microsoft Graph servers and the Azure VM is the bottleneck.

## Implemented Optimizations

### 1. Enhanced Logging and Timing

**Location**: `routes/webhooks.py`, `services/graph_service.py`

- Added detailed timing logs to track when validation requests arrive vs subscription creation
- Extracts request-id from validation tokens and Graph API error responses
- Calculates and logs network latency when validation requests arrive
- Tracks subscription creation times for latency analysis

**What you'll see in logs**:
```
NETWORK LATENCY DETECTED: Validation request arrived 10234.56ms (10.23s) after subscription creation for resource: /teams/.../messages. Request-ID: abc123
```

### 2. Optimized Nginx Configuration

**Location**: `deploy/nginx-optimized.conf`

- HTTP/2 support for faster connections
- Optimized SSL/TLS cipher suites
- Disabled proxy buffering for instant response
- Reduced connection timeouts
- Keepalive optimizations

**To apply**:
```bash
# On your VM
sudo cp deploy/nginx-optimized.conf /etc/nginx/sites-available/teams-notion-api
sudo nginx -t
sudo systemctl restart nginx
```

### 3. Rapid Retry Mode

**Location**: `routes/subscription.py`

- New `rapid_retry` query parameter for subscription creation
- Tries 15 attempts with short delays (0.5s initial, capped at 2s)
- Optimized for network latency issues

**Usage**:
```bash
curl -X POST "https://api.cc3solutions.com/subscription/create?rapid_retry=true&pre_warmup=true" \
  -H "Content-Type: application/json" \
  -d '{
    "resource": "teams/.../messages",
    "change_types": ["created"],
    "expiration_days": 0.04
  }'
```

### 4. Improved Retry Logic

**Location**: `services/graph_service.py`

- Increased default retries from 3 to 5
- Reduced initial delay from 2.0s to 1.0s
- Variable delay strategy: shorter for rapid mode, exponential for normal
- Better token refresh handling

**Default behavior**:
- Normal mode: 5 attempts with exponential backoff (1s, 2s, 4s, 8s, 10s max)
- Rapid mode: 15 attempts with shorter delays (0.5s, 0.75s, 1.125s, etc., capped at 2s)

### 5. Helper Script

**Location**: `deploy/create_subscription.sh`

A shell script that automates subscription creation with multiple retry attempts.

**Usage**:
```bash
# Basic usage
./deploy/create_subscription.sh

# With custom settings
RESOURCE="teams/.../messages" \
CHANGE_TYPES="created" \
EXPIRATION_DAYS="0.04" \
MAX_ATTEMPTS="20" \
RAPID_RETRY="true" \
./deploy/create_subscription.sh
```

**Environment variables**:
- `API_URL`: API base URL (default: `https://api.cc3solutions.com`)
- `RESOURCE`: Resource to subscribe to
- `CHANGE_TYPES`: Change types (default: `created`)
- `EXPIRATION_DAYS`: Expiration in days (default: `0.04` for ~1 hour)
- `MAX_ATTEMPTS`: Maximum retry attempts (default: `10`)
- `RAPID_RETRY`: Use rapid retry mode (default: `true`)

## Recommended Workflow

### For Network Latency Issues

1. **Use rapid retry mode**:
   ```bash
   curl -X POST "https://api.cc3solutions.com/subscription/create?rapid_retry=true&pre_warmup=true" \
     -H "Content-Type: application/json" \
     -d '{"resource": "...", "change_types": ["created"], "expiration_days": 0.04}'
   ```

2. **Or use the helper script**:
   ```bash
   ./deploy/create_subscription.sh
   ```

3. **Monitor logs** for network latency warnings:
   ```bash
   tail -f /var/log/your-app.log | grep "NETWORK LATENCY"
   ```

### For Normal Operations

Use the default endpoint (no rapid_retry parameter):
```bash
curl -X POST "https://api.cc3solutions.com/subscription/create?pre_warmup=true" \
  -H "Content-Type: application/json" \
  -d '{"resource": "...", "change_types": ["created"], "expiration_days": 3.0}'
```

## Understanding the Logs

### Successful Subscription Creation
```
INFO - Creating subscription for resource: /teams/.../messages
INFO - Successfully created subscription abc123 for resource /teams/.../messages in 1234.56ms
```

### Validation Timeout (Network Latency)
```
ERROR - Subscription validation timeout after 10000.00ms
WARNING - NETWORK LATENCY DETECTED: Validation request arrived 10234.56ms (10.23s) after subscription creation
```

### Rapid Retry Mode
```
INFO - Using rapid retry mode (15 attempts with short delays) for network latency issues
INFO - Retry attempt 2/15 after 0.50s delay
INFO - Retry attempt 3/15 after 0.75s delay
```

## Troubleshooting

### If validation still times out:

1. **Check network latency**:
   ```bash
   # From your VM
   ping graph.microsoft.com
   curl -w "@-" -o /dev/null -s https://graph.microsoft.com/v1.0/ <<'EOF'
        time_total:  %{time_total}\n
   EOF
   ```

2. **Try rapid retry mode** with more attempts:
   ```bash
   # Use helper script with more attempts
   MAX_ATTEMPTS=20 ./deploy/create_subscription.sh
   ```

3. **Check Nginx configuration**:
   ```bash
   sudo nginx -t
   sudo systemctl status nginx
   ```

4. **Verify endpoint is accessible**:
   ```bash
   curl "https://api.cc3solutions.com/webhook/notification?validationToken=test123"
   # Should return: test123
   ```

## Notes

- Network latency is a network routing issue, not a code issue
- The optimizations help work around the latency by:
  - Trying multiple times quickly (rapid retry)
  - Optimizing response speed (Nginx, endpoint)
  - Providing visibility (enhanced logging)
- If latency persists, consider:
  - Using Azure Traffic Manager or Application Gateway
  - Contacting Microsoft support about Graph API routing
  - Trying different Azure regions
