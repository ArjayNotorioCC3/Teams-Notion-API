#!/bin/bash

# Helper script for creating Microsoft Graph subscriptions with retry logic
# This script attempts to create a subscription multiple times to work around network latency issues

set -e

# Configuration
API_URL="${API_URL:-https://api.cc3solutions.com}"
RESOURCE="${RESOURCE:-teams/991d8fe3-2e18-45a1-a131-69dbf4966c98/channels/19:QwI2SPr-5d4d15q_BPlpIrf0KS_SCuDgIHBNp45HwMI1@thread.tacv2/messages}"
CHANGE_TYPES="${CHANGE_TYPES:-created}"
EXPIRATION_DAYS="${EXPIRATION_DAYS:-0.04}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-10}"
RAPID_RETRY="${RAPID_RETRY:-true}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Microsoft Graph Subscription Creator"
echo "=========================================="
echo "API URL: $API_URL"
echo "Resource: $RESOURCE"
echo "Change Types: $CHANGE_TYPES"
echo "Expiration Days: $EXPIRATION_DAYS"
echo "Max Attempts: $MAX_ATTEMPTS"
echo "Rapid Retry: $RAPID_RETRY"
echo "=========================================="
echo ""

# Function to create subscription
create_subscription() {
    local attempt=$1
    local rapid_retry_flag=""
    
    if [ "$RAPID_RETRY" = "true" ]; then
        rapid_retry_flag="?rapid_retry=true&pre_warmup=true"
    else
        rapid_retry_flag="?pre_warmup=true"
    fi
    
    echo -e "${YELLOW}Attempt $attempt/$MAX_ATTEMPTS: Creating subscription...${NC}"
    
    response=$(curl -s -w "\n%{http_code}" -X POST \
        "${API_URL}/subscription/create${rapid_retry_flag}" \
        -H "Content-Type: application/json" \
        -d "{
            \"resource\": \"${RESOURCE}\",
            \"change_types\": [\"${CHANGE_TYPES}\"],
            \"expiration_days\": ${EXPIRATION_DAYS}
        }")
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -eq 200 ] || [ "$http_code" -eq 201 ]; then
        echo -e "${GREEN}✓ Success! Subscription created.${NC}"
        echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
        return 0
    else
        echo -e "${RED}✗ Failed with HTTP $http_code${NC}"
        echo "$body" | python3 -m json.tool 2>/dev/null || echo "$body"
        return 1
    fi
}

# Main retry loop
success=false
for i in $(seq 1 $MAX_ATTEMPTS); do
    if create_subscription $i; then
        success=true
        break
    fi
    
    if [ $i -lt $MAX_ATTEMPTS ]; then
        if [ "$RAPID_RETRY" = "true" ]; then
            delay=$((i * 500))  # 500ms, 1s, 1.5s, etc.
            echo -e "${YELLOW}Waiting ${delay}ms before next attempt...${NC}"
            sleep $(echo "scale=2; $delay / 1000" | bc)
        else
            delay=$((i * 2))  # 2s, 4s, 6s, etc.
            echo -e "${YELLOW}Waiting ${delay}s before next attempt...${NC}"
            sleep $delay
        fi
        echo ""
    fi
done

echo ""
echo "=========================================="
if [ "$success" = true ]; then
    echo -e "${GREEN}✓ Subscription creation succeeded!${NC}"
    exit 0
else
    echo -e "${RED}✗ Subscription creation failed after $MAX_ATTEMPTS attempts${NC}"
    echo ""
    echo "Troubleshooting tips:"
    echo "1. Check network connectivity to Microsoft Graph"
    echo "2. Verify webhook endpoint is accessible: curl ${API_URL}/health"
    echo "3. Check application logs for validation timeout errors"
    echo "4. Try increasing MAX_ATTEMPTS or using rapid_retry=false"
    exit 1
fi
