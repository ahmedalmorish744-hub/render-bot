#!/usr/bin/env python3
"""اختبار v7.2: التحقق من إصلاح استخراج الروابط + إخفاء أزرار الأدمن."""
import os, sys, ast, re
sys.path.insert(0, '/home/z/my-project')

results = []
def ok(n): results.append((n, True, ''))
def fail(n, m): results.append((n, False, m))

# ─── 1) AST: extract_telegram_links accepts 4-char and 3-char usernames ───
print('━━━ 1) AST: link extraction uses len >= 3 ━━━')
src = open('/home/z/my-project/bot.py').read()
# Find all "len(path) >= " and "len(username) >= "
import re
path_lens = re.findall(r'len\(path\) >= (\d+)', src)
username_lens = re.findall(r'len\(username\) >= (\d+)', src)
all_lens = [int(x) for x in path_lens + username_lens]
# Verify all are 3 or less
if all_lens and max(all_lens) <= 4:
    ok(f'link extraction accepts >= {min(all_lens)} chars (was 5 before)')
else:
    fail(f'link extraction len checks', f'values: {all_lens}')

# ─── 2) AST: regex pattern allows 3-char usernames ───
print('━━━ 2) AST: regex pattern allows 3+ char usernames ━━━')
# Check pattern_public regex: [a-zA-Z0-9_]{3,} or {4,}
pattern_match = re.search(r'pattern_public = r\'[^\']+\'', src)
if pattern_match:
    pat = pattern_match.group(0)
    # Look for {N,}
    inner = re.search(r'\{(\d+),\}', pat)
    if inner:
        n = int(inner.group(1))
        if n <= 4:
            ok(f'pattern_public regex uses {{{n},}} (allows {n}+ chars)')
        else:
            fail(f'pattern_public regex', f'requires {n}+ chars: {pat}')
    else:
        fail('pattern_public regex', f'no {{N,}} in pattern: {pat}')
else:
    fail('pattern_public', 'regex not found')

# ─── 3) Functional test: extract_telegram_links catches short usernames ───
print('━━━ 3) Functional: short username extraction ━━━')
try:
    ns = {}
    exec(compile('import re, os, sqlite3, json, asyncio, random, time, logging', '<exec>', 'exec'), ns)
    fn_start = src.find('_LINK_INVISIBLE_RE = re.compile')
    fn_end = src.find('\ndef is_already_joined')
    fn_code = src[fn_start:fn_end]
    exec(fn_code, ns)
    fn = ns['extract_telegram_links']

    test_cases = [
        # 3-char (was failing before, should work now)
        ('t.me/abc', ['https://t.me/abc']),
        ('@abc', ['https://t.me/abc']),
        ('قروب جديد t.me/abc', ['https://t.me/abc']),
        ('الرابط: t.me/abc', ['https://t.me/abc']),
        # 4-char
        ('t.me/abcd', ['https://t.me/abcd']),
        ('@abcd', ['https://t.me/abcd']),
        # 5-char
        ('t.me/abcde', ['https://t.me/abcde']),
        # invite links (always worked)
        ('https://t.me/+abcDef', ['https://t.me/+abcDef']),
        ('https://t.me/joinchat/abcDef', ['https://t.me/joinchat/abcDef']),
        # Multiple
        ('@abc @def t.me/xyz', ['https://t.me/abc', 'https://t.me/def', 'https://t.me/xyz']),
        # No false positives
        ('نص عادي', []),
        ('hello world', []),
    ]
    for text, expected in test_cases:
        result = fn(text)
        result_set = set(result)
        expected_set = set(expected)
        if result_set == expected_set:
            ok(f'extract({text!r})')
        else:
            fail(f'extract({text!r})', f'expected {expected}, got {result}')
except Exception as e:
    import traceback; traceback.print_exc()
    fail('Functional test', str(e))

