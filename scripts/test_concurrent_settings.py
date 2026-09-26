#!/usr/bin/env python3
"""Test that per-user settings isolation works (v5.2 fix)."""
import asyncio
import os
import sys
import tempfile
import sqlite3

sys.path.insert(0, '/home/z/my-project')
import multiuser

DB_PATH = ''

def _set(key, value, owner_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('PRAGMA table_info(settings)')
    cols = [r[1] for r in c.fetchall()]
    if 'owner_id' in cols:
        c.execute('DELETE FROM settings WHERE key=? AND owner_id=?', (key, owner_id))
        c.execute('INSERT INTO settings (key, value, owner_id) VALUES (?, ?, ?)', (key, value, owner_id))
        conn.commit()
        conn.close()
        return
    c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

def _get(key, default=None, owner_id=0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('PRAGMA table_info(settings)')
        cols = [r[1] for r in c.fetchall()]
        if 'owner_id' in cols:
            c.execute('SELECT value FROM settings WHERE key=? AND owner_id=?', (key, owner_id))
            row = c.fetchone()
            if row:
                conn.close()
                return row[0]
            if owner_id != 0:
                c = conn.cursor()
                c.execute('SELECT value FROM settings WHERE key=? AND owner_id=0', (key,))
                row = c.fetchone()
                conn.close()
                if row:
                    return row[0]
            conn.close()
            return default
    except Exception:
        pass
    c.execute('SELECT value FROM settings WHERE key=?', (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default


async def test_concurrent_isolation():
    global DB_PATH
    DB_PATH = tempfile.mktemp(suffix='.db')
    conn = sqlite3.connect(DB_PATH)
    conn.execute('CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)')
    conn.commit()
    conn.close()
    multiuser.migrate_to_multiuser(DB_PATH, fallback_owner=0)

    # Verify PRIMARY KEY is now (owner_id, key)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='settings'")
    sql = c.fetchone()[0]
    print(f'Settings schema: {sql}')
    assert 'PRIMARY KEY ("owner_id", "key")' in sql, 'PRIMARY KEY not composite!'
    conn.close()
    print('✅ PRIMARY KEY is composite (owner_id, key)')

    _set('_pending_phone', '+9665A', owner_id=111)
    _set('_pending_phone', '+9665B', owner_id=222)

    a_val = _get('_pending_phone', owner_id=111)
    b_val = _get('_pending_phone', owner_id=222)
    print(f'User A pending_phone: {a_val}')
    print(f'User B pending_phone: {b_val}')
    assert a_val == '+9665A', f'User A got {a_val}'
    assert b_val == '+9665B', f'User B got {b_val}'
    print('✅ Each user has their own _pending_phone — isolation works!')

    _set('fast_post_delay', '5', owner_id=0)
    u333_val = _get('fast_post_delay', default='3', owner_id=333)
    assert u333_val == '5', f'User 333 got {u333_val} (expected 5)'
    print(f'✅ User 333 reads global default: fast_post_delay={u333_val}')

    _set('fast_post_delay', '10', owner_id=333)
    u333_val = _get('fast_post_delay', default='3', owner_id=333)
    assert u333_val == '10', f'User 333 got {u333_val} (expected 10)'
    print(f'✅ User 333 sets own: fast_post_delay={u333_val}')

    u444_val = _get('fast_post_delay', default='3', owner_id=444)
    assert u444_val == '5', f'User 444 got {u444_val} (expected 5)'
    print(f'✅ User 444 still reads global: fast_post_delay={u444_val}')

    os.remove(DB_PATH)
    print('\n🎉 All isolation tests passed!')


asyncio.run(test_concurrent_isolation())
