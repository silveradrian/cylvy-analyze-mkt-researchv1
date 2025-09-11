# Frontend Testing Guide

## Quick Access URLs

All frontend pages have auto-login functionality built in. Simply navigate to these URLs:

### Main Pages
- **Home**: http://localhost:3000/
- **Setup Wizard**: http://localhost:3000/setup
- **Pipeline Management**: http://localhost:3000/pipeline
- **Pipeline Schedules**: http://localhost:3000/pipeline-schedules
- **Digital Landscapes**: http://localhost:3000/landscapes
- **Custom Dimensions**: http://localhost:3000/dimensions
- **Settings**: http://localhost:3000/settings
- **System Monitoring**: http://localhost:3000/monitoring

## Troubleshooting Login Issues

### 1. Clear Browser Cache
If you're being redirected to login:
1. Open Developer Tools (F12)
2. Go to Application tab
3. Clear Local Storage
4. Delete any `access_token` entries
5. Refresh the page

### 2. Check Console for Auto-Login
Open browser console (F12) and look for:
- `🔐 Attempting auto-login with admin@cylvy.com...`
- `✅ Auto-login successful`

### 3. Manual Login (if needed)
- Email: `admin@cylvy.com`
- Password: `admin123`

## Webhook Setup Summary

✅ **ngrok is running**: https://96b19dbdc912.ngrok-free.app
✅ **Webhook URL configured**: Added to your .env file
✅ **Backend updated**: ngrok headers automatically added for free tier
✅ **Health check working**: /api/v1/webhooks/health responds correctly

## Testing the Full Pipeline

1. **Start a Pipeline**:
   - Go to http://localhost:3000/pipeline
   - Click "Start Analysis Pipeline"
   - Configure your options
   - Start the pipeline

2. **Monitor Progress**:
   - Watch real-time updates on the pipeline page
   - Check http://localhost:3000/monitoring for system status
   - View ngrok inspector at http://127.0.0.1:4040 for webhook calls

3. **View Results**:
   - Pipeline results appear in the history tab
   - Check individual phase results
   - Monitor Scale SERP batch progress

## Important Notes

- **ngrok URL changes**: When you restart ngrok, update the webhook URL in .env
- **Keep ngrok running**: The webhook only works while ngrok is active
- **Browser vs API**: The warning page only affects browsers, not API calls with proper headers

