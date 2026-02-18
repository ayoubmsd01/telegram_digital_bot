#!/bin/bash

# Telegram Bot Launcher with Duplicate Prevention
# This script ensures only one instance runs at a time

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# PID files
BOT_PID_FILE="$SCRIPT_DIR/.bot.pid"
WEBHOOK_PID_FILE="$SCRIPT_DIR/.webhook.pid"
LOCK_FILE="$SCRIPT_DIR/.bot.lock"

LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

BOT_LOG="$LOG_DIR/bot.log"
WEBHOOK_LOG="$LOG_DIR/webhook.log"
SUPERVISOR_LOG="$LOG_DIR/supervisor.log"

# Check if already running
if [ -f "$LOCK_FILE" ]; then
    echo "Bot is already running. Use './stop_bot.sh' to stop it first."
    exit 1
fi

# Create lock file
touch "$LOCK_FILE"

echo "======================================" | tee -a "$SUPERVISOR_LOG"
echo "Bot Supervisor Started: $(date)" | tee -a "$SUPERVISOR_LOG"
echo "======================================" | tee -a "$SUPERVISOR_LOG"

# Kill any existing instances (safety measure)
echo "[$(date)] Stopping any existing instances..." | tee -a "$SUPERVISOR_LOG"
pkill -9 -f "python3 bot.py" 2>/dev/null || true
pkill -9 -f "python3 webhook_server.py" 2>/dev/null || true
pkill -9 -f "./watchdog.sh" 2>/dev/null || true
sleep 2

# Start bot
echo "[$(date)] Starting bot.py..." | tee -a "$SUPERVISOR_LOG"
nohup python3 bot.py >> "$BOT_LOG" 2>&1 &
BOT_PID=$!
echo $BOT_PID > "$BOT_PID_FILE"
echo "[$(date)] Bot started with PID: $BOT_PID" | tee -a "$SUPERVISOR_LOG"

# Wait a moment for bot to initialize
sleep 3

# Start webhook server
echo "[$(date)] Starting webhook_server.py..." | tee -a "$SUPERVISOR_LOG"
nohup python3 webhook_server.py >> "$WEBHOOK_LOG" 2>&1 &
WEBHOOK_PID=$!
echo $WEBHOOK_PID > "$WEBHOOK_PID_FILE"
echo "[$(date)] Webhook server started with PID: $WEBHOOK_PID" | tee -a "$SUPERVISOR_LOG"

# Start watchdog in background
echo "[$(date)] Starting watchdog..." | tee -a "$SUPERVISOR_LOG"
nohup ./watchdog.sh >> "$LOG_DIR/watchdog.log" 2>&1 &
echo "[$(date)] Watchdog started" | tee -a "$SUPERVISOR_LOG"

echo "" | tee -a "$SUPERVISOR_LOG"
echo "✅ All services started successfully!" | tee -a "$SUPERVISOR_LOG"
echo "" | tee -a "$SUPERVISOR_LOG"
echo "📊 Status:" | tee -a "$SUPERVISOR_LOG"
echo "  Bot PID: $BOT_PID" | tee -a "$SUPERVISOR_LOG"
echo "  Webhook PID: $WEBHOOK_PID" | tee -a "$SUPERVISOR_LOG"
echo "" | tee -a "$SUPERVISOR_LOG"
echo "📝 Logs:" | tee -a "$SUPERVISOR_LOG"
echo "  Bot: tail -f $BOT_LOG" | tee -a "$SUPERVISOR_LOG"
echo "  Webhook: tail -f $WEBHOOK_LOG" | tee -a "$SUPERVISOR_LOG"
echo "  Watchdog: tail -f $LOG_DIR/watchdog.log" | tee -a "$SUPERVISOR_LOG"
echo "" | tee -a "$SUPERVISOR_LOG"
echo "🛑 To stop: ./stop_bot.sh" | tee -a "$SUPERVISOR_LOG"
