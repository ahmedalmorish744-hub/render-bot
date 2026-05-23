#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔═══════════════════════════════════════════════════════════════╗
║     🤖 بوت النشر الخارق - النسخة النهائية 🚀                  ║
║     دعم عدة أدمن + انضمام تلقائي + تشفير متقدم               ║
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

from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, FloodWaitError, PhoneCodeInvalidError, PhoneCodeExpiredError
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest
from flask import Flask, jsonify

# ═══════════════════════════════════════════════
#  الإعدادات - تُقرأ من متغيرات البيئة
# ═══════════════════════════════════════════════
API_ID = int(os.environ.get('API_ID', '0'))
API_HASH = os.environ.get('API_HASH', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
PORT = int(os.environ.get('PORT', '10000'))

# قراءة ADMIN_IDS كقائمة (متغير جديد)
ADMIN_IDS_RAW = os.environ.get('ADMIN_IDS', os.environ.get('ADMIN_ID', '0'))
ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS_RAW.split(',') if x.strip().isdigit()]

def is_admin(user_id):
    """التحقق مما إذا كان المستخدم من الأدمن"""
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
#  قاعدة البيانات SQLite
# ═══════════════════════════════════════════════
DB_PATH = os.environ.get('DB_PATH', 'bot_database.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT, media_path TEXT, msg_type TEXT DEFAULT 'text',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_string TEXT, phone TEXT,
        status TEXT DEFAULT 'active',
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER, group_name TEXT,
        username TEXT, member_count INTEGER,
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
#  خادم الويب Flask
# ═══════════════════════════════════════════════
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "bot": "Super Poster Bot v5.0",
        "uptime": datetime.now().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

def run_web():
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)

# ═══════════════════════════════════════════════
#  نظام الإبقاء على البوت نشطاً (بدون aiohttp)
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
#  نظام التشفير المتقدم
# ═══════════════════════════════════════════════
class UltraAdvancedEncryption:
    def __init__(self):
        self.zero_width_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF', '\u2060', '\u2061', '\u2062', '\u2063', '\u2064']
        self.homoglyphs = {
            'a': ['а', 'α', '⍺', 'ａ'], 'b': ['Ь', 'β', 'в', 'ｂ'], 'c': ['с', 'ϲ', 'ⅽ', 'ｃ'],
            'e': ['е', 'ε', 'ё', 'ｅ'], 'h': ['һ', 'н', 'հ', 'ｈ'], 'i': ['і', 'ɪ', 'ι', 'ｉ'],
            'k': ['κ', 'к', 'ｋ'], 'o': ['о', 'ο', 'σ', 'ｏ'], 'p': ['р', 'ρ', 'ｐ'],
            'x': ['х', '×', 'ⅹ', 'ｘ'], 'y': ['у', 'γ', 'ｙ'], 'A': ['Α', 'А', 'Ａ'],
            'B': ['В', 'Β', 'Ｂ'], 'C': ['С', 'Ｃ'], 'E': ['Е', 'Ε', 'Ｅ'],
            'H': ['Н', 'Ｈ'], 'K': ['Κ', 'Ｋ'], 'M': ['Μ', 'Ｍ'], 'O': ['Ο', 'О', 'Ｏ'],
            'P': ['Ρ', 'Р', 'Ｐ'], 'T': ['Τ', 'Т', 'Ｔ'], 'X': ['Χ', 'Х', 'Ｘ'],
        }
        self.direction_override = '\u202E'
    
    def apply_homoglyphs(self, text, intensity=0.2):
        result = []
        for char in text:
            if char in self.homoglyphs and random.random() < intensity:
                result.append(random.choice(self.homoglyphs[char]))
            else:
                result.append(char)
        return ''.join(result)
    
    def add_zero_width_chars(self, text, intensity=0.05):
        if random.random() > 0.7:
            chars = list(text)
            for i in range(len(chars)):
                if random.random() < intensity:
                    chars.insert(i, random.choice(self.zero_width_chars))
            return ''.join(chars)
        return text
    
    def add_invisible_spaces(self, text):
        words = text.split()
        for i in range(len(words) - 1):
            if random.random() > 0.92:
                words[i] += random.choice(self.zero_width_chars)
        return ' '.join(words)
    
    def encrypt(self, text):
        if get_setting('encryption', 'on') != 'on':
            return text
        result = text
        result = self.apply_homoglyphs(result, intensity=0.2)
        result = self.add_zero_width_chars(result, intensity=0.05)
        result = self.add_invisible_spaces(result)
        if random.random() > 0.97:
            result = result + self.direction_override
        return result

