# -*- coding: utf-8 -*-
"""
🧪 اختبار شامل لـ Ghost Encoding v4.0
يتحقق من: حفظ رسم الكلمات + كسر الكشف + الأمان من التكرار + توافق bot.py
"""
import sys
import ast
import unicodedata
import random

sys.path.insert(0, '/home/z/my-project')

from adaptive_obfuscation import (
    AdaptiveObfuscationEngine, adaptive_engine, quick_obfuscate,
    sanitize_invisible_chars, strip_ghost_chars, ghost_ratio,
    ghost_vs_inject, cf_boundary_inject, shield_invisible_distribute,
    bayes_evade, adaptive_spintax, apply_tag_chars, apply_nfd_decomposition,
    apply_arabic_presentation_forms, strip_presentation_forms,
    add_anti_similarity_salt, VS_POOL, INVISIBLE_SHIELD_CHARS,
    NON_FORWARD_JOINERS, apply_layer_protected,
)

PASS = 0
FAIL = 0
FAILED = []

def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        FAILED.append(name)
        print(f"  ❌ {name} {detail}")

GHOST = set(VS_POOL) | set(INVISIBLE_SHIELD_CHARS)

def visible(text):
    """النص الظاهر: حذف كل الأحرف الشبحية"""
    return ''.join(ch for ch in text if ch not in GHOST)

def norm(s):
    return unicodedata.normalize('NFKC', s)

# ═══════════════════════════════════════════════════════════
print("=" * 60)
print("🧪 اختبار Ghost Encoding v4.0 الشامل")
print("=" * 60)

# ═══ 1. رسالة المستخدم الحقيقية ═══
print("\n── 1) رسالة المستخدم الحقيقية (الرسم كما هو) ──")
USER_MSG = "[ إجازة مرضية ﺳﻛﻟﻳف معتمد ] لطلب وتساب: 🌲 خا.، ـااااص @ppppokl"
for profile in ['light', 'medium', 'aggressive', 'insane']:
    eng = AdaptiveObfuscationEngine(profile=profile)
    ok_all = True
    for trial in range(30):
        out, info = eng.obfuscate(USER_MSG)
        if norm(visible(out)) != norm(USER_MSG):
            ok_all = False
            break
    check(f"{profile}: النص الظاهر مطابق 100% (30 تجربة)", ok_all)

# ═══ 2. لا أشكال عرض جديدة + لا تفكيك NFD ═══
print("\n── 2) لا أشكال عرض / لا NFD جديدة ──")
PLAIN = "اشترك في قناتنا عروض حصرية واتساب تواصل مجاناً"
eng = AdaptiveObfuscationEngine(profile='insane')
out, _ = eng.obfuscate(PLAIN)

def count_range(s, a, b):
    return sum(1 for ch in s if a <= ord(ch) <= b)

# أشكال العرض الحقيقية: Forms A (FB50-FDFF) + Forms B (FE70-FEFF)
# (نستثني FE00-FE0F لأنها VS1-16 = قناتنا الخفية وليست أشكال عرض)
new_pf = (count_range(out, 0xFB50, 0xFDFF) - count_range(PLAIN, 0xFB50, 0xFDFF)
          + count_range(out, 0xFE70, 0xFEFF) - count_range(PLAIN, 0xFE70, 0xFEFF))
check("صفر أشكال عرض جديدة (FB50-FDFF + FE70-FEFF)", new_pf == 0, f"(أضيف {new_pf})")

def count_marks(s):
    return sum(1 for ch in s if unicodedata.category(ch) in ('Mn', 'Me') and ch not in GHOST)

new_marks = count_marks(out) - count_marks(PLAIN)
check("صفر علامات تشكيل جديدة (لا NFD/همزات)", new_marks == 0, f"(أضيف {new_marks})")
check("لا ZWJ/ZWNJ/ZWSP في الناتج",
      not any(c in out for c in ('\u200B', '\u200C', '\u200D')))
check("دوال الطبقات القديمة no-op",
      apply_arabic_presentation_forms("نص") == "نص"
      and apply_nfd_decomposition("نص") == "نص"
      and bayes_evade("نص") == "نص"
      and adaptive_spintax("نص") == "نص"
      and apply_tag_chars("نص") == "نص")

# ═══ 3. محاكاة محرك عرض صارم: Cf في مواضع حيادية فقط ═══
print("\n── 3) قواعد الاتصال العربي (محاكاة محرك صارم) ──")
# الحروف العربية (حسب المعيار): Cf غير الواصل يقطع الاتصال بين
# حرف يتصل للأمام وحرف يتصل من الخلف. نتحقق من عدم حدوث ذلك أبداً.
AR_RE = __import__('re').compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')
MARK_RE = __import__('re').compile(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]')

