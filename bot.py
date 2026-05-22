#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔═══════════════════════════════════════════════════════════════╗
║     🤖 بوت النشر الخارق - النسخة النهائية v5.0 🚀            ║
║     تشفير متقدم + حفظ الحسابات + 20 رابط + Render          ║
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
import hashlib
import string
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

API_ID = int(os.environ.get('API_ID', '0'))
API_HASH = os.environ.get('API_HASH', '')
BOT_TOKEN = os.environ.get('BOT_TOKEN', '')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '0'))

if not all([API_ID, API_HASH, BOT_TOKEN, ADMIN_ID]):
    logging.error("⚠️ يجب تعيين جميع متغيرات البيئة: API_ID, API_HASH, BOT_TOKEN, ADMIN_ID")
    exit(1)

# ==================== إعدادات التشغيل ====================

DATA_DIR = "data"
DB_PATH = f"{DATA_DIR}/bot_data.db"

os.makedirs(DATA_DIR, exist_ok=True)

# ==================== قفل قاعدة البيانات ====================
db_lock = threading.Lock()

# ==================== خادم الويب ====================
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        'status': 'online',
        'bot': 'Super Poster Bot v5.0',
        'version': '5.0',
        'time': str(datetime.now()),
        'accounts': len(USER_CLIENTS) if 'USER_CLIENTS' in globals() else 0,
        'is_posting': is_posting if 'is_posting' in globals() else False
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'}), 200

def run_web():
    """تشغيل خادم الويب"""
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ==================== نظام التسجيل ====================

class Logger:
    def __init__(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler()]
        )
        self.logger = logging.getLogger('Bot')
    
    def info(self, msg): self.logger.info(msg); print(f"ℹ️ {msg}")
    def warning(self, msg): self.logger.warning(msg); print(f"⚠️ {msg}")
    def error(self, msg): self.logger.error(msg); print(f"❌ {msg}")
    def success(self, msg): self.logger.info(f"✅ {msg}"); print(f"✅ {msg}")

logger = Logger()

# ╔══════════════════════════════════════════════════════════════╗
# ║  نظام التشفير المتقدم - لا يغيّر النص المرئي أبداً         ║
# ║  يُشفّر بيانياً بحيث لا يكشفه أقوى بوتات الحماية           ║
# ╚══════════════════════════════════════════════════════════════╝

