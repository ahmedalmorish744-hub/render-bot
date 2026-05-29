#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔═══════════════════════════════════════════════════════════════╗
║     🤖 بوت النشر الخارق - الإصدار النهائي (تشفير غير مرئي)  ║
║     النص يبقى كما هو للمستخدم، لكن البوت يراه مشوهاً بالكامل ║
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
from datetime import datetime
from collections import deque

from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, FloodWaitError, PhoneCodeInvalidError, PhoneCodeExpiredError
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import InputMediaContact
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
    
    # القيم الافتراضية
    defaults = {
        'posting_speed': 'fast',
        'message_interval': '2',
        'anti_detect': 'on',
        'encryption': 'on',
        'join_interval': '100',
        'bot_detection': 'on'
    }
    for key, val in defaults.items():
        if get_setting(key) is None:
            set_setting(key, val)
    
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
#  خادم الويب Flask
# ═══════════════════════════════════════════════
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "bot": "Super Poster Bot - Invisible Encryption",
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
#  ═══════════════════════════════════════════════
#  نظام التشفير غير المرئي (يبقي النص كما هو للمستخدم)
#  ═══════════════════════════════════════════════
# ═══════════════════════════════════════════════

class InvisibleEncryption:
    def __init__(self):
        self.invisible_chars = [
            '\u200B', '\u200C', '\u200D', '\uFEFF',
            '\u2060', '\u2061', '\u2062', '\u2063', '\u2064'
        ]
        self.critical_keywords = [
            'اشترك', 'قناة', 'تواصل', 'ربح', 'مجاني', 'عرض', 'سعر', 
            'خصم', 'رابط', 'انضم', 'فوري', 'خدمات', 'طلابية', 'طبية',
            'واجبات', 'بحوث', 'اكسل', 'وورد', 'بوربوينت', 'سيرة', 'ذاتية',
            'أعذار', 'رسمية', 'تقارير', 'همزة', 'وصل', 'تليجرام', 'تيليجرام',
            'https', 'http', 't.me', 'telegram.me', '@', 'بوت', 'قروب', 'مجموعة',
            '✔'
        ]
        self.symbols = ['@', '#', '$', '%', '&', '*', '+', '=', '?', '/', '\\', '|', '~', '`', '.', ',', '!', '؛', '؟']
    
    def obfuscate_text_invisible(self, text):
        if not text:
            return text
        result = text
        for keyword in self.critical_keywords:
            if keyword in result:
                chars = list(keyword)
                new_chars = []
                for ch in chars:
                    new_chars.append(ch)
                    for _ in range(random.randint(2, 4)):
                        new_chars.append(random.choice(self.invisible_chars))
                obfuscated = ''.join(new_chars)
                result = result.replace(keyword, obfuscated)
        result = result.replace('t.me', f't{random.choice(self.invisible_chars)}.{random.choice(self.invisible_chars)}me')
        result = result.replace('telegram.me', f'telegram{random.choice(self.invisible_chars)}.{random.choice(self.invisible_chars)}me')
        result = result.replace('https://', f'https{random.choice(self.invisible_chars)}:{random.choice(self.invisible_chars)}/{random.choice(self.invisible_chars)}/')
        result = result.replace('http://', f'http{random.choice(self.invisible_chars)}:{random.choice(self.invisible_chars)}/{random.choice(self.invisible_chars)}/')
        for sym in self.symbols:
            if sym in result:
                result = result.replace(sym, sym + random.choice(self.invisible_chars))
        words = result.split()
        for i in range(len(words) - 1):
            words[i] = words[i] + random.choice(self.invisible_chars) + random.choice(self.invisible_chars)
        result = ' '.join(words)
        noise = ''.join([random.choice(self.invisible_chars) + str(random.randint(0,9)) for _ in range(8)])
        result = result + noise
        return result
    
    def encrypt(self, text):
        if get_setting('anti_detect', 'on') != 'on':
            return text
        return self.obfuscate_text_invisible(text)

invisible_encryption = InvisibleEncryption()

def encrypt_text(text):
    return invisible_encryption.encrypt(text)

# ═══════════════════════════════════════════════
#  تنسيق الإعلان (بدون أي إضافات مرئية - يبقى النص الأصلي)
# ═══════════════════════════════════════════════
def format_ad_original(text):
    return text

# ═══════════════════════════════════════════════
#  إدارة الحسابات والمجموعات
# ═══════════════════════════════════════════════
user_clients = {}
temp_sessions = {}
is_posting_active = False
is_joining_active = False

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
#  نظام النشر السريع مع التشفير غير المرئي
# ═══════════════════════════════════════════════
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

