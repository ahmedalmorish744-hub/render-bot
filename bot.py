#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔═══════════════════════════════════════════════════════════════╗
║     🤖 بوت النشر الخارق - نسخة الجدولة المتقدمة 📅⚡         ║
║     نشر سريع + جدولة حقيقية + تشفير غير مرئي               ║
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
from telethon.tl.types import InputMediaContact, Chat, Channel, User
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch
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
#  المتغيرات العامة
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
        post_mode TEXT DEFAULT 'fast',
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_run TEXT DEFAULT NULL,
        next_run TEXT DEFAULT NULL)''')
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
    if get_setting('obfuscation_enabled') is None:
        set_setting('obfuscation_enabled', 'on')
    if get_setting('yaytext_messletters_obfuscation') is None:
        set_setting('yaytext_messletters_obfuscation', 'on')

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
#  Scheduled Posts helper functions (محسنة)
# ═══════════════════════════════════════════════
def add_scheduled_post(message_id, post_time, repeat_type='once', repeat_interval=0, post_mode='fast'):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO scheduled_posts (message_id, post_time, repeat_type, repeat_interval, post_mode, status, next_run)
                 VALUES (?, ?, ?, ?, ?, 'pending', ?)''',
              (message_id, post_time, repeat_type, repeat_interval, post_mode, post_time))
    conn.commit()
    sched_id = c.lastrowid
    conn.close()
    return sched_id

def get_pending_scheduled_posts():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, message_id, post_time, repeat_type, repeat_interval, post_mode, last_run, next_run FROM scheduled_posts WHERE status='pending'")
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_scheduled_posts():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, message_id, post_time, repeat_type, repeat_interval, post_mode, status, last_run, next_run FROM scheduled_posts ORDER BY post_time ASC")
    rows = c.fetchall()
    conn.close()
    return rows

def update_scheduled_post(sched_id, **kwargs):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for key, value in kwargs.items():
        c.execute(f'UPDATE scheduled_posts SET {key}=? WHERE id=?', (value, sched_id))
    conn.commit()
    conn.close()

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
    if sched_id in scheduled_tasks:
        try:
            scheduled_tasks[sched_id].cancel()
        except:
            pass
        del scheduled_tasks[sched_id]

