#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔═══════════════════════════════════════════════════════════════╗
║     🤖 بوت النشر الخارق - النسخة المطورة 🚀                  ║
║     مع تشفير متقدم + انضمام 20 رابط + حفظ الحسابات          ║
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
from threading import Thread
from datetime import datetime

from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest
from flask import Flask, jsonify

# ═══════════════════════════════════════════════
#  الإعدادات - تُقرأ من متغيرات البيئة
# ═══════════════════════════════════════════════
API_ID = int(os.environ.get('API_ID', '0'))
API_HASH = os.environ.get('API_HASH', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '0'))

if not all([API_ID, API_HASH, BOT_TOKEN, ADMIN_ID]):
    logging.error("⚠️ يجب تعيين جميع متغيرات البيئة: API_ID, API_HASH, BOT_TOKEN, ADMIN_ID")
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
#  خادم الويب Flask (للحفاظ على التطبيق نشطاً)
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
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ═══════════════════════════════════════════════
#  نظام التشفير المتقدم جداً (لا يغير النص)
# ═══════════════════════════════════════════════

class UltraAdvancedEncryption:
    """تشفير متقدم جداً - لا يغير نص المنشور، يتجاوز أقوى بوتات الحماية"""
    
    def __init__(self):
        # أحرف غير مرئية بتقنيات متعددة
        self.zero_width_chars = [
            '\u200B',  # Zero width space
            '\u200C',  # Zero width non-joiner
            '\u200D',  # Zero width joiner
            '\uFEFF',  # Zero width no-break space
            '\u2060',  # Word joiner
            '\u2061',  # Function application
            '\u2062',  # Invisible times
            '\u2063',  # Invisible separator
            '\u2064',  # Invisible plus
        ]
        
        # أحرف تبدو متشابهة (Homoglyphs)
        self.homoglyphs = {
            'a': ['а', 'α', '⍺', 'ａ'],
            'b': ['Ь', 'β', 'в', 'ｂ'],
            'c': ['с', 'ϲ', 'ⅽ', 'ｃ'],
            'e': ['е', 'ε', 'ё', 'ｅ'],
            'h': ['һ', 'н', 'հ', 'ｈ'],
            'i': ['і', 'ɪ', 'ι', 'ｉ'],
            'k': ['κ', 'к', 'ｋ'],
            'o': ['о', 'ο', 'σ', 'ｏ'],
            'p': ['р', 'ρ', 'ｐ'],
            'x': ['х', '×', 'ⅹ', 'ｘ'],
            'y': ['у', 'γ', 'ｙ'],
            'A': ['Α', 'А', 'Ａ'],
            'B': ['В', 'Β', 'Ｂ'],
            'C': ['С', 'Ｃ'],
            'E': ['Е', 'Ε', 'Ｅ'],
            'H': ['Н', 'Ｈ'],
            'K': ['Κ', 'Ｋ'],
            'M': ['Μ', 'Ｍ'],
            'O': ['Ο', 'О', 'Ｏ'],
            'P': ['Ρ', 'Р', 'Ｐ'],
            'T': ['Τ', 'Т', 'Ｔ'],
            'X': ['Χ', 'Х', 'Ｘ'],
        }
        
        self.direction_override = '\u202E'
    
    def apply_homoglyphs(self, text, intensity=0.2):
        """استبدال بعض الأحرف بأحرف متشابهة"""
        result = []
        for char in text:
            if char in self.homoglyphs and random.random() < intensity:
                result.append(random.choice(self.homoglyphs[char]))
            else:
                result.append(char)
        return ''.join(result)
    
    def add_zero_width_chars(self, text, intensity=0.05):
        """إضافة أحرف غير مرئية بشكل عشوائي"""
        if random.random() > 0.7:
            chars = list(text)
            for i in range(len(chars)):
                if random.random() < intensity:
                    chars.insert(i, random.choice(self.zero_width_chars))
            return ''.join(chars)
        return text
    
    def add_invisible_spaces(self, text):
        """إضافة مسافات غير مرئية بين الكلمات"""
        words = text.split()
        for i in range(len(words) - 1):
            if random.random() > 0.92:
                words[i] += random.choice(self.zero_width_chars)
        return ' '.join(words)
    
    def encrypt(self, text):
        """تشفير متقدم مع الحفاظ على شكل النص الأصلي"""
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
    """تشفير النص مع الحفاظ على الشكل الأصلي"""
    return ultra_encryption.encrypt(text)