async def fast_post_to_all_groups(message):
    global is_posting_active
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT group_id, group_name FROM groups WHERE is_protected=0")
    groups = c.fetchall()
    conn.close()
    if not groups:
        return 0, "لا توجد مجموعات"
    msg_id = message[0]
    content = message[1]
    media_path = message[2]
    msg_type = message[3]
    media_data = message[4] if len(message) > 4 else None
    
    original_content = content if content else ""
    encrypted_content = encrypt_text(original_content)
    
    success_count = 0
    fail_count = 0
    delay = int(get_setting('message_interval', '2'))
    total_groups = len(groups)
    logger.info(f"⚡ بدء النشر السريع في {total_groups} مجموعة (كل {delay} ثانية)")
    
    for group_id, group_name in groups:
        if not is_posting_active:
            break
        available_accs = await get_available_accounts()
        if not available_accs:
            logger.warning("⚠️ لا توجد حسابات متاحة، انتظار...")
            await asyncio.sleep(5)
            continue
        acc_id = random.choice(available_accs)
        client = user_clients.get(acc_id)
        if not client:
            continue
        try:
            await asyncio.sleep(delay)
            if not is_posting_active:
                break
            if msg_type == 'text':
                await client.send_message(int(group_id), encrypted_content)
            elif msg_type == 'photo' and media_path and os.path.exists(media_path):
                await client.send_file(int(group_id), media_path, caption=encrypted_content)
            elif msg_type == 'contact' and media_data:
                contact_data = json.loads(media_data) if isinstance(media_data, str) else media_data
                await send_contact_message(client, int(group_id), contact_data, encrypted_content)
            else:
                if media_path and os.path.exists(media_path):
                    await client.send_file(int(group_id), media_path, caption=encrypted_content)
                else:
                    await client.send_message(int(group_id), encrypted_content)
            success_count += 1
            log_posting(acc_id, int(group_id), msg_id, 'success')
            logger.info(f"⚡ سريع ✅ [{success_count}/{total_groups}] {group_name[:30]}")
        except FloodWaitError as e:
            logger.warning(f"⏸ FloodWait: {e.seconds}ث")
            set_account_cooldown(acc_id, time.time() + e.seconds)
            fail_count += 1
            await asyncio.sleep(5)
        except Exception as e:
            fail_count += 1
            logger.error(f"❌ فشل: {e}")
    return success_count, fail_count

