"""
Admin Panel Handlers for Telegram Digital Bot
Handles all admin-only operations including product management.
"""
import datetime
import traceback
import asyncio

import os
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
import database as db
from strings import STRINGS

# Get admin credentials from environment
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "").lower()

# Conversation states for Add Product
(CHOOSING_TYPE, TITLE_EN, TITLE_RU, DESC_EN, DESC_RU, 
 PRICE, STOCK, DELIVERY_VALUE, CODES_INPUT) = range(9)

# Conversation states for Edit Product
(EDIT_SELECT_PRODUCT, EDIT_SELECT_FIELD, EDIT_NEW_VALUE) = range(9, 12)

# Conversation states for Delete Product
(DELETE_SELECT_PRODUCT, DELETE_CONFIRM) = range(12, 14)

# Conversation states for Manage Stock
(STOCK_SELECT_PRODUCT, STOCK_ENTER_QTY, STOCK_ENTER_CODES) = range(14, 17)

# Conversation states for Manage Codes
(CODES_SELECT_PRODUCT, CODES_ADD_NEW) = range(17, 19)

# Conversation states for Ban Management
(BAN_ENTER_ID, UNBAN_ENTER_ID) = range(19, 21)

def is_admin(user) -> bool:
    """Check if user is admin by user_id or username."""
    if not user:
        return False
    
    # Check by user_id first (most reliable)
    if ADMIN_USER_ID and user.id == ADMIN_USER_ID:
        return True
    
    # Check by username as fallback
    if ADMIN_USERNAME and user.username:
        return user.username.lower() == ADMIN_USERNAME
    
    return False

def get_lang(user_id):
    """Get user language with fallback."""
    return db.get_user_language(user_id) or "en"

