"""
Admin Panel Handlers for Telegram Digital Bot
Handles all admin-only operations including product management.
"""
import os
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
import database as db
from strings import STRINGS

# Get admin user ID from environment
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

# Conversation states
(CHOOSING_TYPE, TITLE_EN, TITLE_RU, DESC_EN, DESC_RU, 
 PRICE, STOCK, DELIVERY_VALUE, CODES_INPUT) = range(9)

def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id == ADMIN_USER_ID

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin panel menu."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text(STRINGS["not_authorized"])
        return
    
    keyboard = [
        ["➕ Add Product", "✏️ Edit Product"],
        ["🗑️ Delete Product", "📦 Manage Stock"],
        ["📤 Manage Files", "🔑 Manage Codes"],
        ["📊 Recent Orders", "⬅️ Back"]
    ]
    
    await update.message.reply_text(
        STRINGS["admin_menu"],
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def start_add_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the add product conversation."""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text(STRINGS["not_authorized"])
        return ConversationHandler.END
    
    keyboard = [["link"], ["file"], ["code"], ["Cancel"]]
    
    await update.message.reply_text(
        STRINGS["choose_product_type"],
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    
    return CHOOSING_TYPE

async def product_type_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle product type selection."""
    text = update.message.text.lower()
    
    if text == "cancel":
        await update.message.reply_text(STRINGS["operation_canceled"], reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    if text not in ["link", "file", "code"]:
        await update.message.reply_text(STRINGS["invalid_input"])
        return CHOOSING_TYPE
    
    context.user_data['product_type'] = text
    await update.message.reply_text(STRINGS["enter_title_en"], reply_markup=ReplyKeyboardRemove())
    return TITLE_EN

async def title_en_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save English title."""
    context.user_data['title_en'] = update.message.text
    await update.message.reply_text(STRINGS["enter_title_ru"])
    return TITLE_RU

async def title_ru_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save Russian title."""
    context.user_data['title_ru'] = update.message.text
    await update.message.reply_text(STRINGS["enter_desc_en"])
    return DESC_EN

async def desc_en_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save English description."""
    context.user_data['desc_en'] = update.message.text
    await update.message.reply_text(STRINGS["enter_desc_ru"])
    return DESC_RU

async def desc_ru_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save Russian description."""
    context.user_data['desc_ru'] = update.message.text
    await update.message.reply_text(STRINGS["enter_price"])
    return PRICE

async def price_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save price."""
    try:
        price = float(update.message.text)
        context.user_data['price'] = price
        await update.message.reply_text(STRINGS["enter_stock"])
        return STOCK
    except ValueError:
        await update.message.reply_text(STRINGS["invalid_input"])
        return PRICE

async def stock_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save stock and request delivery value."""
    try:
        stock = int(update.message.text)
        context.user_data['stock'] = stock
        
        product_type = context.user_data['product_type']
        
        if product_type == "link":
            await update.message.reply_text(STRINGS["enter_link"])
            return DELIVERY_VALUE
        elif product_type == "file":
            await update.message.reply_text(STRINGS["send_file"])
            return DELIVERY_VALUE
        elif product_type == "code":
            await update.message.reply_text(STRINGS["send_codes"])
            return CODES_INPUT
    except ValueError:
        await update.message.reply_text(STRINGS["invalid_input"])
        return STOCK

async def delivery_value_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle delivery value (link or file)."""
    product_type = context.user_data['product_type']
    
    if product_type == "link":
        # Save the URL
        context.user_data['delivery_value'] = update.message.text
        return await finalize_product(update, context)
        
    elif product_type == "file":
        # Get file_id from the document/photo/video
        if update.message.document:
            file_id = update.message.document.file_id
        elif update.message.photo:
            file_id = update.message.photo[-1].file_id
        elif update.message.video:
            file_id = update.message.video.file_id
        else:
            await update.message.reply_text(STRINGS["invalid_input"])
            return DELIVERY_VALUE
        
        context.user_data['delivery_value'] = file_id
        return await finalize_product(update, context)

async def codes_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle codes input."""
    codes_text = update.message.text
    codes_list = [line.strip() for line in codes_text.split('\n') if line.strip()]
    
    context.user_data['codes'] = codes_list
    context.user_data['delivery_value'] = ""  # Codes don't have a single delivery value
    
    return await finalize_product(update, context)

async def finalize_product(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Create the product in database."""
    data = context.user_data
    
    # Add product to database
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
    
    # If type is code, add codes to codes table
    if data['product_type'] == 'code' and 'codes' in data:
        count = db.add_codes_bulk(product_id, data['codes'])
        await update.message.reply_text(
            STRINGS["product_created"].format(product_id=product_id) + "\n" + 
            STRINGS["codes_added"].format(count=count)
        )
    else:
        await update.message.reply_text(STRINGS["product_created"].format(product_id=product_id))
    
    # Clear user data
    context.user_data.clear()
    
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text(STRINGS["operation_canceled"], reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END
