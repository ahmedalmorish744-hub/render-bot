#!/usr/bin/env python3
"""اختبارات شاملة لـ super_engine.py — كل المكونات الستة."""
import os, sys, sqlite3, asyncio, random
sys.path.insert(0, '/home/z/my-project')

results = []
def ok(n): results.append((n, True, ''))
def fail(n, m): results.append((n, False, m))

from super_engine import (
    AccountWarmup, AccountHealthMonitor, PaceScheduler,
    SpintaxBatchExpander, RecipientTracker, AutoPauseManager,
    SmartAccountSelector, init_super_engine, migrate_super_engine_schema
)

# ───────────── 1) SpintaxBatchExpander ─────────────
print('━━━ 1) SpintaxBatchExpander ━━━')
try:
    sx = SpintaxBatchExpander()
    # توسيع 5 نسخ مختلفة لنفس النص
    text = '{مرحباً|أهلاً|سلام} بكم في {قناتنا|مجموعتنا|موقعنا}'
    out = sx.expand(text, 5)
    assert len(out) == 5, f'expected 5, got {len(out)}'
    # كل نسخة يجب أن لا تحتوي على { أو }
    bad = [t for t in out if '{' in t or '}' in t]
    assert not bad, f'unresolved braces: {bad}'
    # تنوع على الأقل نسختين مختلفتين (احتمالياً)
    unique = len(set(out))
    assert unique >= 2, f'expected >=2 unique, got {unique}: {out}'
    ok(f'spintax expand: {unique} unique of 5')

    # عدد المتغيرات = 3 × 3 = 9
    n = sx.count_variants(text)
    assert n == 9, f'expected 9 variants, got {n}'
    ok(f'spintax count_variants: {n}')

    # Spintax متداخل
    nested = '{{مرحبا|أهلا}|سلام}'
    out2 = sx.expand(nested, 10)
    flat = set(out2)
    assert 'مرحبا' in flat or 'أهلا' in flat or 'سلام' in flat, f'nested failed: {out2}'
    ok(f'spintax nested: {flat}')

    # نص بدون spintax يعود كما هو
    out3 = sx.expand('نص عادي بلا spintax', 3)
    assert out3 == ['نص عادي بلا spintax'] * 3, f'expected same: {out3}'
    ok('spintax no-pattern: returns same')

    # نص فارغ
    out4 = sx.expand('', 3)
    assert out4 == [''] * 3
    ok('spintax empty')
except Exception as e:
    import traceback
    traceback.print_exc()
    fail('SpintaxBatchExpander', str(e))

# ───────────── 2) RecipientTracker ─────────────
print('━━━ 2) RecipientTracker ━━━')
try:
    tr = RecipientTracker()
    tr.start_session('s1')
    assert not tr.is_sent('s1', 100)
    tr.mark_sent('s1', 100)
    assert tr.is_sent('s1', 100)
    assert not tr.is_sent('s1', 200)
    assert tr.count_sent('s1') == 1
    tr.mark_sent('s1', 200)
    assert tr.count_sent('s1') == 2
    # جلسة ثانية لا تتعارض
    assert not tr.is_sent('s2', 100)
    tr.start_session('s2')
    assert not tr.is_sent('s2', 100)
    tr.clear('s1')
    assert tr.count_sent('s1') == 0
    ok('RecipientTracker basic flow')
except Exception as e:
    fail('RecipientTracker', str(e))

# ───────────── 3) AutoPauseManager ─────────────
print('━━━ 3) AutoPauseManager ━━━')
try:
    settings = {'auto_pause_error_threshold': '50', 'auto_pause_min_attempts': '5',
                'auto_pause_cooldown_seconds': '10'}
    gs = lambda k, d=None: settings.get(k, d)
    ap = AutoPauseManager(gs)
    # أقل من الحد الأدنى من المحاولات → لا
    should, _ = ap.should_pause(1, 3, 3)
    assert not should, 'should not pause (too few attempts)'
    # 5 محاولات، 4 أخطاء = 80% > 50% → نعم
    should, reason = ap.should_pause(1, 5, 4)
    assert should, f'should pause: {reason}'
    assert '80.0%' in reason or '80%' in reason
    ok(f'AutoPause trigger: {reason}')
    # مرة ثانية مباشرة → في cooldown → لا
    should, why = ap.should_pause(1, 10, 8)
    assert not should, f'should be in cooldown, got {should} {why}'
    ok(f'AutoPause cooldown: {why}')
except Exception as e:
    fail('AutoPauseManager', str(e))

