# -*- coding: utf-8 -*-
"""
multiuser.py - نظام تعدد المستخدمين والإدارة
================================================
يوفّر:
  • عزل كامل لكل مستخدم (حسابات/قروبات/رسائل/إعدادات/جدولة/تاريخ)
  • مصادقة الأدمن (ADMIN_IDS من البيئة + جدول users)
  • لوحة أدمن: قائمة المستخدمين، إحصائيات لكل مستخدم، حظر/رفع حظر
  • استيراد قروبات أي مستخدم + تصديرها ملف txt
  • migration تلقائي لإضافة owner_id لكل الجداول القائمة

كل الدوال thread-safe عبر SQLite connection-per-call.
"""
import os
import re
import sqlite3
import logging
from contextvars import ContextVar
from datetime import datetime

logger = logging.getLogger(__name__)

# ─── سياق المستخدم الحالي (يُضبط عند دخول أي handler) ───
CURRENT_USER: ContextVar[int] = ContextVar('CURRENT_USER', default=0)

def set_current_user(uid: int) -> None:
    """ضبط سياق المستخدم الحالي - يُستدعى في بداية كل handler"""
    CURRENT_USER.set(int(uid) if uid else 0)

def get_current_user() -> int:
    """قراءة معرّف المستخدم الحالي من السياق"""
    return CURRENT_USER.get()

# ─── الأدمن من البيئة ───
ADMIN_IDS_RAW = os.environ.get('ADMIN_IDS', os.environ.get('ADMIN_ID', ''))
ENV_ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(',') if x.strip().isdigit()]


def env_admin_ids() -> list:
    """قائمة الأدمن من متغيرات البيئة (دائمين)"""
    return list(ENV_ADMIN_IDS)


# ═══════════════════════════════════════════════════════════
#  Migration - إضافة owner_id + جدول users
# ═══════════════════════════════════════════════════════════

