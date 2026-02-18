#!/usr/bin/env python3

import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    print("❌ TELEGRAM_BOT_TOKEN not found in .env")
    exit(1)

# Delete webhook
url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook?drop_pending_updates=true"
response = requests.get(url)

if response.status_code == 200:
    print("✅ Webhook deleted successfully")
    print(f"Response: {response.json()}")
else:
    print(f"❌ Failed to delete webhook: {response.text}")

# Get webhook info
info_url = f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo"
info_response = requests.get(info_url)

if info_response.status_code == 200:
    info = info_response.json()
    print("\n📊 Current Webhook Info:")
    print(f"URL: {info['result'].get('url', 'None')}")
    print(f"Pending Updates: {info['result'].get('pending_update_count', 0)}")
else:
    print(f"❌ Failed to get webhook info: {info_response.text}")
