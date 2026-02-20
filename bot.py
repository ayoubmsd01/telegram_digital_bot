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

# ============================================================================
# SILENT BAN GUARD - Checks BEFORE any processing
# ============================================================================

def is_user_banned(update: Update) -> bool:
    """Check if the user who triggered this update is banned.
    If banned, we return True and the handler must immediately return
    without sending any response — complete silent ignore."""
    user = update.effective_user
    if not user:
        return False
    return db.is_banned(user.id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    if is_user_banned(update):
        return  # Silent ignore — banned user gets nothing
    
    user = update.effective_user
    db_lang = db.get_user_language(user.id)
    
    if db_lang:
        # Update user tracking
        username = str(user.username) if user.username else str(user.first_name)
        db.add_user(user.id, db_lang, username)

        # User already has language set, skip selection
        
        # Check for deep links (e.g., /start prod_123)
        if context.args:
            arg = context.args[0]
            if arg.startswith("prod_"):
                try:
                    p_id = int(arg.split("_")[1])
                    await _show_product_details(update, context, user.id, p_id, db_lang, edit_message=False)
                    return
                except ValueError:
                    pass
            elif arg.startswith("cat_"):
                # If they click a category, just show the whole catalog
                await _send_all_products_grouped(update, context, db_lang)
                return

        await show_main_menu(update, context, db_lang)
        
        # Check Stock Notification
        try:
            enabled = db.get_setting("stock_update_enabled")
            if enabled and str(enabled).strip() == "1":
                stock_msg = db.get_setting(f"stock_update_{db_lang}")
                
                # Fallback
                if not stock_msg and db_lang != 'en':
                    stock_msg = db.get_setting("stock_update_en")
                    
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
    if is_user_banned(update):
        return  # Silent ignore
    
    query = update.callback_query
    await query.answer()
    
    lang = query.data.split("_")[1]
    user = query.from_user
    username = str(user.username) if user.username else str(user.first_name)
    db.add_user(user.id, lang, username)
    
    await query.edit_message_text(text=f"Language set to {lang.upper()}")
    await show_main_menu(update, context, lang)

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /ad command to open admin panel."""
    if is_user_banned(update):
        return  # Silent ignore
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
    if is_user_banned(update):
        return  # Silent ignore — banned user gets nothing
    
    user_id = update.effective_user.id
    
    # Check if admin is waiting for ban/unban or balance input
    if admin_handlers.is_admin(update.effective_user):
        handled = await admin_handlers.process_ban_unban_input(update, context)
        if handled:
            return
        handled = await admin_handlers.process_admin_balance_input(update, context)
        if handled:
            return
    
    # Check if user is in topup amount flow
    if context.user_data.get('awaiting_topup_amount'):
        context.user_data.pop('awaiting_topup_amount', None)
        text_input = update.message.text.strip()
        lang = db.get_user_language(user_id) or "en"
        s = strings.STRINGS[lang]
        
        # Validate amount
        try:
            amount = float(text_input.replace(",", "."))
            if amount < 1:
                raise ValueError
        except (ValueError, TypeError):
            await update.message.reply_text(s["topup_invalid_amount"])
            return
        
        # Create CryptoBot invoice
        try:
            result = create_invoice(
                amount=amount,
                currency="USD",
                description=f"Balance top-up ${amount:.2f}",
                payload=f"topup_{user_id}_{amount}"
            )
            
            if result.get("ok") and result.get("result"):
                inv = result["result"]
                invoice_id = inv["invoice_id"]
                pay_url = inv.get("bot_invoice_url") or inv.get("pay_url") or inv.get("mini_app_invoice_url", "")
                
                # Save topup record
                db.create_topup(invoice_id, user_id, amount, 'USD')
                
                # Send payment link
                keyboard = [
                    [InlineKeyboardButton(s["topup_pay_btn"].replace("{amount}", f"{amount:.2f}"), url=pay_url)],
                    [InlineKeyboardButton(s["topup_check_btn"], callback_data=f"topup_check:{invoice_id}")]
                ]
                
                await update.message.reply_text(
                    s["topup_invoice_created"].replace("{amount}", f"{amount:.2f}"),
                    parse_mode='HTML',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                error_msg = result.get("error", {}).get("name", "Unknown")
                logger.error(f"CryptoBot invoice error: {error_msg}")
                await update.message.reply_text(s["topup_error"])
        except Exception as e:
            logger.error(f"Topup create error: {e}")
            await update.message.reply_text(s["topup_error"])
        return
    
    lang = db.get_user_language(user_id)
    if not lang:
        await start(update, context) # Fallback
        return

    # Update username opportunistically
    try:
        user = update.effective_user
        uname = str(user.username) if user.username else str(user.first_name)
        db.update_user_name(user_id, uname)
    except: pass

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
    elif text == s["menu_profile"]:
        await show_profile(update, context, lang)
    elif text == s["back"] or text == "⬅️ Back":
        await show_main_menu(update, context, lang)
    else:
        # Unknown button, just ignore it
        pass

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str):
    """Show user profile with inline buttons."""
    user = update.effective_user
    user_id = user.id
    s = strings.STRINGS[lang]
    
    # Get profile data
    profile = db.get_user_profile(user_id)
    purchases_count = db.get_user_purchases_count(user_id)
    
    # Format registration date
    registered_at = "—"
    if profile and profile.get('joined_at'):
        registered_at = str(profile['joined_at'])[:10]
    
    # Get real balance from DB
    balance = f"{db.get_user_balance(user_id):.2f}"
    
    # Build profile message
    msg = s["profile_text"].format(
        user_id=user_id,
        balance=balance,
        purchases_count=purchases_count,
        registered_at=registered_at
    )
    
    # Inline buttons
    keyboard = [
        [InlineKeyboardButton(s["btn_topup"], callback_data="profile_topup")],
        [InlineKeyboardButton(s["btn_my_purchases"], callback_data="profile_purchases")],
        [InlineKeyboardButton(s["btn_my_topups"], callback_data="profile_topups")],
        [InlineKeyboardButton(s["btn_activate_coupon"], callback_data="profile_coupon")],
    ]
    
    await update.message.reply_text(
        msg, parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def profile_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle profile inline button clicks."""
    if is_user_banned(update):
        return
    
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_id = user.id
    lang = db.get_user_language(user_id) or "en"
    s = strings.STRINGS[lang]
    data = query.data
    
    if data == "profile_topup":
        # Ask for amount
        context.user_data['awaiting_topup_amount'] = True
        cancel_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(s["topup_cancel"], callback_data="topup_cancel")]
        ])
        await query.message.reply_text(
            s["topup_enter_amount"], parse_mode='HTML',
            reply_markup=cancel_kb
        )
    
    elif data == "profile_purchases":
        # Show user's completed orders
        orders = db.get_user_orders(user_id) if hasattr(db, 'get_user_orders') else []
        if not orders:
            await query.message.reply_text(s["no_purchases"])
            return
        msg = f"🛒 <b>{'Мои покупки' if lang == 'ru' else 'My purchases'}:</b>\n\n"
        for i, o in enumerate(orders[:20], 1):
            status_icon = "✅" if o.get('status') in ('paid', 'delivered') else "⏳"
            amount = o.get('price_usd', 0)
            date = str(o.get('created_at', ''))[:10]
            msg += f"{i}. {status_icon} ${amount} — {date}\n"
        await query.message.reply_text(msg, parse_mode='HTML')
    
    elif data == "profile_topups":
        # Show topup history
        topups = db.get_user_topups(user_id)
        if not topups:
            await query.message.reply_text(s["no_topups"])
            return
        msg = f"💳 <b>{'Мои пополнения' if lang == 'ru' else 'My top-ups'}:</b>\n\n"
        for i, t in enumerate(topups[:20], 1):
            status_icon = "✅" if t['status'] == 'paid' else "⏳"
            msg += f"{i}. {status_icon} ${t['amount']:.2f} — {str(t['created_at'])[:10]}\n"
        await query.message.reply_text(msg, parse_mode='HTML')
    
    elif data == "profile_coupon":
        coupon_msg = "🎁 " + ("Функция купонов скоро будет доступна!" if lang == 'ru' else "Coupon feature coming soon!")
        await query.message.reply_text(coupon_msg)

