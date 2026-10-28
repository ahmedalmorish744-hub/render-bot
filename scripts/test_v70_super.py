#!/usr/bin/env python3
"""اختبار v7.0 SUPER: التحقق من التكامل بين bot.py و super_engine.py.
1) bot.py يستورد super_engine بأمان
2) أوامر /super /warmup /health مسجلة
3) معالجات الـ callbacks (super_*, suwarm_*) موجودة
4) init_db يهيّئ المحرك السوبر
5) migration يضيف الأعمدة الجديدة لـ accounts
6) لا توجد تعارضات مع v5.4
"""
import os, sys, ast, re

ROOT = '/home/z/my-project'
sys.path.insert(0, ROOT)
os.environ.setdefault('API_ID', '12345')
os.environ.setdefault('API_HASH', 'abcdef')
os.environ.setdefault('BOT_TOKEN', '123:abc')
os.environ.setdefault('ADMIN_IDS', '999999')

results = []
def ok(n): results.append((n, True, ''))
def fail(n, m): results.append((n, False, m))

# ───────────── 1) AST فحص: bot.py يستورد super_engine ─────────────
print('━━━ 1) AST: bot.py imports super_engine ━━━')
src = open(f'{ROOT}/bot.py').read()
if 'import super_engine' in src or 'from super_engine' in src:
    ok('bot.py imports super_engine')
else:
    fail('import super_engine', 'not found')

# ───────────── 2) AST فحص: _super_engine_inst معرّف ─────────────
print('━━━ 2) AST: _super_engine_inst global ━━━')
if '_super_engine_inst' in src and 'global _super_engine_inst' in src:
    ok('_super_engine_inst global declared')
else:
    fail('_super_engine_inst', 'global declaration missing')

# ───────────── 3) AST فحص: أوامر /super /warmup /health مسجلة ─────────────
print('━━━ 3) AST: /super /warmup /health handlers ━━━')
patterns = [
    "events.NewMessage(pattern='/super')",
    "events.NewMessage(pattern='/warmup')",
    "events.NewMessage(pattern='/health')",
]
for p in patterns:
    if p in src:
        ok(f'handler for {p.split("/")[-1].strip("\'")}')
    else:
        fail(f'handler {p}', 'not found')

# ───────────── 4) AST فحص: callback handlers super_* موجودة ─────────────
print('━━━ 4) AST: super callback handlers ━━━')
callbacks = [
    'super_panel',
    'super_warmup',
    'super_health',
    'super_warmup_all',
    'suwarm_',
    'super_toggle_warmup',
    'super_toggle_pace',
    'super_warmup_settings',
    'super_pace_settings',
]
for cb in callbacks:
    if cb in src:
        ok(f'callback {cb}')
    else:
        fail(f'callback {cb}', 'missing')

# ───────────── 5) AST فحص: init_db تهيّئ المحرك السوبر ─────────────
print('━━━ 5) AST: init_db initializes super engine ━━━')
if 'init_super_engine(' in src and 'migrate_super_engine_schema(' in src:
    ok('init_db calls init_super_engine + migrate_super_engine_schema')
else:
    fail('init_db super init', 'calls missing')

# ───────────── 6) AST فحص: بناء bot.py صالح ─────────────
print('━━━ 6) AST: bot.py syntax valid ━━━')
try:
    ast.parse(src)
    ok('bot.py parses')
except Exception as e:
    fail('bot.py syntax', str(e))

# ───────────── 7) AST فحص: super_engine.py بناء صالح ─────────────
print('━━━ 7) AST: super_engine.py syntax valid ━━━')
try:
    ast.parse(open(f'{ROOT}/super_engine.py').read())
    ok('super_engine.py parses')
except Exception as e:
    fail('super_engine.py syntax', str(e))

# ───────────── 8) استيراد فعلي: super_engine ─────────────
print('━━━ 8) Import: super_engine ━━━')
try:
    import super_engine as se
    ok(f'super_engine imports: {len(dir(se))} names')
    # كل الكلاسات الأساسية موجودة
    for cls in ['AccountWarmup', 'AccountHealthMonitor', 'PaceScheduler',
                'SpintaxBatchExpander', 'RecipientTracker', 'AutoPauseManager',
                'SmartAccountSelector', 'init_super_engine', 'migrate_super_engine_schema']:
        assert hasattr(se, cls), f'missing: {cls}'
    ok(f'super_engine classes: {len([c for c in dir(se) if not c.startswith("_")])}')
except Exception as e:
    fail('super_engine import', str(e))

# ───────────── 9) اختبار: init_db على قاعدة بيانات حقيقية ━━━
print('━━━ 9) Test: init_db integration ━━━')
import tempfile, sqlite3
tmpdb = tempfile.NamedTemporaryFile(suffix='.db', delete=False).name
os.environ['DB_PATH'] = tmpdb
try:
    # نستورد bot AFTER setting DB_PATH
    import bot
    # init_db يضيف migration
    bot.init_db()
    # تحقق أن الأعمدة الجديدة موجودة في accounts
    conn = sqlite3.connect(tmpdb)
    c = conn.cursor()
    cols = [r[1] for r in c.execute('PRAGMA table_info(accounts)').fetchall()]
    expected = ['warmup_messages_sent', 'warmup_target_messages', 'last_activity',
                'error_message', 'success_count', 'failure_count']
    for col in expected:
        if col in cols:
            ok(f'column {col} added')
        else:
            fail(f'column {col}', f'not in {cols}')
    conn.close()
    # تحقق أن _super_engine_inst ليس None
    if bot._super_engine_inst is not None:
        ok(f'_super_engine_inst initialized: {len(bot._super_engine_inst)} components')
    else:
        fail('_super_engine_inst', 'is None — init failed')
except Exception as e:
    import traceback; traceback.print_exc()
    fail('init_db integration', str(e))
finally:
    try: os.unlink(tmpdb)
    except: pass

# ───────────── 10) اختبار: لا تكسر أوامر v5.4 ━━━
print('━━━ 10) Verify: v5.4 commands still registered ━━━')
v54_commands = ['/start', '/debug', '/test', '/set_mode', '/get_mode',
                '/encrypt', '/check', '/fast_post']
for cmd in v54_commands:
    if cmd in src:
        ok(f'command {cmd} still present')
    else:
        fail(f'command {cmd}', 'MISSING — v5.4 broken')

# ───────────── النتيجة ─────────────
print('\n' + '━'*60)
passed = sum(1 for _, p, _ in results if p)
failed = sum(1 for _, p, _ in results if not p)
print(f'✅ نجح: {passed}  ❌ فشل: {failed}')
for n, p, m in results:
    if p: print(f'  ✓ {n}')
    else: print(f'  ✗ {n}: {m}')
sys.exit(0 if failed == 0 else 1)
