import database as db
import asyncio

db.init_db()

async def run_test():
    # 1. Create a category
    cat_id = db.add_category("🇨🇭 Tutti GMX", "🇨🇭 Tutti GMX")
    
    # 2. Add products
    conn = db.get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO products (title_ru, price_usd, category_id, stock) VALUES (?, ?, ?, 0)",
              ("🇨🇭 Tutti.ch — mail access", 18.0, cat_id))
    p1_id = c.lastrowid
    
    cat2_id = db.add_category("🇨🇭 Anibis MIX .CH DOMEN", "🇨🇭 Anibis MIX .CH DOMEN")
    c.execute("INSERT INTO products (title_ru, price_usd, category_id, stock) VALUES (?, ?, ?, 0)",
              ("🇨🇭 Anibis.ch — mail access | IMAP ", 6.0, cat2_id))
    p2_id = c.lastrowid
    
    c.execute("INSERT INTO products (title_ru, price_usd, category_id, stock) VALUES (?, ?, ?, 0)",
              ("🇨🇭 Dead Stock | No Items ", 10.0, cat2_id))
    p3_id = c.lastrowid
    
    conn.commit()
    conn.close()
    
    db.add_stock_items_bulk(p1_id, 'code', ['c1', 'c2', 'c3', 'c4'])
    db.add_stock_items_bulk(p2_id, 'code', ['c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7', 'c8'])
    # p3_id stays at 0
    
    # Render
    lang = "ru"
    categories = db.get_categories(only_active=True)
    blocks = []
    
    for c in categories:
        c_id = c["category_id"]
        cat_name = c["name_ru"]
        products = db.get_products(category_id=c_id, only_active=True)
        visible_products = [p for p in products if p["stock"] > 0]
        
        if not visible_products:
            continue
            
        block = f"— — — {cat_name} — — —\n"
        for p in visible_products:
            p_id = p["product_id"]
            title = p["title_ru"]
            price = p["price_usd"]
            stock = p["stock"]
            stock_text = f"{stock} шт."
            
            parts = title.split('|', 1)
            name_part = parts[0].strip()
            rest_part = ""
            if len(parts) > 1:
                rest_part = " | " + parts[1].strip()
                
            link = f'<a href="https://t.me/TestBotName?start=prod_{p_id}">{name_part}</a>'
            line = f"{link}{rest_part} | {stock_text} | ${price:g}\n"
            block += line
            
        block += "\n"
        blocks.append(block)
    
    for b in blocks:
        print(b, end="")

if __name__ == "__main__":
    asyncio.run(run_test())