# ───────────── 4) PaceScheduler ─────────────
print('━━━ 4) PaceScheduler ━━━')
try:
    settings = {'pace_messages_per_minute': '6', 'pace_messages_per_hour': '20',
                'pace_max_concurrent': '1', 'pace_jitter_seconds': '0'}
    gs = lambda k, d=None: settings.get(k, d)
    ps = PaceScheduler(gs)
    # 10 رسائل على حسابين
    sched = ps.build_pace_schedule(10, [1, 2])
    assert len(sched) == 10, f'expected 10, got {len(sched)}'
    # كل slot له wait_before_ms و account_id
    for slot in sched:
        assert 'wait_before_ms' in slot
        assert 'account_id' in slot
        assert slot['account_id'] in [1, 2]
    # الحسابان يجب أن يُستخدما على الأقل مرة واحدة (round-robin)
    used_accounts = set(s['account_id'] for s in sched)
    assert used_accounts == {1, 2}, f'both accounts must be used: {used_accounts}'
    ok(f'PaceScheduler: {len(sched)} slots on 2 accounts')

    # 0 رسالة → قائمة فارغة
    sched0 = ps.build_pace_schedule(0, [1, 2])
    assert sched0 == []
    ok('PaceScheduler zero messages')

    # بدون حسابات → قائمة فارغة
    sched1 = ps.build_pace_schedule(10, [])
    assert sched1 == []
    ok('PaceScheduler no accounts')
except Exception as e:
    import traceback; traceback.print_exc()
    fail('PaceScheduler', str(e))

# ───────────── 5) AccountHealthMonitor ─────────────
print('━━━ 5) AccountHealthMonitor ━━━')
try:
    # قاعدة بيانات اختبار
    DB = '/tmp/test_super_engine.db'
    if os.path.exists(DB):
        os.remove(DB)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE accounts (
        id INTEGER PRIMARY KEY, session_string TEXT, phone TEXT, status TEXT,
        owner_id INTEGER DEFAULT 0, warmup_messages_sent INTEGER DEFAULT 0,
        last_activity TEXT, error_message TEXT, success_count INTEGER DEFAULT 0,
        failure_count INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE posting_history (
        id INTEGER PRIMARY KEY, account_id INTEGER, group_id TEXT, group_name TEXT,
        status TEXT, posted_at TIMESTAMP, owner_id INTEGER DEFAULT 0)''')
    # إدراج 10 إرسالات ناجحة + 2 فاشلة
    from datetime import datetime
    now_iso = datetime.utcnow().isoformat()
    for i in range(10):
        c.execute("INSERT INTO posting_history (account_id, group_id, status, posted_at) VALUES (1, 'g1', 'success', ?)", (now_iso,))
    for i in range(2):
        c.execute("INSERT INTO posting_history (account_id, group_id, status, posted_at) VALUES (1, 'g1', 'fail', ?)", (now_iso,))
    conn.commit()
    conn.close()

    settings = {'warmup_enabled': 'off'}
    gs = lambda k, d=None: settings.get(k, d)
    hm = AccountHealthMonitor(DB, gs)
    # حساب ممتاز: 100% success rate, آخر نشاط الآن, لا أخطاء
    info_good = {
        'status': 'active', 'success_rate': 100.0,
        'last_activity': now_iso, 'warmup_complete': True,
        'error_message': None,
    }
    r = hm.score_account(1, info_good)
    assert r['score'] >= 90, f'expected >=90, got {r["score"]}'
    assert r['health_status'] == 'EXCELLENT'
    ok(f'health EXCELLENT: score={r["score"]}, status={r["health_status"]}')

    # حساب سيئ: 30% success rate, لا نشاط, خطأ
    info_bad = {
        'status': 'active', 'success_rate': 30.0,
        'last_activity': None, 'warmup_complete': False,
        'error_message': 'FloodWaitError',
    }
    r2 = hm.score_account(1, info_bad)
    assert r2['score'] < 60, f'expected <60, got {r2["score"]}'
    assert r2['health_status'] in ('WARNING', 'CRITICAL'), r2['health_status']
    ok(f'health CRITICAL: score={r2["score"]}, status={r2["health_status"]}')

    # حساب غير نشط → OFFLINE
    info_offline = {'status': 'expired', 'success_rate': 100.0}
    r3 = hm.score_account(1, info_offline)
    assert r3['health_status'] == 'OFFLINE'
    ok('health OFFLINE for non-active')

    # حساب مع أخطاء 24h (هذا من قاعدة البيانات) + success_rate = 70 (< 80)
    info_recent = {
        'status': 'active', 'success_rate': 70.0,
        'last_activity': now_iso, 'warmup_complete': True,
        'error_message': None,
    }
    r4 = hm.score_account(1, info_recent)
    # 12 محاولة, 2 فشل → error_rate ~16.7% > 10% → -10
    # 70% success_rate → -15
    # النتيجة: 100 - 15 - 10 = 75 (WARNING)
    assert r4['score'] <= 80, f'expected <=80, got {r4["score"]}'
    ok(f'health with 24h errors: score={r4["score"]}, status={r4["health_status"]}')
except Exception as e:
    import traceback; traceback.print_exc()
    fail('AccountHealthMonitor', str(e))

# ───────────── 6) AccountWarmup (state only, no real send) ─────────────
print('━━━ 6) AccountWarmup ━━━')
try:
    DB = '/tmp/test_super_engine_warmup.db'
    if os.path.exists(DB):
        os.remove(DB)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE accounts (
        id INTEGER PRIMARY KEY, phone TEXT, status TEXT,
        warmup_messages_sent INTEGER DEFAULT 0, last_activity TEXT)''')
    c.execute("INSERT INTO accounts (id, phone, status, warmup_messages_sent) VALUES (1, '+9671', 'active', 0)")
    conn.commit()
    conn.close()

    settings = {'warmup_enabled': 'on', 'warmup_target_messages': '3',
                'warmup_interval_minutes': '1', 'warmup_ui_interval_seconds': '1'}
    gs = lambda k, d=None: settings.get(k, d)
    ss = lambda k, v: settings.update({k: v})
    aw = AccountWarmup(DB, gs, ss)
    # الحالة الأولية: 0/3, not complete, not in progress
    st = aw.status(1)
    assert st['sent'] == 0, f'expected 0, got {st["sent"]}'
    assert not st['complete']
    assert not st['in_progress']
    ok(f'warmup initial: {st}')

    # محاكاة إرسال واحد فقط (لا نرسل فعلاً لـ 'me' في الاختبار)
    # نختبر is_complete + status logic فقط
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("UPDATE accounts SET warmup_messages_sent=3 WHERE id=1")
    conn.commit()
    conn.close()
    st2 = aw.status(1)
    assert st2['sent'] == 3, f'expected 3, got {st2["sent"]}'
    assert st2['complete']
    ok(f'warmup complete: {st2}')
