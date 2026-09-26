#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧪 اختبار v4.5 - إصلاحات: (1) salt لا يلتصق باليوزر (2) درع الهواتف المتبقية
(3) زر اختبار النشر (عين المستخدم/عين البوت)
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('API_ID', '33957094')
os.environ.setdefault('API_HASH', '35e04f65aaa')
os.environ.setdefault('BOT_TOKEN', '864204:test')

USER_AD = """✅اعذار طبية تطبيق صحتي
تقرير مرافق مريض
حرمانية دوام انتقال
يومين اسبوع
حسب نظام صحتي
للتواصل واتساب
0552948177
@ppppokl"""

import bot
bot.init_db()
from bot import (prepare_content_for_sending, visualize_invisibles,
                 _bot_regex_findings, build_publish_test_report,
                 _is_invisible_cp)

# ⚠️ بناء نطاقات VS النجمية برمجياً (‏\U0001E0100 خاطئة - الصحيح U+E0100)
_VS_LO, _VS_HI = chr(0xE0100), chr(0xE01EF)
_VS_CLASS = f"[{re.escape(_VS_LO)}-{re.escape(_VS_HI)}]"

fails = []

def check(name, cond, detail=""):
    print(f"  {'✅' if cond else '❌'} {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        fails.append(name)

print("=" * 68)
print("اختبار 1: ثبات المسار الكامل (10 تجارب)")
print("=" * 68)
for i in range(10):
    encoded, use_html, ents = prepare_content_for_sending(USER_AD)

    # أ) الرقم الهاتف محمي: regex الهواتف لا يجده
    phone_clean = bool(re.search(r'(?<![\w@./])\+?\d[\d\s\-]{5,16}\d(?![\w@./])', encoded))
    check(f"[{i}] الهاتف مخفي عن regex", not phone_clean)

    # ب) salt لا يلتصق بنهاية اليوزر: آخر حرف مرئي ليس ملتصقاً بأحرف خفية بعد يوزر
    # نتحقق: لا يوجد @username متبوعاً مباشرة بأحرف خفية متكدسة (3+)
    # ⚠️ النطاق النجمي في Python regex يُكتب \U0001E0100 (8 أرقام)
    stacked = re.search(r'@[a-zA-Z0-9_]{3,31}' + _VS_CLASS + r'{3,}\s*$', encoded)
    check(f"[{i}] لا تكديس خفي بعد اليوزر", not stacked)

    # ج) اليوزر نفسه نظيف داخلياً (قابل للمنشن)
    m = re.search(r'(?<![\w@.])@ppppokl(?!' + _VS_CLASS + r')', encoded)
    check(f"[{i}] @ppppokl نظيف قابل للمنشن", bool(m))

    # د) الكلمات المفتاحية مجزأة
    kws = [kw for kw in ['اعذار', 'طبية', 'صحتي', 'تقرير', 'مرافق', 'حرمانية', 'واتساب', 'تواصل'] if kw in encoded]
    check(f"[{i}] لا كلمة مفتاحية كاملة", not kws, f"({kws})" if kws else "")

    # هـ) الرسم الظاهر مطابق (NFKC بعد إزالة الخفي)
    import unicodedata
    from adaptive_obfuscation import strip_ghost_chars
    visible = ''.join(ch for ch in encoded if not _is_invisible_cp(ord(ch)))
    check(f"[{i}] الرسم الظاهر مطابق 100%",
          unicodedata.normalize('NFKC', visible) == unicodedata.normalize('NFKC', USER_AD))

print()
print("=" * 68)
print("اختبار 2: عين البوت على النتيجة الأخيرة")
print("=" * 68)
encoded, use_html, ents = prepare_content_for_sending(USER_AD)
raw_findings = _bot_regex_findings(USER_AD)
enc_findings = _bot_regex_findings(encoded)
print(f"  قبل التكويد: {len(raw_findings)} ثغرة → {raw_findings}")
print(f"  بعد التكويد: {len(enc_findings)} ثغرة → {enc_findings}")
check("الهاتف لم يعد يُلتقط", len(enc_findings) < len(raw_findings))
check("لم يبقَ إلا اليوزر (يُحل بزر الارتباط)",
      all('يوزر' in f for f in enc_findings) if enc_findings else True)

print()
print("=" * 68)
print("اختبار 3: كيانات العرض (المنشن قابل للضغط)")
print("=" * 68)
ent_types = [type(e).__name__ for e in (ents or [])]
print(f"  الكيانات: {ent_types}")
check("يوجد MessageEntityMention لليوزر", 'MessageEntityMention' in ent_types)

# التحقق من دقة إزاحة المنشن (UTF-16)
from link_guard import find_clean_mentions
mentions = find_clean_mentions(encoded)
if mentions:
    off, ln, uname = mentions[0]
    import json
    enc_u16 = encoded.encode('utf-16-le')
    # استخراج النص بالإزاحة والطول بوحدات UTF-16
    tok_bytes = enc_u16[off*2:(off+ln)*2]
    tok = tok_bytes.decode('utf-16-le')
    check(f"إزاحة المنشن صحيحة (يستخرج @{uname})", tok == f"@{uname}", f"got {tok!r}")
else:
    check("إزاحة المنشن صحيحة", False, "لا منشن!")

print()
print("=" * 68)
print("اختبار 4: عين البوت (التصوير البصري ◌)")
print("=" * 68)
viz = visualize_invisibles(encoded)
inv_in_viz = sum(1 for ch in viz if _is_invisible_cp(ord(ch)))
check("الصورة البصرية بلا أحرف خفية متبقية", inv_in_viz == 0)
check("الصورة تعرض ◌", '◌' in viz)
check("الصورة تحفظ النص الظاهر",
      viz.replace('◌', '') == ''.join(ch for ch in encoded if not _is_invisible_cp(ord(ch))))
print()
print(viz[:400])

print()
print("=" * 68)
print("اختبار 5: تقرير اختبار النشر (زر القائمة)")
print("=" * 68)
report = build_publish_test_report(USER_AD, encoded, ents)
check("التقرير يتضمن قبل التكويد", "قبل التكويد" in report)
check("التقرير يتضمن عدد الأحرف الخفية", "أحرف خفية محقونة" in report)
check("التقرير يتضمن محاكاة البوتات", "محاكاة regex" in report)
print()
print(report[:900])

print()
print("=" * 68)
print("اختبار 6: salt موزع لا ختامي (إحصائياً)")
print("=" * 68)
tail_ok = 0
for i in range(20):
    e2, _, _ = prepare_content_for_sending(USER_AD)
    # هل تنتهي الرسالة بأحرف خفية؟
    if not re.search(_VS_CLASS.replace(']', '\u2063\u2064]') + r'{3,}\s*$', e2):
        tail_ok += 1
check(f"salt في المنتصف في {tail_ok}/20 تجربة (النهاية نظيفة)", tail_ok >= 18, f"{tail_ok}/20")

print()
print("=" * 68)
print(f"النتيجة: {'🎉 كل الاختبارات نجحت' if not fails else '❌ فشل: ' + str(fails)}")
print("=" * 68)
sys.exit(1 if fails else 0)
