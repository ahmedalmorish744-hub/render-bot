#!/usr/bin/env python3
"""فحص شامل v2: أزرار inline (ثابتة وديناميكية) مقابل معالجات الموزع"""
import re

with open('/home/z/my-project/bot.py', 'r', encoding='utf-8') as f:
    src = f.read()

# 1) كل بيانات الأزرار الثابتة (b"data" أو "data")
buttons = set()
for m in re.finditer(r'Button\.inline\([^,]+,\s*(b?"[^"]*\")\s*[,)]', src):
    raw = m.group(1).strip()
    if raw.startswith('b'):
        raw = raw[1:]
    data = raw.strip('"')
    if '{' not in data:
        buttons.add(data)

# بيانات أزرار من متغيرات/أوف-ستنق
dyn = set()
for m in re.finditer(r'Button\.inline\([^,]+,\s*f?"([^"]*\{[^}]+\}[^"]*)"', src):
    dyn.add(m.group(1))
for m in re.finditer(r'Button\.inline\([^,]+,\s*([a-zA-Z_][\w.]*)\(?[^)]*\)?\s*[,)]', src):
    v = m.group(1)
    if v not in ('True', 'False'):
        dyn.add('VAR: ' + v)

# 2) معالجات الموزع
handled = set()
for m in re.finditer(r'(?:if|elif)\s+data\s*==\s*[\'"]([^\'"]+)[\'"]', src):
    handled.add(m.group(1))
startswith_patterns = [m.group(1) for m in re.finditer(r'data\.startswith\([\'"]([^\'"]+)[\'"]\)', src)]

def covered_by_prefix(b):
    return [p for p in startswith_patterns if b.startswith(p)]

print("=== أ) أزرار بلا معالج (معطلة للمستخدم) ===")
unhandled = sorted(b for b in buttons if b not in handled and not covered_by_prefix(b))
print('  (لا شيء)' if not unhandled else '\n'.join(f"  '{b}' ❌" for b in unhandled))

print("\n=== ب) معالجات لا يصلك منها ضغطة زر ثابت (يتيمة) ===")
orphans = sorted(h for h in handled - buttons if not any(h.startswith(p) for p in startswith_patterns))
print('  (لا شيء)' if not orphans else '\n'.join(f"  '{h}'" for h in orphans))

print("\n=== ج) أزرار ديناميكية ===")
for d in sorted(dyn):
    print(f"  {d}")

print("\n=== د) أنماط startswith في الموزع ===")
for p in startswith_patterns:
    print(f"  '{p}'")

# 3) أين تُستخدم المعالجات اليتيمة؟ هل تُبنى أزرارها بنمط مختلف؟
print("\n=== هـ) مواضع أزرار مبنية بأسلوب مختلف (Button.inline بأسطر متعددة) ===")
for m in re.finditer(r'Button\.inline\(\s*\n?\s*[^,]+,\s*\n?\s*([^)]{1,60})\)', src):
    d = m.group(1).strip()
    if d.startswith('b"') or d.startswith('"') or d.startswith("b'") or d.startswith("'"):
        continue
    if '{' in d:
        continue
    line = src[:m.start()].count('\n') + 1
    print(f"  L{line}: {d[:70]}")
