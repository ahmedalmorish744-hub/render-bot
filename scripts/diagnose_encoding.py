#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔬 تشخيص: لماذا يقول المستخدم أن إعلانه "ما يتكود"؟
نُشغّل المسار الفعلي prepare_content_for_sending على إعلان المستخدم الحقيقي
ونفحص: عدد الأحرف الخفية + ما تراه regex بوتات الحماية
"""
import sys, os, re, unicodedata
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

GHOST_RANGES = [
    (0x200B, 0x200F), (0x202A, 0x202E), (0x2060, 0x206F),
    (0xFE00, 0xFE0F), (0xFEFF, 0xFEFF), (0x061C, 0x061C),
    (0x180B, 0x180E), (0xE0000, 0xE0FFF), (0x1D173, 0x1D17A),
]

def count_invisible(text):
    n = 0
    details = {}
    for ch in text:
        cp = ord(ch)
        for lo, hi in GHOST_RANGES:
            if lo <= cp <= hi:
                n += 1
                key = f'U+{cp:04X}'
                details[key] = details.get(key, 0) + 1
                break
    return n, details

def bot_regex_scan(text):
    """محاكاة بوتات الحماية"""
    findings = []
    if re.search(r'@[a-zA-Z0-9_]{4,}', text):
        findings.append('@username ظاهر نظيفاً ← regex يلتقطه')
    if re.search(r'(?:https?://|t\.me/|wa\.me/|telegram\.me/)\S+', text):
        findings.append('رابط ظاهر نظيفاً ← regex يلتقطه')
    if re.search(r'(?:\+?966|0)?5\d{2}[\s-]?\d{3}[\s-]?\d{3}|\b7\d{8}\b|\b05\d{8}\b', text):
        findings.append('رقم هاتف ظاهر نظيفاً ← regex يلتقطه')
    # كلمات مفتاحية كاملة (بلا تجزئة)
    for kw in ['اعذار', 'طبية', 'صحتي', 'تقرير', 'مرافق', 'حرمانية', 'واتساب', 'تواصل']:
        if kw in text:
            findings.append(f'كلمة مفتاحية "{kw}" كاملة ← مطابقة تامة')
    return findings

print('=' * 70)
print('1) الإعلان الأصلي')
print('=' * 70)
inv, det = count_invisible(USER_AD)
print(f'أحرف خفية: {inv}')
print('ما تراه بوتات الحماية:')
for f in bot_regex_scan(USER_AD):
    print('  🚨', f)

print()
print('=' * 70)
print('2) تشغيل المسار الفعلي prepare_content_for_sending')
print('=' * 70)
import bot
bot.init_db()
content, use_html, entities = bot.prepare_content_for_sending(USER_AD)

inv2, det2 = count_invisible(content)
print(f'الناتج: {len(content)} حرف (الأصل {len(USER_AD)})')
print(f'أحرف خفية: {inv2}')
if det2:
    top = sorted(det2.items(), key=lambda x: -x[1])[:8]
    print('تفصيل:', ', '.join(f'{k}×{v}' for k, v in top))
ratio = inv2 / max(len(content), 1)
print(f'نسبة الخفي: {ratio:.1%}')

print()
print('=' * 70)
print('3) ما تراه بوتات الحماية على الناتج')
print('=' * 70)
findings = bot_regex_scan(content)
if findings:
    for f in findings:
        print('  🚨', f)
else:
    print('  ✅ لا شيء — كل شيء مموّه')

print()
print('=' * 70)
print('4) إظهار الخفي بصرياً (كل حرف خفي ← ◌)')
print('=' * 70)
def visualize(text):
    out = []
    for ch in text:
        cp = ord(ch)
        hidden = any(lo <= cp <= hi for lo, hi in GHOST_RANGES)
        out.append('◌' if hidden else ch)
    return ''.join(out)

print(visualize(content)[:600])

print()
print('=' * 70)
print('5) فحص إعدادات الإنتاج الافتراضية')
print('=' * 70)
for key in ['adaptive_obfuscation_enabled', 'adaptive_obfuscation_profile',
            'link_guard_enabled', 'link_guard_targets', 'send_mode',
            'text_style_boost', 'spintax_enabled']:
    print(f'  {key} = {bot.get_setting(key)!r}')
