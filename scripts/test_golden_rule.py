# -*- coding: utf-8 -*-
"""
🧪 اختبار شامل للتحقق من القاعدة الذهبية:
   البوت يرسل نص المستخدم كما هو - لا "السلام عليكم" ولا أي كلمات دخيلة
"""
import sys
import unicodedata

sys.path.insert(0, '/home/z/my-project')

from stego_engine import (stego_engine, SEND_MODES, parse_spintax_advanced,
                          inject_zw_fingerprint, zero_width_hide, diacritic_hide)

# ═══════════════════════════════════════════════
# رسالة المستخدم الحقيقية (من شكواه)
# ═══════════════════════════════════════════════
USER_MSG = "[ إجازة مرضية ﺳﻛﻟﻳف معتمد ] لطلب واتساب: 🌲 خا.، ـااااص @ppppokl"

# كلمات ممنوعة نهائياً أن تظهر في رسالة لم يكتبها المستخدم
FORBIDDEN_WORDS = ["السلام", "عليكم", "مرحباً", "أهلاً", "مساء الخير", "صباح الخير",
                   "نتمنى", "شكراً لكم", "أصدقائي", "ورحمة الله"]


def strip_invisible(text: str) -> str:
    """إزالة كل الأحرف غير المرئية (Formatting + علامات التشكيل) لمقارنة النص الظاهر"""
    return ''.join(
        ch for ch in text
        if unicodedata.category(ch) not in ('Cf', 'Mn')
    )


def visible_match(original: str, processed: str) -> bool:
    """التحقق: النص الظاهر بعد المعالجة = النص الأصلي (مع تطبيع Presentation Forms)"""
    norm_orig = unicodedata.normalize('NFKC', original)
    norm_proc = unicodedata.normalize('NFKC', strip_invisible(processed))
    return norm_orig == norm_proc


def check_forbidden(processed: str, label: str) -> bool:
    """التحقق: لا توجد كلمات دخيلة أضافها البوت"""
    stripped = strip_invisible(processed)
    found = [w for w in FORBIDDEN_WORDS if w in stripped and w not in USER_MSG]
    if found:
        print(f"   ❌ [{label}] كلمات دخيلة: {found}")
        return False
    return True


print("=" * 64)
print("🧪 اختبار القاعدة الذهبية: رسالتك تُرسل كما هي بالضبط")
print("=" * 64)
print(f"\n📝 رسالة المستخدم:\n{USER_MSG}\n")

# ═══════════════════════════════════════════════
# 1) اختبار أوضاع الإرسال الثلاثة
# ═══════════════════════════════════════════════
print("1️⃣ أوضاع الإرسال (stego_engine.process):")
all_ok = True
for mode in ['normal', 'spintax', 'stego']:
    result, info = stego_engine.process(USER_MSG, mode=mode)
    ok_visible = visible_match(USER_MSG, result)
    ok_words = check_forbidden(result, mode)
    status = "✅" if (ok_visible and ok_words) else "❌"
    all_ok = all_ok and ok_visible and ok_words
    print(f"   {status} [{mode}] ظاهر-مطابق={ok_visible} لا-كلمات-دخيلة={ok_words} (طول {len(USER_MSG)}→{len(result)})")

# ═══════════════════════════════════════════════
# 2) اختبار Adaptive Engine بكل المستويات
# ═══════════════════════════════════════════════
print("\n2️⃣ Adaptive Obfuscation Engine (كل المستويات):")
from adaptive_obfuscation import AdaptiveObfuscationEngine, bayes_evade, adaptive_spintax

for profile in ['light', 'medium', 'aggressive', 'insane']:
    engine = AdaptiveObfuscationEngine(profile=profile)
    result, info = engine.obfuscate(USER_MSG)
    ok_visible = visible_match(USER_MSG, result)
    ok_words = check_forbidden(result, profile)
    status = "✅" if (ok_visible and ok_words) else "❌"
    all_ok = all_ok and ok_visible and ok_words
    print(f"   {status} [{profile}] ظاهر-مطابق={ok_visible} لا-كلمات-دخيلة={ok_words} (طبقات: {len(info['layers'])})")

# ═══════════════════════════════════════════════
# 3) الدوال المعطلة ترجع النص كما هو
# ═══════════════════════════════════════════════
print("\n3️⃣ الدوال المعطلة (لا تعدل النص):")
ok1 = bayes_evade(USER_MSG, 0.9) == USER_MSG
ok2 = adaptive_spintax(USER_MSG, 0.9) == USER_MSG
print(f"   {'✅' if ok1 else '❌'} bayes_evade → النص كما هو")
print(f"   {'✅' if ok2 else '❌'} adaptive_spintax → النص كما هو")
all_ok = all_ok and ok1 and ok2

# ═══════════════════════════════════════════════
# 4) لا نصوص غلاف تلقائية
# ═══════════════════════════════════════════════
print("\n4️⃣ لا نصوص غلاف تلقائية (100 محاولة):")
ok3 = True
for i in range(100):
    out = zero_width_hide(USER_MSG, "")          # بدون غلاف
    out2 = diacritic_hide(USER_MSG, "")          # بدون غلاف
    for w in FORBIDDEN_WORDS:
        if w in out or w in out2:
            print(f"   ❌ تسرب نص غلاف: '{w}' في المحاولة {i}")
            ok3 = False
            break
    if not ok3:
        break
print(f"   {'✅' if ok3 else '❌'} لا توجد أي نصوص غلاف مولدة تلقائياً")
all_ok = all_ok and ok3

# ═══════════════════════════════════════════════
# 5) Spintax يحل صيغة المستخدم فقط
# ═══════════════════════════════════════════════
print("\n5️⃣ Spintax (يكتبه المستخدم بنفسه):")
spin_msg = "{مرحباً|أهلاً} بكم في {قناتنا|مجموعتنا} t.me/example"
ok4 = True
for i in range(20):
    out = parse_spintax_advanced(spin_msg)
    if '{' in out or '|' in out or '}' in out:
        print(f"   ❌ لم تُحل الأقواس: {out}")
        ok4 = False
        break
    if "السلام" in out:
        ok4 = False
        break
print(f"   {'✅' if ok4 else '❌'} يختار من خيارات المستخدم فقط")
all_ok = all_ok and ok4

# ═══════════════════════════════════════════════
# 6) الروابط والمعرفات سليمة
# ═══════════════════════════════════════════════
print("\n6️⃣ الروابط والمعرفات تبقى ظاهرة:")
link_msg = "اشترك الآن t.me/mychannel @mybot https://example.com"
r1, _ = stego_engine.process(link_msg, mode='stego')
ok5 = 't.me/mychannel' in r1 and '@mybot' in r1 and 'https://example.com' in r1
print(f"   {'✅' if ok5 else '❌'} الروابط والمعرفات موجودة في وضع stego")
all_ok = all_ok and ok5

# ═══════════════════════════════════════════════
print("\n" + "=" * 64)
if all_ok:
    print("✅✅ نجح كل الاختبار - رسالتك تُرسل كما هي بالضبط!")
    print("   لا (السلام عليكم) ولا أي نص دخيل - تشفير غير مرئي فقط")
else:
    print("❌ فشل اختبار - راجع الأخطاء أعلاه")
    sys.exit(1)
