#!/bin/bash

# Check status of bot services

echo "📊 Telegram Bot Status"
echo "===================="
echo ""

# Check bot.py
if pgrep -f "python3 bot.py" > /dev/null; then
    BOT_PID=$(pgrep -f "python3 bot.py")
    echo "✅ Bot: RUNNING (PID: $BOT_PID)"
else
    echo "❌ Bot: STOPPED"
fi

# Check webhook_server.py
if pgrep -f "python3 webhook_server.py" > /dev/null; then
    WEBHOOK_PID=$(pgrep -f "python3 webhook_server.py")
    echo "✅ Webhook Server: RUNNING (PID: $WEBHOOK_PID)"
else
    echo "❌ Webhook Server: STOPPED"
fi

# Check watchdog
if pgrep -f "./watchdog.sh" > /dev/null; then
    WATCHDOG_PID=$(pgrep -f "./watchdog.sh")
    echo "✅ Watchdog: RUNNING (PID: $WATCHDOG_PID)"
else
    echo "❌ Watchdog: STOPPED"
fi

echo ""
echo "📝 Recent Log Entries:"
echo "--------------------"
if [ -f "logs/bot.log" ]; then
    echo "Last 5 lines from bot.log:"
    tail -5 logs/bot.log
fi