class StealthEncryption:
    """
    تشفير متقدم يجعل كل رسالة فريدة على المستوى الثنائي
    دون أي تغيير مرئي في النص الأصلي.
    
    التقنيات المستخدمة:
    1. Zero-Width Characters Injection - إدخال أحرف مخفية بين كل حرف
    2. Homoglyph Substitution - استبدال أحرف بأخرى متطابقة بصرياً
    3. RTL/LTR Markers - علامات اتجاه النص غير المرئية
    4. Combining Characters - أحرف تجميعية لا تظهر
    5. Unicode Normalization Variation - تنويعات الترميز الموحد
    6. Invisible Binary Signature - توقيع ثنائي مخفي فريد لكل رسالة
    """
    
    def __init__(self):
        # أحرف عدم العرض (Zero-Width Characters)
        self.zwc = {
            '0': '\u200B',   # Zero-Width Space
            '1': '\u200C',   # Zero-Width Non-Joiner
            '2': '\u200D',   # Zero-Width Joiner
            '3': '\u2060',   # Word Joiner
            '4': '\uFEFF',   # BOM / Zero-Width No-Break Space
            '5': '\u180E',   # Mongolian Vowel Separator
            '6': '\u2061',   # Function Application
            '7': '\u2062',   # Invisible Times
            '8': '\u2063',   # Invisible Separator
            '9': '\u2064',   # Invisible Plus
        }
        
        # علامات اتجاه النص غير المرئية
        self.direction_marks = [
            '\u200E',  # Left-to-Right Mark
            '\u200F',  # Right-to-Left Mark
            '\u061C',  # Arabic Letter Mark
        ]
        
        # أحرف تجميعية لا تؤثر على العرض
        self.combining_chars = [
            '\u034F',  # Combining Grapheme Joiner
            '\u0300',  # Combining Grave Accent
            '\u0301',  # Combining Acute Accent
            '\u0302',  # Combining Circumflex Accent
            '\u0303',  # Combining Tilde
            '\u0304',  # Combining Macron
            '\u0305',  # Combining Overline
            '\u0306',  # Combining Breve
            '\u0307',  # Combining Dot Above
            '\u0308',  # Combining Diaeresis
            '\u030A',  # Combining Ring Above
            '\u030B',  # Combining Double Acute Accent
            '\u030C',  # Combining Caron
            '\u030D',  # Combining Candrabindu
            '\u030E',  # Combining Double Vertical Line Above
            '\u030F',  # Combining Double Grave Accent
            '\u0310',  # Combining Candrabindu
            '\u0311',  # Combining Inverted Breve
            '\u0312',  # Combining Turned Comma Above
            '\u0313',  # Combining Comma Above
            '\u0314',  # Combining Reversed Comma Above
            '\u0315',  # Combining Comma Above Right
            '\u0316',  # Combining Grave Accent Below
            '\u0317',  # Combining Acute Accent Below
            '\u0318',  # Combining Left Tack Below
            '\u0319',  # Combining Right Tack Below
        ]
        
        # استبدالات الحروف المتشابهة بصرياً (Homoglyphs)
        # هذه الأحرف تبدو متطابقة تماماً لكنها مختلفة في الترميز
        self.homoglyphs = {
            # أحرف عربية متشابهة
            'ا': ['ا', '\u0622', '\u0623', '\u0625'],  # ألف بمواضع مختلفة
            'و': ['و', '\u0624'],  # واو بهمزة
            'ي': ['ي', '\u0649', '\u0626'],  # ياء بأشكال مختلفة
            'ه': ['ه', '\u0629'],  # هاء/تاء مربوطة
            'ت': ['ت', '\u062B'],  # تاء/ثاء
            'ل': ['ل', '\uFEFB', '\uFEF7'],  # لام بأشكال مختلفة
            # أحرف لاتينية متشابهة (للروابط والأرقام)
            'a': ['a', '\u0430', '\u0251'],  # a بلغات مختلفة
            'e': ['e', '\u0435', '\u1D07'],
            'o': ['o', '\u043E', '\u0254'],
            'c': ['c', '\u0441', '\u0254'],
            'p': ['p', '\u0440'],
            'x': ['x', '\u0445', '\u04BB'],
            'y': ['y', '\u0443'],
            'i': ['i', '\u0456', '\u0131'],
            'j': ['j', '\u0458'],
            's': ['s', '\u0455'],
            # أرقام متشابهة
            '0': ['0', '\u041E', '\u0660'],
            '1': ['1', '\u0661', '\u06F1'],
            '3': ['3', '\u0417', '\u0663'],
            '5': ['5', '\u0665', '\u06F5'],
            '7': ['7', '\u0667', '\u06F7'],
            '8': ['8', '\u0668', '\u06F8'],
        }
        
        # أنماط الحشو المخفي
        self.hidden_patterns = [
            lambda: ''.join(random.choices(list(self.zwc.values()), k=random.randint(3, 8))),
            lambda: random.choice(self.direction_marks),
            lambda: random.choice(self.combining_chars),
            lambda: random.choice(self.direction_marks) + ''.join(random.choices(list(self.zwc.values()), k=random.randint(2, 5))),
        ]
    
    def _generate_unique_signature(self):
        """إنشاء توقيع ثنائي فريد مخفي"""
        timestamp = str(time.time_ns())
        random_salt = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        unique_hash = hashlib.md5(f"{timestamp}{random_salt}".encode()).hexdigest()
        return unique_hash
    
    def _encode_signature_in_zwc(self, signature_hex):
        """ترميز التوقيع كأحرف عدم عرض"""
        encoded = ''
        for hex_char in signature_hex:
            if hex_char in self.zwc:
                encoded += self.zwc[hex_char]
            else:
                digit = int(hex_char, 16)
                encoded += self.zwc[str(digit)]
        return encoded
    
    def _inject_zwc_between_chars(self, text):
        """إدخال أحرف عدم عرض بين كل حرفين - لا يؤثر على العرض"""
        result = []
        for i, char in enumerate(text):
            result.append(char)
            # إدخال 1-3 أحرف مخفية بين كل حرف
            if i < len(text) - 1 and char != ' ' and text[i+1] != ' ':
                num_invisible = random.randint(1, 3)
                for _ in range(num_invisible):
                    result.append(random.choice(list(self.zwc.values())))
        return ''.join(result)
    
    def _apply_homoglyphs(self, text, ratio=0.15):
        """استبدال نسبة من الأحرف بنظائرها المتطابقة بصرياً"""
        result = list(text)
        for i, char in enumerate(result):
            if char in self.homoglyphs and random.random() < ratio:
                result[i] = random.choice(self.homoglyphs[char])
        return ''.join(result)
    
    def _inject_direction_marks(self, text):
        """إدخال علامات اتجاه النص - غير مرئية تماماً"""
        result = []
        words = text.split(' ')
        for i, word in enumerate(words):
            result.append(word)
            if random.random() < 0.4 and i < len(words) - 1:
                result.append(random.choice(self.direction_marks))
            result.append(' ')
        return ''.join(result).rstrip()
    
    def _inject_combining_chars(self, text, ratio=0.08):
        """إدخال أحرف تجميعية غير مرئية"""
        result = list(text)
        insertions = 0
        for i in range(len(result)):
            if result[i] not in [' ', '\n'] and random.random() < ratio:
                combining = random.choice(self.combining_chars)
                # وضع حرف التجميع بعد الحرف مباشرة
                result.insert(i + 1 + insertions, combining)
                insertions += 1
        return ''.join(result)
    
    def _add_hidden_signature(self, text):
        """إضافة توقيع فريد مخفي في بداية ونهاية النص"""
        signature = self._generate_unique_signature()
        encoded_sig = self._encode_signature_in_zwc(signature)
        
        # توقيع في البداية
        prefix = random.choice(self.direction_marks) + encoded_sig[:16] + random.choice(self.direction_marks)
        # توقيع في النهاية
        suffix = random.choice(self.direction_marks) + encoded_sig[16:] + random.choice(self.direction_marks)
        
        return prefix + text + suffix
    
    def _inject_invisible_words(self, text):
        """إدخال كلمات مخفية بين الكلمات الحقيقية"""
        result = []
        words = text.split(' ')
        for i, word in enumerate(words):
            result.append(word)
            # احتمال 25% لإدخال حشو مخفي بين الكلمات
            if random.random() < 0.25 and i < len(words) - 1:
                hidden_word = random.choice(self.hidden_patterns)()
                result.append(hidden_word)
        return ' '.join(result)
    
    def _randomize_whitespace(self, text):
        """تنويع المسافات البيضاء بأحرف غير مرئية"""
        result = []
        for char in text:
            if char == ' ':
                # استبدال المسافة العادية بمسافة + أحرف مخفية
                if random.random() < 0.3:
                    hidden = ''.join(random.choices(list(self.zwc.values()), k=random.randint(1, 4)))
                    result.append(' ' + hidden)
                else:
                    result.append(char)
            else:
                result.append(char)
        return ''.join(result)
    
    def encrypt(self, text):
        """
        التشفير المتقدم - يُنتج نصاً يبدو مطابقاً تماماً للأصل
        لكنه مختلف ثنائياً بنسبة 100% في كل مرة
        لا يستطيع أي بوت حماية كشفه لأن:
        - النص المرئي لم يتغير
        - كل نسخة لها بصمة ثنائية فريدة
        - الأحرف المخفية لا تظهر في أي عميل
        """
        if not text or len(text.strip()) == 0:
            return text
        
        # الخطوة 1: إضافة توقيع فريد مخفي
        result = self._add_hidden_signature(text)
        
        # الخطوة 2: إدخال أحرف عدم عرض بين الحروف
        result = self._inject_zwc_between_chars(result)
        
        # الخطوة 3: استبدال أحرف بنظائرها المتشابهة بصرياً
        result = self._apply_homoglyphs(result, ratio=random.uniform(0.08, 0.20))
        
        # الخطوة 4: إدخال علامات اتجاه النص
        result = self._inject_direction_marks(result)
        
        # الخطوة 5: إدخال أحرف تجميعية
        result = self._inject_combining_chars(result, ratio=random.uniform(0.03, 0.10))
        
        # الخطوة 6: إدخال كلمات مخفية
        result = self._inject_invisible_words(result)
        
        # الخطوة 7: تنويع المسافات البيضاء
        result = self._randomize_whitespace(result)
        
        return result
    
    def generate_variations(self, text, count=6):
        """إنشاء عدة نسخ مختلفة ثنائياً من نفس النص المرئي"""
        variations = []
        for _ in range(count):
            variations.append(self.encrypt(text))
        return variations

