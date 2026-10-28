#!/usr/bin/env python3
"""
v6.2 اختبار شامل للإصلاحات:
1) زر استيراد القروبات للأدمن فقط — لا يظهر للمستخدم العادي
2) إضافة الحساب الذي يشغّل البوت — إعادة توصيل تلقائي بدل "مضاف عندك بالفعل"
3) insert_account يحذف القديم بنفس الرقم+المستخدم
4) تنظيف user_clients قبل الإدراج
"""
import os, sys, sqlite3, asyncio, importlib.util, ast

ROOT = '/home/z/my-project'
sys.path.insert(0, ROOT)

# ──────────────── إعداد بيئة ────────────────
os.environ.setdefault('API_ID', '12345')
os.environ.setdefault('API_HASH', 'abcdef')
os.environ.setdefault('BOT_TOKEN', '123:abc')
os.environ.setdefault('ADMIN_IDS', '999999')

DB_PATH = '/tmp/test_v62.db'
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

results = []
def ok(name): results.append((name, True, ''))
def fail(name, msg): results.append((name, False, msg))

# ──────────────── 1) AST فحص: زر refresh_groups غير موجود في get_main_menu ────────────────
print('━━━ 1) AST: get_main_menu خالية من زر refresh_groups ━━━')
src = open(f'{ROOT}/bot.py').read()
tree = ast.parse(src)
ok_count = 0
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == 'get_main_menu':
        body_src = ast.get_source_segment(src, node)
        if 'refresh_groups' not in body_src:
            ok_count += 1
if ok_count == 1:
    ok('get_main_menu لا يحتوي على refresh_groups')
else:
    fail('get_main_menu refresh_groups count', f'expected 1 (one function with no refresh_groups), found {ok_count}')

# ──────────────── 2) AST فحص: مسار "already added" يتحقق من _ex_client is not None ────────────────
print('━━━ 2) AST: already-added path requires _ex_client is not None ━━━')
# ابحث عن النمط: if _ex_acc is not None and _ex_owner == event.sender_id:
#                  if _ex_client is not None:
pattern = 'if _ex_acc is not None and _ex_owner == event.sender_id:'
idx = src.find(pattern)
if idx >= 0:
    # ابحث بعد ذلك عن 'if _ex_client is not None:'
    after = src[idx:idx+500]
    if 'if _ex_client is not None:' in after:
        ok('already-added path checks _ex_client')
    else:
        fail('already-added path _ex_client check', 'no if _ex_client is not None after _ex_acc check')
else:
    fail('already-added pattern', 'pattern not found')

# ──────────────── 3) AST فحص: _reconnect_existing_account و _delete_accounts_for_phone_owner معرفتان ────────────────
print('━━━ 3) AST: helper functions defined ━━━')
defined_funcs = set()
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
        defined_funcs.add(node.name)
for fname in ['_reconnect_existing_account', '_delete_accounts_for_phone_owner',
              '_cleanup_user_clients_for_phone', '_find_live_client_for_phone']:
    if fname in defined_funcs:
        ok(f'function defined: {fname}')
    else:
        fail(f'function defined: {fname}', 'missing')

# ──────────────── 4) multiuser.insert_account يحذف القديم ────────────────
print('━━━ 4) multiuser.insert_account deletes old rows ━━━')
mu_src = open(f'{ROOT}/multiuser.py').read()
if 'DELETE FROM accounts WHERE phone=? AND owner_id=?' in mu_src:
    ok('insert_account deletes old rows')
else:
    fail('insert_account delete old rows', 'DELETE not found')

# ──────────────── 5) accounts menu لا يعرض refresh_groups للمستخدم العادي ────────────────
print('━━━ 5) accounts menu: refresh_groups admin-only ━━━')
# ابحث عن "elif data == 'accounts':" ثم افحص الكود التالي
idx_acc = src.find("elif data == 'accounts':")
if idx_acc < 0:
    fail('accounts menu', 'handler not found')
else:
    # ابحث عن حوالي 1500 حرف بعد
    block = src[idx_acc:idx_acc+2500]
    # يجب أن يحتوي على is_admin(event.sender_id) قبل _acc_buttons.insert
    if 'is_admin(event.sender_id)' in block and 'refresh_groups' in block:
        ok('accounts menu: refresh_groups gated by is_admin')
    else:
        fail('accounts menu gating', 'is_admin gate not found near refresh_groups insert')

# ──────────────── 6) refresh_groups callback handler يفحص is_admin ────────────────
print('━━━ 6) refresh_groups callback is_admin gated ━━━')
idx_rg = src.find("elif data == 'refresh_groups':")
if idx_rg < 0:
    fail('refresh_groups callback', 'handler not found')
else:
    block = src[idx_rg:idx_rg+500]
    if 'if not is_admin(event.sender_id):' in block and 'alert=True' in block:
        ok('refresh_groups callback is_admin gated')
    else:
        fail('refresh_groups callback gate', 'is_admin check or alert missing')

# ──────────────── 7) multiuser.insert_account حذف ثم إدراج (نمط atomic) ────────────────
print('━━━ 7) multiuser.insert_account: delete then insert ━━━')
mtree = ast.parse(mu_src)
for node in ast.walk(mtree):
    if isinstance(node, ast.FunctionDef) and node.name == 'insert_account':
        body = ast.get_source_segment(mu_src, node)
        # يجب أن يحتوي على c.execute("DELETE FROM accounts ... ثم c.execute('''INSERT INTO accounts
        if 'DELETE FROM accounts' in body and 'INSERT INTO accounts' in body:
            ok('insert_account: delete-then-insert pattern')
        else:
            fail('insert_account pattern', 'DELETE then INSERT not found')
        break

