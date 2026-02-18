# 🚀 دليل نشر البوت على Railway

## ✅ تم الإعداد

تم رفع جميع الملفات المطلوبة للنشر على Railway:
- ✓ `Procfile` - تعريف العمليات
-  `railway.json` - إعدادات Railway
- ✓ `requirements.txt` - المكتبات المطلوبة
- ✓ `runtime.txt` - نسخة Python
- ✓ `.gitignore` - ملفات لتجاهلها

## 📋 خطوات النشر على Railway

### 1. افتح Railway Dashboard

اذهب إلى: https://railway.app/dashboard

### 2. أنشئ مشروع جديد (New Project)

1. اضغط على **"New Project"**
2. اختر **"Deploy from GitHub repo"**
3. اختر repository: **`ayoubmsd01/telegram_digital_bot`**
4. اضغط **"Deploy Now"**

### 3. أضف المتغيرات البيئية (Environment Variables)

في صفحة المشروع، اذهب إلى **Variables** وأضف:

```
TELEGRAM_BOT_TOKEN=8545248106:AAGALMHtUf5YCcbkx4DzVOmn_AiBQhlYE1Q
ADMIN_USER_ID=<YOUR_TELEGRAM_USER_ID>
ADMIN_USERNAME=<YOUR_TELEGRAM_USERNAME>
CRYPTO_PAY_API_TOKEN=<YOUR_CRYPTO_PAY_TOKEN>
```

### 4. إعدادات مهمة

#### تفعيل خدمتين منفصلتين:

Railway تدعم تشغيل عدة services في نفس المشروع:

**Option A: Service واحد يشغل البوت فقط (موصى به)**
1. في Settings → Deploy
2. تأكد من أن **Start Command** هو: `python3 bot.py`
3. **Port**: لا يهم (البوت يستخدم Polling)

**Option B: إضافة Webhook Server (للمدفوعات)**
1. اضغط **"New Service"** من نفس المشروع
2. اختر نفس الـ repository
3. في Settings → Deploy
4. **Start Command**: `python3 webhook_server.py`
5. **Port**: 8000 (سيُعطى domain تلقائياً)

### 5. النشر

- Railway سيبدأ التشغيل **تلقائياً**
- راقب الـ logs في **Deployments** tab
- يجب أن ترى:
```
Bot is polling...
Application started
```

### 6. التحقق من التشغيل

أرسل `/start` للبوت على Telegram
إذا رد = ✅ نجح النشر!

---

## 🔧 إعدادات إضافية

### تفعيل Auto-Deployments

في Settings → Service:
- ✅ تفعيل **"Auto Deploy"**
- Railway سيعيد النشر تلقائياً عند كل `git push`

### إدارة قاعدة البيانات

قاعدة البيانات SQLite في Railway **مؤقتة**.

**الحل الأفضل: استخدام PostgreSQL**

1. في Railway Dashboard → New → Database → PostgreSQL
2. بعد الإنشاء، ستحصل على:
   - `DATABASE_URL`
3. أضفها في Variables

**أو استبقاء SQLite** (سيُحذف عند إعادة التشغيل):
- مقبول للتجربة
- غير موصى به للإنتاج

### إدارة Logs

في Railway Dashboard:
- اضغط على Service → Logs
- راقب Real-time logs
- ابحث عن أخطاء

---

## ⚠️ مشاكل شائعة وحلولها

### 1. البوت لا يرد

**التحقق:**
```bash
# في Railway Logs، ابحث عن:
Bot is polling...
Application started
```

**الحل:**
- تأكد من `TELEGRAM_BOT_TOKEN` صحيح
- تأكد من عدم وجود deployment آخر
- حذف Webhook: قم بإضافة service مؤقت يُشغل `python3 delete_webhook.py`

### 2. Conflict Error

```
telegram.error.Conflict: terminated by other getUpdates request
```

**السبب:** bot يعمل في أكثر من مكان

**الحل:**
1. أوقف أي bot محلي: `./stop_bot.sh`
2. تأكد من service واحد فقط في Railway
3. حذف webhook: `python3 delete_webhook.py`

### 3. Database Locked

**الحل:**
- انتقل لـ PostgreSQL (موصى به)
- أو تأكد من عدم تشغيل نسختين في نفس الوقت

### 4. Service يتوقف بعد فترة

**في Railway:**
- Free Plan: $5/شهر credit
- إذا نفد الـcredit، سيتوقف
- تحقق من **Billing** في Dashboard

---

## 📊 مراقبة البوت

### عرض الـ Logs (Real-time)

في Railway Dashboard:
1. اختر service
2. Logs tab
3. راقب الأخطاء

### Metrics

Railway تعرض:
- CPU Usage
- Memory Usage
- Network

إذا زاد استخدام الذاكرة → قد تحتاج upgrade

---

## 🎯 الخطوات التالية (بعد النشر الناجح)

### 1. توقيف النسخة المحلية

```bash
./stop_bot.sh
```

### 2. مراقبة أول 24 ساعة

- تحقق من الـLogs كل ساعتين
- جرب جميع الأوامر
- اختبر الدفع (إذا مفعّل)

### 3. إعداد Webhook للدفع (اختياري)

إذا كنت تستخدم CryptoPay:

1. شغّل Webhook Service في Railway
2. ستحصل على URL مثل: `https://your-service.railway.app`
3. أضفه في إعدادات CryptoPay

---

## 🆘 الدعم

إذا واجهت مشاكل:

1. **تحقق من Logs** في Railway
2. **ابحث في GitHub Issues**: https://github.com/python-telegram-bot/python-telegram-bot/issues
3. **Railway Docs**: https://docs.railway.app

---

## ✅ Checklist النشر

- [ ] Repository على GitHub محدّث
- [ ] حساب Railway جاهز
- [ ] New Project تم إنشاؤه
- [ ] Environment Variables مضافة
- [ ] Service deployed بنجاح
- [ ] Logs تظهر "Application started"
- [ ] البوت يرد على `/start`
- [ ] تم إيقاف النسخة المحلية
- [ ] تم اختبار جميع الأوامر

---

🎉 **مبروك! البوت الآن يعمل 24/7 على Railway**