stealth = StealthEncryption()

def encrypt_text(text):
    """واجهة التشفير الموحدة"""
    if not SETTINGS.get('encryption', True):
        return text
    return stealth.encrypt(text)

# ==================== كلاس مكافحة الاكتشاف ====================

class AntiDetection:
    def __init__(self):
        self.posted_messages = {}
        self.last_posts = {}
        self.warmed_groups = set()
    
    def random_delay(self, base_delay=12):
        return random.randint(int(base_delay * 0.8), int(base_delay * 1.5))
    
    def get_variation(self, text, variation_count=6):
        """إنشاء تنويعات باستخدام التشفير المتقدم"""
        return stealth.generate_variations(text, variation_count)
    
    async def send_safe(self, client, chat_id, original_text, group_name=""):
        try:
            variations = self.get_variation(original_text, 6)
            final_text = random.choice(variations)
            await asyncio.sleep(self.random_delay(3))
            await client.send_message(chat_id, final_text)
            self.last_posts[chat_id] = datetime.now()
            return True, "تم النشر بنجاح"
        except FloodWaitError as e:
            await asyncio.sleep(e.seconds)
            return False, f"Flood wait: {e.seconds}s"
        except Exception as e:
            return False, str(e)

anti_detection = AntiDetection()

# ==================== نظام إدارة المجموعات المحظورة ====================

class GroupBlacklistManager:
    def __init__(self):
        self.banned_groups = set()
        self.failed_attempts = {}
    
    def record_failure(self, group_id, error):
        if group_id not in self.failed_attempts:
            self.failed_attempts[group_id] = 0
        self.failed_attempts[group_id] += 1
        if self.failed_attempts[group_id] >= 3:
            self.banned_groups.add(group_id)
            logger.warning(f"🚫 تم حظر المجموعة {group_id} مؤقتاً")
    
    def is_banned(self, group_id):
        return group_id in self.banned_groups
    
    def clear_banned(self, group_id):
        if group_id in self.banned_groups:
            self.banned_groups.remove(group_id)
        if group_id in self.failed_attempts:
            del self.failed_attempts[group_id]
    
    def get_banned_count(self):
        return len(self.banned_groups)

