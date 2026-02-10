# Deploying Telegram Digital Bot on Railway 🚂

Follow these steps to deploy your bot for free (or cheap) on Railway.

## 1. Prepare Your GitHub Repository
1. Create a new repository on GitHub (e.g., `my-telegram-bot`).
2. Push the contents of the `telegram_digital_bot` folder to this repository.
   ```bash
   cd telegram_digital_bot
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/my-telegram-bot.git
   git push -u origin main
   ```
   *(Replace with your actual repo URL)*

## 2. Create Project on Railway
1. Go to [Railway Dashboard](https://railway.app/new).
2. Click **"Deploy from GitHub repo"**.
3. Select the repository you just created.
4. Click **"Deploy Now"**.

## 3. Set Environment Variables
Railway needs your secrets to work. Go to the **Variables** tab in your project and add these:

| Variable Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | `8545248106:AAGALMHtUf5YCcbkx4DzVOmn_AiBQhlYE1Q` |
| `CRYPTO_PAY_API_TOKEN`| `529374:AA5KrDFfBrTNECHTRiMBO273tffcfWZHOg6` |
| `CRYPTO_BOT_NET` | `mainnet` |
| `WEBHOOK_SECRET_PATH` | `secret-path` |
| `WEBHOOK_URL` | `https://your-railway-app-url.up.railway.app` *(See step 4)* |
| `DB_PATH` | `/app/data/shop.db` *(Optional, for persistence)* |

## 4. Configure Webhook URL
1. Once deployed, Railway will generate a domain for you (e.g., `web-production-xyz.up.railway.app`).
2. Go to **Settings** -> **Domains** to see/copy it.
3. Go back to **Variables** and update `WEBHOOK_URL` with this domain:  
   `https://web-production-xyz.up.railway.app`
4. Railway will redeploy automatically.

## 5. Enable Persistent Storage (Optional but Recommended)
By default, Railway wipes files on restart. To keep your database (`shop.db`):
1. In Railway, go to your service settings.
2. Add a **Volume**.
3. Mount path: `/app/data` (matches `DB_PATH` above).
4. Redeploy.

## Troubleshooting
- If the build fails, check the **Build Logs**.
- If the bot starts but crashes, check the **Deploy Logs**.
- Ensure `requirements.txt` has all dependencies (we updated it for you).

## Cost
Railway offers a trial but eventually is paid. Alternatively, you can use **Render.com** (similar steps) or a VPS.
