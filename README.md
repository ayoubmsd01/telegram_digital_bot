# Telegram Digital Product Bot

This is a professional Telegram bot for selling digital products using CryptoBot for payments.

## Features
- Mandatory Language Selection (RU/EN).
- Automated Digital Delivery (Links, Codes, Files).
- Crypto Payments via Crypto Pay API.
- Stock Management.
- SQLite Database.

## Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   - Rename `.env.example` (or provided `.env`) and fill in your tokens.
   - `TELEGRAM_BOT_TOKEN`: From @BotFather.
   - `CRYPTO_PAY_API_TOKEN`: From @CryptoBot (mainnet) or @CryptoTestnetBot (testnet).
   - `WEBHOOK_SECRET_PATH`: A secret path for your webhook (e.g., `my-secret-path`).

3. **Database Initialization**:
   The database `shop.db` will be automatically created and seeded with sample products on the first run of `database.py`.
   You can manually init it by running:
   ```bash
   python database.py
   ```

## Running the Bot

You need to run two processes: the Telegram Bot (polling) and the Webhook Server (for payments).

### 1. Start the Webhook Server
This server listens for payment notifications from CryptoBot.
```bash
python webhook_server.py
```
*Note: You need to expose port 8000 to the internet (using ngrok or a VPS) and set the Webhook URL in your CryptoBot settings to `https://your-domain.com/YOUR_SECRET_PATH`.*

### 2. Start the Telegram Bot
This process handles user interactions.
```bash
python bot.py
```

## Adding Products
You can add products by editing the database directly or using a script.
Currently, `database.py` includes a `seed_products()` function that adds 3 sample products if the table is empty.

## Delivery Types
- `link`: Sends the configured link string.
- `code`: Sends the configured value as a copyable code block.
- `file`: Sends a file. Put files in the project directory or provide an absolute path, and set `delivery_value` to the file path.

## Deployment on Render/Railway
- Set the Environment Variables in the dashboard.
- Use a `Procfile` or start command: `python bot.py & python webhook_server.py` (simultaneous execution might require a process manager like `supervisord`).
- Better to deploy as two separate services or use a custom Docker container.