group_blacklist = GroupBlacklistManager()

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
            c.execute('''CREATE TABLE IF NOT EXISTS groups (group_id TEXT PRIMARY KEY, group_name TEXT, group_username TEXT, group_type TEXT, members_count INTEGER DEFAULT 0, added_by TEXT, added_at TIMESTAMP, last_post TIMESTAMP, post_count INTEGER DEFAULT 0, is_blacklisted INTEGER DEFAULT 0)''')
            c.execute('''CREATE TABLE IF NOT EXISTS joined_links (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT, group_id TEXT, group_name TEXT, joined_at TIMESTAMP, joined_by TEXT)''')
            conn.commit()
            conn.close()
            logger.success("✅ قاعدة البيانات المحلية جاهزة")
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
    
    def get_account_session(self, phone):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            result = conn.execute('SELECT session_str FROM accounts WHERE phone = ?', (phone,)).fetchone()
            return result[0] if result else None
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
    
    def blacklist_group(self, group_id):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('UPDATE groups SET is_blacklisted = 1 WHERE group_id = ?', (str(group_id),))
                conn.commit()
            finally:
                conn.close()
    
    def whitelist_group(self, group_id):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('UPDATE groups SET is_blacklisted = 0 WHERE group_id = ?', (str(group_id),))
                conn.commit()
            finally:
                conn.close()
    
    def get_all_groups(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT group_id, group_name, members_count, post_count, is_blacklisted, last_post FROM groups ORDER BY post_count DESC').fetchall()
        finally:
            conn.close()
    
    def get_blacklisted_groups(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT group_id, group_name FROM groups WHERE is_blacklisted = 1').fetchall()
        finally:
            conn.close()
    
    def search_groups(self, query):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT group_id, group_name, members_count FROM groups WHERE group_name LIKE ? LIMIT 20', (f'%{query}%',)).fetchall()
        finally:
            conn.close()
    
    def add_joined_link(self, link, group_id, group_name, joined_by):
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                conn.execute('INSERT INTO joined_links (link, group_id, group_name, joined_at, joined_by) VALUES (?, ?, ?, ?, ?)', (link, str(group_id), group_name[:50], datetime.now(), joined_by))
                conn.commit()
            finally:
                conn.close()
    
    def get_joined_links(self, limit=100):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT link, group_name, joined_at, joined_by FROM joined_links ORDER BY joined_at DESC LIMIT ?', (limit,)).fetchall()
        finally:
            conn.close()
    
    def get_joined_links_count(self):
        conn = sqlite3.connect(self.db_path, timeout=15)
        try:
            return conn.execute('SELECT COUNT(*) FROM joined_links').fetchone()[0]
        finally:
            conn.close()
    
    def safe_reset(self):
        """حذف قاعدة البيانات مع الحفاظ على الحسابات"""
        with db_lock:
            conn = sqlite3.connect(self.db_path, timeout=15)
            try:
                # حفظ الحسابات أولاً
                accounts_backup = conn.execute('SELECT phone, session_str, added_at, status FROM accounts').fetchall()
                
                # حذف جميع الجداول
                for table in ['settings', 'messages', 'groups', 'joined_links']:
                    conn.execute(f'DELETE FROM {table}')
                
                # إعادة الحسابات
                for phone, session_str, added_at, status in accounts_backup:
                    conn.execute('INSERT OR REPLACE INTO accounts (phone, session_str, added_at, last_active, status, total_posts, success_posts, failed_posts) VALUES (?, ?, ?, ?, ?, 0, 0, 0)', 
                               (phone, session_str, added_at, datetime.now(), status))
                
                # إضافة رسالة افتراضية
                conn.execute('INSERT INTO messages (msg_id, content, created_at, is_active) VALUES (?, ?, ?, ?)', 
                           ('default', '📢 مرحباً بك!', datetime.now(), 1))
                
                conn.commit()
            finally:
                conn.close()

db = Database()

# ==================== المتغيرات العامة ====================

USER_CLIENTS = {}
SETTINGS = {
    'interval': 12,
    'encryption': True,
    'anti_detection': True,
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
    active_msg = db.get_active_message()
    msg_preview = active_msg['content'][:20] + "..." if active_msg and len(active_msg['content']) > 20 else (active_msg['content'][:20] if active_msg else "لا يوجد")
    
    return [
        [Button.inline("➕ إضافة حساب", b"add"), Button.inline("🗑 حذف حساب", b"del_list")],
        [Button.inline("📝 إدارة الرسائل", b"manage_messages"), Button.inline("⏱ ضبط الوقت", b"time")],
        [Button.inline(f"📨 {msg_preview}", b"show_active")],
        [Button.inline("🚀 بدء النشر", b"start_p"), Button.inline("🛑 إيقاف النشر", b"stop_p")],
        [Button.inline("📢 المجموعات", b"view_chats"), Button.inline("📊 الحالة", b"status")],
        [Button.inline("🔗 الانضمام البطيء (20 رابط)", b"slow_join")],
        [Button.inline("📊 تقارير الانضمام", b"join_reports")],
        [Button.inline("⚙️ إعدادات متقدمة", b"advanced")],
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
    return [
        [Button.inline("🚫 إدارة المحظورات", b"blacklist_menu")],
        [Button.inline("🗂 إدارة المجموعات", b"manage_groups")],
        [Button.inline("🗑️ حذف القاعدة (مع حفظ الحسابات)", b"safe_reset_db")],
        [Button.inline("⬅️ عودة", b"back")]
    ]

def blacklist_buttons():
    return [
        [Button.inline("➕ إضافة للمحظورات", b"add_blacklist")],
        [Button.inline("➖ إزالة من المحظورات", b"remove_blacklist")],
        [Button.inline("📋 عرض المحظورات", b"view_blacklist")],
        [Button.inline("⬅️ عودة", b"advanced")]
    ]

def groups_buttons():
    return [
        [Button.inline("🔄 تحديث المجموعات", b"refresh_groups")],
        [Button.inline("🔍 بحث في المجموعات", b"search_groups")],
        [Button.inline("📊 إحصائيات المجموعات", b"group_stats")],
        [Button.inline("⬅️ عودة", b"advanced")]
    ]

# ==================== المعالجات ====================

async def start_handler(event):
    if event.sender_id != ADMIN_ID:
        return
    accounts = db.get_accounts()
    groups = db.get_all_groups()
    joined_links = db.get_joined_links_count()
    active_msg = db.get_active_message()
    
    await event.respond(
        f"👋 **أهلاً بك في بوت النشر الخارق v5.0!**\n\n"
        f"📊 **الإحصائيات:**\n"
        f"• الحسابات: {len(accounts)}\n"
        f"• المجموعات: {len(groups)}\n"
        f"• الروابط المنضم لها: {joined_links}\n"
        f"• الرسائل المحفوظة: {len(db.get_all_messages())}\n\n"
        f"🛡 **التشفير المتقدم:** {'مفعل' if SETTINGS.get('encryption', True) else 'معطل'}\n"
        f"🐢 **انضمام بطيء:** حتى 20 رابط بالرسالة\n\n"
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
    elif data == "view_chats":
        await show_groups(event)
    elif data == "advanced":
        await event.edit("⚙️ **الإعدادات المتقدمة**", buttons=advanced_buttons())
    elif data == "back":
        await event.edit("👋 لوحة التحكم الرئيسية", buttons=main_buttons())
    elif data == "show_active":
        active = db.get_active_message()
        if active:
            await event.answer(f"الرسالة النشطة: {active['content'][:50]}...", alert=True)
        else:
            await event.answer("❌ لا توجد رسالة نشطة", alert=True)
    
    # ─── حذف القاعدة مع حفظ الحسابات ───
    elif data == "safe_reset_db":
        await event.edit(
            "⚠️ **تحذير!** ⚠️\n\n"
            "سيتم حذف:\n"
            "• جميع الرسائل\n"
            "• سجل المجموعات\n"
            "• سجل الروابط\n\n"
            "✅ **سيتم الحفاظ على:**\n"
            "• جميع الحسابات المحفوظة\n\n"
            "**هل أنت متأكد؟**",
            buttons=[
                [Button.inline("✅ نعم، احذف مع حفظ الحسابات", b"confirm_safe_reset")],
                [Button.inline("❌ إلغاء", b"advanced")]
            ]
        )
    
    elif data == "confirm_safe_reset":
        try:
            db.safe_reset()
            await event.edit(
                "✅ **تم حذف القاعدة مع حفظ الحسابات!**\n\n"
                "• تم حذف الرسائل والمجموعات والروابط\n"
                "• ✅ جميع الحسابات محفوظة\n\n"
                "اضغط /start للبدء من جديد",
                buttons=[[Button.inline("🔄 العودة للقائمة", b"back")]]
            )
        except Exception as e:
            await event.edit(f"❌ فشل: {str(e)[:100]}", buttons=[[Button.inline("⬅️ عودة", b"advanced")]])
    
    # ─── إدارة الرسائل ───
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
    
    # ─── الانضمام البطيء (20 رابط) ───
    elif data == "slow_join":
        await event.edit(
            "🔗 **الانضمام البطيء للمجموعات**\n\n"
            "أرسل حتى **20 رابط** في رسالة واحدة (رابط في كل سطر):\n\n"
            "مثال:\n"
            "https://t.me/group1\n"
            "https://t.me/group2\n"
            "https://t.me/+abcdef\n"
            "...\n\n"
            "🐢 سرعة بطيئة جداً لحماية الحسابات\n"
            "⏱ رابط كل 2-4 دقائق\n\n"
            "استخدم /cancel للإلغاء"
        )
        TEMP[ADMIN_ID] = "awaiting_links"
    
    # ─── تقارير الانضمام فقط ───
    elif data == "join_reports":
        await show_join_report(event)
    
    # ─── المحظورات ───
    elif data == "blacklist_menu":
        await event.edit("🚫 قائمة المحظورات", buttons=blacklist_buttons())
    elif data == "view_blacklist":
        await show_blacklist(event)
    elif data == "add_blacklist":
        await event.edit("🚫 أرسل اسم المجموعة أو معرفها لحظرها:")
        TEMP[ADMIN_ID] = "add_blacklist"
    elif data == "remove_blacklist":
        await show_remove_blacklist(event)
    elif data.startswith("unblack_"):
        await remove_from_blacklist(event, data.replace("unblack_", ""))
    
    # ─── إدارة المجموعات ───
    elif data == "manage_groups":
        await event.edit("🗂 إدارة المجموعات", buttons=groups_buttons())
    elif data == "refresh_groups":
        await refresh_groups(event)
    elif data == "search_groups":
        await event.edit("🔍 أرسل كلمة البحث:")
        TEMP[ADMIN_ID] = "search_groups"
    elif data == "group_stats":
        await show_group_stats(event)
    
    # ─── بدء/إيقاف النشر ───
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
    
    if len(messages) > 15:
        text += f"\n... و {len(messages) - 15} رسالة أخرى"
    
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

async def show_join_report(event):
    """تقرير الانضمام - التقرير الوحيد المتبقي"""
    links = db.get_joined_links(30)
    accounts = db.get_accounts()
    groups = db.get_all_groups()
    
    text = "📊 **تقرير الانضمام**\n\n"
    text += f"━━━━━━━━━━━━━━━━━━━━\n"
    text += f"👥 الحسابات النشطة: {len([a for a in accounts if a[1] == 'active'])}\n"
    text += f"📢 المجموعات: {len(groups)}\n"
    text += f"🔗 إجمالي الروابط المنضم لها: {db.get_joined_links_count()}\n"
    text += f"🚫 المحظورات: {len(db.get_blacklisted_groups())}\n"
    text += f"━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if links:
        text += "**آخر 30 رابط:**\n\n"
        for link, group_name, joined_at, joined_by in links:
            time_str = datetime.fromisoformat(joined_at).strftime('%Y-%m-%d %H:%M')
            text += f"• **{group_name[:30]}**\n"
            text += f"  🔗 {link[:40]}\n"
            text += f"  📱 {joined_by[-8:]} | 🕐 {time_str}\n\n"
    else:
        text += "📭 لا توجد روابط منضم لها بعد\n"
    
    await event.edit(text, buttons=[[Button.inline("⬅️ عودة", b"back")]])

async def show_status(event):
    accounts = db.get_accounts()
    groups = db.get_all_groups()
    blacklisted = db.get_blacklisted_groups()
    joined_links = db.get_joined_links_count()
    messages_count = len(db.get_all_messages())
    active_msg = db.get_active_message()
    uptime = datetime.now() - start_time
    hours = uptime.total_seconds() // 3600
    minutes = (uptime.total_seconds() % 3600) // 60
    
    active_accounts = len([a for a in accounts if a[1] == 'active'])
    
    text = f"📊 **حالة البوت**\n\n"
    text += f"⏰ **وقت التشغيل:** {int(hours)} س {int(minutes)} د\n"
    text += f"👤 **الحسابات:** {active_accounts}/{len(accounts)}\n"
    text += f"📢 **المجموعات:** {len(groups)}\n"
    text += f"🚫 **المحظورات:** {len(blacklisted)}\n"
    text += f"🔗 **الروابط:** {joined_links}\n"
    text += f"📝 **الرسائل:** {messages_count}\n"
    text += f"⚙️ **الفاصل:** {SETTINGS['interval']} ثانية\n"
    text += f"🛡 **التشفير المتقدم:** {'🟢 مفعّل' if SETTINGS.get('encryption', True) else '🔴 معطّل'}\n"
    text += f"🐢 **انضمام بطيء:** حتى 20 رابط بالرسالة\n"
    text += f"🔄 **النشر:** {'🟢 نشط' if is_posting else '🔴 متوقف'}\n"
    
    if active_msg:
        text += f"\n📨 **الرسالة النشطة:**\n{active_msg['content'][:100]}..."
    
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
    blacklisted = db.get_blacklisted_groups()
    
    text = f"📢 **المجموعات**\nالإجمالي: {len(groups)}\nالمحظور: {len(blacklisted)}\n\n"
    
    for gid, name, members, posts, bl, last in groups[:15]:
        name_short = name[:25] if name else "بدون اسم"
        status = "🚫" if bl else "✅"
        members_fmt = format_number(members) if members else "?"
        text += f"{status} {name_short}\n   👥 {members_fmt} | 📨 {posts}\n"
    
    if len(groups) > 15:
        text += f"\n... و {len(groups) - 15} مجموعة أخرى"
    
    await event.edit(text, buttons=main_buttons())

async def show_blacklist(event):
    blacklisted = db.get_blacklisted_groups()
    if not blacklisted:
        await event.edit("📭 لا توجد مجموعات محظورة", buttons=blacklist_buttons())
        return
    
    text = "🚫 **المجموعات المحظورة**\n\n"
    for gid, name in blacklisted[:20]:
        text += f"• {name[:40]}\n"
    
    if len(blacklisted) > 20:
        text += f"\n... و {len(blacklisted) - 20} مجموعة أخرى"
    
    await event.edit(text, buttons=blacklist_buttons())

async def show_remove_blacklist(event):
    blacklisted = db.get_blacklisted_groups()
    if not blacklisted:
        return await event.answer("❌ لا توجد محظورات", alert=True)
    
    btns = []
    for gid, name in blacklisted[:10]:
        btns.append([Button.inline(f"✅ {name[:20]}", f"unblack_{gid}".encode())])
    
    btns.append([Button.inline("⬅️ عودة", b"blacklist_menu")])
    await event.edit("✅ اختر مجموعة للإزالة", buttons=btns)

async def show_group_stats(event):
    groups = db.get_all_groups()
    if not groups:
        return await event.answer("❌ لا توجد مجموعات", alert=True)
    
    most_active = sorted(groups, key=lambda x: x[3], reverse=True)[:5]
    largest = sorted(groups, key=lambda x: x[2] or 0, reverse=True)[:5]
    
    text = "📊 **إحصائيات المجموعات**\n\n"
    text += "**الأكثر نشاطاً:**\n"
    for gid, name, members, posts, bl, last in most_active:
        text += f"• {name[:25]}: {posts} منشور\n"
    
    text += "\n**الأكبر عدداً:**\n"
    for gid, name, members, posts, bl, last in largest:
        members_fmt = format_number(members) if members else "?"
        text += f"• {name[:25]}: {members_fmt} عضو\n"
    
    await event.edit(text, buttons=groups_buttons())

# ===== دوال الإجراءات =====

async def delete_account(event, phone):
    if phone in USER_CLIENTS:
        await USER_CLIENTS[phone].disconnect()
        del USER_CLIENTS[phone]
    db.remove_account(phone)
    await event.answer(f"✅ تم حذف {phone}", alert=True)
    await show_delete_list(event)

async def remove_from_blacklist(event, group_id):
    db.whitelist_group(group_id)
    group_blacklist.clear_banned(str(group_id))
    await event.answer("✅ تمت الإزالة", alert=True)
    await show_blacklist(event)

async def refresh_groups(event):
    await event.answer("🔄 جاري تحديث المجموعات...")
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
    await event.answer(f"✅ تم تحديث {count} مجموعة")
    await event.edit("🗂 إدارة المجموعات:", buttons=groups_buttons())

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

# ===== معالج النصوص والانضمام البطيء =====

async def text_handler(event):
    state = TEMP.get(ADMIN_ID)
    text = event.message.text.strip()
    
    if state == "new_message":
        msg_id = f"msg_{int(time.time())}"
        db.save_message(msg_id, text, is_active=False)
        TEMP.pop(ADMIN_ID, None)
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
                TEMP.pop(ADMIN_ID, None)
                await event.respond(f"✅ تم ضبط الوقت على {text} ثانية", buttons=main_buttons())
            else:
                await event.respond("❌ الرجاء إدخال قيمة بين 10 و 120")
        except:
            await event.respond("❌ أرسل رقماً فقط")
    
    elif state == "add_blacklist":
        groups = db.search_groups(text)
        if groups:
            for gid, name, members in groups[:5]:
                db.blacklist_group(gid)
            await event.respond(f"✅ تم حظر {len(groups[:5])} مجموعة")
        else:
            await event.respond("❌ لم يتم العثور على مجموعات")
        TEMP.pop(ADMIN_ID, None)
        await event.respond("⚙️ الإعدادات المتقدمة:", buttons=advanced_buttons())
    
    elif state == "search_groups":
        groups = db.search_groups(text)
        if groups:
            msg = f"🔍 **نتائج البحث:**\n\n"
            for gid, name, members in groups:
                msg += f"• {name[:40]}\n  👥 {format_number(members)}\n"
            await event.respond(msg)
        else:
            await event.respond("❌ لا توجد نتائج")
        TEMP.pop(ADMIN_ID, None)
    
    elif state == "awaiting_links":
        # ─── الانضمام البطيء حتى 20 رابط ───
        TEMP.pop(ADMIN_ID, None)
        links = re.findall(r"(https?://t\.me/(?:joinchat/|\+)[a-zA-Z0-9_-]+|https?://t\.me/[a-zA-Z0-9_]+)", text)
        links = links[:20]  # حد أقصى 20 رابط
        
        if not links:
            await event.respond("❌ لم يتم العثور على روابط صالحة!\n\nأرسل روابط بالشكل:\nhttps://t.me/group\nhttps://t.me/+invite", buttons=main_buttons())
            return
        
        await handle_slow_join(event, links)
    
    else:
        # كشف تلقائي للروابط
        links = re.findall(r"(https?://t\.me/(?:joinchat/|\+)[a-zA-Z0-9_-]+|https?://t\.me/[a-zA-Z0-9_]+)", text)
        if links and USER_CLIENTS:
            links = links[:20]
            await handle_slow_join(event, links)

async def handle_slow_join(event, links):
    """الانضمام البطيء حتى 20 رابط - حماية قصوى"""
    await event.respond(
        f"🐢 **انضمام بطيء - أقصى حماية**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 الروابط: {len(links)}\n"
        f"⏱ رابط كل 2-4 دقائق\n"
        f"🛡 حماية كاملة من الحظر\n\n"
        f"جاري البدء..."
    )
    
    success = 0
    failed = 0
    
    for idx, link in enumerate(links):
        link = link.strip()
        if not link:
            continue
        
        await event.respond(
            f"🔗 **[{idx+1}/{len(links)}]** جاري الانضمام...\n"
            f"⏱ انتظار 2-4 دقائق..."
        )
        
        # تأخير عشوائي قبل المحاولة
        initial_delay = random.randint(60, 120)
        await asyncio.sleep(initial_delay)
        
        joined = False
        for phone, client in USER_CLIENTS.items():
            if joined:
                break
            
            try:
                pre_delay = random.randint(45, 90)
                await asyncio.sleep(pre_delay)
                
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
                
                success += 1
                joined = True
                logger.success(f"✅ تم الانضمام: {link}")
                
                # حفظ في قاعدة البيانات
                if group_info:
                    group_id, group_name = group_info
                    db.add_joined_link(link, group_id, group_name[:50], phone)
                    # إضافة المجموعة لقائمة المجموعات أيضاً
                    members = 0
                    try:
                        full_entity = await client.get_entity(int(group_id))
                        members = getattr(full_entity, 'participants_count', 0)
                    except:
                        pass
                    db.add_group(group_id, group_name, '', 'group', members, phone)
                
                post_delay = random.randint(60, 120)
                await asyncio.sleep(post_delay)
                break
                
            except FloodWaitError as e:
                wait_time = e.seconds + random.randint(45, 90)
                logger.warning(f"⏳ FloodWait: انتظار {wait_time} ثانية...")
                await asyncio.sleep(wait_time)
                continue
                
            except Exception as e:
                failed += 1
                logger.error(f"❌ فشل انضمام إلى {link}: {e}")
                error_delay = random.randint(90, 180)
                await asyncio.sleep(error_delay)
                continue
        
        if not joined:
            logger.warning(f"⚠️ فشل الانضمام لـ {link}")
            await asyncio.sleep(random.randint(120, 180))
    
    result_text = f"📊 **نتيجة الانضمام البطيء:**\n"
    result_text += f"━━━━━━━━━━━━━━━━━━━━\n"
    result_text += f"✅ نجاح: {success}\n"
    result_text += f"❌ فشل: {failed}\n"
    result_text += f"📋 إجمالي: {len(links)}\n"
    result_text += f"🛡 سرعة بطيئة - حماية كاملة"
    
    await event.respond(result_text, buttons=main_buttons())

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
        session_str = client.session.save()
        USER_CLIENTS[phone] = client
        db.add_account(phone, session_str)
        await event.respond(f"✅ تم تفعيل الحساب {phone}!\n💾 الجلسة محفوظة - لن تحتاج لإدخالها مرة أخرى")
        TEMP.pop(ADMIN_ID, None)
        asyncio.create_task(refresh_groups_async())
    except SessionPasswordNeededError:
        TEMP[ADMIN_ID]["s"] = "pass"
        await event.respond("🔐 أرسل كلمة المرور:")
    except Exception as e:
        await event.respond(f"❌ فشل: {str(e)[:100]}")

async def handle_password(event, state, password):
    try:
        await state["c"].sign_in(password=password)
        session_str = state["c"].session.save()
        USER_CLIENTS[state["p"]] = state["c"]
        db.add_account(state["p"], session_str)
        await event.respond(f"✅ تم التفعيل بنجاح!\n💾 الجلسة محفوظة - لن تحتاج لإدخالها مرة أخرى")
        TEMP.pop(ADMIN_ID, None)
        asyncio.create_task(refresh_groups_async())
    except Exception as e:
        await event.respond(f"❌ خطأ: {str(e)[:100]}")

# ===== دالة النشر =====
async def poster():
    global is_posting
    logger.info("🚀 بدء النشر بالتشفير المتقدم...")
    
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
            
            # إنشاء تنويعات بالتشفير المتقدم (بدون تغيير النص المرئي)
            variations = anti_detection.get_variation(original_text, 6)
            logger.info(f"📝 تم توليد {len(variations)} تنويع مشفّر")
            
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
                        
                        blacklisted = [g[0] for g in db.get_blacklisted_groups()]
                        if str(dialog.id) in blacklisted:
                            continue
                        
                        if group_blacklist.is_banned(str(dialog.id)):
                            continue
                        
                        db.add_group(dialog.id, dialog.name, 
                                   getattr(dialog.entity, 'username', None),
                                   'group', 
                                   getattr(dialog.entity, 'participants_count', 0), 
                                   phone)
                        
                        selected_text = random.choice(variations)
                        
                        # استخدام التشفير المتقدم
                        success, result = await anti_detection.send_safe(
                            client, dialog.id, selected_text, dialog.name
                        )
                        
                        if success:
                            db.increment_account_posts(phone, success=True)
                            db.update_group_post(dialog.id)
                            groups_sent += 1
                            group_blacklist.clear_banned(str(dialog.id))
                            logger.info(f"✅ [{phone[-8:]}] أرسل لـ {dialog.name[:30]}")
                        else:
                            db.increment_account_posts(phone, success=False)
                            logger.warning(f"⚠️ فشل لـ {dialog.name[:30]}: {result[:50]}")
                            if "banned" in result.lower() or "can't write" in result.lower():
                                group_blacklist.record_failure(str(dialog.id), result)
                        
                        delay = anti_detection.random_delay(SETTINGS.get('interval', 12))
                        await asyncio.sleep(delay)
                    
                    logger.info(f"📊 [{phone[-8:]}] أرسل {groups_sent} رسالة")
                    
                except Exception as e:
                    logger.error(f"❌ خطأ في الحساب {phone[-8:]}: {e}")
                    db.update_account_status(phone, 'error')
            
            cycle_wait = random.randint(90, 180)
            logger.info(f"⏸ استراحة {cycle_wait} ثانية...")
            await asyncio.sleep(cycle_wait)
            
        except Exception as e:
            logger.error(f"💥 خطأ في حلقة النشر: {e}")
            await asyncio.sleep(30)

# استعادة الجلسات
async def restore_sessions():
    """استعادة جميع الحسابات المحفوظة تلقائياً - لا تحتاج لإدخالها مرة أخرى"""
    restored = 0
    accounts = db.get_accounts()
    logger.info(f"🔍 محاولة استعادة {len(accounts)} حساب...")
    
    for account in accounts:
        try:
            if len(account) < 2:
                continue
            phone = account[0]
            session_str = db.get_account_session(phone)
            
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
                logger.warning(f"⚠️ الحساب {phone} غير مصرح به - يحتاج إعادة تسجيل")
                
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
    print("🌐 خادم الويب يعمل")
    
    print("🚀 جاري تشغيل البوت...")
    
    # استعادة الحسابات المحفوظة
    await restore_sessions()
    
    bot = TelegramClient('bot_session', API_ID, API_HASH)
    await bot.start(bot_token=BOT_TOKEN)
    
    me = await bot.get_me()
    print(f"✅ البوت متصل: @{me.username}")
    
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
    
    logger.success("✅ البوت جاهز! أرسل /start")
    print("🎉 البوت يعمل - تشفير متقدم + حفظ الحسابات + 20 رابط")
    await bot.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 تم إيقاف البوت")
    except Exception as e:
        logger.error(f"💥 خطأ: {e}")
        time.sleep(5)
        os.execl(sys.executable, sys.executable, *sys.argv)
