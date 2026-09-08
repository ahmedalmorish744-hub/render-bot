#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبار تكاملي شامل لـ bot.py بعد تعديلات v4.1"""
import sys, re, unicodedata as ud
sys.path.insert(0, '/home/z/my-project')

import bot
print('✅ استيراد bot.py نجح')
bot.init_db()
print('✅ تهيئة قاعدة البيانات للاختبار')

# 1) build_style_entities
bot.set_setting('text_style_boost', 'bold')
ents = bot.build_style_entities('نص تجريبي')
print('bold entities:', [type(e).__name__ for e in (ents or [])])
bot.set_setting('text_style_boost', 'both')
ents2 = bot.build_style_entities('اختبار')
print('both entities:', [type(e).__name__ for e in (ents2 or [])])
bot.set_setting('text_style_boost', 'off')
print('off entities:', bot.build_style_entities('اختبار'))

# 2) طول UTF-16 مع أحرف غير BMP (E0100+)
t = 'ا' + chr(0xE0100) + 'ب' + chr(0xE0101)
u16 = len(t.encode('utf-16-le')) // 2
print(f'utf16 length: {u16} (متوقع 6) {"✅" if u16 == 6 else "❌"}')

# 3) المسار الموحد الكامل (نفس ما يُنشر)
bot.set_setting('adaptive_obfuscation_enabled', 'on')
bot.set_setting('adaptive_obfuscation_profile', 'medium')
bot.set_setting('send_mode', 'normal')
ORIG = '✅اعذار طبية مرافق @ppppokl اتصل 0555123456 https://t.me/x'
out, html = bot.prepare_content_for_sending(ORIG)
print(f'✅ المسار الموحد نجح | use_html={html} | طول: {len(ORIG)} → {len(out)}')

checks = {
    'username hidden': not re.search(r'@[a-zA-Z0-9_]{4,}', out),
    'phone hidden': not re.search(r'\+?\d[\d\s\-()]{5,}\d', out),
    'url hidden': not re.search(r'https?://\S+|t\.me/\S+', out),
    'keyword hidden': not re.search(r'اعذار|طبية|مرافق', out),
}
print('فحوصات الاختباء:', checks)

# 4) تطابق بصري
from adaptive_obfuscation import strip_ghost_chars
vis = ud.normalize('NFKC', strip_ghost_chars(out))
orig_n = ud.normalize('NFKC', ORIG)
print('✅ تطابق بصري كامل:', vis == orig_n)
if vis != orig_n:
    for i, (a, b) in enumerate(zip(vis, orig_n)):
        if a != b:
            print(f'  اختلاف عند {i}: {a!r} != {b!r}'); break
    print(f'  أطوال: {len(vis)} vs {len(orig_n)}')

# 5) وضع stego فوق Ghost (بصمة VS تتكامل)
bot.set_setting('send_mode', 'stego')
out2, _ = bot.prepare_content_for_sending('مرحبا بكم في قناتنا')
from stego_engine import FINGERPRINT_POOL
vs_count = sum(1 for c in out2 if c in FINGERPRINT_POOL)
vis2 = ud.normalize('NFKC', ''.join(c for c in out2 if c not in FINGERPRINT_POOL))
vis2 = ud.normalize('NFKC', strip_ghost_chars(''.join(c for c in out2 if c not in FINGERPRINT_POOL)))
print(f'✅ stego فوق Ghost: بصمة={vs_count} حرف | تطابق بصري: {vis2 == ud.normalize("NFKC", "مرحبا بكم في قناتنا")}')

# 6) إصلاح رسالة قديمة متلخبطة عبر المسار الموحد
OLD = "✅اعﺬﺍر ﻄبية تﻁبﻱق ﺺحتي"
out3, _ = bot.prepare_content_for_sending(OLD)
vis3 = ud.normalize('NFKC', strip_ghost_chars(out3))
print('✅ إصلاح التلوث عبر المسار الموحد:', vis3 == '✅اعذار طبية تطبيق صحتي')

# 7) إعادة التشغيل على نص مكوَّد (حماية التكرار)
out4, _ = bot.prepare_content_for_sending(out)
vis4 = ud.normalize('NFKC', strip_ghost_chars(out4))
print('✅ إعادة معالجة نص مشفر (لا تكديس):', vis4 == orig_n)

print('\n' + '=' * 60)
ok = all(checks.values()) and u16 == 6
print('✅ كل الاختبارات نجحت' if ok else '❌ توجد إخفاقات')
