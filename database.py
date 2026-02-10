import sqlite3
import os

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
    conn = sqlite3.connect(DB_NAME)
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
            status TEXT DEFAULT 'pending', -- 'pending', 'paid', 'delivered'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(product_id) REFERENCES products(product_id)
        )
    ''')
    
    conn.commit()
    conn.close()

def add_user(user_id, language):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO users (user_id, language) VALUES (?, ?)', (user_id, language))
    conn.commit()
    conn.close()

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
    return rows

def get_product(product_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE product_id = ?', (product_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def create_order(user_id, product_id, invoice_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO orders (user_id, product_id, invoice_id, status) VALUES (?, ?, ?, ?)',
                   (user_id, product_id, invoice_id, 'pending'))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return order_id

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

if __name__ == "__main__":
    init_db()
    seed_products()