except Exception as e:
    import traceback; traceback.print_exc()
    fail('AccountWarmup', str(e))

# ───────────── 7) migrate_super_engine_schema ─────────────
print('━━━ 7) migrate_super_engine_schema ━━━')
try:
    DB = '/tmp/test_super_migration.db'
    if os.path.exists(DB):
        os.remove(DB)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    # جدول accounts قديم بدون الأعمدة الجديدة
    c.execute('''CREATE TABLE accounts (
        id INTEGER PRIMARY KEY, phone TEXT, status TEXT, owner_id INTEGER)''')
    c.execute("INSERT INTO accounts (id, phone, status, owner_id) VALUES (1, '+9671', 'active', 100)")
    conn.commit()
    conn.close()
    migrate_super_engine_schema(DB)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    cols = [row[1] for row in c.execute('PRAGMA table_info(accounts)').fetchall()]
    expected = ['warmup_messages_sent', 'warmup_target_messages', 'last_activity',
                'error_message', 'success_count', 'failure_count']
    for col in expected:
        assert col in cols, f'missing column: {col}, got: {cols}'
    # التحقق أن الصف القديم محفوظ
    c.execute('SELECT phone, status FROM accounts WHERE id=1')
    row = c.fetchone()
    assert row == ('+9671', 'active')
    conn.close()
    ok(f'migration: added {len(expected)} columns, old row preserved')
except Exception as e:
    import traceback; traceback.print_exc()
    fail('migrate_super_engine_schema', str(e))

# ───────────── 8) init_super_engine ─────────────
print('━━━ 8) init_super_engine ━━━')
try:
    DB = '/tmp/test_super_init.db'
    if os.path.exists(DB):
        os.remove(DB)
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE accounts (
        id INTEGER PRIMARY KEY, phone TEXT, status TEXT, owner_id INTEGER)''')
    conn.commit()
    conn.close()
    settings = {}
    gs = lambda k, d=None: settings.get(k, d)
    ss = lambda k, v: settings.update({k: v})
    engine = init_super_engine(DB, gs, ss, lambda: [], lambda: {})
    assert 'warmup' in engine
    assert 'health' in engine
    assert 'pace' in engine
    assert 'spintax_batch' in engine
    assert 'tracker' in engine
    assert 'auto_pause' in engine
    assert 'selector' in engine
    ok(f'init_super_engine: {len(engine)} components')
except Exception as e:
    fail('init_super_engine', str(e))

# ───────────── النتيجة ─────────────
print('\n' + '━'*60)
passed = sum(1 for _, p, _ in results if p)
failed = sum(1 for _, p, _ in results if not p)
print(f'✅ نجح: {passed}  ❌ فشل: {failed}')
for n, p, m in results:
    if p: print(f'  ✓ {n}')
    else: print(f'  ✗ {n}: {m}')
sys.exit(0 if failed == 0 else 1)
