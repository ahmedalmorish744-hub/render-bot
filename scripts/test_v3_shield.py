#!/usr/bin/env python3
"""
🧪 اختبار شامل v3.0 - الدرع الخفي الآمن على العربية
يختبر برسالة المستخدم الحقيقية + التحقق من كل الشروط
"""
import sys
import re
import unicodedata

sys.path.insert(0, '/home/z/my-project')

PASS = '✅'
FAIL = '❌'
results = []

def check(name, cond, detail=''):
    results.append((name, cond, detail))
    print(f"{PASS if cond else FAIL} {name}" + (f" — {detail}" if detail else ''))

# ═════════════════════════════════════════════════════
# رسالة المستخدم الحقيقية (التي أبلغ عن تلخبطها)
# ═════════════════════════════════════════════════════
USER_MSG = "[ إجازة مرضية ﺳﻛﻟﻳف معتمد ] لطلب وتساب: 🌲 خا.، ـااااص @ppppokl"

SHAPING_BREAKERS = {'\u200B', '\u200C', '\u200D'}  # ممنوعة نهائياً
FINGERPRINT_ALPHABET = {'\u2060', '\u061C', '\u2061', '\u2062'}
ADAPTIVE_SHIELD = {'\u2063', '\u2064'}
ALL_INVISIBLES = SHAPING_BREAKERS | FINGERPRINT_ALPHABET | ADAPTIVE_SHIELD | {'\uFEFF'}

def visible_text(text):
    """إرجاع النص الظاهر: إزالة الأحرف الخفية + تطبيع NFKC (يعيد أشكال العرض)"""
    cleaned = ''.join(ch for ch in text if ch not in ALL_INVISIBLES)
    return unicodedata.normalize('NFKC', cleaned)

def has_shaping_breaker_inside_words(text):
    """فحص وجود أحرف مقطعة داخل كلمات عربية"""
    for word in text.split(' '):
        if any('\u0600' <= c <= '\u06FF' or '\uFB50' <= c <= '\uFEFF' for c in word):
            for c in word:
                if c in SHAPING_BREAKERS:
                    return True, word
    return False, None

print('═' * 64)
print('🧪 اختبار 1: المحرك التكيفي v3.0 برسالة المستخدم الحقيقية')
print('═' * 64)

from adaptive_obfuscation import (
    AdaptiveObfuscationEngine, adaptive_engine,
    shield_invisible_distribute, apply_arabic_presentation_forms,
    FORBIDDEN_INVISIBLES, INVISIBLE_SHIELD_CHARS, sanitize_invisible_chars
)

for profile in ['light', 'medium', 'aggressive', 'insane']:
    eng = AdaptiveObfuscationEngine(profile=profile)
    ok_all = True
    detail = []
    for trial in range(30):
        result, info = eng.obfuscate(USER_MSG)
        # شرط 1: لا أحرف مقطعة للاتصال إطلاقاً
        breakers = [c for c in result if c in SHAPING_BREAKERS]
        if breakers:
            ok_all = False
            detail.append(f'{profile}: أحرف مقطعة {breakers[:2]}')
            break
        # شرط 2: النص الظاهر = نص المستخدم (NFKC متطابق)
        if visible_text(result) != unicodedata.normalize('NFKC', USER_MSG):
            ok_all = False
            detail.append(f'{profile}: النص الظاهر تغير!')
            print(f'   الأصل: {unicodedata.normalize("NFKC", USER_MSG)!r}')
            print(f'   الناتج: {visible_text(result)!r}')
            break
        # شرط 3: المعرف @ppppokl سليم 100%
        if '@ppppokl' not in result:
            ok_all = False
            detail.append(f'{profile}: المعرف تالف!')
            break
    check(f'المحرك [{profile}] - 30 تجربة نظيفة', ok_all, '; '.join(detail[:1]))

print()
print('═' * 64)
print('🧪 اختبار 2: بصمة stego - آمنة على العربية + فك الترميز')
print('═' * 64)

from stego_engine import (
    inject_zw_fingerprint, zero_width_reveal, zero_width_hide,
    parse_spintax_advanced, has_spintax, FINGERPRINT_ALPHABET
)

ok_fp = True
for trial in range(30):
    fp = inject_zw_fingerprint(USER_MSG, density=0.15)
    # البصمة تستخدم فقط الأبجدية الآمنة
    fp_invis = [c for c in fp if c in ALL_INVISIBLES]
    if any(c in SHAPING_BREAKERS for c in fp_invis):
        ok_fp = False; break
    # النص الظاهر محفوظ
    if visible_text(fp) != unicodedata.normalize('NFKC', USER_MSG):
        ok_fp = False; break
