#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""حذف المعالجات الميتة (لا يصلها ضغطة زر) من bot.py بشكل جراحي"""
import ast, re, sys

PATH = '/home/z/my-project/bot.py'
DEAD = [
    'toggle_stealth', 'toggle_super_encryption', 'toggle_hyper_enc',
    'enc_strength', 'toggle_fancy_text', 'toggle_spintax', 'toggle_kashida',
    'toggle_arabic_homoglyph', 'toggle_vs', 'toggle_tag', 'toggle_ghost_swarm',
    'toggle_human_delay', 'toggle_load_balancer', 'auto_join',
    'set_join_limit', 'toggle_join_human_delay', 'clean_db', 'confirm_clean',
]

with open(PATH, encoding='utf-8') as f:
    lines = f.readlines()

ranges = []
for name in DEAD:
    start = None
    for i, ln in enumerate(lines):
        if ln.rstrip('\n') == f"        elif data == '{name}':":
            start = i
            break
    if start is None:
        print(f"⚠️ لم أجد معالج: {name}")
        continue
    # نهاية الكتلة: أول elif/else على مستوى السلسلة أو خروج للدالة
    end = len(lines)
    for j in range(start + 1, len(lines)):
        ln = lines[j]
        if re.match(r'^ {8}(elif|else)\b', ln):
            end = j
            break
        if ln.strip() and (len(ln) - len(ln.lstrip())) < 8:
            end = j
            break
    ranges.append((start, end, name))

# حذف من الأسفل للأعلى
for start, end, name in sorted(ranges, reverse=True):
    print(f"🗑 حذف {name}: أسطر {start+1}-{end} ({end-start} سطر)")
    del lines[start:end]

src = ''.join(lines)
# تحقق فوري من صحة الصياغة
ast.parse(src)
with open(PATH, 'w', encoding='utf-8') as f:
    f.write(src)
print("\n✅ حُذفت الكتل كلها والصياغة سليمة")

# تحقق: الأسماء المحذوفة لم تعد تظهر كمعالجات
remaining = re.findall(r"elif data == '([^']+)'", src)
leftover = [n for n in DEAD if n in remaining]
print("معالجات متبقية من القائمة:", leftover if leftover else "لا شيء ✅")