ultra_encryption = UltraAdvancedEncryption()

def encrypt_text(text):
    return ultra_encryption.encrypt(text)

def generate_text_variation(text):
    if get_setting('anti_detect', 'on') != 'on':
        return text
    return encrypt_text(text)

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
    c.execute("SELECT COUNT(*) FROM groups")
    count = c.fetchone()[0]
    conn.close()
    return count

# ═══════════════════════════════════════════════
#  نظام الانضمام التلقائي
# ═══════════════════════════════════════════════
async def auto_join_links(links):
    global is_joining_active
    
    if is_joining_active:
        return 0, 0, "يوجد عملية انضمام قيد التنفيذ"
    
    is_joining_active = True
    
    if not user_clients:
        is_joining_active = False
        return 0, 0, "لا توجد حسابات نشطة"
    
    acc_id = random.choice(list(user_clients.keys()))
    client = user_clients[acc_id]
    
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
            logger.info(f"⏸ انتظار {join_interval} ثانية قبل الرابط {i}/{len(clean_links)}")
            await asyncio.sleep(join_interval)
            
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
            await asyncio.sleep(e.seconds)
            failed_count += 1
            save_join_history(link, 0, "غير معروف", 'failed: flood wait', f"account_{acc_id}")
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
#  نظام النشر
# ═══════════════════════════════════════════════
async def post_to_groups(message_content, msg_type='text', media_path=None):
    global is_posting_active
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT group_id, group_name FROM groups")
    groups = c.fetchall()
    c.execute("SELECT id FROM accounts WHERE status='active'")
    accounts = c.fetchall()
    conn.close()

    if not groups:
        return 0, "لا توجد مجموعات"
    if not accounts:
        return 0, "لا توجد حسابات"

    success_count = 0
    fail_count = 0
    account_list = list(accounts)
    random.shuffle(account_list)
    message_interval = int(get_setting('message_interval', '60'))

    for idx, (group_id, group_name) in enumerate(groups):
        if not is_posting_active:
            break
            
        acc_id = account_list[idx % len(account_list)][0]
        client = user_clients.get(acc_id)
        if not client:
            continue

        try:
            variation = generate_text_variation(message_content)
            
            for _ in range(message_interval):
                if not is_posting_active:
                    break
                await asyncio.sleep(1)
            
            if not is_posting_active:
                break

            if msg_type == 'text':
                await client.send_message(int(group_id), variation)
            elif msg_type == 'photo' and media_path:
                await client.send_file(int(group_id), media_path, caption=variation)

            success_count += 1
            log_posting(acc_id, int(group_id), 0, 'success')
            logger.info(f"✅ نشر في {group_name[:30]}")

        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            fail_count += 1
            log_posting(acc_id, int(group_id), 0, 'failed: flood wait')
        except Exception as e:
            fail_count += 1
            log_posting(acc_id, int(group_id), 0, f'failed: {str(e)[:50]}')
            logger.error(f"❌ فشل النشر: {e}")

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
    
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content TEXT, media_path TEXT, msg_type TEXT DEFAULT 'text',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_string TEXT, phone TEXT,
        status TEXT DEFAULT 'active',
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER, group_name TEXT,
        username TEXT, member_count INTEGER,
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
    enc_status = "✅" if get_setting('encryption', 'on') == 'on' else "❌"
    anti_status = "✅" if get_setting('anti_detect', 'on') == 'on' else "❌"
    message_interval = get_setting('message_interval', '60')
    join_interval = get_setting('join_interval', '100')
    
    return [
        [Button.inline("📝 إدارة الرسائل", b"messages")],
        [Button.inline("👥 إدارة الحسابات", b"accounts")],
        [Button.inline("📢 إدارة المجموعات", b"groups")],
        [Button.inline("🚀 بدء النشر", b"start_posting"),
         Button.inline("⏹ إيقاف النشر", b"stop_posting")],
        [Button.inline(f"🛡 التشفير {enc_status}", b"toggle_enc"),
         Button.inline(f"🎭 مكافحة الكشف {anti_status}", b"toggle_anti")],
        [Button.inline("⚙️ الإعدادات", b"settings"),
         Button.inline("📊 الإحصائيات", b"stats")],
        [Button.inline(f"🐢 انضمام ({join_interval}ث)", b"slow_join"),
         Button.inline("📋 تقارير الانضمام", b"join_reports")],
        [Button.inline(f"⏱ مدة النشر ({message_interval}ث)", b"set_msg_interval"),
         Button.inline("🐢 مدة الانضمام", b"set_join_interval")],
        [Button.inline("🗑 تنظيف قاعدة البيانات", b"clean_db")],
        [Button.inline("🔄 تحديث المجموعات", b"refresh_groups")],
    ]

