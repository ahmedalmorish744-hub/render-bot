#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 اختبار شامل لإصلاح ميزة الانضمام للروابط المرسلة - v4.4

يختبر:
1) كشف الروابط الملوثة بأحرف خفية (السبب الجذري الأشهر)
2) كل صيغ الروابط (t.me / telegram.me / joinchat / +hash / @user)
3) إصلاح الرابط الوهمي t.me/joinchat
4) حفظ واسترجاع طابور الانضمام في قاعدة البيانات
5) العلم اليتيم awaiting_slow_join لم يعد في قائمة المنع
6) تقرير أسباب الفشل
7) عدم كسر منطق link_guard (درع الروابط لا يزال سليماً)
"""
import re
import os
import sys
import json
import sqlite3
import tempfile

PASS = []
FAIL = []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"   ✅ {name}")
    else:
        FAIL.append(name)
        print(f"   ❌ {name} {detail}")


os.environ.setdefault('BOT_TOKEN', '1:test')
os.environ.setdefault('API_ID', '12345')
os.environ.setdefault('API_HASH', 'test_hash_0000000000000000000000000000')

# ═══════════════════════════════════════════
# استيراد extract_telegram_links من bot.py
# ═══════════════════════════════════════════
sys.path.insert(0, '/home/z/my-project')

# محاكاة بيئة الاستيراد (bot.py يتوقع متغيرات بيئة)
import importlib

print("\n" + "=" * 60)
print("🧪 1) استيراد الدوال من bot.py")
print("=" * 60)

try:
    bot_mod = importlib.import_module('bot')
    extract_telegram_links = bot_mod.extract_telegram_links
    _LINK_INVISIBLE_RE = bot_mod._LINK_INVISIBLE_RE
    check("استيراد bot.py بنجاح", True)
except Exception as e:
    check("استيراد bot.py", False, f"→ {e}")
    # fallback: استخراج الدالة بتنفيذ جزء الكود
    raise SystemExit(1)

print("\n" + "=" * 60)
print("🧪 2) كشف الروابط الملوثة بأحرف خفية (السبب الجذري)")
print("=" * 60)

# رابط ملوث بـ Variation Selectors (FE00-FE0F)
polluted_vs = "https://t.m\uFE00e/join_test2 \uFE0F https://t.me/\uFE0Fsecond_link"
links = extract_telegram_links(polluted_vs)
check("رابط ملوث بـ VS1-16 يُكشف", len(links) >= 1, f"→ {links}")

# رابط ملوث بـ Tag chars (E0000-E01EF) - مثل عينة المستخدم الفعلية
polluted_tag = "https://t.me/\U000e0067\U000e006froup_test انضم هنا"
links = extract_telegram_links(polluted_tag)
check("رابط ملوث بـ Tag chars يُكشف", any('roup_test' in l for l in links), f"→ {links}")

# يوزر ملوث (نفس نمط عينة المستخدم @p󠄜p󠄯pp...)
polluted_user = "ت󠆝ط󠇀󠅡بيق󠇦 تواصل @p\U000e011cp\U000e012fpp\U000e0067ok\U000e016al للطلب"
links = extract_telegram_links(polluted_user)
check("يوزر ملوث بأحرف Tag يُكشف كرابط t.me", any('ppppokl' in l or 'ppokl' in l for l in links), f"→ {links}")

# ZWSP + ZWNJ + bidi + soft hyphen
polluted_mix = "https\u200b://\u200ct.me\u200d/\u200fmy_\u00adchannel_test"
links = extract_telegram_links(polluted_mix)
check("رابط ملوث بـ ZW+bidi+SHY يُكشف", any('my_channel_test' in l for l in links), f"→ {links}")

# رابط نظيف يبقى يعمل
links = extract_telegram_links("انضم https://t.me/clean_group الآن")
check("رابط نظيف عادي يُكشف", 'https://t.me/clean_group' in links, f"→ {links}")

print("\n" + "=" * 60)
print("🧪 3) كل صيغ الروابط")
print("=" * 60)

cases = [
    ("https://t.me/mychannel", ['https://t.me/mychannel']),
    ("http://t.me/mychannel", ['http://t.me/mychannel']),
    ("t.me/mychannel", ['https://t.me/mychannel']),
    ("1- https://t.me/mychannel", ['https://t.me/mychannel']),
    ("*t.me/mychannel*", ['https://t.me/mychannel']),
    ("https://t.me/+AbCdEfGh123", ['https://t.me/+AbCdEfGh123']),
    ("https://t.me/joinchat/AbCdEfGh", ['https://t.me/joinchat/AbCdEfGh']),
    ("https://telegram.me/mychannel", ['https://t.me/mychannel']),
    ("@myusername", ['https://t.me/myusername']),
    ("انضموا لقناتنا https://t.me/mychannel و https://t.me/second_grp",
     ['https://t.me/mychannel', 'https://t.me/second_grp']),
]
for i, (text, expected) in enumerate(cases, 1):
    links = extract_telegram_links(text)
    ok = all(any(exp == l for l in links) for exp in expected)
    check(f"صيغة {i}: {text[:40]!r}", ok, f"→ حصل: {links}")

print("\n" + "=" * 60)
print("🧪 4) إصلاح الرابط الوهمي t.me/joinchat")
print("=" * 60)

links = extract_telegram_links("https://t.me/joinchat/RealHash123")
check("رابط joinchat الحقيقي يُكشف", 'https://t.me/joinchat/RealHash123' in links, f"→ {links}")
check("لا رابط وهمي t.me/joinchat (بدون كود)",
      'https://t.me/joinchat' not in links and 'https://t.me/joinchat/' not in
      [l for l in links if l.rstrip('/') != 'https://t.me/joinchat/RealHash123'] and
      not any(l == 'https://t.me/joinchat' for l in links),
      f"→ {links}")

print("\n" + "=" * 60)
print("🧪 5) حفظ واسترجاع طابور الانضمام (قاعدة بيانات)")
print("=" * 60)

tmpdir = tempfile.mkdtemp()
db_path = os.path.join(tmpdir, 'test.db')
conn = sqlite3.connect(db_path)
conn.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
conn.execute('''CREATE TABLE IF NOT EXISTS join_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link TEXT, group_id INTEGER, group_name TEXT,
    status TEXT, joined_by TEXT, joined_at TIMESTAMP)''')
conn.commit()
conn.close()

# تجاوز DB_PATH في bot.py
bot_mod.DB_PATH = db_path
bot_mod.join_queue = ['https://t.me/queued_one', 'https://t.me/queued_two']

bot_mod.save_join_queue()
raw = sqlite3.connect(db_path).execute(
    "SELECT value FROM settings WHERE key='join_queue'").fetchone()
check("الطابور يُحفظ في قاعدة البيانات", raw is not None and 'queued_one' in raw[0], f"→ {raw}")

bot_mod.join_queue = []
bot_mod.load_join_queue()
check("الطابور يُسترجع عند الإقلاع",
      bot_mod.join_queue == ['https://t.me/queued_one', 'https://t.me/queued_two'],
      f"→ {bot_mod.join_queue}")

# طابور فاضي لا يكسر شيئاً
bot_mod.join_queue = []
bot_mod.save_join_queue()
bot_mod.load_join_queue()
check("طابور فارغ: حفظ واسترجاع آمنان", bot_mod.join_queue == [])

print("\n" + "=" * 60)
print("🧪 6) العلم اليتيم awaiting_slow_join")
print("=" * 60)

with open('/home/z/my-project/bot.py', encoding='utf-8') as f:
    full_src = f.read()

# أي_انتظار القائمة داخل message_handler
any_awaiting_block = full_src.split("any_awaiting = any(get_setting(k) == 'true' for k in [")[1].split("])")[0]
check("awaiting_slow_join خارج قائمة any_awaiting", "awaiting_slow_join" not in any_awaiting_block)
check("بقية الأعلام الأساسية ما زالت في القائمة",
      "'awaiting_msg'" in any_awaiting_block and "'awaiting_auto_join'" in any_awaiting_block
      and "'awaiting_lg_target_add'" in any_awaiting_block)

# تنظيف الإقلاع
check("تنظيف أعلام الانتظار عند الإقلاع موجود",
      "UPDATE settings SET value='' WHERE key LIKE 'awaiting_%'" in full_src)
check("استرجاع الطابور عند الإقلاع موجود", "load_join_queue()" in full_src)

print("\n" + "=" * 60)
print("🧪 7) تقرير أسباب الفشل")
print("=" * 60)

bot_mod._join_reasons = {}
bot_mod.save_join_history("https://t.me/x", 0, "x", 'failed:expired_invite', "account_1")
bot_mod.save_join_history("https://t.me/y", 0, "y", 'failed:private', "account_1")
bot_mod.save_join_history("https://t.me/z", 0, "z", 'failed:expired_invite', "account_2")
check("أسباب الفشل تُحتسب", bot_mod._join_reasons.get('رابط دعوة منتهي الصلاحية') == 2
      and bot_mod._join_reasons.get('قناة/مجموعة خاصة') == 1,
      f"→ {bot_mod._join_reasons}")
check("النجاح لا يدخل الأسباب", 'success' not in str(bot_mod._join_reasons))

print("\n" + "=" * 60)
print("🧪 8) درع الروابط link_guard لم يتأثر")
print("=" * 60)

from link_guard import apply_link_guard, parse_targets
ad = "✅اعذار طبية تطبيق صحتي\nمرافق @ppppokl اتصل 0777123456"
# بلا أهداف → لا شيء
t1, e1 = apply_link_guard(ad)
check("بلا أهداف: لا تعديل (القاعدة الصارمة)", t1 == ad and e1 == [])
# مع أهداف → زر
targets = parse_targets("@ppppokl\n0777123456")
t2, e2 = apply_link_guard(ad, targets=targets)
check("مع أهداف: اليوزر تحول لزر", "@ppppokl" not in t2 and len(e2) == 2, f"→ {t2[:50]}")

print("\n" + "=" * 60)
print("🧪 9) أزرار جديدة لها معالجات")
print("=" * 60)

check("معالج process_queue_now موجود", "elif data == 'process_queue_now':" in full_src)
check("معالج view_join_queue موجود", "elif data == 'view_join_queue':" in full_src)
check("زر معالجة الطابور في القائمة", 'b"process_queue_now"' in full_src)
check("رسالة بلا حسابات في مسار الروابط", "لا توجد حسابات متصلة" in full_src and 'b"accounts"' in full_src)
check("تنبيه الروابط في مسار إضافة رسالة", "رسالتك تحتوي" in full_src)

print("\n" + "=" * 60)
print(f"📊 النتيجة: {len(PASS)} نجح | {len(FAIL)} فشل")
print("=" * 60)
if FAIL:
    print("❌ اختبارات فاشلة:")
    for f in FAIL:
        print(f"   - {f}")
    sys.exit(1)
print("🎉 كل اختبارات إصلاح الانضمام نجحت!")