# ═══════════════════════════════════════════════
#  نظام مكافحة الكشف المتقدم (اختياري)
# ═══════════════════════════════════════════════
def generate_text_variation(text):
    """إنشاء نسخة مختلفة من النص مع التشفير المتقدم"""
    if get_setting('anti_detect', 'on') != 'on':
        return text
    return encrypt_text(text)

# ═══════════════════════════════════════════════
#  إدارة الحسابات
# ═══════════════════════════════════════════════
user_clients = {}

async def restore_sessions():
    """استعادة جلسات الحسابات المحفوظة"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, session_string, phone, status FROM accounts WHERE status='active'")
    accounts = c.fetchall()
    conn.close()

    for acc_id, session_str, phone, status in accounts:
        try:
            client = TelegramClient(
                StringSession(session_str),
                API_ID, API_HASH
            )
            await client.connect()
            if await client.is_user_authorized():
                user_clients[acc_id] = client
                logger.info(f"✅ تم استعادة حساب: {phone}")
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

# ═══════════════════════════════════════════════
#  نظام النشر
# ═══════════════════════════════════════════════
is_posting_active = False

async def post_to_groups(bot, message_content, msg_type='text', media_path=None):
    """نشر رسالة في جميع المجموعات باستخدام الحسابات المتاحة"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT group_id FROM groups")
    groups = c.fetchall()
    c.execute("SELECT id FROM accounts WHERE status='active'")
    accounts = c.fetchall()
    conn.close()

    if not groups:
        return 0, "لا توجد مجموعات مسجلة"

    if not accounts:
        return 0, "لا توجد حسابات نشطة"

    success_count = 0
    fail_count = 0
    account_list = list(accounts)
    random.shuffle(account_list)

    for idx, (group_id,) in enumerate(groups):
        acc_id = account_list[idx % len(account_list)][0]
        client = user_clients.get(acc_id)

        if not client:
            continue

        try:
            # تطبيق التشفير المتقدم
            variation = generate_text_variation(message_content)

            delay = random.uniform(
                float(get_setting('min_delay', '3')),
                float(get_setting('max_delay', '8'))
            )
            await asyncio.sleep(delay)

            if msg_type == 'text':
                await client.send_message(int(group_id), variation)
            elif msg_type == 'photo' and media_path:
                await client.send_file(int(group_id), media_path, caption=variation)

            success_count += 1
            log_posting(acc_id, int(group_id), 0, 'success')

        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            fail_count += 1
            log_posting(acc_id, int(group_id), 0, f'failed: flood wait {e.seconds}s')
        except Exception as e:
            fail_count += 1
            log_posting(acc_id, int(group_id), 0, f'failed: {str(e)[:50]}')
            logger.error(f"فشل النشر في {group_id}: {e}")

    return success_count, fail_count

