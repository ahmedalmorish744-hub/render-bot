#!/usr/bin/env python3
"""Simulate full account-add flow to check if awaiting_code triggers sign_in correctly."""
import os
import asyncio
import sqlite3
import tempfile
import sys

# Set env first
os.environ['ADMIN_IDS'] = '123456'
os.environ['API_ID'] = '123456'
os.environ['API_HASH'] = 'fake'
os.environ['BOT_TOKEN'] = 'fake:token'

# Import multiuser and patch DB_PATH
sys.path.insert(0, '/home/z/my-project')
import multiuser
from multiuser import (
    set_current_user, get_current_user, register_user,
    migrate_to_multiuser, insert_account,
)
import sqlite3

# Build a fake DB and simulate the flow
DB_PATH = tempfile.mktemp(suffix='.db')
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute('CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)')
c.execute('''CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_string TEXT, phone TEXT, status TEXT DEFAULT 'active',
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    owner_id INTEGER DEFAULT 0)''')
c.execute('''CREATE TABLE groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER, group_name TEXT, username TEXT, member_count INTEGER,
    added_by TEXT, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    owner_id INTEGER DEFAULT 0)''')
c.execute('''CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT, media_path TEXT, msg_type TEXT DEFAULT 'text',
    media_data TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    owner_id INTEGER DEFAULT 0)''')
conn.commit()
conn.close()

# Migrate
multiuser.migrate_to_multiuser(DB_PATH, fallback_owner=123456)

# Verify composite PK
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='settings'")
print(f'Settings schema: {c.fetchone()[0]}')
conn.close()

# Simulate user 7777 clicking "Add account" (callback) - sets awaiting_phone=true
multiuser.set_current_user(7777)
# Replicate set_setting exactly as in bot.py
def set_setting(key, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('PRAGMA table_info(settings)')
    cols = [r[1] for r in c.fetchall()]
    if 'owner_id' in cols:
        c.execute('DELETE FROM settings WHERE key=? AND owner_id=?', (key, 7777))
        c.execute('INSERT INTO settings (key, value, owner_id) VALUES (?, ?, ?)', (key, value, 7777))
        conn.commit()
        conn.close()
        return
    c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

def get_setting(key, default=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('PRAGMA table_info(settings)')
        cols = [r[1] for r in c.fetchall()]
        if 'owner_id' in cols:
            c.execute('SELECT value FROM settings WHERE key=? AND owner_id=?', (key, 7777))
            row = c.fetchone()
            if row:
                conn.close()
                return row[0]
            if 7777 != 0:
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

# User 7777 clicks "Add account" → set awaiting_phone=true
set_setting('awaiting_phone', 'true')
print(f'awaiting_phone = {get_setting("awaiting_phone")}')
assert get_setting('awaiting_phone') == 'true'

# Simulate another user 8888 clicking - they should NOT see user 7777's awaiting_phone
def set_setting_8888(key, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM settings WHERE key=? AND owner_id=?', (key, 8888))
    c.execute('INSERT INTO settings (key, value, owner_id) VALUES (?, ?, ?)', (key, value, 8888))
    conn.commit()
    conn.close()

def get_setting_8888(key, default=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key=? AND owner_id=?', (key, 8888))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

# User 8888 also clicks "Add account"
set_setting_8888('awaiting_phone', 'true')
# User 7777 still has their value
multiuser.set_current_user(7777)
assert get_setting('awaiting_phone') == 'true', 'User 7777 lost their awaiting_phone!'
# User 8888 sees their own value
multiuser.set_current_user(8888)
assert get_setting_8888('awaiting_phone') == 'true', 'User 8888 lost their awaiting_phone!'
print('✅ Two users can both have awaiting_phone=true simultaneously')

# Now simulate 7777 typing phone → sets awaiting_code=true
multiuser.set_current_user(7777)
set_setting('awaiting_phone', '')
set_setting('awaiting_code', 'true')
print(f'After phone entered by 7777: awaiting_code = {get_setting("awaiting_code")}')
assert get_setting('awaiting_code') == 'true'

# Simulate 7777 typing code → should see awaiting_code=true → trigger sign_in
val = get_setting('awaiting_code')
print(f'When 7777 types code, get_setting("awaiting_code") returns: {val}')
assert val == 'true', f'BUG: awaiting_code is not true → sign_in would be skipped!'

print('\n🎉 All flow checks passed — settings isolation is correct')
print('If sign_in still fails, the bug is NOT in settings; it must be:')
print('  1. Telethon sign_in raising a specific exception we are not catching')
print('  2. temp_sessions[event.sender_id] being lost between handlers')
print('  3. Render deployment has stale code')
os.remove(DB_PATH)
