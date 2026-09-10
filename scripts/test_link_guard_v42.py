# -*- coding: utf-8 -*-
"""
🧪 اختبار شامل لدرع الروابط v4.2 + توافق Ghost Encoding
معيار القبول (من المستخدم):
  1. "ارسدها تبقى نفس الاصليه"  → النص الظاهر مطابق 100% (ما عدا تحويل
     اليوزر/الهاتف/الرابط إلى أزرار — مطلوب من المستخدم صراحة)
  2. اليوزر قابل للضغط → يتحول لزر ارتباط تشعبي TextUrl
  3. البوتات لا تتعرف على اليوزر/الهاتف/الرابط → لا regex matches
  4. الإزاحات (UTF-16) صحيحة
"""
import re
import sys
import unicodedata

sys.path.insert(0, '/home/z/my-project')

PASS = 0
FAIL = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} {detail}")

print("=" * 64)
print("🧪 1) اختبار وحدة link_guard المستقلة")
print("=" * 64)
from link_guard import apply_link_guard, analyze, find_sensitive_tokens, u16len, build_telethon_entities

ad = ("✅اعذار طبية تطبيق صحتي\n"
      "✅يوم /يومين /اسبوع\n"
      "✅تقرير طبي\n"
      "✅مرافق @ppppokl اتصل 0777123456")

new_text, ents = apply_link_guard(ad, anchor="للطلب اضغط هنا", country_code="967")
print(new_text)
check("اليوزر حُول لزر", "@ppppokl" not in new_text)
check("الهاتف حُول لزر", "0777123456" not in new_text)
check("نص الإعلان العادي سليم", "اعذار طبية تطبيق صحتي" in new_text)
check("نص الإعلان سليم (سطر التقرير)", "تقرير طبي" in new_text)
check("الزر مكان اليوزر", "مرافق للطلب اضغط هنا" in new_text)
check("الزر مكان الهاتف", "اتصل للطلب اضغط هنا" in new_text)
check("عدد الكيانات = 2", len(ents) == 2, f"got {len(ents)}")
check("وجهة اليوزر t.me", ents[0][2] == "https://t.me/ppppokl", ents[0][2])
check("وجهة الهاتف wa.me بكود الدولة", ents[1][2] == "https://wa.me/967777123456", ents[1][2])

# التحقق من الإزاحات UTF-16
b = new_text.encode('utf-16-le')
for off, ln, url in ents:
    sliced = b[off*2:(off+ln)*2].decode('utf-16-le')
    check(f"إزاحة صحيحة ({url[:30]}...)", sliced == "للطلب اضغط هنا", repr(sliced))

# الترقيم/الأسعار تبقى
price_text = "السعر 1500 ريال والتخفيض 30% ينتهي 2026"
pt, pe = apply_link_guard(price_text)
check("الأسعار والتواريخ تبقى نصاً", pt == price_text, repr(pt))

# يوزر بكود الدولة مختلف
_, e2 = apply_link_guard("واتس 00967777123456", country_code="966")
check("رقم دولي 00 يُعالج كما هو", bool(e2) and e2[0][2] == "https://wa.me/967777123456", str(e2))

print()
print("=" * 64)
print("🧪 2) اختبار خط الأنابيب الكامل عبر bot.py (المسار الموحد)")
print("=" * 64)
import bot  # noqa - استيراد آمن (لا يبدأ الاتصال)

bot.init_db()  # إنشاء جداول الإعدادات للاختبار

bot.set_setting('link_guard_enabled', 'on')
bot.set_setting('adaptive_obfuscation_enabled', 'on')
bot.set_setting('adaptive_obfuscation_profile', 'medium')
bot.set_setting('text_style_boost', 'off')
bot.set_setting('send_mode', 'normal')
bot.set_setting('spintax_enabled', 'off')

out, use_html, ents = bot.prepare_content_for_sending(ad)
print("--- المخرج كما سيُنشر ---")
print(out)
print("--- كيانات:", [(type(e).__name__, e.offset, e.length, getattr(e, 'url', '')) for e in (ents or [])])

GHOST = set()
from adaptive_obfuscation import _GHOST_CHARS as GHOST_SET

