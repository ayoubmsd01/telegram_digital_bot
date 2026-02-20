import sqlite3
import os
import datetime as dt

DB_NAME = os.getenv("DB_PATH", "shop.db")

def seed_products():
    """Seed some initial products for testing if empty."""
    conn = get_connection()
    cursor = conn.cursor()
    # Create tables first just in case
    init_db()
    
    cursor.execute('SELECT count(*) FROM products')
    try:
        count = cursor.fetchone()[0]
    except:
        count = 0
        
    if count == 0:
        products = [
            ("Premium VPN 1 Month", "Premium VPN 1 Month", "High speed VPN key", "Ключ для быстрого VPN", 5.0, 10, "code", "VPN-KEY-12345"),
            ("E-Book Python Guide", "E-Book Python Guide", "Learn Python fast", "Учи Python быстро", 10.0, 5, "link", "https://example.com/book.pdf"),
            ("Exclusive File", "Exclusive File", "Secret document", "Секретный документ", 2.0, 50, "file", "FILE_ID_PLACEHOLDER")
        ]
        cursor.executemany('''
            INSERT INTO products (title_en, title_ru, desc_en, desc_ru, price_usd, stock, delivery_type, delivery_value)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', products)
        conn.commit()
        print("Seeded initial products.")
    conn.close()

def get_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            language TEXT
        )
    ''')
    
    # Products table
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY AUTOINCREMENT,
            title_ru TEXT,
            title_en TEXT,
            desc_ru TEXT,
            desc_en TEXT,
            price_usd REAL,
            stock INTEGER,
            delivery_type TEXT, -- 'link', 'file', 'code'
            delivery_value TEXT -- The actual link, file_id, or code text
        )
    ''')
    
    # Orders table
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            invoice_id INTEGER,
            status TEXT DEFAULT 'pending', -- 'pending', 'paid', 'delivered', 'canceled'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(product_id) REFERENCES products(product_id)
        )
    ''')
    
    # Codes table for code-based products
    c.execute('''
        CREATE TABLE IF NOT EXISTS codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            is_used INTEGER DEFAULT 0,
            used_by INTEGER,
            used_at TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES products(product_id)
        )
    ''')
    
    # Migrations: Add new columns to orders table safely
    columns_to_add = [
        ("price_usd", "REAL"),
        ("paid_amount", "TEXT"),
        ("paid_asset", "TEXT"),
        ("paid_at", "TEXT"),
        ("delivered_type", "TEXT"),
        ("delivered_value", "TEXT"),
        ("delivered_filename", "TEXT"),
        ("delivered_at", "TEXT"),
        ("used_balance", "REAL DEFAULT 0"),
        ("need_crypto", "REAL DEFAULT 0")
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            c.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            # Column likely already exists
            pass
            
    # Settings table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, 
            language TEXT,
            username TEXT,
            joined_at TEXT
        )
    ''')

    # Categories Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_ru TEXT NOT NULL,
            name_en TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1
        )
    ''')

    # Stock Items Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS stock_items (
            stock_id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            content TEXT,
            file_id TEXT,
            status TEXT DEFAULT 'available',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES products(product_id)
        )
    ''')
    
    # Migrations for existing tables
    try:
        c.execute("ALTER TABLE users ADD COLUMN username TEXT")
    except: pass
    try:
        c.execute("ALTER TABLE users ADD COLUMN joined_at TEXT")
    except: pass
    try:
        c.execute("ALTER TABLE products ADD COLUMN category_id INTEGER DEFAULT 0")
    except: pass
    try:
        c.execute("ALTER TABLE products ADD COLUMN is_active INTEGER DEFAULT 1")
    except: pass
    try:
        c.execute("ALTER TABLE orders ADD COLUMN stock_id INTEGER DEFAULT 0")
    except: pass

    # Settings table
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT
        )
    ''')
    
    # Bans table for Silent Ban system
    c.execute('''
        CREATE TABLE IF NOT EXISTS bans (
            user_id INTEGER PRIMARY KEY,
            banned_at TEXT NOT NULL
        )
    ''')
    
    # Topups table for balance top-up invoices
    c.execute('''
        CREATE TABLE IF NOT EXISTS topups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER UNIQUE,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT 'USD',
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            paid_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    
    # Admin balance adjustments log
    c.execute('''
        CREATE TABLE IF NOT EXISTS admin_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL
        )
    ''')
    
    # Migration: add balance column to users if missing
    try:
        c.execute("ALTER TABLE users ADD COLUMN balance REAL DEFAULT 0.0")
    except: pass
    
    # Favorites table
    c.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER,
            product_id INTEGER,
            created_at TEXT NOT NULL,
            PRIMARY KEY (user_id, product_id),
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(product_id) REFERENCES products(product_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # Initialize the ban cache
    _refresh_ban_cache()
    
    print("Database tables initialized successfully.")

# ============================================================================
# SILENT BAN SYSTEM
# ============================================================================

# In-memory cache for banned user IDs (fast O(1) lookup per message)
_banned_users_cache = set()

def _refresh_ban_cache():
    """Reload the banned users set from the database."""
    global _banned_users_cache
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM bans')
        rows = cursor.fetchall()
        conn.close()
        _banned_users_cache = {row['user_id'] for row in rows}
    except Exception:
        pass  # Keep existing cache on error

def is_banned(user_id: int) -> bool:
    """Check if a user is banned. Uses in-memory cache for speed."""
    return user_id in _banned_users_cache

def ban_user(user_id: int) -> bool:
    """Ban a user silently. Returns True if newly banned, False if already banned."""
    import datetime as dt
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT OR IGNORE INTO bans (user_id, banned_at) VALUES (?, ?)',
            (user_id, dt.datetime.now().isoformat())
        )
        conn.commit()
        newly_banned = cursor.rowcount > 0
    except Exception:
        newly_banned = False
    finally:
        conn.close()
    
    # Update cache immediately
    _banned_users_cache.add(user_id)
    return newly_banned

def unban_user(user_id: int) -> bool:
    """Unban a user. Returns True if was banned, False if wasn't."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM bans WHERE user_id = ?', (user_id,))
    conn.commit()
    was_banned = cursor.rowcount > 0
    conn.close()
    
    # Update cache immediately
    _banned_users_cache.discard(user_id)
    return was_banned

def get_banned_users():
    """Get all banned users with their ban dates."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, banned_at FROM bans ORDER BY banned_at DESC')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ============================================================================
# USER MANAGEMENT
# ============================================================================

def add_user(user_id, language, username=None):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Get current time if new
    import datetime as dt
    now = dt.datetime.now().isoformat()
    
    # We use INSERT OR REPLACE. If updating, we want to keep joined_at if possible, 
    # but REPLACE deletes the row. Ideally utilize ON CONFLICT strictly for updates.
    # Simple approach: Check existence first.
    cursor.execute('SELECT joined_at FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    
    if row:
        joined = row['joined_at']
        cursor.execute('''
            UPDATE users SET language = ?, username = ? WHERE user_id = ?
        ''', (language, username, user_id))
    else:
        cursor.execute('''
            INSERT INTO users (user_id, language, username, joined_at) VALUES (?, ?, ?, ?)
        ''', (user_id, language, username, now))
        
    conn.commit()
    conn.close()

def update_user_name(user_id, username):
    """Update only the username if it changed or is missing."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET username = ? WHERE user_id = ?', (username, user_id))
    conn.commit()
    conn.close()

def add_favorite(user_id, product_id):
    """Add a product to user favorites. Ignore if already exists."""
    import datetime as dt
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            'INSERT INTO favorites (user_id, product_id, created_at) VALUES (?, ?, ?)',
            (user_id, product_id, dt.datetime.now().isoformat())
        )
        conn.commit()
    except Exception:
        pass # Already exists
    conn.close()

def check_favorite(user_id, product_id) -> bool:
    """Check if a product is in user favorites."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM favorites WHERE user_id = ? AND product_id = ?', (user_id, product_id))
    row = cursor.fetchone()
    conn.close()
    return bool(row)

def get_product_favorites(product_id):
    """Get all user_ids who favorited a specific product."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM favorites WHERE product_id = ?', (product_id,))
    rows = cursor.fetchall()
    conn.close()
    return [row['user_id'] for row in rows]

def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, language, username, joined_at FROM users')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_user_language(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT language FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row['language'] if row else None

def get_user_profile(user_id):
    """Get user profile data."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, language, username, joined_at, balance FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_purchases_count(user_id):
    """Count completed purchases (paid or delivered) for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) as cnt FROM orders WHERE user_id = ? AND status IN ('paid', 'delivered')",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row['cnt'] if row else 0

def get_user_balance(user_id):
    """Get user balance."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row['balance'] is not None:
        return float(row['balance'])
    return 0.0

def add_user_balance(user_id, amount):
    """Add amount to user balance (atomic). Returns new balance."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET balance = COALESCE(balance, 0) + ? WHERE user_id = ?',
        (amount, user_id)
    )
    conn.commit()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return float(row['balance']) if row else amount

def deduct_user_balance(user_id, amount):
    """Deduct amount from user balance. Returns True if enough balance else False."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Atomic deduction to prevent race conditions
    cursor.execute(
        'UPDATE users SET balance = balance - ? WHERE user_id = ? AND balance >= ?',
        (amount, user_id, amount)
    )
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def create_topup(invoice_id, user_id, amount, currency='USD'):
    """Create a topup record."""
    import datetime as dt
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO topups (invoice_id, user_id, amount, currency, status, created_at) VALUES (?, ?, ?, ?, ?, ?)',
        (invoice_id, user_id, amount, currency, 'pending', dt.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def update_topup_status(invoice_id, status, paid_at=None):
    """Update topup status. Returns True if updated, False if already in that status."""
    conn = get_connection()
    cursor = conn.cursor()
    if paid_at:
        cursor.execute(
            'UPDATE topups SET status = ?, paid_at = ? WHERE invoice_id = ? AND status != ?',
            (status, paid_at, invoice_id, status)
        )
    else:
        cursor.execute(
            'UPDATE topups SET status = ? WHERE invoice_id = ? AND status != ?',
            (status, invoice_id, status)
        )
    updated = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return updated

def get_topup_by_invoice(invoice_id):
    """Get topup record by CryptoPay invoice_id."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM topups WHERE invoice_id = ?', (invoice_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_orders(user_id, limit=20):
    """Get orders for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM orders WHERE user_id = ? AND status IN ('paid', 'delivered') ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_user_topups(user_id, limit=20):
    """Get topup history for a user."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM topups WHERE user_id = ? ORDER BY created_at DESC LIMIT ?',
        (user_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_admin_adjustment(admin_id, user_id, amount, note=None):
    """Log an admin balance adjustment."""
    import datetime as dt
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO admin_adjustments (admin_id, user_id, amount, note, created_at) VALUES (?, ?, ?, ?, ?)',
        (admin_id, user_id, amount, note, dt.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def get_products(category_id=None, only_active=True):
    conn = get_connection()
    cursor = conn.cursor()
    
    query = '''
        SELECT p.*, 
               (SELECT COUNT(*) FROM stock_items WHERE product_id = p.product_id AND status='available') as real_stock
        FROM products p
        WHERE 1=1
    '''
    params = []
    
    if only_active:
        query += " AND p.is_active = 1"
    if category_id is not None:
        query += " AND p.category_id = ?"
        params.append(category_id)
        
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    conn.close()
    
    products = []
    for row in rows:
        d = dict(row)
        d['stock'] = d['real_stock']
        products.append(d)
    return products

def get_product(product_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.*, 
               (SELECT COUNT(*) FROM stock_items WHERE product_id = p.product_id AND status='available') as real_stock
        FROM products p 
        WHERE p.product_id = ?
    ''', (product_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        d['stock'] = d['real_stock']
        return d
    return None

def add_category(name_ru, name_en):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO categories (name_ru, name_en) VALUES (?, ?)', (name_ru, name_en))
    cat_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return cat_id

def get_categories(only_active=True):
    conn = get_connection()
    cursor = conn.cursor()
    query = 'SELECT * FROM categories'
    if only_active:
        query += ' WHERE is_active = 1'
    query += ' ORDER BY sort_order, category_id'
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_category(category_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM categories WHERE category_id = ?', (category_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def add_stock_item(product_id, type_str, content=None, file_id=None):
    """Add a single stock item."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO stock_items (product_id, type, content, file_id, status)
        VALUES (?, ?, ?, ?, 'available')
    ''', (product_id, type_str, content, file_id))
    conn.commit()
    conn.close()
    return True

def add_stock_items_bulk(product_id, type_str, contents_list):
    """Add multiple stock items (usually codes)."""
    conn = get_connection()
    cursor = conn.cursor()
    data = [(product_id, type_str, c.strip(), None, 'available') for c in contents_list if c.strip()]
    cursor.executemany('''
        INSERT INTO stock_items (product_id, type, content, file_id, status)
        VALUES (?, ?, ?, ?, ?)
    ''', data)
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count

def reserve_stock_item(product_id):
    """Reserves one stock item for a product and returns it."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT stock_id, type, content, file_id 
        FROM stock_items 
        WHERE product_id = ? AND status = 'available' 
        ORDER BY stock_id ASC
        LIMIT 1
    ''', (product_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
        
    stock_id = row['stock_id']
    cursor.execute("UPDATE stock_items SET status = 'reserved' WHERE stock_id = ?", (stock_id,))
    conn.commit()
    conn.close()
    return dict(row)

def release_stock_item(stock_id):
    """Release a reserved stock item back to available."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE stock_items SET status = 'available' WHERE stock_id = ?", (stock_id,))
    conn.commit()
    conn.close()

def mark_stock_item_sold(stock_id):
    """Mark a stock item as sold."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE stock_items SET status = 'sold' WHERE stock_id = ?", (stock_id,))
    conn.commit()
    conn.close()

def get_stock_item(stock_id):
    """Get a stock item by its ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stock_items WHERE stock_id = ?", (stock_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def create_order(user_id, product_id, invoice_id, price_usd=0.0, used_balance=0.0, need_crypto=0.0, stock_id=0):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO orders (user_id, product_id, invoice_id, price_usd, status, used_balance, need_crypto, stock_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        (user_id, product_id, invoice_id, price_usd, 'pending', used_balance, need_crypto, stock_id)
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return order_id

def update_order_delivery(order_id, type, value, filename, timestamp):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE orders 
        SET delivered_type = ?, delivered_value = ?, delivered_filename = ?, delivered_at = ? 
        WHERE order_id = ?
    ''', (type, value, filename, timestamp, order_id))
    conn.commit()
    conn.close()

def update_order_payment(order_id, amount, asset, timestamp):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE orders 
        SET paid_amount = ?, paid_asset = ?, paid_at = ?
        WHERE order_id = ?
    ''', (amount, asset, timestamp, order_id))
    conn.commit()
    conn.close()

def get_order_by_invoice(invoice_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE invoice_id = ?', (invoice_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_order_status(order_id, status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE orders SET status = ? WHERE order_id = ?', (status, order_id))
    conn.commit()
    conn.close()

def decrease_stock(product_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE products SET stock = stock - 1 WHERE product_id = ? AND stock > 0', (product_id,))
    conn.commit()
    conn.close()

def increase_stock(product_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE products SET stock = stock + 1 WHERE product_id = ?', (product_id,))
    conn.commit()
    conn.close()

def get_expired_pending_orders(minutes=15):
    conn = get_connection()
    cursor = conn.cursor()
    # SQLite 'datetime' modifier usage
    cursor.execute(f'''
        SELECT * FROM orders 
        WHERE status = 'pending' 
        AND created_at < datetime('now', '-{minutes} minutes')
    ''')
    rows = cursor.fetchall()
    conn.close()
    return rows

def cancel_order_db(order_id):
    conn = get_connection()
    cursor = conn.cursor()
    # Get order info to restore stock and refund balance
    cursor.execute('SELECT product_id, status, user_id, used_balance, stock_id FROM orders WHERE order_id = ?', (order_id,))
    row = cursor.fetchone()
    if row and row['status'] == 'pending':
        cursor.execute("UPDATE orders SET status = 'canceled' WHERE order_id = ?", (order_id,))
        # Increase stock back
        stock_id = row['stock_id']
        if stock_id:
            cursor.execute("UPDATE stock_items SET status = 'available' WHERE stock_id = ?", (stock_id,))
            
        # Refund used_balance back to user
        used_bal = row['used_balance'] or 0
        if used_bal > 0:
            cursor.execute(
                'UPDATE users SET balance = COALESCE(balance, 0) + ? WHERE user_id = ?',
                (used_bal, row['user_id'])
            )
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False

# Code management functions
def get_unused_code(product_id):
    """Get one unused code for a product."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM codes WHERE product_id = ? AND is_used = 0 LIMIT 1', (product_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def mark_code_as_used(code_id, user_id):
    """Mark a code as used."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE codes 
        SET is_used = 1, used_by = ?, used_at = CURRENT_TIMESTAMP 
        WHERE id = ?
    ''', (user_id, code_id))
    conn.commit()
    conn.close()