def joining_breaks(text):
    """يحاكي محرك عرض صارم: يعد مواضع كسر الاتصال المسببة بالأحرف الشبحية"""
    chars = list(text)
    breaks = 0
    for i, ch in enumerate(chars):
        if ch in INVISIBLE_SHIELD_CHARS:  # Cf غير واصل
            prev = chars[i-1] if i > 0 else ''
            nxt = chars[i+1] if i+1 < len(chars) else ''
            if not prev or not nxt:
                continue
            # نتجاهل مواضع قبل/بعد علامات التشكيل (شفافة)
            if MARK_RE.match(nxt) or MARK_RE.match(prev):
                continue
            if AR_RE.match(prev) and AR_RE.match(nxt):
                prev_fw = prev not in NON_FORWARD_JOINERS
                # كل الحروف العربية تتصل من الخلف (عدا العلامات)
                if prev_fw:
                    breaks += 1
    return breaks

TEST_WORDS = "شكرا جزيلا على المساعدة الودودة، حبذا لو تتابعون الملفات المطلوبة بتأكد أكثر"
for profile in ['medium', 'aggressive', 'insane']:
    eng = AdaptiveObfuscationEngine(profile=profile)
    total_breaks = 0
    for _ in range(50):
        out, _ = eng.obfuscate(TEST_WORDS)
        total_breaks += joining_breaks(out)
    check(f"{profile}: صفر كسور اتصال (50 تجربة)", total_breaks == 0, f"(كسور: {total_breaks})")

# ═══ 4. كسر الكلمات المفتاحية (مستحيل الكشف) ═══
print("\n── 4) كسر كشف الكلمات المفتاحية ──")
SPAM = "اشترك في قناتنا للحصول على عروض حصرية واتساب 0555123456"
eng = AdaptiveObfuscationEngine(profile='medium')
keywords_found_total = 0
for _ in range(20):
    out, _ = eng.obfuscate(SPAM)
    # محاكاة بوت كشف: يحذف الأحرف الكلاسيكية المعروفة فقط (200B-200D/2060-2064/061C/FEFF)
    # لكن لا يحذف قناة VS الحديثة → الكلمات تبقى مجزأة
    classic_stripped = ''.join(
        ch for ch in out
        if ch not in ('\u200B', '\u200C', '\u200D', '\u2060', '\u2061', '\u2062', '\u2063', '\u2064', '\u061C', '\uFEFF')
    )
    for kw in ['اشترك', 'قناتنا', 'عروض', 'واتساب']:
        if kw in classic_stripped:
            keywords_found_total += 1
check("الكلمات المفتاحية مجزأة (لا تجدها بوتات التنظيف الكلاسيكي)",
      keywords_found_total == 0, f"(عثر على {keywords_found_total})")

# حتى بوت ينجو منه عبر حذف VS من مواضع عشوائية؟ تدهور رشيق:
out, _ = eng.obfuscate(SPAM)
check("تدهور رشيق: حذف كل الخفي يعيد النص الأصلي سليماً",
      norm(strip_ghost_chars(out)) == norm(SPAM))

# ═══ 5. حماية التكرار (سبب تلبّط "بدء النشر" سابقاً) ═══
print("\n── 5) الأمان من التشفير المزدوج ──")
eng = AdaptiveObfuscationEngine(profile='insane')
out1, _ = eng.obfuscate(SPAM)
out2, _ = eng.obfuscate(out1)  # محاكاة مرور ثانٍ بمسار آخر
out3, _ = eng.obfuscate(out2)
check("تشفير ثلاثي: الرسم محفوظ", norm(visible(out3)) == norm(SPAM))
check("تشفير ثلاثي: لا انفجار طول", len(out3) < len(SPAM) * 2.5,
      f"(طول: {len(SPAM)} → {len(out3)})")
r1 = ghost_ratio(out1)
r3 = ghost_ratio(out3)
check("تشفير ثلاثي: لا تكديس (النسبة ثابتة تقريباً)", abs(r3 - r1) < 0.15,
      f"({r1:.2%} → {r3:.2%})")
check("النسبة تحت سقف الكشف الإحصائي (< 45%)", r3 < 0.45, f"({r3:.2%})")

