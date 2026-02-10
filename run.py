import subprocess
import time
import os
import signal
import sys

def main():
    print("Starting Telegram Digital Bot System...")
    
    # Start Webhook Server
    server_process = subprocess.Popen(
        [sys.executable, "webhook_server.py"],
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    print(f"Webhook Server started with PID: {server_process.pid}")
    
    # Start Telegram Bot
    bot_process = subprocess.Popen(
        [sys.executable, "bot.py"],
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    print(f"Telegram Bot started with PID: {bot_process.pid}")
    
    try:
        while True:
            time.sleep(1)
            if server_process.poll() is not None:
                print("Webhook Server stopped unexpectedly.")
                break
            if bot_process.poll() is not None:
                print("Telegram Bot stopped unexpectedly.")
                break
    except KeyboardInterrupt:
        print("\nStopping services...")
    finally:
        server_process.terminate()
        bot_process.terminate()
        server_process.wait()
        bot_process.wait()
        print("Services stopped.")

if __name__ == "__main__":
    main()
