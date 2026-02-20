import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import database as db
from strings import STRINGS
from admin_handlers import is_admin

logger = logging.getLogger(__name__)

# Constants for states
ADD_CAT_RU = 2001
ADD_CAT_EN = 2002

PRODUCT_SELECT_OPTION = 2003
PRODUCT_SELECT_CAT = 2004
PRODUCT_TITLE_RU = 2005
PRODUCT_TITLE_EN = 2006
PRODUCT_PRICE = 2007

STOCK_SELECT_CAT = 2010
STOCK_SELECT_PROD = 2011
STOCK_SELECT_TYPE = 2012
STOCK_INPUT = 2013

async def start_add_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user):
        return ConversationHandler.END
    await update.message.reply_text(
        "📥 <b>Add Category</b>\n\nEnter the category name in Russian:\n(Send /cancel to abort)",
        parse_mode="HTML"
    )
    return ADD_CAT_RU

async def add_cat_ru(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text
    if txt == '/cancel':
        await update.message.reply_text("❌ Cancelled.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    context.user_data['cat_ru'] = txt
    await update.message.reply_text("📥 Enter the category name in English:")
    return ADD_CAT_EN

async def add_cat_en(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text
    if txt == '/cancel':
        await update.message.reply_text("❌ Cancelled.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    ru = context.user_data['cat_ru']
    en = txt
    db.add_category(ru, en)
    await update.message.reply_text(f"✅ Category added!\nRU: {ru}\nEN: {en}")
    context.user_data.clear()
    from admin_handlers import admin_panel
    # Redirect back to admin_panel doesn't strictly work this way but we can call it.
    await admin_panel(update, context)
    return ConversationHandler.END


async def start_add_product_stock(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_user):
        return ConversationHandler.END
        
    keyboard = [
        ["🆕 New product"],
        ["➕ Add stock to existing"],
        ["Cancel"]
    ]
    await update.message.reply_text(
        "What would you like to do?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return PRODUCT_SELECT_OPTION

async def product_option_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text
    if txt == 'Cancel':
        await update.message.reply_text("❌ Cancelled.", reply_markup=ReplyKeyboardRemove())
        from admin_handlers import admin_panel
        await admin_panel(update, context)
        return ConversationHandler.END
        
    categories = db.get_categories(only_active=True)
    if not categories:
        await update.message.reply_text("⚠️ No categories found. Please add a category first.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    keyboard = []
    for c in categories:
        keyboard.append([InlineKeyboardButton(f"📁 {c['name_ru']} / {c['name_en']}", callback_data=f"selcat_{c['category_id']}")])

    if txt == "🆕 New product":
        context.user_data['action'] = "new_product"
        await update.message.reply_text(
            "Please select a Category for the NEW product:", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return PRODUCT_SELECT_CAT
        
    elif txt == "➕ Add stock to existing":
        context.user_data['action'] = "add_stock"
        await update.message.reply_text(
            "Please select a Category first:", 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return STOCK_SELECT_CAT
        
    return PRODUCT_SELECT_OPTION

async def product_cat_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    cat_id = int(data.split("_")[1])
    context.user_data['cat_id'] = cat_id
    
    await query.edit_message_text("📥 Enter product title in Russian:")
    return PRODUCT_TITLE_RU

async def product_title_ru(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['title_ru'] = update.message.text
    await update.message.reply_text("📥 Enter product title in English:")
    return PRODUCT_TITLE_EN

async def product_title_en(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['title_en'] = update.message.text
    await update.message.reply_text("📥 Enter the price in USD (e.g. 5.99):")
    return PRODUCT_PRICE

async def product_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    txt = update.message.text.replace(',', '.')
    try:
        price = float(txt)
    except:
        await update.message.reply_text("❌ Invalid price. Enter a number (e.g. 10.50):")
        return PRODUCT_PRICE
        
    cat_id = context.user_data['cat_id']
    ru = context.user_data['title_ru']
    en = context.user_data['title_en']
    
    # Insert product
    conn = db.get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO products (title_ru, title_en, price_usd, category_id, stock) VALUES (?, ?, ?, ?, 0)",
        (ru, en, price, cat_id)
    )
    prod_id = c.lastrowid
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ Product created successfully!\nID: {prod_id}\n\nYou can now go to '➕ Add Product/Stock' -> 'Add stock to existing' to add actual stock items for this product.")
    
    from admin_handlers import admin_panel
    # We delay admin_panel since reply_text was just sent
    await admin_panel(update, context)
    context.user_data.clear()
    return ConversationHandler.END


# Add Stock Flow
async def stock_cat_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.split("_")[1])
    
    products = db.get_products(category_id=cat_id, only_active=True)
    if not products:
        await query.edit_message_text("⚠️ No products found in this category.")
        return ConversationHandler.END
        
    keyboard = []
    for p in products:
        keyboard.append([InlineKeyboardButton(p['title_en'], callback_data=f"selprod_{p['product_id']}")])
        
    await query.edit_message_text("Select a Product to add stock to:", reply_markup=InlineKeyboardMarkup(keyboard))
    return STOCK_SELECT_PROD
    

async def stock_prod_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split("_")[1])
    context.user_data['prod_id'] = prod_id
    
    keyboard = [
        [InlineKeyboardButton("📄 Add file", callback_data="type_file")],
        [InlineKeyboardButton("🔗 Add link", callback_data="type_link")],
        [InlineKeyboardButton("🔑 Add code", callback_data="type_code")]
    ]
    await query.edit_message_text("Select stock type:", reply_markup=InlineKeyboardMarkup(keyboard))
    return STOCK_SELECT_TYPE

async def stock_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    type_str = query.data.split("_")[1] # file, link, code
    context.user_data['stock_type'] = type_str
    
    if type_str == 'file':
        await query.edit_message_text("Upload the file below:\n(Or send /done when finished)")
    elif type_str == 'link':
        await query.edit_message_text("Send the link below:\n(Or send /done when finished)")
    elif type_str == 'code':
        await query.edit_message_text("Send codes (one per message, or multiple codes separated by newlines):\n(Send /done when finished)")
        
    return STOCK_INPUT

async def stock_input_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message and update.message.text == '/done':
        await update.message.reply_text("✅ Stock addition complete.")
        from admin_handlers import admin_panel
        await admin_panel(update, context)
        context.user_data.clear()
        return ConversationHandler.END
        
    prod_id = context.user_data['prod_id']
    stype = context.user_data['stock_type']
    
    was_empty = (db.get_product(prod_id)['stock'] == 0)
    qty_added = 0
    
    if stype == 'file':
        if not update.message.document:
            await update.message.reply_text("❌ Please upload a file.")
            return STOCK_INPUT
            
        file_id = update.message.document.file_id
        db.add_stock_item(prod_id, 'file', file_id=file_id)
        qty_added = 1
        await update.message.reply_text("✅ File saved! Send another file or /done.")
        
    elif stype == 'link':
        if not update.message.text:
            return STOCK_INPUT
        db.add_stock_item(prod_id, 'link', content=update.message.text)
        qty_added = 1
        await update.message.reply_text("✅ Link saved! Send another or /done.")
        
    elif stype == 'code':
        if not update.message.text:
            return STOCK_INPUT
        codes = update.message.text.split("\n")
        qty_added = db.add_stock_items_bulk(prod_id, 'code', codes)
        await update.message.reply_text(f"✅ Saved {qty_added} codes! Send more or /done.")
        
    if was_empty and qty_added > 0:
        from admin_handlers import trigger_restock_notifications
        await trigger_restock_notifications(prod_id, context)

    return STOCK_INPUT

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Operation cancelled.", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

async def list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(update.effective_user):
        return
    categories = db.get_categories(only_active=True)
    if not categories:
        await update.message.reply_text("🗂 No categories exist.", parse_mode="HTML")
        return
        
    msg = "🗂 <b>Categories</b>\n\n"
    for c in categories:
        msg += f"ID {c['category_id']}: {c['name_en']} / {c['name_ru']}\n"
    await update.message.reply_text(msg, parse_mode="HTML")

# Export the ConversationHandlers so they can be added to bot.py
add_category_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Add Category$"), start_add_category)],
    states={
        ADD_CAT_RU: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_cat_ru)],
        ADD_CAT_EN: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_cat_en)],
    },
    fallbacks=[CommandHandler("cancel", cancel_handler)]
)

add_product_stock_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Add Product/Stock$"), start_add_product_stock)],
    states={
        PRODUCT_SELECT_OPTION: [MessageHandler(filters.TEXT, product_option_chosen)],
        
        PRODUCT_SELECT_CAT: [CallbackQueryHandler(product_cat_selected, pattern="^selcat_")],
        PRODUCT_TITLE_RU: [MessageHandler(filters.TEXT & ~filters.COMMAND, product_title_ru)],
        PRODUCT_TITLE_EN: [MessageHandler(filters.TEXT & ~filters.COMMAND, product_title_en)],
        PRODUCT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, product_price)],
        
        STOCK_SELECT_CAT: [CallbackQueryHandler(stock_cat_selected, pattern="^selcat_")],
        STOCK_SELECT_PROD: [CallbackQueryHandler(stock_prod_selected, pattern="^selprod_")],
        STOCK_SELECT_TYPE: [CallbackQueryHandler(stock_type_selected, pattern="^type_")],
        STOCK_INPUT: [MessageHandler(filters.ALL, stock_input_received)]
    },
    fallbacks=[CommandHandler("cancel", cancel_handler), MessageHandler(filters.Regex("^Cancel$"), cancel_handler)]
)