def is_command_button(text: str) -> bool:
    """Check if the text is one of the admin panel buttons."""
    if not text:
        return False
    buttons = [
        "➕ Add Product", "✏️ Edit Product", "🗑️ Delete Product",
        "📦 Manage Stock", "📤 Manage Files", "🔑 Manage Codes",
        "📊 Recent Orders", "👥 Users Stats", "🚫 Ban Management",
        "➕ Add Balance",
        "⬅️ Back", "/start", "/admin", "/ad"
    ]
    return text in buttons or text.startswith("/")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin panel menu."""
    user = update.effective_user
    lang = get_lang(user.id)
    s = STRINGS[lang]
    
    if not is_admin(user):
        await update.message.reply_text(s["not_authorized"])
        return
    
    keyboard = [
        ["➕ Add Product", "✏️ Edit Product"],
        ["🗑️ Delete Product", "📦 Manage Stock"],
        ["🔑 Manage Codes", "📊 Recent Orders"],
        ["👥 Users Stats", "🚫 Ban Management"],
        ["➕ Add Balance", "⬅️ Back"]
    ]
    
    await update.message.reply_text(
        s["admin_menu"],
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

    # In-Bot Stock Notification Controls
    stock_keyboard = [
        [InlineKeyboardButton("📣 Publish Stock Update (in-bot)", callback_data="admin_publish_stock")],
        [InlineKeyboardButton("🛑 Hide Stock Update", callback_data="admin_hide_stock")]
    ]
    
    await update.message.reply_text(
        "📢 <b>Stock Notification Controls:</b>\n"
        "(Updates only appear inside the bot)", 
        reply_markup=InlineKeyboardMarkup(stock_keyboard), 
        parse_mode='HTML'
    )

# ============================================================================
# ADD PRODUCT HANDLERS
# ============================================================================

async def start_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the add product conversation."""
    user = update.effective_user
    lang = get_lang(user.id)
    s = STRINGS[lang]
    
    if not is_admin(user):
        await update.message.reply_text(s["not_authorized"])
        return ConversationHandler.END
    
    keyboard = [["link"], ["file"], ["code"], ["Cancel"]]
    
    await update.message.reply_text(
        s["choose_product_type"],
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    
    return CHOOSING_TYPE

async def product_type_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle product type selection."""
    lang = get_lang(update.effective_user.id)
    s = STRINGS[lang]
    text = update.message.text.lower()
    
    if text == "cancel":
        await update.message.reply_text(s["operation_canceled"], reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    if text not in ["link", "file", "code"]:
        await update.message.reply_text(s["invalid_input"])
        return CHOOSING_TYPE
    
    context.user_data['product_type'] = text
    await update.message.reply_text(s["enter_title_en"], reply_markup=ReplyKeyboardRemove())
    return TITLE_EN

async def title_en_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save English title."""
    lang = get_lang(update.effective_user.id)
    s = STRINGS[lang]
    context.user_data['title_en'] = update.message.text
    await update.message.reply_text(s["enter_title_ru"])
    return TITLE_RU

async def title_ru_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save Russian title."""
    lang = get_lang(update.effective_user.id)
    s = STRINGS[lang]
    context.user_data['title_ru'] = update.message.text
    await update.message.reply_text(s["enter_desc_en"])
    return DESC_EN

async def desc_en_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save English description."""
    lang = get_lang(update.effective_user.id)
    s = STRINGS[lang]
    context.user_data['desc_en'] = update.message.text
    await update.message.reply_text(s["enter_desc_ru"])
    return DESC_RU

async def desc_ru_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save Russian description."""
    lang = get_lang(update.effective_user.id)
    s = STRINGS[lang]
    context.user_data['desc_ru'] = update.message.text
    await update.message.reply_text(s["enter_price"])
    return PRICE

async def price_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save price."""
    text = update.message.text
    if is_command_button(text):
        await update.message.reply_text("⚠️ Operation cancelled. Select the command again.", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END
        
    lang = get_lang(update.effective_user.id)
    s = STRINGS[lang]
    text = text.strip().replace(',', '.')
    try:
        price = float(text)
        context.user_data['price'] = price
        await update.message.reply_text(s["enter_stock"])
        return STOCK
    except ValueError:
        await update.message.reply_text(f"❌ Invalid price: '{text}'. Please use dot format (e.g. 9.99)")
        return PRICE

async def stock_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save stock and request delivery value."""
    text = update.message.text
    if is_command_button(text):
        await update.message.reply_text("⚠️ Operation cancelled. Select the command again.", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END
        
    lang = get_lang(update.effective_user.id)
    s = STRINGS[lang]
    try:
        text = text.strip().replace(',', '.')
        stock = int(float(text))
        context.user_data['stock'] = stock
        
        product_type = context.user_data['product_type']
        
        if product_type == "link":
            await update.message.reply_text(s["enter_link"])
            return DELIVERY_VALUE
        elif product_type == "file":
            await update.message.reply_text(s["send_file"])
            return DELIVERY_VALUE
        elif product_type == "code":
            await update.message.reply_text(s["send_codes"])
            return CODES_INPUT
    except ValueError:
        await update.message.reply_text(s["invalid_input"])
        return STOCK

async def delivery_value_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle delivery value (link or file)."""
    lang = get_lang(update.effective_user.id)
    s = STRINGS[lang]
    product_type = context.user_data['product_type']
    
    if product_type == "link":
        context.user_data['delivery_value'] = update.message.text
        return await finalize_product(update, context)
        
    elif product_type == "file":
        if update.message.document:
            file_id = update.message.document.file_id
        elif update.message.photo:
            file_id = update.message.photo[-1].file_id
        elif update.message.video:
            file_id = update.message.video.file_id
        else:
            await update.message.reply_text(s["invalid_input"])
            return DELIVERY_VALUE
        
        context.user_data['delivery_value'] = file_id
        return await finalize_product(update, context)

async def codes_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle codes input."""
    codes_text = update.message.text
    codes_list = [line.strip() for line in codes_text.split('\n') if line.strip()]
    
    context.user_data['codes'] = codes_list
    context.user_data['delivery_value'] = ""
    
    return await finalize_product(update, context)

async def finalize_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Create the product in database."""
    lang = get_lang(update.effective_user.id)
    s = STRINGS[lang]
    data = context.user_data
    
    product_id = db.add_product(
        title_en=data['title_en'],
        title_ru=data['title_ru'],
        desc_en=data['desc_en'],
        desc_ru=data['desc_ru'],
        price_usd=data['price'],
        stock=data['stock'],
        delivery_type=data['product_type'],
        delivery_value=data.get('delivery_value', '')
    )
    
    if data['product_type'] == 'code' and 'codes' in data:
        count = db.add_codes_bulk(product_id, data['codes'])
        await update.message.reply_text(
            s["product_created"].format(product_id=product_id) + "\n" + 
            s["codes_added"].format(count=count)
        )
    else:
        await update.message.reply_text(s["product_created"].format(product_id=product_id))
    
    context.user_data.clear()
    return ConversationHandler.END

# ============================================================================
# EDIT PRODUCT HANDLERS
# ============================================================================

async def start_edit_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show list of products to edit."""
    lang = get_lang(update.effective_user.id)
    s = STRINGS[lang]
    
    products = db.get_products()
    if not products:
        await update.message.reply_text("❌ No products found.")
        return ConversationHandler.END
    
    message = "📝 Select product to edit (send Product ID):\n\n"
    for p in products:
        title = p[f'title_{lang}'] if lang in ['en', 'ru'] else p['title_en']
        message += f"ID: {p['product_id']} - {title} (${p['price_usd']})\n"
    
    await update.message.reply_text(message)
    return EDIT_SELECT_PRODUCT

async def edit_product_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle product selection for editing."""
    lang = get_lang(update.effective_user.id)
    s = STRINGS[lang]
    
    try:
        product_id = int(update.message.text)
        product = db.get_product(product_id)
        
        if not product:
            await update.message.reply_text("❌ Product not found.")
            return ConversationHandler.END
        
        context.user_data['edit_product_id'] = product_id
        
        keyboard = [
            ["Price"], ["Stock"], ["Title EN"], ["Title RU"],
            ["Desc EN"], ["Desc RU"], ["Cancel"]
        ]
        
        await update.message.reply_text(
            f"Editing: {product['title_en']}\nSelect field to edit:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        )
        return EDIT_SELECT_FIELD
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")
        return EDIT_SELECT_PRODUCT

async def edit_field_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle field selection."""
    text = update.message.text
    
    if text == "Cancel":
        await update.message.reply_text("❌ Operation canceled.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    field_map = {
        "Price": "price_usd",
        "Stock": "stock",
        "Title EN": "title_en",
        "Title RU": "title_ru",
        "Desc EN": "desc_en",
        "Desc RU": "desc_ru"
    }
    
    if text in field_map:
        context.user_data['edit_field'] = field_map[text]
        await update.message.reply_text(f"Enter new value for {text}:", reply_markup=ReplyKeyboardRemove())
        return EDIT_NEW_VALUE
    
    await update.message.reply_text("❌ Invalid selection.")
    return EDIT_SELECT_FIELD

async def edit_new_value_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Update the product field."""
    # Safety check
    if 'edit_product_id' not in context.user_data or 'edit_field' not in context.user_data:
        await update.message.reply_text("❌ Session expired. Please start again.")
        return ConversationHandler.END
    
    text = update.message.text
    if is_command_button(text):
        await update.message.reply_text("⚠️ Edit cancelled. Select the command again.", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END
        
    product_id = context.user_data['edit_product_id']
    field = context.user_data['edit_field']
    new_value_str = text.strip().replace(',', '.')
    
    # Convert to appropriate type
    if field in ['price_usd']:
        try:
            new_value = float(new_value_str)
        except ValueError:
            await update.message.reply_text(f"❌ Invalid number: '{new_value_str}'. Please enter a valid price (e.g. 5.99).")
            return EDIT_NEW_VALUE
    elif field == 'stock':
        try:
            new_value = int(float(new_value_str))
        except ValueError:
            await update.message.reply_text(f"❌ Invalid number: '{new_value_str}'. Please enter a valid integer.")
            return EDIT_NEW_VALUE
    
   # Update in database
    old_stock = 0
    if field == 'stock':
        product = db.get_product(product_id)
        if product:
            old_stock = product['stock']

    db.update_product_field(product_id, field, new_value)
    
    if field == 'stock' and old_stock == 0 and new_value > 0:
        await trigger_restock_notifications(product_id, context)
        
    await update.message.reply_text(f"✅ Product updated!\n{field} = {new_value}")
    context.user_data.clear()
    return ConversationHandler.END

# ============================================================================
# DELETE PRODUCT HANDLERS
# ============================================================================

async def start_delete_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show list of products to delete."""
    lang = get_lang(update.effective_user.id)
    
    products = db.get_products()
    if not products:
        await update.message.reply_text("❌ No products found.")
        return ConversationHandler.END
    
    message = "🗑️ Select product to DELETE (send Product ID):\n\n"
    for p in products:
        title = p[f'title_{lang}'] if lang in ['en', 'ru'] else p['title_en']
        message += f"ID: {p['product_id']} - {title}\n"
    
    await update.message.reply_text(message)
    return DELETE_SELECT_PRODUCT

async def delete_product_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirm product deletion with Inline Buttons."""
    text = update.message.text
    if is_command_button(text):
        await update.message.reply_text("⚠️ Operation cancelled.", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END

    try:
        product_id = int(text)
        product = db.get_product(product_id)
        
        if not product:
            await update.message.reply_text("❌ Product not found.")
            return ConversationHandler.END
        
        context.user_data['delete_product_id'] = product_id
        
        keyboard = [
            [
                InlineKeyboardButton("✅ YES", callback_data="admin_del_yes"),
                InlineKeyboardButton("❌ NO", callback_data="admin_del_no")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"⚠️ Are you sure you want to delete:\n<b>{product['title_en']}</b>?\n(ID: {product_id})",
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        return DELETE_CONFIRM
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")
        return DELETE_SELECT_PRODUCT

async def admin_delete_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle delete confirmation via callback."""
    query = update.callback_query
    await query.answer()
    
    choice = query.data
    
    if choice == "admin_del_yes":
        if 'delete_product_id' not in context.user_data:
            await query.edit_message_text("❌ Session expired. Please start again.")
            return ConversationHandler.END
            
        product_id = context.user_data['delete_product_id']
        
        # Log deletion
        print(f"[ADMIN DELETE] product_id={product_id} deleted_by={update.effective_user.id}")
        
        # Execute deletion
        try:
            db.delete_product(product_id)
            await query.edit_message_text(f"✅ Product (ID: {product_id}) deleted successfully!")
        except Exception as e:
            print(f"Error deleting product: {e}")
            await query.edit_message_text(f"❌ Error deleting product: {str(e)}")
            
    else:
        await query.edit_message_text("❌ Deletion canceled.")
    
    context.user_data.pop('delete_product_id', None)
    return ConversationHandler.END

# ============================================================================
# MANAGE STOCK HANDLERS
# ============================================================================

async def start_manage_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show list of products to manage stock."""
    user = update.effective_user
    print(f"[ADMIN STOCK] step=start user_id={user.id}")
    
    lang = get_lang(user.id)
    
    products = db.get_products()
    if not products:
        await update.message.reply_text("❌ No products found.")
        return ConversationHandler.END
    
    message = "📦 Select product to ADD STOCK (send Product ID):\n\n"
    for p in products:
        title = p[f'title_{lang}'] if lang in ['en', 'ru'] else p['title_en']
        message += f"ID: {p['product_id']} - {title} (Current: {p['stock']})\n"
    
    await update.message.reply_text(message)
    return STOCK_SELECT_PRODUCT

async def stock_product_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle product selection for stock update."""
    text = update.message.text
    if is_command_button(text):
        await update.message.reply_text("⚠️ Operation cancelled.", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END

    try:
        product_id = int(text)
        product = db.get_product(product_id)
        
        if not product:
            await update.message.reply_text("❌ Product not found.")
            return ConversationHandler.END
        
        context.user_data['stock_product_id'] = product_id
        context.user_data['stock_delivery_type'] = product['delivery_type']
        
        print(f"[ADMIN STOCK] step=choose_product product_id={product_id} type={product['delivery_type']}")
        
        await update.message.reply_text(
            f"📦 Selected: {product['title_en']}\n"
            f"Current Stock: {product['stock']}\n\n"
            "Enter quantity to ADD (e.g. 5):"
        )
        return STOCK_ENTER_QTY
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")
        return STOCK_SELECT_PRODUCT

async def trigger_restock_notifications(product_id: int, context: ContextTypes.DEFAULT_TYPE):
    """Notify users who favorited this product if stock > 0."""
    try:
        product = db.get_product(product_id)
        if not product or product["stock"] <= 0: return
        
        users_to_notify = db.get_product_favorites(product_id)
        if not users_to_notify: return
        
        price = product["price_usd"]
        stock = product["stock"]
        
        from telegram import InlineKeyboardMarkup, InlineKeyboardButton
        import strings
        
        for user_id in users_to_notify:
            # Check silent ban!
            if db.is_banned(user_id):
                continue
                
            lang = db.get_user_language(user_id) or "en"
            s = strings.STRINGS[lang]
            title = product["title_ru"] if lang == "ru" else product["title_en"]
            
            msg = s["restock_notification"].format(
                name=title,
                price=f"{price:.2f}",
                stock=stock
            )
            
            kb = [[InlineKeyboardButton(s["buy_from_restock"], callback_data=f"buy_{product_id}")]]
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=msg,
                    reply_markup=InlineKeyboardMarkup(kb),
                    parse_mode='HTML'
                )
            except Exception as e:
                print(f"[RESTOCK NOTIFY] Failed for {user_id}: {e}")
                
    except Exception as e:
        print(f"[ERROR] trigger_restock_notifications: {e}")

async def stock_qty_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle quantity input."""
    if 'stock_product_id' not in context.user_data:
        await update.message.reply_text("❌ Session expired. Please start again.")
        return ConversationHandler.END
    
    text = update.message.text
    if is_command_button(text):
        await update.message.reply_text("⚠️ Operation cancelled.", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END
        
    try:
        qty = int(text)
        if qty <= 0:
            await update.message.reply_text("❌ Quantity must be positive.")
            return STOCK_ENTER_QTY
            
        product_id = context.user_data['stock_product_id']
        delivery_type = context.user_data['stock_delivery_type']
        
        print(f"[ADMIN STOCK] step=enter_qty qty={qty} product_id={product_id}")
        
        # If Link or File -> Update immediately
        if delivery_type in ['link', 'file']:
            was_zero = db.increment_stock(product_id, qty)
            await update.message.reply_text(f"✅ Stock updated successfully (+{qty})!")
            if was_zero:
                await trigger_restock_notifications(product_id, context)
            context.user_data.clear()
            return ConversationHandler.END
            
        # If Code -> Ask for codes
        elif delivery_type == 'code':
            context.user_data['stock_add_qty'] = qty
            await update.message.reply_text(
                f"🔑 delivery_type='code'.\n"
                f"Please send {qty} codes (one per line):"
            )
            return STOCK_ENTER_CODES
        
        # Unknown type fallback
        else:
            was_zero = db.increment_stock(product_id, qty)
            await update.message.reply_text(f"✅ Stock updated successfully (+{qty})!")
            if was_zero:
                await trigger_restock_notifications(product_id, context)
            context.user_data.clear()
            return ConversationHandler.END
            
    except ValueError:
        await update.message.reply_text("❌ Invalid number. Please enter an integer.")
        return STOCK_ENTER_QTY

async def stock_codes_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle codes input."""
    if 'stock_product_id' not in context.user_data:
        await update.message.reply_text("❌ Session expired.")
        return ConversationHandler.END
        
    text = update.message.text
    if is_command_button(text):
        await update.message.reply_text("⚠️ Operation cancelled.", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END
        
    codes = [line.strip() for line in text.split('\n') if line.strip()]
    expected_qty = context.user_data['stock_add_qty']
    product_id = context.user_data['stock_product_id']
    
    print(f"[ADMIN STOCK] step=enter_codes count={len(codes)} expected={expected_qty}")
    
    if len(codes) != expected_qty:
        await update.message.reply_text(
            f"❌ You sent {len(codes)} codes, but I expected {expected_qty}.\n"
            "Please send exactly the right amount, or Cancel."
        )
        return STOCK_ENTER_CODES
        
    # Save codes and update stock
    try:
        db.add_codes_bulk(product_id, codes)
        was_zero = db.increment_stock(product_id, expected_qty)
        
        await update.message.reply_text(f"✅ Added {len(codes)} codes and updated stock!")
        if was_zero:
            await trigger_restock_notifications(product_id, context)
    except Exception as e:
        print(f"Error adding codes: {e}")
        await update.message.reply_text(f"❌ Error: {str(e)}")
        
    context.user_data.clear()
    return ConversationHandler.END

# ============================================================================
# MANAGE CODES HANDLERS
# ============================================================================

async def start_manage_codes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show list of code-type products."""
    lang = get_lang(update.effective_user.id)
    
    products = db.get_products()
    code_products = [p for p in products if p['delivery_type'] == 'code']
    
    if not code_products:
        await update.message.reply_text("❌ No code products found.")
        return ConversationHandler.END
    
    message = "🔑 Select product to add codes (send Product ID):\n\n"
    for p in code_products:
        title = p[f'title_{lang}'] if lang in ['en', 'ru'] else p['title_en']
        available = db.count_available_codes(p['product_id'])
        message += f"ID: {p['product_id']} - {title} ({available} codes)\n"
    
    await update.message.reply_text(message)
    return CODES_SELECT_PRODUCT

async def codes_product_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle product selection for adding codes."""
    try:
        product_id = int(update.message.text)
        product = db.get_product(product_id)
        
        if not product or product['delivery_type'] != 'code':
            await update.message.reply_text("❌ Invalid code product.")
            return ConversationHandler.END
        
        context.user_data['codes_product_id'] = product_id
        await update.message.reply_text("Send new codes (one per line):")
        return CODES_ADD_NEW
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")
        return CODES_SELECT_PRODUCT

async def codes_add_new_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Add new codes to product."""
    if 'codes_product_id' not in context.user_data:
        await update.message.reply_text("❌ Session expired. Please start again.")
        return ConversationHandler.END
        
    codes_text = update.message.text
    codes_list = [line.strip() for line in codes_text.split('\n') if line.strip()]
    
    product_id = context.user_data['codes_product_id']
    count = db.add_codes_bulk(product_id, codes_list)
    was_zero = db.increment_stock(product_id, count)
    
    await update.message.reply_text(f"✅ Added {count} codes and updated stock!")
    if was_zero:
        await trigger_restock_notifications(product_id, context)
        
    context.user_data.clear()
    return ConversationHandler.END

# ============================================================================
# RECENT ORDERS HANDLER
# ============================================================================

async def show_recent_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent orders."""
    user = update.effective_user
    print(f"[ADMIN] recent_orders clicked by user_id={user.id}")
    
    # Permission check for extra safety
    if not is_admin(user):
        await update.message.reply_text("❌ Not authorized.")
        return
        
    try:
        # Get orders (limit 20) with joined data
        orders = db.get_recent_orders(limit=20)
        
        if not orders:
            await update.message.reply_text("📊 No recent orders found.")
            return
        
        message = "📊 Recent Orders (Last 20 ordered):\n\n"
        
        for o in orders:
            order_id = o.get('order_id', 'N/A')
            status = o.get('status', 'unknown')
            title = o.get('title_en') or "Deleted Product"
            price = o.get('price_usd') or 0.0
            price_str = f"${price}" if price else "$0.0"
            
            user_id = str(o.get('user_id', 'N/A'))
            created_at = str(o.get('created_at', ''))[:16]
            
            # Payment Details
            paid_amount = o.get('paid_amount')
            paid_asset = o.get('paid_asset') or ""
            invoice_id = o.get('invoice_id')
            
            if status == 'delivered': status_text = "✅ DELIVERED"
            elif status == 'paid': status_text = "✅ PAID"
            elif status == 'pending': status_text = "⏳ AWAITING PAYMENT"
            elif status in ['canceled', 'expired']: status_text = "❌"
            else: status_text = f"❓ {status.upper()}"
            
            message += f"#{order_id} | {title} | {status_text}\n"
            
            # Payment line
            pay_details = f"User: <code>{user_id}</code> | Price: {price_str}"
            if paid_amount:
                pay_details += f" | Paid: {paid_amount} {paid_asset}"
            pay_details += f" | Invoice: {invoice_id} | {created_at}"
            message += f"{pay_details}\n"
            
            # Delivery details
            if status == 'delivered':
                 dtype = o.get('delivered_type')
                 dvalue = o.get('delivered_value')
                 dname = o.get('delivered_filename')
                 dat = o.get('delivered_at')
                 
                 if dtype == 'file':
                     message += f"Delivered: FILE | Name: {dname or 'N/A'} | Time: {dat}\n"
                 elif dtype == 'link':
                     short_v = (dvalue[:25] + '...') if dvalue and len(dvalue) > 25 else dvalue
                     message += f"Delivered: LINK | {short_v} | Time: {dat}\n"
                 elif dtype == 'code':
                     short_c = (dvalue[-5:] if dvalue and len(dvalue) > 5 else dvalue)
                     message += f"Delivered: CODE | ...{short_c} | Time: {dat}\n"
            
            message += "-------------------\n"
            
        # Send message (split if too long)
        if len(message) > 4000:
            chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode='HTML')
        else:
            await update.message.reply_text(message, parse_mode='HTML')
            
    except Exception as e:
        error_msg = f"Error in recent_orders: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        await update.message.reply_text(f"❌ Error fetching orders: {str(e)}")

# ============================================================================
# ============================================================================
# STOCK UPDATE NOTIFICATIONS
# ============================================================================

async def admin_publish_stock_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    products = db.get_products()
    available = [p for p in products if p['stock'] > 0]
    
    if not available:
        await query.message.reply_text("⚠️ No products in stock to publish. / Нет товаров.")
        return

    # Helper for formatting
    msg_ru = "📢 <b>Обновление наличия:</b>\n\n"
    for p in available:
        msg_ru += f"🔹 <b>{p['title_ru']}</b> - ${p['price_usd']} ({p['stock']} шт.)\n"
    
    msg_en = "📢 <b>Stock Update:</b>\n\n"
    for p in available:
        msg_en += f"🔹 <b>{p['title_en']}</b> - ${p['price_usd']} ({p['stock']} pcs)\n"

    try:
        db.set_setting("stock_update_ru", msg_ru)
        db.set_setting("stock_update_en", msg_en)
        db.set_setting("stock_update_enabled", "1")
        
        # Immediate Verification
        check = db.get_setting("stock_update_enabled")
        
        if str(check).strip() == "1":
            await query.message.reply_text("✅ Stock update published & VERIFIED!")
            
             # BROADCAST LOGIC
            status_msg = await query.message.reply_text("🚀 Starting BROADCAST (Push)...")
            
            users = db.get_all_users()
            sent_count = 0
            fail_count = 0
            ban_skip = 0
            total_db = len(users)
            
            # Use background task logic conceptually, but run here for simplicity as user requested
            for i, u in enumerate(users):
                try:
                    uid = u['user_id']
                    
                    # Skip banned users silently — no broadcast for them
                    if db.is_banned(uid):
                        ban_skip += 1
                        continue
                    
                    ulang = u.get('language')
                    text = msg_ru if ulang == 'ru' else msg_en
                    
                    await context.bot.send_message(chat_id=uid, text=text, parse_mode='HTML')
                    sent_count += 1
                except Exception:
                    # Likely blocked by user
                    fail_count += 1
                
                # Rate limit safety: sleep every 25 messages for 1 sec
                if (i + 1) % 25 == 0:
                    await asyncio.sleep(1.0)
            
            final_report = (
                f"✅ <b>Broadcast Completed!</b>\n"
                f"• Sent: {sent_count}\n"
                f"• Failed: {fail_count} (Blocked/Deleted)\n"
                f"• Banned (skipped): {ban_skip}\n"
                f"• Total DB Users: {total_db}"
            )
            
            # Reply to admin
            await context.bot.send_message(chat_id=user_id, text=final_report, parse_mode='HTML')
            
        else:
            await query.message.reply_text(f"⚠️ Published but verification failed. Value: {check}")
            
        print(f"[STOCK_UPDATE] published by admin_id={user_id} verified={check}")
    except Exception as e:
        print(f"FAILED TO PUBLISH STOCK UPDATE: {e}")
        await query.message.reply_text(f"❌ Error publishing: {str(e)}")

async def admin_hide_stock_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    db.set_setting("stock_update_enabled", "0")
    
    await query.message.reply_text("🛑 Stock update hidden. / Обновление скрыто.")
    print(f"[STOCK_UPDATE] hidden by admin_id={query.from_user.id}")

async def debug_stock_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Debug command to check current settings state."""
    enbl = db.get_setting("stock_update_enabled")
    ru = db.get_setting("stock_update_ru")
    en = db.get_setting("stock_update_en")
    
    msg = (
        f"🔍 <b>Debug Stock Settings:</b>\n"
        f"Enabled: <code>{enbl}</code>\n"
        f"RU Msg Len: {len(ru) if ru else 0}\n"
        f"EN Msg Len: {len(en) if en else 0}\n"
        f"Sample EN: <code>{str(en)[:20]}...</code>"
    )
    await update.message.reply_text(msg, parse_mode='HTML')

async def show_users_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show list of users."""
    users = db.get_all_users()
    total = len(users)
    
    if total == 0:
        await update.message.reply_text("👥 No users recorded yet.")
        return

    msg = f"👥 <b>Registered Users: {total}</b>\n\n"
    
    # Sort: joined_at DESC (if exists), else user_id DESC
    sorted_users = sorted(users, key=lambda x: str(x.get('joined_at') or '0'), reverse=True)
    
    limit = 60
    shown = 0
    
    for u in sorted_users:
        if shown >= limit:
            msg += f"\n... and {total - shown} more."
            break
            
        uid = u['user_id']
        uname = u.get('username')
        joined = u.get('joined_at')
        
        # Format
        if uname and uname != 'None':
            user_ref = f"@{uname}"
        else:
            user_ref = "No Username"
             
        date_str = str(joined)[:10] if joined else ""
        
        msg += f"{shown+1}. {user_ref} | ID: <code>{uid}</code> | {date_str}\n"
        shown += 1
        
    msg += "\nℹ️ <i>Usernames update automatically when users interact.</i>"
    await update.message.reply_text(msg, parse_mode='HTML')

# ============================================================================
# CANCEL HANDLER
# ============================================================================

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    lang = get_lang(update.effective_user.id)
    s = STRINGS[lang]
    await update.message.reply_text(s["operation_canceled"], reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

# ============================================================================
# SILENT BAN MANAGEMENT
# ============================================================================

async def ban_management_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the ban management panel with inline buttons."""
    user = update.effective_user
    if not is_admin(user):
        return  # Silent ignore for non-admins
    
    banned_count = len(db.get_banned_users())
    
    keyboard = [
        [InlineKeyboardButton("🚫 Ban User by ID", callback_data="ban_start")],
        [InlineKeyboardButton("✅ Unban User by ID", callback_data="unban_start")],
        [InlineKeyboardButton("📋 View Banned List", callback_data="ban_list")]
    ]
    
    await update.message.reply_text(
        f"🚫 <b>Silent Ban Management</b>\n\n"
        f"Currently banned: <b>{banned_count}</b> users\n\n"
        f"ℹ️ <i>Banned users are completely ignored by the bot.\n"
        f"They receive no responses, no broadcasts, no notifications.\n"
        f"They will never know they are banned.</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def ban_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle ban management inline button clicks."""
    query = update.callback_query
    user = query.from_user
    
    if not is_admin(user):
        return  # Silent ignore
    
    await query.answer()
    data = query.data
    
    if data == "ban_start":
        await query.message.reply_text(
            "🚫 <b>Ban User</b>\n\n"
            "Send the <b>user ID</b> (numeric) to ban:\n\n"
            "<i>Send /cancel to cancel.</i>",
            parse_mode='HTML'
        )
        context.user_data['awaiting_ban_id'] = True
        
    elif data == "unban_start":
        # Show current banned list first for reference
        banned = db.get_banned_users()
        if not banned:
            await query.message.reply_text("✅ No banned users to unban.")
            return
        
        msg = "✅ <b>Unban User</b>\n\nCurrently banned:\n"
        for i, b in enumerate(banned, 1):
            msg += f"{i}. <code>{b['user_id']}</code> (since {str(b['banned_at'])[:10]})\n"
        msg += "\nSend the <b>user ID</b> to unban:\n<i>Send /cancel to cancel.</i>"
        
        await query.message.reply_text(msg, parse_mode='HTML')
        context.user_data['awaiting_unban_id'] = True
        
    elif data == "ban_list":
        banned = db.get_banned_users()
        
        if not banned:
            await query.message.reply_text("📋 <b>Banned Users</b>\n\n✅ No banned users.", parse_mode='HTML')
            return
        
        msg = f"📋 <b>Banned Users ({len(banned)}):</b>\n\n"
        for i, b in enumerate(banned, 1):
            uid = b['user_id']
            date = str(b['banned_at'])[:10]
            msg += f"{i}. <code>{uid}</code> — banned {date}\n"
        
        await query.message.reply_text(msg, parse_mode='HTML')

async def process_ban_unban_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Process ban/unban ID input from admin. Returns True if handled."""
    user = update.effective_user
    if not is_admin(user):
        return False
    
    text = update.message.text.strip()
    
    # Handle /cancel
    if text == '/cancel':
        context.user_data.pop('awaiting_ban_id', None)
        context.user_data.pop('awaiting_unban_id', None)
        await update.message.reply_text("❌ Operation cancelled.")
        return True
    
    # Handle ban input
    if context.user_data.get('awaiting_ban_id'):
        context.user_data.pop('awaiting_ban_id', None)
        
        try:
            target_id = int(text)
        except ValueError:
            await update.message.reply_text("❌ Invalid ID. Must be a number. Try again from Ban Management.")
            return True
        
        # Don't allow banning yourself
        if target_id == user.id:
            await update.message.reply_text("❌ You cannot ban yourself!")
            return True
        
        newly_banned = db.ban_user(target_id)
        
        if newly_banned:
            await update.message.reply_text(
                f"🚫 <b>User Banned!</b>\n\n"
                f"User ID: <code>{target_id}</code>\n"
                f"Status: Silently banned ✅\n\n"
                f"<i>The user will receive no responses or notifications.\n"
                f"They will never know they are banned.</i>",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                f"ℹ️ User <code>{target_id}</code> is already banned.",
                parse_mode='HTML'
            )
        return True
    
    # Handle unban input
    if context.user_data.get('awaiting_unban_id'):
        context.user_data.pop('awaiting_unban_id', None)
        
        try:
            target_id = int(text)
        except ValueError:
            await update.message.reply_text("❌ Invalid ID. Must be a number. Try again from Ban Management.")
            return True
        
        was_banned = db.unban_user(target_id)
        
        if was_banned:
            await update.message.reply_text(
                f"✅ <b>User Unbanned!</b>\n\n"
                f"User ID: <code>{target_id}</code>\n"
                f"Status: Unblocked ✅\n\n"
                f"<i>The user can now use the bot normally.</i>",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                f"ℹ️ User <code>{target_id}</code> is not in the ban list.",
                parse_mode='HTML'
            )
        return True
    
    return False  # Not a ban/unban input

# ============================================================================
# ADMIN BALANCE MANAGEMENT
# ============================================================================

async def admin_add_balance_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin balance management panel."""
    user = update.effective_user
    if not is_admin(user):
        return
    
    keyboard = [
        [InlineKeyboardButton("➕ Add balance to user", callback_data="admin_balance_start")]
    ]
    
    await update.message.reply_text(
        "➕ <b>Add Balance</b>\n\n"
        "Manually add balance to any user.\n"
        "Press the button below to start.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

async def admin_balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin balance inline button."""
    query = update.callback_query
    user = query.from_user
    if not is_admin(user):
        return
    
    await query.answer()
    
    await query.message.reply_text(
        "➕ <b>Add Balance</b>\n\n"
        "Send: <code>user_id amount</code>\n"
        "Example: <code>1549155542 10</code>\n\n"
        "<i>Send /cancel to cancel.</i>",
        parse_mode='HTML'
    )
    context.user_data['awaiting_admin_balance'] = True

async def process_admin_balance_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Process admin balance input. Returns True if handled."""
    user = update.effective_user
    if not is_admin(user):
        return False
    
    if not context.user_data.get('awaiting_admin_balance'):
        return False
    
    text = update.message.text.strip()
    
    # Handle /cancel
    if text == '/cancel':
        context.user_data.pop('awaiting_admin_balance', None)
        await update.message.reply_text("❌ Operation cancelled.")
        return True
    
    context.user_data.pop('awaiting_admin_balance', None)
    
    # Parse input: user_id amount
    parts = text.split()
    if len(parts) != 2:
        await update.message.reply_text(
            "❌ Invalid format.\nSend: <code>user_id amount</code>\nExample: <code>1549155542 10</code>",
            parse_mode='HTML'
        )
        return True
    
    try:
        target_id = int(parts[0])
        amount = float(parts[1])
        if amount <= 0:
            raise ValueError("Amount must be positive")
    except (ValueError, TypeError):
        await update.message.reply_text(
            "❌ Invalid input. user_id must be a number and amount must be positive.",
        )
        return True
    
    # Check if user exists
    profile = db.get_user_profile(target_id)
    if not profile:
        await update.message.reply_text(
            f"❌ User <code>{target_id}</code> not found in database.",
            parse_mode='HTML'
        )
        return True
    
    # Add balance
    new_balance = db.add_user_balance(target_id, amount)
    
    # Log adjustment
    db.add_admin_adjustment(user.id, target_id, amount, "Manual admin adjustment")
    
    username = profile.get('username', 'Unknown')
    
    await update.message.reply_text(
        f"✅ <b>Balance Added!</b>\n\n"
        f"User: <code>{target_id}</code> (@{username})\n"
        f"Added: <b>${amount:.2f}</b>\n"
        f"New balance: <b>${new_balance:.2f}</b>",
        parse_mode='HTML'
    )
    return True