def migrate_to_multiuser(db_path: str, fallback_owner: int = 0) -> None:
    """migration آمن: إضافة owner_id لكل الجداول + إنشاء جدول users + backfill"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # 1) جدول المستخدمين
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        telegram_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        is_banned INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0,
        notes TEXT,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_seen TIMESTAMP
    )''')

    # 2) إضافة owner_id لكل جدول (إذا لم يكن موجوداً)
    # نتعامل مع جميع الجداول المعروفة
    for table in ['accounts', 'groups', 'messages', 'scheduled_posts',
                  'posting_history', 'join_history', 'blacklist']:
        try:
            c.execute(f'PRAGMA table_info({table})')
            cols = [row[1] for row in c.fetchall()]
            if 'owner_id' not in cols:
                c.execute(f'ALTER TABLE {table} ADD COLUMN owner_id INTEGER DEFAULT 0')
        except Exception:
            pass  # الجدول قد لا يكون موجوداً بعد (يُنشأ لاحقاً)

    # 3) إعداد الأدمن البيئي كمالك افتراضي (backfill)
    if fallback_owner:
        # backfill: كل الصفوف بـ owner_id=0 تُسند للأدمن البيئي
        for table in ['accounts', 'groups', 'messages', 'scheduled_posts',
                      'posting_history', 'join_history', 'blacklist']:
            try:
                c.execute(f'UPDATE {table} SET owner_id=? WHERE owner_id=0 OR owner_id IS NULL',
                          (fallback_owner,))
            except Exception:
                pass
        # تسجيل الأدمن البيئي في جدول users
        c.execute('''INSERT OR IGNORE INTO users (telegram_id, is_admin, joined_at, last_seen)
                     VALUES (?, 1, ?, ?)''',
                  (fallback_owner, datetime.now().isoformat(), datetime.now().isoformat()))

    # 4) settings: نقل من PRIMARY KEY (key) إلى (owner_id, key)
    #    🔧 v5.2: ضرورة فصل المفتاح per-user — لو بقي PRIMARY KEY على (key) فقط،
    #    مستخدمون مختلفون لا يمكنهم امتلاك نفس الإعداد (مثل _pending_phone)،
    #    ويصير آخر مستخدم يكتب يحذف إعداد الآخر!
    c.execute('PRAGMA table_info(settings)')
    settings_cols = [row[1] for row in c.fetchall()]
    if 'owner_id' not in settings_cols:
        c.execute('ALTER TABLE settings ADD COLUMN owner_id INTEGER DEFAULT 0')
        if fallback_owner:
            c.execute('UPDATE settings SET owner_id=? WHERE owner_id=0 OR owner_id IS NULL',
                      (fallback_owner,))

    # 🔧 v5.2: إعادة بناء الجدول بـ composite PRIMARY KEY (owner_id, key)
    # بدون هذا، INSERT OR REPLACE على key='fast_post_delay' من مستخدم B
    # يكتب فوق إعداد مستخدم A.
    try:
        c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='settings'")
        sql_row = c.fetchone()
        if sql_row:
            create_sql = sql_row[0] or ''
            # اكتشاف الجداول القديمة بـ PRIMARY KEY على (key) فقط (وليس على (owner_id, key))
            # نقبل صياغتين: "PRIMARY KEY (key)" و "key TEXT PRIMARY KEY"
            needs_rebuild = ('PRIMARY KEY (owner_id, key)' not in create_sql
                             and 'PRIMARY KEY ("owner_id", "key")' not in create_sql)
            if needs_rebuild:
                # جلب كل الأعمدة + أنواعها
                c.execute('PRAGMA table_info(settings)')
                cols_info = c.fetchall()
                col_defs = []
                col_names = []
                for r in cols_info:
                    col_name = r[1]
                    col_type = r[2] or 'TEXT'
                    # إزالة أي "PRIMARY KEY" مضمّن في type (مثل "TEXT PRIMARY KEY")
                    col_type_clean = re.sub(r'\s+PRIMARY\s+KEY', '', col_type, flags=re.IGNORECASE)
                    col_defs.append(f'"{col_name}" {col_type_clean}')
                    col_names.append(col_name)
                # نسخ الجدول إلى جدول مؤقت
                c.execute('ALTER TABLE settings RENAME TO settings_old_v52')
                cols_def_str = ', '.join(col_defs)
                c.execute(f'CREATE TABLE settings ({cols_def_str}, PRIMARY KEY ("owner_id", "key"))')
                # نسخ البيانات
                cols_list = ', '.join(f'"{n}"' for n in col_names)
                c.execute(f'INSERT INTO settings ({cols_list}) SELECT {cols_list} FROM settings_old_v52')
                c.execute('DROP TABLE settings_old_v52')
                logger.info("✅ v5.2: settings PRIMARY KEY = (owner_id, key)")
            else:
                try:
                    c.execute('CREATE INDEX IF NOT EXISTS idx_settings_owner_key ON settings (owner_id, key)')
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"⚠️ v5.2: تعذّر إعادة بناء جدول settings ({e}) — قد تحدث تعارضات بين المستخدمين")

    conn.commit()
    conn.close()


# ═══════════════════════════════════════════════════════════
#  تسجيل المستخدمين
# ═══════════════════════════════════════════════════════════

def register_user(db_path: str, telegram_id: int, username: str = '',
                   first_name: str = '', last_name: str = '') -> dict:
    """تسجيل/تحديث مستخدم. يُرجع row dict."""
    tid = int(telegram_id)
    is_admin_flag = 1 if tid in ENV_ADMIN_IDS else 0
    now = datetime.now().isoformat()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO users (telegram_id, username, first_name, last_name,
                  is_admin, joined_at, last_seen)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (tid, username or '', first_name or '', last_name or '', is_admin_flag, now, now))
    # تحديث آخر رؤية + البيانات (دون لمس is_banned/is_admin إن لم تكن من البيئة)
    c.execute('''UPDATE users SET last_seen=?, username=COALESCE(NULLIF(?, ''), username),
                 first_name=COALESCE(NULLIF(?, ''), first_name),
                 last_name=COALESCE(NULLIF(?, ''), last_name),
                 is_admin=? WHERE telegram_id=?''',
              (now, username or '', first_name or '', last_name or '', is_admin_flag, tid))
    c.execute('SELECT telegram_id, username, first_name, last_name, is_banned, is_admin, joined_at, last_seen FROM users WHERE telegram_id=?', (tid,))
    row = c.fetchone()
    conn.commit()
    conn.close()
    if not row:
        return {}
    return {
        'telegram_id': row[0], 'username': row[1], 'first_name': row[2], 'last_name': row[3],
        'is_banned': bool(row[4]), 'is_admin': bool(row[5]) or tid in ENV_ADMIN_IDS,
        'joined_at': row[6], 'last_seen': row[7]
    }


def is_banned(db_path: str, telegram_id: int) -> bool:
    """هل المستخدم محظور؟ 🛡️ متسامح مع خطأ."""
    tid = int(telegram_id)
    if tid in ENV_ADMIN_IDS:
        return False  # الأدمن لا يُحظر
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'")
        if not c.fetchone():
            conn.close()
            return False
        c.execute('SELECT is_banned FROM users WHERE telegram_id=?', (tid,))
        row = c.fetchone()
        conn.close()
        return bool(row and row[0])
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return False


def is_user_admin(db_path: str, telegram_id: int) -> bool:
    """هل المستخدم أدمن؟ (بيئة أو جدول).
    🛡️ v5.3.3: متسامح مع خطأ - يرجع True/False بدل رفع exception لو الجدول غير جاهز."""
    tid = int(telegram_id)
    if tid in ENV_ADMIN_IDS:
        return True
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        # تحقق من وجود جدول users
        c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'")
        if not c.fetchone():
            conn.close()
            return False
        c.execute('SELECT is_admin FROM users WHERE telegram_id=?', (tid,))
        row = c.fetchone()
        conn.close()
        return bool(row and row[0])
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return False


def set_banned(db_path: str, telegram_id: int, banned: bool) -> None:
    """حظر/رفع حظر مستخدم (لا يؤثر على أدمن البيئة)"""
    tid = int(telegram_id)
    if tid in ENV_ADMIN_IDS:
        return  # لا يمكن حظر أدمن البيئة
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    # إن لم يكن مسجلاً أصلاً، نسجله أولاً
    c.execute('INSERT OR IGNORE INTO users (telegram_id, joined_at, last_seen) VALUES (?, ?, ?)',
              (tid, datetime.now().isoformat(), datetime.now().isoformat()))
    c.execute('UPDATE users SET is_banned=? WHERE telegram_id=?', (1 if banned else 0, tid))
    conn.commit()
    conn.close()


def set_admin(db_path: str, telegram_id: int, is_admin_flag: bool) -> None:
    """ترقية/تنزيل مستخدم لأدمن"""
    tid = int(telegram_id)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (telegram_id, joined_at, last_seen) VALUES (?, ?, ?)',
              (tid, datetime.now().isoformat(), datetime.now().isoformat()))
    c.execute('UPDATE users SET is_admin=? WHERE telegram_id=?', (1 if is_admin_flag else 0, tid))
    conn.commit()
    conn.close()


def list_all_users(db_path: str, limit: int = 500) -> list:
    """قائمة كل المستخدمين (للأدمن)"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''SELECT telegram_id, username, first_name, last_name, is_banned, is_admin, joined_at, last_seen
                 FROM users ORDER BY joined_at DESC LIMIT ?''', (limit,))
    rows = c.fetchall()
    conn.close()
    return [{
        'telegram_id': r[0], 'username': r[1] or '', 'first_name': r[2] or '',
        'last_name': r[3] or '', 'is_banned': bool(r[4]), 'is_admin': bool(r[5]),
        'joined_at': r[6], 'last_seen': r[7]
    } for r in rows]


def get_user_stats(db_path: str, telegram_id: int) -> dict:
    """إحصائيات مستخدم (حسابات، قروبات، رسائل، جدولة، منشورات)"""
    tid = int(telegram_id)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    stats = {'accounts': 0, 'active_accounts': 0, 'groups': 0, 'messages': 0,
             'scheduled': 0, 'posts_sent': 0, 'joins': 0}
    try:
        c.execute('SELECT COUNT(*) FROM accounts WHERE owner_id=?', (tid,))
        stats['accounts'] = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM accounts WHERE owner_id=? AND status='active'", (tid,))
        stats['active_accounts'] = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM groups WHERE owner_id=?', (tid,))
        stats['groups'] = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM messages WHERE owner_id=?', (tid,))
        stats['messages'] = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM scheduled_posts WHERE owner_id=? AND status='pending'", (tid,))
        stats['scheduled'] = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM posting_history WHERE owner_id=?', (tid,))
        stats['posts_sent'] = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM join_history WHERE owner_id=?', (tid,))
        stats['joins'] = c.fetchone()[0]
    except Exception:
        pass
    conn.close()
    return stats


def get_user_accounts(db_path: str, telegram_id: int) -> list:
    """كل حسابات مستخدم (للأدمن)"""
    tid = int(telegram_id)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT id, phone, status, added_at FROM accounts WHERE owner_id=? ORDER BY id DESC', (tid,))
    rows = c.fetchall()
    conn.close()
    return [{'id': r[0], 'phone': r[1], 'status': r[2], 'added_at': r[3]} for r in rows]


def get_user_groups(db_path: str, telegram_id: int, limit: int = 10000) -> list:
    """كل قروبات مستخدم"""
    tid = int(telegram_id)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''SELECT group_id, group_name, username, member_count, added_by
                 FROM groups WHERE owner_id=? ORDER BY member_count DESC NULLS LAST LIMIT ?''', (tid, limit))
    rows = c.fetchall()
    conn.close()
    return [{'group_id': r[0], 'group_name': r[1] or '', 'username': r[2] or '',
             'member_count': r[3] or 0, 'added_by': r[4] or ''} for r in rows]