async def topup_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel topup flow."""
    if is_user_banned(update):
        return
    query = update.callback_query
    await query.answer()
    context.user_data.pop('awaiting_topup_amount', None)
    lang = db.get_user_language(query.from_user.id) or "en"
    await query.message.reply_text(strings.STRINGS[lang]["topup_cancelled"])

async def topup_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Check if topup invoice is paid."""
    if is_user_banned(update):
        return
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    lang = db.get_user_language(user_id) or "en"
    s = strings.STRINGS[lang]
    
    # Extract invoice_id from callback data: topup_check:{invoice_id}
    invoice_id = int(query.data.split(":")[1])
    
    # Check in our DB first
    topup = db.get_topup_by_invoice(invoice_id)
    if not topup:
        await query.message.reply_text("❌ Invoice not found.")
        return
    
    if topup['status'] == 'paid':
        await query.message.reply_text(s["topup_already_paid"])
        return
    
    # Check with CryptoPay API
    try:
        from crypto_pay import get_invoices
        result = get_invoices(invoice_ids=invoice_id)
        
        if result.get("ok") and result.get("result", {}).get("items"):
            invoice = result["result"]["items"][0]
            if invoice.get("status") == "paid":
                import datetime as dt
                amount = topup['amount']
                
                # Update topup status (prevents double-credit)
                updated = db.update_topup_status(invoice_id, 'paid', dt.datetime.now().isoformat())
                if updated:
                    new_balance = db.add_user_balance(user_id, amount)
                    success_msg = s["topup_success"].replace("{amount}", f"{amount:.2f}").replace("{new_balance}", f"{new_balance:.2f}")
                    await query.message.reply_text(success_msg, parse_mode='HTML')
                else:
                    await query.message.reply_text(s["topup_already_paid"])
            else:
                await query.message.reply_text(s["topup_not_paid"])
        else:
            await query.message.reply_text(s["topup_not_paid"])
    except Exception as e:
        logger.error(f"Topup check error: {e}")
        await query.message.reply_text(s["topup_not_paid"])