def add_codes_bulk(product_id, codes_list):
    """Add multiple codes for a product."""
    conn = get_connection()
    cursor = conn.cursor()
    codes_data = [(product_id, code.strip()) for code in codes_list if code.strip()]
    cursor.executemany('INSERT INTO codes (product_id, code) VALUES (?, ?)', codes_data)
    conn.commit()
    count = cursor.rowcount
    conn.close()
    return count

def get_codes_count(product_id):
    """Get count of unused codes for a product."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM codes WHERE product_id = ? AND is_used = 0', (product_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

# Product management functions
def add_product(title_en, title_ru, desc_en, desc_ru, price_usd, stock, delivery_type, delivery_value):
    """Add a new product."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO products (title_en, title_ru, desc_en, desc_ru, price_usd, stock, delivery_type, delivery_value)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (title_en, title_ru, desc_en, desc_ru, price_usd, stock, delivery_type, delivery_value))
    product_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return product_id

def update_product(product_id, title_en, title_ru, desc_en, desc_ru, price_usd, stock, delivery_value):
    """Update an existing product."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE products 
        SET title_en = ?, title_ru = ?, desc_en = ?, desc_ru = ?, price_usd = ?, stock = ?, delivery_value = ?
        WHERE product_id = ?
    ''', (title_en, title_ru, desc_en, desc_ru, price_usd, stock, delivery_value, product_id))
    conn.commit()
    conn.close()

def delete_product(product_id):
    """Delete a product and its codes."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM codes WHERE product_id = ?', (product_id,))
    cursor.execute('DELETE FROM products WHERE product_id = ?', (product_id,))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    seed_products()


