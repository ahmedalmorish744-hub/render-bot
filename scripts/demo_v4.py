# -*- coding: utf-8 -*-
"""مثال تطبيقي حي لعرض آلية Ghost Encoding v4.0 في التقرير"""
import sys, unicodedata
sys.path.insert(0, '/home/z/my-project')
from adaptive_obfuscation import AdaptiveObfuscationEngine, strip_ghost_chars, VS_POOL

USER_MSG = "[ إجازة مرضية ﺳﻛﻟﻳف معتمد ] لطلب وتساب: 🌲 خا.، ـااااص @ppppokl"
SPAM_MSG = "اشترك في قناتنا للحصول على عروض حصرية واتساب 0555123456"

def hexdump(text, limit=60):
    """تمثيل الأكواد الداخلية"""
    out = []
    for ch in text[:limit]:
        cp = ord(ch)
        if cp < 128 and ch.isprintable():
            out.append(ch)
        elif ch == ' ':
            out.append('␠')
        else:
            out.append(f"U+{cp:04X}")
    return ' '.join(out)

print("════════════════════════════════════════════════")
print("مثال 1: رسالة المستخدم الحقيقية")
print("════════════════════════════════════════════════")
print(f"الأصل: {USER_MSG}")
eng = AdaptiveObfuscationEngine(profile='medium')
for i in range(2):
    out, info = eng.obfuscate(USER_MSG)
    vis = strip_ghost_chars(out)
    same = unicodedata.normalize('NFKC', vis) == unicodedata.normalize('NFKC', USER_MSG)
    print(f"\n🧬 النسخة المشفرة #{i+1} (خفي: {info['invisible_chars']} حرف):")
    print(f"{out}")
    print(f"الظاهر بعد إزالة الخفي: {vis} | مطابق: {same}")
    print(f"أول 40 كود: {hexdump(out, 40)}")

print()
print("════════════════════════════════════════════════")
print("مثال 2: رسالة إعلانية فيها كلمات مفتاحية")
print("════════════════════════════════════════════════")
print(f"الأصل: {SPAM_MSG}")
out, info = eng.obfuscate(SPAM_MSG)
print(f"مشفرة (خفي: {info['invisible_chars']}): {out}")
# محاكاة بوت حماية يبحث عن الكلمات بعد تنظيف الأحرف الكلاسيكية فقط
classic = ''.join(ch for ch in out if ch not in
                  '\u200B\u200C\u200D\u2060\u2061\u2062\u2063\u2064\u061C\uFEFF')
for kw in ['اشترك', 'قناتنا', 'عروض', 'واتساب']:
    print(f"  بوت يبحث عن '{kw}': {'❌ وجدها!' if kw in classic else '✅ لم يجدها (مجزأة)'}")
print(f"بعد حذف كل الخفي: {strip_ghost_chars(out)}")