def get_scheduled_post_by_id(sched_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, message_id, post_time, repeat_type, repeat_interval, post_mode, status, last_run, next_run FROM scheduled_posts WHERE id=?", (sched_id,))
    row = c.fetchone()
    conn.close()
    return row

# ═══════════════════════════════════════════════
#  خادم الويب
# ═══════════════════════════════════════════════
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "bot": "Super Poster Bot - Advanced Scheduling + Fast Post",
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
#  نظام التشفير المتطور (الحفاظ على المحتوى)
# ═══════════════════════════════════════════════
class UltimateAntiDetection:
    """
    نظام مكافحة الكشف المتطور - النص يبقى كما هو للمستخدم العادي
    الروابط والمعرفات تبقى قابلة للنقر تماماً
    التغييرات غير مرئية للعين المجردة فقط:
    - أحرف غير مرئية بين الكلمات (ليس داخل الروابط)
    - مسافات بديلة بدل المسافة العادية (ليس داخل الروابط)
    - حروف لاتينية متشابهة (homoglyphs) بنسبة منخفضة (ليس داخل الروابط)
    - الروابط والمعرفات تترك كما هي تماماً بدون أي تعديل
    """
    def __init__(self):
        self.invisible_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF']
        self.homoglyphs = {
            'a': '\u0430', 'e': '\u0435', 'o': '\u043E',
            'c': '\u0441', 'p': '\u0440', 'x': '\u0445',
            'i': '\u0456', 'j': '\u0458',
        }
        self.sent_messages_cache = deque(maxlen=500)

    def _extract_protected_segments(self, text):
        """استخراج الروابط والمعرفات لحمايتها من أي تعديل"""
        protected = []
        for match in re.finditer(r'https?://\S+', text):
            protected.append((match.start(), match.end(), match.group()))
        for match in re.finditer(r'@[a-zA-Z0-9_]{3,}', text):
            overlaps = any(match.start() >= p[0] and match.start() < p[1] for p in protected)
            if not overlaps:
                protected.append((match.start(), match.end(), match.group()))
        protected.sort(key=lambda x: x[0])
        clean = []
        for seg in protected:
            if not clean:
                clean.append(seg)
            elif seg[0] >= clean[-1][1]:
                clean.append(seg)
        return clean

    def _split_text_protected(self, text):
        """تقسيم النص إلى أجزاء محمية (روابط/معرفات) وأجزاء عادية"""
        protected = self._extract_protected_segments(text)
        segments = []
        last_end = 0
        for start, end, original in protected:
            if start > last_end:
                segments.append(('text', text[last_end:start]))
            segments.append(('protected', original))
            last_end = end
        if last_end < len(text):
            segments.append(('text', text[last_end:]))
        return segments

    def _apply_to_text_only(self, text, func):
        """تطبيق دالة تحويل على النص العادي فقط بدون الروابط والمعرفات"""
        segments = self._split_text_protected(text)
        result = []
        for seg_type, seg_text in segments:
            if seg_type == 'protected':
                result.append(seg_text)  # لا نعدل الروابط والمعرفات أبداً
            else:
                result.append(func(seg_text))
        return ''.join(result)

    def apply_homoglyphs(self, text, intensity=0.06):
        def _apply(seg):
            result = []
            for char in seg:
                if char in self.homoglyphs and random.random() < intensity:
                    result.append(self.homoglyphs[char])
                else:
                    result.append(char)
            return ''.join(result)
        return self._apply_to_text_only(text, _apply)

    def add_invisible_between_words(self, text, intensity=0.15):
        def _apply(seg):
            if not seg or len(seg) < 5:
                return seg
            result = list(seg)
            space_positions = [i for i, c in enumerate(result) if c == ' ']
            if not space_positions:
                return seg
            insert_positions = []
            for pos in space_positions:
                if random.random() < intensity:
                    insert_positions.append(pos + 1)
            for pos in reversed(insert_positions):
                inv = random.choice(self.invisible_chars)
                result.insert(pos, inv)
            return ''.join(result)
        return self._apply_to_text_only(text, _apply)

    def replace_some_spaces(self, text, intensity=0.3):
        def _apply(seg):
            result = list(seg)
            space_positions = [i for i, c in enumerate(result) if c == ' ']
            for pos in space_positions:
                if random.random() < intensity:
                    replacement = random.choice(['\u00A0', '\u2009', '\u202F'])
                    result[pos] = replacement
            return ''.join(result)
        return self._apply_to_text_only(text, _apply)

    def is_duplicate_message(self, text, group_id):
        cache_key = f"{group_id}:{hash(text)}"
        if cache_key in self.sent_messages_cache:
            return True
        self.sent_messages_cache.append(cache_key)
        return False

    def generate_ultimate_variation(self, text, group_id=None):
        if get_setting('anti_detect', 'on') != 'on':
            return text
        if group_id and self.is_duplicate_message(text, group_id):
            text = '\u200B' + text
        result = text
        # الروابط والمعرفات لا يتم تعديلها أبداً - تبقى قابلة للنقر
        result = self.apply_homoglyphs(result, intensity=0.06)
        result = self.replace_some_spaces(result, intensity=0.3)
        result = self.add_invisible_between_words(result, intensity=0.15)
        return result

anti_detection = UltimateAntiDetection()

def encrypt_text(text, group_id=None):
    return anti_detection.generate_ultimate_variation(text, group_id)

# ═══════════════════════════════════════════════
#  نظام تشويش YayText & Messletters المتقدم 🔄✨
# ═══════════════════════════════════════════════
class YayTextMesslettersObfuscator:
    """
    نظام تشويش متقدم مستوحى من YayText و Messletters
    يحول النصوص لأنماط Unicode مزخرفة ومشوشة
    مع تشويش خاص للروابط والمعرفات والأرقام
    بحيث يصبح غير قابل للتعرف من بوتات الحماية
    مع بقائه مقروءاً تماماً للمستخدمين
    """

    # ─── خط عريض (Math Bold) ───
    BOLD_MAP = {}
    # ─── خط مائل (Math Italic) ───
    ITALIC_MAP = {}
    # ─── خط عريض مائل (Math Bold Italic) ───
    BOLD_ITALIC_MAP = {}
    # ─── خط Monospace ───
    MONOSPACE_MAP = {}
    # ─── خط Cursive / Script ───
    SCRIPT_MAP = {}
    # ─── خط Cursive عريض ───
    BOLD_SCRIPT_MAP = {}
    # ─── خط Fraktur (قوطي) ───
    FRAKTUR_MAP = {}
    # ─── خط Fraktur عريض ───
    BOLD_FRAKTUR_MAP = {}
    # ─── خط Double-Struck ───
    DOUBLE_STRUCK_MAP = {}
    # ─── خط Sans-Serif ───
    SANS_MAP = {}
    # ─── خط Sans-Serif عريض ───
    SANS_BOLD_MAP = {}
    # ─── خط Sans-Serif مائل ───
    SANS_ITALIC_MAP = {}
    # ─── خط Sans-Serif عريض مائل ───
    SANS_BOLD_ITALIC_MAP = {}
    # ─── خط Monospace Sans ───
    SANS_MONO_MAP = {}
    # ─── خط Small Caps ───
    SMALL_CAPS_MAP = {}
    # ─── خط Fullwidth (Messletters) ───
    FULLWIDTH_MAP = {}

    # ─── جداول أرقام Unicode مستقلة ───
    DIGIT_BOLD_MAP = {}
    DIGIT_DOUBLE_STRUCK_MAP = {}
    DIGIT_SANS_MAP = {}
    DIGIT_SANS_BOLD_MAP = {}
    DIGIT_MONO_MAP = {}
    DIGIT_FULLWIDTH_MAP = {}
    DIGIT_CIRCLED_MAP = {}
    DIGIT_NEGATIVE_CIRCLED_MAP = {}

    # ─── Homoglyphs متشابهة ───
    HOMOGLYPH_MAP = {}

    # ─── زخارف ورموز ───
    DECORATIONS = []

    def __init__(self):
        self._build_maps()
        self._last_style = -1

    def _build_maps(self):
        """بناء جداول التحويل لكل نمط"""
        # ═══ الأحرف اللاتينية الكبيرة A-Z ═══
        # Bold: U+1D400 - U+1D419
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.BOLD_MAP[c] = chr(0x1D400 + i)
        # Italic: U+1D434 - U+1D44D
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.ITALIC_MAP[c] = chr(0x1D434 + i)
            if c == 'H':
                self.ITALIC_MAP['H'] = '\u210E'
        # Bold Italic: U+1D468 - U+1D481
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.BOLD_ITALIC_MAP[c] = chr(0x1D468 + i)
        # Monospace: U+1D670 - U+1D689
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.MONOSPACE_MAP[c] = chr(0x1D670 + i)
        # Script: U+1D49C - U+1D4B5
        script_exceptions = {'B': '\u212C', 'E': '\u2130', 'F': '\u2131',
                            'H': '\u210B', 'I': '\u2110', 'L': '\u2112',
                            'M': '\u2133', 'R': '\u211B'}
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            if c in script_exceptions:
                self.SCRIPT_MAP[c] = script_exceptions[c]
            else:
                self.SCRIPT_MAP[c] = chr(0x1D49C + i)
        # Bold Script: U+1D4D0 - U+1D4E9
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.BOLD_SCRIPT_MAP[c] = chr(0x1D4D0 + i)
        # Fraktur: U+1D504 - U+1D51D
        fraktur_exceptions = {'C': '\u212D', 'H': '\u210C', 'I': '\u2111',
                              'R': '\u211C', 'Z': '\u2128'}
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            if c in fraktur_exceptions:
                self.FRAKTUR_MAP[c] = fraktur_exceptions[c]
            else:
                self.FRAKTUR_MAP[c] = chr(0x1D504 + i)
        # Bold Fraktur: U+1D56C - U+1D585
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.BOLD_FRAKTUR_MAP[c] = chr(0x1D56C + i)
        # Double-Struck: U+1D538 - U+1D551
        ds_exceptions = {'C': '\u2102', 'H': '\u210D', 'N': '\u2115',
                         'P': '\u2119', 'Q': '\u211A', 'R': '\u211D', 'Z': '\u2124'}
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            if c in ds_exceptions:
                self.DOUBLE_STRUCK_MAP[c] = ds_exceptions[c]
            else:
                self.DOUBLE_STRUCK_MAP[c] = chr(0x1D538 + i)
        # Sans-Serif: U+1D5A0 - U+1D5B9
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SANS_MAP[c] = chr(0x1D5A0 + i)
        # Sans-Serif Bold: U+1D5D4 - U+1D5ED
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SANS_BOLD_MAP[c] = chr(0x1D5D4 + i)
        # Sans-Serif Italic: U+1D608 - U+1D621
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SANS_ITALIC_MAP[c] = chr(0x1D608 + i)
        # Sans-Serif Bold Italic: U+1D63C - U+1D655
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SANS_BOLD_ITALIC_MAP[c] = chr(0x1D63C + i)
        # Sans-Serif Monospace: U+1D6A8 - U+1D6C1
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SANS_MONO_MAP[c] = chr(0x1D6A8 + i)
        # Fullwidth: U+FF21 - U+FF3A (Messletters)
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.FULLWIDTH_MAP[c] = chr(0xFF21 + i)

        # ═══ الأحرف اللاتينية الصغيرة a-z ═══
        # Bold: U+1D41A - U+1D433
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.BOLD_MAP[c] = chr(0x1D41A + i)
        # Italic: U+1D44E - U+1D467
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.ITALIC_MAP[c] = chr(0x1D44E + i)
            if c == 'h':
                self.ITALIC_MAP['h'] = '\u210F'
        # Bold Italic: U+1D482 - U+1D49B
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.BOLD_ITALIC_MAP[c] = chr(0x1D482 + i)
        # Monospace: U+1D68A - U+1D6A3
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.MONOSPACE_MAP[c] = chr(0x1D68A + i)
        # Script: U+1D4B6 - U+1D4CF
        script_lower_exceptions = {'e': '\u212F', 'g': '\u210A', 'o': '\u2134'}
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            if c in script_lower_exceptions:
                self.SCRIPT_MAP[c] = script_lower_exceptions[c]
            else:
                self.SCRIPT_MAP[c] = chr(0x1D4B6 + i)
        # Bold Script: U+1D4EA - U+1D503
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.BOLD_SCRIPT_MAP[c] = chr(0x1D4EA + i)
        # Fraktur: U+1D51E - U+1D537
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.FRAKTUR_MAP[c] = chr(0x1D51E + i)
        # Bold Fraktur: U+1D586 - U+1D59F
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.BOLD_FRAKTUR_MAP[c] = chr(0x1D586 + i)
        # Double-Struck: U+1D552 - U+1D56B
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.DOUBLE_STRUCK_MAP[c] = chr(0x1D552 + i)
        # Sans-Serif: U+1D5BA - U+1D5D3
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SANS_MAP[c] = chr(0x1D5BA + i)
        # Sans-Serif Bold: U+1D5EE - U+1D607
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SANS_BOLD_MAP[c] = chr(0x1D5EE + i)
        # Sans-Serif Italic: U+1D622 - U+1D63B
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SANS_ITALIC_MAP[c] = chr(0x1D622 + i)
        # Sans-Serif Bold Italic: U+1D656 - U+1D66F
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SANS_BOLD_ITALIC_MAP[c] = chr(0x1D656 + i)
        # Sans-Serif Monospace: U+1D6C2 - U+1D6DB
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SANS_MONO_MAP[c] = chr(0x1D6C2 + i)
        # Fullwidth: U+FF41 - U+FF5A (Messletters)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.FULLWIDTH_MAP[c] = chr(0xFF41 + i)

        # ═══ الأرقام 0-9 لكل نمط خط ═══
        # Bold digits: U+1D7CE - U+1D7D7
        for i in range(10):
            self.BOLD_MAP[str(i)] = chr(0x1D7CE + i)
            self.DIGIT_BOLD_MAP[str(i)] = chr(0x1D7CE + i)
        # Double-Struck digits: U+1D7D8 - U+1D7E1
        ds_digits = {'0': '\U0001D7D8', '1': '\U0001D7D9', '2': '\U0001D7DA',
                     '3': '\U0001D7DB', '4': '\U0001D7DC', '5': '\U0001D7DD',
                     '6': '\U0001D7DE', '7': '\U0001D7DF', '8': '\U0001D7E0',
                     '9': '\U0001D7E1'}
        self.DOUBLE_STRUCK_MAP.update(ds_digits)
        self.DIGIT_DOUBLE_STRUCK_MAP = dict(ds_digits)
        # Sans digits: U+1D7E2 - U+1D7EB
        for i in range(10):
            self.SANS_MAP[str(i)] = chr(0x1D7E2 + i)
            self.DIGIT_SANS_MAP[str(i)] = chr(0x1D7E2 + i)
        # Sans Bold digits: U+1D7EC - U+1D7F5
        for i in range(10):
            self.SANS_BOLD_MAP[str(i)] = chr(0x1D7EC + i)
            self.DIGIT_SANS_BOLD_MAP[str(i)] = chr(0x1D7EC + i)
        # Monospace digits: U+1D7F6 - U+1D7FF
        for i in range(10):
            self.MONOSPACE_MAP[str(i)] = chr(0x1D7F6 + i)
            self.DIGIT_MONO_MAP[str(i)] = chr(0x1D7F6 + i)
        # Fullwidth digits: U+FF10 - U+FF19 (Messletters)
        for i in range(10):
            self.FULLWIDTH_MAP[str(i)] = chr(0xFF10 + i)
            self.DIGIT_FULLWIDTH_MAP[str(i)] = chr(0xFF10 + i)
        # Circled digits: U+2460 - U+2468 (1-9) + U+24EA (0)
        self.DIGIT_CIRCLED_MAP = {
            '0': '\u24EA', '1': '\u2460', '2': '\u2461', '3': '\u2462',
            '4': '\u2463', '5': '\u2464', '6': '\u2465', '7': '\u2466',
            '8': '\u2467', '9': '\u2468'
        }
        # Negative circled digits: U+2776 - U+277F
        self.DIGIT_NEGATIVE_CIRCLED_MAP = {
            '0': '\u24FF', '1': '\u2776', '2': '\u2777', '3': '\u2778',
            '4': '\u2779', '5': '\u277A', '6': '\u277B', '7': '\u277C',
            '8': '\u277D', '9': '\u277E'
        }

        # ═══ Small Caps ═══
        small_caps = {
            'A': '\u1D00', 'B': '\u0299', 'C': '\u1D04', 'D': '\u1D05',
            'E': '\u1D07', 'F': '\uA730', 'G': '\u0262', 'H': '\u029C',
            'I': '\u026A', 'J': '\u1D0A', 'K': '\u1D0B', 'L': '\u029F',
            'M': '\u1D0D', 'N': '\u0274', 'O': '\u1D0F', 'P': '\u1D18',
            'Q': '\u01EB', 'R': '\u0280', 'S': '\uA731', 'T': '\u1D1B',
            'U': '\u1D1C', 'V': '\u1D20', 'W': '\u1D21', 'X': '\uA78D',
            'Y': '\u028F', 'Z': '\u1D22',
        }
        self.SMALL_CAPS_MAP = small_caps

        # ═══ Homoglyphs (Cyrillic/Greek مشابهة) ═══
        self.HOMOGLYPH_MAP = {
            'a': '\u0430', 'A': '\u0410',
            'c': '\u0441', 'C': '\u0421',
            'e': '\u0435', 'E': '\u0415',
            'o': '\u043E', 'O': '\u041E',
            'p': '\u0440', 'P': '\u0420',
            'x': '\u0445', 'X': '\u0425',
            'y': '\u0443', 'Y': '\u0423',
            'i': '\u0456', 'I': '\u0406',
            'j': '\u0458', 'J': '\u0408',
            's': '\u0455', 'S': '\u0405',
            'k': '\u043A', 'K': '\u041A',
            'H': '\u041D', 'T': '\u0422',
            'M': '\u041C', 'B': '\u0412',
        }

        # ═══ الزخارف والرموز (Messletters) ═══
        self.DECORATIONS = [
            # حروف محاطة بدوائر (a-z)
            ['\u24D0', '\u24D1', '\u24D2', '\u24D3', '\u24D4', '\u24D5',
             '\u24D6', '\u24D7', '\u24D8', '\u24D9', '\u24DA', '\u24DB',
             '\u24DC', '\u24DD', '\u24DE', '\u24DF', '\u24E0', '\u24E1',
             '\u24E2', '\u24E3', '\u24E4', '\u24E5', '\u24E6', '\u24E7',
             '\u24E8', '\u24E9'],
            # حروف محاطة بدوائر كبيرة (A-Z)
            ['\u24B6', '\u24B7', '\u24B8', '\u24B9', '\u24BA', '\u24BB',
             '\u24BC', '\u24BD', '\u24BE', '\u24BF', '\u24C0', '\u24C1',
             '\u24C2', '\u24C3', '\u24C4', '\u24C5', '\u24C6', '\u24C7',
             '\u24C8', '\u24C9', '\u24CA', '\u24CB', '\u24CC', '\u24CD',
             '\u24CE', '\u24CF'],
        ]

        # ═══ قائمة كل الأنماط المتاحة ═══
        self.STYLES = [
            ('bold', self.BOLD_MAP),
            ('italic', self.ITALIC_MAP),
            ('bold_italic', self.BOLD_ITALIC_MAP),
            ('monospace', self.MONOSPACE_MAP),
            ('script', self.SCRIPT_MAP),
            ('bold_script', self.BOLD_SCRIPT_MAP),
            ('fraktur', self.FRAKTUR_MAP),
            ('bold_fraktur', self.BOLD_FRAKTUR_MAP),
            ('double_struck', self.DOUBLE_STRUCK_MAP),
            ('sans', self.SANS_MAP),
            ('sans_bold', self.SANS_BOLD_MAP),
            ('sans_italic', self.SANS_ITALIC_MAP),
            ('sans_bold_italic', self.SANS_BOLD_ITALIC_MAP),
            ('fullwidth', self.FULLWIDTH_MAP),
            ('small_caps', self.SMALL_CAPS_MAP),
        ]

        # ═══ جداول تحويل الأرقام المتاحة ═══
        self.DIGIT_STYLES = [
            self.DIGIT_BOLD_MAP,
            self.DIGIT_DOUBLE_STRUCK_MAP,
            self.DIGIT_SANS_MAP,
            self.DIGIT_SANS_BOLD_MAP,
            self.DIGIT_MONO_MAP,
            self.DIGIT_FULLWIDTH_MAP,
        ]

    def _apply_map(self, text, char_map):
        """تطبيق جدول تحويل على النص"""
        result = []
        for c in text:
            if c in char_map:
                result.append(char_map[c])
            else:
                result.append(c)
        return ''.join(result)

    def _apply_map_preserve_digits(self, text, char_map):
        """تطبيق جدول تحويل على النص مع الحفاظ على الأرقام كما هي"""
        result = []
        for c in text:
            if c.isdigit():
                result.append(c)  # الأرقام تبقى أصلية
            elif c in char_map:
                result.append(char_map[c])
            else:
                result.append(c)
        return ''.join(result)

    def _apply_strikethrough(self, text):
        """خط يتوسطه خط: إضافة U+0336 بعد كل حرف (بدون الأرقام)"""
        combining_long = '\u0336'
        result = []
        for c in text:
            if c.isalpha():
                result.append(c + combining_long)
            else:
                result.append(c)
        return ''.join(result)

    def _apply_underline(self, text):
        """خط مسطر: إضافة U+0332 بعد كل حرف (بدون الأرقام)"""
        combining_low = '\u0332'
        result = []
        for c in text:
            if c.isalpha():
                result.append(c + combining_low)
            else:
                result.append(c)
        return ''.join(result)

    def _apply_homoglyphs(self, text, intensity=0.35):
        """استبدال أحرف بنظيراتها المتشابهة (Cyrillic/Greek)"""
        result = []
        for c in text:
            if c in self.HOMOGLYPH_MAP and random.random() < intensity:
                result.append(self.HOMOGLYPH_MAP[c])
            else:
                result.append(c)
        return ''.join(result)

    def _apply_decorations(self, text, intensity=0.08):
        """إضافة رموز زخرفية عشوائية (Messletters style)"""
        words = text.split(' ')
        decorated = []
        for word in words:
            if not word:
                decorated.append(word)
                continue
            if word[0].isalpha() and random.random() < intensity:
                first_upper = word[0].upper()
                if first_upper >= 'A' and first_upper <= 'Z':
                    idx = ord(first_upper) - ord('A')
                    dec_set = random.choice(self.DECORATIONS)
                    if idx < len(dec_set):
                        word = dec_set[idx] + word[1:]
            decorated.append(word)
        return ' '.join(decorated)

    def _create_url_display(self, url, style_idx):
        """
        إنشاء نص عرض متنوع وطبيعي للرابط - يخفيه تماماً من بوتات الحماية
        النص متنوع جداً ولا يشبه نمط إعلاني محدد
        كل رسالة تحصل على نص مختلف
        """
        # أنماط متنوعة جداً - بعضها يبدو كمحادثة عادية
        tme_displays = [
            'تابع القناة', 'انضم لنا', 'القناة هنا', 'زورنا',
            'ادخل القناة', 'اشترك معنا', 'تفضل بالدخول', 'الرابط',
            'من هنا', 'اضغط', 'تابعنا', 'قناتنا',
            'انضم الآن', 'هنا', 'ادخل هنا', 'شاهد',
            'تفضل', 'تابع التحديثات', 'آخر الأخبار هنا', 'صحبتنا',
            'محتوى مميز', 'تواصل معنا', 'تعرف علينا', 'انضمام',
            'القناة الرسمية', 'متابعة', 'دخول', 'رابط القناة',
        ]
        general_displays = [
            'اضغط هنا', 'الرابط', 'من هنا', 'تفضل',
            'شاهد', 'تابع', 'ادخل', 'هنا',
            'تفاصيل أكثر', 'المزيد', 'زورنا', 'اضغط',
            'معلومات إضافية', 'تفقد الرابط', 'انتقل', 'الموقع',
            'رابط مباشر', 'اضغط للمتابعة', 'تصفح', 'الدخول',
        ]
        if 't.me/' in url:
            return random.choice(tme_displays)
        else:
            return random.choice(general_displays)

    def _create_mention_display(self, mention, style_idx):
        """
        إنشاء نص عرض متنوع وطبيعي للمعرف @username
        يخفيه تماماً من بوتات الحماية
        """
        displays = [
            'اضغط هنا', 'الملف الشخصي', 'هنا',
            'تفضل', 'تابعنا', 'الرابط',
            'من هنا', 'تعرف علينا', 'تواصل',
            'ادخل', 'الصفحة', 'اضغط',
        ]
        return random.choice(displays)

    def _escape_html(self, text):
        """تهريب أحرف HTML الخاصة لمنع تضارب مع parse_mode='html'"""
        if not text:
            return text
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        return text

    def _obfuscate_display_text(self, text, style_idx):
        """
        تشويش نص العرض (للروابط والمعرفات) بأحرف غير مرئية وتحويلات خفيفة
        النص يبقى مقروءاً تماماً لكن يتغير لكل رسالة
        """
        if not text or len(text) < 2:
            return text

        inv_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF', '\u2060', '\u2061']

        # إضافة حرف غير مرئي في البداية (لتغيير البصمة)
        result = random.choice(inv_chars) + text

        # استبدال بعض المسافات بمسافات بديلة
        alt_spaces = ['\u00A0', '\u2009', '\u202F', '\u2008']
        chars = list(result)
        for i, c in enumerate(chars):
            if c == ' ' and random.random() < 0.4:
                chars[i] = random.choice(alt_spaces)
        result = ''.join(chars)

        # إضافة حرف غير مرئي عشوائي بين الكلمات
        space_positions = [i for i, c in enumerate(result) if c in [' ', '\u00A0', '\u2009', '\u202F']]
        for pos in space_positions:
            if random.random() < 0.25:
                result = result[:pos+1] + random.choice(inv_chars) + result[pos+1:]

        # تحويلات عربية خفيفة لنص العرض
        arabic_variants = {
            'ي': '\u06CC',  # ي فارسية
            'ك': '\u06A9',  # ك كردية
            'ه': '\u0647',  # ه مختلفة
            'ة': '\u0629',  # ة مفتوحة
        }
        chars = list(result)
        for i, c in enumerate(chars):
            if c in arabic_variants and random.random() < 0.06:
                chars[i] = arabic_variants[c]
        result = ''.join(chars)

        # علامة RTL خفية أحياناً
        if random.random() < 0.2:
            result = result + '\u200F'

        return result

    def _apply_style_to_text(self, text, style_idx):
        """
        تطبيق كامل لكل تقنيات مكافحة الكشف على النص العادي
        الأرقام تبقى كما هي للحفاظ على وظيفتها (أرقام هواتف قابلة للنقر)
        
        الطبقات:
        1. نمط YayText Unicode (خط عريض/مائل/زخرفي)
        2. Homoglyphs إضافية (حروف سيريلية/يونانية متشابهة)
        3. زخارف Messletters خفيفة
        4. أحرف غير مرئية بين الكلمات
        5. مسافات بديلة (Unicode alternate spaces)
        6. تحويلات عربية خفيفة (ي→ى، ك→ڪ)
        7. أحرف غير مرئية حول علامات الترقيم
        8. علامة RTL خفية
        9. أحرف غير مرئية كثيفة (إضافية لتغيير البصمة بقوة)
        10. تشويش أنماط الكلمات العربية المتكررة
        """
        if not text:
            return text

        # ═══ الطبقة 1: نمط YayText Unicode ═══
        if style_idx >= 0:
            style_name, char_map = self.STYLES[style_idx]
            transformed = self._apply_map_preserve_digits(text, char_map)
        elif style_idx == -1:
            transformed = self._apply_strikethrough(text)
        elif style_idx == -2:
            transformed = self._apply_underline(text)
        elif style_idx == -3:
            transformed = self._apply_homoglyphs(text, intensity=0.5)
        elif style_idx == -4:
            transformed = self._apply_map_preserve_digits(text, self.FULLWIDTH_MAP)
            transformed = self._apply_homoglyphs(transformed, intensity=0.2)
        else:
            transformed = text

        # ═══ الطبقة 2: Homoglyphs إضافية ═══
        if style_idx >= 0 and style_idx != -3:
            transformed = self._apply_homoglyphs(transformed, intensity=0.12)

        # ═══ الطبقة 3: زخارف Messletters خفيفة ═══
        if random.random() < 0.2:
            transformed = self._apply_decorations(transformed, intensity=0.03)

        # ═══ الطبقة 4: أحرف غير مرئية بين الكلمات ═══
        inv_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF', '\u2060', '\u2061', '\u2062', '\u2063']
        words = transformed.split(' ')
        new_words = []
        for i, w in enumerate(words):
            new_words.append(w)
            if i < len(words) - 1 and random.random() < 0.15:
                new_words.append(random.choice(inv_chars))
        transformed = ' '.join(new_words)

        # ═══ الطبقة 5: مسافات بديلة ═══
        alt_spaces = ['\u00A0', '\u2009', '\u202F', '\u2008', '\u2007', '\u2006', '\u2005', '\u2004']
        result_list = list(transformed)
        for i, c in enumerate(result_list):
            if c == ' ' and random.random() < 0.3:
                result_list[i] = random.choice(alt_spaces)
        transformed = ''.join(result_list)

        # ═══ الطبقة 6: تحويلات عربية خفيفة ═══
        arabic_variants = {
            'ي': '\u06CC',  # ي فارسية
            'ك': '\u06A9',  # ك كردية
        }
        result_list = list(transformed)
        for i, c in enumerate(result_list):
            if c in arabic_variants and random.random() < 0.04:
                result_list[i] = arabic_variants[c]
        transformed = ''.join(result_list)

        # ═══ الطبقة 7: أحرف غير مرئية حول علامات الترقيم العربية ═══
        if len(transformed) > 5:
            punctuation = '،.؛:!؟-'
            result_list = list(transformed)
            insert_positions = []
            for i, c in enumerate(result_list):
                if c in punctuation and random.random() < 0.25:
                    insert_positions.append((i + 1, random.choice(['\u200B', '\u200C'])))
            for pos, char in sorted(insert_positions, key=lambda x: x[0], reverse=True):
                result_list.insert(pos, char)
            transformed = ''.join(result_list)

        # ═══ الطبقة 8: علامة RTL خفية أحياناً ═══
        if random.random() < 0.15:
            transformed = transformed + '\u200F'

        # ═══ الطبقة 9: أحرف غير مرئية كثيفة (إضافية لتغيير البصمة بقوة) ═══
        inv_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF', '\u2060', '\u2061', '\u2062', '\u2063']
        # إضافة أحرف غير مرئية بين كل كلمتين عربيتين
        words = transformed.split(' ')
        dense_words = []
        for i, w in enumerate(words):
            dense_words.append(w)
            if i < len(words) - 1:
                # إضافة 0-2 أحرف غير مرئية بين الكلمات
                num_inv = random.randint(0, 2)
                for _ in range(num_inv):
                    dense_words.append(random.choice(inv_chars))
        transformed = ' '.join(dense_words)

        # إضافة أحرف غير مرئية عشوائية في مواقع متنوعة
        if len(transformed) > 10:
            chars = list(transformed)
            insert_positions = []
            for i in range(len(chars)):
                # إضافة أحرف غير مرئية بعد كل حرف عربي بنسبة 5%
                if chars[i] >= '\u0600' and chars[i] <= '\u06FF' and random.random() < 0.05:
                    insert_positions.append((i + 1, random.choice(inv_chars[:4])))
            for pos, char in sorted(insert_positions, key=lambda x: x[0], reverse=True):
                chars.insert(pos, char)
            transformed = ''.join(chars)

        # ═══ الطبقة 10: تشويش أنماط الكلمات العربية المتكررة ═══
        # تحويلات عربية إضافية أكثر تنوعاً لتغيير بصمة النص
        arabic_dense_variants = {
            'ي': '\u06CC',  # ي فارسية
            'ك': '\u06A9',  # ك كردية
            'ه': '\u0647',  # هاء فردية
            'ة': '\u0629',  # تاء مفتوحة
            'أ': '\u0623',  # ألف مقصورة مختلفة
            'إ': '\u0625',  # ألف مكسورة مختلفة
            'آ': '\u0622',  # ألف مد مختلفة
            'و': '\u0648',  # واو مختلفة
            'ن': '\u06BC',  # نون بنقطة مختلفة
            'ل': '\u06B5',  # لام مختلفة
            'ب': '\u067E',  # با مختلفة
            'س': '\u0633',  # سين مختلفة
            'ع': '\u0639',  # عين مختلفة
            'ف': '\u0641',  # فاء مختلفة
        }
        result_list = list(transformed)
        for i, c in enumerate(result_list):
            if c in arabic_dense_variants and random.random() < 0.03:
                result_list[i] = arabic_dense_variants[c]
        transformed = ''.join(result_list)

        # إضافة أحرف غير مرئية في البداية والنهاية (تغيير البصمة)
        transformed = random.choice(inv_chars) + transformed + random.choice(inv_chars)

        return transformed

    def _get_random_style(self):
        """اختيار نمط عشوائي مختلف عن السابق"""
        available = list(range(len(self.STYLES)))
        if self._last_style in available and len(available) > 1:
            available.remove(self._last_style)
        # أضف أنماط Strikethrough و Underline و Homoglyphs كخيارات
        available.append(-1)  # strikethrough
        available.append(-2)  # underline
        available.append(-3)  # homoglyphs only
        available.append(-4)  # fullwidth + homoglyphs (Messletters combo)
        chosen = random.choice(available)
        self._last_style = chosen
        return chosen

    def _extract_protected_segments(self, text):
        """استخراج الروابط والمعرفات لحمايتها من تحويل الأنماط"""
        protected = []
        # حماية الروابط الكاملة (https:// و http://)
        for match in re.finditer(r'https?://\S+', text):
            url = match.group().rstrip('\u200B\u200C\u200D\uFEFF\u2060\u2061\u2062\u2063\u00A0\u2009\u202F')
            end_pos = match.start() + len(url)
            protected.append((match.start(), end_pos, url, 'url'))
        # حماية روابط t.me بدون بروتوكول
        for match in re.finditer(r'(?<![a-zA-Z0-9/:.])t\.me/[a-zA-Z0-9_]+', text):
            overlaps = any(match.start() >= p[0] and match.start() < p[1] for p in protected)
            if not overlaps:
                full_url = 'https://' + match.group()
                protected.append((match.start(), match.end(), full_url, 'url'))
        # حماية @username
        for match in re.finditer(r'@[a-zA-Z0-9_]{3,}', text):
            overlaps = any(match.start() >= p[0] and match.start() < p[1] for p in protected)
            if not overlaps:
                protected.append((match.start(), match.end(), match.group(), 'mention'))
        # ترتيب حسب الموقع
        protected.sort(key=lambda x: x[0])
        # إزالة الأجزاء المتداخلة
        clean = []
        for seg in protected:
            if not clean:
                clean.append(seg)
            elif seg[0] >= clean[-1][1]:
                clean.append(seg)
        return clean

    def obfuscate(self, text):
        """
        التحويل الرئيسي - يختار نمطاً عشوائياً ويطبقه
        
        🔗 الروابط: تُستبدل بنص متنوع + رابط HTML <a href>
           → المستخدم يضغط النص → يفتح الرابط الحقيقي ✅
           → بوتات الحماية لا تجد أي نمط رابط في النص ✅
           → لا حاجة لحساب إزاحات UTF-16 - HTML يتكفل بذلك ✅
        
        👤 المعرفات: تُستبدل بنص متنوع + رابط HTML
           → الضغط يفتح الملف الشخصي الحقيقي ✅
        
        🔢 الأرقام: تبقى كما هي (قابلة للنقر كأرقام هواتف) ✅
        
        يُرجع: (النص المشوش, use_html) حيث use_html يحدد استخدام parse_mode='html'
        """
        if not text or len(text) < 2:
            return text, False

        # استخراج الروابط والمعرفات المحمية
        all_protected = self._extract_protected_segments(text)

        # إذا لا توجد روابط أو معرفات، لا حاجة لـ HTML
        has_links = any(seg_type in ('url', 'mention') for _, _, _, seg_type in all_protected)

        # تقسيم النص إلى أجزاء محمية وغير محمية
        segments = []
        last_end = 0
        for start, end, original, seg_type in all_protected:
            if start > last_end:
                segments.append(('text', text[last_end:start]))
            segments.append((seg_type, original))
            last_end = end
        if last_end < len(text):
            segments.append(('text', text[last_end:]))

        # اختيار النمط
        style_idx = self._get_random_style()

        # بناء النص المشوش تدريجياً
        # باستخدام HTML <a href> للروابط بدلاً من MessageEntityTextUrl
        result_parts = []

        for seg_type, seg_text in segments:
            if seg_type == 'url':
                # إنشاء نص عرض متنوع ومشوش للرابط
                display = self._create_url_display(seg_text, style_idx)
                display = self._obfuscate_display_text(display, style_idx)
                # تهريب أي أحرف HTML في نص العرض
                display = self._escape_html(display)
                # استخدام HTML <a href> للرابط - أكثر موثوقية من MessageEntityTextUrl
                result_parts.append(f'<a href="{seg_text}">{display}</a>')

            elif seg_type == 'mention':
                # إنشاء نص عرض متنوع ومشوش للمعرف
                display = self._create_mention_display(seg_text, style_idx)
                display = self._obfuscate_display_text(display, style_idx)
                display = self._escape_html(display)
                username = seg_text[1:]  # إزالة @
                result_parts.append(f'<a href="tg://resolve?domain={username}">{display}</a>')

            else:
                # نص عادي - تطبيق كل تقنيات مكافحة الكشف
                transformed = self._apply_style_to_text(seg_text, style_idx)
                # تهريب أحرف HTML في النص العادي
                transformed = self._escape_html(transformed)
                result_parts.append(transformed)

        final_text = ''.join(result_parts)

        # إضافة حرف غير مرئي في البداية (لتغيير الهاش)
        inv_char = random.choice(['\u200B', '\u200C', '\uFEFF'])
        final_text = inv_char + final_text

        return final_text, has_links

    def get_style_name(self, idx=None):
        """اسم النمط الحالي"""
        if idx is None:
            idx = self._last_style
        if idx >= 0 and idx < len(self.STYLES):
            return self.STYLES[idx][0]
        elif idx == -1:
            return 'strikethrough'
        elif idx == -2:
            return 'underline'
        elif idx == -3:
            return 'homoglyphs'
        elif idx == -4:
            return 'fullwidth_homoglyphs'
        return 'unknown'

    def get_all_style_names(self):
        """أسماء كل الأنماط المتاحة"""
        names = [s[0] for s in self.STYLES]
        names.extend(['strikethrough', 'underline', 'homoglyphs_only', 'fullwidth_homoglyphs'])
        return names

    def preview_all(self, text):
        """معاينة النص بكل الأنماط"""
        if not text:
            return {}
        results = {}
        for name, char_map in self.STYLES:
            results[name] = self._apply_map(text, char_map)
        results['strikethrough'] = self._apply_strikethrough(text)
        results['underline'] = self._apply_underline(text)
        results['homoglyphs'] = self._apply_homoglyphs(text, intensity=0.5)
        results['fullwidth_homoglyphs'] = self._apply_homoglyphs(
            self._apply_map(text, self.FULLWIDTH_MAP), intensity=0.2)
        return results


yaytext_obfuscator = YayTextMesslettersObfuscator()


# ═══════════════════════════════════════════════
#  نظام التشفير والتكويد المتقدم 🔐✨
# ═══════════════════════════════════════════════
class AdvancedMessageEncoder:
    """
    نظام تشفير وتكويد رسائل متعدد الطبقات
    يطبق عدة تقنيات في سلسلة لتعظيم الحماية من بوتات الحماية:
    
    الطبقة 1: تحويل النص لأنماط Unicode (YayText/Messletters)
    الطبقة 2: إخفاء الروابط في كيانات TextUrl
    الطبقة 3: أحرف غير مرئية استراتيجية
    الطبقة 4: مسافات بديلة عشوائية
    الطبقة 5: حروف متشابهة (Homoglyphs) سيريلية/يونانية
    الطبقة 6: إخفاء نمطي بالتشويش العكسي
    الطبقة 7: علامات RTL خفية لتغيير ترتيب القراءة
    """
    
    # أحرف غير مرئية متنوعة
    INVISIBLE_CHARS = ['\u200B', '\u200C', '\u200D', '\uFEFF', '\u2060', '\u2061', '\u2062', '\u2063']
    
    # مسافات بديلة من مختلف نطاقات Unicode
    ALT_SPACES = [
        '\u00A0',   # No-Break Space
        '\u2009',   # Thin Space
        '\u202F',   # Narrow No-Break Space
        '\u2008',   # Punctuation Space
        '\u2007',   # Figure Space
        '\u2006',   # Six-Per-Em Space
        '\u2005',   # Four-Per-Em Space
        '\u2004',   # Three-Per-Em Space
    ]
    
    # حروف سيريلية/يونانية متشابهة مع اللاتينية (Homoglyphs)
    ADVANCED_HOMOGLYPHS = {
        'a': '\u0430', 'A': '\u0410',  # Cyrillic a/A
        'c': '\u0441', 'C': '\u0421',  # Cyrillic es/Es
        'e': '\u0435', 'E': '\u0415',  # Cyrillic ye/Ye
        'o': '\u043E', 'O': '\u041E',  # Cyrillic o/O
        'p': '\u0440', 'P': '\u0420',  # Cyrillic er/Er
        'x': '\u0445', 'X': '\u0425',  # Cyrillic ha/Ha
        'y': '\u0443', 'Y': '\u0423',  # Cyrillic u/U
        'i': '\u0456', 'I': '\u0406',  # Cyrillic byelorussian
        'j': '\u0458', 'J': '\u0408',  # Cyrillic je/Je
        's': '\u0455', 'S': '\u0405',  # Cyrillic dze/Dze
        'k': '\u043A', 'K': '\u041A',  # Cyrillic ka/Ka
        'H': '\u041D',                  # Cyrillic En
        'T': '\u0422',                  # Cyrillic Te
        'M': '\u041C',                  # Cyrillic Em
        'B': '\u0412',                  # Cyrillic Ve
        'g': '\u0493', 'G': '\u0492',  # Cyrillic Ghe with stroke
        'h': '\u04BB',                  # Cyrillic Shha
        'b': '\u0431', 'B': '\u0412',  # Cyrillic be/Ve
        'd': '\u0501',                  # Cyrillic Komi De
        'u': '\u04AF',                  # Cyrillic straight u
    }
    
    def __init__(self):
        self._message_hash_cache = deque(maxlen=1000)
    
    def _is_protected_zone(self, pos, protected_zones):
        """التحقق مما إذا كان الموقع داخل منطقة محمية (رابط/معرف)"""
        return any(start <= pos < end for start, end in protected_zones)
    
    def _extract_protected_zones(self, text):
        """استخراج مناطق الروابط والمعرفات لحمايتها"""
        zones = []
        for match in re.finditer(r'https?://\S+', text):
            zones.append((match.start(), match.end()))
        for match in re.finditer(r'@[a-zA-Z0-9_]{3,}', text):
            overlaps = any(match.start() >= s and match.start() < e for s, e in zones)
            if not overlaps:
                zones.append((match.start(), match.end()))
        return zones
    
    def apply_strategic_invisibles(self, text, intensity=0.2):
        """
        الطبقة 3: إضافة أحرف غير مرئية استراتيجياً
        - بين الكلمات (مسافة + حرف غير مرئي)
        - في بداية ونهاية النص
        - قبل وبعد علامات الترقيم
        - لا يضاف داخل الروابط/المعرفات
        """
        if not text or len(text) < 3:
            return text
        
        protected = self._extract_protected_zones(text)
        result = list(text)
        insert_positions = []
        
        # أحرف غير مرئية بعد المسافات (بين الكلمات)
        space_positions = [i for i, c in enumerate(result) if c == ' ' and not self._is_protected_zone(i, protected)]
        for pos in space_positions:
            if random.random() < intensity:
                insert_positions.append((pos + 1, random.choice(self.INVISIBLE_CHARS)))
        
        # أحرف غير مرئية قبل علامات الترقيم العربية
        punctuation = '،.؛:!؟-'
        for i, c in enumerate(result):
            if c in punctuation and not self._is_protected_zone(i, protected):
                if random.random() < intensity * 0.5:
                    insert_positions.append((i, random.choice(['\u200B', '\u200C'])))
        
        # أحرف غير مرئية بعد الأقواس
        bracket_chars = '()[]{}'
        for i, c in enumerate(result):
            if c in bracket_chars and not self._is_protected_zone(i, protected):
                if random.random() < intensity * 0.3:
                    insert_positions.append((i + 1, random.choice(['\u200D', '\u2060'])))
        
        # تطبيق الإضافات بترتيب عكسي للحفاظ على المواقع
        for pos, char in sorted(insert_positions, key=lambda x: x[0], reverse=True):
            result.insert(pos, char)
        
        return ''.join(result)
    
    def apply_alternate_spaces(self, text, intensity=0.35):
        """
        الطبقة 4: استبدال المسافات العادية بمسافات بديلة من Unicode
        المسافات البديلة تبدو متطابقة للمستخدم لكنها مختلفة للآلات
        """
        if not text:
            return text
        
        protected = self._extract_protected_zones(text)
        result = list(text)
        
        space_positions = [i for i, c in enumerate(result) if c == ' ' and not self._is_protected_zone(i, protected)]
        for pos in space_positions:
            if random.random() < intensity:
                result[pos] = random.choice(self.ALT_SPACES)
        
        return ''.join(result)
    
    def apply_homoglyphs(self, text, intensity=0.15):
        """
        الطبقة 5: استبدال أحرف لاتينية بنظيراتها السيريلية/يونانية
        تبدو متطابقة تماماً للعين لكنها مختلفة في الترميز
        يصعب على بوتات الحماية اكتشاف النص بعد هذا التحويل
        """
        if not text:
            return text
        
        protected = self._extract_protected_zones(text)
        result = list(text)
        
        for i, c in enumerate(result):
            if c in self.ADVANCED_HOMOGLYPHS and not self._is_protected_zone(i, protected):
                if random.random() < intensity:
                    result[i] = self.ADVANCED_HOMOGLYPHS[c]
        
        return ''.join(result)
    
    def apply_pattern_disruption(self, text):
        """
        الطبقة 6: تشويش النمط - إضافة أحرف غير مرئية لتغيير بصمة النص
        يمنع بوتات الحماية من مطابقة الأنماط المتكررة
        """
        if not text or len(text) < 10:
            return text
        
        protected = self._extract_protected_zones(text)
        result = list(text)
        
        # إضافة حرف غير مرئي في بداية النص
        prefix = random.choice(self.INVISIBLE_CHARS)
        # أحياناً إضافة 2 أحرف غير مرئية
        if random.random() < 0.3:
            prefix += random.choice(self.INVISIBLE_CHARS)
        
        # إضافة أحرف غير مرئية بين الجمل (بعد النقاط)
        for i, c in enumerate(result):
            if c in '.!؟\n' and not self._is_protected_zone(i, protected):
                if random.random() < 0.4:
                    result.insert(i + 1, random.choice(['\u200B', '\u200C', '\uFEFF']))
        
        # إضافة علامة RTL خفية أحياناً لتغيير البصمة
        if random.random() < 0.2:
            result.append('\u200F')  # Right-to-Left Mark
        
        return prefix + ''.join(result)
    
    def apply_unicode_normalization_trick(self, text, intensity=0.05):
        """
        الطبقة 7: تحويلات Unicode طفيفة - استخدام ترميزات مختلفة
        لنفس الأحرف العربية (مثل Hamza بأنماط مختلفة)
        """
        if not text:
            return text
        
        protected = self._extract_protected_zones(text)
        result = list(text)
        
        # تحويلات عربية خفيفة
        arabic_variants = {
            'ي': '\u06CC',  # Farsi Yeh (ي UNICODE مختلف)
            'ك': '\u06A9',  # Farsi Keheh (ك UNICODE مختلف)
            'ء': '\u0621',  # Hamza بترميز مختلف
        }
        
        for i, c in enumerate(result):
            if c in arabic_variants and not self._is_protected_zone(i, protected):
                if random.random() < intensity:
                    result[i] = arabic_variants[c]
        
        return ''.join(result)
    
    def encode_message(self, text, group_id=None):
        """
        تطبيق كل طبقات التشفير والتكويد على الرسالة
        يُرجع: (النص المشفر, use_html) حيث use_html يحدد استخدام parse_mode='html'
        """
        if not text or len(text) < 2:
            return text, False
        
        # تطبيق YayText/Messletters (الطبقة 1+2)
        # الآن يُرجع (نص مع أكواد HTML, use_html)
        obfuscated_text, use_html = yaytext_obfuscator.obfuscate(text)
        
        # الطبقة 3: أحرف غير مرئية استراتيجية
        obfuscated_text = self.apply_strategic_invisibles(obfuscated_text, intensity=0.15)
        
        # الطبقة 4: مسافات بديلة
        obfuscated_text = self.apply_alternate_spaces(obfuscated_text, intensity=0.3)
        
        # الطبقة 5: Homoglyphs
        obfuscated_text = self.apply_homoglyphs(obfuscated_text, intensity=0.1)
        
        # الطبقة 6: تشويش النمط
        obfuscated_text = self.apply_pattern_disruption(obfuscated_text)
        
        # الطبقة 7: تحويلات Unicode عربية
        obfuscated_text = self.apply_unicode_normalization_trick(obfuscated_text, intensity=0.03)
        
        return obfuscated_text, use_html
    
    def _recalculate_entity_offsets(self, original_text, obfuscated_text, entities):
        """
        إعادة حساب مواقع الكيانات بعد إضافة الأحرف غير المرئية
        هذا مهم لأن الطبقات 3-7 تضيف أحرفاً تغير المواقع
        """
        # بما أننا أضفنا أحرف غير مرئية فقط (لا نحذف أو نستبدل أحرفاً مرئية)،
        # يمكننا تقريباً حساب الإزاحة بنسبة التمدد
        if not entities:
            return entities
        
        # حساب نسبة التمدد
        original_len = len(original_text.encode('utf-16-le')) // 2
        obfuscated_len = len(obfuscated_text.encode('utf-16-le')) // 2
        
        if original_len == 0:
            return entities
        
        stretch_ratio = obfuscated_len / original_len
        
        # إعادة حساب المواقع بالتناسب
        for entity in entities:
            # تقريب الموقع الجديد بنسبة التمدد
            entity.offset = int(entity.offset * stretch_ratio)
            # الطول يبقى تقريبياً نفسه لأن النص داخل الكيان لم يتغير كثيراً
        
        return entities


# إنشاء مثيل عام لنظام التشفير المتقدم
advanced_encoder = AdvancedMessageEncoder()


def yaytext_obfuscate(text):
    """
    تطبيق تشويش YayText & Messletters على النص - تُستدعى قبل الإرسال مباشرة
    يتم اختيار نمط عشوائي مختلف لكل رسالة
    
    🔗 الروابط: نص متنوع + رابط HTML <a href>
       → الضغط على النص يفتح الرابط الحقيقي ✅
       → بوتات الحماية لا ترى أي نمط رابط ✅
       → لا مشاكل في حساب الإزاحات ✅
    
    👤 المعرفات: نص متنوع + رابط مخفي (قابل للضغط ✅)
    🔢 الأرقام: تبقى أصلية (قابلة للنقر كأرقام هواتف ✅)
    
    يُرجع: (النص المشوش, use_html) حيث use_html يحدد استخدام parse_mode='html'
    """
    if get_setting('yaytext_messletters_obfuscation', 'on') != 'on':
        return text, False
    if not text:
        return text, False
    return yaytext_obfuscator.obfuscate(text)


# ═══════════════════════════════════════════════
#  Text variation (غير مرئي للمستخدم)
# ═══════════════════════════════════════════════
def vary_text(text):
    """
    تطبيق اختلافات غير مرئية - النص يبقى كما هو للقارئ
    فقط الآلات تستطيع اكتشاف التغيير
    الروابط والمعرفات لا يتم تعديلها أبداً
    """
    if not text:
        return text

    # حماية الروابط والمعرفات
    protected_segments = []
    for match in re.finditer(r'https?://\S+', text):
        protected_segments.append((match.start(), match.end()))
    for match in re.finditer(r'@[a-zA-Z0-9_]{3,}', text):
        overlaps = any(match.start() >= p[0] and match.start() < p[1] for p in protected_segments)
        if not overlaps:
            protected_segments.append((match.start(), match.end()))

    def _is_protected(pos):
        return any(pos >= s and pos < e for s, e in protected_segments)

    result = text

    # أحرف غير مرئية في البداية
    inv_char = random.choice(['\u200B', '\u200C', '\uFEFF'])
    result = inv_char + result
    # تحديث المواقع المحمية بسبب الإضافة في البداية
    protected_segments = [(s+1, e+1) for s, e in protected_segments]

    # استبدال 1-2 مسافات بمسافات بديلة (غير مرئي) - ليس داخل الروابط
    spaces = [i for i, c in enumerate(result) if c == ' ' and not _is_protected(i)]
    if spaces:
        num_replace = min(random.randint(1, 2), len(spaces))
        chosen = random.sample(spaces, num_replace)
        for pos in chosen:
            replacement = random.choice(['\u00A0', '\u2009', '\u202F'])
            result = result[:pos] + replacement + result[pos+1:]

    # أحرف غير مرئية بين كلمتين عشوائيتين - ليس داخل الروابط
    space_positions = [i for i, c in enumerate(result) if c in [' ', '\u00A0', '\u2009', '\u202F'] and not _is_protected(i)]
    if space_positions and random.random() > 0.4:
        pos = random.choice(space_positions)
        inv = random.choice(['\u200B', '\u200C'])
        result = result[:pos+1] + inv + result[pos+1:]

    # استبدال حرف لاتيني بنظيره (غير مرئي) - ليس داخل الروابط
    latin_chars = [i for i, c in enumerate(result) if c.isascii() and c.isalpha() and c.lower() in 'aecpxio' and not _is_protected(i)]
    if latin_chars and random.random() > 0.5:
        pos = random.choice(latin_chars)
        c = result[pos]
        homoglyph_map = {
            'a': '\u0430', 'A': '\u0410', 'e': '\u0435', 'E': '\u0415',
            'c': '\u0441', 'C': '\u0421', 'p': '\u0440', 'P': '\u0420',
            'x': '\u0445', 'X': '\u0425', 'o': '\u043E', 'O': '\u041E',
            'i': '\u0456',
        }
        if c in homoglyph_map:
            result = result[:pos] + homoglyph_map[c] + result[pos+1:]

    return result


def obfuscate_for_humans(text):
    """
    تشويش غير مرئي للمستخدم - النص يبقى مفهوماً تماماً
    الروابط والمعرفات لا يتم تعديلها أبداً - تبقى قابلة للنقر
    """
    if not text:
        return text

    # حماية الروابط والمعرفات
    protected_segments = []
    for match in re.finditer(r'https?://\S+', text):
        protected_segments.append((match.start(), match.end()))
    for match in re.finditer(r'@[a-zA-Z0-9_]{3,}', text):
        overlaps = any(match.start() >= p[0] and match.start() < p[1] for p in protected_segments)
        if not overlaps:
            protected_segments.append((match.start(), match.end()))

    def _is_protected(pos):
        return any(pos >= s and pos < e for s, e in protected_segments)

    result = text

    # استبدال حروف لاتينية بنظيراتها السيريلية (تبدو متطابقة) - ليس داخل الروابط
    if random.random() > 0.3:
        homoglyph_map = {
            'a': '\u0430', 'o': '\u043E', 'c': '\u0441',
            'e': '\u0435', 'p': '\u0440', 'x': '\u0445', 'i': '\u0456',
        }
        chars = list(result)
        for i, c in enumerate(chars):
            if c in homoglyph_map and random.random() > 0.6 and not _is_protected(i):
                chars[i] = homoglyph_map[c]
        result = ''.join(chars)

    # استبدال بعض المسافات بمسافات بديلة - ليس داخل الروابط
    if random.random() > 0.3:
        spaces = [i for i, c in enumerate(result) if c == ' ' and not _is_protected(i)]
        for pos in spaces:
            if random.random() > 0.5:
                replacement = random.choice(['\u00A0', '\u2009', '\u202F'])
                result = result[:pos] + replacement + result[pos+1:]

    # أحرف غير مرئية بين الكلمات فقط - ليس داخل الروابط
    if random.random() > 0.4 and len(result) > 5:
        space_positions = [i for i, c in enumerate(result) if c in [' ', '\u00A0', '\u2009', '\u202F'] and not _is_protected(i)]
        insert_positions = []
        for pos in space_positions:
            if random.random() > 0.75:
                insert_positions.append(pos + 1)
        chars = list(result)
        for pos in reversed(insert_positions):
            inv = random.choice(['\u200B', '\u200C'])
            chars.insert(pos, inv)
        result = ''.join(chars)

    # حرف غير مرئي في البداية
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
    """جلب كل المجموعات والقنوات من الحساب بدون أي استثناء"""
    count = 0
    try:
        async for dialog in client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
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
    """جلب كل المجموعات/القنوات ديناميكياً بدون أي استثناء"""
    groups = []
    try:
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            if isinstance(entity, (Chat, Channel)):
                group_id = dialog.id
                group_name = dialog.name or "بدون اسم"
                groups.append((group_id, group_name))
    except Exception as e:
        logger.error(f"❌ فشل جلب المجموعات من الحساب: {e}")
    return groups

async def get_all_groups_count():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM groups")
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
        return 0, 0, "لا توجد حسابات"
    acc_id = random.choice(list(user_clients.keys()))
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
#  إرسال رسالة لمجموعة
# ═══════════════════════════════════════════════
async def send_message_to_group(client, group_id, encrypted_content, msg_type, media_path, media_data, use_html=False):
    """إرسال رسالة لمجموعة مع دعم HTML للروابط المخفية"""
    parse_mode = 'html' if use_html else None
    try:
        if msg_type == 'text':
            await client.send_message(int(group_id), encrypted_content, parse_mode=parse_mode)
        elif msg_type == 'photo' and media_path and os.path.exists(media_path):
            await client.send_file(int(group_id), media_path, caption=encrypted_content, parse_mode=parse_mode)
        elif msg_type == 'video' and media_path and os.path.exists(media_path):
            await client.send_file(int(group_id), media_path, caption=encrypted_content, parse_mode=parse_mode)
        elif msg_type == 'audio' and media_path and os.path.exists(media_path):
            await client.send_file(int(group_id), media_path, caption=encrypted_content, parse_mode=parse_mode)
        elif msg_type == 'document' and media_path and os.path.exists(media_path):
            await client.send_file(int(group_id), media_path, caption=encrypted_content, parse_mode=parse_mode)
        elif msg_type == 'contact' and media_data:
            contact_data = json.loads(media_data) if isinstance(media_data, str) else media_data
            await send_contact_message(client, int(group_id), contact_data, encrypted_content)
        else:
            if media_path and os.path.exists(media_path):
                await client.send_file(int(group_id), media_path, caption=encrypted_content, parse_mode=parse_mode)
            else:
                await client.send_message(int(group_id), encrypted_content, parse_mode=parse_mode)
    except Exception as e:
        # إذا فشل الإرسال بـ HTML، حاول بدونه
        if use_html:
            logger.warning(f"⚠️ فشل HTML، إعادة المحاولة بدون HTML: {e}")
            # إزالة أكواد HTML من النص
            clean_text = re.sub(r'<a href="[^"]*">([^<]*)</a>', r'\1', encrypted_content)
            clean_text = clean_text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            if msg_type == 'text':
                await client.send_message(int(group_id), clean_text)
            elif media_path and os.path.exists(media_path):
                await client.send_file(int(group_id), media_path, caption=clean_text)
            else:
                await client.send_message(int(group_id), clean_text)
        else:
            raise

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
#  النشر السريع - ينشر بكل الحسابات لكل المجموعات
# ═══════════════════════════════════════════════
async def fast_post_to_all_groups(message):
    """نشر سريع لكل المجموعات من كل الحسابات - كل حساب ينشر في كل مجموعاته"""
    global is_posting_active

    msg_id = message[0]
    content = message[1]
    media_path = message[2]
    msg_type = message[3]
    media_data = message[4] if len(message) > 4 else None
    fast_delay = max(2, int(get_setting('fast_post_delay', '3')))
    obfuscation_on = get_setting('obfuscation_enabled', 'on') == 'on'
    success_count = 0
    fail_count = 0
    total_posts = 0

    # حساب إجمالي المجموعات عبر كل الحسابات
    for acc_id, client in list(user_clients.items()):
        try:
            groups = await get_account_groups(client)
            total_posts += len(groups)
        except:
            continue

    if total_posts == 0:
        return 0, 0, "لا توجد مجموعات"

    logger.info(f"⚡ بدء النشر السريع: {len(user_clients)} حساب × مجموعاتهم (إجمالي ~{total_posts} منشور)")

    # كل حساب ينشر في كل مجموعاته الخاصة
    for acc_id, client in list(user_clients.items()):
        if not is_posting_active:
            break

        try:
            acc_groups = await get_account_groups(client)
        except Exception as e:
            logger.error(f"❌ فشل جلب مجموعات الحساب {acc_id}: {e}")
            continue

        for gid, gname in acc_groups:
            if not is_posting_active:
                break

            # تخطي المجموعات المحظورة
            if is_group_blacklisted(gid):
                continue

            use_html = False
            if content:
                yaytext_on = get_setting('yaytext_messletters_obfuscation', 'on') == 'on'
                if yaytext_on:
                    encrypted_content, use_html = yaytext_obfuscate(content)
                else:
                    varied = vary_text(content)
                    if obfuscation_on:
                        varied = obfuscate_for_humans(varied)
                    encrypted_content = encrypt_text(varied, gid)
            else:
                encrypted_content = ""

            try:
                await asyncio.sleep(fast_delay)
                if not is_posting_active:
                    break
                await send_message_to_group(client, gid, encrypted_content, msg_type, media_path, media_data, use_html)
                success_count += 1
                log_posting(acc_id, int(gid), msg_id, 'success')
                logger.info(f"⚡ سريع ✅ {gname[:30]} (حساب {acc_id}) ({success_count}/{total_posts})")
            except FloodWaitError as e:
                logger.warning(f"⏸ FloodWait: {e.seconds}ث - انتظار ثم إعادة المحاولة")
                try:
                    await asyncio.sleep(e.seconds + 1)
                    if not is_posting_active:
                        break
                    await send_message_to_group(client, gid, encrypted_content, msg_type, media_path, media_data, use_html)
                    success_count += 1
                    log_posting(acc_id, int(gid), msg_id, 'success (retry after flood)')
                    logger.info(f"⚡ سريع ✅ (بعد FloodWait) {gname[:30]}")
                except Exception as retry_e:
                    fail_count += 1
                    logger.error(f"❌ فشل بعد إعادة المحاولة: {retry_e}")
            except Exception as e:
                fail_count += 1
                logger.error(f"❌ فشل: {e}")

    return success_count, fail_count, total_posts

# ═══════════════════════════════════════════════
#  النشر العادي - ينشر بكل الحسابات لكل المجموعات
# ═══════════════════════════════════════════════
async def post_to_all_groups(message):
    """نشر عادي لكل المجموعات من كل الحسابات - كل حساب ينشر في كل مجموعاته"""
    global is_posting_active

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
    total_posts = 0

    # حساب إجمالي المجموعات عبر كل الحسابات
    for acc_id, client in list(user_clients.items()):
        try:
            groups = await get_account_groups(client)
            total_posts += len(groups)
        except:
            continue

    if total_posts == 0:
        return 0, 0, "لا توجد مجموعات"

    # كل حساب ينشر في كل مجموعاته الخاصة
    for acc_id, client in list(user_clients.items()):
        if not is_posting_active:
            break

        try:
            acc_groups = await get_account_groups(client)
        except Exception as e:
            logger.error(f"❌ فشل جلب مجموعات الحساب {acc_id}: {e}")
            continue

        for gid, gname in acc_groups:
            if not is_posting_active:
                break

            # تخطي المجموعات المحظورة
            if is_group_blacklisted(gid):
                continue

            use_html = False
            if content:
                yaytext_on = get_setting('yaytext_messletters_obfuscation', 'on') == 'on'
                if yaytext_on:
                    encrypted_content, use_html = yaytext_obfuscate(content)
                else:
                    varied = vary_text(content)
                    if obfuscation_on:
                        varied = obfuscate_for_humans(varied)
                    encrypted_content = encrypt_text(varied, gid)
            else:
                encrypted_content = ""

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
                await send_message_to_group(client, gid, encrypted_content, msg_type, media_path, media_data, use_html)
                success_count += 1
                log_posting(acc_id, int(gid), msg_id, 'success')
                logger.info(f"✅ [{msg_type}] {gname[:30]} (حساب {acc_id})")
            except FloodWaitError as e:
                wait_time = e.seconds
                logger.warning(f"⏸ حساب {acc_id} FloodWait: {wait_time}ث")
                try:
                    await asyncio.sleep(wait_time + 1)
                    if not is_posting_active:
                        break
                    await send_message_to_group(client, gid, encrypted_content, msg_type, media_path, media_data, use_html)
                    success_count += 1
                    log_posting(acc_id, int(gid), msg_id, 'success (retry after flood)')
                except Exception as retry_e:
                    fail_count += 1
                    logger.error(f"❌ فشل بعد إعادة المحاولة: {retry_e}")
            except Exception as e:
                fail_count += 1
                log_posting(acc_id, int(gid), msg_id, f'failed: {str(e)[:50]}')
                logger.error(f"❌ فشل النشر: {e}")

    return success_count, fail_count, total_posts

def log_posting(account_id, group_id, message_id, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO posting_history (account_id, group_id, message_id, status, posted_at)
                 VALUES (?, ?, ?, ?, ?)''', (account_id, group_id, message_id, status, datetime.now()))
    conn.commit()
    conn.close()

# ═══════════════════════════════════════════════
#  نظام جدولة النشر (محسن وحقيقي)
# ═══════════════════════════════════════════════
async def execute_scheduled_post(sched_id, msg_id, post_mode='fast'):
    """تنفيذ منشور مجدول"""
    global is_posting_active
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, content, media_path, msg_type, media_data FROM messages WHERE id=?", (msg_id,))
    msg = c.fetchone()
    conn.close()
    if not msg:
        logger.error(f"❌ رسالة مجدولة #{sched_id}: الرسالة #{msg_id} غير موجودة")
        update_scheduled_post_status(sched_id, 'failed')
        return False

    # انتظر حتى ينتهي أي نشر آخر
    wait_count = 0
    while is_posting_active and wait_count < 60:
        await asyncio.sleep(5)
        wait_count += 1
    if is_posting_active:
        logger.warning(f"⚠️ تخطي منشور مجدول #{sched_id} - النشر مشغول")
        return False

    is_posting_active = True
    try:
        if post_mode == 'fast':
            success, fails, total = await fast_post_to_all_groups(msg)
        else:
            success, fails, total = await post_to_all_groups(msg)
        logger.info(f"📅 منشور مجدول #{sched_id}: نجاح={success}, فشل={fails} من {total}")
        return True
    except Exception as e:
        logger.error(f"❌ فشل تنفيذ منشور مجدول #{sched_id}: {e}")
        return False
    finally:
        is_posting_active = False


async def schedule_checker(bot):
    """مهمة خلفية تفحص المنشورات المجدولة وتنفذها"""
    while True:
        try:
            now = datetime.now()
            pending = get_pending_scheduled_posts()
            for sched_id, msg_id, post_time_str, repeat_type, repeat_interval, post_mode, last_run, next_run in pending:
                try:
                    post_time = datetime.fromisoformat(post_time_str)
                    # تحقق مما إذا حان وقت النشر
                    if now >= post_time:
                        logger.info(f"📅 تنفيذ منشور مجدول #{sched_id} (رسالة #{msg_id})")

                        executed = await execute_scheduled_post(sched_id, msg_id, post_mode)
                        now_str = datetime.now().isoformat()

                        if executed:
                            # معالجة التكرار
                            if repeat_type == 'repeat' and repeat_interval > 0:
                                next_time = now + timedelta(minutes=repeat_interval)
                                update_scheduled_post(sched_id, post_time=next_time.isoformat(), last_run=now_str, next_run=next_time.isoformat())
                                logger.info(f"📅 منشور مجدول #{sched_id} - الجولة القادمة: {next_time.strftime('%Y-%m-%d %H:%M')}")
                            elif repeat_type == 'daily':
                                next_time = post_time + timedelta(days=1)
                                update_scheduled_post(sched_id, post_time=next_time.isoformat(), last_run=now_str, next_run=next_time.isoformat())
                                logger.info(f"📅 منشور مجدول #{sched_id} - غداً: {next_time.strftime('%Y-%m-%d %H:%M')}")
                            elif repeat_type == 'weekly':
                                next_time = post_time + timedelta(weeks=1)
                                update_scheduled_post(sched_id, post_time=next_time.isoformat(), last_run=now_str, next_run=next_time.isoformat())
                                logger.info(f"📅 منشور مجدول #{sched_id} - الأسبوع القادم: {next_time.strftime('%Y-%m-%d %H:%M')}")
                            elif repeat_type == 'hourly':
                                next_time = now + timedelta(hours=1)
                                update_scheduled_post(sched_id, post_time=next_time.isoformat(), last_run=now_str, next_run=next_time.isoformat())
                                logger.info(f"📅 منشور مجدول #{sched_id} - الساعة القادمة: {next_time.strftime('%H:%M')}")
                            else:
                                update_scheduled_post_status(sched_id, 'completed', now_str)
                                logger.info(f"📅 منشور مجدول #{sched_id} - مكتمل")
                        else:
                            # أعد المحاولة بعد دقيقتين
                            retry_time = now + timedelta(minutes=2)
                            update_scheduled_post(sched_id, post_time=retry_time.isoformat())
                            logger.info(f"📅 منشور مجدول #{sched_id} - إعادة محاولة بعد دقيقتين")
                except Exception as e:
                    logger.error(f"❌ خطأ في تنفيذ منشور مجدول #{sched_id}: {e}")
        except Exception as e:
            logger.error(f"❌ خطأ في فحص الجدولة: {e}")
        # فحص كل 15 ثانية للدقة
        await asyncio.sleep(15)

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
        post_mode TEXT DEFAULT 'fast',
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_run TEXT DEFAULT NULL,
        next_run TEXT DEFAULT NULL)''')
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
    obf_status = "✅" if get_setting('obfuscation_enabled', 'on') == 'on' else "❌"
    ym_status = "✅" if get_setting('yaytext_messletters_obfuscation', 'on') == 'on' else "❌"
    message_interval = get_setting('message_interval', '3')
    join_interval = get_setting('join_interval', '100')
    fast_delay = get_setting('fast_post_delay', '3')
    pending_sched = len(get_pending_scheduled_posts())
    return [
        [Button.inline("📝 إدارة الرسائل", b"messages")],
        [Button.inline("👥 إدارة الحسابات", b"accounts")],
        [Button.inline("⚡ نشر سريع للكل", b"fast_posting"),
         Button.inline("🚀 بدء النشر", b"start_posting"),
         Button.inline("⏹ إيقاف النشر", b"stop_posting")],
        [Button.inline(f"📅 جدولة النشر ({pending_sched})", b"scheduling")],
        [Button.inline(f"🛡 التشفير {enc_status}", b"toggle_enc"),
         Button.inline(f"🎭 مكافحة الكشف {anti_status}", b"toggle_anti")],
        [Button.inline(f"🎭 تشويش النص {obf_status}", b"toggle_obfuscate"),
         Button.inline(f"📳 Jitter {jitter_status}", b"toggle_jitter")],
        [Button.inline(f"🔄 تشويش YayText & Messletters {ym_status}", b"toggle_yaytext")],
        [Button.inline("⚙️ الإعدادات", b"settings"),
         Button.inline("📊 الإحصائيات", b"stats")],
        [Button.inline(f"🐢 انضمام ({join_interval}ث)", b"slow_join"),
         Button.inline("📋 تقارير الانضمام", b"join_reports")],
        [Button.inline(f"⏱ مدة النشر ({message_interval}ث)", b"set_msg_interval"),
         Button.inline(f"⚡ سرعة النشر السريع ({fast_delay}ث)", b"set_fast_delay"),
         Button.inline("🐢 مدة الانضمام", b"set_join_interval")],
        [Button.inline("🚫 القائمة السوداء", b"blacklist")],
        [Button.inline("🗑 تنظيف قاعدة البيانات", b"clean_db")],
        [Button.inline("🔄 تحديث المجموعات", b"refresh_groups")],
    ]

def get_scheduling_menu():
    pending = len(get_pending_scheduled_posts())
    all_sched = len(get_all_scheduled_posts())
    return [
        [Button.inline("➕ جدولة منشور جديد", b"schedule_new")],
        [Button.inline("📋 المنشورات المجدولة", b"schedule_list")],
        [Button.inline("🗑 حذف جدولة", b"schedule_delete")],
        [Button.inline("🗑 حذف كل الجداول", b"schedule_delete_all")],
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
    obf_status = "✅" if get_setting('obfuscation_enabled', 'on') == 'on' else "❌"
    ym_status = "✅" if get_setting('yaytext_messletters_obfuscation', 'on') == 'on' else "❌"
    return [
        [Button.inline(f"🛡 تبديل التشفير {enc_status}", b"toggle_enc")],
        [Button.inline(f"🎭 تبديل مكافحة الكشف {anti_status}", b"toggle_anti")],
        [Button.inline(f"🎭 تشويش النص {obf_status}", b"toggle_obfuscate")],
        [Button.inline(f"📳 تبديل Jitter {jitter_status}", b"toggle_jitter")],
        [Button.inline(f"🔄 تشويش YayText & Messletters {ym_status}", b"toggle_yaytext")],
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
    logger.info("🤖 البوت يعمل - مع الجدولة المتقدمة والنشر السريع")

    # بدء فاحص الجدولة
    asyncio.create_task(schedule_checker(bot))
    logger.info("📅 نظام الجدولة يعمل (فحص كل 15 ثانية)")

    @bot.on(events.NewMessage(pattern='/start'))
    async def start_handler(event):
        if not is_admin(event.sender_id):
            return
        groups_count = await get_all_groups_count()
        message_interval = get_setting('message_interval', '3')
        fast_delay = get_setting('fast_post_delay', '3')
        pending_sched = len(get_pending_scheduled_posts())
        example_text = "اشترك في قناتنا للحصول على عروض حصرية"
        encrypted_example = encrypt_text(example_text)
        await event.respond(
            "🛡 **بوت النشر - الجدولة المتقدمة + النشر السريع**\n\n"
            "✨ **تقنيات تجاوز الحماية (تحافظ على المحتوى):**\n"
            "• أحرف غير مرئية بين الكلمات\n• مسافات بديلة (غير مرئية)\n"
            "• حروف لاتينية متشابهة (homoglyphs)\n"
            "• أنماط Unicode مزخرفة (YayText & Messletters)\n"
            "• تشويش الأرقام بأنماط Unicode مختلفة\n"
            "• 🔗 الروابط تبقى قابلة للنقر!\n"
            "• 👤 المعرفات تبقى قابلة للنقر!\n\n"
            f"📅 **الجدولة المتقدمة:**\n"
            "• مرة واحدة في وقت محدد\n• تكرار كل X دقيقة/ساعة\n"
            "• يومياً في وقت محدد\n• أسبوعياً\n\n"
            f"⚡ النشر السريع ({fast_delay} ثانية)\n"
            f"📌 منشورات مجدولة معلقة: {pending_sched}\n\n"
            f"📝 **مثال للتشفير:**\n"
            f"الأصلي: {example_text}\n"
            f"المشفر: {encrypted_example}\n\n"
            f"📢 المجموعات: {groups_count}\n"
            f"⏱ مدة النشر العادي: {message_interval} ثانية\n\n"
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
        obf_status = '✅ مفعل' if get_setting('obfuscation_enabled', 'on') == 'on' else '❌ معطل'
        pending_sched = len(get_pending_scheduled_posts())
        await event.respond(
            f"📊 **حالة البوت:**\n"
            f"• المجموعات: {groups}\n• الرسائل: {msgs}\n"
            f"• إجمالي الحسابات: {len(all_accs)}\n"
            f"• النشر: {'🟢 نشط' if is_posting_active else '🔴 متوقف'}\n"
            f"• التشفير: {'✅ مفعل' if get_setting('encryption', 'on') == 'on' else '❌ معطل'}\n"
            f"• مكافحة الكشف: {'✅ مفعلة' if get_setting('anti_detect', 'on') == 'on' else '❌ معطلة'}\n"
            f"• تشويش النص: {obf_status}\n"
            f"• 📅 منشورات مجدولة معلقة: {pending_sched}"
        )

    @bot.on(events.NewMessage(pattern='/test'))
    async def test_handler(event):
        if not is_admin(event.sender_id):
            return
        await event.respond("✅ البوت يعمل مع الجدولة المتقدمة والنشر السريع!")

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
            await event.respond("⚠️ النشر يعمل بالفعل!")
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
            # ⚡ نشر سريع لكل القروبات
            await event.answer("⚡ جاري النشر السريع لكل المجموعات...", alert=True)
            msg_count = await get_all_messages_count()
            all_accs = await get_all_accounts()
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
                f"👥 {len(all_accs)} حساب\n"
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
                f"👥 {len(all_accs)} حساب\n"
                f"⏱ كل {message_interval} ثانية\n🛡 التشفير: {enc_status}\n🎭 مكافحة الكشف: {anti_status}\n🎭 تشويش النص: {obf_status}\n\n✅ النشر يعمل!",
                buttons=[[Button.inline("⏹ إيقاف", b"stop_posting")]]
            )
            asyncio.create_task(auto_posting_loop())

        elif data == 'stop_posting':
            is_posting_active = False
            await event.edit("⏹ **تم إيقاف النشر**", buttons=[[Button.inline("🔙 رجوع", b"back")]])

        elif data == 'scheduling':
            pending_count = len(get_pending_scheduled_posts())
            all_count = len(get_all_scheduled_posts())
            await event.edit(
                f"📅 **جدولة النشر المتقدمة**\n\n"
                f"⏳ منشورات معلقة: {pending_count}\n"
                f"📋 إجمالي المنشورات: {all_count}\n\n"
                "🔹 **أنواع الجدولة:**\n"
                "• مرة واحدة في وقت محدد\n"
                "• تكرار كل X دقيقة\n"
                "• تكرار كل ساعة\n"
                "• يومياً في وقت محدد\n"
                "• أسبوعياً\n\n"
                "🔹 **أوضاع النشر:**\n"
                "• ⚡ سريع (3 ثواني بين المجموعات)\n"
                "• 🚀 عادي (بالمدة المحددة)",
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
                "⏰ **كل ساعة:** `15:30 ساعي`\n"
                "📅 **يومي:** `15:30 يومي` (كل يوم الساعة 3:30)\n"
                "📆 **أسبوعي:** `15:30 أسبوعي` (كل أسبوع نفس الوقت)\n\n"
                "🔹 **أوضاع النشر:**\n"
                "أضف `سريع` أو `عادي` في النهاية\n"
                "مثال: `15:30 يومي سريع`\n\n"
                "/cancel للإلغاء",
            )
            set_setting('awaiting_schedule', 'true')

        elif data == 'schedule_list':
            schedules = get_all_scheduled_posts()
            if not schedules:
                await event.edit("📋 لا توجد منشورات مجدولة", buttons=get_scheduling_menu())
            else:
                text = "📋 **المنشورات المجدولة:**\n\n"
                for sched_id, msg_id, post_time, repeat_type, repeat_interval, post_mode, status, last_run, next_run in schedules[:15]:
                    status_icon = "⏳" if status == 'pending' else "✅" if status == 'completed' else "❌"
                    repeat_text = ""
                    if repeat_type == 'repeat':
                        repeat_text = f" (كل {repeat_interval} دقيقة)"
                    elif repeat_type == 'daily':
                        repeat_text = " (يومي)"
                    elif repeat_type == 'weekly':
                        repeat_text = " (أسبوعي)"
                    elif repeat_type == 'hourly':
                        repeat_text = " (كل ساعة)"
                    mode_text = "⚡" if post_mode == 'fast' else "🚀"
                    try:
                        pt = datetime.fromisoformat(post_time)
                        time_str = pt.strftime('%Y-%m-%d %H:%M')
                    except:
                        time_str = post_time
                    text += f"{status_icon} #{sched_id} | رسالة #{msg_id}\n   🕐 {time_str}{repeat_text} {mode_text}\n\n"
                await event.edit(text, buttons=get_scheduling_menu())

        elif data == 'schedule_delete':
            await event.edit("🗑 أرسل رقم الجدولة للحذف:\n/cancel للإلغاء")
            set_setting('awaiting_schedule_delete', 'true')

        elif data == 'schedule_delete_all':
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM scheduled_posts")
            conn.commit()
            conn.close()
            for sid in list(scheduled_tasks.keys()):
                try:
                    scheduled_tasks[sid].cancel()
                except:
                    pass
            scheduled_tasks.clear()
            await event.answer("✅ تم حذف كل الجداول", alert=True)
            await event.edit("✅ تم حذف كل المنشورات المجدولة", buttons=get_scheduling_menu())

        elif data == 'set_fast_delay':
            await event.edit("⚡ أرسل المدة بين المجموعات في النشر السريع (2-30 ثانية):\n/cancel للإلغاء")
            set_setting('awaiting_fast_delay', 'true')

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
            c.execute("SELECT id, phone, status FROM accounts")
            accs = c.fetchall()
            conn.close()
            if not accs:
                await event.edit("👥 لا توجد حسابات", buttons=[[Button.inline("🔙 رجوع", b"accounts")]])
            else:
                text = "👥 **الحسابات:**\n\n"
                for aid, phone, status in accs:
                    emoji = "✅" if status == 'active' else "⏸️"
                    text += f"{emoji} #{aid} - {phone}\n"
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
                f"🔄 تشويش YayText & Messletters: {get_setting('yaytext_messletters_obfuscation', 'on')}",
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
        elif data == 'toggle_yaytext':
            current = get_setting('yaytext_messletters_obfuscation', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('yaytext_messletters_obfuscation', new_val)
            if new_val == 'on':
                example = "Hello World عروض حصرية @user https://t.me/test 966512345678"
                preview_text, preview_entities = yaytext_obfuscator.obfuscate(example)
                await event.answer("تشويش YayText & Messletters: مفعل ✨")
                await event.edit(
                    f"🔄 **تشويش YayText & Messletters: مفعل** ✅\n\n"
                    f"📝 **معاينة:**\n"
                    f"الأصلي: {example}\n"
                    f"المشوش: {preview_text}\n\n"
                    f"🎨 **أنماط النصوص ({len(yaytext_obfuscator.get_all_style_names())}):**\n"
                    f"• Bold, Italic, Bold Italic, Monospace\n"
                    f"• Script, Bold Script, Fraktur, Bold Fraktur\n"
                    f"• Double-Struck, Sans-Serif, Fullwidth\n"
                    f"• Small Caps, Strikethrough, Underline\n"
                    f"• Homoglyphs, زخارف Messletters\n\n"
                    f"🔗 **الروابط:** نص مشوش + كيان مخفي (قابل للضغط! ✅)\n"
                    f"   → بوتات الحماية لا تجد الرابط في النص\n"
                    f"   → الضغط على النص المشوش يفتح الرابط الحقيقي\n\n"
                    f"👤 **المعرفات:** نص مشوش + كيان مخفي (قابل للضغط! ✅)\n\n"
                    f"🔢 **الأرقام:** تبقى أصلية (قابلة للنقر كأرقام هواتف ✅)\n\n"
                    f"🔄 كل رسالة تستخدم نمط مختلف تلقائياً",
                    buttons=get_settings_menu()
                )
            else:
                await event.answer("تشويش YayText & Messletters: معطل")
                await event.edit("🔄 **تشويش YayText & Messletters: معطل** ❌", buttons=get_settings_menu())

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
                f"📢 المجموعات: {grp_count}\n"
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
                set_setting('yaytext_messletters_obfuscation', 'on')
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

        # === جدولة النشر (محسنة) ===
        if get_setting('awaiting_schedule') == 'true':
            set_setting('awaiting_schedule', '')
            text = event.raw_text.strip()
            try:
                post_time = None
                repeat_type = 'once'
                repeat_interval = 0
                post_mode = 'fast'  # افتراضي: سريع

                # تحقق من وضع النشر (سريع/عادي)
                if 'سريع' in text:
                    post_mode = 'fast'
                    text = text.replace('سريع', '').strip()
                elif 'عادي' in text:
                    post_mode = 'normal'
                    text = text.replace('عادي', '').strip()

                # Parse "15:30 أسبوعي"
                if 'أسبوعي' in text:
                    time_part = text.replace('أسبوعي', '').strip()
                    hour, minute = map(int, time_part.split(':'))
                    today = datetime.now()
                    post_time = today.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if post_time <= today:
                        post_time += timedelta(weeks=1)
                    repeat_type = 'weekly'

                # Parse "15:30 يومي"
                elif 'يومي' in text:
                    time_part = text.replace('يومي', '').strip()
                    hour, minute = map(int, time_part.split(':'))
                    today = datetime.now()
                    post_time = today.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if post_time <= today:
                        post_time += timedelta(days=1)
                    repeat_type = 'daily'

                # Parse "15:30 ساعي"
                elif 'ساعي' in text:
                    time_part = text.replace('ساعي', '').strip()
                    hour, minute = map(int, time_part.split(':'))
                    today = datetime.now()
                    post_time = today.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if post_time <= today:
                        post_time += timedelta(hours=1)
                    repeat_type = 'hourly'

                # Parse "30د كل 60" or "2س كل 120"
                elif 'كل' in text:
                    parts = text.split('كل')
                    first_part = parts[0].strip()
                    repeat_interval = int(parts[1].strip())
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
                        "• `15:30 يومي` لليومي\n"
                        "• `15:30 أسبوعي` للأسبوعي\n"
                        "• `15:30 ساعي` لكل ساعة\n"
                        "• أضف `سريع` أو `عادي` لنوع النشر",
                        buttons=get_main_menu()
                    )
                    return

                # تحقق من وجود رسائل
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT id FROM messages")
                msg_ids = [row[0] for row in c.fetchall()]
                conn.close()
                if not msg_ids:
                    await event.respond("⚠️ لا توجد رسائل! أضف رسالة أولاً", buttons=get_main_menu())
                    return

                # جدولة كل الرسائل
                sched_ids = []
                for msg_id in msg_ids:
                    sched_id = add_scheduled_post(msg_id, post_time.isoformat(), repeat_type, repeat_interval, post_mode)
                    sched_ids.append(sched_id)

                repeat_text = ""
                if repeat_type == 'repeat':
                    repeat_text = f"\n🔄 يتكرر كل {repeat_interval} دقيقة"
                elif repeat_type == 'daily':
                    repeat_text = "\n📅 يتكرر يومياً"
                elif repeat_type == 'weekly':
                    repeat_text = "\n📆 يتكرر أسبوعياً"
                elif repeat_type == 'hourly':
                    repeat_text = "\n⏰ يتكرر كل ساعة"

                mode_text = "⚡ سريع" if post_mode == 'fast' else "🚀 عادي"

                await event.respond(
                    f"✅ **تمت الجدولة بنجاح!**\n\n"
                    f"🕐 وقت النشر: {post_time.strftime('%Y-%m-%d %H:%M')}\n"
                    f"📝 عدد الرسائل: {len(msg_ids)}\n"
                    f"📌 أرقام الجدولة: {', '.join(map(str, sched_ids))}\n"
                    f"📋 وضع النشر: {mode_text}"
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
                    await event.respond("❌ الرجاء إدخال قيمة بين 2 و 30", buttons=get_main_menu())
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
                    await event.respond("❌ بين 2 و 600", buttons=get_main_menu())
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
            types = {'text':'نص','photo':'صورة','video':'فيديو','audio':'صوت','document':'ملف','contact':'جهة اتصال'}
            await event.respond(
                f"✅ **تم حفظ الرسالة #{msg_id}!**\n\n"
                f"📎 النوع: {types.get(msg_type, msg_type)}\n\n"
                f"💡 التشويش والتشفير يحافظان على المحتوى كما هو\n"
                f"التغييرات غير مرئية للعين - فقط الآلات تكتشفها",
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

    await bot.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
