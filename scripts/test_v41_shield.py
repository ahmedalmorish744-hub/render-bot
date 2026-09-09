#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""اختبار سريع للمحرك v4.1 - مثال المستخدم الحقيقي"""
import re, sys, unicodedata
sys.path.insert(0, '/home/z/my-project')
from adaptive_obfuscation import (
    AdaptiveObfuscationEngine, strip_ghost_chars, ghost_ratio,
    find_sensitive_spans, sanitize_invisible_chars
)
from adaptive_obfuscation import _GHOST_CHARS as _GHOST

USER_MSG = """✅اعذار طبية تطبيق صحتي
✅يوم /يومين /اسبوع
✅تقرير طبي
✅مرافق @ppppokl. اتصل 0555123456 او https://t.me/mychannel"""

print("📝 النص الأصلي:")
print(USER_MSG)
print("=" * 70)

spans = find_sensitive_spans(USER_MSG)
print("🎯 الرموز الحساسة المكتشفة:")
for s, e in spans:
    print(f"   [{s}:{e}] = '{USER_MSG[s:e]}'")

eng = AdaptiveObfuscationEngine(profile='medium')
result, info = eng.obfuscate(USER_MSG)

print("\n📤 النص المشفر (كما سيُنشر):")
print(result)
print("\n📊 معلومات:", info)

# 1) التطابق البصري
visible = strip_ghost_chars(result)
norm = lambda t: unicodedata.normalize('NFKC', t)
same = norm(visible) == norm(USER_MSG)
print(f"\n{'✅' if same else '❌'} التطابق البصري (بعد إزالة الخفي): {same}")
if not same:
    for i, (a, b) in enumerate(zip(norm(visible), norm(USER_MSG))):
        if a != b:
            print(f"   أول اختلاف عند {i}: '{a}' (U+{ord(a):04X}) != '{b}' (U+{ord(b):04X})")
            break
    print(f"   أطوال: {len(norm(visible))} vs {len(norm(USER_MSG))}")

# 2) كشف بوتات الحماية (regex نموذجي)
bot_patterns = {
    'username': r'@[a-zA-Z0-9_]{4,}',
    'phone': r'\+?\d[\d\s\-()]{5,}\d',
    'url': r'(https?://\S+|t\.me/\S+|wa\.me/\S+)',
    'keyword اعذار': r'اعذار',
    'keyword طبية': r'طبية',
    'keyword تطبيق': r'تطبيق',
}
print("\n🤖 فحص عيون بوتات الحماية (على النص المشفر):")
all_hidden = True
for name, pat in bot_patterns.items():
    hit = re.search(pat, result, re.IGNORECASE)
    status = '🚨 كُشف!' if hit else '✅ خفي'
    if hit: all_hidden = False
    print(f"   {status}  {name}")

# 3) نسبة الخفي
print(f"\n📈 نسبة الأحرف الشبحية: {ghost_ratio(result):.1%}")

# 4) إصلاح التلوث (رسالة قديمة متلخبطة)
OLD = "✅اعﺬﺍر ﻄبية تﻁبﻱق ﺺحتي"
repaired = sanitize_invisible_chars(OLD)
print(f"\n🩹 إصلاح رسالة قديمة متلخبطة:")
print(f"   قبل: {OLD}")
print(f"   بعد: {repaired}")
print(f"   {'✅ أُصلحت' if norm(repaired) == '✅اعذار طبية تطبيق صحتي' else '❌ فشل الإصلاح'}")

# 5) لا مقطعات اتصال وسط الكلمات العربية
bad = 0
for i, ch in enumerate(result):
    if ch in '\u2063\u2064':
        # آخر حرف حقيقي قبل الموضع
        p = i - 1
        while p >= 0 and (result[p] in _GHOST or unicodedata.category(result[p]) in ('Mn', 'Me')):
            p -= 1
        q = i + 1
        while q < len(result) and (result[q] in _GHOST or unicodedata.category(result[q]) in ('Mn', 'Me')):
            q += 1
        prev = result[p] if p >= 0 else ''
        nxt = result[q] if q < len(result) else ''
        if prev and nxt and '\u0600' <= prev <= '\u06FF' and '\u0600' <= nxt <= '\u06FF':
            if prev not in 'اأإآدذرزوؤةء':  # حرف واصل للأمام → يقطع الاتصال!
                bad += 1
print(f"\n🔗 مواضع قطع اتصال محتملة (2063/2064 وسط كلمة): {bad} {'✅' if bad == 0 else '❌'}")

print("\n" + "=" * 70)
print("✅ اكتمل الاختبار" if (same and all_hidden and bad == 0) else "❌ توجد مشاكل")
