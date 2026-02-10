from fastapi import FastAPI, Request, HTTPException
import uvicorn
import os
import hashlib
import hmac
from telegram import Bot
import database as db
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
WEBHOOK_SECRET_PATH = os.getenv("WEBHOOK_SECRET_PATH", "secret-path")
CRYPTO_PAY_TOKEN = os.getenv("CRYPTO_PAY_API_TOKEN")

if not CRYPTO_PAY_TOKEN:
    print("Warning: CRYPTO_PAY_API_TOKEN is missing")

bot = Bot(token=BOT_TOKEN)

def verify_signature(body: bytes, signature: str) -> bool:
    """
    Verify Crypto Pay signature.
    Signature is HMAC-SHA256 of the body with the sha256 of API token as key.
    """
    if not CRYPTO_PAY_TOKEN:
        return False
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
        raise HTTPException(status_code=403, detail="Invalid path")
    
    signature = request.headers.get("crypto-pay-api-signature")
    body = await request.body()
    try:
        body_text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid encoding")

    if signature:
        if not verify_signature(body, signature):
             print("Invalid signature")
             raise HTTPException(status_code=403, detail="Invalid signature")
    else:
        # If strict security, raise error. For now, log warning.
        print("Warning: No signature header received")

    try:
        update = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Process update
    if update.get("update_type") == "invoice_paid":
        payload = update.get("payload", {})
        invoice_id = payload.get("invoice_id")
        status = payload.get("status")

        if status == "paid":
            # Check order in DB
            order = db.get_order_by_invoice(invoice_id)
            if not order:
                print(f"Order not found for invoice {invoice_id}")
                return {"ok": True}
            
            if order["status"] == "paid":
                 return {"ok": True}
                 
            # Get product and user info needed for stock/delivery logic
            product_id = order["product_id"]
            user_id = order["user_id"]
            product = db.get_product(product_id)
            
            # Update order and handle stock
            if order["status"] == "canceled":
                 # It was auto-canceled but user paid. Re-decrease stock if possible.
                 if product["stock"] > 0:
                     db.decrease_stock(product_id)
                     db.update_order_status(order["order_id"], "paid")
                 else:
                     await bot.send_message(chat_id=user_id, text="alert: You paid but stock ran out due to timeout. Contact support.")
                     return {"ok": True}
            else:
                 # Normal flow: pending -> paid
                 # Stock was already reserved at creation.
                 db.update_order_status(order["order_id"], "paid")
            
            # Delivery (common code)
            
            # Determine language
            lang = db.get_user_language(user_id) or "en"
            
            delivery_type = product["delivery_type"]
            value = product["delivery_value"]
            
            msg_text = "🎁 Payment Received! Here is your product:\n\n"
            if lang == "ru":
                 msg_text = "🎁 Оплата получена! Вот ваш товар:\n\n"
                 
            try:
                if delivery_type == "link":
                    # Send URL link
                    await bot.send_message(chat_id=user_id, text=f"{msg_text}🔗 {value}")
                    
                elif delivery_type == "file":
                    # Send file using Telegram file_id
                    await bot.send_document(chat_id=user_id, document=value, caption=msg_text)
                    
                elif delivery_type == "code":
                    # Get one unused code for this product
                    code_row = db.get_unused_code(product_id)
                    
                    if code_row:
                        # Mark code as used
                        db.mark_code_as_used(code_row["id"], user_id)
                        
                        # Send code to user
                        code_text = code_row["code"]
                        await bot.send_message(
                            chat_id=user_id, 
                            text=f"{msg_text}🔑 Your code:\n<code>{code_text}</code>", 
                            parse_mode="HTML"
                        )
                    else:
                        # No codes available
                        await bot.send_message(
                            chat_id=user_id, 
                            text="⚠️ No codes available for this product. Please contact support."
                        )
                        
                # Mark order as delivered
                db.update_order_status(order["order_id"], "delivered")
                
            except Exception as e:
                print(f"Failed to deliver: {e}")
                logger.error(f"Delivery error: {e}")
                
    return {"ok": True}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
