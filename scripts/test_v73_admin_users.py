#!/usr/bin/env python3
"""اختبار v7.3: ميزات الأدمن الجديدة — عدد المستخدمين + استيراد قروبات مستخدم."""
import os, sys, ast
sys.path.insert(0, '/home/z/my-project')

results = []
def ok(n): results.append((n, True, ''))
def fail(n, m): results.append((n, False, m))

src = open('/home/z/my-project/bot.py').read()

# ─── 1) AST: زر "عدد المستخدمين" موجود في لوحة الأدمن ───
print('━━━ 1) AST: admin_users_count button in admin panel ━━━')
if "admin_users_count" in src and "Button.inline(\"👥 عدد المستخدمين (تفصيل)\"" in src:
    ok('admin_users_count button registered')
else:
    fail('admin_users_count button', 'not found')

# ─── 2) AST: معالج admin_users_count موجود ───
print('━━━ 2) AST: admin_users_count handler ━━━')
if "elif data == 'admin_users_count':" in src:
    ok('admin_users_count handler registered')
else:
    fail('admin_users_count handler', 'not found')

# ─── 3) AST: معالج admin_users_count يعرض تفاصيل (إجمالي/نشط/محظور/أدمن) ───
print('━━━ 3) AST: admin_users_count shows detailed stats ━━━')
idx = src.find("elif data == 'admin_users_count':")
if idx > 0:
    block = src[idx:idx+2500]
    required_strings = [
        'الإجمالي',  # total
        'نشطون',     # active
        'محظورون',   # banned
        'أدمنز',     # admins
        'بالحسابات', # users_with_accounts
        'بالقروبات', # users_with_groups
        'نشط آخر 24h',  # active_24h
    ]
    missing = [s for s in required_strings if s not in block]
    if not missing:
        ok('admin_users_count shows all detailed stats')
    else:
        fail('admin_users_count detail', f'missing: {missing}')
else:
    fail('admin_users_count handler', 'not found')

# ─── 4) AST: زر "استيراد قروبات مستخدم" موجود ───
print('━━━ 4) AST: admin_import_picker button ━━━')
if "admin_import_picker" in src and "Button.inline(\"📥 استيراد قروبات مستخدم\"" in src:
    ok('admin_import_picker button registered')
else:
    fail('admin_import_picker button', 'not found')

# ─── 5) AST: معالج admin_import_picker موجود ───
print('━━━ 5) AST: admin_import_picker handler ━━━')
if "elif data == 'admin_import_picker':" in src:
    ok('admin_import_picker handler registered')
else:
    fail('admin_import_picker handler', 'not found')

# ─── 6) AST: معالج admin_import_<uid> موجود ───
print('━━━ 6) AST: admin_import_<uid> handler ━━━')
if "elif data.startswith('admin_import_'):" in src:
    ok('admin_import_<uid> handler registered')
else:
    fail('admin_import_<uid> handler', 'not found')

# ─── 7) AST: معالج admin_import يقرأ session_string من DB ───
print('━━━ 7) AST: admin_import reads session_string from DB ━━━')
idx_import = src.find("elif data.startswith('admin_import_'):")
if idx_import > 0:
    block = src[idx_import:idx_import+5000]
    has_session_read = "SELECT session_string FROM accounts WHERE id=?" in block
    has_telethon_client = "TelegramClient(StringSession" in block
    has_owner_param = "_silent_import_all_groups(acc['id'], client, owner_id=target_uid)" in block
    if has_session_read and has_telethon_client and has_owner_param:
        ok('admin_import: reads session_string + connects + imports with owner_id')
    else:
        fail('admin_import logic',
             f'session_read={has_session_read}, telethon={has_telethon_client}, owner_param={has_owner_param}')
else:
    fail('admin_import handler', 'not found')

# ─── 8) AST: زر "استيراد قروباته الآن" في ملف المستخدم ───
print('━━━ 8) AST: import button in user profile ━━━')
idx_user = src.find("elif data.startswith('admin_user_'):")
if idx_user > 0:
    block = src[idx_user:idx_user+3000]
    # The button text uses .encode() in the source — we search for the f-string
    has_import_button = 'admin_import_{target_uid}' in block
    if has_import_button:
        ok('import button in user profile')
    else:
        fail('import button in user profile', 'not found')