def export_user_groups_txt(db_path: str, telegram_id: int) -> str:
    """تصدير قروبات مستخدم كنص txt (للإرسال كملف)"""
    tid = int(telegram_id)
    groups = get_user_groups(db_path, tid)
    user_info = register_user(db_path, tid)  # للحصول على الاسم
    header = (f"# قروبات المستخدم: {user_info.get('first_name','')} "
              f"(@{user_info.get('username','') or '—'}) [ID: {tid}]\n"
              f"# تاريخ التصدير: {datetime.now().isoformat()}\n"
              f"# إجمالي القروبات: {len(groups)}\n"
              f"{'='*60}\n\n")
    lines = [header]
    for i, g in enumerate(groups, 1):
        gid = g['group_id']
        gname = g['group_name']
        uname = g['username']
        members = g.get('member_count') or 0
        # صياغة سطر واحد لكل قروب
        link = f"https://t.me/{uname}" if uname else f"(private id:{gid})"
        lines.append(f"{i:04d}. {gname}\n")
        lines.append(f"      الرابط: {link}\n")
        lines.append(f"      ID: {gid} | الأعضاء: {members}\n\n")
    return ''.join(lines)


def get_accounts_for_current(db_path: str) -> list:
    """الحسابات النشطة للمستخدم الحالي فقط"""
    uid = get_current_user()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id FROM accounts WHERE status='active' AND owner_id=?", (uid,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_groups_for_current(db_path: str) -> list:
    """القروبات للمستخدم الحالي فقط"""
    uid = get_current_user()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT group_id, group_name, username, member_count FROM groups WHERE owner_id=?', (uid,))
    rows = c.fetchall()
    conn.close()
    return rows


