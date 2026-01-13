# Azure VM Deployment Guide

Complete step-by-step instructions for deploying the Teams-Notion middleware to Azure Virtual Machine.

## Prerequisites

Before deploying, ensure you have:

1. **Azure Account** with active subscription
2. **Azure CLI** installed ([Install Guide](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli))
3. **SSH client** (built into Linux/macOS, use PuTTY or WSL on Windows)
4. **Git** installed
5. **Microsoft Azure App Registration** with Graph API permissions configured
6. **Notion Workspace** with database and integration token

## Step 1: Create Azure Virtual Machine

### Option A: Using Azure Portal

1. Go to [Azure Portal](https://portal.azure.com)
2. Click **"Create a resource"** → Search for **"Virtual Machine"** → Click **"Create"**
3. Fill in the basic settings:
   - **Subscription**: Select your subscription
   - **Resource Group**: Create new or select existing
   - **Virtual machine name**: `teams-notion-vm`
   - **Region**: Choose closest to your users
   - **Image**: **Ubuntu Server 22.04 LTS** (or latest LTS)
   - **Size**: **Standard_B1s** (1 vCPU, 1GB RAM) for testing, or **Standard_B2s** (2 vCPU, 4GB RAM) for production
   - **Authentication type**: **SSH public key** (recommended) or Password
   - **Username**: `azureuser` (or your choice)
   - **SSH public key**: Paste your public key or generate new
4. Click **"Review + create"** → **"Create"**
5. Wait for deployment to complete (2-3 minutes)

### Option B: Using Azure CLI

```bash
# Login to Azure
az login

# Set variables
RESOURCE_GROUP="teams-notion-rg"
VM_NAME="teams-notion-vm"
LOCATION="eastus"  # Change to your preferred region
VM_USER="azureuser"
VM_SIZE="Standard_B2s"  # 2 vCPU, 4GB RAM

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create virtual network (if needed)
az network vnet create \
  --resource-group $RESOURCE_GROUP \
  --name teams-notion-vnet \
  --address-prefix 10.0.0.0/16 \
  --subnet-name default \
  --subnet-prefix 10.0.1.0/24

# Create network security group with HTTP/HTTPS rules
az network nsg create \
  --resource-group $RESOURCE_GROUP \
  --name teams-notion-nsg

az network nsg rule create \
  --resource-group $RESOURCE_GROUP \
  --nsg-name teams-notion-nsg \
  --name AllowHTTP \
  --priority 1000 \
  --protocol Tcp \
  --destination-port-ranges 80

az network nsg rule create \
  --resource-group $RESOURCE_GROUP \
  --nsg-name teams-notion-nsg \
  --name AllowHTTPS \
  --priority 1001 \
  --protocol Tcp \
  --destination-port-ranges 443

az network nsg rule create \
  --resource-group $RESOURCE_GROUP \
  --nsg-name teams-notion-nsg \
  --name AllowSSH \
  --priority 1002 \
  --protocol Tcp \
  --destination-port-ranges 22

# Create public IP
az network public-ip create \
  --resource-group $RESOURCE_GROUP \
  --name teams-notion-ip \
  --allocation-method Static \
  --sku Standard

# Create VM
az vm create \
  --resource-group $RESOURCE_GROUP \
  --name $VM_NAME \
  --image Ubuntu2204 \
  --size $VM_SIZE \
  --admin-username $VM_USER \
  --generate-ssh-keys \
  --vnet-name teams-notion-vnet \
  --subnet default \
  --public-ip-address teams-notion-ip \
  --nsg teams-notion-nsg
```

## Step 2: Connect to VM and Initial Setup

### Get VM Public IP

**Using Azure Portal:**
1. Go to your VM → **"Overview"**
2. Copy the **"Public IP address"**

**Using Azure CLI:**
```bash
az vm show -d -g $RESOURCE_GROUP -n $VM_NAME --query publicIps -o tsv
```

### SSH into VM

```bash
# Replace with your VM's public IP and username
ssh azureuser@<VM_PUBLIC_IP>
```

### Update System and Install Dependencies

```bash
# Update package list
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip python3-venv git nginx certbot python3-certbot-nginx

# Verify Python version (should be 3.10 or higher)
python3 --version
```

## Step 3: Clone and Setup Application

```bash
# Create application directory
sudo mkdir -p /opt/teams-notion-api
sudo chown $USER:$USER /opt/teams-notion-api

# Clone repository (replace with your repo URL)
cd /opt
git clone https://github.com/your-username/teams-notion-api-dev.git teams-notion-api
cd teams-notion-api

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

## Step 4: Configure Environment Variables

```bash
# Create .env file
nano /opt/teams-notion-api/.env
```

Add the following content (replace with your actual values):

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
WEBHOOK_CLIENT_STATE=your_random_secret_string_here

# Optional: Default ticket status
DEFAULT_TICKET_STATUS=New

# Optional: Source identifier
TICKET_SOURCE=Teams
```

**Important**: Update `WEBHOOK_NOTIFICATION_URL` with your actual domain or VM's public IP after setting up domain/SSL.

Save and exit (Ctrl+X, then Y, then Enter).

## Step 5: Setup Systemd Service

```bash
# Copy systemd service file
sudo cp /opt/teams-notion-api/systemd/teams-notion-api.service /etc/systemd/system/

# Reload systemd to recognize new service
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable teams-notion-api.service

# Start the service
sudo systemctl start teams-notion-api.service

# Check service status
sudo systemctl status teams-notion-api.service
```

### View Service Logs

```bash
# View logs
sudo journalctl -u teams-notion-api.service -f

# View last 50 lines
sudo journalctl -u teams-notion-api.service -n 50
```

## Step 6: Configure Nginx Reverse Proxy (Recommended)

### Basic Nginx Configuration

```bash
# Create Nginx configuration
sudo nano /etc/nginx/sites-available/teams-notion-api
```

Add the following configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com;  # Replace with your domain or VM IP

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site:

```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/teams-notion-api /etc/nginx/sites-enabled/

# Remove default site (optional)
sudo rm /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t

# Restart Nginx
sudo systemctl restart nginx
```

## Step 7: Setup SSL Certificate (Let's Encrypt)

**Note**: Requires a domain name pointing to your VM's public IP.

```bash
# Install Certbot (if not already installed)
sudo apt install -y certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d your-domain.com

# Certbot will automatically configure Nginx and set up auto-renewal
```

### Verify SSL Auto-Renewal

```bash
# Test renewal process
sudo certbot renew --dry-run
```

## Step 8: Configure Firewall

```bash
# Allow HTTP, HTTPS, and SSH
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Check firewall status
sudo ufw status
```

## Step 9: Verify Deployment

### Test Health Endpoint

```bash
# Using VM's public IP
curl http://<VM_PUBLIC_IP>/health

# Or using domain (if configured)
curl https://your-domain.com/health

# Expected response: {"status":"healthy"}
```

### Test Root Endpoint

```bash
curl http://<VM_PUBLIC_IP>/

# Expected response: {"name":"Teams-Notion Webhook Middleware","version":"1.0.0","status":"running"}
```

### Test API Documentation

Open in browser:
- `http://<VM_PUBLIC_IP>/docs` - Swagger UI
- `http://<VM_PUBLIC_IP>/redoc` - ReDoc

## Step 10: Create Microsoft Graph Subscription

After deployment, create a subscription to monitor Teams messages:

```bash
# Set your VM URL (replace with your domain or IP)
VM_URL="https://your-domain.com"  # or http://<VM_PUBLIC_IP>

# Create subscription
curl -X POST "$VM_URL/subscription/create?pre_warmup=true" \
  -H "Content-Type: application/json" \
  -d '{
    "resource": "teams/{teamId}/channels/{channelId}/messages",
    "change_types": ["created"],
    "expiration_days": 0.04
  }'
```

**Note**: Replace `{teamId}` and `{channelId}` with your actual Teams team and channel IDs.

## Step 11: Setup Domain (Optional)

If you have a domain name:

1. **Add DNS A Record**:
   - Point your domain to the VM's public IP
   - Example: `api.yourdomain.com` → `<VM_PUBLIC_IP>`

2. **Update Environment Variables**:
   ```bash
   sudo nano /opt/teams-notion-api/.env
   # Update WEBHOOK_NOTIFICATION_URL to use your domain
   ```

3. **Restart Service**:
   ```bash
   sudo systemctl restart teams-notion-api.service
   ```

## Deployment Updates

To deploy updates:

```bash
# Option 1: Use deployment script (recommended)
sudo /opt/teams-notion-api/deploy/deploy.sh

# Option 2: Manual deployment
cd /opt/teams-notion-api
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart teams-notion-api.service
```

## Monitoring and Troubleshooting

### View Application Logs

```bash
# Real-time logs
sudo journalctl -u teams-notion-api.service -f

# Last 100 lines
sudo journalctl -u teams-notion-api.service -n 100

# Logs since today
sudo journalctl -u teams-notion-api.service --since today
```

### Check Service Status

```bash
# Service status
sudo systemctl status teams-notion-api.service

# Check if service is running
sudo systemctl is-active teams-notion-api.service

# Check if service is enabled (starts on boot)
sudo systemctl is-enabled teams-notion-api.service
```

### Common Issues

#### Issue: Service won't start

**Check logs:**
```bash
sudo journalctl -u teams-notion-api.service -n 50
```

**Common causes:**
- Missing environment variables in `.env` file
- Port 8000 already in use
- Python dependencies not installed
- Incorrect file permissions

**Solutions:**
```bash
# Check if port is in use
sudo netstat -tulpn | grep 8000

# Check file permissions
ls -la /opt/teams-notion-api

# Verify virtual environment
source /opt/teams-notion-api/venv/bin/activate
python -c "import fastapi; print('OK')"
```

#### Issue: Webhook validation timeout

**Symptoms**: "Subscription validation request timed out" error

**Solutions:**
1. Ensure `WEBHOOK_NOTIFICATION_URL` is correctly set to your domain/IP
2. Verify webhook endpoint responds quickly (< 2 seconds)
3. Test validation endpoint:
   ```bash
   curl "https://your-domain.com/webhook/notification?validationToken=test123"
   # Should return: test123
   ```
4. Check Nginx configuration allows proper proxying
5. Verify firewall allows HTTP/HTTPS traffic

#### Issue: Authentication errors

**Symptoms**: 401/403 errors from Microsoft Graph or Notion

**Solutions:**
1. Verify environment variables are set correctly:
   ```bash
   sudo cat /opt/teams-notion-api/.env
   ```
2. Check Azure App Registration permissions and admin consent
3. Verify Notion integration token and database access
4. Restart service after updating `.env`:
   ```bash
   sudo systemctl restart teams-notion-api.service
   ```

#### Issue: Nginx 502 Bad Gateway

**Solutions:**
1. Check if application is running:
   ```bash
   sudo systemctl status teams-notion-api.service
   ```
2. Verify application is listening on port 8000:
   ```bash
   curl http://127.0.0.1:8000/health
   ```
3. Check Nginx error logs:
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```

## Security Best Practices

1. **Keep System Updated**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

2. **Use SSH Keys** (not passwords) for VM access

3. **Configure Firewall**:
   - Only allow necessary ports (22, 80, 443)
   - Use Azure NSG for additional network-level security

4. **Protect Environment Variables**:
   ```bash
   # Set proper permissions on .env file
   sudo chmod 600 /opt/teams-notion-api/.env
   sudo chown www-data:www-data /opt/teams-notion-api/.env
   ```

5. **Enable Automatic Security Updates**:
   ```bash
   sudo apt install -y unattended-upgrades
   sudo dpkg-reconfigure -plow unattended-upgrades
   ```

6. **Use Azure Key Vault** (optional):
   - Store sensitive secrets in Azure Key Vault
   - Access from VM using managed identity

7. **Regular Backups**:
   - Backup `.env` file securely
   - Consider Azure Backup for VM snapshots

## Cost Optimization

### VM Size Recommendations

- **Development/Testing**: `Standard_B1s` (1 vCPU, 1GB RAM) - ~$7/month
- **Production (Low Traffic)**: `Standard_B2s` (2 vCPU, 4GB RAM) - ~$30/month
- **Production (Medium Traffic)**: `Standard_B2ms` (2 vCPU, 8GB RAM) - ~$60/month

### Cost-Saving Tips

1. **Use Reserved Instances** for 1-3 year commitments (save up to 72%)
2. **Stop VM when not in use** (development/testing)
3. **Use Spot Instances** for non-critical workloads (up to 90% savings)
4. **Monitor usage** with Azure Cost Management

## Next Steps

1. ✅ VM created and configured
2. ✅ Application deployed and running
3. ✅ Systemd service configured
4. ✅ Nginx reverse proxy setup
5. ✅ SSL certificate installed
6. ✅ Health endpoint responding
7. ✅ Create Microsoft Graph subscription
8. ✅ Test webhook notifications
9. ✅ Monitor logs and performance
10. ✅ Set up automated backups

## Support Resources

- [Azure VM Documentation](https://docs.microsoft.com/en-us/azure/virtual-machines/)
- [Ubuntu Server Guide](https://ubuntu.com/server/docs)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
