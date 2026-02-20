import database as db

def run_migration():
    conn = db.get_connection()
    cursor = conn.cursor()

    # 1. Ensure at least one category exists
    cursor.execute("SELECT * FROM categories ORDER BY sort_order, category_id LIMIT 1")
    cat = cursor.fetchone()
    if not cat:
        cursor.execute("INSERT INTO categories (name_ru, name_en) VALUES ('Общее', 'General')")
        cat_id = cursor.lastrowid
        conn.commit()
        print(f"Created default category with ID {cat_id}")
    else:
        cat_id = cat['category_id']
        print(f"Using existing default category ID {cat_id}")

    # 2. Update all products without category
    cursor.execute("UPDATE products SET category_id = ? WHERE category_id = 0 OR category_id IS NULL", (cat_id,))
    updated_cats = cursor.rowcount
    conn.commit()
    print(f"Updated {updated_cats} products to belong to category {cat_id}")

    # 3. Migrate existing stock
    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    migrated_products = 0
    migrated_items = 0

    for p in products:
        p_id = p['product_id']
        base_stock = p['stock']
        d_type = p['delivery_type']
        d_val = p['delivery_value']
        
        # Check if we already migrated this product by looking for stock_items
        cursor.execute("SELECT COUNT(*) FROM stock_items WHERE product_id = ?", (p_id,))
        if cursor.fetchone()[0] > 0:
            continue # Already has stock items, skip
            
        if d_type == 'code':
            # Migrate from `codes` table
            cursor.execute("SELECT * FROM codes WHERE product_id = ? AND is_used = 0", (p_id,))
            codes = cursor.fetchall()
            for code_row in codes:
                cursor.execute(
                    "INSERT INTO stock_items (product_id, type, content, status) VALUES (?, ?, ?, 'available')",
                    (p_id, 'code', code_row['code'])
                )
                migrated_items += 1
            migrated_products += 1
            
        elif d_type in ['link', 'file']:
            # We don't have a list of items, just a stock count and a single value.
            # We need to replicate the item `base_stock` times.
            if base_stock > 0:
                for _ in range(base_stock):
                    if d_type == 'link':
                        cursor.execute(
                            "INSERT INTO stock_items (product_id, type, content, status) VALUES (?, ?, ?, 'available')",
                            (p_id, 'link', d_val)
                        )
                    elif d_type == 'file':
                        cursor.execute(
                            "INSERT INTO stock_items (product_id, type, file_id, status) VALUES (?, ?, ?, 'available')",
                            (p_id, 'file', d_val)
                        )
                    migrated_items += 1
                migrated_products += 1

    conn.commit()
    conn.close()

    print(f"Migration complete. Migrated {migrated_items} stock items for {migrated_products} products.")

if __name__ == '__main__':
    run_migration()
