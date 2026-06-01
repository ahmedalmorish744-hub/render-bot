#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔═══════════════════════════════════════════════════════════════╗
║     🤖 بوت النشر الخارق - نسخة الحماية القصوى 🛡️             ║
║     متجاوز لجميع بوتات الحماية + نشر سريع + جدولة ⚡📅       ║
╚═══════════════════════════════════════════════════════════════╝
"""

import os
import re
import json
import time
import random
import sqlite3
import asyncio
import logging
import urllib.request
from threading import Thread
from datetime import datetime, timedelta
from collections import deque

from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, FloodWaitError, PhoneCodeInvalidError, PhoneCodeExpiredError
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import InputMediaContact, Chat, Channel
from flask import Flask, jsonify

# ═══════════════════════════════════════════════
#  الإعدادات الأساسية
# ═══════════════════════════════════════════════
API_ID = int(os.environ.get('API_ID', '0'))
API_HASH = os.environ.get('API_HASH', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
PORT = int(os.environ.get('PORT', '10000'))

ADMIN_IDS_RAW = os.environ.get('ADMIN_IDS', os.environ.get('ADMIN_ID', '0'))
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(',') if x.strip().isdigit()]

def is_admin(user_id):
    return user_id in ADMIN_IDS

if not ADMIN_IDS:
    logging.error("⚠️ يجب تعيين ADMIN_IDS أو ADMIN_ID في متغيرات البيئة")
    exit(1)

if not all([API_ID, API_HASH, BOT_TOKEN]):
    logging.error("⚠️ يجب تعيين API_ID, API_HASH, BOT_TOKEN")
    exit(1)

# ═══════════════════════════════════════════════
#  إعداد السجلات
# ═══════════════════════════════════════════════
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════
#  المتغيرات العامة (يجب أن تكون قبل أي دالة تستخدمها)
# ═══════════════════════════════════════════════
user_clients = {}
temp_sessions = {}
is_posting_active = False
is_joining_active = False
scheduled_tasks = {}  # {schedule_id: asyncio.Task}

# ═══════════════════════════════════════════════
#  قاعدة البيانات
# ═══════════════════════════════════════════════
DB_PATH = os.environ.get('DB_PATH', 'bot_database.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT, media_path TEXT, msg_type TEXT DEFAULT 'text',
        media_data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_string TEXT, phone TEXT,
        status TEXT DEFAULT 'active',
        cooldown_until TIMESTAMP DEFAULT NULL,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER, group_name TEXT,
        username TEXT, member_count INTEGER,
        is_protected INTEGER DEFAULT 0,
        added_by TEXT,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS posting_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER, group_id INTEGER,
        message_id INTEGER, status TEXT,
        posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS join_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        link TEXT, group_id INTEGER, group_name TEXT,
        status TEXT, joined_by TEXT,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS protected_groups_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER, group_name TEXT,
        bot_name TEXT, detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS blacklist (
        group_id TEXT PRIMARY KEY,
        group_name TEXT,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS scheduled_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER,
        post_time TEXT NOT NULL,
        repeat_type TEXT DEFAULT 'once',
        repeat_interval INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_run TEXT DEFAULT NULL)''')

    if get_setting('fast_post_delay') is None:
        set_setting('fast_post_delay', '3')
    if get_setting('message_interval') is None:
        set_setting('message_interval', '3')
    if get_setting('join_interval') is None:
        set_setting('join_interval', '100')
    if get_setting('encryption') is None:
        set_setting('encryption', 'on')
    if get_setting('anti_detect') is None:
        set_setting('anti_detect', 'on')
    if get_setting('use_jitter') is None:
        set_setting('use_jitter', 'on')
    if get_setting('bot_detection') is None:
        set_setting('bot_detection', 'on')
    if get_setting('obfuscation_enabled') is None:
        set_setting('obfuscation_enabled', 'on')

    conn.commit()
    conn.close()
    logger.info("✅ قاعدة البيانات جاهزة")

def get_setting(key, default=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT value FROM settings WHERE key=?', (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

# ═══════════════════════════════════════════════
#  Blacklist helper functions
# ═══════════════════════════════════════════════
def add_to_blacklist(group_id, group_name=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO blacklist (group_id, group_name, added_at) VALUES (?, ?, ?)',
              (str(group_id), group_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def remove_from_blacklist(group_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM blacklist WHERE group_id=?', (str(group_id),))
    conn.commit()
    conn.close()

def get_blacklisted_groups():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT group_id, group_name, added_at FROM blacklist ORDER BY added_at DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def is_group_blacklisted(group_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT 1 FROM blacklist WHERE group_id=?', (str(group_id),))
    row = c.fetchone()
    conn.close()
    return row is not None

# ═══════════════════════════════════════════════
#  Scheduled Posts helper functions
# ═══════════════════════════════════════════════
def add_scheduled_post(message_id, post_time, repeat_type='once', repeat_interval=0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO scheduled_posts (message_id, post_time, repeat_type, repeat_interval, status)
                 VALUES (?, ?, ?, ?, 'pending')''',
              (message_id, post_time, repeat_type, repeat_interval))
    conn.commit()
    sched_id = c.lastrowid
    conn.close()
    return sched_id

def get_pending_scheduled_posts():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, message_id, post_time, repeat_type, repeat_interval, last_run FROM scheduled_posts WHERE status='pending'")
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_scheduled_posts():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, message_id, post_time, repeat_type, repeat_interval, status, last_run FROM scheduled_posts ORDER BY post_time ASC")
    rows = c.fetchall()
    conn.close()
    return rows

def update_scheduled_post_status(sched_id, status, last_run=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if last_run:
        c.execute('UPDATE scheduled_posts SET status=?, last_run=? WHERE id=?', (status, last_run, sched_id))
    else:
        c.execute('UPDATE scheduled_posts SET status=? WHERE id=?', (status, sched_id))
    conn.commit()
    conn.close()

def delete_scheduled_post(sched_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM scheduled_posts WHERE id=?', (sched_id,))
    conn.commit()
    conn.close()
    # Cancel the task if running
    if sched_id in scheduled_tasks:
        try:
            scheduled_tasks[sched_id].cancel()
        except:
            pass
        del scheduled_tasks[sched_id]

# ═══════════════════════════════════════════════
#  Account cooldown functions
# ═══════════════════════════════════════════════
def set_account_cooldown(acc_id, until_timestamp):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE accounts SET cooldown_until=?, status=? WHERE id=?',
              (datetime.fromtimestamp(until_timestamp).isoformat(), 'cooldown', acc_id))
    conn.commit()
    conn.close()

def is_account_in_cooldown(acc_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT cooldown_until FROM accounts WHERE id=?', (acc_id,))
    row = c.fetchone()
    conn.close()
    if row and row[0]:
        try:
            cooldown = datetime.fromisoformat(row[0])
            if cooldown > datetime.now():
                return True, (cooldown - datetime.now()).total_seconds()
        except:
            pass
    return False, 0

def clear_all_cooldowns():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE accounts SET cooldown_until=NULL, status='active'")
    conn.commit()
    conn.close()
    logger.info("✅ تم مسح تبريد جميع الحسابات")

def log_protected_group(group_id, group_name, bot_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO protected_groups_log (group_id, group_name, bot_name) VALUES (?, ?, ?)',
              (group_id, group_name, bot_name))
    c.execute('UPDATE groups SET is_protected=1 WHERE group_id=?', (group_id,))
    conn.commit()
    conn.close()

def get_protected_groups():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT group_id, group_name, bot_name, detected_at FROM protected_groups_log ORDER BY detected_at DESC LIMIT 50")
    rows = c.fetchall()
    conn.close()
    return rows

# ═══════════════════════════════════════════════
#  خادم الويب
# ═══════════════════════════════════════════════
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "bot": "Super Poster Bot - Ultimate Protection + Fast Post + Scheduling",
        "uptime": datetime.now().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

def run_web():
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)

# ═══════════════════════════════════════════════
#  نظام الإبقاء على البوت نشطاً
# ═══════════════════════════════════════════════
async def keep_alive_ping():
    url = f"http://localhost:{PORT}/health"
    while True:
        try:
            urllib.request.urlopen(url, timeout=10)
            logger.info("🔄 [Keep Alive] البوت نشط")
        except Exception as e:
            logger.error(f"❌ [Keep Alive] خطأ: {e}")
        await asyncio.sleep(240)

# ═══════════════════════════════════════════════
#  نظام التشفير المتطور (نسخة محسنة - الحفاظ على المحتوى)
# ═══════════════════════════════════════════════
class UltimateAntiDetection:
    """
    نظام مكافحة الكشف المتطور - النسخة المحسنة
    
    المبدأ الأساسي: النص يبقى كما هو للمستخدم العادي
    التغييرات تكون غير مرئية للعين المجردة فقط:
    - أحرف غير مرئية بين الكلمات (ليس داخل الكلمات)
    - مسافات بديلة (non-breaking space, thin space) بدل المسافة العادية
    - حروف لاتينية متشابهة (homoglyphs) بنسبة منخفضة جداً
    - تشويش الروابط بأحرف غير مرئية فقط
    
    ما لا يتم فعله (لأنه يخرب المحتوى):
    - لا يتم استبدال الكلمات العربية بمرادفاتها
    - لا يتم تقسيم الكلمات العربية بأحرف غير مرئية
    - لا يتم إعادة ترتيب الكلمات
    - لا يتم إضافة ضوضاء عشوائية (أرقام/رموز)
    - لا يتم إضافة تشكيل عربي عشوائي
    - لا يتم عكس الكلمات بـ bidi control
    """
    def __init__(self):
        # Invisible characters that don't affect display
        self.invisible_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF']
        # Homoglyphs for Latin letters only (Cyrillic lookalikes)
        self.homoglyphs = {
            'a': '\u0430',  # а
            'e': '\u0435',  # е
            'o': '\u043E',  # о
            'c': '\u0441',  # с
            'p': '\u0440',  # р
            'x': '\u0445',  # х
            'i': '\u0456',  # і
            'j': '\u0458',  # ј
        }
        self.decorations = [
            ('✨', '✨'), ('🌟', '🌟'), ('⭐', '⭐'), ('💫', '💫'),
            ('✧', '✧'), ('✦', '✦'), ('❁', '❁'), ('✿', '✿'),
        ]
        self.sent_messages_cache = deque(maxlen=500)

    def obfuscate_links(self, text):
        """Obfuscate links with invisible chars only - link still works and looks the same."""
        # Add invisible char after t. in t.me links
        text = text.replace('t.me', 't\u200B.me')
        # Add invisible char in https://
        text = text.replace('https://', 'https:\u200C//')
        text = text.replace('http://', 'http:\u200D//')
        return text

    def obfuscate_mentions(self, text):
        """Add invisible char after @ in mentions."""
        def replace_mention(match):
            username = match.group(1)
            return '@\u200B' + username
        return re.sub(r'@([a-zA-Z0-9_]{3,})', replace_mention, text)

    def apply_homoglyphs(self, text, intensity=0.06):
        """
        Replace Latin letters with Cyrillic lookalikes at very low intensity.
        These look identical to the human eye but are different to machines.
        Only affects Latin letters, Arabic text is never touched.
        """
        result = []
        for char in text:
            if char in self.homoglyphs and random.random() < intensity:
                result.append(self.homoglyphs[char])
            else:
                result.append(char)
        return ''.join(result)

    def add_invisible_between_words(self, text, intensity=0.15):
        """
        Add invisible chars BETWEEN words only (never inside words).
        This preserves word integrity and readability completely.
        """
        if not text or len(text) < 5:
            return text
        # Find positions between words (after spaces)
        result = list(text)
        space_positions = [i for i, c in enumerate(result) if c == ' ']
        if not space_positions:
            return text
        # Add invisible char after some spaces
        insert_positions = []
        for pos in space_positions:
            if random.random() < intensity:
                insert_positions.append(pos + 1)  # After the space
        # Insert in reverse to preserve positions
        for pos in reversed(insert_positions):
            inv = random.choice(self.invisible_chars)
            result.insert(pos, inv)
        return ''.join(result)

    def replace_some_spaces(self, text, intensity=0.3):
        """
        Replace some normal spaces with alternative invisible spaces.
        Looks identical to the user but different to machines.
        """
        result = list(text)
        space_positions = [i for i, c in enumerate(result) if c == ' ']
        for pos in space_positions:
            if random.random() < intensity:
                replacement = random.choice(['\u00A0', '\u2009', '\u202F'])  # non-breaking, thin, narrow no-break
                result[pos] = replacement
        return ''.join(result)

    def add_decorations(self, text):
        """Add decorative emoji around text (only when encryption is on)."""
        if random.random() > 0.6 and len(text) < 200:
            left, right = random.choice(self.decorations)
            patterns = [
                f"{left} {text} {right}",
                f"{left}{left} {text} {right}{right}",
            ]
            return random.choice(patterns)
        return text

    def is_duplicate_message(self, text, group_id):
        cache_key = f"{group_id}:{hash(text)}"
        if cache_key in self.sent_messages_cache:
            return True
        self.sent_messages_cache.append(cache_key)
        return False

    def generate_ultimate_variation(self, text, group_id=None):
        """
        Generate variation that preserves content meaning and readability.
        All changes are invisible to the human eye - only machines can detect them.
        """
        if get_setting('anti_detect', 'on') != 'on':
            return text
        if group_id and self.is_duplicate_message(text, group_id):
            # Add invisible char to make hash different - invisible to user
            text = '\u200B' + text
        result = text
        # 1. Obfuscate links (invisible chars only)
        result = self.obfuscate_links(result)
        # 2. Obfuscate mentions (invisible char after @)
        result = self.obfuscate_mentions(result)
        # 3. Apply homoglyphs to Latin letters only (very low intensity)
        result = self.apply_homoglyphs(result, intensity=0.06)
        # 4. Replace some spaces with alternative spaces (invisible difference)
        result = self.replace_some_spaces(result, intensity=0.3)
        # 5. Add invisible chars between words (not inside words)
        result = self.add_invisible_between_words(result, intensity=0.15)
        # 6. Decorations (only if encryption is on)
        if get_setting('encryption', 'on') == 'on':
            result = self.add_decorations(result)
        return result

anti_detection = UltimateAntiDetection()

def encrypt_text(text, group_id=None):
    return anti_detection.generate_ultimate_variation(text, group_id)

# ═══════════════════════════════════════════════
#  Text variation and obfuscation functions
#  (نسخة محسنة - الحفاظ على المحتوى)
# ═══════════════════════════════════════════════

def vary_text(text):
    """
    Apply gentle, invisible variations to text before sending.
    Each message gets a unique fingerprint but content stays IDENTICAL to the reader.
    No word replacement, no word splitting, no reordering, no noise.
    """
    if not text:
        return text
    result = text

    # 1. Add an invisible char at the very beginning (invisible to reader)
    inv_char = random.choice(['\u200B', '\u200C', '\uFEFF'])
    result = inv_char + result

    # 2. Replace 1-2 regular spaces with non-breaking or thin spaces (invisible change)
    spaces = [i for i, c in enumerate(result) if c == ' ']
    if spaces:
        # Replace 1 or 2 spaces
        num_replace = min(random.randint(1, 2), len(spaces))
        chosen = random.sample(spaces, num_replace)
        for pos in chosen:
            replacement = random.choice(['\u00A0', '\u2009', '\u202F'])
            result = result[:pos] + replacement + result[pos+1:]

    # 3. Add invisible char between two random words (after a space, not inside a word)
    space_positions = [i for i, c in enumerate(result) if c in [' ', '\u00A0', '\u2009', '\u202F']]
    if space_positions and random.random() > 0.4:
        pos = random.choice(space_positions)
        inv = random.choice(['\u200B', '\u200C'])
        result = result[:pos+1] + inv + result[pos+1:]

    # 4. Swap one Latin letter with homoglyph (very rarely, invisible to reader)
    latin_chars = [i for i, c in enumerate(result) if c.isascii() and c.isalpha() and c.lower() in 'aecpxio']
    if latin_chars and random.random() > 0.5:
        pos = random.choice(latin_chars)
        c = result[pos]
        homoglyph_map = {
            'a': '\u0430', 'A': '\u0410',
            'e': '\u0435', 'E': '\u0415',
            'c': '\u0441', 'C': '\u0421',
            'p': '\u0440', 'P': '\u0420',
            'x': '\u0445', 'X': '\u0425',
            'o': '\u043E', 'O': '\u041E',
            'i': '\u0456',
        }
        if c in homoglyph_map:
            result = result[:pos] + homoglyph_map[c] + result[pos+1:]

    return result


def obfuscate_for_humans(text):
    """
    Apply human-INVISIBLE obfuscation techniques.
    The text looks EXACTLY the same to a human reader.
    Only machine analysis (hash comparison, char inspection) can detect the changes.
    
    Techniques used:
    1. Homoglyphs on Latin letters (looks identical)
    2. Invisible chars between words (not inside words)
    3. Alternative spaces (non-breaking, thin) instead of regular spaces
    4. Invisible char at beginning/end
    
    Techniques NOT used (because they corrupt content):
    - NO Arabic diacritics (changes pronunciation/meaning)
    - NO bidirectional control (breaks display)
    - NO keyword replacement (changes meaning)
    - NO word reordering (changes meaning)
    - NO random noise (changes content)
    """
    if not text:
        return text
    result = text

    # 1. Replace some Latin letters with Cyrillic homoglyphs (looks identical)
    if random.random() > 0.3:
        homoglyph_map = {
            'a': '\u0430',  # а
            'o': '\u043E',  # о
            'c': '\u0441',  # с
            'e': '\u0435',  # е
            'p': '\u0440',  # р
            'x': '\u0445',  # х
            'i': '\u0456',  # і
        }
        chars = list(result)
        for i, c in enumerate(chars):
            if c in homoglyph_map and random.random() > 0.6:
                chars[i] = homoglyph_map[c]
        result = ''.join(chars)

    # 2. Replace some regular spaces with alternative spaces (invisible difference)
    if random.random() > 0.3:
        spaces = [i for i, c in enumerate(result) if c == ' ']
        for pos in spaces:
            if random.random() > 0.5:
                replacement = random.choice(['\u00A0', '\u2009', '\u202F'])
                result = result[:pos] + replacement + result[pos+1:]

    # 3. Add invisible chars between words only (never inside words)
    if random.random() > 0.4 and len(result) > 5:
        # Find word boundaries (positions after a space)
        space_positions = [i for i, c in enumerate(result) if c in [' ', '\u00A0', '\u2009', '\u202F']]
        insert_positions = []
        for pos in space_positions:
            if random.random() > 0.75:  # ~25% of word boundaries
                insert_positions.append(pos + 1)
        # Insert in reverse to preserve positions
        chars = list(result)
        for pos in reversed(insert_positions):
            inv = random.choice(['\u200B', '\u200C'])
            chars.insert(pos, inv)
        result = ''.join(chars)

    # 4. Add invisible char at the very beginning (invisible to reader)
    if random.random() > 0.5:
        inv = random.choice(['\u200B', '\u200C', '\uFEFF'])
        result = inv + result

    return result


# ═══════════════════════════════════════════════
#  إدارة الحسابات والمجموعات
# ═══════════════════════════════════════════════
async def restore_sessions():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, session_string, phone, status FROM accounts WHERE status='active'")
    accounts = c.fetchall()
    conn.close()
    for acc_id, session_str, phone, status in accounts:
        try:
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            await client.connect()
            if await client.is_user_authorized():
                user_clients[acc_id] = client
                logger.info(f"✅ تم استعادة حساب: {phone}")
                await fetch_all_groups_for_account(acc_id, client)
            else:
                logger.warning(f"⚠️ الجلسة منتهية: {phone}")
                set_account_status(acc_id, 'expired')
        except Exception as e:
            logger.error(f"❌ فشل استعادة حساب {phone}: {e}")

def set_account_status(acc_id, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE accounts SET status=? WHERE id=?', (status, acc_id))
    conn.commit()
    conn.close()

async def fetch_all_groups_for_account(acc_id, client):
    count = 0
    try:
        async for dialog in client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                if getattr(dialog.entity, 'username', None) == "join":
                    continue
                group_id = dialog.id
                group_name = dialog.name or "بدون اسم"
                member_count = getattr(dialog.entity, 'participants_count', 0)
                username = getattr(dialog.entity, 'username', None)
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('''INSERT OR IGNORE INTO groups (group_id, group_name, username, member_count, added_by)
                             VALUES (?, ?, ?, ?, ?)''', (group_id, group_name[:100], username, member_count, f"account_{acc_id}"))
                conn.commit()
                conn.close()
                count += 1
        logger.info(f"✅ تم استيراد {count} مجموعة من الحساب {acc_id}")
    except Exception as e:
        logger.error(f"❌ فشل استيراد المجموعات: {e}")
    return count

async def get_account_groups(client):
    """Dynamically fetch all groups/channels from a user account, excluding blacklisted ones."""
    groups = []
    try:
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            # Filter only Chat and Channel type entities
            if isinstance(entity, (Chat, Channel)):
                group_id = dialog.id
                group_name = dialog.name or "بدون اسم"
                # Skip blacklisted groups
                if is_group_blacklisted(group_id):
                    continue
                groups.append((group_id, group_name))
    except Exception as e:
        logger.error(f"❌ فشل جلب المجموعات من الحساب: {e}")
    return groups

async def get_all_groups_count():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM groups WHERE is_protected=0")
    count = c.fetchone()[0]
    conn.close()
    return count

async def get_all_messages_count():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM messages")
    count = c.fetchone()[0]
    conn.close()
    return count

async def get_all_accounts():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM accounts WHERE status='active'")
    accounts = c.fetchall()
    conn.close()
    return [a[0] for a in accounts]

async def get_available_accounts():
    accounts = await get_all_accounts()
    available = []
    for acc_id in accounts:
        in_cooldown, remaining = is_account_in_cooldown(acc_id)
        if not in_cooldown:
            available.append(acc_id)
        elif in_cooldown and remaining < 30:
            available.append(acc_id)
    return available

# ═══════════════════════════════════════════════
#  نظام الانضمام التلقائي
# ═══════════════════════════════════════════════
async def auto_join_links(links):
    global is_joining_active
    if is_joining_active:
        return 0, 0, "يوجد عملية انضمام قيد التنفيذ"
    is_joining_active = True
    available_accs = await get_available_accounts()
    if not available_accs:
        is_joining_active = False
        return 0, 0, "لا توجد حسابات متاحة"
    acc_id = random.choice(available_accs)
    client = user_clients.get(acc_id)
    if not client:
        is_joining_active = False
        return 0, 0, "لا يوجد عميل للحساب"
    success_count = 0
    failed_count = 0
    join_interval = int(get_setting('join_interval', '100'))
    clean_links = []
    for link in links:
        link = link.strip()
        if link and (link.startswith('https://t.me/') or link.startswith('http://t.me/')):
            clean_links.append(link)
    if not clean_links:
        is_joining_active = False
        return 0, 0, "لا توجد روابط صالحة"
    if len(clean_links) > 20:
        clean_links = clean_links[:20]
    logger.info(f"🚀 بدء الانضمام لـ {len(clean_links)} رابط")
    for i, link in enumerate(clean_links, 1):
        try:
            jitter = random.randint(-10, 20)
            actual_delay = max(30, join_interval + jitter)
            logger.info(f"⏸ انتظار {actual_delay} ثانية قبل الرابط {i}/{len(clean_links)}")
            await asyncio.sleep(actual_delay)
            group_info = None
            if "joinchat" in link or "+" in link:
                hash_part = link.split('/')[-1].replace('+', '')
                updates = await client(ImportChatInviteRequest(hash_part))
                if updates.chats:
                    chat = updates.chats[0]
                    group_info = (chat.id, chat.title)
            else:
                username = link.split('/')[-1]
                entity = await client.get_entity(username)
                if entity:
                    await client(JoinChannelRequest(link))
                    group_info = (entity.id, getattr(entity, 'title', username))
            success_count += 1
            logger.info(f"✅ [{i}/{len(clean_links)}] تم الانضمام إلى {link[:50]}")
            if group_info:
                group_id, group_name = group_info
                save_join_history(link, group_id, group_name[:50], 'success', f"account_{acc_id}")
                add_group_to_db(group_id, group_name)
        except FloodWaitError as e:
            logger.warning(f"⏸ حساب {acc_id} في FloodWait: {e.seconds}ث")
            set_account_cooldown(acc_id, time.time() + e.seconds)
            failed_count += 1
            save_join_history(link, 0, "غير معروف", 'failed: flood wait', f"account_{acc_id}")
            break
        except Exception as e:
            failed_count += 1
            logger.error(f"❌ [{i}/{len(clean_links)}] فشل: {e}")
            save_join_history(link, 0, "غير معروف", f'failed: {str(e)[:50]}', f"account_{acc_id}")
    is_joining_active = False
    return success_count, failed_count, f"تم الانضمام لـ {success_count} من {len(clean_links)}"

def save_join_history(link, group_id, group_name, status, joined_by):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO join_history (link, group_id, group_name, status, joined_by, joined_at)
                 VALUES (?, ?, ?, ?, ?, ?)''', (link, group_id, group_name, status, joined_by, datetime.now()))
    conn.commit()
    conn.close()

def add_group_to_db(group_id, group_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO groups (group_id, group_name) VALUES (?, ?)', (group_id, group_name))
    conn.commit()
    conn.close()

def get_join_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM join_history")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM join_history WHERE status='success'")
    success = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM join_history WHERE status LIKE 'failed%'")
    failed = c.fetchone()[0]
    conn.close()
    return {'total': total, 'success': success, 'failed': failed}

def get_join_history(limit=30):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT link, group_name, joined_at, joined_by, status FROM join_history ORDER BY joined_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return rows

# ═══════════════════════════════════════════════
#  إرسال رسالة لمجموعة (دالة مساعدة)
# ═══════════════════════════════════════════════
async def send_message_to_group(client, group_id, encrypted_content, msg_type, media_path, media_data):
    """Send a message to a specific group with the appropriate type."""
    if msg_type == 'text':
        await client.send_message(int(group_id), encrypted_content)
    elif msg_type == 'photo' and media_path and os.path.exists(media_path):
        await client.send_file(int(group_id), media_path, caption=encrypted_content)
    elif msg_type == 'video' and media_path and os.path.exists(media_path):
        await client.send_file(int(group_id), media_path, caption=encrypted_content)
    elif msg_type == 'audio' and media_path and os.path.exists(media_path):
        await client.send_file(int(group_id), media_path, caption=encrypted_content)
    elif msg_type == 'document' and media_path and os.path.exists(media_path):
        await client.send_file(int(group_id), media_path, caption=encrypted_content)
    elif msg_type == 'contact' and media_data:
        contact_data = json.loads(media_data) if isinstance(media_data, str) else media_data
        await send_contact_message(client, int(group_id), contact_data, encrypted_content)
    else:
        if media_path and os.path.exists(media_path):
            await client.send_file(int(group_id), media_path, caption=encrypted_content)
        else:
            await client.send_message(int(group_id), encrypted_content)

async def send_contact_message(client, chat_id, contact_data, caption):
    try:
        contact = InputMediaContact(
            phone_number=contact_data.get('phone', ''),
            first_name=contact_data.get('first_name', ''),
            last_name=contact_data.get('last_name', ''),
            vcard=contact_data.get('vcard', '')
        )
        return await client.send_file(chat_id, contact, caption=caption)
    except Exception as e:
        logger.error(f"خطأ في إرسال جهة الاتصال: {e}")
        raise

# ═══════════════════════════════════════════════
#  النشر السريع - ينشر بكل القروبات المتاحة
# ═══════════════════════════════════════════════
async def fast_post_to_all_groups(message):
    """Fast post to ALL available groups from ALL accounts."""
    global is_posting_active
    # Dynamically fetch groups from all active accounts
    all_groups = []
    seen_ids = set()
    for acc_id, client in list(user_clients.items()):
        try:
            acc_groups = await get_account_groups(client)
            for gid, gname in acc_groups:
                if gid not in seen_ids:
                    seen_ids.add(gid)
                    all_groups.append((gid, gname, acc_id))
        except Exception as e:
            logger.error(f"❌ فشل جلب مجموعات الحساب {acc_id}: {e}")
            continue

    if not all_groups:
        return 0, 0, "لا توجد مجموعات"

    msg_id = message[0]
    content = message[1]
    media_path = message[2]
    msg_type = message[3]
    media_data = message[4] if len(message) > 4 else None
    fast_delay = max(2, int(get_setting('fast_post_delay', '3')))
    obfuscation_on = get_setting('obfuscation_enabled', 'on') == 'on'
    success_count = 0
    fail_count = 0
    total_groups = len(all_groups)

    logger.info(f"⚡ بدء النشر السريع إلى {total_groups} مجموعة")

    for group_id, group_name, acc_id in all_groups:
        if not is_posting_active:
            break
        # Apply text processing pipeline: vary_text → obfuscate_for_humans (if enabled) → encrypt_text
        if content:
            varied = vary_text(content)
            if obfuscation_on:
                varied = obfuscate_for_humans(varied)
            encrypted_content = encrypt_text(varied, group_id)
        else:
            encrypted_content = ""

        client = user_clients.get(acc_id)
        if not client:
            # Fallback: try any available account
            available_accs = await get_available_accounts()
            if not available_accs:
                await asyncio.sleep(5)
                continue
            fallback_acc = random.choice(available_accs)
            client = user_clients.get(fallback_acc)
            if not client:
                continue
            acc_id = fallback_acc

        try:
            await asyncio.sleep(fast_delay)
            if not is_posting_active:
                break
            await send_message_to_group(client, group_id, encrypted_content, msg_type, media_path, media_data)
            success_count += 1
            log_posting(acc_id, int(group_id), msg_id, 'success')
            logger.info(f"⚡ سريع ✅ {group_name[:30]} ({success_count}/{total_groups})")
        except FloodWaitError as e:
            logger.warning(f"⏸ FloodWait: {e.seconds}ث - انتظار ثم إعادة المحاولة")
            try:
                await asyncio.sleep(e.seconds + 1)
                if not is_posting_active:
                    break
                await send_message_to_group(client, group_id, encrypted_content, msg_type, media_path, media_data)
                success_count += 1
                log_posting(acc_id, int(group_id), msg_id, 'success (retry after flood)')
                logger.info(f"⚡ سريع ✅ (بعد FloodWait) {group_name[:30]}")
            except Exception as retry_e:
                fail_count += 1
                logger.error(f"❌ فشل بعد إعادة المحاولة: {retry_e}")
                set_account_cooldown(acc_id, time.time() + e.seconds)
        except Exception as e:
            fail_count += 1
            logger.error(f"❌ فشل: {e}")
    return success_count, fail_count, total_groups

# ═══════════════════════════════════════════════
#  النشر العادي
# ═══════════════════════════════════════════════
async def post_to_all_groups(message):
    global is_posting_active
    # Dynamically fetch groups from all active accounts
    all_groups = []
    seen_ids = set()
    for acc_id, client in list(user_clients.items()):
        try:
            acc_groups = await get_account_groups(client)
            for gid, gname in acc_groups:
                if gid not in seen_ids:
                    seen_ids.add(gid)
                    all_groups.append((gid, gname, acc_id))
        except Exception as e:
            logger.error(f"❌ فشل جلب مجموعات الحساب {acc_id}: {e}")
            continue

    if not all_groups:
        return 0, 0, "لا توجد مجموعات"

    msg_id = message[0]
    content = message[1]
    media_path = message[2]
    msg_type = message[3]
    media_data = message[4] if len(message) > 4 else None
    base_interval = max(2, int(get_setting('message_interval', '3')))
    use_jitter = get_setting('use_jitter', 'on') == 'on'
    obfuscation_on = get_setting('obfuscation_enabled', 'on') == 'on'
    success_count = 0
    fail_count = 0
    total_groups = len(all_groups)

    for group_id, group_name, acc_id in all_groups:
        if not is_posting_active:
            break
        # Apply text processing pipeline: vary_text → obfuscate_for_humans (if enabled) → encrypt_text
        if content:
            varied = vary_text(content)
            if obfuscation_on:
                varied = obfuscate_for_humans(varied)
            encrypted_content = encrypt_text(varied, group_id)
        else:
            encrypted_content = ""

        client = user_clients.get(acc_id)
        if not client:
            available_accs = await get_available_accounts()
            if not available_accs:
                all_accs = await get_all_accounts()
                if all_accs:
                    min_wait = 999999
                    for a_id in all_accs:
                        in_cooldown, remaining = is_account_in_cooldown(a_id)
                        if in_cooldown and remaining < min_wait:
                            min_wait = remaining
                    if min_wait < 999999:
                        wait_time = min(min_wait, 60)
                        logger.info(f"⏸ انتظار {wait_time:.0f} ثانية...")
                        await asyncio.sleep(wait_time)
                        continue
                await asyncio.sleep(30)
                continue
            fallback_acc = random.choice(available_accs)
            client = user_clients.get(fallback_acc)
            if not client:
                continue
            acc_id = fallback_acc

        try:
            if use_jitter:
                jitter = random.randint(-1, 2)
                actual_delay = max(2, base_interval + jitter)
            else:
                actual_delay = base_interval
            for _ in range(actual_delay):
                if not is_posting_active:
                    break
                await asyncio.sleep(1)
            if not is_posting_active:
                break
            await send_message_to_group(client, group_id, encrypted_content, msg_type, media_path, media_data)
            success_count += 1
            log_posting(acc_id, int(group_id), msg_id, 'success')
            logger.info(f"✅ [{msg_type}] {group_name[:30]} (حساب {acc_id})")
        except FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"⏸ حساب {acc_id} FloodWait: {wait_time}ث - انتظار ثم إعادة المحاولة")
            try:
                await asyncio.sleep(wait_time + 1)
                if not is_posting_active:
                    break
                await send_message_to_group(client, group_id, encrypted_content, msg_type, media_path, media_data)
                success_count += 1
                log_posting(acc_id, int(group_id), msg_id, 'success (retry after flood)')
                logger.info(f"✅ [{msg_type}] (بعد FloodWait) {group_name[:30]}")
            except Exception as retry_e:
                fail_count += 1
                set_account_cooldown(acc_id, time.time() + wait_time)
                log_posting(acc_id, int(group_id), msg_id, f'failed: retry after flood {str(retry_e)[:30]}')
                logger.error(f"❌ فشل بعد إعادة المحاولة: {retry_e}")
        except Exception as e:
            fail_count += 1
            log_posting(acc_id, int(group_id), msg_id, f'failed: {str(e)[:50]}')
            logger.error(f"❌ فشل النشر: {e}")
    return success_count, fail_count, total_groups

def log_posting(account_id, group_id, message_id, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO posting_history (account_id, group_id, message_id, status, posted_at)
                 VALUES (?, ?, ?, ?, ?)''', (account_id, group_id, message_id, status, datetime.now()))
    conn.commit()
    conn.close()

# ═══════════════════════════════════════════════
#  نظام جدولة النشر
# ═══════════════════════════════════════════════
async def schedule_checker(bot):
    """Background task that checks for scheduled posts and executes them."""
    while True:
        try:
            now = datetime.now()
            pending = get_pending_scheduled_posts()
            for sched_id, msg_id, post_time_str, repeat_type, repeat_interval, last_run in pending:
                try:
                    post_time = datetime.fromisoformat(post_time_str)
                    # Check if it's time to post
                    if now >= post_time:
                        logger.info(f"📅 تنفيذ منشور مجدول #{sched_id}")
                        # Get the message
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("SELECT id, content, media_path, msg_type, media_data FROM messages WHERE id=?", (msg_id,))
                        msg = c.fetchone()
                        conn.close()
                        if not msg:
                            update_scheduled_post_status(sched_id, 'failed')
                            continue
                        # Execute the post
                        global is_posting_active
                        if is_posting_active:
                            # Skip if posting is already active, try again later
                            continue
                        is_posting_active = True
                        success, fails, total = await fast_post_to_all_groups(msg)
                        is_posting_active = False

                        # Handle repeat
                        if repeat_type == 'repeat' and repeat_interval > 0:
                            next_time = now + timedelta(minutes=repeat_interval)
                            conn2 = sqlite3.connect(DB_PATH)
                            c2 = conn2.cursor()
                            c2.execute('UPDATE scheduled_posts SET post_time=?, last_run=? WHERE id=?',
                                      (next_time.isoformat(), now.isoformat(), sched_id))
                            conn2.commit()
                            conn2.close()
                            logger.info(f"📅 منشور مجدول #{sched_id} - الجولة القادمة: {next_time.strftime('%H:%M')}")
                        elif repeat_type == 'daily':
                            next_time = post_time + timedelta(days=1)
                            conn2 = sqlite3.connect(DB_PATH)
                            c2 = conn2.cursor()
                            c2.execute('UPDATE scheduled_posts SET post_time=?, last_run=? WHERE id=?',
                                      (next_time.isoformat(), now.isoformat(), sched_id))
                            conn2.commit()
                            conn2.close()
                            logger.info(f"📅 منشور مجدول #{sched_id} - غداً: {next_time.strftime('%H:%M')}")
                        else:
                            update_scheduled_post_status(sched_id, 'completed', now.isoformat())
                            logger.info(f"📅 منشور مجدول #{sched_id} - مكتمل")
                except Exception as e:
                    logger.error(f"❌ خطأ في تنفيذ منشور مجدول #{sched_id}: {e}")
        except Exception as e:
            logger.error(f"❌ خطأ في فحص الجدولة: {e}")
        # Check every 30 seconds
        await asyncio.sleep(30)

# ═══════════════════════════════════════════════
#  تنظيف قاعدة البيانات
# ═══════════════════════════════════════════════
def clean_database_keep_accounts():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT session_string, phone, status FROM accounts")
    accounts = c.fetchall()
    c.execute("DROP TABLE IF EXISTS messages")
    c.execute("DROP TABLE IF EXISTS groups")
    c.execute("DROP TABLE IF EXISTS posting_history")
    c.execute("DROP TABLE IF EXISTS join_history")
    c.execute("DROP TABLE IF EXISTS settings")
    c.execute("DROP TABLE IF EXISTS protected_groups_log")
    c.execute("DROP TABLE IF EXISTS blacklist")
    c.execute("DROP TABLE IF EXISTS scheduled_posts")
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT, media_path TEXT, msg_type TEXT DEFAULT 'text',
        media_data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_string TEXT, phone TEXT,
        status TEXT DEFAULT 'active',
        cooldown_until TIMESTAMP DEFAULT NULL,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER, group_name TEXT,
        username TEXT, member_count INTEGER,
        is_protected INTEGER DEFAULT 0,
        added_by TEXT,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS posting_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER, group_id INTEGER,
        message_id INTEGER, status TEXT,
        posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS join_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        link TEXT, group_id INTEGER, group_name TEXT,
        status TEXT, joined_by TEXT,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS protected_groups_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER, group_name TEXT,
        bot_name TEXT, detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS blacklist (
        group_id TEXT PRIMARY KEY,
        group_name TEXT,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS scheduled_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER,
        post_time TEXT NOT NULL,
        repeat_type TEXT DEFAULT 'once',
        repeat_interval INTEGER DEFAULT 0,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_run TEXT DEFAULT NULL)''')
    for session_str, phone, status in accounts:
        c.execute('INSERT INTO accounts (session_string, phone, status) VALUES (?, ?, ?)',
                  (session_str, phone, status))
    conn.commit()
    conn.close()
    return len(accounts)

# ═══════════════════════════════════════════════
#  القوائم والأزرار
# ═══════════════════════════════════════════════
def get_main_menu():
    enc_status = "✅" if get_setting('encryption', 'on') == 'on' else "❌"
    anti_status = "✅" if get_setting('anti_detect', 'on') == 'on' else "❌"
    jitter_status = "✅" if get_setting('use_jitter', 'on') == 'on' else "❌"
    bot_detect_status = "✅" if get_setting('bot_detection', 'on') == 'on' else "❌"
    obf_status = "✅" if get_setting('obfuscation_enabled', 'on') == 'on' else "❌"
    message_interval = get_setting('message_interval', '3')
    join_interval = get_setting('join_interval', '100')
    fast_delay = get_setting('fast_post_delay', '3')
    return [
        [Button.inline("📝 إدارة الرسائل", b"messages")],
        [Button.inline("👥 إدارة الحسابات", b"accounts")],
        [Button.inline("⚡ نشر سريع للكل", b"fast_posting"),
         Button.inline("🚀 بدء النشر", b"start_posting"),
         Button.inline("⏹ إيقاف النشر", b"stop_posting")],
        [Button.inline("📅 جدولة النشر", b"scheduling")],
        [Button.inline(f"🛡 التشفير {enc_status}", b"toggle_enc"),
         Button.inline(f"🎭 مكافحة الكشف {anti_status}", b"toggle_anti")],
        [Button.inline(f"🎭 تشويش النص {obf_status}", b"toggle_obfuscate"),
         Button.inline(f"📳 Jitter {jitter_status}", b"toggle_jitter")],
        [Button.inline(f"🤖 كشف البوتات {bot_detect_status}", b"toggle_bot_detect")],
        [Button.inline("⚙️ الإعدادات", b"settings"),
         Button.inline("📊 الإحصائيات", b"stats")],
        [Button.inline(f"🐢 انضمام ({join_interval}ث)", b"slow_join"),
         Button.inline("📋 تقارير الانضمام", b"join_reports")],
        [Button.inline(f"⏱ مدة النشر ({message_interval}ث)", b"set_msg_interval"),
         Button.inline(f"⚡ سرعة النشر السريع ({fast_delay}ث)", b"set_fast_delay"),
         Button.inline("🐢 مدة الانضمام", b"set_join_interval")],
        [Button.inline("🔄 مسح تبريد الحسابات", b"clear_cooldowns")],
        [Button.inline("🛡️ المجموعات المحمية", b"protected_groups")],
        [Button.inline("🚫 القائمة السوداء", b"blacklist")],
        [Button.inline("🗑 تنظيف قاعدة البيانات", b"clean_db")],
        [Button.inline("🔄 تحديث المجموعات", b"refresh_groups")],
    ]

def get_scheduling_menu():
    return [
        [Button.inline("➕ جدولة منشور جديد", b"schedule_new")],
        [Button.inline("📋 المنشورات المجدولة", b"schedule_list")],
        [Button.inline("🗑 حذف جدولة", b"schedule_delete")],
        [Button.inline("🔙 رجوع", b"back")],
    ]

def get_join_reports_menu():
    return [
        [Button.inline("📊 إحصائيات الانضمام", b"join_stats")],
        [Button.inline("📋 سجل الانضمام", b"join_history")],
        [Button.inline("🔙 رجوع", b"back")],
    ]

def get_settings_menu():
    enc_status = "✅" if get_setting('encryption', 'on') == 'on' else "❌"
    anti_status = "✅" if get_setting('anti_detect', 'on') == 'on' else "❌"
    jitter_status = "✅" if get_setting('use_jitter', 'on') == 'on' else "❌"
    bot_detect_status = "✅" if get_setting('bot_detection', 'on') == 'on' else "❌"
    obf_status = "✅" if get_setting('obfuscation_enabled', 'on') == 'on' else "❌"
    return [
        [Button.inline(f"🛡 تبديل التشفير {enc_status}", b"toggle_enc")],
        [Button.inline(f"🎭 تبديل مكافحة الكشف {anti_status}", b"toggle_anti")],
        [Button.inline(f"🎭 تشويش النص {obf_status}", b"toggle_obfuscate")],
        [Button.inline(f"📳 تبديل Jitter {jitter_status}", b"toggle_jitter")],
        [Button.inline(f"🤖 تبديل كشف البوتات {bot_detect_status}", b"toggle_bot_detect")],
        [Button.inline("⏱ مدة النشر", b"set_msg_interval")],
        [Button.inline("⚡ سرعة النشر السريع", b"set_fast_delay")],
        [Button.inline("🐢 مدة الانضمام", b"set_join_interval")],
        [Button.inline("🔙 رجوع", b"back")]
    ]

def get_blacklist_menu():
    return [
        [Button.inline("➕ إضافة للقائمة السوداء", b"add_blacklist")],
        [Button.inline("📋 عرض القائمة السوداء", b"view_blacklist")],
        [Button.inline("🗑 حذف من القائمة السوداء", b"del_blacklist")],
        [Button.inline("🔙 رجوع", b"back")],
    ]

# ═══════════════════════════════════════════════
#  البوت الرئيسي
# ═══════════════════════════════════════════════
async def main():
    global is_posting_active
    Thread(target=run_web, daemon=True).start()
    logger.info(f"🌐 خادم الويب على المنفذ {PORT}")
    asyncio.create_task(keep_alive_ping())
    logger.info("🔄 نظام الإبقاء على البوت نشطاً يعمل")
    init_db()
    await restore_sessions()
    bot = TelegramClient('bot_session', API_ID, API_HASH)
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("🤖 البوت يعمل - مع الحماية القصوى والنشر السريع والجدولة")

    # Start schedule checker
    asyncio.create_task(schedule_checker(bot))
    logger.info("📅 نظام الجدولة يعمل")

    @bot.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        if not is_admin(event.sender_id):
            return
        groups_count = await get_all_groups_count()
        message_interval = get_setting('message_interval', '3')
        join_interval = get_setting('join_interval', '100')
        fast_delay = get_setting('fast_post_delay', '3')
        example_text = "اشترك في قناتنا للحصول على عروض حصرية"
        encrypted_example = encrypt_text(example_text)
        await event.respond(
            "🛡 **بوت النشر - الحماية القصوى + النشر السريع + الجدولة**\n\n"
            "✨ **تقنيات تجاوز الحماية (محسنة - تحافظ على المحتوى):**\n"
            "• أحرف غير مرئية بين الكلمات\n• مسافات بديلة (غير مرئية)\n"
            "• حروف لاتينية متشابهة (homoglyphs)\n• تشويش الروابط\n"
            "• النص يبقى كما هو للمستخدم العادي!\n\n"
            f"📅 **الجدولة:** جدولة النشر لأوقات محددة\n"
            f"⚡ النشر السريع ({fast_delay} ثانية)\n\n"
            f"📝 **مثال للتشفير:**\n"
            f"الأصلي: {example_text}\n"
            f"المشفر: {encrypted_example}\n\n"
            f"📢 المجموعات: {groups_count}\n"
            f"⏱ مدة النشر العادي: {message_interval} ثانية\n"
            f"🐢 مدة الانضمام: {join_interval} ثانية\n\n"
            "اختر من القائمة:",
            buttons=get_main_menu()
        )

    async def auto_posting_loop():
        global is_posting_active
        logger.info("🔄 بدء النشر العادي...")
        while is_posting_active:
            try:
                if not is_posting_active:
                    break
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT id, content, media_path, msg_type, media_data FROM messages")
                msgs = c.fetchall()
                conn.close()
                if not msgs:
                    logger.warning("⚠️ لا توجد رسائل")
                    is_posting_active = False
                    break
                for msg in msgs:
                    if not is_posting_active:
                        break
                    logger.info(f"📤 نشر رسالة #{msg[0]} ({msg[3]})")
                    success, fails, total = await post_to_all_groups(msg)
                    logger.info(f"📤 النتيجة: نجاح={success}, فشل={fails} من {total}")
                    if not is_posting_active:
                        break
                    base_interval = max(2, int(get_setting('message_interval', '3')))
                    use_jitter = get_setting('use_jitter', 'on') == 'on'
                    loop_delay = base_interval + (random.randint(-1, 2) if use_jitter else 0)
                    loop_delay = max(2, loop_delay)
                    for _ in range(loop_delay):
                        if not is_posting_active:
                            break
                        await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"خطأ: {e}")
                await asyncio.sleep(5)
        logger.info("✅ توقف النشر العادي")

    @bot.on(events.NewMessage(pattern='/encrypt'))
    async def encrypt_preview(event):
        if not is_admin(event.sender_id):
            return
        text = event.raw_text.replace('/encrypt', '').strip()
        if not text:
            text = "اشترك في قناتنا للحصول على عروض حصرية"
        varied = vary_text(text)
        obfuscated = obfuscate_for_humans(varied)
        encrypted = encrypt_text(obfuscated)
        await event.respond(
            f"📝 **النص الأصلي:**\n{text}\n\n"
            f"🔀 **بعد التشويش:**\n{obfuscated}\n\n"
            f"🛡 **بعد التشفير:**\n{encrypted}\n\n"
            f"💡 ملاحظة: التغييرات غير مرئية للمستخدم العادي\nفقط الآلات تستطيع اكتشافها!"
        )

    @bot.on(events.NewMessage(pattern='/check'))
    async def check_handler(event):
        if not is_admin(event.sender_id):
            return
        groups = await get_all_groups_count()
        msgs = await get_all_messages_count()
        all_accs = await get_all_accounts()
        available = await get_available_accounts()
        obf_status = '✅ مفعل' if get_setting('obfuscation_enabled', 'on') == 'on' else '❌ معطل'
        pending_sched = len(get_pending_scheduled_posts())
        await event.respond(
            f"📊 **حالة البوت:**\n"
            f"• المجموعات: {groups}\n• الرسائل: {msgs}\n"
            f"• إجمالي الحسابات: {len(all_accs)}\n• حسابات متاحة: {len(available)}\n"
            f"• النشر: {'🟢 نشط' if is_posting_active else '🔴 متوقف'}\n"
            f"• التشفير: {'✅ مفعل' if get_setting('encryption', 'on') == 'on' else '❌ معطل'}\n"
            f"• مكافحة الكشف: {'✅ مفعلة' if get_setting('anti_detect', 'on') == 'on' else '❌ معطلة'}\n"
            f"• تشويش النص: {obf_status}\n"
            f"• 📅 منشورات مجدولة: {pending_sched}"
        )

    @bot.on(events.NewMessage(pattern='/clear_cooldowns'))
    async def clear_cooldowns_cmd(event):
        if not is_admin(event.sender_id):
            return
        clear_all_cooldowns()
        await event.respond("✅ تم مسح تبريد جميع الحسابات!")

    @bot.on(events.NewMessage(pattern='/test'))
    async def test_handler(event):
        if not is_admin(event.sender_id):
            return
        await event.respond("✅ البوت يعمل مع الحماية القصوى والنشر السريع والجدولة!")

    @bot.on(events.NewMessage(pattern='/fast_post'))
    async def fast_post_command(event):
        global is_posting_active
        if not is_admin(event.sender_id):
            return
        if not user_clients:
            await event.respond("⚠️ لا توجد حسابات! أضف حساباً أولاً")
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, content, media_path, msg_type, media_data FROM messages LIMIT 1")
        msg = c.fetchone()
        conn.close()
        if not msg:
            await event.respond("⚠️ لا توجد رسائل! أضف رسالة أولاً")
            return
        if is_posting_active:
            await event.respond("⚠️ النشر يعمل بالفعل! استخدم /stop_posting أولاً")
            return
        is_posting_active = True
        fast_delay = get_setting('fast_post_delay', '3')
        await event.respond(f"⚡ بدء النشر السريع لكل المجموعات (كل {fast_delay} ثانية)...")
        success, fails, total = await fast_post_to_all_groups(msg)
        is_posting_active = False
        await event.respond(f"✅ اكتمل النشر السريع!\n✅ نجاح: {success}\n❌ فشل: {fails}\n📢 من أصل {total} مجموعة")

    @bot.on(events.NewMessage(pattern='/stop_posting'))
    async def stop_posting_command(event):
        global is_posting_active
        is_posting_active = False
        await event.respond("⏹ **تم إيقاف النشر**")

    @bot.on(events.NewMessage(pattern='/scan_groups'))
    async def scan_groups(event):
        if not is_admin(event.sender_id):
            return
        await event.respond("🔄 جاري المسح...")
        total = 0
        for acc_id, client in user_clients.items():
            count = await fetch_all_groups_for_account(acc_id, client)
            total += count
        await event.respond(f"✅ تم استيراد {total} مجموعة")

    @bot.on(events.NewMessage(pattern='/set_msg_interval'))
    async def set_msg_cmd(event):
        if not is_admin(event.sender_id):
            return
        try:
            val = int(event.raw_text.split()[1])
            if 2 <= val <= 600:
                set_setting('message_interval', str(val))
                await event.respond(f"✅ مدة النشر العادي: {val} ثانية")
        except:
            await event.respond("❌ استخدم: /set_msg_interval 3 (الحد الأدنى: 2)")

    @bot.on(events.NewMessage(pattern='/set_fast_delay'))
    async def set_fast_cmd(event):
        if not is_admin(event.sender_id):
            return
        try:
            val = int(event.raw_text.split()[1])
            if 2 <= val <= 30:
                set_setting('fast_post_delay', str(val))
                await event.respond(f"✅ سرعة النشر السريع: {val} ثانية")
        except:
            await event.respond("❌ استخدم: /set_fast_delay 3 (الحد الأدنى: 2)")

    @bot.on(events.NewMessage(pattern='/set_join_interval'))
    async def set_join_cmd(event):
        if not is_admin(event.sender_id):
            return
        try:
            val = int(event.raw_text.split()[1])
            if 30 <= val <= 600:
                set_setting('join_interval', str(val))
                await event.respond(f"✅ مدة الانضمام: {val} ثانية")
        except:
            await event.respond("❌ استخدم: /set_join_interval 100")

    @bot.on(events.CallbackQuery)
    async def callback_handler(event):
        global is_posting_active
        if not is_admin(event.sender_id):
            await event.answer("⛔ غير مصرح", alert=True)
            return
        data = event.data.decode('utf-8')
        if data == 'back':
            groups_count = await get_all_groups_count()
            message_interval = get_setting('message_interval', '3')
            join_interval = get_setting('join_interval', '100')
            pending_sched = len(get_pending_scheduled_posts())
            await event.edit(
                "🛡 **لوحة التحكم**\n\n"
                f"📢 المجموعات: {groups_count}\n"
                f"⏱ مدة النشر: {message_interval} ثانية\n"
                f"🐢 مدة الانضمام: {join_interval} ثانية\n"
                f"📅 منشورات مجدولة: {pending_sched}",
                buttons=get_main_menu()
            )
        elif data == 'fast_posting':
            # ⚡ نشر سريع لكل القروبات المتاحة فوراً
            await event.answer("⚡ جاري النشر السريع لكل المجموعات...", alert=True)
            msg_count = await get_all_messages_count()
            all_accs = await get_all_accounts()
            available = await get_available_accounts()
            fast_delay = get_setting('fast_post_delay', '3')
            if not user_clients:
                await event.edit("⚠️ لا توجد حسابات!\nاضغط 'إضافة حساب' أولاً",
                               buttons=[[Button.inline("➕ إضافة حساب", b"add_acc")]])
                return
            if msg_count == 0:
                await event.edit("⚠️ لا توجد رسائل!", buttons=[[Button.inline("➕ إضافة", b"add_msg")]])
                return
            if is_posting_active:
                await event.edit("⚠️ النشر يعمل بالفعل! (أوقف النشر أولاً)",
                               buttons=[[Button.inline("⏹ إيقاف النشر", b"stop_posting")]])
                return
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id, content, media_path, msg_type, media_data FROM messages")
            msgs = c.fetchall()
            conn.close()
            if not msgs:
                await event.edit("⚠️ لا توجد رسائل!", buttons=[[Button.inline("➕ إضافة", b"add_msg")]])
                return
            is_posting_active = True
            enc_status = "✅ مفعل" if get_setting('encryption', 'on') == 'on' else "❌ معطل"
            anti_status = "✅ مفعل" if get_setting('anti_detect', 'on') == 'on' else "❌ معطل"
            obf_status = "✅ مفعل" if get_setting('obfuscation_enabled', 'on') == 'on' else "❌ معطل"
            await event.edit(
                f"⚡ **النشر السريع لكل المجموعات!**\n\n"
                f"👥 {len(all_accs)} حساب (متاح: {len(available)})\n"
                f"📝 {len(msgs)} رسالة\n"
                f"⏱ كل {fast_delay} ثانية\n"
                f"🛡 التشفير: {enc_status}\n🎭 مكافحة الكشف: {anti_status}\n🎭 تشويش النص: {obf_status}\n\nجاري النشر...",
                buttons=[[Button.inline("⏹ إيقاف", b"stop_posting")]]
            )
            total_success = 0
            total_fails = 0
            total_groups = 0
            for msg in msgs:
                if not is_posting_active:
                    break
                success, fails, total = await fast_post_to_all_groups(msg)
                total_success += success
                total_fails += fails
                total_groups = max(total_groups, total)
            is_posting_active = False
            await event.edit(
                f"✅ **اكتمل النشر السريع!**\n\n✅ نجاح: {total_success}\n❌ فشل: {total_fails}\n📢 من أصل {total_groups} مجموعة\n📝 عدد الرسائل: {len(msgs)}\n⚡ تم النشر بمعدل {fast_delay} ثانية",
                buttons=[[Button.inline("🔙 رجوع", b"back")]]
            )
        elif data == 'start_posting':
            msg_count = await get_all_messages_count()
            all_accs = await get_all_accounts()
            available = await get_available_accounts()
            if not user_clients:
                await event.edit("⚠️ لا توجد حسابات!\nاضغط 'إضافة حساب' أولاً",
                               buttons=[[Button.inline("➕ إضافة حساب", b"add_acc")]])
                return
            if msg_count == 0:
                await event.edit("⚠️ لا توجد رسائل!", buttons=[[Button.inline("➕ إضافة", b"add_msg")]])
                return
            if is_posting_active:
                await event.edit("⚠️ النشر يعمل بالفعل!", buttons=[[Button.inline("🔙 رجوع", b"back")]])
                return
            is_posting_active = True
            message_interval = get_setting('message_interval', '3')
            enc_status = "✅ مفعل" if get_setting('encryption', 'on') == 'on' else "❌ معطل"
            anti_status = "✅ مفعل" if get_setting('anti_detect', 'on') == 'on' else "❌ معطل"
            obf_status = "✅ مفعل" if get_setting('obfuscation_enabled', 'on') == 'on' else "❌ معطل"
            await event.edit(
                f"🚀 **بدأ النشر بالحماية القصوى!**\n\n"
                f"👥 {len(all_accs)} حساب (متاح: {len(available)})\n"
                f"⏱ كل {message_interval} ثانية\n🛡 التشفير: {enc_status}\n🎭 مكافحة الكشف: {anti_status}\n🎭 تشويش النص: {obf_status}\n\n✅ النشر يعمل!",
                buttons=[[Button.inline("⏹ إيقاف", b"stop_posting")]]
            )
            asyncio.create_task(auto_posting_loop())
        elif data == 'stop_posting':
            is_posting_active = False
            await event.edit("⏹ **تم إيقاف النشر**", buttons=[[Button.inline("🔙 رجوع", b"back")]])
        elif data == 'set_fast_delay':
            await event.edit("⚡ أرسل المدة بين المجموعات في النشر السريع (2-30 ثانية):\n/cancel للإلغاء")
            set_setting('awaiting_fast_delay', 'true')
        elif data == 'scheduling':
            pending_count = len(get_pending_scheduled_posts())
            await event.edit(
                f"📅 **جدولة النشر**\n\n📌 منشورات مجدولة معلقة: {pending_count}\n\n"
                "يمكنك جدولة النشر لأوقات محددة:\n"
                "• مرة واحدة في وقت محدد\n"
                "• تكرار كل X دقيقة\n"
                "• يومياً في وقت محدد",
                buttons=get_scheduling_menu()
            )
        elif data == 'schedule_new':
            await event.edit(
                "📅 **جدولة منشور جديد**\n\n"
                "أرسل التوقيت بأحد الصيغ التالية:\n\n"
                "🕐 **وقت محدد:** `15:30` (الساعة 3:30 مساءً اليوم)\n"
                "🕐 **بعد فترة:** `30د` (بعد 30 دقيقة)\n"
                "🕐 **بعد ساعات:** `2س` (بعد ساعتين)\n"
                "🔄 **تكرار:** `30د كل 60` (بعد 30 دقيقة ويتكرر كل 60 دقيقة)\n"
                "📅 **يومي:** `15:30 يومي` (كل يوم الساعة 3:30)\n\n"
                "/cancel للإلغاء",
            )
            set_setting('awaiting_schedule', 'true')
        elif data == 'schedule_list':
            schedules = get_all_scheduled_posts()
            if not schedules:
                await event.edit("📋 لا توجد منشورات مجدولة", buttons=get_scheduling_menu())
            else:
                text = "📋 **المنشورات المجدولة:**\n\n"
                for sched_id, msg_id, post_time, repeat_type, repeat_interval, status, last_run in schedules[:15]:
                    status_icon = "⏳" if status == 'pending' else "✅" if status == 'completed' else "❌"
                    repeat_text = ""
                    if repeat_type == 'repeat':
                        repeat_text = f" (كل {repeat_interval} دقيقة)"
                    elif repeat_type == 'daily':
                        repeat_text = " (يومي)"
                    try:
                        pt = datetime.fromisoformat(post_time)
                        time_str = pt.strftime('%Y-%m-%d %H:%M')
                    except:
                        time_str = post_time
                    text += f"{status_icon} #{sched_id} | رسالة #{msg_id}\n   🕐 {time_str}{repeat_text}\n\n"
                await event.edit(text, buttons=get_scheduling_menu())
        elif data == 'schedule_delete':
            await event.edit("🗑 أرسل رقم الجدولة للحذف:\n/cancel للإلغاء")
            set_setting('awaiting_schedule_delete', 'true')
        elif data == 'messages':
            await event.edit("📝 **إدارة الرسائل**", buttons=[
                [Button.inline("➕ إضافة", b"add_msg")],
                [Button.inline("📋 عرض", b"list_msg")],
                [Button.inline("🗑 حذف", b"del_msg")],
                [Button.inline("🔙 رجوع", b"back")],
            ])
        elif data == 'add_msg':
            await event.edit("➕ أرسل النص أو الوسائط (صورة/فيديو/ملف/جهة اتصال) مع تعليق:\n/cancel للإلغاء")
            set_setting('awaiting_msg', 'true')
        elif data == 'list_msg':
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id, substr(content,1,50), msg_type FROM messages LIMIT 20")
            msgs = c.fetchall()
            conn.close()
            if not msgs:
                await event.edit("📋 لا توجد رسائل", buttons=[[Button.inline("🔙 رجوع", b"messages")]])
            else:
                text = "📋 **الرسائل:**\n\n"
                for mid, content, mtype in msgs:
                    icons = {'text':'📝','photo':'📷','video':'🎬','audio':'🎵','document':'📄','contact':'👤'}
                    text += f"{icons.get(mtype,'📦')} #{mid} [{mtype}] - {content[:30]}...\n"
                await event.edit(text, buttons=[[Button.inline("🔙 رجوع", b"messages")]])
        elif data == 'del_msg':
            await event.edit("🗑 أرسل رقم الرسالة:\n/cancel للإلغاء")
            set_setting('awaiting_del_msg', 'true')
        elif data == 'accounts':
            await event.edit("👥 **إدارة الحسابات**", buttons=[
                [Button.inline("➕ إضافة", b"add_acc")],
                [Button.inline("📋 عرض", b"list_acc")],
                [Button.inline("🗑 حذف", b"del_acc")],
                [Button.inline("🔙 رجوع", b"back")],
            ])
        elif data == 'add_acc':
            await event.edit("➕ أرسل رقم الهاتف (مثال: +966512345678)\n/cancel للإلغاء")
            set_setting('awaiting_phone', 'true')
        elif data == 'list_acc':
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id, phone, status, cooldown_until FROM accounts")
            accs = c.fetchall()
            conn.close()
            if not accs:
                await event.edit("👥 لا توجد حسابات", buttons=[[Button.inline("🔙 رجوع", b"accounts")]])
            else:
                text = "👥 **الحسابات:**\n\n"
                for aid, phone, status, cooldown in accs:
                    emoji = "✅" if status == 'active' else "⏸️"
                    cd = f" (تبريد)" if cooldown else ""
                    text += f"{emoji} #{aid} - {phone}{cd}\n"
                await event.edit(text, buttons=[[Button.inline("🔙 رجوع", b"accounts")]])
        elif data == 'del_acc':
            await event.edit("🗑 أرسل رقم الحساب:\n/cancel للإلغاء")
            set_setting('awaiting_del_acc', 'true')
        elif data == 'refresh_groups':
            await event.edit("🔄 جاري تحديث المجموعات...")
            total = 0
            for acc_id, client in user_clients.items():
                count = await fetch_all_groups_for_account(acc_id, client)
                total += count
            await event.edit(f"✅ تم تحديث {total} مجموعة", buttons=[[Button.inline("🔙 رجوع", b"back")]])
        elif data == 'clear_cooldowns':
            clear_all_cooldowns()
            await event.answer("✅ تم مسح التبريد!", alert=True)
            await event.edit("✅ تم مسح تبريد جميع الحسابات", buttons=[[Button.inline("🔙 رجوع", b"back")]])
        elif data == 'settings':
            obf_status = get_setting('obfuscation_enabled', 'on')
            await event.edit(
                "⚙️ **الإعدادات**\n\n"
                f"⏱ مدة النشر العادي: {get_setting('message_interval', '3')} ثانية\n"
                f"⚡ مدة النشر السريع: {get_setting('fast_post_delay', '3')} ثانية\n"
                f"🐢 مدة الانضمام: {get_setting('join_interval', '100')} ثانية\n"
                f"🛡 التشفير: {get_setting('encryption', 'on')}\n"
                f"🎭 مكافحة الكشف: {get_setting('anti_detect', 'on')}\n"
                f"🎭 تشويش النص: {obf_status}\n"
                f"📳 Jitter: {get_setting('use_jitter', 'on')}\n"
                f"🤖 كشف البوتات: {get_setting('bot_detection', 'on')}",
                buttons=get_settings_menu()
            )
        elif data == 'set_msg_interval':
            await event.edit("⏱ أرسل المدة (2-600 ثانية، الحد الأدنى 2):\n/cancel للإلغاء")
            set_setting('awaiting_msg_interval', 'true')
        elif data == 'set_join_interval':
            await event.edit("🐢 أرسل المدة (30-600 ثانية):\n/cancel للإلغاء")
            set_setting('awaiting_join_interval', 'true')
        elif data == 'toggle_enc':
            current = get_setting('encryption', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('encryption', new_val)
            await event.answer(f"التشفير: {'مفعل' if new_val == 'on' else 'معطل'}")
            await event.edit("⚙️ الإعدادات", buttons=get_settings_menu())
        elif data == 'toggle_anti':
            current = get_setting('anti_detect', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('anti_detect', new_val)
            await event.answer(f"مكافحة الكشف: {'مفعلة' if new_val == 'on' else 'معطلة'}")
            await event.edit("⚙️ الإعدادات", buttons=get_settings_menu())
        elif data == 'toggle_obfuscate':
            current = get_setting('obfuscation_enabled', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('obfuscation_enabled', new_val)
            await event.answer(f"تشويش النص: {'مفعل' if new_val == 'on' else 'معطل'}")
            await event.edit("⚙️ الإعدادات", buttons=get_settings_menu())
        elif data == 'toggle_jitter':
            current = get_setting('use_jitter', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('use_jitter', new_val)
            await event.answer(f"Jitter: {'مفعل' if new_val == 'on' else 'معطل'}")
            await event.edit("⚙️ الإعدادات", buttons=get_settings_menu())
        elif data == 'toggle_bot_detect':
            current = get_setting('bot_detection', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('bot_detection', new_val)
            await event.answer(f"كشف البوتات: {'مفعل' if new_val == 'on' else 'معطل'}")
            await event.edit("⚙️ الإعدادات", buttons=get_settings_menu())
        elif data == 'blacklist':
            bl_count = len(get_blacklisted_groups())
            await event.edit(f"🚫 **القائمة السوداء** ({bl_count} مجموعة)", buttons=get_blacklist_menu())
        elif data == 'add_blacklist':
            await event.edit("🚫 أرسل معرف المجموعة (group_id) لإضافتها للقائمة السوداء:\n/cancel للإلغاء")
            set_setting('awaiting_add_blacklist', 'true')
        elif data == 'view_blacklist':
            blacklisted = get_blacklisted_groups()
            if not blacklisted:
                await event.edit("🚫 القائمة السوداء فارغة", buttons=get_blacklist_menu())
            else:
                text = "🚫 **القائمة السوداء:**\n\n"
                for gid, gname, added_at in blacklisted[:30]:
                    text += f"🚫 {gname[:25]} (ID: {gid})\n   📅 {added_at[:16]}\n\n"
                await event.edit(text, buttons=get_blacklist_menu())
        elif data == 'del_blacklist':
            await event.edit("🚫 أرسل معرف المجموعة (group_id) لإزالتها من القائمة السوداء:\n/cancel للإلغاء")
            set_setting('awaiting_del_blacklist', 'true')
        elif data == 'stats':
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM messages")
            msg_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM accounts WHERE status='active'")
            acc_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM groups")
            grp_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM groups WHERE is_protected=1")
            protected_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM posting_history WHERE status='success'")
            success_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM posting_history WHERE status LIKE 'failed%'")
            fail_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM blacklist")
            blacklist_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM scheduled_posts WHERE status='pending'")
            sched_count = c.fetchone()[0]
            join_stats = get_join_stats()
            conn.close()
            obf_status = '✅' if get_setting('obfuscation_enabled', 'on') == 'on' else '❌'
            await event.edit(
                f"📊 **الإحصائيات**\n\n"
                f"📝 الرسائل: {msg_count}\n👥 الحسابات: {acc_count}\n"
                f"📢 المجموعات: {grp_count}\n🛡️ محمية: {protected_count}\n"
                f"🚫 القائمة السوداء: {blacklist_count}\n"
                f"✅ نجاح: {success_count}\n❌ فشل: {fail_count}\n"
                f"🔗 انضمام: {join_stats['total']} (نجاح: {join_stats['success']})\n"
                f"🎭 تشويش النص: {obf_status}\n"
                f"📅 مجدولة: {sched_count}",
                buttons=[[Button.inline("🔙 رجوع", b"back")]]
            )
        elif data == 'slow_join':
            await event.edit("🐢 **انضمام بطيء**\n\nأرسل الروابط (كل رابط في سطر):\n/cancel للإلغاء")
            set_setting('awaiting_slow_join', 'true')
        elif data == 'join_reports':
            await event.edit("🔗 **تقارير الانضمام**", buttons=get_join_reports_menu())
        elif data == 'join_stats':
            stats = get_join_stats()
            await event.edit(
                f"📊 **إحصائيات الانضمام**\n\n📌 المجموع: {stats['total']}\n✅ نجاح: {stats['success']}\n❌ فشل: {stats['failed']}\n📈 النسبة: {stats['success']/(stats['total'] or 1)*100:.1f}%",
                buttons=get_join_reports_menu()
            )
        elif data == 'join_history':
            history = get_join_history(30)
            if not history:
                await event.edit("📭 لا توجد سجلات", buttons=get_join_reports_menu())
            else:
                text = "🔗 **آخر عمليات الانضمام:**\n\n"
                for link, group_name, joined_at, joined_by, status in history[:15]:
                    icon = "✅" if status == 'success' else "❌"
                    text += f"{icon} {group_name[:25]}\n   🔗 {link[:40]}\n\n"
                await event.edit(text, buttons=get_join_reports_menu())
        elif data == 'protected_groups':
            protected = get_protected_groups()
            if not protected:
                await event.edit("🛡️ لا توجد مجموعات محمية", buttons=[[Button.inline("🔙 رجوع", b"back")]])
            else:
                text = "🛡️ **المجموعات المحمية:**\n\n"
                for gid, gname, bot_name, detected_at in protected[:20]:
                    text += f"🛡️ {gname[:25]}\n   🤖 {bot_name}\n   📅 {detected_at[:16]}\n\n"
                await event.edit(text, buttons=[[Button.inline("🔙 رجوع", b"back")]])
        elif data == 'clean_db':
            await event.edit(
                "⚠️ **تنظيف قاعدة البيانات**\n\nسيتم حذف كل شيء ما عدا الحسابات\n\nهل أنت متأكد؟",
                buttons=[[Button.inline("✅ نعم", b"confirm_clean")], [Button.inline("❌ إلغاء", b"back")]]
            )
        elif data == 'confirm_clean':
            try:
                saved = clean_database_keep_accounts()
                set_setting('message_interval', '3')
                set_setting('fast_post_delay', '3')
                set_setting('join_interval', '100')
                set_setting('encryption', 'on')
                set_setting('anti_detect', 'on')
                set_setting('obfuscation_enabled', 'on')
                await event.edit(f"✅ تم التنظيف! ✅ تم حفظ {saved} حساب",
                               buttons=[[Button.inline("🔄 تحديث", b"refresh_groups")]])
            except Exception as e:
                await event.edit(f"❌ فشل: {e}", buttons=[[Button.inline("🔙 رجوع", b"back")]])

    # معالج الرسائل النصية والوسائط
    @bot.on(events.NewMessage)
    async def message_handler(event):
        if not is_admin(event.sender_id):
            return
        if event.raw_text == '/cancel':
            for key in ['awaiting_msg', 'awaiting_phone', 'awaiting_code', 'awaiting_password',
                       'awaiting_slow_join', 'awaiting_del_msg', 'awaiting_del_acc',
                       'awaiting_msg_interval', 'awaiting_join_interval',
                       'awaiting_fast_delay', 'awaiting_add_blacklist', 'awaiting_del_blacklist',
                       'awaiting_schedule', 'awaiting_schedule_delete']:
                set_setting(key, '')
            if event.sender_id in temp_sessions:
                try:
                    await temp_sessions[event.sender_id]["client"].disconnect()
                except:
                    pass
                del temp_sessions[event.sender_id]
            await event.respond("تم الإلغاء", buttons=get_main_menu())
            return

        # === جدولة النشر ===
        if get_setting('awaiting_schedule') == 'true':
            set_setting('awaiting_schedule', '')
            text = event.raw_text.strip()
            try:
                post_time = None
                repeat_type = 'once'
                repeat_interval = 0

                # Parse "15:30 يومي"
                if 'يومي' in text:
                    time_part = text.replace('يومي', '').strip()
                    hour, minute = map(int, time_part.split(':'))
                    today = datetime.now()
                    post_time = today.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if post_time <= today:
                        post_time += timedelta(days=1)
                    repeat_type = 'daily'

                # Parse "30د كل 60" or "2س كل 120"
                elif 'كل' in text:
                    parts = text.split('كل')
                    first_part = parts[0].strip()
                    repeat_interval = int(parts[1].strip())
                    # Parse the first delay
                    if 'د' in first_part:
                        delay_min = int(first_part.replace('د', '').strip())
                        post_time = datetime.now() + timedelta(minutes=delay_min)
                    elif 'س' in first_part:
                        delay_hours = int(first_part.replace('س', '').strip())
                        post_time = datetime.now() + timedelta(hours=delay_hours)
                    repeat_type = 'repeat'

                # Parse "15:30" (specific time today)
                elif re.match(r'^\d{1,2}:\d{2}$', text):
                    hour, minute = map(int, text.split(':'))
                    today = datetime.now()
                    post_time = today.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if post_time <= today:
                        post_time += timedelta(days=1)

                # Parse "30د" (after 30 minutes)
                elif 'د' in text:
                    delay_min = int(text.replace('د', '').strip())
                    post_time = datetime.now() + timedelta(minutes=delay_min)

                # Parse "2س" (after 2 hours)
                elif 'س' in text:
                    delay_hours = int(text.replace('س', '').strip())
                    post_time = datetime.now() + timedelta(hours=delay_hours)

                if post_time is None:
                    await event.respond(
                        "❌ صيغة غير صحيحة!\n\nاستخدم:\n"
                        "• `15:30` للوقت المحدد\n"
                        "• `30د` للدقائق\n"
                        "• `2س` للساعات\n"
                        "• `30د كل 60` للتكرار\n"
                        "• `15:30 يومي` لليومي",
                        buttons=get_main_menu()
                    )
                    return

                # Get messages count
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM messages")
                msg_count = c.fetchone()[0]
                conn.close()
                if msg_count == 0:
                    await event.respond("⚠️ لا توجد رسائل! أضف رسالة أولاً", buttons=get_main_menu())
                    return

                # Schedule all messages
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT id FROM messages")
                msg_ids = [row[0] for row in c.fetchall()]
                conn.close()

                sched_ids = []
                for msg_id in msg_ids:
                    sched_id = add_scheduled_post(msg_id, post_time.isoformat(), repeat_type, repeat_interval)
                    sched_ids.append(sched_id)

                repeat_text = ""
                if repeat_type == 'repeat':
                    repeat_text = f"\n🔄 يتكرر كل {repeat_interval} دقيقة"
                elif repeat_type == 'daily':
                    repeat_text = "\n📅 يتكرر يومياً"

                await event.respond(
                    f"✅ **تمت الجدولة بنجاح!**\n\n"
                    f"🕐 وقت النشر: {post_time.strftime('%Y-%m-%d %H:%M')}\n"
                    f"📝 عدد الرسائل: {len(msg_ids)}\n"
                    f"📌 أرقام الجدولة: {', '.join(map(str, sched_ids))}"
                    f"{repeat_text}",
                    buttons=get_main_menu()
                )
            except Exception as e:
                await event.respond(f"❌ خطأ: {e}\n\nاستخدم الصيغ المطلوبة", buttons=get_main_menu())
            return

        # === حذف جدولة ===
        if get_setting('awaiting_schedule_delete') == 'true':
            set_setting('awaiting_schedule_delete', '')
            try:
                sched_id = int(event.raw_text.strip())
                delete_scheduled_post(sched_id)
                await event.respond(f"✅ تم حذف الجدولة #{sched_id}", buttons=get_main_menu())
            except:
                await event.respond("❌ رقم غير صالح", buttons=get_main_menu())
            return

        if get_setting('awaiting_fast_delay') == 'true':
            set_setting('awaiting_fast_delay', '')
            try:
                val = int(event.raw_text.strip())
                if 2 <= val <= 30:
                    set_setting('fast_post_delay', str(val))
                    await event.respond(f"✅ تم ضبط سرعة النشر السريع إلى {val} ثانية", buttons=get_main_menu())
                else:
                    await event.respond("❌ الرجاء إدخال قيمة بين 2 و 30 (الحد الأدنى 2)", buttons=get_main_menu())
            except:
                await event.respond("❌ أرسل رقماً صحيحاً", buttons=get_main_menu())
            return
        if get_setting('awaiting_msg_interval') == 'true':
            set_setting('awaiting_msg_interval', '')
            try:
                val = int(event.raw_text.strip())
                if 2 <= val <= 600:
                    set_setting('message_interval', str(val))
                    await event.respond(f"✅ تم الضبط إلى {val} ثانية", buttons=get_main_menu())
                else:
                    await event.respond("❌ بين 2 و 600 (الحد الأدنى 2)", buttons=get_main_menu())
            except:
                await event.respond("❌ رقم غير صالح", buttons=get_main_menu())
            return
        if get_setting('awaiting_join_interval') == 'true':
            set_setting('awaiting_join_interval', '')
            try:
                val = int(event.raw_text.strip())
                if 30 <= val <= 600:
                    set_setting('join_interval', str(val))
                    await event.respond(f"✅ تم الضبط إلى {val} ثانية", buttons=get_main_menu())
                else:
                    await event.respond("❌ بين 30 و 600", buttons=get_main_menu())
            except:
                await event.respond("❌ رقم غير صالح", buttons=get_main_menu())
            return
        # Blacklist add
        if get_setting('awaiting_add_blacklist') == 'true':
            set_setting('awaiting_add_blacklist', '')
            try:
                group_id = event.raw_text.strip()
                group_name = ""
                for acc_id, client in user_clients.items():
                    try:
                        entity = await client.get_entity(int(group_id))
                        group_name = getattr(entity, 'title', str(group_id))
                        break
                    except:
                        continue
                add_to_blacklist(group_id, group_name)
                await event.respond(f"✅ تمت إضافة المجموعة إلى القائمة السوداء: {group_name or group_id}", buttons=get_main_menu())
            except:
                await event.respond("❌ معرف غير صالح", buttons=get_main_menu())
            return
        # Blacklist remove
        if get_setting('awaiting_del_blacklist') == 'true':
            set_setting('awaiting_del_blacklist', '')
            try:
                group_id = event.raw_text.strip()
                remove_from_blacklist(group_id)
                await event.respond(f"✅ تمت إزالة المجموعة من القائمة السوداء: {group_id}", buttons=get_main_menu())
            except:
                await event.respond("❌ معرف غير صالح", buttons=get_main_menu())
            return
        # الروابط - انضمام تلقائي
        links = re.findall(r'(https?://t\.me/(?:joinchat/|\+)?[a-zA-Z0-9_\-]+)', event.raw_text)
        if links and user_clients and not get_setting('awaiting_msg'):
            await event.respond(f"🚀 تم اكتشاف {len(links[:20])} رابط، جاري الانضمام...")
            success, failed, msg = await auto_join_links(links)
            await event.respond(f"📊 النتيجة: ✅ {success} نجاح / ❌ {failed} فشل", buttons=get_main_menu())
            return
        # إضافة رسالة
        if get_setting('awaiting_msg') == 'true':
            set_setting('awaiting_msg', '')
            msg_type = 'text'
            media_path = None
            content = event.raw_text or ""
            media_data = None
            if event.photo:
                msg_type = 'photo'
                os.makedirs('media', exist_ok=True)
                media_path = await bot.download_media(event.message, 'media/')
                content = event.raw_text or ""
            elif event.video:
                msg_type = 'video'
                os.makedirs('media', exist_ok=True)
                media_path = await bot.download_media(event.message, 'media/')
                content = event.raw_text or ""
            elif event.audio:
                msg_type = 'audio'
                os.makedirs('media', exist_ok=True)
                media_path = await bot.download_media(event.message, 'media/')
                content = event.raw_text or ""
            elif event.document:
                msg_type = 'document'
                os.makedirs('media', exist_ok=True)
                media_path = await bot.download_media(event.message, 'media/')
                content = event.raw_text or ""
            elif event.contact:
                msg_type = 'contact'
                contact = event.message.media
                contact_data = {
                    'phone': contact.phone_number,
                    'first_name': contact.first_name,
                    'last_name': contact.last_name or '',
                    'vcard': contact.vcard or ''
                }
                media_data = json.dumps(contact_data)
                content = event.raw_text or f"جهة اتصال: {contact.first_name}"
            elif event.raw_text and event.raw_text.strip():
                msg_type = 'text'
                content = event.raw_text
            else:
                await event.respond("❌ نوع غير مدعوم!", buttons=get_main_menu())
                return
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('INSERT INTO messages (content, media_path, msg_type, media_data) VALUES (?, ?, ?, ?)',
                      (content, media_path, msg_type, media_data))
            conn.commit()
            msg_id = c.lastrowid
            conn.close()
            # Show preview
            varied_preview = vary_text(content[:200]) if content else ""
            obfuscated_preview = obfuscate_for_humans(varied_preview) if content else ""
            encrypted_preview = encrypt_text(obfuscated_preview, 0) if content else ""
            types = {'text':'نص','photo':'صورة','video':'فيديو','audio':'صوت','document':'ملف','contact':'جهة اتصال'}
            await event.respond(
                f"✅ **تم حفظ الرسالة #{msg_id}!**\n\n"
                f"📎 النوع: {types.get(msg_type, msg_type)}\n\n"
                f"💡 التشويش والتشفير يحافظان على المحتوى كما هو\n"
                f"التغييرات غير مرئية للعين - فقط الآلات تكتشفها\n\n"
                f"سيتم تطبيق التشويش + التشفير عند النشر",
                buttons=get_main_menu()
            )
            return
        # إضافة حساب - رقم الهاتف
        if get_setting('awaiting_phone') == 'true':
            set_setting('awaiting_phone', '')
            phone = event.raw_text.strip()
            if not re.match(r'^\+?\d{8,15}$', phone):
                await event.respond("❌ رقم غير صالح! مثال: +966512345678")
                return
            try:
                client = TelegramClient(StringSession(), API_ID, API_HASH)
                await client.connect()
                result = await client.send_code_request(phone)
                temp_sessions[event.sender_id] = {
                    "phone": phone,
                    "client": client,
                    "phone_code_hash": result.phone_code_hash
                }
                set_setting('awaiting_code', 'true')
                await event.respond(f"📩 تم إرسال الرمز إلى {phone}\nأرسل الرمز:")
            except Exception as e:
                await event.respond(f"❌ {str(e)[:200]}")
            return
        if get_setting('awaiting_code') == 'true':
            set_setting('awaiting_code', '')
            code = event.raw_text.strip()
            session_data = temp_sessions.get(event.sender_id)
            if not session_data:
                await event.respond("❌ انتهت الجلسة")
                return
            try:
                await session_data["client"].sign_in(session_data["phone"], code, phone_code_hash=session_data["phone_code_hash"])
                me = await session_data["client"].get_me()
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('INSERT INTO accounts (session_string, phone, status) VALUES (?, ?, ?)',
                          (session_data["client"].session.save(), me.phone, 'active'))
                conn.commit()
                acc_id = c.lastrowid
                conn.close()
                user_clients[acc_id] = session_data["client"]
                group_count = await fetch_all_groups_for_account(acc_id, session_data["client"])
                del temp_sessions[event.sender_id]
                await event.respond(f"✅ تم إضافة {me.phone}\n📢 {group_count} مجموعة", buttons=get_main_menu())
            except SessionPasswordNeededError:
                set_setting('awaiting_password', 'true')
                await event.respond("🔐 أرسل كلمة المرور:")
            except PhoneCodeInvalidError:
                await event.respond("❌ رمز غير صحيح!")
            except Exception as e:
                await event.respond(f"❌ {str(e)[:200]}")
            return
        if get_setting('awaiting_password') == 'true':
            set_setting('awaiting_password', '')
            password = event.raw_text.strip()
            session_data = temp_sessions.get(event.sender_id)
            if not session_data:
                await event.respond("❌ انتهت الجلسة")
                return
            try:
                await session_data["client"].sign_in(password=password)
                me = await session_data["client"].get_me()
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('INSERT INTO accounts (session_string, phone, status) VALUES (?, ?, ?)',
                          (session_data["client"].session.save(), me.phone, 'active'))
                conn.commit()
                acc_id = c.lastrowid
                conn.close()
                user_clients[acc_id] = session_data["client"]
                group_count = await fetch_all_groups_for_account(acc_id, session_data["client"])
                del temp_sessions[event.sender_id]
                await event.respond(f"✅ تم إضافة {me.phone}\n📢 {group_count} مجموعة", buttons=get_main_menu())
            except Exception as e:
                await event.respond(f"❌ {e}")
            return
        if get_setting('awaiting_slow_join') == 'true':
            set_setting('awaiting_slow_join', '')
            links = [l.strip() for l in event.raw_text.split('\n') if l.strip()]
            if links:
                success, failed, msg = await auto_join_links(links)
                await event.respond(f"✅ نجاح: {success}\n❌ فشل: {failed}", buttons=get_main_menu())
            return
        if get_setting('awaiting_del_msg') == 'true':
            set_setting('awaiting_del_msg', '')
            try:
                msg_id = int(event.raw_text.strip())
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('DELETE FROM messages WHERE id=?', (msg_id,))
                conn.commit()
                conn.close()
                await event.respond("✅ تم الحذف", buttons=get_main_menu())
            except:
                await event.respond("❌ رقم غير صالح", buttons=get_main_menu())
            return
        if get_setting('awaiting_del_acc') == 'true':
            set_setting('awaiting_del_acc', '')
            try:
                acc_id = int(event.raw_text.strip())
                if acc_id in user_clients:
                    await user_clients[acc_id].disconnect()
                    del user_clients[acc_id]
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('DELETE FROM accounts WHERE id=?', (acc_id,))
                conn.commit()
                conn.close()
                await event.respond("✅ تم الحذف", buttons=get_main_menu())
            except:
                await event.respond("❌ رقم غير صالح", buttons=get_main_menu())
            return

    # كشف بوتات الحماية
    @bot.on(events.NewMessage(incoming=True))
    async def bot_detection_handler(event):
        if get_setting('bot_detection', 'on') != 'on':
            return
        try:
            text = event.raw_text.lower() if event.raw_text else ""
            warning_keywords = ['حظر', 'تحذير', 'spam', 'إعلان', 'محظور', 'ممنوع', 'تكرار', 'بوت', 'bot', 'protection', 'حماية', 'طرد', 'kick', 'ban']
            sender = await event.get_sender()
            is_bot = getattr(sender, 'bot', False)
            if is_bot and any(kw in text for kw in warning_keywords):
                chat = await event.get_chat()
                log_protected_group(event.chat_id, getattr(chat, 'title', 'Unknown'), getattr(sender, 'username', 'Unknown'))
                logger.warning(f"🛡️ تم اكتشاف بوت حماية")
        except:
            pass

    logger.info("✅ البوت جاهز - مع الحماية القصوى والنشر السريع والتشويش المحسن والجدولة")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