def count_groups_for_current(db_path: str) -> int:
    uid = get_current_user()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM groups WHERE owner_id=?', (uid,))
    n = c.fetchone()[0]
    conn.close()
    return n


def count_messages_for_current(db_path: str) -> int:
    uid = get_current_user()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM messages WHERE owner_id=?', (uid,))
    n = c.fetchone()[0]
    conn.close()
    return n


def insert_account(db_path: str, session_string: str, phone: str, status: str = 'active') -> int:
    """إضافة حساب مرتبط بالمستخدم الحالي"""
    uid = get_current_user()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''INSERT INTO accounts (session_string, phone, status, owner_id)
                 VALUES (?, ?, ?, ?)''', (session_string, phone, status, uid))
    conn.commit()
    acc_id = c.lastrowid
    conn.close()
    return acc_id


def insert_group(db_path: str, group_id: int, group_name: str,
                 username: str = None, member_count: int = 0,
                 added_by: str = '') -> None:
    """إضافة قروب مرتبط بالمستخدم الحالي"""
    uid = get_current_user()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO groups (group_id, group_name, username, member_count, added_by, owner_id)
                 VALUES (?, ?, ?, ?, ?, ?)''',
              (group_id, (group_name or '')[:100], username, member_count, added_by, uid))
    conn.commit()
    conn.close()


