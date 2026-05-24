#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔═══════════════════════════════════════════════════════════════╗
║     🤖 بوت النشر الخارق - النسخة الكاملة 🚀                   ║
║     تشفير متقدم + مكافحة كشف + تزيين + بدون حدود            ║
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
from telethon.tl.types import InputMediaContact
from flask import Flask, jsonify

# ═══════════════════════════════════════════════
#  الإعدادات - تُقرأ من متغيرات البيئة
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
#  قاعدة البيانات SQLite
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
        "bot": "Super Poster Bot - Full Protection",
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
#  نظام التشفير المتقدم + مكافحة الكشف
#  ═══════════════════════════════════════════════
# ═══════════════════════════════════════════════

class AdvancedAntiDetection:
    """
    نظام متكامل لمكافحة الكشف:
    - تشفير الروابط
    - إضافة أحرف غير مرئية
    - تزيين النصوص
    - تغيير بسيط في الصياغة
    """
    
    def __init__(self):
        # أحرف غير مرئية
        self.zero_width_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF']
        
        # زخارف ونقوش
        self.decorations = [
            ('✨', '✨'), ('🌟', '🌟'), ('⭐', '⭐'), ('💫', '💫'),
            ('✧', '✧'), ('✦', '✦'), ('❁', '❁'), ('✿', '✿'),
            ('🌸', '🌸'), ('🌺', '🌺'), ('◈', '◈'), ('♥', '♥'),
            ('★', '★'), ('☆', '☆'), ('♡', '♡'), ('❂', '❂'),
        ]
        
        # إطارات زخرفية
        self.frames = [
            lambda t: f"「 {t} 」",
            lambda t: f"『 {t} 』",
            lambda t: f"【 {t} 】",
            lambda t: f"✦ {t} ✦",
            lambda t: f"✧ {t} ✧",
            lambda t: f"▸ {t} ◂",
            lambda t: f"► {t} ◄",
            lambda t: f"▪️ {t} ▪️",
            lambda t: f"➤ {t} ➣",
        ]
        
        # خطوط عربية جميلة
        self.arabic_fonts = {
            'ا': 'ﺍ', 'ب': 'ﺏ', 'ت': 'ﺕ', 'ث': 'ﺙ', 'ج': 'ﺝ', 'ح': 'ﺡ',
            'خ': 'ﺥ', 'د': 'ﺩ', 'ذ': 'ﺫ', 'ر': 'ﺭ', 'ز': 'ﺯ', 'س': 'ﺱ',
            'ش': 'ﺵ', 'ص': 'ﺹ', 'ض': 'ﺽ', 'ط': 'ﻁ', 'ظ': 'ﻅ', 'ع': 'ﻉ',
            'غ': 'ﻍ', 'ف': 'ﻑ', 'ق': 'ﻕ', 'ك': 'ﻙ', 'ل': 'ﻝ', 'م': 'ﻡ',
            'ن': 'ﻥ', 'ه': 'ﻩ', 'و': 'ﻭ', 'ي': 'ﻱ', 'ة': 'ﺓ', 'ى': 'ﻯ'
        }
        
        # خطوط إنجليزية جميلة
        self.english_fonts = {
            'a': '𝗮', 'b': '𝗯', 'c': '𝗰', 'd': '𝗱', 'e': '𝗲', 'f': '𝗳',
            'g': '𝗴', 'h': '𝗵', 'i': '𝗶', 'j': '𝗷', 'k': '𝗸', 'l': '𝗹',
            'm': '𝗺', 'n': '𝗻', 'o': '𝗼', 'p': '𝗽', 'q': '𝗾', 'r': '𝗿',
            's': '𝘀', 't': '𝘁', 'u': '𝘂', 'v': '𝘃', 'w': '𝘄', 'x': '𝘅',
            'y': '𝘆', 'z': '𝘇',
            'A': '𝗔', 'B': '𝗕', 'C': '𝗖', 'D': '𝗗', 'E': '𝗘', 'F': '𝗙',
            'G': '𝗚', 'H': '𝗛', 'I': '𝗜', 'J': '𝗝', 'K': '𝗞', 'L': '𝗟',
            'M': '𝗠', 'N': '𝗡', 'O': '𝗢', 'P': '𝗣', 'Q': '𝗤', 'R': '𝗥',
            'S': '𝗦', 'T': '𝗧', 'U': '𝗨', 'V': '𝗩', 'W': '𝗪', 'X': '𝗫',
            'Y': '𝗬', 'Z': '𝗭'
        }
    
    def obfuscate_link(self, text):
        """تشفير الروابط - أهم ميزة لتجاوز الحظر"""
        # تشويه روابط t.me
        text = text.replace('t.me', 't.\u200Bme')
        text = text.replace('telegram.me', 'tele\u200Cgram.me')
        # تشويه روابط https
        text = text.replace('https://', 'https:\u200D//')
        text = text.replace('http://', 'http:\u200C//')
        return text
    
    def obfuscate_username(self, text):
        """تشويه المعرفات @username"""
        def replace_at(match):
            username = match.group(1)
            return '@\u200B' + username
        return re.sub(r'@([a-zA-Z0-9_]{3,})', replace_at, text)
    
    def add_zero_width_chars(self, text, intensity=0.05):
        """إضافة أحرف غير مرئية - تخفي النص من بوتات الكشف"""
        if random.random() > 0.7:
            chars = list(text)
            for i in range(len(chars)):
                if random.random() < intensity:
                    chars.insert(i, random.choice(self.zero_width_chars))
            return ''.join(chars)
        return text
    
    def apply_arabic_font(self, text, intensity=0.3):
        """تطبيق خط عربي جميل"""
        if random.random() > (1 - intensity):
            result = []
            for char in text:
                if char in self.arabic_fonts and random.random() < 0.5:
                    result.append(self.arabic_fonts[char])
                else:
                    result.append(char)
            return ''.join(result)
        return text
    
    def apply_english_font(self, text, intensity=0.2):
        """تطبيق خط إنجليزي جميل"""
        if random.random() > (1 - intensity):
            result = []
            for char in text:
                if char in self.english_fonts and random.random() < 0.4:
                    result.append(self.english_fonts[char])
                else:
                    result.append(char)
            return ''.join(result)
        return text
    
    def add_frame(self, text):
        """إضافة إطار حول النص"""
        if random.random() > 0.6 and len(text) < 150:
            return random.choice(self.frames)(text)
        return text
    
    def add_decorations(self, text):
        """إضافة زخارف حول النص"""
        if random.random() > 0.5:
            left, right = random.choice(self.decorations)
            return f"{left} {text} {right}"
        return text
    
    def add_emoji_variation(self, text):
        """إضافة إيموجي عشوائي للتنويع"""
        emojis = [' 👍', ' 🔥', ' ✅', ' ⭐', ' 💯', ' ✨', ' 🌟']
        if random.random() > 0.85:
            return text + random.choice(emojis)
        return text
    
    def split_keywords(self, text):
        """تقطيع الكلمات المفتاحية الشائعة (خفيف)"""
        patterns = [
            (r'\b(اشترك)\b', 'اش\u200Bترك'),
            (r'\b(قناة)\b', 'قن\u200Cاة'),
            (r'\b(رابط)\b', 'را\u200Cبط'),
            (r'\b(انضم)\b', 'ان\u200Bضم'),
        ]
        for pattern, replacement in patterns:
            if random.random() > 0.8:
                text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text
    
    def encrypt_full(self, text):
        """
        تطبيق جميع تقنيات التشفير ومكافحة الكشف
        مع الحفاظ على قراءة النص
        """
        if get_setting('encryption', 'on') != 'on':
            return text
        
        result = text
        
        # 1. تشفير الروابط (الأهم)
        result = self.obfuscate_link(result)
        result = self.obfuscate_username(result)
        
        # 2. تقطيع الكلمات المفتاحية (خفيف)
        if random.random() > 0.7:
            result = self.split_keywords(result)
        
        # 3. تطبيق الخطوط الجميلة
        if get_setting('anti_detect', 'on') == 'on':
            result = self.apply_arabic_font(result, 0.25)
            result = self.apply_english_font(result, 0.15)
        
        # 4. إضافة أحرف غير مرئية (خفيفة)
        result = self.add_zero_width_chars(result, 0.04)
        
        # 5. تزيين النص
        result = self.add_frame(result)
        result = self.add_decorations(result)
        result = self.add_emoji_variation(result)
        
        return result