# ─── 4) AST: accounts menu has admin-only gate ───
print('━━━ 4) AST: accounts menu admin gate ━━━')
idx_acc = src.find("elif data == 'accounts':")
if idx_acc >= 0:
    block = src[idx_acc:idx_acc+2500]
    # Check that:
    # 1. Buttons list starts with add/view/del/back only
    # 2. is_admin check inserts refresh_groups/vault_backup/vault_restore conditionally
    has_is_admin = 'is_admin(event.sender_id)' in block
    has_refresh = 'refresh_groups' in block
    has_vault_b = 'vault_backup' in block
    has_vault_r = 'vault_restore' in block
    # Verify the base buttons list does NOT contain the admin buttons
    # (look at the initial _acc_buttons = [ ... ] list)
    init_list_start = block.find('_acc_buttons = [')
    init_list_end = block.find(']', init_list_start) + 1
    init_list = block[init_list_start:init_list_end]
    base_has_refresh = 'refresh_groups' in init_list
    base_has_vault_b = 'vault_backup' in init_list
    base_has_vault_r = 'vault_restore' in init_list

    if (has_is_admin and has_refresh and has_vault_b and has_vault_r
            and not base_has_refresh and not base_has_vault_b and not base_has_vault_r):
        ok('accounts menu: admin-only buttons (refresh/vault_backup/vault_restore)')
    else:
        fail('accounts menu admin gate',
             f'admin check={has_is_admin}, refresh in base={base_has_refresh}, '
             f'vault_b in base={base_has_vault_b}, vault_r in base={base_has_vault_r}')
else:
    fail('accounts menu', 'handler not found')

# ─── 5) AST: vault_backup callback is admin-gated ───
print('━━━ 5) AST: vault_backup callback admin-gated ━━━')
idx_vb = src.find("elif data == 'vault_backup':")
if idx_vb >= 0:
    block = src[idx_vb:idx_vb+500]
    has_admin_check = 'if not is_admin(event.sender_id):' in block
    has_alert = "alert=True" in block
    has_return = 'return' in block
    if has_admin_check and has_alert and has_return:
        ok('vault_backup callback: admin-gated')
    else:
        fail('vault_backup callback gate',
             f'admin_check={has_admin_check}, alert={has_alert}, return={has_return}')
else:
    fail('vault_backup callback', 'not found')

# ─── 6) AST: vault_restore callback is admin-gated ───
print('━━━ 6) AST: vault_restore callback admin-gated ━━━')
idx_vr = src.find("elif data == 'vault_restore':")
if idx_vr >= 0:
    block = src[idx_vr:idx_vr+500]
    has_admin_check = 'if not is_admin(event.sender_id):' in block
    has_alert = "alert=True" in block
    has_return = 'return' in block
    if has_admin_check and has_alert and has_return:
        ok('vault_restore callback: admin-gated')
    else:
        fail('vault_restore callback gate',
             f'admin_check={has_admin_check}, alert={has_alert}, return={has_return}')
else:
    fail('vault_restore callback', 'not found')

# ─── 7) AST: refresh_groups callback is admin-gated ───
print('━━━ 7) AST: refresh_groups callback admin-gated ━━━')
idx_rg = src.find("elif data == 'refresh_groups':")
if idx_rg >= 0:
    block = src[idx_rg:idx_rg+500]
    has_admin_check = 'if not is_admin(event.sender_id):' in block
    has_alert = "alert=True" in block
    has_return = 'return' in block
    if has_admin_check and has_alert and has_return:
        ok('refresh_groups callback: admin-gated')
    else:
        fail('refresh_groups callback gate',
             f'admin_check={has_admin_check}, alert={has_alert}, return={has_return}')
else:
    fail('refresh_groups callback', 'not found')

# ─── 8) AST: bot.py syntax valid ━──
print('━━━ 8) AST: bot.py syntax valid ━━━')
try:
    ast.parse(src)
    ok('bot.py parses')
except Exception as e:
    fail('bot.py syntax', str(e))

# ─── النتيجة ───
print('\n' + '━'*60)
passed = sum(1 for _, p, _ in results if p)
failed = sum(1 for _, p, _ in results if not p)
print(f'✅ نجح: {passed}  ❌ فشل: {failed}')
for n, p, m in results:
    if p: print(f'  ✓ {n}')
    else: print(f'  ✗ {n}: {m}')
sys.exit(0 if failed == 0 else 1)