# ═══ 6. الروابط والمعرفات محمية ═══
print("\n── 6) حماية الروابط والمعرفات ──")
LINKS = "زورونا https://t.me/mychannel t.me/other @ppppokl للتواصل"
ok = True
for _ in range(20):
    out, _ = eng.obfuscate(LINKS)
    for token in ['https://t.me/mychannel', 't.me/other', '@ppppokl']:
        if token not in out:
            ok = False
check("الروابط والمعرفات تمر حرفياً بدون أي تعديل", ok)

# ═══ 7. حماية الطول ═══
print("\n── 7) حماية طول رسالة تيليجرام ──")
LONG = "نص طويل جداً للاختبار مع كلمات كثيرة. " * 60  # ~2400 حرف
eng = AdaptiveObfuscationEngine(profile='insane')
out, info = eng.obfuscate(LONG)
check(f"الطول داخل الميزانية الآمنة ({len(out)} ≤ 3900)", len(out) <= 3900)
check("النص الظاهر محفوظ بعد القص", norm(visible(out)) == norm(LONG))

# ═══ 8. التوافق مع واجهة bot.py ═══
print("\n── 8) توافق API مع bot.py ──")
check("get_layer_status بأسماء جديدة",
      adaptive_engine.get_layer_status('ghost_vs_channel') is True
      and adaptive_engine.get_layer_status('cf_boundary') is True
      and adaptive_engine.get_layer_status('keyword_boost') is True
      and adaptive_engine.get_layer_status('salt') is True)
check("get_layer_status بأسماء قديمة (توافق)",
      adaptive_engine.get_layer_status('zw_distribution') is True   # alias → ghost_vs
      and adaptive_engine.get_layer_status('arabic_forms') is False # معطلة
      and adaptive_engine.get_layer_status('nfd') is False
      and adaptive_engine.get_layer_status('tag_chars') is False)
check("toggle_layer يعمل + الطبقات الخطرة ممنوعة",
      adaptive_engine.toggle_layer('salt') is False
      and adaptive_engine.toggle_layer('salt') is True
      and adaptive_engine.toggle_layer('arabic_forms') is False)
check("set_profile يقبل المستويات الأربعة",
      all(adaptive_engine.set_profile(p) for p in ['light', 'medium', 'aggressive', 'insane']))
check("obfuscate يرجع (نص, معلومات)",
      isinstance(adaptive_engine.obfuscate("تجربة")[0], str)
      and 'layers' in adaptive_engine.obfuscate("تجربة")[1])
check("get_info نص غير فارغ", len(adaptive_engine.get_info()) > 100)
check("quick_obfuscate يعمل", len(quick_obfuscate("نص للتشفير السريع")) > 10)
info_str = adaptive_engine.get_info()
check("get_info يعرض v4.0", 'v4.0' in info_str)

# ═══ 9. نص المستخدم السابق مع أشكال عرض أصلاً (لا معالجة مزدوجة) ═══
print("\n── 9) نص يحتوي أشكال عرض أصلاً ──")
MIXED = "[ إجازة مرضية ﺳﻛﻟﻳف معتمد ] لطلب وتساب: @ppppokl"
eng = AdaptiveObfuscationEngine(profile='medium')
ok = True
for _ in range(20):
    out, _ = eng.obfuscate(MIXED)
    # أشكال العرض الأصلية تبقى كما هي (لا تُعالج ولا تُحذف)
    if 'ﺳﻛﻟﻳف' not in visible(out):
        ok = False
check("أشكال العرض الموجودة في نص المستخدم تُترك كما هي", ok)

# ═══ 10. بناء جملة bot.py سليم ═══
print("\n── 10) بناء جملة bot.py ──")
src = open('/home/z/my-project/bot.py', encoding='utf-8').read()
try:
    ast.parse(src)
    check("bot.py ast.parse ناجح", True)
except SyntaxError as e:
    check("bot.py ast.parse ناجح", False, str(e))
src2 = open('/home/z/my-project/adaptive_obfuscation.py', encoding='utf-8').read()
try:
    ast.parse(src2)
    check("adaptive_obfuscation.py ast.parse ناجح", True)
except SyntaxError as e:
    check("adaptive_obfuscation.py ast.parse ناجح", False, str(e))

# ═══ النتيجة ═══
print("\n" + "=" * 60)
print(f"📊 النتيجة: {PASS} نجح | {FAIL} فشل")
if FAILED:
    print("❌ الاختبارات الفاشلة:")
    for f in FAILED:
        print(f"   - {f}")
    sys.exit(1)
print("✅ كل الاختبارات نجحت!")