# إنشاء نسخة من نظام مكافحة الكشف
anti_detection = AdvancedAntiDetection()

def encrypt_text(text):
    """تشفير النص - الواجهة الرئيسية"""
    return anti_detection.encrypt_full(text)

def generate_unique_variation(text):
    """
    توليد نسخة فريدة من النص في كل مرة
    يستخدم كل تقنيات مكافحة الكشف
    """
    if get_setting('anti_detect', 'on') != 'on':
        return text
    
    # تطبيق التشفير المتقدم
    result = encrypt_text(text)
    
    # إضافة تنويع إضافي عشوائي
    chars = list(result)
    if len(chars) > 10 and random.random() > 0.9:
        pos = random.randint(5, len(chars) - 5)
        chars.insert(pos, random.choice(anti_detection.zero_width_chars))
        result = ''.join(chars)
    
    return result

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
#  نظام النشر مع التشفير ومكافحة الكشف
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

async def post_to_all_groups(message):
    global is_posting_active
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT group_id, group_name FROM groups WHERE is_protected=0")
    groups = c.fetchall()
    conn.close()

    if not groups:
        return 0, 0, "لا توجد مجموعات"

    msg_id = message[0]
    content = message[1]
    media_path = message[2]
    msg_type = message[3]
    media_data = message[4] if len(message) > 4 else None
    
    base_interval = int(get_setting('message_interval', '60'))
    use_jitter = get_setting('use_jitter', 'on') == 'on'
    
    # ⭐ تطبيق التشفير ومكافحة الكشف على النص
    encrypted_content = generate_unique_variation(content) if content else ""
    
    success_count = 0
    fail_count = 0
    
    for group_id, group_name in groups:
        if not is_posting_active:
            break
        
        available_accs = await get_available_accounts()
        
        if not available_accs:
            all_accs = await get_all_accounts()
            if all_accs:
                min_wait = 999999
                for acc_id in all_accs:
                    in_cooldown, remaining = is_account_in_cooldown(acc_id)
                    if in_cooldown and remaining < min_wait:
                        min_wait = remaining
                if min_wait < 999999:
                    wait_time = min(min_wait, 60)
                    logger.info(f"⏸ انتظار {wait_time:.0f} ثانية...")
                    await asyncio.sleep(wait_time)
                    continue
            await asyncio.sleep(30)
            continue
        
        acc_id = random.choice(available_accs)
        client = user_clients.get(acc_id)
        
        if not client:
            continue

        try:
            if use_jitter:
                jitter = random.randint(-10, 20)
                actual_delay = max(10, base_interval + jitter)
            else:
                actual_delay = base_interval
            
            for _ in range(actual_delay):
                if not is_posting_active:
                    break
                await asyncio.sleep(1)
            
            if not is_posting_active:
                break

            # إرسال حسب نوع الوسائط مع النص المشفر
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

            success_count += 1
            log_posting(acc_id, int(group_id), msg_id, 'success')
            logger.info(f"✅ [{msg_type}] {group_name[:30]} (حساب {acc_id}) [مشفر]")

        except FloodWaitError as e:
            wait_time = e.seconds
            logger.warning(f"⏸ حساب {acc_id} FloodWait: {wait_time}ث")
            set_account_cooldown(acc_id, time.time() + wait_time)
            fail_count += 1
            log_posting(acc_id, int(group_id), msg_id, f'failed: flood wait {wait_time}s')
            
        except Exception as e:
            fail_count += 1
            log_posting(acc_id, int(group_id), msg_id, f'failed: {str(e)[:50]}')
            logger.error(f"❌ فشل النشر: {e}")

    return success_count, fail_count, len(groups)

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
    enc_status = "✅" if get_setting('encryption', 'on') == 'on' else "❌"
    anti_status = "✅" if get_setting('anti_detect', 'on') == 'on' else "❌"
    jitter_status = "✅" if get_setting('use_jitter', 'on') == 'on' else "❌"
    bot_detect_status = "✅" if get_setting('bot_detection', 'on') == 'on' else "❌"
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
        [Button.inline(f"📳 Jitter {jitter_status}", b"toggle_jitter"),
         Button.inline(f"🤖 كشف البوتات {bot_detect_status}", b"toggle_bot_detect")],
        [Button.inline("⚙️ الإعدادات", b"settings"),
         Button.inline("📊 الإحصائيات", b"stats")],
        [Button.inline(f"🐢 انضمام ({join_interval}ث)", b"slow_join"),
         Button.inline("📋 تقارير الانضمام", b"join_reports")],
        [Button.inline(f"⏱ مدة النشر ({message_interval}ث)", b"set_msg_interval"),
         Button.inline("🐢 مدة الانضمام", b"set_join_interval")],
        [Button.inline("🔄 مسح تبريد الحسابات", b"clear_cooldowns")],
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
    enc_status = "✅" if get_setting('encryption', 'on') == 'on' else "❌"
    anti_status = "✅" if get_setting('anti_detect', 'on') == 'on' else "❌"
    jitter_status = "✅" if get_setting('use_jitter', 'on') == 'on' else "❌"
    bot_detect_status = "✅" if get_setting('bot_detection', 'on') == 'on' else "❌"
    
    return [
        [Button.inline(f"🛡 تبديل التشفير {enc_status}", b"toggle_enc")],
        [Button.inline(f"🎭 تبديل مكافحة الكشف {anti_status}", b"toggle_anti")],
        [Button.inline(f"📳 تبديل Jitter {jitter_status}", b"toggle_jitter")],
        [Button.inline(f"🤖 تبديل كشف البوتات {bot_detect_status}", b"toggle_bot_detect")],
        [Button.inline("⏱ مدة النشر", b"set_msg_interval")],
        [Button.inline("🐢 مدة الانضمام", b"set_join_interval")],
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

    defaults = {
        'message_interval': '60',
        'join_interval': '100',
        'encryption': 'on',
        'anti_detect': 'on',
        'use_jitter': 'on',
        'bot_detection': 'on',
    }
    for key, val in defaults.items():
        if get_setting(key) is None:
            set_setting(key, val)

    await restore_sessions()

    bot = TelegramClient('bot_session', API_ID, API_HASH)
    await bot.start(bot_token=BOT_TOKEN)
    logger.info("🤖 البوت يعمل - مع التشفير ومكافحة الكشف!")

    # ─── أمر /start ───
    @bot.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        if not is_admin(event.sender_id):
            return
        groups_count = await get_all_groups_count()
        message_interval = get_setting('message_interval', '60')
        join_interval = get_setting('join_interval', '100')
        
        # مثال لتوضيح التشفير
        example_text = "مرحباً بك في بوت النشر"
        encrypted_example = generate_unique_variation(example_text)
        
        await event.respond(
            "🛡 **بوت النشر - مع التشفير ومكافحة الكشف**\n\n"
            "✨ **ميزات الحماية:**\n"
            "• تشفير الروابط (t.me → t.\\u200Bme)\n"
            "• إضافة أحرف غير مرئية\n"
            "• تزيين النصوص\n"
            "• تنويع فريد لكل رسالة\n\n"
            f"📝 **مثال للتشفير:**\n{encrypted_example}\n\n"
            f"📢 المجموعات: {groups_count}\n"
            f"⏱ مدة النشر: {message_interval} ثانية\n"
            f"🐢 مدة الانضمام: {join_interval} ثانية\n\n"
            "اختر من القائمة:",
            buttons=get_main_menu()
        )

    # ─── حلقة النشر ───
    async def auto_posting_loop():
        global is_posting_active
        logger.info("🔄 بدء النشر مع التشفير...")
        
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
                        
                    logger.info(f"📤 نشر رسالة #{msg[0]} ({msg[3]}) مع تشفير")
                    success, fails, total = await post_to_all_groups(msg)
                    logger.info(f"📤 النتيجة: نجاح={success}, فشل={fails} من {total}")

                    if not is_posting_active:
                        break

                    base_interval = int(get_setting('message_interval', '60'))
                    use_jitter = get_setting('use_jitter', 'on') == 'on'
                    if use_jitter:
                        jitter = random.randint(-15, 25)
                        loop_delay = max(10, base_interval + jitter)
                    else:
                        loop_delay = base_interval
                    
                    for _ in range(loop_delay):
                        if not is_posting_active:
                            break
                        await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"خطأ: {e}")
                await asyncio.sleep(5)
        
        logger.info("✅ توقف النشر")

    # ─── أمر معاينة التشفير ───
    @bot.on(events.NewMessage(pattern='/encrypt'))
    async def encrypt_preview(event):
        if not is_admin(event.sender_id):
            return
        text = event.raw_text.replace('/encrypt', '').strip()
        if not text:
            text = "هذا نص تجريبي لاختبار التشفير"
        
        encrypted = generate_unique_variation(text)
        await event.respond(
            f"📝 **النص الأصلي:**\n{text}\n\n"
            f"🛡 **بعد التشفير:**\n{encrypted}\n\n"
            f"✨ تم تطبيق: تشفير الروابط + أحرف غير مرئية + تزيين"
        )

    # ─── أوامر سريعة ───
    @bot.on(events.NewMessage(pattern='/check'))
    async def check_handler(event):
        if not is_admin(event.sender_id):
            return
        groups = await get_all_groups_count()
        msgs = await get_all_messages_count()
        all_accs = await get_all_accounts()
        available = await get_available_accounts()
        
        await event.respond(
            f"📊 **حالة البوت:**\n"
            f"• المجموعات: {groups}\n"
            f"• الرسائل: {msgs}\n"
            f"• إجمالي الحسابات: {len(all_accs)}\n"
            f"• حسابات متاحة: {len(available)}\n"
            f"• النشر: {'🟢 نشط' if is_posting_active else '🔴 متوقف'}\n"
            f"• التشفير: {'✅ مفعل' if get_setting('encryption', 'on') == 'on' else '❌ معطل'}\n"
            f"• مكافحة الكشف: {'✅ مفعلة' if get_setting('anti_detect', 'on') == 'on' else '❌ معطلة'}"
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
        await event.respond("✅ البوت يعمل مع التشفير ومكافحة الكشف!")

    # ─── معالج الأزرار ───
    @bot.on(events.CallbackQuery)
    async def callback_handler(event):
        global is_posting_active
        
        if not is_admin(event.sender_id):
            await event.answer("⛔ غير مصرح", alert=True)
            return

        data = event.data.decode('utf-8')

        if data == 'back':
            groups_count = await get_all_groups_count()
            message_interval = get_setting('message_interval', '60')
            join_interval = get_setting('join_interval', '100')
            await event.edit(
                "🛡 **لوحة التحكم**\n\n"
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
            await event.edit(
                "➕ **إضافة رسالة**\n\n"
                "أرسل:\n• نص عادي\n• صورة مع تعليق\n• فيديو مع تعليق\n• ملف مع تعليق\n• جهة اتصال مع تعليق\n\n"
                "📌 سيتم تطبيق التشفير تلقائياً عند النشر\n"
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
            c.execute("SELECT id, group_name, member_count, is_protected FROM groups LIMIT 50")
            grps = c.fetchall()
            conn.close()
            if not grps:
                await event.edit("📢 لا توجد مجموعات", buttons=[[Button.inline("🔄 تحديث", b"refresh_groups")]])
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
            await event.edit("🗑 تم الحذف", buttons=[[Button.inline("🔙 رجوع", b"groups")]])

        elif data == 'refresh_groups':
            await event.edit("🔄 جاري التحديث...")
            total = 0
            for acc_id, client in user_clients.items():
                count = await fetch_all_groups_for_account(acc_id, client)
                total += count
            await event.edit(f"✅ تم تحديث {total} مجموعة", buttons=[[Button.inline("🔙 رجوع", b"back")]])

        elif data == 'clear_cooldowns':
            clear_all_cooldowns()
            await event.answer("✅ تم مسح التبريد!", alert=True)
            await event.edit("✅ تم مسح تبريد جميع الحسابات", buttons=[[Button.inline("🔙 رجوع", b"back")]])

        elif data == 'start_posting':
            groups_count = await get_all_groups_count()
            msg_count = await get_all_messages_count()
            all_accs = await get_all_accounts()
            available = await get_available_accounts()
            
            if groups_count == 0:
                await event.edit("⚠️ لا توجد مجموعات!\nاضغط 'تحديث المجموعات' أولاً", 
                               buttons=[[Button.inline("🔄 تحديث", b"refresh_groups")]])
                return
            
            if msg_count == 0:
                await event.edit("⚠️ لا توجد رسائل!", buttons=[[Button.inline("➕ إضافة", b"add_msg")]])
                return
            
            if not all_accs:
                await event.edit("⚠️ لا توجد حسابات!", buttons=[[Button.inline("➕ إضافة حساب", b"add_acc")]])
                return
            
            if is_posting_active:
                await event.edit("⚠️ النشر يعمل!", buttons=[[Button.inline("🔙 رجوع", b"back")]])
                return
            
            is_posting_active = True
            message_interval = get_setting('message_interval', '60')
            enc_status = "✅ مفعل" if get_setting('encryption', 'on') == 'on' else "❌ معطل"
            anti_status = "✅ مفعل" if get_setting('anti_detect', 'on') == 'on' else "❌ معطل"
            
            await event.edit(
                f"🚀 **بدأ النشر!**\n\n"
                f"📢 {groups_count} مجموعة\n"
                f"👥 {len(all_accs)} حساب (متاح: {len(available)})\n"
                f"⏱ كل {message_interval} ثانية\n"
                f"🛡 التشفير: {enc_status}\n"
                f"🎭 مكافحة الكشف: {anti_status}\n\n"
                f"✅ النشر يعمل مع الحماية الكاملة!",
                buttons=[[Button.inline("⏹ إيقاف", b"stop_posting")]]
            )
            asyncio.create_task(auto_posting_loop())

        elif data == 'stop_posting':
            is_posting_active = False
            await event.edit("⏹ **تم إيقاف النشر**", buttons=[[Button.inline("🔙 رجوع", b"back")]])

        elif data == 'settings':
            await event.edit(
                "⚙️ **الإعدادات**\n\n"
                f"⏱ مدة النشر: {get_setting('message_interval', '60')} ثانية\n"
                f"🐢 مدة الانضمام: {get_setting('join_interval', '100')} ثانية\n"
                f"🛡 التشفير: {get_setting('encryption', 'on')}\n"
                f"🎭 مكافحة الكشف: {get_setting('anti_detect', 'on')}\n"
                f"📳 Jitter: {get_setting('use_jitter', 'on')}\n"
                f"🤖 كشف البوتات: {get_setting('bot_detection', 'on')}",
                buttons=get_settings_menu()
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
            await event.edit("⚙️ الإعدادات", buttons=get_settings_menu())

        elif data == 'toggle_anti':
            current = get_setting('anti_detect', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('anti_detect', new_val)
            await event.answer(f"مكافحة الكشف: {'مفعلة' if new_val == 'on' else 'معطلة'}")
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
            await event.edit("🐢 **انضمام بطيء**\n\nأرسل الروابط (كل رابط في سطر):\n/cancel للإلغاء")
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
                for key, val in defaults.items():
                    set_setting(key, val)
                await event.edit(f"✅ تم التنظيف! ✅ تم حفظ {saved} حساب", 
                               buttons=[[Button.inline("🔄 تحديث", b"refresh_groups")]])
            except Exception as e:
                await event.edit(f"❌ فشل: {e}", buttons=[[Button.inline("🔙 رجوع", b"back")]])

    # ─── معالج الرسائل ───
    @bot.on(events.NewMessage)
    async def message_handler(event):
        if not is_admin(event.sender_id):
            return

        if event.raw_text == '/cancel':
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
                val = int(event.raw_text.strip())
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
                val = int(event.raw_text.strip())
                if 30 <= val <= 600:
                    set_setting('join_interval', str(val))
                    await event.respond(f"✅ تم الضبط إلى {val} ثانية", buttons=get_main_menu())
                else:
                    await event.respond("❌ بين 30 و 600", buttons=get_main_menu())
            except:
                await event.respond("❌ رقم غير صالح", buttons=get_main_menu())
            return

        # الروابط - انضمام تلقائي
        links = re.findall(r'(https?://t\.me/(?:joinchat/|\+)?[a-zA-Z0-9_\-]+)', event.raw_text)
        if links and user_clients and not get_setting('awaiting_msg'):
            await event.respond(f"🚀 تم اكتشاف {len(links[:20])} رابط، جاري الانضمام...")
            success, failed, msg = await auto_join_links(links)
            await event.respond(f"📊 النتيجة: ✅ {success} نجاح / ❌ {failed} فشل", buttons=get_main_menu())
            return

        # إضافة رسالة جديدة
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
            
            # معاينة التشفير
            encrypted_preview = generate_unique_variation(content[:100]) if content else ""
            
            types = {'text':'نص','photo':'صورة','video':'فيديو','audio':'صوت','document':'ملف','contact':'جهة اتصال'}
            await event.respond(
                f"✅ **تم حفظ الرسالة #{msg_id}!**\n\n"
                f"📎 النوع: {types.get(msg_type, msg_type)}\n"
                f"🛡 **معاينة التشفير:**\n{encrypted_preview}\n\n"
                f"سيتم تطبيق التشفير تلقائياً عند النشر",
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

        # انضمام بطيء
        if get_setting('awaiting_slow_join') == 'true':
            set_setting('awaiting_slow_join', '')
            links = [l.strip() for l in event.raw_text.split('\n') if l.strip()]
            if links:
                success, failed, msg = await auto_join_links(links)
                await event.respond(f"✅ نجاح: {success}\n❌ فشل: {failed}", buttons=get_main_menu())
            return

        # حذف
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

    # ─── كشف بوتات الحماية ───
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
        except:
            await event.respond("❌ استخدم: /set_join_interval 100")

    logger.info("✅ البوت جاهز - مع التشفير المتقدم ومكافحة الكشف!")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
