#!/usr/bin/env python3
"""Smoke test: simulate multiuser migration on an empty DB, then exercise key flows."""
import os
import sys
import sqlite3
import tempfile

# ضبط البيئة الأساسية
os.environ.setdefault('ADMIN_IDS', '123456789')
os.environ.setdefault('API_ID', '12345')
os.environ.setdefault('API_HASH', 'fakehash')
os.environ.setdefault('BOT_TOKEN', 'fake:token')

# استيراد multiuser بشكل مستقل
sys.path.insert(0, '/home/z/my-project')
import multiuser

# قاعدة بيانات مؤقتة
db_path = tempfile.mktemp(suffix='.db')

# محاكاة الجداول القديمة (قبل migration)
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute('CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)')
c.execute('''CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_string TEXT, phone TEXT, status TEXT DEFAULT 'active',
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
c.execute('''CREATE TABLE groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER, group_name TEXT, username TEXT, member_count INTEGER,
    added_by TEXT, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
c.execute('''CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT, media_path TEXT, msg_type TEXT DEFAULT 'text',
    media_data TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
c.execute('''CREATE TABLE scheduled_posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, message_id INTEGER,
    post_time TEXT NOT NULL, repeat_type TEXT DEFAULT 'once',
    repeat_interval INTEGER DEFAULT 0, post_mode TEXT DEFAULT 'fast',
    status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_run TEXT, next_run TEXT)''')
c.execute('''CREATE TABLE posting_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, account_id INTEGER, group_id INTEGER,
    message_id INTEGER, status TEXT, posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
c.execute('''CREATE TABLE join_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, group_id INTEGER, group_name TEXT,
    status TEXT, joined_by TEXT, joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
c.execute('''CREATE TABLE blacklist (
    group_id TEXT PRIMARY KEY, group_name TEXT, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

# بيانات قديمة
c.execute("INSERT INTO settings (key, value) VALUES ('fast_post_delay', '5')")
c.execute("INSERT INTO accounts (session_string, phone, status) VALUES ('sess1', '+9665', 'active')")
c.execute("INSERT INTO groups (group_id, group_name) VALUES (123, 'test_group')")
c.execute("INSERT INTO messages (content, msg_type) VALUES ('hi', 'text')")
conn.commit()
conn.close()

print('✅ Schema before migration built')

# Run migration
multiuser.migrate_to_multiuser(db_path, fallback_owner=123456789)
print('✅ Migration ran')

# Verify schema
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("PRAGMA table_info(accounts)")
cols = [r[1] for r in c.fetchall()]
assert 'owner_id' in cols, f'accounts missing owner_id: {cols}'
c.execute("PRAGMA table_info(groups)")
cols = [r[1] for r in c.fetchall()]
assert 'owner_id' in cols, f'groups missing owner_id: {cols}'
c.execute("PRAGMA table_info(settings)")
cols = [r[1] for r in c.fetchall()]
assert 'owner_id' in cols, f'settings missing owner_id: {cols}'
print('✅ owner_id columns added')

# Backfill check
c.execute("SELECT owner_id FROM accounts LIMIT 1")
assert c.fetchone()[0] == 123456789
c.execute("SELECT owner_id FROM settings WHERE key='fast_post_delay'")
assert c.fetchone()[0] == 123456789
print('✅ Backfill assigned to admin')

# Verify users table
c.execute("SELECT telegram_id, is_admin FROM users WHERE telegram_id=123456789")
r = c.fetchone()
assert r and r[1] == 1
print('✅ Admin registered in users table')
conn.close()

# Test user registration
u = multiuser.register_user(db_path, 987654321, 'testuser', 'Test', 'User')
assert u['telegram_id'] == 987654321
assert u['is_admin'] is False
assert u['is_banned'] is False
print(f'✅ Registered user: {u}')

# Test ban
multiuser.set_banned(db_path, 987654321, True)
assert multiuser.is_banned(db_path, 987654321) is True
assert multiuser.is_banned(db_path, 123456789) is False  # admin can't be banned
print('✅ Ban works (admin protected)')

# Test admin promotion
multiuser.set_admin(db_path, 987654321, True)
assert multiuser.is_user_admin(db_path, 987654321) is True
print('✅ Admin promotion works')

# Test current-user context
multiuser.set_current_user(987654321)
assert multiuser.get_current_user() == 987654321

# Test insert_account for current user
acc_id = multiuser.insert_account(db_path, 'sess2', '+9666', 'active')
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT owner_id FROM accounts WHERE id=?", (acc_id,))
assert c.fetchone()[0] == 987654321
print('✅ insert_account assigned to current user')
conn.close()

# Test insert_group + get_user_groups + export
multiuser.insert_group(db_path, 456, 'Group2', 'group2_username', 500, 'me')
g = multiuser.get_user_groups(db_path, 987654321)
assert len(g) >= 1
print(f'✅ get_user_groups returned {len(g)} groups')

txt = multiuser.export_user_groups_txt(db_path, 987654321)
assert 'Group2' in txt
assert 'group2_username' in txt
print(f'✅ export_user_groups_txt OK ({len(txt)} chars)')

# Test list_all_users
all_u = multiuser.list_all_users(db_path)
print(f'✅ list_all_users: {len(all_u)} users')
for u in all_u:
    print(f'  - {u["telegram_id"]} {u["first_name"]} @{u["username"]} admin={u["is_admin"]} ban={u["is_banned"]}')

# Test get_user_stats
st = multiuser.get_user_stats(db_path, 987654321)
print(f'✅ stats: {st}')

# Cleanup
os.remove(db_path)
print('\n🎉 جميع اختبارات multiuser نجحت!')
