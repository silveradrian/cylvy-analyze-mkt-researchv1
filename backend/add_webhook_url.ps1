# PowerShell script to add webhook URL to .env file

Write-Host "🔧 Scale SERP Webhook Configuration" -ForegroundColor Green
Write-Host "===================================" -ForegroundColor Green
Write-Host ""

# Check ngrok window
Write-Host "📌 Please check your ngrok window for the HTTPS forwarding URL" -ForegroundColor Yellow
Write-Host "   It should look like: https://1234-5678-90ab-cdef.ngrok-free.app" -ForegroundColor Yellow
Write-Host ""

# Get ngrok URL
$ngrokUrl = Read-Host "Enter your ngrok HTTPS URL"

# Validate URL
if (-not $ngrokUrl.StartsWith("https://")) {
    Write-Host "❌ Error: URL must start with https://" -ForegroundColor Red
    exit 1
}

# Construct webhook URL
$webhookUrl = "$ngrokUrl/api/v1/webhooks/scaleserp/batch-complete"

Write-Host ""
Write-Host "✅ Full webhook URL: $webhookUrl" -ForegroundColor Green
Write-Host ""

# Add to .env file
Write-Host "📝 Add this line to your backend/.env file:" -ForegroundColor Cyan
Write-Host ""
Write-Host "SCALESERP_WEBHOOK_URL=$webhookUrl" -ForegroundColor White
Write-Host ""

# Test instructions
Write-Host "📋 Next steps:" -ForegroundColor Yellow
Write-Host "1. Add the above line to your backend/.env file" -ForegroundColor White
Write-Host "2. Restart Docker: docker-compose down && docker-compose up -d" -ForegroundColor White
Write-Host "3. Test webhook: curl $ngrokUrl/api/v1/webhooks/health" -ForegroundColor White
Write-Host ""
Write-Host "⚠️  Remember: ngrok URL changes when restarted (free plan)" -ForegroundColor Yellow

