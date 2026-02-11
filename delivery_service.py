import database as db
import logging

logger = logging.getLogger(__name__)

async def deliver_order(order_id: int, bot):
    """
    Deliver product to user and update order status.
    Idempotent: checks if already delivered.
    """
    print(f"[DELIVERY] Starting delivery for order_id={order_id}")
    
    order = db.get_order(order_id)
    if not order:
        print(f"[DELIVERY] Order {order_id} not found")
        return False
        
    if order['status'] == 'delivered':
        print(f"[DELIVERY] Order {order_id} already delivered")
        return True
        
    user_id = order['user_id']
    product_id = order['product_id']
    
    product = db.get_product(product_id)
    if not product:
        print(f"[DELIVERY] Product {product_id} not found")
        return False
        
    lang = db.get_user_language(user_id) or "en"
    delivery_type = product['delivery_type']
    value = product['delivery_value']
    
    title = product['title_ru'] if lang == 'ru' else product['title_en']
    
    # Message templates
    if lang == 'ru':
        msg_header = f"✅ Оплата подтверждена! Отправляю товар...\n📦 <b>{title}</b>\n\n"
        msg_done = "✅ Готово! Вот ваш товар:"
        msg_no_code = "⚠️ К сожалению, коды закончились. Пожалуйста, свяжитесь с поддержкой."
    else:
        msg_header = f"✅ Payment confirmed! Delivering...\n📦 <b>{title}</b>\n\n"
        msg_done = "✅ Done! Here is your product:"
        msg_no_code = "⚠️ Sorry, out of stock (no codes). Please contact support."

    # 1. Notify user that delivery started
    try:
        await bot.send_message(chat_id=user_id, text=msg_header, parse_mode='HTML')
    except Exception as e:
        # Determine if user blocked bot, etc.
        print(f"[DELIVERY] Failed to send header: {e}")

    try:
        # 2. Perform Delivery
        if delivery_type == 'link':
            await bot.send_message(chat_id=user_id, text=f"{msg_done}\n🔗 {value}")
            
        elif delivery_type == 'file':
            await bot.send_document(chat_id=user_id, document=value, caption=msg_done)
            
        elif delivery_type == 'code':
            code_row = db.get_unused_code(product_id)
            if code_row:
                # Mark used
                db.mark_code_as_used(code_row['id'], user_id)
                # Remove from stock if it hasn't been done (Code products stock management is usually implicit by count of codes, but we also have 'stock' column)
                # In current logic, stock is decreased at order creation (reservation).
                # But for codes, we need to pick a SPECIFIC code.
                
                code_text = code_row['code']
                await bot.send_message(
                    chat_id=user_id, 
                    text=f"{msg_done}\n\n<code>{code_text}</code>", 
                    parse_mode='HTML'
                )
            else:
                await bot.send_message(chat_id=user_id, text=msg_no_code)
                print(f"[DELIVERY] No codes for product {product_id}")
                return False

        # 3. Update DB
        db.update_order_status(order_id, 'delivered')
        print(f"[DELIVERY] Order {order_id} marked as delivered")
        return True
        
    except Exception as e:
        print(f"[DELIVERY] Failed to deliver: {e}")
        import traceback
        traceback.print_exc()
        return False
