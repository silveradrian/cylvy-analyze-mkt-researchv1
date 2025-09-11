# Webhook Improvements & Manual Resend Feature

## Overview

We've enhanced the Scale SERP integration with webhook support and reduced polling frequency, providing a more efficient and responsive system.

## Key Improvements

### 1. Webhook Resend Button
- **Location**: System Monitoring page (`/monitoring`) → Scale SERP Batches tab
- **Function**: Manually trigger Scale SERP to resend webhook notifications
- **Use Case**: Useful when webhook delivery fails or for manual pipeline initiation

### 2. Reduced Polling Frequency
- **Previous**: Checked every 60 seconds
- **Now**: Checks every 2 minutes (120 seconds)
- **Benefit**: Reduces API calls by 50% since webhooks handle real-time notifications

### 3. Webhook Configuration
- **Auto-detection**: System automatically detects if webhooks are configured
- **ngrok Support**: Automatically adds headers for ngrok free tier
- **Logging**: Enhanced logging shows whether webhooks are enabled

## API Endpoints

### Resend Webhook
```
POST /api/v1/webhooks/resend/{batch_id}/{result_set_id}
```

Example:
```bash
curl -X POST https://your-domain.com/api/v1/webhooks/resend/batch_123/1 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Get SERP Batches
```
GET /api/v1/monitoring/serp-batches
```

Returns list of recent SERP batches with their status and result sets.

## Frontend Integration

### Monitoring Dashboard
The System Monitoring page now shows:
- All recent SERP batches
- Batch status (idle, running, queued, failed)
- Progress bars for batch completion
- **"Resend Webhook" button** for completed batches

### How to Use
1. Navigate to http://localhost:3000/monitoring
2. Click on "Scale SERP Batches" tab
3. Find the batch you want to trigger
4. Click "Resend Webhook" button

## Technical Details

### Webhook Flow
```
1. Pipeline creates SERP batch
   ↓
2. Scale SERP processes searches
   ↓
3. Scale SERP sends webhook to ngrok URL
   ↓
4. Webhook handler processes results
   ↓
5. Pipeline continues with next phase
```

### Fallback Polling
Even with webhooks enabled, the system still polls as a fallback:
- **Frequency**: Every 2 minutes
- **Purpose**: Ensures batch completion even if webhook fails
- **Timeout**: 30 minutes maximum wait time

### Configuration

#### Environment Variables
```bash
# Webhook URL (set automatically when using ngrok)
SCALESERP_WEBHOOK_URL=https://your-ngrok-url.ngrok-free.app/api/v1/webhooks/scaleserp/batch-complete
```

#### ngrok Headers
For ngrok free tier, the system automatically adds:
```json
{
  "ngrok-skip-browser-warning": "true"
}
```

## Benefits

1. **Reduced API Calls**: 50% reduction in Scale SERP API polling
2. **Faster Response**: Immediate notification when batch completes
3. **Manual Control**: Ability to manually trigger webhook resend
4. **Better Monitoring**: Visual status of all SERP batches
5. **Fallback Safety**: Polling continues as backup

## Troubleshooting

### Webhook Not Received
1. Check ngrok is running: `ngrok http 8001`
2. Verify webhook URL in .env file
3. Check ngrok web interface: http://127.0.0.1:4040
4. Use "Resend Webhook" button to manually trigger

### Batch Stuck
If a batch appears stuck:
1. Check batch status in monitoring dashboard
2. Try "Resend Webhook" button
3. Check backend logs for errors
4. Fallback polling will eventually process it (max 30 min)

### ngrok Issues
- **Free tier warning page**: Handled automatically with headers
- **URL changes**: Update .env when restarting ngrok
- **Connection drops**: Restart ngrok and update URL

## Performance Metrics

- **Webhook delivery time**: ~1-2 seconds
- **Polling interval**: 2 minutes (reduced from 1 minute)
- **API call reduction**: 50% fewer Scale SERP status checks
- **User control**: Manual webhook resend available instantly
