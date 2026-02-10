"""
Admin Panel Handlers for Telegram Digital Bot
Handles all admin-only operations including product management.
"""
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
(STOCK_SELECT_PRODUCT, STOCK_NEW_VALUE) = range(14, 16)

# Conversation states for Manage Codes
(CODES_SELECT_PRODUCT, CODES_ADD_NEW) = range(16, 18)

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
        "📊 Recent Orders", "⬅️ Back", "/start", "/admin", "/ad"
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
        ["⬅️ Back"]
    ]
    
    await update.message.reply_text(
        s["admin_menu"],
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
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
    db.update_product_field(product_id, field, new_value)
    
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
    """Confirm product deletion."""
    lang = get_lang(update.effective_user.id)
    
    try:
        product_id = int(update.message.text)
        product = db.get_product(product_id)
        
        if not product:
            await update.message.reply_text("❌ Product not found.")
            return ConversationHandler.END
        
        context.user_data['delete_product_id'] = product_id
        
        keyboard = [["✅ YES, DELETE"], ["❌ Cancel"]]
        await update.message.reply_text(
            f"⚠️ Are you sure you want to delete:\n{product['title_en']}?",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        )
        return DELETE_CONFIRM
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")
        return DELETE_SELECT_PRODUCT

async def delete_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Execute product deletion."""
    text = update.message.text
    
    if text == "✅ YES, DELETE":
        if 'delete_product_id' not in context.user_data:
            await update.message.reply_text("❌ Session expired. Please start again.", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        product_id = context.user_data['delete_product_id']
        db.delete_product(product_id)
        await update.message.reply_text("✅ Product deleted!", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("❌ Deletion canceled.", reply_markup=ReplyKeyboardRemove())
    
    context.user_data.clear()
    return ConversationHandler.END

# ============================================================================
# MANAGE STOCK HANDLERS
# ============================================================================

async def start_manage_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show list of products to manage stock."""
    lang = get_lang(update.effective_user.id)
    
    products = db.get_products()
    if not products:
        await update.message.reply_text("❌ No products found.")
        return ConversationHandler.END
    
    message = "📦 Select product to update stock (send Product ID):\n\n"
    for p in products:
        title = p[f'title_{lang}'] if lang in ['en', 'ru'] else p['title_en']
        message += f"ID: {p['product_id']} - {title} (Stock: {p['stock']})\n"
    
    await update.message.reply_text(message)
    return STOCK_SELECT_PRODUCT

async def stock_product_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle product selection for stock update."""
    try:
        product_id = int(update.message.text)
        product = db.get_product(product_id)
        
        if not product:
            await update.message.reply_text("❌ Product not found.")
            return ConversationHandler.END
        
        context.user_data['stock_product_id'] = product_id
        await update.message.reply_text(
            f"Current stock: {product['stock']}\nEnter new stock value:"
        )
        return STOCK_NEW_VALUE
    except ValueError:
        await update.message.reply_text("❌ Invalid ID.")
        return STOCK_SELECT_PRODUCT

async def stock_new_value_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Update product stock."""
    if 'stock_product_id' not in context.user_data:
        await update.message.reply_text("❌ Session expired. Please start again.")
        return ConversationHandler.END
    
    text = update.message.text
    if is_command_button(text):
        await update.message.reply_text("⚠️ Operation cancelled. Select the command again.", reply_markup=ReplyKeyboardRemove())
        context.user_data.clear()
        return ConversationHandler.END

    try:
        text = text.strip().replace(',', '.')
        new_stock = int(float(text))
        product_id = context.user_data['stock_product_id']
        
        db.update_product_field(product_id, 'stock', new_stock)
        await update.message.reply_text(f"✅ Stock updated to {new_stock}!")
        
        context.user_data.clear()
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(f"❌ Invalid number: '{update.message.text}'. Please enter a valid integer.")
        return STOCK_NEW_VALUE
        return STOCK_NEW_VALUE

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
    
    await update.message.reply_text(f"✅ Added {count} codes!")
    context.user_data.clear()
    return ConversationHandler.END

# ============================================================================
# RECENT ORDERS HANDLER
# ============================================================================

async def show_recent_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show recent orders."""
    lang = get_lang(update.effective_user.id)
    
    orders = db.get_recent_orders(limit=10)
    
    if not orders:
        await update.message.reply_text("📊 No recent orders.")
        return
    
    message = "📊 Recent Orders:\n\n"
    for order in orders:
        product = db.get_product(order['product_id'])
        if product:
            title = product[f'title_{lang}'] if lang in ['en', 'ru'] else product['title_en']
            message += f"Order #{order['id']}: {title}\n"
            message += f"Price: ${order['amount_usd']} | Status: {order['status']}\n\n"
    
    await update.message.reply_text(message)

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
