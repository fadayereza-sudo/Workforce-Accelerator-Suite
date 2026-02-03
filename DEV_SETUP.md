# Development Setup Guide

## Quick Start

When starting development, follow these steps:

### 1. Start ngrok (if not already running)
```bash
ngrok http 8000
```
Keep this terminal open. The ngrok URL stays the same as long as this keeps running.

### 2. Update the bot URL (only needed when ngrok restarts)
```bash
./dev.sh
```

Or manually:
```bash
python3 update_bot_url.py
```

This script automatically:
- ✅ Fetches your current ngrok URL
- ✅ Updates the dev bot's menu button via Telegram API
- ✅ Updates the `.env` file with the new `APP_URL`

### 3. Start/Restart the backend
```bash
cd backend
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

With `--reload`, the server auto-restarts when you change code.

---

## Daily Workflow

### When ngrok is ALREADY running:
Just restart the backend server. No need to run `update_bot_url.py` again.

### When ngrok restarts (computer restart, ngrok crashes, etc.):
1. Start ngrok: `ngrok http 8000`
2. Run: `./dev.sh`
3. Backend server can keep running (or restart it)

---

## Testing

- **Dev Bot**: `@apex_workforce_dev_bot` (points to your ngrok URL)
- **Prod Bot**: Points to Railway/production server

Both bots share the same Supabase database, so your test data persists.

---

## Troubleshooting

### "Could not connect to ngrok"
Make sure ngrok is running on port 4040 (default).

### "No HTTPS tunnel found"
Start ngrok with: `ngrok http 8000` (not `ngrok http ...` with other ports)

### Changes not appearing in Telegram
Clear the mini-app cache:
- **iOS**: Long-press mini-app → "Reload"
- **Android**: Settings → Data and Storage → Clear Web App Data

### Backend shows old APP_URL
Restart the backend server after running `update_bot_url.py`.
