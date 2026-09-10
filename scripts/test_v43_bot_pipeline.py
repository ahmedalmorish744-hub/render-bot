#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبار تكاملي v4.3: المسار الكامل prepare_content_for_sending بوضع المستخدم اليدوي"""
import sys, os
# متغيرات بيئة وهمية للاختبار (bot.py يخرج بدونها)
os.environ.setdefault('API_ID', '12345')
os.environ.setdefault('API_HASH', 'test_hash_for_unit_tests_only')
os.environ.setdefault('BOT_TOKEN', '123456:test_token_for_unit_tests_only')
os.environ.setdefault('ADMIN_ID', '123456789')
os.environ.setdefault('DB_PATH', '/home/z/my-project/scripts/test_pipeline.db')
sys.path.insert(0, '/home/z/my-project')
os.chdir('/home/z/my-project')

import bot
import unicodedata as ud
from link_guard import _strip_invisible

def visual(s: str) -> str:
    """النص المرئي: إزالة الأحرف الخفية + تطبيع NFKC"""
    return ud.normalize('NFKC', _strip_invisible(s))

print('✅ استيراد bot.py نجح')
bot.init_db()

PASS = FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond: PASS += 1; print(f"✅ {name}")
    else: FAIL += 1; print(f"❌ {name} {detail}")

# إعلان المستخدم الحقيقي
ad = ("✅اعذار طبية تطبيق صحتي\n"
      "✅يوم /يومين /اسبوع\n"
      "✅تقرير طبي\n"
      "✅مرافق @ppppokl اتصل 0777123456")

# ضبط بيئة اختبار نظيفة
bot.set_setting('adaptive_obfuscation_enabled', 'on')
bot.set_setting('adaptive_obfuscation_profile', 'medium')
bot.set_setting('send_mode', 'normal')
bot.set_setting('text_style_boost', 'off')
bot.set_setting('link_guard_enabled', 'on')
bot.set_setting('link_guard_targets', '')          # ← بلا أهداف
bot.set_setting('super_encryption_enabled', 'off')
bot.set_setting('stealth_obfuscator_enabled', 'off')

# ═══ 1) بلا أهداف: لا إضافات + اليوزر قابل للضغط ═══
out, use_html, ents = bot.prepare_content_for_sending(ad)
check("بلا أهداف: نص المستخدم ظاهر (اعذار/طبية/صحتي)",
      all(w in visual(out) for w in ['اعذار', 'طبية', 'صحتي']))
check("بلا أهداف: لا أزرار ارتباط",
      not any(type(e).__name__ == 'MessageEntityTextUrl' for e in (ents or [])))
mention_ents = [e for e in (ents or []) if type(e).__name__ == 'MessageEntityMention']
check("بلا أهداف: كيان Mention صريح لـ @ppppokl", len(mention_ents) >= 1,
      str([type(e).__name__ for e in (ents or [])]))
if mention_ents:
    e0 = mention_ents[0]
    chunk = out.encode('utf-16-le')[e0.offset*2:(e0.offset+e0.length)*2].decode('utf-16-le')
    check(f"Mention يشير إلى {chunk!r}", 'ppppokl' in chunk)

# ═══ 2) مع هدف @ppppokl: زر ارتباط فقط له ═══
bot.set_setting('link_guard_targets', '@ppppokl')
out2, _, ents2 = bot.prepare_content_for_sending(ad)
check("مع هدف: اليوزر اختفى نصاً", 'ppppokl' not in out2)
check("مع هدف: الهاتف بقي كما هو (لم يحدده المستخدم)", '0777123456' in out2)
text_ents = [e for e in (ents2 or []) if type(e).__name__ == 'MessageEntityTextUrl']
check("مع هدف: زر TextUrl واحد", len(text_ents) == 1,
      str([type(e).__name__ for e in (ents2 or [])]))
if text_ents:
    check("وجهة الزر t.me/ppppokl", text_ents[0].url == 'https://t.me/ppppokl', text_ents[0].url)
    chunk = out2.encode('utf-16-le')[text_ents[0].offset*2:(text_ents[0].offset+text_ents[0].length)*2].decode('utf-16-le')
    check(f"نص الزر = {chunk!r}", chunk == 'للطلب اضغط هنا')
mention_ents2 = [e for e in (ents2 or []) if type(e).__name__ == 'MessageEntityMention']
check("مع هدف: لا Mention للهدف المستبدل", len(mention_ents2) == 0)

# ═══ 3) إعلان بلا يوزرات/أرقام: لا يضاف أي شيء ═══
clean_ad = "✅عرض خاص على الابسور الشتوية لفترة محدودة"
bot.set_setting('link_guard_targets', '@ppppokl')
out3, _, ents3 = bot.prepare_content_for_sending(clean_ad)
check("إعلان بلا أهداف: لا أزرار",
      not any(type(e).__name__ == 'MessageEntityTextUrl' for e in (ents3 or [])))
check("إعلان بلا أهداف: النص ظاهر كما هو",
      all(w in visual(out3) for w in ['عرض', 'خاص', 'الابسور', 'الشتوية']))

# ═══ 4) أهداف متعددة: يوزر + هاتف ═══
bot.set_setting('link_guard_targets', '@ppppokl\n0777123456')
out4, _, ents4 = bot.prepare_content_for_sending(ad)
text_ents4 = [e for e in (ents4 or []) if type(e).__name__ == 'MessageEntityTextUrl']
check("هدفان: زران", len(text_ents4) == 2, str(len(text_ents4)))
urls4 = sorted(e.url for e in text_ents4)
check("الوجهتان صحيحتان",
      urls4 == ['https://t.me/ppppokl', 'https://wa.me/967777123456'], str(urls4))

# ═══ 5) وضع stego فوق التكويد: الكيانات تبقى صحيحة ═══
bot.set_setting('send_mode', 'stego')
bot.set_setting('link_guard_targets', '@ppppokl')
out5, _, ents5 = bot.prepare_content_for_sending(ad)
text_ents5 = [e for e in (ents5 or []) if type(e).__name__ == 'MessageEntityTextUrl']
ok5 = False
if text_ents5:
    for e in text_ents5:
        chunk = out5.encode('utf-16-le')[e.offset*2:(e.offset+e.length)*2].decode('utf-16-le')
        if chunk == 'للطلب اضغط هنا':
            ok5 = True
check("stego mode: إزاحات الزر دقيقة بعد البصمة الخفية", ok5)
bot.set_setting('send_mode', 'normal')

# تنظيف إعدادات الاختبار
bot.set_setting('link_guard_targets', '')

print(f"\n{'='*45}")
print(f"النتيجة: {PASS} نجح | {FAIL} فشل")
sys.exit(1 if FAIL else 0)
