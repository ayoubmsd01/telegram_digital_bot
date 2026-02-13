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
        ("delivered_at", "TEXT")
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
    
    # Migration for users table (if older version exists)
    try:
        c.execute("ALTER TABLE users ADD COLUMN username TEXT")
    except: pass
    try:
        c.execute("ALTER TABLE users ADD COLUMN joined_at TEXT")
    except: pass

    # Settings table
    c.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database tables initialized successfully.")

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

def get_products():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def create_order(user_id, product_id, invoice_id, price_usd=0.0):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO orders (user_id, product_id, invoice_id, price_usd, status) VALUES (?, ?, ?, ?, ?)',
                   (user_id, product_id, invoice_id, price_usd, 'pending'))
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
    # Get product_id to restore stock
    cursor.execute('SELECT product_id, status FROM orders WHERE order_id = ?', (order_id,))
    row = cursor.fetchone()
    if row and row['status'] == 'pending':
        cursor.execute("UPDATE orders SET status = 'canceled' WHERE order_id = ?", (order_id,))
        # Increase stock back
        cursor.execute('UPDATE products SET stock = stock + 1 WHERE product_id = ?', (row['product_id'],))
        conn.commit()
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

def get_product(product_id):
    """Get a single product by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE product_id = ?', (product_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def increment_stock(product_id, qty):
    """Increment product stock by qty."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE products SET stock = stock + ? WHERE product_id = ?', (qty, product_id))
    conn.commit()
    conn.close()

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