else:
    fail('admin_user handler', 'not found')

# ─── 9) AST: زر "عرض قروباته" في ملف المستخدم ───
print('━━━ 9) AST: list_groups button in user profile ━━━')
if 'admin_list_groups_{target_uid}' in src:
    ok('list_groups button in user profile')
else:
    fail('list_groups button', 'not found')

# ─── 10) AST: معالج admin_list_groups_<uid> ───
print('━━━ 10) AST: admin_list_groups_<uid> handler ━━━')
if "elif data.startswith('admin_list_groups_'):" in src:
    ok('admin_list_groups_<uid> handler registered')
else:
    fail('admin_list_groups_<uid> handler', 'not found')

# ─── 11) AST: _silent_import_all_groups يقبل owner_id ───
print('━━━ 11) AST: _silent_import_all_groups accepts owner_id ━━━')
sig_match = "_silent_import_all_groups(acc_id, client, owner_id=None)"
if sig_match in src:
    ok('_silent_import_all_groups accepts owner_id param')
else:
    fail('_silent_import_all_groups signature', 'owner_id param missing')

# ─── 12) AST: لوحة الأدمن الرئيسية تحتوي الأزرار الجديدة ───
print('━━━ 12) AST: admin panel has all new buttons ━━━')
idx_panel = src.find("elif data == 'admin_panel':")
if idx_panel > 0:
    block = src[idx_panel:idx_panel+2500]
    required_buttons = [
        'admin_users_count',
        'admin_users_list',
        'admin_global_stats',
        'admin_import_picker',
        'admin_export_groups',
    ]
    missing = [b for b in required_buttons if b not in block]
    if not missing:
        ok('admin panel: all 5 admin buttons present')
    else:
        fail('admin panel buttons', f'missing: {missing}')
else:
    fail('admin panel handler', 'not found')

# ─── 13) AST: لوحة الأدمن تعرض عدد الحسابات النشطة ───
print('━━━ 13) AST: admin panel shows active accounts count ━━━')
idx_panel = src.find("elif data == 'admin_panel':")
if idx_panel > 0:
    block = src[idx_panel:idx_panel+2500]
    if "total_acc_active" in block and "نشط:" in block:
        ok('admin panel shows active accounts count')
    else:
        fail('admin panel active acc count', 'missing')
else:
    fail('admin panel', 'not found')

# ─── 14) AST: bot.py syntax valid ───
print('━━━ 14) AST: bot.py syntax valid ━━━')
try:
    ast.parse(src)
    ok('bot.py parses')
except Exception as e:
    fail('bot.py syntax', str(e))

# ─── 15) Functional test: _silent_import_all_groups accepts owner_id ───
print('━━━ 15) Functional: _silent_import_all_groups signature ━━━')
try:
    import inspect
    # Extract just the function source
    fn_start = src.find('async def _silent_import_all_groups(')
    fn_end = src.find('\nasync def ', fn_start + 10)
    if fn_end < 0:
        fn_end = src.find('\ndef ', fn_start + 10)
    fn_src = src[fn_start:fn_end]
    # Verify it accepts owner_id keyword arg
    if 'owner_id=None' in fn_src.split('\n')[0:3][0] + ''.join(fn_src.split('\n')[0:3][1:3]):
        ok('_silent_import_all_groups signature has owner_id=None')
    else:
        # Check the first ~500 chars
        if 'owner_id=None' in fn_src[:500]:
            ok('_silent_import_all_groups has owner_id param')
        else:
            fail('_silent_import_all_groups sig', f'no owner_id in: {fn_src[:300]}')
except Exception as e:
    fail('signature check', str(e))

# ─── النتيجة ───
print('\n' + '━'*60)
passed = sum(1 for _, p, _ in results if p)
failed = sum(1 for _, p, _ in results if not p)
print(f'✅ نجح: {passed}  ❌ فشل: {failed}')
for n, p, m in results:
    if p: print(f'  ✓ {n}')
    else: print(f'  ✗ {n}: {m}')
sys.exit(0 if failed == 0 else 1)