async def _send_all_products_grouped(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str):
    """Send all active categories and their products grouped, chunked to handle long messages."""
    categories = db.get_categories(only_active=True)
    s = strings.STRINGS[lang]
    
    if not categories:
        msg = s.get("no_categories", "📦 No products available yet.")
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(msg)
            except Exception:
                await update.callback_query.message.reply_text(msg)
        else:
            await update.message.reply_text(msg)
        return

    bot_username = context.bot.username
    blocks = []
    has_any_products = False
    
    for c in categories:
        c_id = c["category_id"]
        cat_name = c["name_ru"] if lang == "ru" else c["name_en"]
        products = db.get_products(category_id=c_id, only_active=True)
        
        # Only visible products with stock > 0
        visible_products = [p for p in products if p["stock"] > 0]
        
        if not visible_products:
            continue
            
        has_any_products = True
            
        cat_link = f'<a href="https://t.me/{bot_username}?start=cat_{c_id}">{cat_name}</a>'
        block = f"— — — {cat_link} — — —\n"
        for p in visible_products:
            p_id = p["product_id"]
            title = p["title_ru"] if lang == "ru" else p["title_en"]
            price = p["price_usd"]
            stock = p["stock"]
            stock_text = f"{stock} шт." if lang == "ru" else f"{stock} pcs."
            
            # Use the entire title as the link
            prod_link = f'<a href="https://t.me/{bot_username}?start=prod_{p_id}">{title}</a>'
            line = f"{prod_link} | {stock_text} | ${price:g}\n"
            block += line
            
        block += "\n"
        blocks.append(block)
        
    if not has_any_products:
        msg = s.get("no_products", "📦 No products available yet.")
        if update.callback_query:
            try:
                await update.callback_query.edit_message_text(msg)
            except Exception:
                await update.callback_query.message.reply_text(msg)
        else:
            await update.message.reply_text(msg)
        return
        
    # Chunking
    messages = []
    current_msg = ""
    for block in blocks:
        if len(current_msg) + len(block) > 4000:
            messages.append(current_msg)
            current_msg = block
        else:
            current_msg += block
            
    if current_msg:
        messages.append(current_msg)
        
    for i, msg in enumerate(messages):
        # We only try to edit the first message chunk to replace the previous bubble
        if i == 0 and update.callback_query:
            try:
                await update.callback_query.edit_message_text(msg, parse_mode='HTML', disable_web_page_preview=True)
            except Exception:
                await update.callback_query.message.reply_text(msg, parse_mode='HTML', disable_web_page_preview=True)
        else:
            if update.message:
                await update.message.reply_text(msg, parse_mode='HTML', disable_web_page_preview=True)
            else:
                await update.callback_query.message.reply_text(msg, parse_mode='HTML', disable_web_page_preview=True)

