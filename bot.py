#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔═══════════════════════════════════════════════════════════════╗
║     🤖 بوت النشر الخارق - النسخة النهائية V5 🚀              ║
║     حفظ الحسابات + انضمام 20 رابط + تشفير متقدم             ║
╚═══════════════════════════════════════════════════════════════╝
"""

import asyncio
import re
import os
import random
import json
import sqlite3
import sys
import logging
import shutil
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest
from flask import Flask, jsonify
from threading import Thread

# ==================== الإعدادات الأساسية ====================

API_ID = int(os.environ.get('API_ID', ))
API_HASH = os.environ.get('API_HASH', "")
BOT_TOKEN = os.environ.get('BOT_TOKEN', "")
ADMIN_ID = int(os.environ.get('ADMIN_ID', ))

# ==================== إعدادات التشغيل ====================

DATA_DIR = "data"
BACKUPS_DIR = "backups"
LOGS_DIR = "logs"
DB_PATH = f"{DATA_DIR}/bot_data.db"

for dir_path in [DATA_DIR, BACKUPS_DIR, LOGS_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# ==================== قفل قاعدة البيانات ====================
db_lock = threading.Lock()

# ==================== خادم الويب ====================
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        'status': 'online',
        'bot': 'Telegram Poster Bot V5',
        'version': '5.0',
        'time': str(datetime.now()),
        'accounts': len(USER_CLIENTS) if 'USER_CLIENTS' in globals() else 0,
        'is_posting': is_posting if 'is_posting' in globals() else False
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

def run_web():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ==================== نظام التسجيل ====================

class Logger:
    def __init__(self):
        log_file = f"{LOGS_DIR}/bot_{datetime.now().strftime('%Y%m%d')}.log"
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler(log_file, encoding='utf-8'), logging.StreamHandler()]
        )
        self.logger = logging.getLogger('Bot')
    
    def info(self, msg): self.logger.info(msg); print(f"ℹ️ {msg}")
    def warning(self, msg): self.logger.warning(msg); print(f"⚠️ {msg}")
    def error(self, msg): self.logger.error(msg); print(f"❌ {msg}")
    def success(self, msg): self.logger.info(f"✅ {msg}"); print(f"✅ {msg}")
    def critical(self, msg): self.logger.critical(msg); print(f"💥 {msg}")

logger = Logger()

# ==================== نظام التشفير المتقدم جداً ====================

class UltraAdvancedEncryption:
    """
    تشفير متقدم جداً - لا يغير نص المنشور
    يستخدم تقنيات معقدة لتجاوز أقوى بوتات الحماية
    """
    
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
        
        # تقنيات إضافية
        self.direction_override = '\u202E'  # Right-to-left override
        
    def apply_homoglyphs(self, text, intensity=0.25):
        """استبدال بعض الأحرف بأحرف متشابهة"""
        result = []
        for char in text:
            if char in self.homoglyphs and random.random() < intensity:
                result.append(random.choice(self.homoglyphs[char]))
            else:
                result.append(char)
        return ''.join(result)
    
    def add_zero_width_chars(self, text, intensity=0.08):
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
    
    def encrypt_ultra(self, text):
        """
        تشفير متقدم جداً مع الحفاظ على شكل النص الأصلي
        لا يغير المعنى أو القراءة
        """
        result = text
        
        # تطبيق تقنيات متعددة بتدرجات مختلفة
        result = self.apply_homoglyphs(result, intensity=0.2)
        result = self.add_zero_width_chars(result, intensity=0.05)
        result = self.add_invisible_spaces(result)
        
        # إضافة رمز اتجاه عكسي في نهاية الرسالة (نادراً)
        if random.random() > 0.97:
            result = result + self.direction_override
        
        return result

ultra_encryption = UltraAdvancedEncryption()

def encrypt_text(text):
    """تشفير النص مع الحفاظ على الشكل الأصلي"""
    if not SETTINGS.get('encryption', True):
        return text
    return ultra_encryption.encrypt_ultra(text)

# ==================== كلاس النشر الآمن ====================

class SafePoster:
    def __init__(self):
        self.last_posts = {}
    
    def random_delay(self, base_delay=12):
        return random.randint(int(base_delay * 0.9), int(base_delay * 1.1))
    
    async def send_safe(self, client, chat_id, original_text, group_name=""):
        try:
            # تطبيق التشفير المتقدم بدون تغيير المعنى
            final_text = encrypt_text(original_text)
            
            # تأخير قصير
            await asyncio.sleep(self.random_delay(2))
            
            # إرسال الرسالة
            await client.send_message(chat_id, final_text)
            self.last_posts[chat_id] = datetime.now()
            
            return True, "تم النشر بنجاح"
            
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            return False, f"Flood wait: {e.seconds}s"
        except Exception as e:
            return False, str(e)

safe_poster = SafePoster()

# ==================== قاعدة البيانات ====================

class Database:
    def __init__(self):
        self.db_path = DB_PATH
        self.init_database()
    
    def init_database(self):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP)''')
            c.execute('''CREATE TABLE IF NOT EXISTS messages (msg_id TEXT PRIMARY KEY, content TEXT, created_at TIMESTAMP, is_active INTEGER DEFAULT 0)''')
            c.execute('''CREATE TABLE IF NOT EXISTS accounts (phone TEXT PRIMARY KEY, session_str TEXT, added_at TIMESTAMP, last_active TIMESTAMP, status TEXT, total_posts INTEGER DEFAULT 0, success_posts INTEGER DEFAULT 0, failed_posts INTEGER DEFAULT 0)''')
            c.execute('''CREATE TABLE IF NOT EXISTS groups (group_id TEXT PRIMARY KEY, group_name TEXT, group_username TEXT, group_type TEXT, members_count INTEGER DEFAULT 0, added_by TEXT, added_at TIMESTAMP, last_post TIMESTAMP, post_count INTEGER DEFAULT 0)''')
            c.execute('''CREATE TABLE IF NOT EXISTS posting_history (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT, group_id TEXT, group_name TEXT, sent_at TIMESTAMP, status TEXT, error TEXT)''')
            c.execute('''CREATE TABLE IF NOT EXISTS join_history (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, group_id TEXT, group_name TEXT, joined_at TIMESTAMP, joined_by TEXT, status TEXT)''')
            conn.commit()
            conn.close()
            logger.success("✅ قاعدة البيانات جاهزة")
            if not self.get_all_messages():
                self.save_message("default", "📢 مرحباً بك!", is_active=True)
    
    def save_setting(self, key, value):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)', (key, json.dumps(value), datetime.now()))
                conn.commit()
            finally:
                conn.close()
    
    def get_setting(self, key, default=None):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            result = conn.execute('SELECT value FROM settings WHERE key = ?', (key,)).fetchone()
            return json.loads(result[0]) if result else default
        finally:
            conn.close()
    
    def get_all_settings(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            rows = conn.execute('SELECT key, value FROM settings').fetchall()
            return {key: json.loads(value) for key, value in rows}
        finally:
            conn.close()
    
    def save_message(self, msg_id, content, is_active=False):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                if is_active:
                    conn.execute('UPDATE messages SET is_active = 0')
                conn.execute('INSERT OR REPLACE INTO messages (msg_id, content, created_at, is_active) VALUES (?, ?, ?, ?)', (msg_id, content, datetime.now(), 1 if is_active else 0))
                conn.commit()
            finally:
                conn.close()
    
    def get_all_messages(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT msg_id, content, is_active FROM messages ORDER BY created_at DESC').fetchall()
        finally:
            conn.close()
    
    def get_active_message(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            row = conn.execute('SELECT msg_id, content FROM messages WHERE is_active = 1').fetchone()
            if row:
                return {'id': row[0], 'content': row[1]}
            msgs = self.get_all_messages()
            if msgs:
                self.set_active_message(msgs[0][0])
                return {'id': msgs[0][0], 'content': msgs[0][1]}
            return None
        finally:
            conn.close()
    
    def set_active_message(self, msg_id):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('UPDATE messages SET is_active = 0')
                conn.execute('UPDATE messages SET is_active = 1 WHERE msg_id = ?', (msg_id,))
                conn.commit()
            finally:
                conn.close()
    
    def delete_message(self, msg_id):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('DELETE FROM messages WHERE msg_id = ?', (msg_id,))
                conn.commit()
            finally:
                conn.close()
    
    def add_account(self, phone, session_str):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('INSERT OR REPLACE INTO accounts (phone, session_str, added_at, last_active, status) VALUES (?, ?, ?, ?, ?)', (phone, session_str, datetime.now(), datetime.now(), 'active'))
                conn.commit()
            finally:
                conn.close()
    
    def remove_account(self, phone):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('DELETE FROM accounts WHERE phone = ?', (phone,))
                conn.commit()
            finally:
                conn.close()
    
    def get_accounts(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT phone, status, total_posts, success_posts, failed_posts FROM accounts ORDER BY added_at DESC').fetchall()
        finally:
            conn.close()
    
    def get_accounts_only(self):
        """جلب الحسابات فقط (للحفظ عند تنظيف قاعدة البيانات)"""
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT phone, session_str FROM accounts').fetchall()
        finally:
            conn.close()
    
    def update_account_status(self, phone, status):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('UPDATE accounts SET status = ?, last_active = ? WHERE phone = ?', (status, datetime.now(), phone))
                conn.commit()
            finally:
                conn.close()
    
    def increment_account_posts(self, phone, success=True):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                if success:
                    conn.execute('UPDATE accounts SET total_posts = total_posts + 1, success_posts = success_posts + 1 WHERE phone = ?', (phone,))
                else:
                    conn.execute('UPDATE accounts SET total_posts = total_posts + 1, failed_posts = failed_posts + 1 WHERE phone = ?', (phone,))
                conn.commit()
            finally:
                conn.close()
    
    def add_group(self, group_id, group_name, group_username, group_type, members_count, added_by):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('INSERT OR IGNORE INTO groups (group_id, group_name, group_username, group_type, members_count, added_by, added_at) VALUES (?, ?, ?, ?, ?, ?, ?)', (str(group_id), group_name or "بدون اسم", group_username or "", group_type, members_count or 0, added_by, datetime.now()))
                conn.commit()
            finally:
                conn.close()
    
    def update_group_post(self, group_id):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('UPDATE groups SET post_count = post_count + 1, last_post = ? WHERE group_id = ?', (datetime.now(), str(group_id)))
                conn.commit()
            finally:
                conn.close()
    
    def get_all_groups(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT group_id, group_name, members_count, post_count, last_post FROM groups ORDER BY post_count DESC').fetchall()
        finally:
            conn.close()
    
    def log_post(self, phone, group_id, group_name, status='success', error=None):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('INSERT INTO posting_history (phone, group_id, group_name, sent_at, status, error) VALUES (?, ?, ?, ?, ?, ?)', (phone, str(group_id), group_name[:50], datetime.now(), status, error))
                if status == 'success':
                    self.increment_account_posts(phone, success=True)
                    self.update_group_post(group_id)
                else:
                    self.increment_account_posts(phone, success=False)
                conn.commit()
            finally:
                conn.close()
    
    def log_join(self, link, group_id, group_name, joined_by, status='success'):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('INSERT INTO join_history (link, group_id, group_name, joined_at, joined_by, status) VALUES (?, ?, ?, ?, ?, ?)', (link, str(group_id) if group_id else None, group_name[:50] if group_name else "غير معروف", datetime.now(), joined_by, status))
                conn.commit()
            finally:
                conn.close()
    
    def get_join_history(self, limit=50):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT link, group_name, joined_at, joined_by, status FROM join_history ORDER BY joined_at DESC LIMIT ?', (limit,)).fetchall()
        finally:
            conn.close()
    
    def get_join_stats(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            total = conn.execute('SELECT COUNT(*) FROM join_history').fetchone()[0]
            success = conn.execute("SELECT COUNT(*) FROM join_history WHERE status = 'success'").fetchone()[0]
            failed = conn.execute("SELECT COUNT(*) FROM join_history WHERE status = 'failed'").fetchone()[0]
            return {'total': total, 'success': success, 'failed': failed}
        finally:
            conn.close()
    
    def create_backup(self):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"{BACKUPS_DIR}/backup_{timestamp}.db"
        with db_lock:
            shutil.copy2(self.db_path, backup_file)
        backups = sorted(Path(BACKUPS_DIR).glob('backup_*.db'))
        if len(backups) > 20:
            for old in backups[:-20]:
                old.unlink()
        return backup_file
    
    def clean_database_keep_accounts(self):
        """حذف كل الجداول ماعدا الحسابات"""
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                # حفظ الحسابات مؤقتاً
                accounts = self.get_accounts_only()
                
                # حذف جميع الجداول
                conn.execute('DROP TABLE IF EXISTS messages')
                conn.execute('DROP TABLE IF EXISTS groups')
                conn.execute('DROP TABLE IF EXISTS posting_history')
                conn.execute('DROP TABLE IF EXISTS join_history')
                conn.execute('DROP TABLE IF EXISTS settings')
                
                # إعادة إنشاء الجداول
                conn.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP)''')
                conn.execute('''CREATE TABLE IF NOT EXISTS messages (msg_id TEXT PRIMARY KEY, content TEXT, created_at TIMESTAMP, is_active INTEGER DEFAULT 0)''')
                conn.execute('''CREATE TABLE IF NOT EXISTS groups (group_id TEXT PRIMARY KEY, group_name TEXT, group_username TEXT, group_type TEXT, members_count INTEGER DEFAULT 0, added_by TEXT, added_at TIMESTAMP, last_post TIMESTAMP, post_count INTEGER DEFAULT 0)''')
                conn.execute('''CREATE TABLE IF NOT EXISTS posting_history (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT, group_id TEXT, group_name TEXT, sent_at TIMESTAMP, status TEXT, error TEXT)''')
                conn.execute('''CREATE TABLE IF NOT EXISTS join_history (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, group_id TEXT, group_name TEXT, joined_at TIMESTAMP, joined_by TEXT, status TEXT)''')
                
                # استعادة الحسابات
                for phone, session_str in accounts:
                    conn.execute('INSERT OR REPLACE INTO accounts (phone, session_str, added_at, last_active, status, total_posts, success_posts, failed_posts) VALUES (?, ?, ?, ?, ?, 0, 0, 0)', 
                               (phone, session_str, datetime.now(), datetime.now(), 'active'))
                
                conn.commit()
                logger.success(f"✅ تم تنظيف قاعدة البيانات مع حفظ {len(accounts)} حساب")
                return len(accounts)
            finally:
                conn.close()

db = Database()

# ==================== المتغيرات العامة ====================

USER_CLIENTS = {}
SETTINGS = {
    'interval': 12,
    'encryption': True,
    'auto_join_enabled': True,
}
SETTINGS.update(db.get_all_settings())
TEMP = {}
is_posting = False
bot = None
start_time = datetime.now()

# ==================== وظائف مساعدة ====================

def format_number(num):
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    elif num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)

# ==================== الأزرار ====================

def main_buttons():
    enc_status = "✅ مفعل" if SETTINGS['encryption'] else "❌ معطل"
    active_msg = db.get_active_message()
    msg_preview = active_msg['content'][:20] + "..." if active_msg and len(active_msg['content']) > 20 else (active_msg['content'][:20] if active_msg else "لا يوجد")
    
    return [
        [Button.inline("➕ إضافة حساب", b"add"), Button.inline("🗑 حذف حساب", b"del_list")],
        [Button.inline("📝 إدارة الرسائل", b"manage_messages"), Button.inline("⏱ ضبط الوقت", b"time")],
        [Button.inline(f"📨 {msg_preview}", b"show_active")],
        [Button.inline("🚀 بدء النشر", b"start_p"), Button.inline("🛑 إيقاف النشر", b"stop_p")],
        [Button.inline(f"🛡 التشفير: {enc_status}", b"toggle_enc"), Button.inline("📊 الحالة", b"status")],
        [Button.inline("📢 المجموعات", b"view_chats")],
        [Button.inline("🔗 تقارير الانضمام", b"join_reports"), Button.inline("⚙️ إعدادات", b"advanced")],
        [Button.inline("💾 نسخ احتياطي", b"backup"), Button.inline("🗑 تنظيف قاعدة البيانات", b"clean_database")],
    ]

def messages_buttons():
    return [
        [Button.inline("📋 عرض الكل", b"list_messages")],
        [Button.inline("➕ إضافة جديدة", b"add_message")],
        [Button.inline("✅ تعيين نشطة", b"set_active_message")],
        [Button.inline("🗑 حذف رسالة", b"delete_message")],
        [Button.inline("⬅️ عودة", b"back")]
    ]

def advanced_buttons():
    auto_join = "✅" if SETTINGS.get('auto_join_enabled', True) else "❌"
    
    return [
        [Button.inline(f"🤖 انضمام تلقائي {auto_join}", b"toggle_autojoin")],
        [Button.inline("⬅️ عودة", b"back")]
    ]

def join_report_buttons():
    return [
        [Button.inline("📊 إحصائيات الانضمام", b"join_stats")],
        [Button.inline("📋 سجل الانضمام", b"join_history")],
        [Button.inline("⬅️ عودة", b"back")]
    ]

# ==================== المعالجات ====================

async def start_handler(event):
    if event.sender_id != ADMIN_ID:
        return
    accounts = db.get_accounts()
    groups = db.get_all_groups()
    active_msg = db.get_active_message()
    join_stats = db.get_join_stats()
    
    await event.respond(
        f"👋 **أهلاً بك في بوت النشر الخارق V5!**\n\n"
        f"📊 **الإحصائيات:**\n"
        f"• الحسابات: {len(accounts)}\n"
        f"• المجموعات: {len(groups)}\n"
        f"• الرسائل المحفوظة: {len(db.get_all_messages())}\n"
        f"• عمليات الانضمام: {join_stats['total']} (نجاح: {join_stats['success']})\n\n"
        f"🛡 **التشفير المتطور:** مفعل\n"
        f"⚡ **انضمام 20 رابط:** مفعل\n\n"
        f"📨 **الرسالة النشطة:**\n{active_msg['content'][:100] if active_msg else 'لا توجد'}\n\n"
        f"استخدم الأزرار للتحكم:", 
        buttons=main_buttons()
    )

async def callback_handler(event):
    global SETTINGS
    global is_posting
    
    if event.sender_id != ADMIN_ID:
        return
    
    data = event.data.decode()
    logger.info(f"🖱 نقرة: {data}")
    
    if data == "status":
        await show_status(event)
    elif data == "add":
        await event.edit("📱 أرسل رقم الهاتف مع رمز الدولة (مثال: +967...)"); 
        TEMP[ADMIN_ID] = "phone"
    elif data == "del_list":
        await show_delete_list(event)
    elif data.startswith("rm_"):
        await delete_account(event, data.replace("rm_", ""))
    elif data == "time":
        await event.edit("⏱ أرسل الفاصل الزمني (10-120 ثانية):"); 
        TEMP[ADMIN_ID] = "time"
    elif data == "toggle_enc":
        SETTINGS['encryption'] = not SETTINGS['encryption']
        db.save_setting('encryption', SETTINGS['encryption'])
        await event.answer(f"✅ التشفير المتطور {'مفعل' if SETTINGS['encryption'] else 'معطل'}")
        await event.edit("👋 لوحة التحكم:", buttons=main_buttons())
    elif data == "view_chats":
        await show_groups(event)
    elif data == "advanced":
        await event.edit("⚙️ الإعدادات", buttons=advanced_buttons())
    elif data == "back":
        await event.edit("👋 لوحة التحكم الرئيسية", buttons=main_buttons())
    elif data == "backup":
        await create_backup_handler(event)
    elif data == "show_active":
        active = db.get_active_message()
        if active:
            await event.answer(f"الرسالة النشطة: {active['content'][:50]}...", alert=True)
        else:
            await event.answer("❌ لا توجد رسالة نشطة", alert=True)
    elif data == "join_reports":
        await event.edit("🔗 **تقارير الانضمام**", buttons=join_report_buttons())
    elif data == "join_stats":
        await show_join_stats(event)
    elif data == "join_history":
        await show_join_history(event)
    
    elif data == "clean_database":
        await event.edit(
            "⚠️ **تنظيف قاعدة البيانات** ⚠️\n\n"
            "سيتم حذف:\n"
            "❌ جميع الرسائل المحفوظة\n"
            "❌ جميع المجموعات\n"
            "❌ سجل النشر\n"
            "❌ سجل الانضمام\n"
            "❌ الإعدادات\n\n"
            "✅ **سيتم الحفاظ على:**\n"
            "✓ جميع الحسابات المسجلة\n"
            "✓ جلسات الحسابات\n\n"
            "**هل أنت متأكد؟**",
            buttons=[
                [Button.inline("✅ نعم، نظف مع حفظ الحسابات", b"confirm_clean")],
                [Button.inline("❌ إلغاء", b"back")]
            ]
        )
    
    elif data == "confirm_clean":
        try:
            # إنشاء نسخة احتياطية قبل التنظيف
            backup_file = db.create_backup()
            logger.info(f"📦 تم إنشاء نسخة احتياطية: {backup_file}")
            
            # تنظيف مع حفظ الحسابات
            saved_accounts = db.clean_database_keep_accounts()
            
            # إعادة تعيين الإعدادات
            SETTINGS.update({
                'interval': 12,
                'encryption': True,
                'auto_join_enabled': True,
            })
            
            # إعادة إنشاء رسالة افتراضية
            if not db.get_all_messages():
                db.save_message("default", "📢 مرحباً بك!", is_active=True)
            
            await event.edit(
                f"✅ **تم تنظيف قاعدة البيانات بنجاح!**\n\n"
                f"• ✅ تم الحفاظ على {saved_accounts} حساب\n"
                f"• 📦 تم إنشاء نسخة احتياطية\n"
                f"• 🗑 تم حذف: الرسائل، المجموعات، السجلات\n\n"
                f"**ملاحظة:** حساباتك لا تزال موجودة وجاهزة للاستخدام\n\n"
                f"اضغط /start للبدء",
                buttons=[[Button.inline("🔄 العودة", b"back")]]
            )
        except Exception as e:
            await event.edit(f"❌ فشل التنظيف: {str(e)[:100]}", buttons=[[Button.inline("⬅️ عودة", b"back")]])
    
    elif data == "toggle_autojoin":
        SETTINGS['auto_join_enabled'] = not SETTINGS.get('auto_join_enabled', True)
        db.save_setting('auto_join_enabled', SETTINGS['auto_join_enabled'])
        await event.answer(f"✅ الانضمام التلقائي {'مفعل' if SETTINGS['auto_join_enabled'] else 'معطل'}")
        await event.edit("⚙️ الإعدادات:", buttons=advanced_buttons())
    
    elif data == "manage_messages":
        await event.edit("📝 **إدارة الرسائل**", buttons=messages_buttons())
    elif data == "list_messages":
        await list_all_messages(event)
    elif data == "add_message":
        await event.edit("📝 **أرسل نص الرسالة الجديدة:**")
        TEMP[ADMIN_ID] = "new_message"
    elif data == "set_active_message":
        await show_set_active_message(event)
    elif data.startswith("set_active_"):
        msg_id = data.replace("set_active_", "")
        db.set_active_message(msg_id)
        await event.answer("✅ تم تعيين الرسالة كنشطة", alert=True)
        await event.edit("📝 إدارة الرسائل", buttons=messages_buttons())
    elif data == "delete_message":
        await show_delete_message(event)
    elif data.startswith("del_msg_"):
        msg_id = data.replace("del_msg_", "")
        db.delete_message(msg_id)
        await event.answer("✅ تم حذف الرسالة", alert=True)
        await event.edit("📝 إدارة الرسائل", buttons=messages_buttons())
    
    elif data == "start_p":
        if not USER_CLIENTS:
            return await event.answer("❌ لا توجد حسابات!", alert=True)
        active_msg = db.get_active_message()
        if not active_msg:
            return await event.answer("❌ لا توجد رسالة نشطة!", alert=True)
        is_posting = True
        asyncio.create_task(poster())
        await event.edit("🚀 بدأ النشر", buttons=main_buttons())
    elif data == "stop_p":
        is_posting = False
        await event.edit("🛑 تم إيقاف النشر", buttons=main_buttons())

# ===== دوال العرض =====

async def list_all_messages(event):
    messages = db.get_all_messages()
    if not messages:
        await event.edit("📭 لا توجد رسائل", buttons=messages_buttons())
        return
    
    text = "📋 **جميع الرسائل المحفوظة**\n\n"
    for i, (msg_id, content, is_active) in enumerate(messages[:15], 1):
        status = "🌟 نشطة" if is_active else "📄 عادية"
        preview = content[:50] + "..." if len(content) > 50 else content
        text += f"{i}. {status}\n   `{preview}`\n   🆔 {msg_id}\n\n"
    
    await event.edit(text, buttons=messages_buttons())

async def show_set_active_message(event):
    messages = db.get_all_messages()
    if not messages:
        await event.answer("❌ لا توجد رسائل!", alert=True)
        return
    
    btns = []
    for msg_id, content, is_active in messages[:10]:
        preview = content[:25] + "..." if len(content) > 25 else content
        status = "🌟" if is_active else "📄"
        btns.append([Button.inline(f"{status} {preview}", f"set_active_{msg_id}".encode())])
    btns.append([Button.inline("⬅️ عودة", b"manage_messages")])
    await event.edit("✅ اختر الرسالة النشطة", buttons=btns)

async def show_delete_message(event):
    messages = db.get_all_messages()
    if not messages:
        await event.answer("❌ لا توجد رسائل!", alert=True)
        return
    
    btns = []
    for msg_id, content, is_active in messages[:10]:
        preview = content[:25] + "..." if len(content) > 25 else content
        status = "🌟" if is_active else "📄"
        btns.append([Button.inline(f"🗑 {status} {preview}", f"del_msg_{msg_id}".encode())])
    btns.append([Button.inline("⬅️ عودة", b"manage_messages")])
    await event.edit("🗑 اختر رسالة للحذف", buttons=btns)

async def show_join_stats(event):
    stats = db.get_join_stats()
    
    text = "🔗 **إحصائيات الانضمام**\n\n"
    text += f"📊 إجمالي المحاولات: {stats['total']}\n"
    text += f"✅ ناجح: {stats['success']}\n"
    text += f"❌ فاشل: {stats['failed']}\n"
    text += f"📈 نسبة النجاح: {stats['success']/(stats['total'] or 1)*100:.1f}%\n"
    
    await event.edit(text, buttons=join_report_buttons())

async def show_join_history(event):
    history = db.get_join_history(30)
    if not history:
        await event.edit("📭 لا توجد سجلات انضمام", buttons=join_report_buttons())
        return
    
    text = "🔗 **آخر 30 عملية انضمام**\n\n"
    for link, group_name, joined_at, joined_by, status in history:
        time_str = datetime.fromisoformat(joined_at).strftime('%H:%M:%S')
        icon = "✅" if status == 'success' else "❌"
        text += f"{icon} {time_str} - {group_name[:25]}\n"
        text += f"   🔗 {link[:40]}...\n"
        text += f"   📱 {joined_by[-8:]}\n\n"
    
    await event.edit(text, buttons=join_report_buttons())

async def show_status(event):
    accounts = db.get_accounts()
    groups = db.get_all_groups()
    join_stats = db.get_join_stats()
    messages_count = len(db.get_all_messages())
    active_msg = db.get_active_message()
    uptime = datetime.now() - start_time
    hours = uptime.total_seconds() // 3600
    minutes = (uptime.total_seconds() % 3600) // 60
    
    active_accounts = len([a for a in accounts if a[1] == 'active'])
    
    text = f"📊 **حالة البوت V5**\n\n"
    text += f"⏰ **وقت التشغيل:** {int(hours)} س {int(minutes)} د\n"
    text += f"👤 **الحسابات:** {active_accounts}/{len(accounts)}\n"
    text += f"📢 **المجموعات:** {len(groups)}\n"
    text += f"📝 **الرسائل:** {messages_count}\n"
    text += f"🔗 **عمليات الانضمام:** {join_stats['total']}\n"
    text += f"⚙️ **الفاصل:** {SETTINGS['interval']} ثانية\n"
    text += f"🛡 **التشفير المتطور:** {'🟢 مفعل' if SETTINGS['encryption'] else '🔴 معطل'}\n"
    text += f"🔄 **النشر:** {'🟢 نشط' if is_posting else '🔴 متوقف'}\n\n"
    
    if active_msg:
        text += f"📨 **الرسالة النشطة:**\n{active_msg['content'][:100]}..."
    
    await event.edit(text, buttons=main_buttons())

async def show_delete_list(event):
    accounts = db.get_accounts()
    if not accounts:
        return await event.answer("❌ لا توجد حسابات", alert=True)
    
    btns = []
    for phone, status, posts, success, failed in accounts[:10]:
        short = phone[-8:] if len(phone) > 8 else phone
        status_icon = "🟢" if status == 'active' else "🔴"
        btns.append([Button.inline(f"{status_icon} {short} ({posts})", f"rm_{phone}".encode())])
    
    btns.append([Button.inline("⬅️ عودة", b"back")])
    await event.edit("🗑 اختر حساباً للحذف", buttons=btns)

async def show_groups(event):
    groups = db.get_all_groups()
    
    text = f"📢 **المجموعات**\nالإجمالي: {len(groups)}\n\n"
    
    for gid, name, members, posts, last in groups[:20]:
        name_short = name[:25] if name else "بدون اسم"
        members_fmt = format_number(members) if members else "?"
        text += f"✅ {name_short}\n   👥 {members_fmt} | 📨 {posts}\n"
    
    if len(groups) > 20:
        text += f"\n... و {len(groups) - 20} مجموعة أخرى"
    
    await event.edit(text, buttons=main_buttons())

# ===== دوال الإجراءات =====

async def delete_account(event, phone):
    if phone in USER_CLIENTS:
        await USER_CLIENTS[phone].disconnect()
        del USER_CLIENTS[phone]
    db.remove_account(phone)
    await event.answer(f"✅ تم حذف {phone}", alert=True)
    await show_delete_list(event)

async def create_backup_handler(event):
    try:
        backup_file = db.create_backup()
        await event.answer(f"✅ تم إنشاء النسخة", alert=True)
    except Exception as e:
        await event.answer(f"❌ فشل النسخ: {e}", alert=True)

# ===== معالج النصوص والانضمام لـ 20 رابط =====

async def text_handler(event):
    state = TEMP.get(ADMIN_ID)
    text = event.message.text.strip()
    
    if state == "new_message":
        msg_id = f"msg_{int(time.time())}"
        db.save_message(msg_id, text, is_active=False)
        TEMP.pop(ADMIN_ID)
        await event.respond(f"✅ **تم إضافة الرسالة!**\n\n📝 {text[:100]}...\n🆔 {msg_id}", buttons=messages_buttons())
        return
    
    elif state == "phone":
        await handle_phone_login(event, text)
    
    elif state == "time":
        try:
            interval = int(text)
            if 10 <= interval <= 120:
                SETTINGS['interval'] = interval
                db.save_setting('interval', interval)
                TEMP.pop(ADMIN_ID)
                await event.respond(f"✅ تم ضبط الوقت على {text} ثانية", buttons=main_buttons())
            else:
                await event.respond("❌ الرجاء إدخال قيمة بين 10 و 120")
        except:
            await event.respond("❌ أرسل رقماً فقط")
    
    else:
        # استخراج جميع الروابط (حتى 20 رابط)
        links = re.findall(r"(https?://t\.me/(?:joinchat/|\+)[a-zA-Z0-9_-]+|https?://t\.me/[a-zA-Z0-9_]+)", text)
        if links and SETTINGS.get('auto_join_enabled', True) and USER_CLIENTS:
            await handle_multi_join(event, links[:20])

async def handle_multi_join(event, links):
    """الانضمام لـ 20 رابط في رسالة واحدة"""
    total_links = len(links)
    await event.respond(
        f"🚀 **انضمام لـ {total_links} رابط**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 جاري معالجة {total_links} رابط\n"
        f"🛡 تشغيل الحماية المتقدمة\n\n"
        f"جاري البدء..."
    )
    
    success_count = 0
    failed_count = 0
    
    for i, link in enumerate(links, 1):
        joined = False
        
        for phone, client in USER_CLIENTS.items():
            if joined:
                break
                
            try:
                # تأخير قصير بين المحاولات (10-20 ثانية)
                delay = random.randint(10, 20)
                logger.info(f"⏸ انتظار {delay} ثانية قبل الرابط {i}/{total_links}")
                await asyncio.sleep(delay)
                
                group_info = None
                if "joinchat" in link or "+" in link:
                    hash_part = link.split('/')[-1].replace('+', '')
                    logger.info(f"🔗 [{i}/{total_links}] انضمام عبر دعوة...")
                    updates = await client(ImportChatInviteRequest(hash_part))
                    if updates.chats:
                        chat = updates.chats[0]
                        group_info = (chat.id, chat.title)
                else:
                    username = link.split('/')[-1]
                    logger.info(f"🔗 [{i}/{total_links}] انضمام إلى @{username}...")
                    entity = await client.get_entity(username)
                    if entity:
                        await client(JoinChannelRequest(link))
                        group_info = (entity.id, getattr(entity, 'title', username))
                
                success_count += 1
                joined = True
                logger.success(f"✅ تم الانضمام إلى {link[:50]} باستخدام {phone[-8:]}")
                
                # تسجيل في قاعدة البيانات
                if group_info:
                    group_id, group_name = group_info
                    db.log_join(link, group_id, group_name[:50], phone, 'success')
                    db.add_group(group_id, group_name[:50], None, 'group', 0, phone)
                
                break
                
            except FloodWaitError as e:
                wait_time = e.seconds + random.randint(10, 30)
                logger.warning(f"⏳ FloodWait: انتظار {wait_time} ثانية...")
                await asyncio.sleep(wait_time)
                continue
                
            except Exception as e:
                logger.error(f"❌ فشل انضمام {link[:50]}: {e}")
                db.log_join(link, None, "غير معروف", phone, 'failed')
                continue
        
        if not joined:
            failed_count += 1
            logger.warning(f"⚠️ فشل الانضمام لـ {link[:50]} بجميع الحسابات")
            db.log_join(link, None, "غير معروف", "all", 'failed')
    
    await asyncio.sleep(random.randint(5, 10))
    
    result_text = f"📊 **نتيجة الانضمام لـ {total_links} رابط**\n"
    result_text += f"━━━━━━━━━━━━━━━━━━━━\n"
    result_text += f"✅ نجاح: {success_count}\n"
    result_text += f"❌ فشل: {failed_count}\n"
    result_text += f"📈 نسبة النجاح: {success_count/total_links*100:.1f}%\n"
    result_text += f"🛡 تم استخدام التشفير المتقدم"
    
    await event.respond(result_text)

# دوال تسجيل الدخول
async def handle_phone_login(event, phone):
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        await client.send_code_request(phone)
        TEMP[ADMIN_ID] = {"s": "code", "p": phone, "c": client}
        await event.respond(f"📩 أرسل الكود لـ {phone}:")
    except Exception as e:
        await event.respond(f"❌ خطأ: {str(e)[:100]}")

async def handle_code_verification(event, state, code):
    try:
        client = state["c"]
        phone = state["p"]
        await client.sign_in(phone, code)
        USER_CLIENTS[phone] = client
        db.add_account(phone, client.session.save())
        await event.respond(f"✅ تم تفعيل الحساب {phone}!")
        TEMP.pop(ADMIN_ID)
        await refresh_groups_async()
    except SessionPasswordNeededError:
        TEMP[ADMIN_ID]["s"] = "pass"
        await event.respond("🔐 أرسل كلمة المرور:")
    except Exception as e:
        await event.respond(f"❌ فشل: {str(e)[:100]}")

async def handle_password(event, state, password):
    try:
        await state["c"].sign_in(password=password)
        USER_CLIENTS[state["p"]] = state["c"]
        db.add_account(state["p"], state["c"].session.save())
        await event.respond(f"✅ تم التفعيل بنجاح!")
        TEMP.pop(ADMIN_ID)
        await refresh_groups_async()
    except Exception as e:
        await event.respond(f"❌ خطأ: {str(e)[:100]}")

async def refresh_groups_async():
    count = 0
    for phone, client in USER_CLIENTS.items():
        try:
            async for dialog in client.iter_dialogs():
                if dialog.is_group:
                    members = getattr(dialog.entity, 'participants_count', 0)
                    db.add_group(dialog.id, dialog.name, getattr(dialog.entity, 'username', None), 'group', members, phone)
                    count += 1
        except:
            pass
    logger.info(f"✅ تم تحديث {count} مجموعة")

# ===== دالة النشر =====
async def poster():
    global is_posting
    logger.info("🚀 بدء النشر مع التشفير المتقدم...")
    
    stats = {'total': 0, 'success': 0, 'failed': 0}
    
    while is_posting:
        try:
            if not USER_CLIENTS:
                await asyncio.sleep(10)
                continue
            
            active_msg = db.get_active_message()
            if not active_msg:
                logger.warning("⚠️ لا توجد رسالة نشطة")
                await asyncio.sleep(5)
                continue
            
            original_text = active_msg['content']
            
            accounts_list = list(USER_CLIENTS.items())
            
            for phone, client in accounts_list:
                if not is_posting:
                    break
                
                try:
                    groups_sent = 0
                    groups_list = []
                    
                    async for dialog in client.iter_dialogs():
                        if dialog.is_group and groups_sent < 50:
                            groups_list.append(dialog)
                    
                    random.shuffle(groups_list)
                    
                    for dialog in groups_list:
                        if not is_posting:
                            break
                        
                        db.add_group(dialog.id, dialog.name, 
                                   getattr(dialog.entity, 'username', None),
                                   'group', 
                                   getattr(dialog.entity, 'participants_count', 0), 
                                   phone)
                        
                        # استخدام نظام النشر الآمن مع التشفير المتقدم
                        success, result = await safe_poster.send_safe(
                            client, dialog.id, original_text, dialog.name
                        )
                        
                        if success:
                            db.log_post(phone, dialog.id, dialog.name, 'success')
                            groups_sent += 1
                            stats['success'] += 1
                            logger.info(f"✅ [{phone[-8:]}] أرسل لـ {dialog.name[:30]}")
                        else:
                            stats['failed'] += 1
                            logger.warning(f"⚠️ فشل لـ {dialog.name[:30]}: {result[:50]}")
                        
                        stats['total'] += 1
                        
                        delay = safe_poster.random_delay(SETTINGS.get('interval', 12))
                        await asyncio.sleep(delay)
                    
                    logger.info(f"📊 [{phone[-8:]}] أرسل {groups_sent} رسالة")
                    
                except Exception as e:
                    logger.error(f"❌ خطأ في الحساب {phone[-8:]}: {e}")
                    db.update_account_status(phone, 'error')
            
            logger.info(f"📈 إحصائيات الدورة: {stats['success']} نجاح / {stats['failed']} فشل")
            
            cycle_wait = random.randint(60, 120)
            logger.info(f"⏸ استراحة {cycle_wait} ثانية...")
            await asyncio.sleep(cycle_wait)
            
        except Exception as e:
            logger.error(f"💥 خطأ في حلقة النشر: {e}")
            await asyncio.sleep(30)

# استعادة الجلسات
async def restore_sessions():
    restored = 0
    accounts = db.get_accounts()
    logger.info(f"🔍 محاولة استعادة {len(accounts)} حساب...")
    
    for account in accounts:
        try:
            if len(account) < 2:
                continue
            phone = account[0]
            session_str = None
            
            conn = sqlite3.connect(DB_PATH, timeout=15)
            try:
                result = conn.execute('SELECT session_str FROM accounts WHERE phone = ?', (phone,)).fetchone()
                if result and result[0]:
                    session_str = result[0]
            finally:
                conn.close()
            
            if not session_str:
                logger.warning(f"⚠️ لا توجد جلسة للحساب {phone}")
                continue
            
            client = TelegramClient(StringSession(session_str), API_ID, API_HASH)
            await client.connect()
            
            if await client.is_user_authorized():
                USER_CLIENTS[phone] = client
                db.update_account_status(phone, 'active')
                restored += 1
                logger.success(f"✅ تم استعادة {phone}")
            else:
                db.update_account_status(phone, 'unauthorized')
                logger.warning(f"⚠️ الحساب {phone} غير مصرح به")
                
        except Exception as e:
            logger.error(f"❌ فشل استعادة حساب: {e}")
            if len(account) > 0:
                db.update_account_status(account[0], 'error')
    
    logger.info(f"✅ تم استعادة {restored} من أصل {len(accounts)} حساب")
    return restored

# ==================== التشغيل الرئيسي ====================

async def main():
    global bot, start_time
    start_time = datetime.now()
    
    # تشغيل خادم الويب
    Thread(target=run_web, daemon=True).start()
    print("🌐 خادم الويب يعمل على المنفذ 10000")
    
    print("🚀 جاري تشغيل البوت V5...")
    print("👤 ADMIN_ID المستخدم:", ADMIN_ID)
    
    # استعادة الحسابات المحفوظة
    await restore_sessions()
    
    # تشغيل البوت
    bot = TelegramClient('bot_session', API_ID, API_HASH)
    await bot.start(bot_token=BOT_TOKEN)
    
    me = await bot.get_me()
    print(f"✅ البوت متصل: @{me.username}")
    print(f"👤 آيدي البوت: {me.id}")
    
    @bot.on(events.NewMessage(pattern='/start'))
    async def start(e):
        await start_handler(e)
    
    @bot.on(events.CallbackQuery())
    async def callback(e):
        await callback_handler(e)
    
    @bot.on(events.NewMessage)
    async def text(e):
        if e.message.text and e.sender_id == ADMIN_ID:
            state = TEMP.get(ADMIN_ID)
            if isinstance(state, dict) and state.get("s") == "code":
                await handle_code_verification(e, state, e.message.text.strip())
            elif isinstance(state, dict) and state.get("s") == "pass":
                await handle_password(e, state, e.message.text.strip())
            else:
                await text_handler(e)
        elif e.is_group and e.message.text:
            await text_handler(e)
    
    logger.success("✅ البوت V5 جاهز! أرسل /start")
    print("🎉 البوت يعمل مع:")
    print("   - تشفير متقدم جداً (لا يغير نص المنشور)")
    print("   - انضمام لـ 20 رابط في الرسالة")
    print("   - حفظ الحسابات عند تنظيف قاعدة البيانات")
    print("   - تقارير انضمام فقط")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 تم إيقاف البوت")
    except Exception as e:
        logger.critical(f"💥 خطأ: {e}")
        time.sleep(5)
        os.execl(sys.executable, sys.executable, *sys.argv)
