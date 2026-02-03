#!/usr/bin/env python3
"""
Auto-update Telegram Bot menu button URL when ngrok restarts.
Run this after starting ngrok to sync the bot with the new URL.
"""
import os
import sys
import requests
from dotenv import load_dotenv, set_key

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_HUB_TOKEN")
ENV_FILE = ".env"

def get_ngrok_url():
    """Fetch the current ngrok public URL from the local API."""
    try:
        response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
        response.raise_for_status()
        tunnels = response.json()["tunnels"]

        # Find HTTPS tunnel
        for tunnel in tunnels:
            if tunnel["proto"] == "https":
                return tunnel["public_url"]

        print("❌ No HTTPS tunnel found. Make sure ngrok is running with: ngrok http 8000")
        return None
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to ngrok. Make sure ngrok is running on port 4040")
        return None
    except Exception as e:
        print(f"❌ Error fetching ngrok URL: {e}")
        return None


def update_bot_menu_button(bot_token, base_url):
    """Update the bot's menu button to point to the ngrok URL."""
    hub_url = f"{base_url}/static/mini-apps/hub/index.html"

    telegram_api_url = f"https://api.telegram.org/bot{bot_token}/setChatMenuButton"

    payload = {
        "menu_button": {
            "type": "web_app",
            "text": "Open Hub",
            "web_app": {
                "url": hub_url
            }
        }
    }

    try:
        response = requests.post(telegram_api_url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()

        if result.get("ok"):
            print(f"✅ Bot menu button updated successfully!")
            print(f"   Hub URL: {hub_url}")
            return True
        else:
            print(f"❌ Telegram API error: {result.get('description')}")
            return False
    except Exception as e:
        print(f"❌ Error updating bot: {e}")
        return False


def update_env_file(base_url):
    """Update APP_URL in .env file."""
    try:
        set_key(ENV_FILE, "APP_URL", base_url)
        print(f"✅ Updated {ENV_FILE} with APP_URL={base_url}")
        return True
    except Exception as e:
        print(f"❌ Error updating .env file: {e}")
        return False


def main():
    print("🔄 Fetching ngrok URL...")
    ngrok_url = get_ngrok_url()

    if not ngrok_url:
        sys.exit(1)

    print(f"📡 Ngrok URL: {ngrok_url}")
    print()

    if not BOT_TOKEN:
        print("❌ BOT_HUB_TOKEN not found in .env file")
        sys.exit(1)

    print("🤖 Updating Telegram bot menu button...")
    success_bot = update_bot_menu_button(BOT_TOKEN, ngrok_url)

    print()
    print("📝 Updating .env file...")
    success_env = update_env_file(ngrok_url)

    print()
    if success_bot and success_env:
        print("✨ All done! Your dev bot is now configured.")
        print("   Restart the backend server to pick up the new APP_URL")
        print(f"   or just keep it running - it uses the ngrok URL: {ngrok_url}")
    else:
        print("⚠️  Some steps failed. Check the errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
