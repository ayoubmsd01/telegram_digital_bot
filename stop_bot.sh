#!/bin/bash

# Stop all bot services

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

LOCK_FILE="$SCRIPT_DIR/.bot.lock"
BOT_PID_FILE="$SCRIPT_DIR/.bot.pid"
WEBHOOK_PID_FILE="$SCRIPT_DIR/.webhook.pid"
WATCHDOG_PID_FILE="$SCRIPT_DIR/.watchdog.pid"

echo "🛑 Stopping Telegram Bot Services..."

# Kill watchdog first
pkill -9 -f "./watchdog.sh" 2>/dev/null || true
sleep 1

# Kill bot.py
pkill -9 -f "python3 bot.py" 2>/dev/null || true
sleep 1

# Kill webhook_server.py
pkill -9 -f "python3 webhook_server.py" 2>/dev/null || true
sleep 1

# Remove lock and PID files
rm -f "$LOCK_FILE"
rm -f "$BOT_PID_FILE"
rm -f "$WEBHOOK_PID_FILE"
rm -f "$WATCHDOG_PID_FILE"

echo "✅ All services stopped"

# Verify
if pgrep -f "python3 bot.py" > /dev/null || pgrep -f "python3 webhook_server.py" > /dev/null || pgrep -f "./watchdog.sh" > /dev/null; then
    echo "⚠️ Warning: Some processes may still be running"
    ps aux | grep -E "(bot.py|webhook_server.py|watchdog.sh)" | grep -v grep
else
    echo "✓ All processes confirmed stopped"
fi
