# Scale SERP Webhook Setup Guide

## Quick Setup Steps

### 1. Get your ngrok URL
Look for the ngrok window that just opened. You should see something like:
```
Session Status                online
Account                       your-email@example.com
Version                       3.x.x
Region                        United States (us)
Latency                       32ms
Web Interface                 http://127.0.0.1:4040
Forwarding                    https://1234-5678-90ab-cdef.ngrok-free.app -> http://localhost:8001
```

Copy the HTTPS forwarding URL (e.g., `https://1234-5678-90ab-cdef.ngrok-free.app`)

### 2. Add webhook URL to your .env file

Add this line to your `backend/.env` file:
```
SCALESERP_WEBHOOK_URL=https://YOUR-NGROK-URL.ngrok-free.app/api/v1/webhooks/scaleserp/batch-complete
```

Replace `YOUR-NGROK-URL` with your actual ngrok URL.

### 3. Restart Docker containers
```powershell
cd backend
docker-compose down
docker-compose up -d
```

### 4. Test the webhook endpoint
Once Docker is running, test that your webhook is accessible:
```powershell
curl https://YOUR-NGROK-URL.ngrok-free.app/api/v1/webhooks/health
```

You should get a response like:
```json
{
  "status": "healthy",
  "service": "webhook-handler",
  "timestamp": "2024-01-20T12:00:00.000000"
}
```

## How the Webhook Works

1. **Batch Creation**: When you create a Scale SERP batch, it includes your webhook URL
2. **Batch Completion**: When Scale SERP finishes processing, it sends a POST request to your webhook
3. **Automatic Processing**: Your webhook endpoint can automatically trigger further pipeline phases
4. **Real-time Updates**: No more polling - get instant notifications when results are ready

## Testing the Full Flow

1. Start a pipeline that creates SERP batches
2. Watch the ngrok Web Interface (http://127.0.0.1:4040) to see incoming webhooks
3. Check your logs for webhook processing

## Important Notes

- **ngrok URL changes**: Each time you restart ngrok (free plan), you get a new URL
- **Update .env**: Remember to update the webhook URL in .env when ngrok restarts
- **Keep ngrok running**: The webhook only works while ngrok is active
- **Production**: For production, use a permanent domain instead of ngrok

## Webhook Payload Example

Scale SERP sends a payload like this when a batch completes:
```json
{
  "request_info": {
    "type": "batch_resultset_completed"
  },
  "batch": {
    "id": "batch_123",
    "name": "Cylvy Pipeline Batch 20240120_120000",
    "status": "idle"
  },
  "result_set": {
    "id": 456,
    "searches_completed": 100,
    "searches_failed": 0,
    "download_links": {
      "json": {
        "pages": ["https://api.scaleserp.com/..."]
      }
    }
  }
}
```