async def _show_product_details(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, p_id: int, lang: str, edit_message=False):
    s = strings.STRINGS[lang]
    product = db.get_product(p_id)
    if not product:
        if edit_message:
            await update.callback_query.edit_message_text("Product not found.")
        else:
            await update.message.reply_text("Product not found.")
        return

    title = product["title_ru"] if lang == "ru" else product["title_en"]
    desc = product["desc_ru"] if lang == "ru" else product["desc_en"]
    price = product["price_usd"]
    stock = product["stock"]
    
    cat_id = product.get("category_id", None)
    back_data = "back_to_store"
    
    if stock <= 0:
        msg = s["out_of_stock_detailed"].format(name=title)
        keyboard = [
            [InlineKeyboardButton(s["btn_add_favorite"], callback_data=f"fav_{p_id}")],
            [InlineKeyboardButton(s["btn_back"], callback_data="back_to_store")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if edit_message:
            await update.callback_query.edit_message_text(msg, reply_markup=reply_markup, parse_mode="HTML")
        else:
            await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="HTML")
        return
        
    text = f"<b>{title}</b>\n\n{desc}\n\nPrice: ${price}\nStock: {stock}"
    
    keyboard = [
        [InlineKeyboardButton(s["buy_button"].format(price=price), callback_data=f"buy_{p_id}")],
        [InlineKeyboardButton(s["btn_back"], callback_data=back_data)] 
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if edit_message:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str):
    await _send_all_products_grouped(update, context, lang)

async def show_stock(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str):
    # Check Published Stock Update (Alert) First
    try:
        enabled = db.get_setting("stock_update_enabled")
        if enabled and str(enabled).strip() == "1":
            stock_msg = db.get_setting(f"stock_update_{lang}")
            
            # Fallback to English if translation missing
            if not stock_msg and lang != 'en':
                stock_msg = db.get_setting("stock_update_en")
                
            if stock_msg:
                 await update.message.reply_text(stock_msg, parse_mode='HTML')
                 print(f"[STOCK_UPDATE] shown to user_id={update.effective_user.id} lang={lang}")
    except Exception as e:
        print(f"Error sending stock update: {e}")

    await _send_all_products_grouped(update, context, lang)

async def product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = query.from_user.id
    if is_user_banned(update):
        return  # Silent ignore
    
    lang = db.get_user_language(user_id) or "en"
    s = strings.STRINGS[lang]

    if data.startswith("cat_"):
        c_id = int(data.split("_")[1])
        await _send_product_list(update, context, lang, category_id=c_id, edit_message=True)

    elif data.startswith("prod_"):
        p_id = int(data.split("_")[1])
        await _show_product_details(update, context, user_id, p_id, lang, edit_message=True)
        
    elif data.startswith("fav_"):
        p_id = int(data.split("_")[1])
        db.add_favorite(user_id, p_id)
        await query.answer(s.get("favorite_added_success", "Added to favorites!"), show_alert=True)

    elif data == "back_to_store" or data == "back_to_categories" or data.startswith("back_to_products"):
        # Regardless of what back button previously existed, render grouped list
        await _send_all_products_grouped(update, context, lang)
        
    elif data.startswith("buy_"):
        p_id = int(data.split("_")[1])
        product = db.get_product(p_id)
        
        if not product or product["stock"] <= 0:
            await query.message.reply_text(s.get("out_of_stock_detailed", "Out of stock.").format(name=product["title_en"] if product else "Unknown"))
            return

        price = product["price_usd"]
        user_balance = db.get_user_balance(user_id)
        title = product["title_ru"] if lang == "ru" else product["title_en"]

        # Strategy
        if user_balance >= price:
            # Full balance purchase
            if db.deduct_user_balance(user_id, price):
                stock_item = db.reserve_stock_item(p_id)
                if not stock_item:
                    # Race condition: ran out of stock
                    db.add_user_balance(user_id, price)
                    await query.message.reply_text(s.get("out_of_stock_detailed", "Out of stock.").format(name=title))
                    return

                stock_id = stock_item['stock_id']
                # Create order with stock_id
                order_id = db.create_order(user_id, p_id, 0, price, used_balance=price, need_crypto=0.0, stock_id=stock_id)
                db.update_order_status(order_id, 'paid')
                
                import datetime as dt
                db.update_order_payment(order_id, price, "BALANCE", dt.datetime.now().isoformat())
                
                msg = s["buy_full_balance"].replace("{price}", f"{price:.2f}")
                await query.message.reply_text(msg, parse_mode="HTML")
                
                # Deliver
                await delivery_service.deliver_order(order_id, context.bot)
            else:
                await query.message.reply_text(s["topup_error"])
            return

        # Partial or no balance
        need_crypto = price
        used_balance = 0.0
        
        if user_balance > 0:
            used_balance = user_balance
            need_crypto = price - user_balance

        # Reserve Stock immediately
        stock_item = db.reserve_stock_item(p_id)
        if not stock_item:
            await query.message.reply_text(s.get("out_of_stock_detailed", "Out of stock.").format(name=title))
            return
            
        stock_id = stock_item['stock_id']

        # Deduct available balance
        if used_balance > 0:
            if not db.deduct_user_balance(user_id, used_balance):
                # Race condition: balance became unavailable
                db.release_stock_item(stock_id)
                await query.message.reply_text(s["topup_error"])
                return

        try:
            invoice = create_invoice(
                amount=need_crypto,
                currency="USD",
                description=f"Buying {product['title_en']}",
                payload=f"{user_id}:{p_id}" 
            )
            
            if invoice and invoice.get("ok"):
                result = invoice["result"]
                invoice_id = result["invoice_id"]
                pay_url = result.get("bot_invoice_url") or result.get("pay_url") or result.get("mini_app_invoice_url", "")
                
                # Create Order in DB
                order_id = db.create_order(user_id, p_id, invoice_id, price, used_balance=used_balance, need_crypto=need_crypto, stock_id=stock_id)
                
                if used_balance > 0:
                    msg_text = s["buy_partial_balance"].format(
                        invoice_id=invoice_id,
                        title=title,
                        used_balance=f"${used_balance:.2f}",
                        need_crypto=f"${need_crypto:.2f}"
                    )
                else:
                    msg_text = s["buy_no_balance"].format(
                        invoice_id=invoice_id,
                        title=title,
                        price=f"${price:.2f}"
                    )
                
                check_btn_text = "✅ Check Payment" if lang != "ru" else "✅ Проверить оплату"
                keyboard = [
                    [InlineKeyboardButton(s["pay_link"], url=pay_url)],
                    [InlineKeyboardButton(check_btn_text, callback_data=f"checkpay:{order_id}")],
                    [InlineKeyboardButton("❌ Cancel Order / Отменить", callback_data=f"cancel_{order_id}_{invoice_id}")]
                ]
                await query.message.reply_text(msg_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
            else:
                # Failed to create invoice, restore stock and balance
                db.release_stock_item(stock_id)
                if used_balance > 0:
                    db.add_user_balance(user_id, used_balance)
                logger.error(f"Invoice creation failed: {invoice}")
                await query.message.reply_text("Error creating invoice. Please try again.")
        except Exception as e:
            # Restore stock and balance on error
            db.release_stock_item(stock_id)
            if used_balance > 0:
                db.add_user_balance(user_id, used_balance)
            logger.error(f"Error: {e}")
            await query.message.reply_text("System error.")



async def cancel_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if is_user_banned(update):
        return  # Silent ignore
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
    if is_user_banned(update):
        return  # Silent ignore
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

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the dispatcher."""
    logger.error(f"Exception while handling an update: {context.error}")
    # Don't crash the bot on individual handler errors
    import traceback
    traceback.print_exc()

def main() -> None:
    """Run the bot."""
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found in .env")
        return
        
    db.init_db()
    
    # Run migrations for stock items and categories
    import migrate_stock
    try:
        migrate_stock.run_migration()
    except Exception as e:
        print(f"Migration error: {e}")
        
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Register global error handler to prevent crashes
    application.add_error_handler(error_handler)

    import admin_categories
    
    # New Handlers
    application.add_handler(admin_categories.add_category_conv)
    application.add_handler(admin_categories.add_product_stock_conv)
    application.add_handler(MessageHandler(filters.Regex("^🗂 Manage Categories$"), admin_categories.list_categories))

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

    # Recent Orders Handler
    application.add_handler(MessageHandler(filters.Regex("^📊 Recent Orders$"), admin_handlers.show_recent_orders))
    application.add_handler(MessageHandler(filters.Regex("^👥 Users Stats$"), admin_handlers.show_users_stats))

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("ad", admin_command))
    application.add_handler(CommandHandler("admin", admin_command))  # Alias for /ad
    application.add_handler(CommandHandler("debug_stock", admin_handlers.debug_stock_settings)) # Debug
    application.add_handler(CallbackQueryHandler(language_callback, pattern="^lang_"))
    application.add_handler(CallbackQueryHandler(product_callback, pattern="^(cat_|prod_|buy_|fav_|back_to_)"))
    application.add_handler(CallbackQueryHandler(cancel_order_callback, pattern="^cancel_"))
    application.add_handler(CallbackQueryHandler(check_pay_callback, pattern="^checkpay:"))
    application.add_handler(CallbackQueryHandler(admin_handlers.admin_publish_stock_callback, pattern="^admin_publish_stock$"))
    application.add_handler(CallbackQueryHandler(admin_handlers.admin_hide_stock_callback, pattern="^admin_hide_stock$"))
    
    # Reset Catalog handlers
    application.add_handler(MessageHandler(filters.Regex("^🧹 Reset catalog$"), admin_handlers.reset_catalog_prompt))
    application.add_handler(CallbackQueryHandler(admin_handlers.reset_catalog_action, pattern="^reset_catalog_"))
    
    # Ban Management handlers
    application.add_handler(MessageHandler(filters.Regex("^🚫 Ban Management$"), admin_handlers.ban_management_panel))
    application.add_handler(CallbackQueryHandler(admin_handlers.ban_callback, pattern="^(ban_start|unban_start|ban_list)$"))
    
    # Profile & Topup handlers
    application.add_handler(CallbackQueryHandler(profile_callback, pattern="^profile_(topup|purchases|topups|coupon)$"))
    application.add_handler(CallbackQueryHandler(topup_cancel_callback, pattern="^topup_cancel$"))
    application.add_handler(CallbackQueryHandler(topup_check_callback, pattern="^topup_check:"))
    
    # Admin Balance handler
    application.add_handler(MessageHandler(filters.Regex("^➕ Add Balance$"), admin_handlers.admin_add_balance_panel))
    application.add_handler(CallbackQueryHandler(admin_handlers.admin_balance_callback, pattern="^admin_balance_start$"))
    
    application.add_handler(MessageHandler(filters.TEXT, menu_handler))

    try:
        print(f"DEBUG: Stock ENBL: {db.get_setting('stock_update_enabled')}")
        val_ru = db.get_setting('stock_update_ru')
        print(f"DEBUG: Stock RU: {str(val_ru)[:30] if val_ru else 'None'}")
    except: pass
    
    logger.info("Bot is starting polling...")
    
    # Drop pending updates to avoid processing stale messages after restart
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )

async def expiration_task():
    while True:
        await check_expirations(None)
        await asyncio.sleep(60)

if __name__ == "__main__":
    import time as _time
    
    MAX_BACKOFF = 300  # 5 minutes max wait
    backoff = 10       # Start with 10 seconds
    
    while True:
        try:
            logger.info(f"Starting bot (backoff={backoff}s if crash)...")
            main()
            # If main() returns normally (e.g. graceful shutdown), exit
            logger.info("Bot stopped gracefully.")
            break
        except KeyboardInterrupt:
            logger.info("Bot stopped by user (Ctrl+C).")
            break
        except Exception as e:
            logger.error(f"Bot crashed: {e}")
            logger.info(f"Restarting in {backoff} seconds...")
            _time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)
            # Re-init DB in case connection was lost
            try:
                db.init_db()
            except: pass
