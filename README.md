# 🤖 Telegram Digital Shop Bot

Bot Telegram للتجارة الإلكترونية مع دعم المدفوعات والتوصيل التلقائي.

## 🚀 النشر السريع على Railway

### الخطوة 1: افتح Railway Dashboard
اذهب إلى: https://railway.app/dashboard

### الخطوة 2: New Project
1. اضغط **"New Project"**
2. اختر **"Deploy from GitHub repo"**
3. اختر: `ayoubmsd01/telegram_digital_bot`

### الخطوة 3: أضف المتغيرات
في **Variables** tab:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
ADMIN_USER_ID=your_telegram_user_id
ADMIN_USERNAME=your_telegram_username
CRYPTO_PAY_API_TOKEN=your_crypto_pay_token
```

### الخطوة 4: Deploy!
- Railway سينشر تلقائياً
- انتظر 2-3 دقائق
- جرب البوت: `/start`

## 📖 الدليل الكامل
اقرأ: [RAILWAY_DEPLOYMENT.md](./RAILWAY_DEPLOYMENT.md)

## ✨ المميزات

- 🛍️ إدارة المنتجات
- 💳 دعم CryptoPay
- 📦 توصيل تلقائي
- 👥 إحصائيات المستخدمين
- 📢 إشعارات المخزون
- 🌐 دعم متعدد اللغات (EN/RU)

## 🔧 التطوير المحلي

```bash
# التثبيت
pip install -r requirements.txt

# نسخ .env
cp .env.example .env

# تعديل .env بالـ tokens الخاصة بك

# التشغيل
./run_bot.sh

# الإيقاف
./stop_bot.sh

# الحالة
./status.sh
```

## 📝 الرخصة
MIT License
