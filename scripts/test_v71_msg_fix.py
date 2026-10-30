#!/usr/bin/env python3
"""اختبار v7.1: التحقق من إصلاح bug get_setting + bulletproof add_msg."""
import os, sys, sqlite3, tempfile
sys.path.insert(0, '/home/z/my-project')

results = []
def ok(n): results.append((n, True, ''))
def fail(n, m): results.append((n, False, m))

# ─── 1) get_setting fallback صحيح ───
print('━━━ 1) get_setting fallback to owner_id=0 ━━━')
try:
    import bot
    DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False).name
    os.environ['DB_PATH'] = DB
    bot.DB_PATH = DB
    bot.init_db()
    # التحقق: get_setting لمفتاح غير موجود يرجع default
    val = bot.get_setting('nonexistent_key_xyz', 'default_value')
    assert val == 'default_value', f'expected default_value, got {val}'
    ok('get_setting returns default for nonexistent key')
    # التحقق: set ثم get round-trip للمستخدم 0
    bot.set_setting('test_key', 'test_value_for_user_0')
    val2 = bot.get_setting('test_key')
    assert val2 == 'test_value_for_user_0', f'expected test_value_for_user_0, got {val2}'
    ok('get_setting returns the set value')
    # التحقق: مستخدم آخر لا يرى إعداد مستخدم 0
    val3 = bot.get_setting('test_key', owner_id=100, default='NONE')
    assert val3 == 'test_value_for_user_0', f'expected fallback to owner=0 (val_for_0), got {val3}'
    ok('get_setting fallback to owner_id=0 works (the bug we fixed)')
    # التحقق: لو set للمستخدم 100، get يقرأه (لا fallback)
    bot.set_setting('test_key', 'val_for_100', owner_id=100)
    val4 = bot.get_setting('test_key', owner_id=100)
    assert val4 == 'val_for_100', f'expected val_for_100, got {val4}'
    ok('get_setting scoped (no fallback when row exists)')
    # التحقق: مفتاح غير موجود لأي مستخدم
    val5 = bot.get_setting('nonexistent_for_owner_500', owner_id=500, default='NOPE')
    assert val5 == 'NOPE', f'expected NOPE, got {val5}'
    ok('get_setting default for nonexistent (no row for any owner)')
except Exception as e:
    import traceback; traceback.print_exc()
    fail('get_setting fallback', str(e))
finally:
    try: os.unlink(DB)
    except: pass

# ─── 2) set_setting ثم get_setting round-trip ───
print('━━━ 2) set/get round-trip ━━━')
try:
    DB = tempfile.NamedTemporaryFile(suffix='.db', delete=False).name
    bot.DB_PATH = DB
    bot.init_db()
    # اختبار مع owner_id صريح
    bot.set_setting('awaiting_msg', 'true', owner_id=99999)
    val = bot.get_setting('awaiting_msg', owner_id=99999)
    assert val == 'true', f'expected true, got {val}'
    ok('awaiting_msg round-trip with explicit owner_id')
    # عند الإلغاء، يجب أن نرى ''
    bot.set_setting('awaiting_msg', '', owner_id=99999)
    val2 = bot.get_setting('awaiting_msg', owner_id=99999)
    assert val2 == '', f'expected empty, got {val2}'
    ok('awaiting_msg cleared properly')
    # مستخدم آخر لا يرى إعداد مستخدم 99999
    val3 = bot.get_setting('awaiting_msg', owner_id=88888, default='no_value')
    # fallback to owner_id=0 → ''  (because we set it to '' above for user 99999)
    # actually owner_id=0 wasn't set, so should return 'no_value'
    assert val3 == 'no_value', f'expected no_value for owner 88888, got {val3}'
    ok('user isolation: other users see their own value')
except Exception as e:
    import traceback; traceback.print_exc()
    fail('set/get round-trip', str(e))
finally:
    try: os.unlink(DB)
    except: pass

# ─── 3) أمر /add و /addmsg و /new موجودة ───
print('━━━ 3) AST: /add /addmsg /new commands ━━━')
import ast
src = open('/home/z/my-project/bot.py').read()
for cmd in ['/add', '/addmsg', '/new']:
    pattern_str = f"events.NewMessage(pattern='{cmd}')"
    if pattern_str in src:
        ok(f'command {cmd} registered')
    else:
        fail(f'command {cmd}', 'not registered')

# ─── 4) cancel_add_msg_cmd handler موجودة ───
print('━━━ 4) AST: cancel_add_msg_cmd callback ━━━')
if "elif data == 'cancel_add_msg_cmd'" in src:
    ok('cancel_add_msg_cmd callback present')
else:
    fail('cancel_add_msg_cmd', 'missing')

# ─── 5) add_msg callback يضع set_setting أولاً ───
print('━━━ 5) AST: add_msg callback sets awaiting_msg before event.edit ━━━')
# نبحث عن النمط: set_setting('awaiting_msg', 'true') قبل await event.edit
idx = src.find("elif data == 'add_msg':")
if idx > 0:
    block = src[idx:idx+1000]
    set_pos = block.find("set_setting('awaiting_msg', 'true')")
    edit_pos = block.find("await event.edit")
    if set_pos > 0 and edit_pos > 0 and set_pos < edit_pos:
        ok('add_msg: set_setting before event.edit (bulletproof)')
    else:
        fail('add_msg order', f'set_pos={set_pos}, edit_pos={edit_pos}')
else:
    fail('add_msg callback', 'not found')

# ─── 6) get_setting لا يستخدم cursor بعد conn.close() في المسار الأساسي ───
print('━━━ 6) AST: no cursor-after-close bug in get_setting main path ━━━')
# فحص المسار الأساسي (scoped): لا يجب أن نرى conn.close() ثم c = conn.cursor()
# (المسار القديم يعيد فتح conn — هذا ليس مشكلة)
gs_start = src.find('def get_setting(')
gs_end = src.find('def set_setting(')
gs_block = src[gs_start:gs_end]
main_path_start = gs_block.find("if 'owner_id' in cols:")
main_path_end = gs_block.find("except Exception as _inner_e:")
main_path = gs_block[main_path_start:main_path_end]
bad_pattern_count = 0
lines = main_path.split('\n')
for i, line in enumerate(lines):
    if 'conn.close()' in line:
        for j in range(i+1, min(i+10, len(lines))):
            if 'c = conn.cursor()' in lines[j]:
                bad_pattern_count += 1
                break
            if 'return ' in lines[j] or 'def ' in lines[j]:
                break
if bad_pattern_count == 0:
    ok('get_setting main path: no cursor-after-close bug')
else:
    fail('get_setting cursor-after-close', f'{bad_pattern_count} occurrences in main path')

# ─── النتيجة ───
print('\n' + '━'*60)
passed = sum(1 for _, p, _ in results if p)
failed = sum(1 for _, p, _ in results if not p)
print(f'✅ نجح: {passed}  ❌ فشل: {failed}')
for n, p, m in results:
    if p: print(f'  ✓ {n}')
    else: print(f'  ✗ {n}: {m}')
sys.exit(0 if failed == 0 else 1)
