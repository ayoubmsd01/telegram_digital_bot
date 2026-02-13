import logging
import os
import asyncio
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
from dotenv import load_dotenv

import database as db
import strings
from crypto_pay import create_invoice
import admin_handlers

import delivery_service
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "").lower()

load_dotenv()

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Keyboards
LANG_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
     InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")]
])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    db_lang = db.get_user_language(user.id)
    
    if db_lang:
        # User already has language set, skip selection
        await show_main_menu(update, context, db_lang)
        
        # Check Stock Notification
        try:
            enabled = db.get_setting("stock_update_enabled")
            if enabled == "1":
                stock_msg = db.get_setting(f"stock_update_{db_lang}")
                if stock_msg:
                    await update.message.reply_text(stock_msg, parse_mode='HTML')
                    print(f"[STOCK_UPDATE] shown to user_id={user.id} in /start")
        except Exception as e:
            print(f"Error sending stock update: {e}")
    else:
        # First time user, ask for language
        await update.message.reply_text(
            "Welcome! Please choose your language.\nДобро пожаловать! Пожалуйста, выберите язык.",
            reply_markup=LANG_KEYBOARD
        )

async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle language selection."""
    query = update.callback_query
    await query.answer()
    
    lang = query.data.split("_")[1]
    user_id = query.from_user.id
    
    db.add_user(user_id, lang)
    
    await query.edit_message_text(text=f"Language set to {lang.upper()}")
    await show_main_menu(update, context, lang)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ad command to open admin panel."""
    await admin_handlers.admin_panel(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str):
    """Show the main menu keyboard."""
    user = update.effective_user
    
    text = strings.STRINGS[lang]["welcome"]
    keyboard = strings.KEYBOARDS[lang].copy()
    
    # Don't add Admin Panel button here - only via /ad command
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    elif update.callback_query:
        # If called from callback, we can't reply with ReplyKeyboard easily in edit_message, 
        # so we delete the old message or just send a new one.
        await update.callback_query.message.reply_text(text, reply_markup=reply_markup)

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle menu button clicks."""
    user_id = update.effective_user.id
    lang = db.get_user_language(user_id)
    if not lang:
        await start(update, context) # Fallback
        return

    text = update.message.text
    s = strings.STRINGS[lang]
    
    
    if text == s["menu_products"]:
        await show_products(update, context, lang)
    elif text == s["menu_stock"]:
        await show_stock(update, context, lang)
    elif text == s["menu_rules"]:
        await update.message.reply_text(s["rules_text"])
    elif text == s["menu_help"]:
        await update.message.reply_text(s["help_text"])
    elif text == s["menu_projects"]:
        await update.message.reply_text(s["projects_text"])
    elif text == s["back"] or text == "⬅️ Back":
        await show_main_menu(update, context, lang)
    else:
        # Unknown button, just ignore it
        pass

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str):
    products = db.get_products()
    s = strings.STRINGS[lang]
    
    if not products:
        await update.message.reply_text("No products available.")
        return

    keyboard = []
    for p in products:
        p_id = p["product_id"]
        title = p["title_ru"] if lang == "ru" else p["title_en"]
        price = p["price_usd"]
        stock = p["stock"]
        
        if stock > 0:
            btn_text = f"{title} - ${price}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"prod_{p_id}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(s["choose_product"], reply_markup=reply_markup)

async def show_stock(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str):
    # Check Published Stock Update
    try:
        enabled = db.get_setting("stock_update_enabled")
        if enabled == "1":
            stock_msg = db.get_setting(f"stock_update_{lang}")
            if stock_msg:
                 await update.message.reply_text(stock_msg, parse_mode='HTML')
                 print(f"[STOCK_UPDATE] shown to user_id={update.effective_user.id} lang={lang}")
                 return
    except Exception as e:
        print(f"Error sending stock update: {e}")

    products = db.get_products()
    s = strings.STRINGS[lang]
    msg = s["stock_title"] + "\n\n"
    
    for p in products:
        title = p["title_ru"] if lang == "ru" else p["title_en"]
        stock = p["stock"]
        msg += f"• {title}: {stock} pcs\n"
        
    await update.message.reply_text(msg)

async def product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    lang = db.get_user_language(user_id) or "en"
    s = strings.STRINGS[lang]

    if data.startswith("prod_"):
        p_id = int(data.split("_")[1])
        product = db.get_product(p_id)
        if not product:
            await query.edit_message_text("Product not found.")
            return

        title = product["title_ru"] if lang == "ru" else product["title_en"]
        desc = product["desc_ru"] if lang == "ru" else product["desc_en"]
        price = product["price_usd"]
        stock = product["stock"]
        
        if stock <= 0:
            await query.edit_message_text(s["out_of_stock"])
            return
            
        text = f"<b>{title}</b>\n\n{desc}\n\nPrice: ${price}\nStock: {stock}"
        
        keyboard = [
            [InlineKeyboardButton(s["buy_button"].format(price=price), callback_data=f"buy_{p_id}")],
            [InlineKeyboardButton(s["back"], callback_data="back_to_products")] 
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        
    elif data.startswith("buy_"):
        p_id = int(data.split("_")[1])
        product = db.get_product(p_id)
        
        if not product or product["stock"] <= 0:
            await query.message.reply_text(s["out_of_stock"])
            return

        # Decrease Stock immediately (Reservation)
        db.decrease_stock(p_id)

        try:
            invoice = create_invoice(
                amount=product["price_usd"],
                currency="USD",
                description=f"Buying {product['title_en']}",
                payload=f"{user_id}:{p_id}" 
            )
            
            if invoice and invoice.get("ok"):
                result = invoice["result"]
                invoice_id = result["invoice_id"]
                pay_url = result["pay_url"] # Or bot_invoice_url
                
                # Create Order in DB
                order_id = db.create_order(user_id, p_id, invoice_id, product["price_usd"])
                
                msg_text = (
                    f"🧾 <b>Invocie #{invoice_id}</b>\n"
                    f"📦 Product: {product['title_en']}\n"
                    f"💰 Price: ${product['price_usd']}\n\n"
                    f"⏳ Stock reserved for 15 minutes.\n"
                    f"✅ Please pay using the link below:"
                    if lang == "en" else
                    f"🧾 <b>Счет #{invoice_id}</b>\n"
                    f"📦 Товар: {product['title_ru']}\n"
                    f"💰 Цена: ${product['price_usd']}\n\n"
                    f"⏳ Товар зарезервирован на 15 минут.\n"
                    f"✅ Оплатите по ссылке ниже:"
                )
                
                check_btn_text = "✅ Check Payment" if lang != "ru" else "✅ Проверить оплату"
                keyboard = [
                    [InlineKeyboardButton(s["pay_link"], url=pay_url)],
                    [InlineKeyboardButton(check_btn_text, callback_data=f"checkpay:{order_id}")],
                    [InlineKeyboardButton("❌ Cancel Order / Отменить", callback_data=f"cancel_{order_id}_{invoice_id}")]
                ]
                await query.message.reply_text(msg_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            else:
                # Failed to create invoice, restore stock
                db.increase_stock(p_id)
                logger.error(f"Invoice creation failed: {invoice}")
                await query.message.reply_text("Error creating invoice. Please try again.")
        except Exception as e:
            # Restore stock on error
            db.increase_stock(p_id)
            logger.error(f"Error: {e}")
            await query.message.reply_text("System error.")

    elif data == "back_to_products":
        # Re-show product lists
        products = db.get_products()
        keyboard = []
        for p in products:
            p_id = p["product_id"]
            title = p["title_ru"] if lang == "ru" else p["title_en"]
            price = p["price_usd"]
            stock = p["stock"]
            if stock > 0:
                btn_text = f"{title} - ${price}"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"prod_{p_id}")])
        
        await query.edit_message_text(s["choose_product"], reply_markup=InlineKeyboardMarkup(keyboard))

async def cancel_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # format: cancel_{order_id}_{invoice_id}
    parts = data.split("_")
    order_id = int(parts[1])
    invoice_id = int(parts[2])
    
    # Cancel in DB and restore stock
    success = db.cancel_order_db(order_id)
    
    if success:
        # Delete invoice from CryptoBot
        from crypto_pay import delete_invoice
        try:
            delete_invoice(invoice_id)
        except:
            pass
        await query.edit_message_text(f"❌ Order #{order_id} canceled. Stock returned.")
    else:
        await query.edit_message_text("Order already processed or expired.")

async def check_expirations(context: ContextTypes.DEFAULT_TYPE):
    """Background task to cancel expired orders."""
    expired_orders = db.get_expired_pending_orders(minutes=15)
    for order in expired_orders:
        order_id = order["order_id"]
        invoice_id = order["invoice_id"]
        # Cancel logic
        if db.cancel_order_db(order_id):
            print(f"Auto-canceled expired order #{order_id}")
            # Try delete invoice
            from crypto_pay import delete_invoice
            try:
                delete_invoice(invoice_id)
            except:
                pass

async def check_pay_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    data = query.data
    try:
        order_id = int(data.split(":")[1])
    except ValueError:
        return

    order = db.get_order(order_id)
    if not order:
        await query.message.reply_text("❌ Order not found.")
        return

    if order['status'] == 'paid' or order['status'] == 'delivered':
        await delivery_service.deliver_order(order_id, context.bot)
        await query.message.reply_text("✅ Payment already confirmed! Check your messages.")
        return

    if order['status'] == 'canceled':
        await query.message.reply_text("❌ Order was canceled.")
        return

    # Check via CryptoPay API
    invoice_id = order['invoice_id']
    from crypto_pay import get_invoices
    
    try:
        print(f"Checking invoice {invoice_id} via API...")
        result = get_invoices(invoice_ids=invoice_id)
        
        is_paid = False
        if result and result.get('ok'):
            items = result['result'].get('items', [])
            if items:
                status = items[0]['status']
                print(f"Invoice {invoice_id} status: {status}")
                if status == 'paid':
                    is_paid = True
        
        if is_paid:
            if order['status'] == 'pending':
                db.update_order_status(order_id, 'paid')
                
            success = await delivery_service.deliver_order(order_id, context.bot)
            if success:
                # Edit original message to remove buttons ideally, but replying is safer
                await query.message.reply_text("✅ Payment confirmed! Delivering...")
            else:
                await query.message.reply_text("✅ Payment confirmed, but delivery failed. Contact support.")
        else:
            lang = db.get_user_language(order['user_id']) or "en"
            msg = "⏳ Payment not received yet. Please try again." if lang != 'ru' else "⏳ Оплата ещё не поступила. Попробуйте позже."
            await query.message.reply_text(msg)
            
    except Exception as e:
        print(f"Check payment exception: {e}")
        await query.message.reply_text("❌ Error checking payment status.")

async def post_init(application: Application) -> None:
    # Use create_task on the loop
    application.create_task(background_expiration_loop())

async def background_expiration_loop():
    while True:
        try:
            await check_expirations(None)
        except Exception as e:
            print(f"Expiration task error: {e}")
        await asyncio.sleep(60)

async def command_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """End conversation and handle command."""
    context.user_data.clear()
    cmd = update.message.text
    if cmd == '/start':
        await start(update, context)
    elif cmd in ['/admin', '/ad']:
        await admin_handlers.admin_panel(update, context)
    return ConversationHandler.END

def main() -> None:
    """Run the bot."""
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env")
        return
        
    db.init_db()
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Add Product ConversationHandler
    add_product_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Add Product$"), admin_handlers.start_add_product)],
        states={
            admin_handlers.CHOOSING_TYPE: [MessageHandler(filters.TEXT, admin_handlers.product_type_chosen)],
            admin_handlers.TITLE_EN: [MessageHandler(filters.TEXT, admin_handlers.title_en_received)],
            admin_handlers.TITLE_RU: [MessageHandler(filters.TEXT, admin_handlers.title_ru_received)],
            admin_handlers.DESC_EN: [MessageHandler(filters.TEXT, admin_handlers.desc_en_received)],
            admin_handlers.DESC_RU: [MessageHandler(filters.TEXT, admin_handlers.desc_ru_received)],
            admin_handlers.PRICE: [MessageHandler(filters.TEXT, admin_handlers.price_received)],
            admin_handlers.STOCK: [MessageHandler(filters.TEXT, admin_handlers.stock_received)],
            admin_handlers.DELIVERY_VALUE: [
                MessageHandler((filters.TEXT | filters.Document.ALL | filters.PHOTO | filters.VIDEO) & ~filters.COMMAND, 
                              admin_handlers.delivery_value_received)
            ],
            admin_handlers.CODES_INPUT: [MessageHandler(filters.TEXT, admin_handlers.codes_received)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^(Cancel|Отмена)$"), admin_handlers.cancel_conversation),
            CommandHandler(["start", "admin", "ad"], command_fallback)
        ],
    )
    
    application.add_handler(add_product_handler)

    # Edit Product ConversationHandler
    edit_product_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^✏️ Edit Product$"), admin_handlers.start_edit_product)],
        states={
            admin_handlers.EDIT_SELECT_PRODUCT: [MessageHandler(filters.TEXT, admin_handlers.edit_product_selected)],
            admin_handlers.EDIT_SELECT_FIELD: [MessageHandler(filters.TEXT, admin_handlers.edit_field_selected)],
            admin_handlers.EDIT_NEW_VALUE: [MessageHandler(filters.TEXT, admin_handlers.edit_new_value_received)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^(Cancel|Отмена)$"), admin_handlers.cancel_conversation),
            CommandHandler(["start", "admin", "ad"], command_fallback)
        ],
    )
    application.add_handler(edit_product_handler)

    # Delete Product ConversationHandler
    delete_product_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🗑️ Delete Product$"), admin_handlers.start_delete_product)],
        states={
            admin_handlers.DELETE_SELECT_PRODUCT: [MessageHandler(filters.TEXT, admin_handlers.delete_product_selected)],
            admin_handlers.DELETE_CONFIRM: [CallbackQueryHandler(admin_handlers.admin_delete_confirm_callback, pattern="^admin_del_")],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^(Cancel|❌ Cancel)$"), admin_handlers.cancel_conversation),
            CommandHandler(["start", "admin", "ad"], command_fallback)
        ],
    )
    application.add_handler(delete_product_handler)

    # Manage Stock ConversationHandler
    manage_stock_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📦 Manage Stock$"), admin_handlers.start_manage_stock)],
        states={
            admin_handlers.STOCK_SELECT_PRODUCT: [MessageHandler(filters.TEXT, admin_handlers.stock_product_selected)],
            admin_handlers.STOCK_ENTER_QTY: [MessageHandler(filters.TEXT, admin_handlers.stock_qty_received)],
            admin_handlers.STOCK_ENTER_CODES: [MessageHandler(filters.TEXT, admin_handlers.stock_codes_received)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^(Cancel|Отмена)$"), admin_handlers.cancel_conversation),
            CommandHandler(["start", "admin", "ad"], command_fallback)
        ],
    )
    application.add_handler(manage_stock_handler)

    # Manage Codes ConversationHandler
    manage_codes_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔑 Manage Codes$"), admin_handlers.start_manage_codes)],
        states={
            admin_handlers.CODES_SELECT_PRODUCT: [MessageHandler(filters.TEXT, admin_handlers.codes_product_selected)],
            admin_handlers.CODES_ADD_NEW: [MessageHandler(filters.TEXT, admin_handlers.codes_add_new_received)],
        },
        fallbacks=[
            MessageHandler(filters.Regex("^(Cancel|Отмена)$"), admin_handlers.cancel_conversation),
            CommandHandler(["start", "admin", "ad"], command_fallback)
        ],
    )
    application.add_handler(manage_codes_handler)

    # Recent Orders Handler
    application.add_handler(MessageHandler(filters.Regex("^📊 Recent Orders$"), admin_handlers.show_recent_orders))

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ad", admin_command))
    application.add_handler(CommandHandler("admin", admin_command))  # Alias for /ad
    application.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(product_callback, pattern="^(prod_|buy_|back_to_products)"))
    application.add_handler(CallbackQueryHandler(cancel_order_callback, pattern="^cancel_"))
    application.add_handler(CallbackQueryHandler(check_pay_callback, pattern="^checkpay:"))
    application.add_handler(CallbackQueryHandler(admin_handlers.admin_publish_stock_callback, pattern="^admin_publish_stock$"))
    application.add_handler(CallbackQueryHandler(admin_handlers.admin_hide_stock_callback, pattern="^admin_hide_stock$"))
    
    application.add_handler(MessageHandler(filters.TEXT, menu_handler))

    print("Bot is polling...")
    application.run_polling()

async def expiration_task():
    while True:
        await check_expirations(None)
        await asyncio.sleep(60)

if __name__ == "__main__":
    main()