def increment_stock(product_id, qty):
    """Increment product stock by qty. Returns True if stock was 0 before."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT stock FROM products WHERE product_id = ?', (product_id,))
    row = cursor.fetchone()
    old_stock = row['stock'] if row else 0

    cursor.execute('UPDATE products SET stock = stock + ? WHERE product_id = ?', (qty, product_id))
    conn.commit()
    conn.close()
    return old_stock == 0 and qty > 0

def update_product_field(product_id, field, value):
    """Update a single field of a product."""
    conn = get_connection()
    cursor = conn.cursor()
    query = f'UPDATE products SET {field} = ? WHERE product_id = ?'
    cursor.execute(query, (value, product_id))
    conn.commit()
    conn.close()

def count_available_codes(product_id):
    """Count available (unused) codes for a product."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM codes WHERE product_id = ? AND is_used = 0', (product_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_recent_orders(limit=20):
    """Get recent orders with product details."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f'''
        SELECT 
            o.order_id, o.user_id, o.status, o.created_at, o.invoice_id,
            p.title_en, p.price_usd, p.product_id
        FROM orders o
        LEFT JOIN products p ON o.product_id = p.product_id
        ORDER BY o.order_id DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_order(order_id):
    """Get single order by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def update_order_status(order_id, status):
    """Update status of an order."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE orders SET status = ? WHERE order_id = ?', (status, order_id))
    conn.commit()
    conn.close()

def set_setting(key, value):
    conn = get_connection()
    cursor = conn.cursor()
    import datetime as dt
    now = dt.datetime.now().isoformat()
    # ensure value is string
    cursor.execute('INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)', (key, str(value), now))
    conn.commit()
    conn.close()

def get_setting(key):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else None
