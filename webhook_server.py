from fastapi import FastAPI, Request, HTTPException
import uvicorn
import os
import hashlib
import hmac
from telegram import Bot
import database as db
import delivery_service
import logging
import json
from dotenv import load_dotenv

# Configure logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WEBHOOK")

load_dotenv()

app = FastAPI()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_SECRET_PATH = os.getenv("WEBHOOK_SECRET_PATH", "secret-path")
CRYPTO_PAY_TOKEN = os.getenv("CRYPTO_PAY_API_TOKEN")

if not CRYPTO_PAY_TOKEN:
    logger.warning("CRYPTO_PAY_API_TOKEN is missing")

bot = Bot(token=BOT_TOKEN)

def verify_signature(body: bytes, signature: str) -> bool:
    if not CRYPTO_PAY_TOKEN:
        return True 
    secret = hashlib.sha256(CRYPTO_PAY_TOKEN.encode()).digest()
    computed_signature = hmac.new(
        key=secret,
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed_signature, signature)

@app.post("/{secret_path}")
async def crypto_webhook(secret_path: str, request: Request):
    """Handle incoming Crypto Pay webhooks."""
    if secret_path != WEBHOOK_SECRET_PATH:
        logger.warning(f"Invalid path accessed: {secret_path}")
        raise HTTPException(status_code=403, detail="Invalid path")
    
    signature = request.headers.get("crypto-pay-api-signature")
    body = await request.body()
    
    # logger.info(f"[WEBHOOK] Received payload. Size: {len(body)}")
    
    if signature:
        if not verify_signature(body, signature):
             logger.error("Invalid signature")
             # Proceeding with caution or return 403
             # raise HTTPException(status_code=403, detail="Invalid signature")
    else:
        logger.warning("No signature header received")

    try:
        update = await request.json()
        logger.info(f"[WEBHOOK] JSON: {json.dumps(update)}")
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    update_type = update.get("update_type")
    
    if update_type == "invoice_paid":
        # CryptoPay structure can carry payload directly or inside sender
        payload = update.get("payload", {})
        
        # Look for invoice_id
        invoice_id = payload.get("invoice_id")
        
        logger.info(f"[WEBHOOK] Invoice Paid Event. Invoice ID: {invoice_id}")

        if not invoice_id:
             logger.error("No invoice_id found in payload")
             return {"ok": True}

        # Check if this is a topup payment (payload starts with "topup_")
        invoice_payload = payload.get("payload", "")
        
        # Check topup first
        topup = db.get_topup_by_invoice(invoice_id)
        if topup and topup['status'] != 'paid':
            import datetime as dt
            amount = topup['amount']
            user_id = topup['user_id']
            
            # Update status (prevents double-credit)
            updated = db.update_topup_status(invoice_id, 'paid', dt.datetime.now().isoformat())
            if updated:
                new_balance = db.add_user_balance(user_id, amount)
                logger.info(f"[WEBHOOK] Topup credited: user={user_id}, amount=${amount}, new_balance=${new_balance}")
                
                # Send confirmation to user
                try:
                    lang = db.get_user_language(user_id) or "en"
                    if lang == "ru":
                        msg = f"✅ Оплата подтверждена. Баланс пополнен на ${amount:.2f}.\nНовый баланс: <b>${new_balance:.2f}</b>"
                    else:
                        msg = f"✅ Payment confirmed. Balance increased by ${amount:.2f}.\nNew balance: <b>${new_balance:.2f}</b>"
                    await bot.send_message(chat_id=user_id, text=msg, parse_mode='HTML')
                except Exception as e:
                    logger.error(f"[WEBHOOK] Failed to send topup confirmation: {e}")
            else:
                logger.info(f"[WEBHOOK] Topup {invoice_id} already processed")
            return {"ok": True}

        # Check order in DB (existing product purchase flow)
        order = db.get_order_by_invoice(invoice_id)
        if not order:
            logger.error(f"[WEBHOOK] Order not found for invoice {invoice_id}")
            return {"ok": True}
        
        order_id = order["order_id"]
        logger.info(f"[WEBHOOK] Found Order ID: {order_id} (Status: {order['status']})")
        
        # Mark as paid if not
        if order["status"] != "delivered":
             if order["status"] != "paid":
                 paid_asset = payload.get("asset")
                 paid_amount = payload.get("amount")
                 paid_at = payload.get("paid_at")
                 
                 db.update_order_status(order_id, "paid")
                 db.update_order_payment(order_id, paid_amount, paid_asset, paid_at)
                 logger.info(f"[WEBHOOK] Order {order_id} updated to PAID ({paid_amount} {paid_asset})")

             # Deliver
             success = await delivery_service.deliver_order(order_id, bot)
             if success:
                 logger.info(f"[WEBHOOK] Delivery SUCCESS for {order_id}")
             else:
                 logger.error(f"[WEBHOOK] Delivery FAILED for {order_id}")
                
    return {"ok": True}