def log_posting(account_id, group_id, message_id, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO posting_history (account_id, group_id, message_id, status, posted_at)
                 VALUES (?, ?, ?, ?, ?)''', (account_id, group_id, message_id, status, datetime.now()))
    conn.commit()
    conn.close()

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
    for session_str, phone, status in accounts:
        c.execute('INSERT INTO accounts (session_string, phone, status) VALUES (?, ?, ?)',
                  (session_str, phone, status))
    conn.commit()
    conn.close()
    return len(accounts)

# ═══════════════════════════════════════════════
#  لوحة التحكم
# ═══════════════════════════════════════════════
def get_main_menu():
    anti_status = "✅" if get_setting('anti_detect', 'on') == 'on' else "❌"
    message_interval = get_setting('message_interval', '2')
    join_interval = get_setting('join_interval', '100')
    posting_speed = get_setting('posting_speed', 'fast')
    speed_icon = "⚡" if posting_speed == 'fast' else "🐌" if posting_speed == 'normal' else "🐢"
    return [
        [Button.inline("📝 إدارة الرسائل", b"messages")],
        [Button.inline("👥 إدارة الحسابات", b"accounts")],
        [Button.inline("📢 إدارة المجموعات", b"groups")],
        [Button.inline("⚡ نشر سريع", b"fast_posting"),
         Button.inline("⏹ إيقاف الكل", b"stop_posting")],
        [Button.inline(f"{speed_icon} سرعة النشر", b"posting_speed"),
         Button.inline("🔄 مسح تبريد", b"clear_cooldowns")],
        [Button.inline(f"🛡 التشفير الخارق {anti_status}", b"toggle_anti")],
        [Button.inline("⚙️ الإعدادات", b"settings"),
         Button.inline("📊 الإحصائيات", b"stats")],
        [Button.inline(f"🐢 انضمام ({join_interval}ث)", b"slow_join"),
         Button.inline("📋 تقارير الانضمام", b"join_reports")],
        [Button.inline("🛡️ المجموعات المحمية", b"protected_groups")],
        [Button.inline("🗑 تنظيف قاعدة البيانات", b"clean_db")],
        [Button.inline("🔄 تحديث المجموعات", b"refresh_groups")],
    ]

def get_join_reports_menu():
    return [
        [Button.inline("📊 إحصائيات الانضمام", b"join_stats")],
        [Button.inline("📋 سجل الانضمام", b"join_history")],
        [Button.inline("🔙 رجوع", b"back")],
    ]

def get_settings_menu():
    anti_status = "✅" if get_setting('anti_detect', 'on') == 'on' else "❌"
    return [
        [Button.inline(f"🛡 تبديل التشفير الخارق {anti_status}", b"toggle_anti")],
        [Button.inline("🐢 مدة الانضمام", b"set_join_interval")],
        [Button.inline("🔙 رجوع", b"back")]
    ]

def get_speed_menu():
    current_speed = get_setting('posting_speed', 'fast')
    return [
        [Button.inline("⚡ سريع (2 ثانية)", b"set_speed_fast"),
         Button.inline("✅" if current_speed == 'fast' else "⬜", b"dummy")],
        [Button.inline("🐌 عادي (60 ثانية)", b"set_speed_normal"),
         Button.inline("✅" if current_speed == 'normal' else "⬜", b"dummy")],
        [Button.inline("🐢 بطيء (120 ثانية)", b"set_speed_slow"),
         Button.inline("✅" if current_speed == 'slow' else "⬜", b"dummy")],
        [Button.inline("🔙 رجوع", b"back")]
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
    logger.info("🤖 البوت يعمل - تشفير غير مرئي تماماً")

    @bot.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        if not is_admin(event.sender_id):
            return
        groups_count = await get_all_groups_count()
        message_interval = get_setting('message_interval', '2')
        join_interval = get_setting('join_interval', '100')
        example_text = "همزة وصل - خدمات طلابية كاملة"
        encrypted_example = encrypt_text(example_text)
        await event.respond(
            "🛡 **بوت النشر الخارق - تشفير غير مرئي**\n\n"
            "✨ **المميزات:**\n"
            "• 🔒 تشفير خارق غير مرئي للمستخدم\n"
            "• 🤖 بوتات الحماية ترى نصاً مشوهاً بالكامل\n"
            "• ⚡ نشر سريع (ثانيتين بين المجموعات)\n"
            "• 🐢 انضمام بطيء لحماية الحسابات\n\n"
            f"📝 **مثال: النص الأصلي (كما يراه المستخدم)**\n{example_text}\n\n"
            f"🔐 **ما يراه بوت الحماية (مشوّه بالكامل)**\n`{encrypted_example[:200]}...`\n\n"
            f"📢 المجموعات: {groups_count}\n"
            f"⚡ سرعة النشر: {message_interval} ثانية\n"
            f"🐢 مدة الانضمام: {join_interval} ثانية\n\n"
            "اختر من القائمة:",
            buttons=get_main_menu()
        )

    @bot.on(events.NewMessage(pattern='/fast_post'))
    async def fast_post_cmd(event):
        if not is_admin(event.sender_id):
            return
        groups_count = await get_all_groups_count()
        if groups_count == 0:
            await event.respond("⚠️ لا توجد مجموعات! اضغط 'تحديث المجموعات' أولاً")
            return
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, content, media_path, msg_type, media_data FROM messages LIMIT 1")
        msg = c.fetchone()
        conn.close()
        if not msg:
            await event.respond("⚠️ لا توجد رسائل! أضف رسالة أولاً")
            return
        await event.respond(f"⚡ بدء النشر السريع في {groups_count} مجموعة...")
        global is_posting_active
        is_posting_active = True
        success, fails = await fast_post_to_all_groups(msg)
        is_posting_active = False
        await event.respond(f"✅ اكتمل النشر!\n✅ نجاح: {success}\n❌ فشل: {fails}")

    @bot.on(events.CallbackQuery)
    async def callback_handler(event):
        global is_posting_active
        if not is_admin(event.sender_id):
            await event.answer("⛔ غير مصرح", alert=True)
            return
        data = event.data.decode('utf-8')
        if data == 'back':
            groups_count = await get_all_groups_count()
            message_interval = get_setting('message_interval', '2')
            join_interval = get_setting('join_interval', '100')
            await event.edit(
                "🛡 **لوحة التحكم**\n\n"
                f"📢 المجموعات: {groups_count}\n"
                f"⚡ سرعة النشر: {message_interval} ثانية\n"
                f"🐢 مدة الانضمام: {join_interval} ثانية",
                buttons=get_main_menu()
            )
        elif data == 'fast_posting':
            await event.answer("⚡ جاري النشر السريع...", alert=True)
            groups_count = await get_all_groups_count()
            msg_count = await get_all_messages_count()
            if groups_count == 0:
                await event.edit("⚠️ لا توجد مجموعات!\nاضغط 'تحديث المجموعات' أولاً", 
                               buttons=[[Button.inline("🔄 تحديث المجموعات", b"refresh_groups")]])
                return
            if msg_count == 0:
                await event.edit("⚠️ لا توجد رسائل!\nأضف رسالة أولاً", 
                               buttons=[[Button.inline("➕ إضافة", b"add_msg")]])
                return
            if is_posting_active:
                await event.edit("⚠️ النشر يعمل بالفعل!", buttons=[[Button.inline("🔙 رجوع", b"back")]])
                return
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id, content, media_path, msg_type, media_data FROM messages LIMIT 1")
            msg = c.fetchone()
            conn.close()
            if not msg:
                await event.edit("⚠️ لا توجد رسائل!", buttons=[[Button.inline("➕ إضافة", b"add_msg")]])
                return
            is_posting_active = True
            message_interval = get_setting('message_interval', '2')
            await event.edit(
                f"⚡ **النشر السريع قيد التشغيل!**\n\n"
                f"📢 {groups_count} مجموعة\n"
                f"⏱ {message_interval} ثانية بين كل مجموعة\n"
                f"🔒 تشفير غير مرئي ضد البوتات\n\n"
                f"جاري النشر...",
                buttons=[[Button.inline("⏹ إيقاف", b"stop_posting")]]
            )
            success, fails = await fast_post_to_all_groups(msg)
            is_posting_active = False
            await event.edit(
                f"✅ **اكتمل النشر السريع!**\n\n"
                f"✅ نجاح: {success}\n"
                f"❌ فشل: {fails}\n"
                f"📢 من أصل {groups_count} مجموعة\n"
                f"🔒 تم استخدام التشفير غير المرئي",
                buttons=[[Button.inline("🔙 رجوع", b"back")]]
            )
        elif data == 'stop_posting':
            is_posting_active = False
            await event.edit("⏹ **تم إيقاف النشر**", buttons=[[Button.inline("🔙 رجوع", b"back")]])
        elif data == 'posting_speed':
            await event.edit("⚡ **سرعة النشر**\n\nاختر السرعة المناسبة:", buttons=get_speed_menu())
        elif data == 'set_speed_fast':
            set_setting('posting_speed', 'fast')
            set_setting('message_interval', '2')
            await event.answer("✅ تم ضبط السرعة: سريع")
            await event.edit("⚡ تم ضبط سرعة النشر إلى **سريع (ثانيتين بين المجموعات)**", 
                           buttons=[[Button.inline("🔙 رجوع", b"back")]])
        elif data == 'set_speed_normal':
            set_setting('posting_speed', 'normal')
            set_setting('message_interval', '60')
            await event.answer("✅ تم ضبط السرعة: عادي")
            await event.edit("🐌 تم ضبط سرعة النشر إلى **عادي (60 ثانية)**", 
                           buttons=[[Button.inline("🔙 رجوع", b"back")]])
        elif data == 'set_speed_slow':
            set_setting('posting_speed', 'slow')
            set_setting('message_interval', '120')
            await event.answer("✅ تم ضبط السرعة: بطيء")
            await event.edit("🐢 تم ضبط سرعة النشر إلى **بطيء (120 ثانية)**", 
                           buttons=[[Button.inline("🔙 رجوع", b"back")]])
        elif data == 'clear_cooldowns':
            clear_all_cooldowns()
            await event.answer("✅ تم مسح التبريد!", alert=True)
            await event.edit("✅ تم مسح تبريد جميع الحسابات", buttons=[[Button.inline("🔙 رجوع", b"back")]])
        elif data == 'messages':
            await event.edit("📝 **إدارة الرسائل**", buttons=[
                [Button.inline("➕ إضافة رسالة", b"add_msg")],
                [Button.inline("📋 عرض الرسائل", b"list_msg")],
                [Button.inline("🗑 حذف رسالة", b"del_msg")],
                [Button.inline("🔙 رجوع", b"back")],
            ])
        elif data == 'add_msg':
            await event.edit(
                "➕ **إضافة رسالة جديدة**\n\n"
                "أرسل الإعلان كما تريد نشره:\n"
                "• سيتم تطبيق التشفير الخارق تلقائياً\n"
                "• يمكنك إرسال نص، صورة، فيديو، ملف أو جهة اتصال\n\n"
                "📝 مثال للإعلان:\n"
                "همزة وصل  \n"
                "✔ خدمات طلابية كامله  \n"
                "1.واجبات 2.بحوث 3.شغل اكسل وورد بوربوينت  \n\n"
                "/cancel للإلغاء"
            )
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
                text = "📋 **الرسائل المحفوظة:**\n\n"
                for mid, content, mtype in msgs:
                    icons = {'text':'📝','photo':'📷','video':'🎬','audio':'🎵','document':'📄','contact':'👤'}
                    text += f"{icons.get(mtype,'📦')} #{mid} [{mtype}] - {content[:30]}...\n"
                await event.edit(text, buttons=[[Button.inline("🔙 رجوع", b"messages")]])
        elif data == 'del_msg':
            await event.edit("🗑 أرسل رقم الرسالة:\n/cancel للإلغاء")
            set_setting('awaiting_del_msg', 'true')
        elif data == 'accounts':
            await event.edit("👥 **إدارة الحسابات**", buttons=[
                [Button.inline("➕ إضافة حساب", b"add_acc")],
                [Button.inline("📋 عرض الحسابات", b"list_acc")],
                [Button.inline("🗑 حذف حساب", b"del_acc")],
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
        elif data == 'groups':
            await event.edit("📢 **إدارة المجموعات**", buttons=[
                [Button.inline("📋 عرض المجموعات", b"list_groups")],
                [Button.inline("🗑 حذف مجموعة", b"del_group")],
                [Button.inline("🗑 حذف الكل", b"del_all_groups")],
                [Button.inline("🔙 رجوع", b"back")],
            ])
        elif data == 'list_groups':
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id, group_name, member_count, is_protected FROM groups LIMIT 50")
            grps = c.fetchall()
            conn.close()
            if not grps:
                await event.edit("📢 لا توجد مجموعات\nاضغط 'تحديث المجموعات' أولاً", 
                               buttons=[[Button.inline("🔄 تحديث المجموعات", b"refresh_groups")]])
            else:
                text = "📢 **المجموعات:**\n\n"
                for gid, gname, members, protected in grps:
                    shield = "🛡️" if protected else ""
                    text += f"📌 #{gid} {shield} - {gname[:30]} ({members or 0} عضو)\n"
                await event.edit(text, buttons=[[Button.inline("🔙 رجوع", b"groups")]])
        elif data == 'del_group':
            await event.edit("🗑 أرسل رقم المجموعة:\n/cancel للإلغاء")
            set_setting('awaiting_del_group', 'true')
        elif data == 'del_all_groups':
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM groups")
            conn.commit()
            conn.close()
            await event.edit("🗑 تم حذف جميع المجموعات", buttons=[[Button.inline("🔙 رجوع", b"groups")]])
        elif data == 'refresh_groups':
            await event.edit("🔄 جاري تحديث المجموعات...")
            total = 0
            for acc_id, client in user_clients.items():
                count = await fetch_all_groups_for_account(acc_id, client)
                total += count
            await event.edit(f"✅ تم تحديث {total} مجموعة", buttons=[[Button.inline("🔙 رجوع", b"back")]])
        elif data == 'settings':
            await event.edit(
                "⚙️ **الإعدادات**\n\n"
                f"⚡ سرعة النشر: {get_setting('message_interval', '2')} ثانية\n"
                f"🐢 مدة الانضمام: {get_setting('join_interval', '100')} ثانية\n"
                f"🛡 التشفير الخارق: {get_setting('anti_detect', 'on')}\n"
                f"🤖 كشف البوتات: {get_setting('bot_detection', 'on')}",
                buttons=get_settings_menu()
            )
        elif data == 'set_join_interval':
            await event.edit("🐢 أرسل المدة بين الروابط (30-600 ثانية):\n/cancel للإلغاء")
            set_setting('awaiting_join_interval', 'true')
        elif data == 'toggle_anti':
            current = get_setting('anti_detect', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('anti_detect', new_val)
            await event.answer(f"التشفير الخارق: {'مفعل' if new_val == 'on' else 'معطل'}")
            await event.edit("⚙️ الإعدادات", buttons=get_settings_menu())
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
            join_stats = get_join_stats()
            conn.close()
            await event.edit(
                f"📊 **الإحصائيات**\n\n"
                f"📝 الرسائل: {msg_count}\n"
                f"👥 الحسابات: {acc_count}\n"
                f"📢 المجموعات: {grp_count}\n"
                f"🛡️ محمية: {protected_count}\n"
                f"✅ نجاح: {success_count}\n"
                f"❌ فشل: {fail_count}\n"
                f"🔗 انضمام: {join_stats['total']} (نجاح: {join_stats['success']})",
                buttons=[[Button.inline("🔙 رجوع", b"back")]]
            )
        elif data == 'slow_join':
            await event.edit("🐢 **انضمام بطيء**\n\nأرسل روابط المجموعات (رابط في كل سطر):\n/cancel للإلغاء")
            set_setting('awaiting_slow_join', 'true')
        elif data == 'join_reports':
            await event.edit("🔗 **تقارير الانضمام**", buttons=get_join_reports_menu())
        elif data == 'join_stats':
            stats = get_join_stats()
            await event.edit(
                f"📊 **إحصائيات الانضمام**\n\n"
                f"📌 المجموع: {stats['total']}\n"
                f"✅ نجاح: {stats['success']}\n"
                f"❌ فشل: {stats['failed']}\n"
                f"📈 النسبة: {stats['success']/(stats['total'] or 1)*100:.1f}%",
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
                set_setting('message_interval', '2')
                set_setting('join_interval', '100')
                set_setting('anti_detect', 'on')
                await event.edit(f"✅ تم التنظيف! ✅ تم حفظ {saved} حساب", 
                               buttons=[[Button.inline("🔄 تحديث المجموعات", b"refresh_groups")]])
            except Exception as e:
                await event.edit(f"❌ فشل: {e}", buttons=[[Button.inline("🔙 رجوع", b"back")]])

    @bot.on(events.NewMessage)
    async def message_handler(event):
        if not is_admin(event.sender_id):
            return
        if event.raw_text == '/cancel':
            for key in ['awaiting_msg', 'awaiting_phone', 'awaiting_code', 'awaiting_password',
                       'awaiting_slow_join', 'awaiting_del_msg', 'awaiting_del_acc', 
                       'awaiting_del_group', 'awaiting_join_interval']:
                set_setting(key, '')
            if event.sender_id in temp_sessions:
                try:
                    await temp_sessions[event.sender_id]["client"].disconnect()
                except:
                    pass
                del temp_sessions[event.sender_id]
            await event.respond("تم الإلغاء", buttons=get_main_menu())
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
        links = re.findall(r'(https?://t\.me/(?:joinchat/|\+)?[a-zA-Z0-9_\-]+)', event.raw_text)
        if links and user_clients and not get_setting('awaiting_msg'):
            await event.respond(f"🚀 تم اكتشاف {len(links[:20])} رابط، جاري الانضمام...")
            success, failed, msg = await auto_join_links(links)
            await event.respond(f"📊 النتيجة: ✅ {success} نجاح / ❌ {failed} فشل", buttons=get_main_menu())
            return
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
            encrypted_preview = encrypt_text(content[:200]) if content else ""
            types = {'text':'نص','photo':'صورة','video':'فيديو','audio':'صوت','document':'ملف','contact':'جهة اتصال'}
            await event.respond(
                f"✅ **تم حفظ الرسالة #{msg_id}!**\n\n"
                f"📎 النوع: {types.get(msg_type, msg_type)}\n"
                f"🎨 **النص الأصلي (كما يراه المستخدم):**\n```\n{content}\n```\n\n"
                f"🔒 **ما يراه بوت الحماية (مشوّه):**\n`{encrypted_preview}`\n\n"
                f"⚡ سيتم تطبيق التشفير غير المرئي عند النشر",
                buttons=get_main_menu()
            )
            return
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
        if get_setting('awaiting_del_group') == 'true':
            set_setting('awaiting_del_group', '')
            try:
                grp_id = int(event.raw_text.strip())
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('DELETE FROM groups WHERE id=?', (grp_id,))
                conn.commit()
                conn.close()
                await event.respond("✅ تم الحذف", buttons=get_main_menu())
            except:
                await event.respond("❌ رقم غير صالح", buttons=get_main_menu())
            return

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

    logger.info("✅ البوت جاهز - تشفير غير مرئي تماماً!")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