# ──────────────── 8) اختبار DB مباشر: حذف القديم يعمل ━━━
print('━━━ 8) DB test: insert_account deletes old rows ━━━')
try:
    import multiuser
    # إنشاء كل الجداول اللازمة قبل migrate
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_string TEXT, phone TEXT, status TEXT,
        owner_id INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
        group_id TEXT PRIMARY KEY, group_name TEXT, username TEXT,
        member_count INTEGER DEFAULT 0, added_by TEXT,
        owner_id INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT, media_path TEXT, msg_type TEXT, media_data TEXT,
        owner_id INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT, value TEXT, owner_id INTEGER DEFAULT 0,
        PRIMARY KEY (owner_id, key))''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY,
        username TEXT, first_name TEXT, last_name TEXT,
        is_banned INTEGER DEFAULT 0, is_admin INTEGER DEFAULT 0,
        notes TEXT, joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS scheduled_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER, post_time TEXT,
        repeat_type TEXT, repeat_interval INTEGER,
        post_mode TEXT, status TEXT, created_at TIMESTAMP,
        last_run TEXT, next_run TEXT, owner_id INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS posting_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id TEXT, group_name TEXT, status TEXT,
        posted_at TIMESTAMP, owner_id INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS join_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        link TEXT, group_id TEXT, group_name TEXT,
        status TEXT, joined_by TEXT, joined_at TIMESTAMP,
        owner_id INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS blacklist (
        group_id TEXT PRIMARY KEY, group_name TEXT,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        owner_id INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()
    multiuser.migrate_to_multiuser(DB_PATH, fallback_owner=0)
    from multiuser import insert_account, register_user, set_current_user
    register_user(DB_PATH, 100, 'u1', 'first', 'last')
    set_current_user(100)
    # إدراج أول
    acc1 = insert_account(DB_PATH, 'sess1', '+967730000001', 'active')
    # إدراج ثاني بنفس الرقم+المستخدم — يجب أن يحذف الأول
    acc2 = insert_account(DB_PATH, 'sess2', '+967730000001', 'active')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM accounts WHERE phone='+967730000001' AND owner_id=100")
    cnt = c.fetchone()[0]
    c.execute("SELECT session_string FROM accounts WHERE id=?", (acc2,))
    sess = c.fetchone()[0]
    conn.close()
    if cnt == 1 and acc1 != acc2 and sess == 'sess2':
        ok('insert_account: old row deleted, new row has new session')
    else:
        fail(f'insert_account: cnt={cnt}, acc1={acc1}, acc2={acc2}, sess={sess}', 'unexpected')
except Exception as e:
    fail('DB test', str(e))

# ──────────────── 9) اختبار: مستخدم مختلف بنفس الرقم — لا يجب أن يُحذف حسابه ━━━
print('━━━ 9) DB test: different owner keeps their account ━━━')
try:
    register_user(DB_PATH, 200, 'u2', 'first2', 'last2')
    set_current_user(200)
    acc_other = insert_account(DB_PATH, 'sess_other', '+967730000001', 'active')
    # حساب المستخدم 100 يجب أن يبقى
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM accounts WHERE phone='+967730000001'")
    cnt = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM accounts WHERE phone='+967730000001' AND owner_id=100")
    cnt_100 = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM accounts WHERE phone='+967730000001' AND owner_id=200")
    cnt_200 = c.fetchone()[0]
    conn.close()
    if cnt == 2 and cnt_100 == 1 and cnt_200 == 1:
        ok('different owner: keeps their account')
    else:
        fail(f'different owner: cnt={cnt}, cnt_100={cnt_100}, cnt_200={cnt_200}', 'unexpected')
except Exception as e:
    fail('different owner test', str(e))

# ──────────────── 10) اختبار: نفس المستخدم برقم مختلف — لا يجب أن يُحذف ━━━
print('━━━ 10) DB test: same user different phone keeps old account ━━━')
try:
    set_current_user(100)
    acc_diff = insert_account(DB_PATH, 'sess_diff', '+967730000002', 'active')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM accounts WHERE owner_id=100")
    cnt_100 = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM accounts WHERE owner_id=100 AND phone='+967730000001'")
    cnt_p1 = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM accounts WHERE owner_id=100 AND phone='+967730000002'")
    cnt_p2 = c.fetchone()[0]
    conn.close()
    if cnt_100 == 2 and cnt_p1 == 1 and cnt_p2 == 1:
        ok('same user different phone: both accounts kept')
    else:
        fail(f'same user diff phone: cnt_100={cnt_100}, p1={cnt_p1}, p2={cnt_p2}', 'unexpected')
except Exception as e:
    fail('same user diff phone test', str(e))

# ──────────────── النتيجة ━━━
print('\n' + '━'*60)
passed = sum(1 for _, p, _ in results if p)
failed = sum(1 for _, p, _ in results if not p)
print(f'✅ نجح: {passed}  ❌ فشل: {failed}')
for name, p, msg in results:
    if p:
        print(f'  ✓ {name}')
    else:
        print(f'  ✗ {name}: {msg}')
sys.exit(0 if failed == 0 else 1)
