import database as db
import datetime as dt

db.init_db()

print("--- Forcing Stock Update Settings ---")
db.set_setting("stock_update_enabled", "1")
db.set_setting("stock_update_en", "📢 <b>Stock Update Test EN</b>\nProduct A - $10")
db.set_setting("stock_update_ru", "📢 <b>Обновление Тест RU</b>\nТовар А - $10")

print("Verification:")
print(f"Enabled: {db.get_setting('stock_update_enabled')}")
print(f"EN Msg: {db.get_setting('stock_update_en')}")