def insert_message(db_path: str, content, media_path, msg_type, media_data=None) -> int:
    """إضافة رسالة مرتبطة بالمستخدم الحالي"""
    uid = get_current_user()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('''INSERT INTO messages (content, media_path, msg_type, media_data, owner_id)
                 VALUES (?, ?, ?, ?, ?)''', (content, media_path, msg_type, media_data, uid))
    conn.commit()
    mid = c.lastrowid
    conn.close()
    return mid


def delete_account(db_path: str, acc_id: int) -> bool:
    """حذف حساب (للمستخدم الحالي فقط)"""
    uid = get_current_user()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('DELETE FROM accounts WHERE id=? AND owner_id=?', (acc_id, uid))
    conn.commit()
    deleted = c.rowcount > 0
    conn.close()
    return deleted


def get_messages_for_current(db_path: str, limit: int = 100) -> list:
    """رسائل المستخدم الحالي فقط"""
    uid = get_current_user()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT id, content, media_path, msg_type, media_data FROM messages WHERE owner_id=? LIMIT ?',
              (uid, limit))
    rows = c.fetchall()
    conn.close()
    return rows


def get_message_by_id_for_current(db_path: str, msg_id: int):
    """رسالة محددة للمستخدم الحالي فقط أو None"""
    uid = get_current_user()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute('SELECT id, content, media_path, msg_type, media_data FROM messages WHERE id=? AND owner_id=?',
              (msg_id, uid))
    row = c.fetchone()
    conn.close()
    return row


# ─── Session restore helpers (per-user) ───

def get_active_sessions_for_current(db_path: str) -> list:
    """كل جلسات المستخدم الحالي النشطة (للاستعادة عند الإقلاع)"""
    uid = get_current_user()
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, session_string, phone FROM accounts WHERE status='active' AND owner_id=?", (uid,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_all_active_sessions_grouped(db_path: str) -> dict:
    """كل الجلسات النشطة مجمّعة حسب owner_id (للإقلاع) - {owner_id: [(acc_id, session, phone), ...]}"""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        c.execute('''SELECT id, session_string, phone, owner_id FROM accounts
                     WHERE status='active' ORDER BY owner_id''')
        rows = c.fetchall()
    except Exception:
        rows = []
    conn.close()
    out = {}
    for acc_id, sess, phone, owner in rows:
        out.setdefault(owner or 0, []).append((acc_id, sess, phone))
    return out