visible = ''.join(ch for ch in out if ch not in GHOST_SET)
check("لا HTML", use_html is False)
check("اليوزر اختفى نصاً (لا regex)", "@ppppokl" not in visible)
check("الهاتف اختفى نصاً (لا regex)", not re.search(r'0777\d+', visible))
check("النص العربي ظاهر مطابق", "اعذار طبية تطبيق صحتي" in unicodedata.normalize('NFKC', visible))
check("أزرار ارتباط تشعبي موجودة", ents and sum(1 for e in ents if type(e).__name__ == 'MessageEntityTextUrl') == 2)

# الرسم البصري مطابق؟ قارن الأحرف الظاهرة مع الأصل (بعد استبعاد الأزرار)
orig_without_sensitive = ("✅اعذار طبية تطبيق صحتي\n"
                          "✅يوم /يومين /اسبوع\n"
                          "✅تقرير طبي\n"
                          "✅مرافق للطلب اضغط هنا اتصل للطلب اضغط هنا")
norm = lambda s: unicodedata.normalize('NFKC', s)
check("النص الظاهر = الأصل + الأزرار فقط", norm(visible) == norm(orig_without_sensitive),
      f"\nGOT:  {norm(visible)!r}\nWANT: {norm(orig_without_sensitive)!r}")

# الإزاحات على المخرج النهائي (بعد Ghost الذي زرع أحرفاً خفية!)
if ents:
    b2 = out.encode('utf-16-le')
    for e in ents:
        if type(e).__name__ == 'MessageEntityTextUrl':
            sliced = b2[e.offset*2:(e.offset+e.length)*2].decode('utf-16-le')
            ok = unicodedata.normalize('NFKC', sliced) == "للطلب اضغط هنا"
            check(f"إزاحة صحيحة بعد Ghost ({e.url[:30]})", ok, repr(sliced))

print()
print("=" * 64)
print("🧪 3) الطبقة الاحتياطية: درع VS (لو عطّل المستخدم درع الروابط)")
print("=" * 64)
bot.set_setting('link_guard_enabled', 'off')
out2, _, ents2 = bot.prepare_content_for_sending("مرافق @ppppokl")
vis2 = ''.join(ch for ch in out2 if ch not in GHOST_SET)
# بوتات الحماية ترى النص الخام (مع الأحرف الخفية) - regex لا يجد اليوزر
check("درع VS: اليوزر مخفي عن regex (النص الخام)", "@ppppokl" not in out2)
check("درع VS: العين ترى اليوزر كما هو", "@ppppokl" in vis2)  # المستخدم يقرأه طبيعياً
check("درع VS: الكيانات فارغة (لا أزرار)", not ents2 or not any(type(e).__name__ == 'MessageEntityTextUrl' for e in (ents2 or [])))
print(f"  (الخام: {out2.strip()[:60]!r}...)")
print(f"  (الظاهر للعين: {vis2.strip()!r})")
bot.set_setting('link_guard_enabled', 'on')

print()
print("=" * 64)
print("🧪 4) تقوية العرض + درع الروابط معاً")
print("=" * 64)
bot.set_setting('text_style_boost', 'bold')
out3, _, ents3 = bot.prepare_content_for_sending("مرافق @ppppokl")
kinds = [type(e).__name__ for e in (ents3 or [])]
check("زر ارتباط + غامق معاً", 'MessageEntityTextUrl' in kinds and 'MessageEntityBold' in kinds, str(kinds))
bot.set_setting('text_style_boost', 'off')

print()
print("=" * 64)
print("🧪 5) بث كيانات Telethon صالحة للإرسال")
print("=" * 64)
tel_ents = build_telethon_entities(ents if ents else [])
check("كيانات Telethon قابلة للبناء", tel_ents is not None)
try:
    from telethon.tl.types import MessageEntityTextUrl
    check("النوع MessageEntityTextUrl رسمي", all(isinstance(e, MessageEntityTextUrl) for e in tel_ents))
    # TL serialization check
    for e in tel_ents:
        d = e.to_dict()
        check(f"تسلسل TL سليم (offset={e.offset})", 'offset' in d)
except Exception as ex:
    check("كيانات Telethon", False, str(ex))

print()
print(f"{'=' * 64}")
print(f"📊 النتيجة: {PASS} نجاح | {FAIL} فشل")
print(f"{'=' * 64}")
sys.exit(1 if FAIL else 0)
