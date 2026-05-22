# 🤖 بوت النشر الخارق v4.0 - نسخة Render

## 📋 المتطلبات

1. حساب على [Render](https://render.com)
2. حساب على [GitHub](https://github.com)
3. بيانات Telegram API من [my.telegram.org](https://my.telegram.org)
4. Bot Token من [@BotFather](https://t.me/BotFather)

## 🚀 خطوات النشر على Render

### الخطوة 1: رفع المشروع إلى GitHub

1. أنشئ مستودع جديد على GitHub (اجعله **Private** للأمان)
2. ارفع جميع ملفات هذا المجلد إلى المستودع:
   ```
   bot.py
   requirements.txt
   Procfile
   runtime.txt
   render.yaml
   .gitignore
   ```

### الخطوة 2: إنشاء خدمة على Render

1. اذهب إلى [dashboard.render.com](https://dashboard.render.com)
2. اضغط **New +** ثم اختر **Web Service**
3. اختر **Build and deploy from a Git repository**
4. اربط حساب GitHub واختر المستودع الذي أنشأته

### الخطوة 3: إعدادات الخدمة

| الإعداد | القيمة |
|---------|--------|
| **Name** | `super-poster-bot` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python bot.py` |
| **Instance Type** | `Free` |

### الخطوة 4: إضافة متغيرات البيئة

في صفحة الخدمة، اذهب إلى **Environment** وأضف:

| المفتاح | الوصف | مثال |
|---------|-------|------|
| `API_ID` | معرف API من my.telegram.org | `12345678` |
| `API_HASH` | هاش API من my.telegram.org | `abc123def456...` |
| `BOT_TOKEN` | توكن البوت من @BotFather | `123456:ABC-DEF...` |
| `ADMIN_ID` | معرف تيليجرام المطور | `7853478744` |
| `PORT` | منفذ خادم الويب (Render يعينه تلقائياً) | `10000` |

### الخطوة 5: النشر

1. اضغط **Manual Deploy** → **Deploy latest commit**
2. انتظر حتى يكتمل البناء والنشر
3. تحقق من السجلات (Logs) للتأكد من عمل البوت

## ⚠️ ملاحظات مهمة عن Render المجاني

| الميزة | التفاصيل |
|--------|----------|
| **السبات** | الخدمة تدخل في وضع السبات بعد 15 دقيقة بدون طلبات |
| **الاستيقاظ** | تستيقظ عند استقبال طلب HTTP (لكن يأخذ ~30 ثانية) |
| **ساعات مجانية** | 750 ساعة/شهر |
| **قاعدة البيانات** | SQLite تُحذف عند إعادة النشر! استخدم Render Disk أو قاعدة خارجية |
| **الحل** | استخدم خدمة ping خارجية (مثل UptimeRobot) لإبقاء الخدمة مستيقظة |

## 🔧 الحفاظ على البوت مستيقظاً

1. أنشئ حساب على [UptimeRobot](https://uptimerobot.com)
2. أضف مراقب (Monitor) من نوع HTTP
3. أدخل رابط خدمة Render (مثل: `https://super-poster-bot.onrender.com/health`)
4. اختر فترة المراقبة كل 5 دقائق
5. هذا يمنع خدمة Render من الدخول في وضع السبات

## 📁 هيكل الملفات

```
├── bot.py              # الكود الرئيسي للبوت
├── requirements.txt    # مكتبات Python المطلوبة
├── Procfile            # أمر تشغيل الخدمة (web)
├── runtime.txt         # إصدار Python
├── render.yaml         # إعدادات Render Blueprint
├── .gitignore          # ملفات مستبعدة من Git
└── README.md           # هذا الملف
```

## 🔄 تحديث البوت

1. عدّل الكود محلياً
2. ارفع التعديلات إلى GitHub (`git push`)
3. Render سيعيد النشر تلقائياً