def log_posting(account_id, group_id, message_id, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO posting_history (account_id, group_id, message_id, status)
                 VALUES (?, ?, ?, ?)''', (account_id, group_id, message_id, status))
    conn.commit()
    conn.close()

# ═══════════════════════════════════════════════
#  نظام الانضمام لـ 20 رابط (سريع)
# ═══════════════════════════════════════════════
async def fast_join_groups(links, account_id=None):
    """الانضمام السريع لـ 20 رابط في رسالة واحدة"""
    if account_id and account_id in user_clients:
        client = user_clients[account_id]
    else:
        active_ids = list(user_clients.keys())
        if not active_ids:
            return 0, "لا توجد حسابات نشطة"
        client = user_clients[random.choice(active_ids)]

    success_count = 0
    failed_count = 0
    
    for i, link in enumerate(links, 1):
        link = link.strip()
        if not link:
            continue
        
        try:
            # تأخير قصير بين المحاولات (10-20 ثانية)
            delay = random.randint(10, 20)
            logger.info(f"⏸ انتظار {delay} ثانية قبل الرابط {i}/{len(links)}")
            await asyncio.sleep(delay)
            
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
            logger.success(f"✅ [{i}/{len(links)}] تم الانضمام إلى {link[:50]}")
            
            # تسجيل في قاعدة البيانات
            if group_info:
                group_id, group_name = group_info
                save_join_history(link, group_id, group_name[:50], 'success', client.get_me().phone if hasattr(client, 'get_me') else "unknown")
                # إضافة المجموعة لقاعدة البيانات
                add_group_to_db(group_id, group_name)
            
        except FloodWaitError as e:
            wait_time = e.seconds + random.randint(10, 30)
            logger.warning(f"⏳ FloodWait: انتظار {wait_time} ثانية...")
            await asyncio.sleep(wait_time)
            failed_count += 1
            save_join_history(link, 0, "غير معروف", f'failed: flood wait', "unknown")
            
        except Exception as e:
            failed_count += 1
            logger.error(f"❌ [{i}/{len(links)}] فشل الانضمام لـ {link[:50]}: {e}")
            save_join_history(link, 0, "غير معروف", f'failed: {str(e)[:50]}', "unknown")
    
    return success_count, failed_count

def save_join_history(link, group_id, group_name, status, joined_by):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO join_history (link, group_id, group_name, status, joined_by)
                 VALUES (?, ?, ?, ?, ?)''', (link, group_id, group_name, status, joined_by))
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
#  تنظيف قاعدة البيانات مع حفظ الحسابات
# ═══════════════════════════════════════════════
def clean_database_keep_accounts():
    """حذف كل الجداول ماعدا الحسابات"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # حفظ الحسابات مؤقتاً
    c.execute("SELECT session_string, phone, status FROM accounts")
    accounts = c.fetchall()
    
    # حذف الجداول
    c.execute("DROP TABLE IF EXISTS messages")
    c.execute("DROP TABLE IF EXISTS groups")
    c.execute("DROP TABLE IF EXISTS posting_history")
    c.execute("DROP TABLE IF EXISTS join_history")
    c.execute("DROP TABLE IF EXISTS settings")
    
    # إعادة إنشاء الجداول
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
    
    # استعادة الحسابات
    for session_str, phone, status in accounts:
        c.execute('INSERT INTO accounts (session_string, phone, status) VALUES (?, ?, ?)',
                  (session_str, phone, status))
    
    conn.commit()
    conn.close()
    return len(accounts)

# ═══════════════════════════════════════════════
#  لوحة التحكم الرئيسية
# ═══════════════════════════════════════════════
def get_main_menu():
    enc_status = "✅" if get_setting('encryption', 'on') == 'on' else "❌"
    anti_status = "✅" if get_setting('anti_detect', 'on') == 'on' else "❌"
    
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
        [Button.inline("🔗 انضمام 20 رابط", b"fast_join"),
         Button.inline("📋 تقارير الانضمام", b"join_reports")],
        [Button.inline("🗑 تنظيف قاعدة البيانات", b"clean_db")],
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
    # بدء خادم الويب في خيط خلفي
    Thread(target=run_web, daemon=True).start()
    logger.info("🌐 خادم الويب يعمل")

    # تهيئة قاعدة البيانات
    init_db()

    # استعادة جلسات الحسابات
    await restore_sessions()

    # إنشاء عميل البوت
    bot = TelegramClient('bot_session', API_ID, API_HASH)
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("🤖 البوت يعمل بنجاح!")

    # ─── أمر /start ───
    @bot.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        if event.sender_id != ADMIN_ID:
            return
        await event.respond(
            "🤖 **بوت النشر الخارق v5.0**\n\n"
            "مرحباً بك في لوحة التحكم الرئيسية!\n"
            "• تشفير متقدم جداً (لا يغير النص)\n"
            "• انضمام لـ 20 رابط دفعة واحدة\n"
            "• حفظ الحسابات عند تنظيف قاعدة البيانات\n\n"
            "اختر من القائمة أدناه:",
            buttons=get_main_menu()
        )

    # ─── التعامل مع الأزرار ───
    @bot.on(events.CallbackQuery)
    async def callback_handler(event):
        if event.sender_id != ADMIN_ID:
            return

        data = event.data.decode('utf-8')

        if data == 'back':
            await event.edit(
                "🤖 **بوت النشر الخارق v5.0**\n\n"
                "اختر من القائمة أدناه:",
                buttons=get_main_menu()
            )

        # ─── إدارة الرسائل ───
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
                "أرسل الرسالة الآن:\n"
                "• أرسل نصاً عادياً لرسالة نصية\n"
                "• أرسل صورة مع تعليق لرسالة بصريبة\n\n"
                "استخدم /cancel للإلغاء"
            )
            set_setting('awaiting_msg', 'true')

        elif data == 'list_msg':
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id, substr(content,1,50), msg_type FROM messages LIMIT 20")
            msgs = c.fetchall()
            conn.close()
            if not msgs:
                await event.edit("📋 لا توجد رسائل محفوظة", buttons=[
                    [Button.inline("🔙 رجوع", b"messages")]
                ])
            else:
                text = "📋 **الرسائل المحفوظة:**\n\n"
                for mid, content, mtype in msgs:
                    text += f"#{mid} [{mtype}] - {content}...\n"
                await event.edit(text, buttons=[
                    [Button.inline("🔙 رجوع", b"messages")]
                ])

        elif data == 'del_msg':
            await event.edit("🗑 أرسل رقم الرسالة لحذفها:\nاستخدم /cancel للإلغاء")
            set_setting('awaiting_del_msg', 'true')

        # ─── إدارة الحسابات ───
        elif data == 'accounts':
            await event.edit("👥 **إدارة الحسابات**", buttons=[
                [Button.inline("➕ إضافة حساب", b"add_acc")],
                [Button.inline("📋 عرض الحسابات", b"list_acc")],
                [Button.inline("🗑 حذف حساب", b"del_acc")],
                [Button.inline("🔙 رجوع", b"back")],
            ])

        elif data == 'add_acc':
            await event.edit(
                "➕ **إضافة حساب جديد**\n\n"
                "أرسل StringSession للحساب:\n\n"
                "💡 للحصول على StringSession:\n"
                "1. اذهب إلى @StringSessionBot\n"
                "2. أدخل رقم هاتفك\n"
                "3. أدخل رمز التحقق\n"
                "4. انسخ الـ StringSession\n\n"
                "استخدم /cancel للإلغاء"
            )
            set_setting('awaiting_session', 'true')

        elif data == 'list_acc':
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id, phone, status FROM accounts")
            accs = c.fetchall()
            conn.close()
            if not accs:
                await event.edit("👥 لا توجد حسابات مسجلة", buttons=[
                    [Button.inline("🔙 رجوع", b"accounts")]
                ])
            else:
                text = "👥 **الحسابات المسجلة:**\n\n"
                for aid, phone, status in accs:
                    emoji = "✅" if status == 'active' else "❌"
                    text += f"{emoji} #{aid} - {phone or 'بدون رقم'} [{status}]\n"
                await event.edit(text, buttons=[
                    [Button.inline("🔙 رجوع", b"accounts")]
                ])

        elif data == 'del_acc':
            await event.edit("🗑 أرسل رقم الحساب لحذفه:\nاستخدم /cancel للإلغاء")
            set_setting('awaiting_del_acc', 'true')

        # ─── إدارة المجموعات ───
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
            c.execute("SELECT id, group_name, member_count FROM groups LIMIT 30")
            grps = c.fetchall()
            conn.close()
            if not grps:
                await event.edit("📢 لا توجد مجموعات مسجلة", buttons=[
                    [Button.inline("🔙 رجوع", b"groups")]
                ])
            else:
                text = "📢 **المجموعات المسجلة:**\n\n"
                for gid, gname, members in grps:
                    text += f"#{gid} - {gname or 'غير مسمى'} ({members or 0} عضو)\n"
                await event.edit(text, buttons=[
                    [Button.inline("🔙 رجوع", b"groups")]
                ])

        elif data == 'del_group':
            await event.edit("🗑 أرسل رقم المجموعة لحذفها:\nاستخدم /cancel للإلغاء")
            set_setting('awaiting_del_group', 'true')

        elif data == 'del_all_groups':
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM groups")
            conn.commit()
            conn.close()
            await event.edit("🗑 تم حذف جميع المجموعات", buttons=[
                [Button.inline("🔙 رجوع", b"groups")]
            ])

        # ─── التحكم في النشر ───
        elif data == 'start_posting':
            global is_posting_active
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT content, msg_type FROM messages")
            msgs = c.fetchall()
            conn.close()
            if not msgs:
                await event.edit("⚠️ لا توجد رسائل للنشر!\nأضف رسائل أولاً.", buttons=[
                    [Button.inline("🔙 رجوع", b"back")]
                ])
                return
            if is_posting_active:
                await event.edit("⚠️ النشر قيد التشغيل بالفعل!", buttons=[
                    [Button.inline("🔙 رجوع", b"back")]
                ])
                return
            is_posting_active = True
            await event.edit("🚀 **تم بدء النشر!**\n\nسيتم النشر في المجموعات بالتناوب.", buttons=[
                [Button.inline("⏹ إيقاف النشر", b"stop_posting")],
                [Button.inline("🔙 رجوع", b"back")],
            ])
            asyncio.create_task(auto_posting_loop(bot))

        elif data == 'stop_posting':
            is_posting_active = False
            await event.edit("⏹ **تم إيقاف النشر**", buttons=[
                [Button.inline("🔙 رجوع", b"back")]
            ])

        # ─── الإعدادات ───
        elif data == 'settings':
            min_delay = get_setting('min_delay', '3')
            max_delay = get_setting('max_delay', '8')
            await event.edit(
                "⚙️ **الإعدادات**\n\n"
                f"⏱ تأخير أدنى: {min_delay} ثانية\n"
                f"⏱ تأخير أقصى: {max_delay} ثانية\n\n"
                "للتعديل أرسل الأمر:\n"
                "• /set_min_delay <رقم>\n"
                "• /set_max_delay <رقم>",
                buttons=[
                    [Button.inline("🔙 رجوع", b"back")]
                ]
            )

        # ─── الإحصائيات ───
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
                "📊 **الإحصائيات**\n\n"
                f"📝 الرسائل: {msg_count}\n"
                f"👥 الحسابات النشطة: {acc_count}\n"
                f"📢 المجموعات: {grp_count}\n"
                f"✅ عمليات نشر ناجحة: {success_count}\n"
                f"❌ عمليات نشر فاشلة: {fail_count}\n"
                f"🔗 عمليات انضمام: {join_stats['total']}\n"
                f"🔗 انضمام ناجح: {join_stats['success']}",
                buttons=[
                    [Button.inline("🔙 رجوع", b"back")]
                ]
            )

        # ─── تبديل التشفير ───
        elif data == 'toggle_enc':
            current = get_setting('encryption', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('encryption', new_val)
            await event.answer(f"✅ التشفير: {'مفعل' if new_val == 'on' else 'معطل'}")
            await event.edit("👋 لوحة التحكم:", buttons=get_main_menu())

        # ─── تبديل مكافحة الكشف ───
        elif data == 'toggle_anti':
            current = get_setting('anti_detect', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('anti_detect', new_val)
            await event.answer(f"✅ مكافحة الكشف: {'مفعلة' if new_val == 'on' else 'معطلة'}")
            await event.edit("👋 لوحة التحكم:", buttons=get_main_menu())

        # ─── انضمام 20 رابط ───
        elif data == 'fast_join':
            await event.edit(
                "🔗 **انضمام لـ 20 رابط دفعة واحدة**\n\n"
                "أرسل روابط المجموعات (رابط في كل سطر):\n\n"
                "مثال:\n"
                "https://t.me/group1\n"
                "https://t.me/group2\n"
                "https://t.me/joinchat/xxxxx\n\n"
                "📌 يمكنك إرسال حتى 20 رابط في رسالة واحدة\n"
                "استخدم /cancel للإلغاء"
            )
            set_setting('awaiting_fast_join', 'true')

        # ─── تقارير الانضمام ───
        elif data == 'join_reports':
            await event.edit("🔗 **تقارير الانضمام**", buttons=get_join_reports_menu())

        elif data == 'join_stats':
            stats = get_join_stats()
            await event.edit(
                f"📊 **إحصائيات الانضمام**\n\n"
                f"📌 إجمالي المحاولات: {stats['total']}\n"
                f"✅ ناجح: {stats['success']}\n"
                f"❌ فاشل: {stats['failed']}\n"
                f"📈 نسبة النجاح: {stats['success']/(stats['total'] or 1)*100:.1f}%",
                buttons=get_join_reports_menu()
            )

        elif data == 'join_history':
            history = get_join_history(30)
            if not history:
                await event.edit("📭 لا توجد سجلات انضمام", buttons=get_join_reports_menu())
            else:
                text = "🔗 **آخر 30 عملية انضمام**\n\n"
                for link, group_name, joined_at, joined_by, status in history:
                    time_str = datetime.fromisoformat(joined_at).strftime('%H:%M:%S')
                    icon = "✅" if status == 'success' else "❌"
                    text += f"{icon} {time_str} - {group_name[:25]}\n"
                    text += f"   🔗 {link[:40]}...\n"
                    text += f"   📱 {joined_by[-8:] if joined_by else '?'}\n\n"
                await event.edit(text, buttons=get_join_reports_menu())

        # ─── تنظيف قاعدة البيانات ───
        elif data == 'clean_db':
            await event.edit(
                "⚠️ **تنظيف قاعدة البيانات** ⚠️\n\n"
                "سيتم حذف:\n"
                "❌ جميع الرسائل المحفوظة\n"
                "❌ جميع المجموعات\n"
                "❌ سجل النشر\n"
                "❌ سجل الانضمام\n\n"
                "✅ **سيتم الحفاظ على:**\n"
                "✓ جميع الحسابات المسجلة\n"
                "✓ جلسات الحسابات\n\n"
                "**هل أنت متأكد؟**",
                buttons=[
                    [Button.inline("✅ نعم، نظف مع حفظ الحسابات", b"confirm_clean")],
                    [Button.inline("❌ إلغاء", b"back")]
                ]
            )

        elif data == 'confirm_clean':
            try:
                saved = clean_database_keep_accounts()
                set_setting('min_delay', '3')
                set_setting('max_delay', '8')
                set_setting('encryption', 'on')
                set_setting('anti_detect', 'on')
                
                await event.edit(
                    f"✅ **تم تنظيف قاعدة البيانات بنجاح!**\n\n"
                    f"• ✅ تم الحفاظ على {saved} حساب\n"
                    f"• 🗑 تم حذف: الرسائل، المجموعات، السجلات\n\n"
                    f"**ملاحظة:** حساباتك لا تزال موجودة وجاهزة للاستخدام\n\n"
                    f"اضغط /start للبدء",
                    buttons=[[Button.inline("🔄 العودة", b"back")]]
                )
            except Exception as e:
                await event.edit(f"❌ فشل التنظيف: {str(e)[:100]}", buttons=[
                    [Button.inline("🔙 رجوع", b"back")]
                ])

    # ─── التعامل مع الرسائل النصية ───
    @bot.on(events.NewMessage)
    async def message_handler(event):
        if event.sender_id != ADMIN_ID:
            return

        text = event.raw_text

        if text == '/cancel':
            set_setting('awaiting_msg', '')
            set_setting('awaiting_session', '')
            set_setting('awaiting_fast_join', '')
            set_setting('awaiting_del_msg', '')
            set_setting('awaiting_del_acc', '')
            set_setting('awaiting_del_group', '')
            await event.respond("تم الإلغاء", buttons=get_main_menu())
            return

        # إضافة رسالة
        if get_setting('awaiting_msg') == 'true':
            set_setting('awaiting_msg', '')
            msg_type = 'text'
            media_path = None
            if event.photo:
                msg_type = 'photo'
                os.makedirs('media', exist_ok=True)
                media_path = await bot.download_media(event.message, 'media/')

            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('INSERT INTO messages (content, media_path, msg_type) VALUES (?, ?, ?)',
                      (text, media_path, msg_type))
            conn.commit()
            conn.close()
            await event.respond("✅ تم حفظ الرسالة!", buttons=get_main_menu())
            return

        # إضافة حساب
        if get_setting('awaiting_session') == 'true':
            set_setting('awaiting_session', '')
            session_str = text.strip()
            try:
                client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
                await client.connect()
                if await client.is_user_authorized():
                    me = await client.get_me()
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute('INSERT INTO accounts (session_string, phone, status) VALUES (?, ?, ?)',
                              (session_str, me.phone, 'active'))
                    conn.commit()
                    acc_id = c.lastrowid
                    conn.close()
                    user_clients[acc_id] = client
                    await event.respond(f"✅ تم إضافة حساب: {me.phone}", buttons=get_main_menu())
                else:
                    await event.respond("❌ الجلسة غير صالحة!", buttons=get_main_menu())
            except Exception as e:
                await event.respond(f"❌ خطأ: {e}", buttons=get_main_menu())
            return

        # انضمام سريع لـ 20 رابط
        if get_setting('awaiting_fast_join') == 'true':
            set_setting('awaiting_fast_join', '')
            links = text.strip().split('\n')
            links = [l.strip() for l in links if l.strip()]
            
            if len(links) > 20:
                await event.respond(f"⚠️ يمكنك إرسال 20 رابط كحد أقصى. تم استلام {len(links)} رابط، سيتم معالجة أول 20 فقط.")
                links = links[:20]
            
            await event.respond(f"🔗 جاري الانضمام لـ {len(links)} مجموعة...\n⏱ سيستغرق حوالي {len(links) * 15} ثانية")
            
            success, failed = await fast_join_groups(links)
            
            await event.respond(
                f"📊 **نتيجة الانضمام لـ {len(links)} رابط**\n\n"
                f"✅ نجاح: {success}\n"
                f"❌ فشل: {failed}\n"
                f"📈 نسبة النجاح: {success/len(links)*100:.1f}%",
                buttons=get_main_menu()
            )
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
                await event.respond("✅ تم حذف الرسالة", buttons=get_main_menu())
            except ValueError:
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
                await event.respond("✅ تم حذف الحساب", buttons=get_main_menu())
            except ValueError:
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
                await event.respond("✅ تم حذف المجموعة", buttons=get_main_menu())
            except ValueError:
                await event.respond("❌ رقم غير صالح", buttons=get_main_menu())
            return

    # ─── أوامر الإعدادات ───
    @bot.on(events.NewMessage(pattern='/set_min_delay'))
    async def set_min_delay(event):
        if event.sender_id != ADMIN_ID:
            return
        try:
            val = float(event.raw_text.split()[1])
            set_setting('min_delay', str(val))
            await event.respond(f"✅ تم تعيين التأخير الأدنى: {val} ثانية")
        except (IndexError, ValueError):
            await event.respond("❌ الاستخدام: /set_min_delay <رقم>")

    @bot.on(events.NewMessage(pattern='/set_max_delay'))
    async def set_max_delay(event):
        if event.sender_id != ADMIN_ID:
            return
        try:
            val = float(event.raw_text.split()[1])
            set_setting('max_delay', str(val))
            await event.respond(f"✅ تم تعيين التأخير الأقصى: {val} ثانية")
        except (IndexError, ValueError):
            await event.respond("❌ الاستخدام: /set_max_delay <رقم>")

    # ─── حلقة النشر التلقائي ───
    async def auto_posting_loop(bot):
        global is_posting_active
        while is_posting_active:
            try:
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
                    success, fails = await post_to_groups(bot, content, msg_type, media_path)
                    logger.info(f"📤 نشر: نجاح={success}, فشل={fails}")

                    interval = int(get_setting('post_interval', '300'))
                    await asyncio.sleep(interval)

            except Exception as e:
                logger.error(f"خطأ في حلقة النشر: {e}")
                await asyncio.sleep(60)

    # بدء البوت
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