def get_join_reports_menu():
    return [
        [Button.inline("📊 إحصائيات الانضمام", b"join_stats")],
        [Button.inline("📋 سجل الانضمام", b"join_history")],
        [Button.inline("🔙 رجوع", b"back")],
    ]

# ═══════════════════════════════════════════════
#  البوت الرئيسي
# ═══════════════════════════════════════════════
async def main():
    # بدء خادم الويب
    Thread(target=run_web, daemon=True).start()
    logger.info(f"🌐 خادم الويب يعمل على المنفذ {PORT}")
    
    # بدء نظام الإبقاء على البوت نشطاً
    asyncio.create_task(keep_alive_ping())
    logger.info("🔄 نظام الإبقاء على البوت نشطاً يعمل")

    # تهيئة قاعدة البيانات
    init_db()

    # تعيين القيم الافتراضية
    if get_setting('message_interval') is None:
        set_setting('message_interval', '60')
    if get_setting('join_interval') is None:
        set_setting('join_interval', '100')
    if get_setting('min_delay') is None:
        set_setting('min_delay', '3')
    if get_setting('max_delay') is None:
        set_setting('max_delay', '8')
    if get_setting('encryption') is None:
        set_setting('encryption', 'on')
    if get_setting('anti_detect') is None:
        set_setting('anti_detect', 'on')

    # استعادة جلسات الحسابات
    await restore_sessions()

    # إنشاء عميل البوت
    bot = TelegramClient('bot_session', API_ID, API_HASH)
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("🤖 البوت يعمل بنجاح!")

    # ─── أمر /start ───
    @bot.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        if not is_admin(event.sender_id):
            return
        groups_count = await get_all_groups_count()
        message_interval = get_setting('message_interval', '60')
        join_interval = get_setting('join_interval', '100')
        await event.respond(
            "🤖 **بوت النشر الخارق v5.0**\n\n"
            "مرحباً بك في لوحة التحكم!\n\n"
            f"📢 المجموعات: {groups_count}\n"
            f"⏱ مدة النشر: {message_interval} ثانية\n"
            f"🐢 مدة الانضمام: {join_interval} ثانية\n\n"
            "اختر من القائمة:",
            buttons=get_main_menu()
        )

    # ─── حلقة النشر ───
    async def auto_posting_loop(bot):
        global is_posting_active
        while is_posting_active:
            try:
                if not is_posting_active:
                    break
                    
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT content, msg_type, media_path FROM messages")
                msgs = c.fetchall()
                conn.close()

                if not msgs:
                    is_posting_active = False
                    break

                for content, msg_type, media_path in msgs:
                    if not is_posting_active:
                        break
                        
                    success, fails = await post_to_groups(content, msg_type, media_path)
                    logger.info(f"📤 نشر: نجاح={success}, فشل={fails}")

                    if not is_posting_active:
                        break

                    message_interval = int(get_setting('message_interval', '60'))
                    for _ in range(message_interval * 2):
                        if not is_posting_active:
                            break
                        await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"خطأ: {e}")
                await asyncio.sleep(5)
        
        logger.info("✅ توقف النشر")

    # ─── معالج الأزرار ───
    @bot.on(events.CallbackQuery)
    async def callback_handler(event):
        if not is_admin(event.sender_id):
            await event.answer("⛔ غير مصرح", alert=True)
            return

        data = event.data.decode('utf-8')

        if data == 'back':
            groups_count = await get_all_groups_count()
            message_interval = get_setting('message_interval', '60')
            join_interval = get_setting('join_interval', '100')
            await event.edit(
                "🤖 **لوحة التحكم**\n\n"
                f"📢 المجموعات: {groups_count}\n"
                f"⏱ مدة النشر: {message_interval} ثانية\n"
                f"🐢 مدة الانضمام: {join_interval} ثانية",
                buttons=get_main_menu()
            )

        elif data == 'messages':
            await event.edit("📝 **إدارة الرسائل**", buttons=[
                [Button.inline("➕ إضافة", b"add_msg")],
                [Button.inline("📋 عرض", b"list_msg")],
                [Button.inline("🗑 حذف", b"del_msg")],
                [Button.inline("🔙 رجوع", b"back")],
            ])

        elif data == 'add_msg':
            await event.edit("➕ أرسل نص الرسالة:\n/cancel للإلغاء")
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
                    text += f"#{mid} [{mtype}] - {content}...\n"
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
            c.execute("SELECT id, phone, status FROM accounts")
            accs = c.fetchall()
            conn.close()
            if not accs:
                await event.edit("👥 لا توجد حسابات", buttons=[[Button.inline("🔙 رجوع", b"accounts")]])
            else:
                text = "👥 **الحسابات:**\n\n"
                for aid, phone, status in accs:
                    emoji = "✅" if status == 'active' else "❌"
                    text += f"{emoji} #{aid} - {phone}\n"
                await event.edit(text, buttons=[[Button.inline("🔙 رجوع", b"accounts")]])

        elif data == 'del_acc':
            await event.edit("🗑 أرسل رقم الحساب:\n/cancel للإلغاء")
            set_setting('awaiting_del_acc', 'true')

        elif data == 'groups':
            await event.edit("📢 **إدارة المجموعات**", buttons=[
                [Button.inline("📋 عرض", b"list_groups")],
                [Button.inline("🗑 حذف مجموعة", b"del_group")],
                [Button.inline("🗑 حذف الكل", b"del_all_groups")],
                [Button.inline("🔙 رجوع", b"back")],
            ])

        elif data == 'list_groups':
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id, group_name, member_count FROM groups LIMIT 50")
            grps = c.fetchall()
            conn.close()
            if not grps:
                await event.edit("📢 لا توجد مجموعات\nاضغط 'تحديث المجموعات'", 
                               buttons=[[Button.inline("🔄 تحديث", b"refresh_groups")],
                                        [Button.inline("🔙 رجوع", b"groups")]])
            else:
                text = "📢 **المجموعات:**\n\n"
                for gid, gname, members in grps:
                    text += f"📌 #{gid} - {gname[:30]} ({members or 0} عضو)\n"
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
            await event.edit("🗑 تم الحذف", buttons=[[Button.inline("🔙 رجوع", b"groups")]])

        elif data == 'refresh_groups':
            await event.edit("🔄 جاري التحديث...")
            total = 0
            for acc_id, client in user_clients.items():
                count = await fetch_all_groups_for_account(acc_id, client)
                total += count
            await event.edit(f"✅ تم تحديث {total} مجموعة", buttons=[[Button.inline("🔙 رجوع", b"back")]])

        elif data == 'start_posting':
            groups_count = await get_all_groups_count()
            if groups_count == 0:
                await event.edit("⚠️ لا توجد مجموعات!\nاضغط 'تحديث المجموعات'", 
                               buttons=[[Button.inline("🔄 تحديث", b"refresh_groups")],
                                        [Button.inline("🔙 رجوع", b"back")]])
                return
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM messages")
            msg_count = c.fetchone()[0]
            conn.close()
            
            if msg_count == 0:
                await event.edit("⚠️ لا توجد رسائل!", 
                               buttons=[[Button.inline("➕ إضافة", b"add_msg")],
                                        [Button.inline("🔙 رجوع", b"back")]])
                return
            
            if not user_clients:
                await event.edit("⚠️ لا توجد حسابات!", 
                               buttons=[[Button.inline("➕ إضافة حساب", b"add_acc")],
                                        [Button.inline("🔙 رجوع", b"back")]])
                return
            
            if is_posting_active:
                await event.edit("⚠️ النشر يعمل!", buttons=[[Button.inline("🔙 رجوع", b"back")]])
                return
            
            is_posting_active = True
            message_interval = get_setting('message_interval', '60')
            await event.edit(
                f"🚀 **بدأ النشر!**\n\n📢 {groups_count} مجموعة\n👥 {len(user_clients)} حساب\n⏱ كل {message_interval} ثانية",
                buttons=[[Button.inline("⏹ إيقاف", b"stop_posting")],
                         [Button.inline("🔙 رجوع", b"back")]]
            )
            asyncio.create_task(auto_posting_loop(bot))

        elif data == 'stop_posting':
            is_posting_active = False
            await event.edit("⏹ **تم الإيقاف**", buttons=[[Button.inline("🔙 رجوع", b"back")]])

        elif data == 'settings':
            await event.edit(
                "⚙️ **الإعدادات**\n\n"
                f"📨 مدة النشر: {get_setting('message_interval', '60')} ثانية\n"
                f"🐢 مدة الانضمام: {get_setting('join_interval', '100')} ثانية\n"
                f"🎭 التشفير: {get_setting('encryption', 'on')}\n"
                f"🛡 مكافحة الكشف: {get_setting('anti_detect', 'on')}",
                buttons=[
                    [Button.inline("⏱ مدة النشر", b"set_msg_interval")],
                    [Button.inline("🐢 مدة الانضمام", b"set_join_interval")],
                    [Button.inline("🛡 تبديل التشفير", b"toggle_enc")],
                    [Button.inline("🎭 تبديل مكافحة الكشف", b"toggle_anti")],
                    [Button.inline("🔙 رجوع", b"back")]
                ]
            )

        elif data == 'set_msg_interval':
            await event.edit("⏱ أرسل المدة (10-600 ثانية):\n/cancel للإلغاء")
            set_setting('awaiting_msg_interval', 'true')

        elif data == 'set_join_interval':
            await event.edit("🐢 أرسل المدة (30-600 ثانية):\n/cancel للإلغاء")
            set_setting('awaiting_join_interval', 'true')

        elif data == 'toggle_enc':
            current = get_setting('encryption', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('encryption', new_val)
            await event.answer(f"التشفير: {'مفعل' if new_val == 'on' else 'معطل'}")
            await event.edit("⚙️ الإعدادات", buttons=[
                [Button.inline("⏱ مدة النشر", b"set_msg_interval")],
                [Button.inline("🐢 مدة الانضمام", b"set_join_interval")],
                [Button.inline("🛡 تبديل التشفير", b"toggle_enc")],
                [Button.inline("🎭 تبديل مكافحة الكشف", b"toggle_anti")],
                [Button.inline("🔙 رجوع", b"back")]
            ])

        elif data == 'toggle_anti':
            current = get_setting('anti_detect', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('anti_detect', new_val)
            await event.answer(f"مكافحة الكشف: {'مفعلة' if new_val == 'on' else 'معطلة'}")
            await event.edit("⚙️ الإعدادات", buttons=[
                [Button.inline("⏱ مدة النشر", b"set_msg_interval")],
                [Button.inline("🐢 مدة الانضمام", b"set_join_interval")],
                [Button.inline("🛡 تبديل التشفير", b"toggle_enc")],
                [Button.inline("🎭 تبديل مكافحة الكشف", b"toggle_anti")],
                [Button.inline("🔙 رجوع", b"back")]
            ])

        elif data == 'stats':
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM messages")
            msg_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM accounts WHERE status='active'")
            acc_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM groups")
            grp_count = c.fetchone()[0]
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
                f"✅ نجاح: {success_count}\n"
                f"❌ فشل: {fail_count}\n"
                f"🔗 انضمام: {join_stats['total']} (نجاح: {join_stats['success']})",
                buttons=[[Button.inline("🔙 رجوع", b"back")]]
            )

        elif data == 'slow_join':
            join_interval = get_setting('join_interval', '100')
            await event.edit(
                f"🐢 **انضمام بطيء**\n\nأرسل الروابط (كل رابط في سطر):\n/cancel للإلغاء"
            )
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

        elif data == 'clean_db':
            await event.edit(
                "⚠️ **تنظيف قاعدة البيانات**\n\nسيتم حذف كل شيء ما عدا الحسابات\n\nهل أنت متأكد؟",
                buttons=[
                    [Button.inline("✅ نعم", b"confirm_clean")],
                    [Button.inline("❌ إلغاء", b"back")]
                ]
            )

        elif data == 'confirm_clean':
            try:
                saved = clean_database_keep_accounts()
                set_setting('message_interval', '60')
                set_setting('join_interval', '100')
                await event.edit(f"✅ تم التنظيف!\n✅ تم حفظ {saved} حساب", 
                               buttons=[[Button.inline("🔄 تحديث", b"refresh_groups")],
                                        [Button.inline("🔙 رجوع", b"back")]])
            except Exception as e:
                await event.edit(f"❌ فشل: {e}", buttons=[[Button.inline("🔙 رجوع", b"back")]])

    # ─── معالج الرسائل النصية ───
    @bot.on(events.NewMessage)
    async def message_handler(event):
        if not is_admin(event.sender_id):
            return

        text = event.raw_text

        if text == '/cancel':
            for key in ['awaiting_msg', 'awaiting_phone', 'awaiting_code', 'awaiting_password',
                       'awaiting_slow_join', 'awaiting_del_msg', 'awaiting_del_acc', 
                       'awaiting_del_group', 'awaiting_msg_interval', 'awaiting_join_interval']:
                set_setting(key, '')
            if event.sender_id in temp_sessions:
                try:
                    await temp_sessions[event.sender_id]["client"].disconnect()
                except:
                    pass
                del temp_sessions[event.sender_id]
            await event.respond("تم الإلغاء", buttons=get_main_menu())
            return

        # ضبط المدة
        if get_setting('awaiting_msg_interval') == 'true':
            set_setting('awaiting_msg_interval', '')
            try:
                val = int(text.strip())
                if 10 <= val <= 600:
                    set_setting('message_interval', str(val))
                    await event.respond(f"✅ تم الضبط إلى {val} ثانية", buttons=get_main_menu())
                else:
                    await event.respond("❌ بين 10 و 600", buttons=get_main_menu())
            except:
                await event.respond("❌ رقم غير صالح", buttons=get_main_menu())
            return

        if get_setting('awaiting_join_interval') == 'true':
            set_setting('awaiting_join_interval', '')
            try:
                val = int(text.strip())
                if 30 <= val <= 600:
                    set_setting('join_interval', str(val))
                    await event.respond(f"✅ تم الضبط إلى {val} ثانية", buttons=get_main_menu())
                else:
                    await event.respond("❌ بين 30 و 600", buttons=get_main_menu())
            except:
                await event.respond("❌ رقم غير صالح", buttons=get_main_menu())
            return

        # الروابط - انضمام تلقائي
        links = re.findall(r'(https?://t\.me/(?:joinchat/|\+)?[a-zA-Z0-9_\-]+)', text)
        if links and user_clients:
            join_interval = get_setting('join_interval', '100')
            total_links = len(links[:20])
            
            await event.respond(
                f"🚀 **تم اكتشاف {total_links} رابط**\n"
                f"🐢 جاري الانضمام كل {join_interval} ثانية..."
            )
            
            success, failed, msg = await auto_join_links(links)
            
            await event.respond(
                f"📊 **النتيجة:**\n✅ نجاح: {success}\n❌ فشل: {failed}\n📈 {success/(total_links or 1)*100:.1f}%",
                buttons=get_main_menu()
            )
            return

        # إضافة رسالة
        if get_setting('awaiting_msg') == 'true':
            set_setting('awaiting_msg', '')
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('INSERT INTO messages (content, msg_type) VALUES (?, ?)', (text, 'text'))
            conn.commit()
            conn.close()
            await event.respond("✅ تم حفظ الرسالة!", buttons=get_main_menu())
            return

        # إضافة حساب - رقم الهاتف
        if get_setting('awaiting_phone') == 'true':
            set_setting('awaiting_phone', '')
            phone = text.strip()
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

        # إضافة حساب - رمز التحقق
        if get_setting('awaiting_code') == 'true':
            set_setting('awaiting_code', '')
            code = text.strip()
            session_data = temp_sessions.get(event.sender_id)
            if not session_data:
                await event.respond("❌ انتهت الجلسة")
                return
            try:
                await session_data["client"].sign_in(
                    session_data["phone"], code, 
                    phone_code_hash=session_data["phone_code_hash"]
                )
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

        # إضافة حساب - كلمة المرور
        if get_setting('awaiting_password') == 'true':
            set_setting('awaiting_password', '')
            password = text.strip()
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

        # انضمام بطيء يدوي
        if get_setting('awaiting_slow_join') == 'true':
            set_setting('awaiting_slow_join', '')
            links = [l.strip() for l in text.split('\n') if l.strip()]
            if links:
                success, failed, msg = await auto_join_links(links)
                await event.respond(f"✅ نجاح: {success}\n❌ فشل: {failed}", buttons=get_main_menu())
            return

        # حذف رسالة
        if get_setting('awaiting_del_msg') == 'true':
            set_setting('awaiting_del_msg', '')
            try:
                msg_id = int(text.strip())
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('DELETE FROM messages WHERE id=?', (msg_id,))
                conn.commit()
                conn.close()
                await event.respond("✅ تم الحذف", buttons=get_main_menu())
            except:
                await event.respond("❌ رقم غير صالح", buttons=get_main_menu())
            return

        # حذف حساب
        if get_setting('awaiting_del_acc') == 'true':
            set_setting('awaiting_del_acc', '')
            try:
                acc_id = int(text.strip())
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

        # حذف مجموعة
        if get_setting('awaiting_del_group') == 'true':
            set_setting('awaiting_del_group', '')
            try:
                grp_id = int(text.strip())
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('DELETE FROM groups WHERE id=?', (grp_id,))
                conn.commit()
                conn.close()
                await event.respond("✅ تم الحذف", buttons=get_main_menu())
            except:
                await event.respond("❌ رقم غير صالح", buttons=get_main_menu())
            return

    # ─── أوامر سريعة ───
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
            if 10 <= val <= 600:
                set_setting('message_interval', str(val))
                await event.respond(f"✅ مدة النشر: {val} ثانية")
            else:
                await event.respond("❌ بين 10 و 600")
        except:
            await event.respond("❌ استخدم: /set_msg_interval 60")

    @bot.on(events.NewMessage(pattern='/set_join_interval'))
    async def set_join_cmd(event):
        if not is_admin(event.sender_id):
            return
        try:
            val = int(event.raw_text.split()[1])
            if 30 <= val <= 600:
                set_setting('join_interval', str(val))
                await event.respond(f"✅ مدة الانضمام: {val} ثانية")
            else:
                await event.respond("❌ بين 30 و 600")
        except:
            await event.respond("❌ استخدم: /set_join_interval 100")

    # بدء البوت
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
