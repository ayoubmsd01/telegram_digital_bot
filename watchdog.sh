#!/bin/bash

# Improved Bot Watchdog - Prevents duplicate instances

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Check if watchdog is already running
WATCH_PID_FILE="$SCRIPT_DIR/.watchdog.pid"
if [ -f "$WATCH_PID_FILE" ]; then
    OLD_PID=$(cat "$WATCH_PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "Watchdog is already running (PID: $OLD_PID)"
        exit 1
    fi
fi

# Save our PID
echo $$ > "$WATCH_PID_FILE"

LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
WATCHDOG_LOG="$LOG_DIR/watchdog.log"

echo "======================================" | tee -a "$WATCHDOG_LOG"
echo "Watchdog Started: $(date)" | tee -a "$WATCHDOG_LOG"
echo "PID: $$" | tee -a "$WATCHDOG_LOG"
echo "Checking every 60 seconds..." | tee -a "$WATCHDOG_LOG"
echo "======================================" | tee -a "$WATCHDOG_LOG"

# Function to check and restart bot.py (single instance only)
check_bot() {
    local bot_count=$(pgrep -fc "python3 bot.py")
    
    if [ "$bot_count" -eq 0 ]; then
        echo "[$(date)] ⚠️ Bot is DOWN! Restarting..." | tee -a "$WATCHDOG_LOG"
        nohup python3 bot.py >> "$LOG_DIR/bot.log" 2>&1 &
        echo "[$(date)] ✅ Bot restarted with PID: $!" | tee -a "$WATCHDOG_LOG"
    elif [ "$bot_count" -gt 1 ]; then
        echo "[$(date)] ⚠️ Multiple bot instances detected ($bot_count)! Killing all..." | tee -a "$WATCHDOG_LOG"
        pkill -9 -f "python3 bot.py"
        sleep 2
        nohup python3 bot.py >> "$LOG_DIR/bot.log" 2>&1 &
        echo "[$(date)] ✅ Bot restarted with PID: $!" | tee -a "$WATCHDOG_LOG"
    fi
}

# Function to check and restart webhook_server.py
check_webhook() {
    local webhook_count=$(pgrep -fc "python3 webhook_server.py")
    
    if [ "$webhook_count" -eq 0 ]; then
        echo "[$(date)] ⚠️ Webhook server is DOWN! Restarting..." | tee -a "$WATCHDOG_LOG"
        nohup python3 webhook_server.py >> "$LOG_DIR/webhook.log" 2>&1 &
        echo "[$(date)] ✅ Webhook server restarted with PID: $!" | tee -a "$WATCHDOG_LOG"
    elif [ "$webhook_count" -gt 1 ]; then
        echo "[$(date)] ⚠️ Multiple webhook instances detected ($webhook_count)! Killing all..." | tee -a "$WATCHDOG_LOG"
        pkill -9 -f "python3 webhook_server.py"
        sleep 2
        nohup python3 webhook_server.py >> "$LOG_DIR/webhook.log" 2>&1 &
        echo "[$(date)] ✅ Webhook server restarted with PID: $!" | tee -a "$WATCHDOG_LOG"
    fi
}

# Cleanup on exit
trap "rm -f $WATCH_PID_FILE; exit" SIGINT SIGTERM EXIT

# Main monitoring loop
while true; do
    check_bot
    sleep 5
    check_webhook
    
    # Wait 60 seconds before next check
    sleep 55
done