check('بصمة ZW - 30 تجربة (آمنة + ظاهر محفوظ)', ok_fp)

# فك ترميز zero_width_hide (الأداة اليدوية) بالأبجدية الجديدة
secret = 't.me/mychannel'
hidden = zero_width_hide(secret, 'نص عربي طويل كافٍ للاختبار هنا')
revealed = zero_width_reveal(hidden)
check('zero_width_hide → reveal roundtrip', revealed == secret, f'revealed={revealed!r}')

print()
print('═' * 64)
print('🧪 اختبار 3: انفصال مجموعات الأحرف (لا تفسد البصمة)')
print('═' * 64)

shield_set = set(INVISIBLE_SHIELD_CHARS)
fp_set = set(FINGERPRINT_ALPHABET)
check('الدرع الخفي ∩ أبجدية البصمة = ∅', not (shield_set & fp_set),
      f'shield={ {hex(ord(c)) for c in shield_set} } fp={ {hex(ord(c)) for c in fp_set} }')
check('لا 200B/200C/200D في أي مجموعة مستخدمة', not (shield_set & SHAPING_BREAKERS) and not (fp_set & SHAPING_BREAKERS))

# محاكاة: بصمة + درع معاً ثم فك
fp2 = inject_zw_fingerprint('نص الاختبار العربي مع تفاصيله الكاملة', density=0.3)
fp2_shielded = shield_invisible_distribute(fp2, density=0.3)
revealed2 = zero_width_reveal(fp2_shielded)
# البصمة العشوائية لا تحمل سراً - الفحص هنا: الدروع لا تضيف بتات البصمة
shield_only_bits = ''.join(
    {**{c: '00' for c in FINGERPRINT_ALPHABET}}.get(c, '')
    for c in fp2_shielded if c in shield_set)
check('أحرف الدرع لا تدخل في تدفق فك البصمة', shield_only_bits == '')

print()
print('═' * 64)
print('🧪 اختبار 4: Spintax (كلمات المستخدم فقط)')
print('═' * 64)

spin = '{مرحباً|أهلاً} بكم في {قناتنا|مجموعتنا} الحصرية t.me/example'
resolved = parse_spintax_advanced(spin)
check('حل Spintax المتداخل', ('{' not in resolved) and ('t.me/example' in resolved), resolved)
check('فحص has_spintax', has_spintax(spin) and not has_spintax('نص عادي بلا أقواس'))

print()
print('═' * 64)
print('🧪 اختبار 5: تنظيف المُدخل من الأحرف الخطرة')
print('═' * 64)

dirty = 'نص \u200cملصوق \u200bمن مصدر خارجي'
clean = sanitize_invisible_chars(dirty)
check('حذف 200B/200C/200D من المُدخل', '\u200c' not in clean and '\u200b' not in clean)

print()
print('═' * 64)
print('🧪 اختبار 6: التمييز البصري (مطابقة NFKC للأشكال الجديدة)')
print('═' * 64)

eng = AdaptiveObfuscationEngine(profile='medium')
r1, _ = eng.obfuscate('إجازة مرضية معتمد')
r2, _ = eng.obfuscate('إجازة مرضية معتمد')
check('كل رسالة تحصل على تكويد مختلف (كسر التشابه)', r1 != r2)
check('لكل النصوص الظاهر متطابق', visible_text(r1) == visible_text(r2) == 'إجازة مرضية معتمد')

print()
print('═' * 64)
print('🧪 اختبار 7: بنية bot.py سليمة')
print('═' * 64)

src = open('/home/z/my-project/bot.py', encoding='utf-8').read()
try:
    compile(src, 'bot.py', 'exec')
    check('bot.py يُترجم بدون أخطاء', True)
except SyntaxError as e:
    check('bot.py يُترجم بدون أخطاء', False, f'line {e.lineno}: {e.msg}')

# القاعدة الذهبية: لا نصوص وهمية في مسارات النشر
posting_region = src[:src.find('def log_posting')]
for bad in ['السلام عليكم', 'مساء الخير', 'شكراً للجميع', "['تم', 'شكراً']"]:
    check(f'لا يوجد "{bad}" في مسارات النشر', bad not in posting_region)

# bot.py يستورد الأسماء الصحيحة
check('استيراد adaptive_engine سليم', 'from adaptive_obfuscation import AdaptiveObfuscationEngine, adaptive_engine' in src)
check('استيراد stego_engine سليم', 'from stego_engine import stego_engine, SEND_MODES' in src)

print()
print('═' * 64)
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print(f'النتيجة: {passed}/{total} نجح')
print('═' * 64)
sys.exit(0 if passed == total else 1)
