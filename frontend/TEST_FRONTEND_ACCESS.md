# Testing Frontend Access

## Problem
You're being redirected to a login screen when trying to access the setup wizard and pipeline management pages.

## Solution

The frontend pages have auto-login functionality built in, but sometimes the browser cache can interfere. Here's how to test:

### 1. Clear Browser Cache and Local Storage
1. Open your browser developer tools (F12)
2. Go to the Application tab
3. Clear Local Storage for http://localhost:3000
4. Delete any stored `access_token`

### 2. Direct Access URLs

Try accessing these URLs directly:

- **Home Page**: http://localhost:3000/
  - This should show the main menu with all options
  - Shows admin credentials: admin@cylvy.com / admin123

- **Setup Wizard**: http://localhost:3000/setup
  - Should auto-login and show the setup wizard

- **Pipeline Management**: http://localhost:3000/pipeline
  - Should auto-login and show pipeline management

- **Pipeline Schedules**: http://localhost:3000/pipeline-schedules
  - Should auto-login and show scheduling options

### 3. Check Console for Auto-Login Messages

Open browser developer console (F12) and look for these messages:
- `🔐 Attempting auto-login with admin@cylvy.com...`
- `✅ Auto-login successful`

If you see `❌ Auto-login failed`, check that:
1. Backend is running on http://localhost:8001
2. The admin user exists in the database
3. No CORS issues

### 4. Manual Test

If auto-login still fails, the credentials are:
- Email: `admin@cylvy.com`
- Password: `admin123`

### 5. Backend Health Check

Test if the backend is accessible:
```powershell
Invoke-RestMethod -Uri "http://localhost:8001/docs"
```

This should open the API documentation page.

