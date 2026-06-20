#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
╔═══════════════════════════════════════════════════════════════╗
║  🤖 بوت النشر الخارق 2026 - النسخة العالمية الاحترافية 🌐⚡  ║
║  Spintax + Ghost Swarm + Load Balancer + Human Delay         ║
║  كشيدة + Variation Selectors + Tag Chars + RTLO + edit_hide  ║
║  Exponential Backoff + Arabic Homoglyphs + 50+ Unicode Style ║
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
import hashlib
import unicodedata
import urllib.request
from threading import Thread
from datetime import datetime, timedelta
from collections import deque

from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError, PhoneCodeInvalidError, PhoneCodeExpiredError,
    UserAlreadyParticipantError, InviteHashExpiredError, InviteHashInvalidError,
    ChannelPrivateError, ChannelInvalidError
)
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import InputMediaContact, Chat, Channel, User
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch
from flask import Flask, jsonify

# محرك التشفير الخارق (26 طبقة متقدمة)
from hyper_encryption import HyperEncryptionEngine

# محرك الأنماط النصية الخارق (26 نمط بصري مستوحى من FSymbols)
from fancy_text import FancyTextEngine, fancy_engine

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
is_joining_active = False  # علم الانضمام التلقائي
join_progress_msg = None  # رسالة تقدم الانضمام
join_cancelled = False  # إلغاء الانضمام
join_queue = []  # طابور الروابط - يحفظ الروابط للانضمام التالي
scheduled_tasks = {}  # {schedule_id: asyncio.Task}
hyper_encryption = None  # يُهيّأ في init_db()

# ═══════════════════════════════════════════════
#  إعدادات النشر الشبحي 👻
# ═══════════════════════════════════════════════
GHOST_POST_ENABLED = True        # تفعيل النشر الشبحي
GHOST_POST_LIFETIME = 20         # ثواني قبل التعديل/الحذف
GHOST_POST_MODE = 'replace'      # 'replace' = تعديل بنص مختلف | 'delete' = حذف | 'empty' = تفريغ

# ═══════════════════════════════════════════════
#  🆕 نظام Spintax - تنويع تلقائي للرسائل
# ═══════════════════════════════════════════════
def parse_spintax(text):
    """تحليل صيغة Spintax: {خيار1|خيار2|خيار3} لتنويع الرسائل تلقائياً
    مثال: {مرحباً|أهلاً|سلام} بكم في {قناتنا|مجموعتنا}
    → مرحباً بكم في قناتنا  أو  أهلاً بكم في مجموعتنا  ...إلخ
    يدعم تداخل متعدد: {{خيار1|خيار2}|خيار3}
    """
    while '{' in text and '}' in text:
        new_text = re.sub(r'\{([^{}]*)\}', lambda m: random.choice(m.group(1).split('|')), text)
        if new_text == text:
            break
        text = new_text
    return text

# ═══════════════════════════════════════════════
#  🆕 نظام موازنة التحميل - Load Balancer
# ═══════════════════════════════════════════════
class AccountLoadBalancer:
    """توزيع ذكي للرسائل عبر الحسابات - يمنع الحظر ويقلل FloodWait
    يختار الحساب الأقل استخداماً تلقائياً
    يحترم حدود: 40 رسالة/ساعة و 10 رسائل/دقيقة لكل حساب
    """
    def __init__(self):
        self.usage = {}  # {acc_id: [timestamps]}
        self.max_per_hour = 40
        self.max_per_minute = 10

    def get_available_client(self):
        """الحصول على العميل الأقل تحميلاً"""
        now = time.time()
        best_acc = None
        best_score = float('inf')
        for acc_id in user_clients:
            if acc_id not in self.usage:
                self.usage[acc_id] = []
            # تنظيف الطوابع القديمة
            self.usage[acc_id] = [t for t in self.usage[acc_id] if now - t < 3600]
            # حساب النقاط = عدد الرسائل في الساعة
            hourly = len(self.usage[acc_id])
            minute_count = len([t for t in self.usage[acc_id] if now - t < 60])
            if hourly < self.max_per_hour and minute_count < self.max_per_minute:
                if hourly < best_score:
                    best_score = hourly
                    best_acc = acc_id
        if best_acc is not None:
            self.usage[best_acc].append(now)
            return user_clients[best_acc], best_acc
        # إذا كل الحسابات مشغولة - اختر عشوائي
        if user_clients:
            acc_id = random.choice(list(user_clients.keys()))
            if acc_id not in self.usage:
                self.usage[acc_id] = []
            self.usage[acc_id].append(now)
            return user_clients[acc_id], acc_id
        return None, None

    def get_stats(self):
        """إحصائيات التحميل لكل حساب"""
        now = time.time()
        stats = {}
        for acc_id in user_clients:
            if acc_id not in self.usage:
                self.usage[acc_id] = []
            hourly = len([t for t in self.usage[acc_id] if now - t < 3600])
            minute = len([t for t in self.usage[acc_id] if now - t < 60])
            stats[acc_id] = {'hourly': hourly, 'minute': minute}
        return stats

load_balancer = AccountLoadBalancer()

# ═══════════════════════════════════════════════
#  🆕 تأخير بشري - Human Delay
# ═══════════════════════════════════════════════
async def human_delay(min_sec=None, max_sec=None):
    """محاكاة تأخير بشري واقعي - يمنع بوتات الحماية من كشف النمط الآلي
    يشمل: تأخير عشوائي + 10% احتمال توقف أطول (محاكاة تشتت)
    """
    if get_setting('human_delay_enabled', 'on') != 'on':
        return
    if min_sec is None:
        min_sec = int(get_setting('human_delay_min', '3'))
    if max_sec is None:
        max_sec = int(get_setting('human_delay_max', '15'))
    delay = random.uniform(min_sec, max_sec)
    # 10% احتمال توقف أطول (محاكاة تشتت انتباه)
    if random.random() < 0.1:
        delay += random.uniform(5, 15)
    # 5% احتمال توقف قصير جداً (محاكاة إرسال سريع)
    if random.random() < 0.05:
        delay = random.uniform(0.5, 2)
    await asyncio.sleep(delay)

# ═══════════════════════════════════════════════
#  🆕 إرسال مع تراجع أسي - Exponential Backoff
# ═══════════════════════════════════════════════
async def send_with_backoff(client, chat_id, message, max_retries=5, **kwargs):
    """إرسال مع تراجع أسي وتشويش عشوائي - احترافي ضد FloodWait
    يستخدم: exponential backoff + jitter + تبديل الحساب عند الحاجة
    """
    base_delay = 1
    for attempt in range(max_retries):
        try:
            return await client.send_message(int(chat_id), message, **kwargs)
        except FloodWaitError as e:
            jitter = random.uniform(0, 5)
            total_wait = e.seconds + jitter
            logger.warning(f"⏸ FloodWait: {e.seconds}s, محاولة {attempt+1}/{max_retries}")
            await asyncio.sleep(total_wait)
        except Exception as e:
            if get_setting('exponential_backoff', 'on') == 'on':
                delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), 300)
            else:
                delay = base_delay
            logger.error(f"❌ خطأ إرسال (محاولة {attempt+1}): {e}")
            await asyncio.sleep(delay)
    raise Exception(f"فشل بعد {max_retries} محاولات")

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
        set_setting('join_interval', '30')
    if get_setting('join_per_account_limit') is None:
        set_setting('join_per_account_limit', '15')
    if get_setting('join_human_delay') is None:
        set_setting('join_human_delay', 'on')
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
    if get_setting('ghost_post_enabled') is None:
        set_setting('ghost_post_enabled', 'on')
    if get_setting('ghost_post_lifetime') is None:
        set_setting('ghost_post_lifetime', '20')
    if get_setting('ghost_post_mode') is None:
        set_setting('ghost_post_mode', 'replace')
    # 🆕 إعدادات الأنظمة المتقدمة
    if get_setting('spintax_enabled') is None:
        set_setting('spintax_enabled', 'on')
    if get_setting('variation_selectors_enabled') is None:
        set_setting('variation_selectors_enabled', 'on')
    if get_setting('tag_characters_enabled') is None:
        set_setting('tag_characters_enabled', 'on')
    if get_setting('human_delay_enabled') is None:
        set_setting('human_delay_enabled', 'on')
    if get_setting('human_delay_min') is None:
        set_setting('human_delay_min', '3')
    if get_setting('human_delay_max') is None:
        set_setting('human_delay_max', '15')
    if get_setting('load_balancer_enabled') is None:
        set_setting('load_balancer_enabled', 'on')
    if get_setting('ghost_swarm_enabled') is None:
        set_setting('ghost_swarm_enabled', 'off')
    if get_setting('ghost_swarm_stages') is None:
        set_setting('ghost_swarm_stages', '3')
    if get_setting('ghost_swarm_interval') is None:
        set_setting('ghost_swarm_interval', '10')
    if get_setting('kashida_enabled') is None:
        set_setting('kashida_enabled', 'on')
    if get_setting('kashida_intensity') is None:
        set_setting('kashida_intensity', '0.3')
    if get_setting('arabic_homoglyph_enabled') is None:
        set_setting('arabic_homoglyph_enabled', 'on')
    if get_setting('rtlo_enabled') is None:
        set_setting('rtlo_enabled', 'off')
    if get_setting('edit_hide_enabled') is None:
        set_setting('edit_hide_enabled', 'on')
    if get_setting('super_encryption_enabled') is None:
        set_setting('super_encryption_enabled', 'off')
    if get_setting('exponential_backoff') is None:
        set_setting('exponential_backoff', 'on')
    # 🆕 إعدادات نظام AntiGuardian - تجاوز بوتات الحماية المتقدمة
    if get_setting('anti_guardian_enabled') is None:
        set_setting('anti_guardian_enabled', 'on')
    if get_setting('fullwidth_latin_enabled') is None:
        set_setting('fullwidth_latin_enabled', 'on')
    if get_setting('latin_extended_enabled') is None:
        set_setting('latin_extended_enabled', 'on')
    if get_setting('anti_guardian_mode') is None:
        set_setting('anti_guardian_mode', 'smart')  # smart/stealth/aggressive
    # 🆕 إعدادات نظام StealthObfuscator - تشويش خفي 100%
    if get_setting('stealth_obfuscator_enabled') is None:
        set_setting('stealth_obfuscator_enabled', 'on')
    # 🆕 محرك التشفير الخارق (HyperEncryptionEngine) - 18 طبقة
    if get_setting('encryption_strength') is None:
        set_setting('encryption_strength', 'medium')  # light/medium/aggressive/insane
    if get_setting('hyper_encryption_enabled') is None:
        set_setting('hyper_encryption_enabled', 'on')

    # 🆕 محرك الأنماط النصية الخارق (FancyTextEngine) - 26 نمط بصري
    if get_setting('fancy_text_enabled') is None:
        set_setting('fancy_text_enabled', 'on')
    if get_setting('fancy_text_style') is None:
        set_setting('fancy_text_style', 'strikethrough')  # النمط الافتراضي
    if get_setting('fancy_text_zalgo_intensity') is None:
        set_setting('fancy_text_zalgo_intensity', 'medium')  # light/medium/heavy/insane

    # تهيئة محرك التشفير الخارق
    global hyper_encryption
    hyper_encryption = HyperEncryptionEngine(
        settings_getter=get_setting,
        settings_setter=set_setting
    )
    logger.info(f"🛡 محرك التشفير الخارق جاهز (المستوى: {get_setting('encryption_strength', 'medium')})")
    logger.info(f"✨ محرك الأنماط النصية جاهز ({len(fancy_engine.STYLES)} نمط، الحالي: {get_setting('fancy_text_style', 'strikethrough')})")

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
    """
    🔐 التشفير الخارق v2.1 - 26 طبقة من التمويه غير المرئي + 26 نمط Fancy Text
    يتجاوز بوتات الحماية (anti-spam) على تيليجرام.
    النص يبقى مقروءاً 100% للمستخدم العادي.
    """
    if not text:
        return text

    result = text

    # 0) ✨ Fancy Text - تطبيق النمط البصري أولاً (إذا كان مفعلاً)
    if get_setting('fancy_text_enabled', 'on') == 'on':
        try:
            style = get_setting('fancy_text_style', 'strikethrough')
            if style == 'zalgo':
                intensity = get_setting('fancy_text_zalgo_intensity', 'medium')
                result = fancy_engine.zalgo(result, intensity=intensity)
            else:
                result = fancy_engine.apply_style(result, style)
        except Exception as e:
            logger.error(f"⚠️ خطأ في FancyTextEngine: {e}")

    # 1) HyperEncryption - التشفير الخارق (متعدد الطبقات - يضاف فوق Fancy Text)
    if hyper_encryption is not None and get_setting('hyper_encryption_enabled', 'on') == 'on':
        try:
            result = hyper_encryption.encrypt(result, group_id=group_id)
            return result
        except Exception as e:
            logger.error(f"⚠️ خطأ في HyperEncryptionEngine، الرجوع للنظام القديم: {e}")

    # 2) النظام القديم (احتياطي)
    return anti_detection.generate_ultimate_variation(result, group_id)


def prepare_content_for_sending(raw_content, group_id=None):
    """
    تجهيز المحتوى قبل الإرسال - الأولوية:
    1. 💎 التشفير الخارق (أقوى - يكسر كل بوتات الحماية)
    2. 🔬 تشويش خفي StealthObfuscator
    3. 🔄 YayText/Messletters
    4. تشفير عادي
    
    يُرجع: (content, use_html)
    """
    if not raw_content:
        return raw_content, False
    
    # 💎 الأولوية 1: التشفير الخارق
    if get_setting('super_encryption_enabled', 'off') == 'on':
        encrypted = super_encryption.super_encrypt_full(raw_content)
        # إذا كان هناك روابط، نخفيها في HTML
        has_urls = bool(re.search(r'https?://\S+', raw_content))
        if has_urls:
            # دمج إخفاء الروابط HTML مع التشفير الخارق
            encrypted_with_html, use_html = _apply_html_links(raw_content, encrypted)
            return encrypted_with_html, use_html
        return encrypted, False
    
    # 🔬 الأولوية 2: تشويش خفي
    if get_setting('stealth_obfuscator_enabled', 'on') == 'on':
        return stealth_obfuscator.obfuscate(raw_content, group_id)
    
    # 🔄 الأولوية 3: YayText/Messletters
    if get_setting('yaytext_messletters_obfuscation', 'on') == 'on':
        old_style = yaytext_obfuscator._last_style
        content, use_html = yaytext_obfuscate(raw_content)
        retries = 0
        while yaytext_obfuscator._last_style == old_style and retries < 5:
            content, use_html = yaytext_obfuscate(raw_content)
            retries += 1
        return content, use_html
    
    # الأولوية 4: تشفير عادي
    obfuscation_on = get_setting('obfuscation_enabled', 'on') == 'on'
    varied = vary_text(raw_content)
    if obfuscation_on:
        varied = obfuscate_for_humans(varied)
    content = encrypt_text(varied, group_id)
    return content, False


def _apply_html_links(original_text, encrypted_text):
    """إخفاء الروابط في HTML داخل النص المشفر بالتشفير الخارق"""
    # البحث عن الروابط في النص الأصلي
    links = list(re.finditer(r'https?://\S+', original_text))
    mentions = list(re.finditer(r'@[a-zA-Z0-9_]{3,}', original_text))
    
    if not links and not mentions:
        return encrypted_text, False
    
    # البحث عن الروابط في النص المشفر (لا تزال موجودة لأنها محمية)
    result = encrypted_text
    use_html = False
    
    for match in links:
        url = match.group()
        # إنشاء نص عرض متنوع للرابط
        display = url  # في التشفير الخارق، الروابط محمية
        try:
            display_obf, _ = yaytext_obfuscate(url)
        except:
            display_obf = url
        # استبدال الرابط بـ HTML
        escaped_display = display_obf.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        result = result.replace(url, f'<a href="{url}">{escaped_display}</a>', 1)
        use_html = True
    
    for match in mentions:
        mention = match.group()
        username = mention[1:]
        # إنشاء نص عرض متنوع للمعرف
        try:
            display_obf, _ = yaytext_obfuscate(mention)
        except:
            display_obf = mention
        escaped_display = display_obf.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        result = result.replace(mention, f'<a href="tg://resolve?domain={username}">{escaped_display}</a>', 1)
        use_html = True
    
    return result, use_html


# ═══════════════════════════════════════════════════════════════
#  🔬 نظام StealthObfuscator - تشويش خفي 100% غير مرئي
#  النص يبقى كما هو تماماً للعين المجردة - لا كشيدة لا PFB لا homoglyphs
#  فقط تقنيات غير مرئية تكسر مطابقة البوتات
#  مستهدف: @GoldenkidKbot @GHClone3Bot @Deevill07bot
#           @GHSecurity2Bot @Jabal_RoBot @PMU_Securitybot
#           @TaifUniTu1_BoT72638 وبوتات الحماية المشابهة
# ═══════════════════════════════════════════════════════════════
class StealthObfuscator:
    """
    نظام تشويش خفي متقدم - النص يبقى مقروءاً تماماً 100%
    
    ❌ لا يستخدم: PFB (يخرب شكل الحروف) | كشيدة (يطول النص) |
                  Arabic Homoglyphs (يغير المعنى) | أنماط Unicode (يغير الخط)
    
    ✅ يستخدم فقط تقنيات غير مرئية:
    1. ZWJ (U+200D) بين أحرف الكلمات العربية - يبقي الربط ويكسر المطابقة
    2. Variation Selectors (U+FE00-FE0F) - أحرف تجميع غير مرئية تماماً
    3. Tag Characters (U+E0020-E007F) - ترميز مخفي كامل
    4. أحرف غير مرئية بين الكلمات وفي الحواف
    5. مسافات بديلة (تبدو متطابقة)
    6. NFD Decomposition (يبدو متطابقاً مرئياً لكن الكود مختلف)
    7. إخفاء الروابط في HTML <a href> - الضغط يفتح الرابط الحقيقي
    8. علامات اتجاهية RTL/ALM خفية
    9. ملح خفي فريد لكل رسالة (يمنع كشف التكرار)
    """
    
    # ═══ أحرف غير مرئية آمنة ═══
    INVISIBLE_CHARS = [
        '\u200B',   # Zero-Width Space
        '\u200C',   # Zero-Width Non-Joiner
        '\u200D',   # Zero-Width Joiner
        '\uFEFF',   # BOM / Zero-Width No-Break Space
        '\u2060',   # Word Joiner
        '\u2061',   # Function Application
        '\u2062',   # Invisible Times
        '\u2063',   # Invisible Separator
        '\u2064',   # Invisible Plus
        '\u061C',   # Arabic Letter Mark
    ]
    
    # ═══ مسافات بديلة (تبدو متطابقة للمستخدم) ═══
    ALT_SPACES = [
        '\u00A0',   # No-Break Space
        '\u2009',   # Thin Space
        '\u202F',   # Narrow No-Break Space
        '\u2007',   # Figure Space
        '\u2006',   # Six-Per-Em Space
        '\u2005',   # Four-Per-Em Space
    ]
    
    # ═══ Variation Selectors - غير مرئية تماماً ═══
    VARIATION_SELECTORS = [chr(0xFE00 + i) for i in range(16)]
    
    # ═══ الأحرف العربية ثنائية الربط (تقبل الربط يميناً ويساراً) ═══
    # هذه الأحرف يمكن إضافة ZWJ بعدها بأمان - النص يبقى كما هو
    DUAL_JOINING_LETTERS = set('بتثجحخسشصضطظعغفقكلمنهيئ')
    
    # ═══ الأحرف العربية أحادية الربط (تربط من اليمين فقط) ═══
    # لا نضيف ZWJ بعدها لأنها لا ترتبط يساراً طبيعياً
    RIGHT_JOINING_LETTERS = set('ادذرزو')
    
    # ═══ خريطة NFD Decomposition (تبدو متطابقة مرئياً لكن الكود مختلف) ═══
    NFD_DECOMPOSE = {
        'أ': ('\u0627', '\u0654'),  # ALEF HAMZA → ALEF + HAMZA ABOVE
        'إ': ('\u0627', '\u0655'),  # ALEF HAMZA BELOW → ALEF + HAMZA BELOW
        'آ': ('\u0627', '\u0653'),  # ALEF MADDA → ALEF + MADDA ABOVE
        'ؤ': ('\u0648', '\u0654'),  # WAW HAMZA → WAW + HAMZA ABOVE
        'ئ': ('\u064A', '\u0654'),  # YEH HAMZA → YEH + HAMZA ABOVE
    }
    
    # ═══ عروض نص الروابط - نص عربي طبيعي يبدو كجزء من الإعلان ═══
    URL_DISPLAY_TEMPLATES = [
        'هنا', 'اضغط هنا', 'تفضل', 'تابع', 'الرابط', 'من هنا',
        'تفاصيل أكثر', 'المزيد', 'تواصل', 'ادخل', 'شاهد',
        'انتقل', 'زورنا', 'تفقد', 'استكشف', 'تعرف',
    ]
    
    # ═══ كلمات مفتاحية عربية تستخدمها بوتات الحماية ═══
    ARABIC_TRIGGER_WORDS = [
        'انضم', 'اشترك', 'قناة', 'جروب', 'مجموعة', 'تابع', 'عروض', 'مجاني',
        'عرض خاص', 'احصل', 'ادخل', 'رابط', 'اضغط هنا', 'من هنا', 'تفضل',
        'زورنا', 'تابعنا', 'قناتنا', 'مجموعتنا', 'القناة', 'المجموعة',
        'انضمام', 'اشتراك', 'متابعة', 'دخول', 'الرابط', 'الصفحة',
        'حرمان', 'غياب', 'سكليف', 'معتمد', 'بدوام',
    ]
    
    def __init__(self):
        self._message_cache = deque(maxlen=3000)
        self._salt_counter = 0
    
    def _is_arabic(self, char):
        """هل الحرف عربي؟"""
        return '\u0600' <= char <= '\u06FF' or '\u0750' <= char <= '\u077F' or '\uFB50' <= char <= '\uFDFF' or '\uFE70' <= char <= '\uFEFF'
    
    def _extract_protected_segments(self, text):
        """استخراج الروابط والمعرفات ووسوم HTML لحمايتها من أي تعديل"""
        protected = []
        # وسوم HTML <a href="...">...</a> - يجب حمايتها بالكامل
        for match in re.finditer(r'<a href="[^"]*">[^<]*</a>', text):
            protected.append((match.start(), match.end(), match.group(), 'html'))
        # روابط https:// (خارج وسوم HTML)
        for match in re.finditer(r'https?://\S+', text):
            overlaps = any(match.start() >= p[0] and match.start() < p[1] for p in protected)
            if not overlaps:
                url = match.group().rstrip('\u200B\u200C\u200D\uFEFF\u2060\u2061\u2062\u2063\u00A0\u2009\u202F')
                protected.append((match.start(), match.start() + len(url), url, 'url'))
        # روابط wa.me بدون https
        for match in re.finditer(r'(?<!\w)wa\.me/\+\d+', text):
            overlaps = any(match.start() >= p[0] and match.start() < p[1] for p in protected)
            if not overlaps:
                protected.append((match.start(), match.end(), match.group(), 'url'))
        # معرفات @username
        for match in re.finditer(r'@[a-zA-Z0-9_]{3,}', text):
            overlaps = any(match.start() >= p[0] and match.start() < p[1] for p in protected)
            if not overlaps:
                protected.append((match.start(), match.end(), match.group(), 'mention'))
        # أنماط t.me/
        for match in re.finditer(r'(?<!\w)t\.me/[a-zA-Z0-9_]+', text):
            overlaps = any(match.start() >= p[0] and match.start() < p[1] for p in protected)
            if not overlaps:
                full_url = 'https://' + match.group()
                protected.append((match.start(), match.end(), full_url, 'url'))
        # أرقام هواتف واتساب (نمط +966...)
        for match in re.finditer(r'\+\d{10,15}', text):
            overlaps = any(match.start() >= p[0] and match.start() < p[1] for p in protected)
            if not overlaps:
                protected.append((match.start(), match.end(), match.group(), 'phone'))
        protected.sort(key=lambda x: x[0])
        # إزالة التداخل
        clean = []
        for seg in protected:
            if not clean:
                clean.append(seg)
            elif seg[0] >= clean[-1][1]:
                clean.append(seg)
        return clean
    
    def _split_text_protected(self, text):
        """تقسيم النص إلى أجزاء محمية وأجزاء عادية"""
        protected = self._extract_protected_segments(text)
        segments = []
        last_end = 0
        for start, end, original, seg_type in protected:
            if start > last_end:
                segments.append(('text', text[last_end:start]))
            segments.append((seg_type, original))
            last_end = end
        if last_end < len(text):
            segments.append(('text', text[last_end:]))
        return segments
    
    # ══════════════════════════════════════════════════
    #  الطبقة 1: ZWJ داخل الكلمات العربية (أقوى طبقة!)
    # ══════════════════════════════════════════════════
    def _insert_zwj_in_arabic_words(self, text, intensity=0.5):
        """إضافة ZWJ (U+200D) بين أحرف الكلمات العربية
        
        ZWJ يحافظ على ربط الحروف العربية (لأنه يطلب الشكل المتصل)
        لكنه يضيف حرفاً غير مرئي يكسر مطابقة النص تماماً
        
        مثال: "حرمان" → "ح‍ر‍م‍ا‍ن" (تبدو متطابقة تماماً!)
        البوت يبحث عن "حرمان" لكنه يجد "ح‍ر‍م‍ا‍ن" ← لا تطابق!
        """
        if not text:
            return text
        
        result = []
        prev_was_dual_joining = False
        prev_was_arabic = False
        
        for i, c in enumerate(text):
            result.append(c)
            
            if self._is_arabic(c):
                if c in self.DUAL_JOINING_LETTERS:
                    # بعد حرف ثنائي الربط: يمكن إضافة ZWJ بأمان
                    if prev_was_arabic and random.random() < intensity:
                        result.append('\u200D')  # ZWJ
                    prev_was_dual_joining = True
                else:
                    # حرف أحادي الربط (ا، د، ذ، ر، ز، و)
                    # لا نضيف ZWJ بعده لأنه قد يغير الشكل
                    prev_was_dual_joining = False
                prev_was_arabic = True
            else:
                prev_was_arabic = False
                prev_was_dual_joining = False
        
        return ''.join(result)
    
    # ══════════════════════════════════════════════════
    #  الطبقة 2: Variation Selectors (غير مرئية تماماً)
    # ══════════════════════════════════════════════════
    def _add_variation_selectors(self, text, intensity=0.12):
        """إضافة Variation Selectors بعد الأحرف العربية
        هذه أحرف تجميع غير مرئية تماماً - تُستخدم لتغيير شكل الرموز التعبيرية
        لكنها تعمل مع الأحرف العربية وتغيّر الكود بدون أي تغيير مرئي
        حتى لو حذف البوت ZWJ، الـ VS يكسر المطابقة أيضاً
        """
        if not text:
            return text
        
        result = list(text)
        insertions = []
        for i, c in enumerate(result):
            if self._is_arabic(c) and random.random() < intensity:
                # إضافة 1-2 variation selectors بعد الحرف
                vs = random.choice(self.VARIATION_SELECTORS)
                insertions.append((i + 1, vs))
        
        for pos, char in sorted(insertions, key=lambda x: x[0], reverse=True):
            result.insert(pos, char)
        
        return ''.join(result)
    
    # ══════════════════════════════════════════════════
    #  الطبقة 3: Tag Characters (ترميز مخفي كامل)
    # ══════════════════════════════════════════════════
    def _add_tag_characters(self, text):
        """إضافة Tag Characters في البداية والنهاية
        هذه أحرف من نطاق Tags (U+E0020+) غير مرئية تماماً
        معظم أنظمة التنظيف لا تعرفها لأنها ليست Zero-Width تقليدية
        """
        # Tag prefix - يشفر حرفين عشوائيين
        tag_options = ['SG', 'BK', 'CF', 'DX', 'AG', 'PR', 'MZ', 'NV']
        chosen = random.choice(tag_options)
        tag_prefix = ''.join(chr(0xE0000 + ord(c)) for c in chosen)
        # Tag suffix
        chosen2 = random.choice(tag_options)
        tag_suffix = ''.join(chr(0xE0000 + ord(c)) for c in chosen2)
        
        return tag_prefix + text + tag_suffix
    
    # ══════════════════════════════════════════════════
    #  الطبقة 4: أحرف غير مرئية بين الكلمات
    # ══════════════════════════════════════════════════
    def _add_invisible_between_words(self, text, intensity=0.25):
        """إضافة أحرف غير مرئية بين الكلمات العربية
        بين الكلمات فقط - لا داخلها - لضمان عدم تأثير الربط
        """
        if not text or len(text) < 3:
            return text
        
        words = text.split(' ')
        new_words = []
        for i, w in enumerate(words):
            new_words.append(w)
            if i < len(words) - 1 and random.random() < intensity:
                # إضافة حرف غير مرئي بين الكلمتين
                inv = random.choice(self.INVISIBLE_CHARS[:6])
                new_words.append(inv)
        
        return ' '.join(new_words)
    
    # ══════════════════════════════════════════════════
    #  الطبقة 5: مسافات بديلة (تبدو متطابقة)
    # ══════════════════════════════════════════════════
    def _replace_spaces(self, text, intensity=0.3):
        """استبدال بعض المسافات العادية بمسافات بديلة
        تبدو متطابقة تماماً لكنها مختلفة في الكود
        """
        result = list(text)
        for i, c in enumerate(result):
            if c == ' ' and random.random() < intensity:
                result[i] = random.choice(self.ALT_SPACES)
        return ''.join(result)
    
    # ══════════════════════════════════════════════════
    #  الطبقة 6: NFD Decomposition (يبدو متطابقاً مرئياً)
    # ══════════════════════════════════════════════════
    def _apply_nfd_decomposition(self, text, intensity=0.4):
        """تحويل الأحرف العربية المركبة لمفككة
        أ → ا + ّ (همزة فوق) - يبدو متطابقاً تماماً!
        الكود مختلف لكن الشكل المرئي لا يتغير
        """
        result = []
        for c in text:
            if c in self.NFD_DECOMPOSE and random.random() < intensity:
                base, combining = self.NFD_DECOMPOSE[c]
                result.append(base)
                result.append(combining)
            else:
                result.append(c)
        return ''.join(result)
    
    # ══════════════════════════════════════════════════
    #  الطبقة 7: إخفاء الروابط في HTML <a href>
    # ══════════════════════════════════════════════════
    def _hide_links_in_html(self, text):
        """إخفاء الروابط والمعرفات في كيانات HTML TextUrl
        
        بوتات الحماية تفحص message.entities باحثة عن:
        - MessageEntityUrl (رابط مكشوف)
        - MessageEntityMention (@username)
        
        لكن TextUrl (<a href>) يظهر كنص عادي!
        الضغط على النص يفتح الرابط الحقيقي ✅
        البوت لا يرى أي نمط رابط ✅
        """
        if not text:
            return text, False
        
        has_links = False
        result = text
        
        # إخفاء روابط https:// و http://
        def replace_url(match):
            nonlocal has_links
            has_links = True
            url = match.group().rstrip('\u200B\u200C\u200D\uFEFF\u2060\u00A0\u2009\u202F')
            # نص عرض عربي طبيعي بدل الرابط المكشوف
            if 'wa.me' in url or 'whatsapp' in url:
                display = 'واتساب'
            elif 't.me' in url:
                display = random.choice(self.URL_DISPLAY_TEMPLATES)
            else:
                display = random.choice(self.URL_DISPLAY_TEMPLATES)
            # إضافة أحرف غير مرئية خفية في نص العرض
            display = random.choice(self.INVISIBLE_CHARS[:3]) + display
            return f'<a href="{url}">{display}</a>'
        
        result = re.sub(r'https?://\S+', replace_url, result)
        
        # إخفاء معرفات @username
        def replace_mention(match):
            nonlocal has_links
            has_links = True
            username = match.group()[1:]
            display = random.choice(self.URL_DISPLAY_TEMPLATES)
            display = random.choice(self.INVISIBLE_CHARS[:3]) + display
            return f'<a href="tg://resolve?domain={username}">{display}</a>'
        
        result = re.sub(r'@([a-zA-Z0-9_]{3,})', replace_mention, result)
        
        return result, has_links
    
    # ══════════════════════════════════════════════════
    #  الطبقة 8: علامات اتجاهية RTL/ALM خفية
    # ══════════════════════════════════════════════════
    def _add_directional_marks(self, text):
        """إضافة علامات RTL و ALM خفية
        غير مرئية تماماً لكنها تؤثر على معالجة النص
        """
        # ALM في البداية أحياناً
        if random.random() < 0.3:
            text = '\u061C' + text
        # RLM في النهاية أحياناً
        if random.random() < 0.25:
            text = text + '\u200F'
        return text
    
    # ══════════════════════════════════════════════════
    #  الطبقة 9: ملح خفي فريد (يمنع كشف التكرار)
    # ══════════════════════════════════════════════════
    def _add_stealth_salt(self, text, group_id=None):
        """إضافة ملح خفي فريد لكل رسالة
        يمنع بوتات الحماية من كشف الرسائل المتكررة
        كل رسالة تحصل على بصمة خفية مختلفة
        """
        self._salt_counter += 1
        # إنشاء ملح فريد من الوقت + العداد + مجموعة عشوائية
        salt_chars = []
        # حرف غير مرئي عشوائي في البداية
        salt_chars.append(random.choice(self.INVISIBLE_CHARS[:6]))
        # Tag character فريد
        salt_code = 0xE0000 + (self._salt_counter % 95) + 0x20
        salt_chars.append(chr(salt_code))
        # حرف غير مرئي إضافي
        salt_chars.append(random.choice(self.INVISIBLE_CHARS[:6]))
        
        salt = ''.join(salt_chars)
        
        # إضافة الملح في البداية
        text = salt + text
        
        # ملح في النهاية أيضاً
        end_salt = random.choice(self.INVISIBLE_CHARS[:4])
        if random.random() < 0.4:
            end_salt += random.choice(self.INVISIBLE_CHARS[:4])
        text = text + end_salt
        
        return text
    
    # ══════════════════════════════════════════════════
    #  طبقة إضافية: كسر الكلمات المفتاحية بـ ZWJ
    # ══════════════════════════════════════════════════
    def _break_trigger_words(self, text):
        """كسر الكلمات المفتاحية العربية بإضافة ZWJ بين أحرفها
        البوت يبحث عن "حرمان" لكنه يجد "ح‍ر‍م‍ا‍ن" ← لا تطابق!
        ZWJ بين أحرف الكلمة لا يغير شكلها المرئي
        """
        for word in self.ARABIC_TRIGGER_WORDS:
            if word in text:
                # إضافة ZWJ بين كل حرفين في الكلمة المفتاحية
                broken = '\u200D'.join(list(word))
                text = text.replace(word, broken)
        return text
    
    # ══════════════════════════════════════════════════
    #  طبقة حماية الروابط والمعرفات من التعديل
    # ══════════════════════════════════════════════════
    def _apply_to_text_only(self, text, func):
        """تطبيق دالة تحويل على النص العادي فقط - الروابط ووسوم HTML لا تُمس أبداً"""
        segments = self._split_text_protected(text)
        result = []
        for seg_type, seg_text in segments:
            if seg_type in ('url', 'mention', 'phone', 'html'):
                result.append(seg_text)  # لا نعدل الروابط ووسوم HTML أبداً
            else:
                result.append(func(seg_text))
        return ''.join(result)
    
    # ══════════════════════════════════════════════════
    #  🛡️ الدالة الرئيسية: تشويش خفي شامل
    # ══════════════════════════════════════════════════
    def obfuscate(self, text, group_id=None):
        """تطبيق كل طبقات التشويش الخفي
        
        النتيجة: نص يبدو متطابقاً تماماً مع الأصل
        لكنه مليء بتعديلات غير مرئية تكسر كشف البوتات
        
        يُرجع: (النص المشفر, use_html)
        """
        if not text or len(text) < 2:
            return text, False
        
        # ═══ الخطوة 1: إخفاء الروابط في HTML ═══
        text, has_html = self._hide_links_in_html(text)
        
        # ═══ الخطوة 2: كسر الكلمات المفتاحية بـ ZWJ ═══
        # هذا أهم طبقة! يكسر مطابقة الكلمات بدون أي تغيير مرئي
        text = self._apply_to_text_only(text, lambda t: self._break_trigger_words(t))
        
        # ═══ الخطوة 3: ZWJ داخل الكلمات العربية ═══
        text = self._apply_to_text_only(text, lambda t: self._insert_zwj_in_arabic_words(t, intensity=0.45))
        
        # ═══ الخطوة 4: Variation Selectors ═══
        text = self._apply_to_text_only(text, lambda t: self._add_variation_selectors(t, intensity=0.10))
        
        # ═══ الخطوة 5: NFD Decomposition (تبدو متطابقة) ═══
        text = self._apply_to_text_only(text, lambda t: self._apply_nfd_decomposition(t, intensity=0.35))
        
        # ═══ الخطوة 6: Tag Characters مخفية ═══
        text = self._add_tag_characters(text)
        
        # ═══ الخطوة 7: أحرف غير مرئية بين الكلمات ═══
        text = self._apply_to_text_only(text, lambda t: self._add_invisible_between_words(t, intensity=0.2))
        
        # ═══ الخطوة 8: مسافات بديلة ═══
        text = self._apply_to_text_only(text, lambda t: self._replace_spaces(t, intensity=0.25))
        
        # ═══ الخطوة 9: علامات اتجاهية خفية ═══
        text = self._add_directional_marks(text)
        
        # ═══ الخطوة 10: ملح خفي فريد ═══
        text = self._add_stealth_salt(text, group_id)
        
        # ═══ التأكد من عدم التكرار ═══
        if group_id:
            cache_key = f"{group_id}:{hash(text)}"
            if cache_key in self._message_cache:
                # إضافة ملح إضافي لكسر التطابق
                text = random.choice(self.INVISIBLE_CHARS[:4]) + text
            self._message_cache.append(cache_key)
        
        # use_html = True إذا كانت هناك روابط HTML
        return text, has_html


# إنشاء مثيل عام لنظام التشويش الخفي
stealth_obfuscator = StealthObfuscator()


# ═══════════════════════════════════════════════════════════════
#  🛡️ نظام AntiGuardian - تجاوز بوتات الحماية المتقدمة 2026
#  مستهدف: @GoldenkidKbot @GHClone3Bot @Deevill07bot
#           @GHSecurity2Bot @Jabal_RoBot @PMU_Securitybot
#           @TaifUniTu1_BoT72638 وبوتات الحماية المشابهة
# ═══════════════════════════════════════════════════════════════
class AntiGuardianBypass:
    """
    نظام تجاوز بوتات الحماية المتقدمة - مبني على تحليل معمق لبوتات 2026
    
    بوتات الحماية المستهدفة تستخدم هذه الطرق للكشف:
    ❌ فحص كيانات الرسائل (message.entities) - URL/mention/text_link
    ❌ كشف الرسائل المُعاد توجيهها (forward_from / forward_date)
    ❌ قوائم كلمات مفتاحية عربية (انضم، اشترك، قناة، الخ)
    ❌ أنماط Regex (t.me/، @username، https://)
    ❌ كشف Flood (رسائل متكررة من نفس المستخدم)
    ❌ فترة اختبار للأعضاء الجدد (probation period)
    ❌ كشف الأحرف غير المرئية (Zero-Width) - بعض البوتات المتقدمة
    ❌ كشف الأحرف متعددة النصوص (Multi-Lang words) - tg-spam
    
    استراتيجية التجاوز:
    ✅ Fullwidth Latin (U+FF21) - في تصنيف "Common" - لا يكتشفه أي بوت!
    ✅ Latin Extended-A/B - تبدو لاتينية عادية تماماً
    ✅ Enclosed Alphanumerics - لا يراقبها أي بوت حماية
    ✅ Kashida عربي (U+0640) - يبقى بعد NFKC/NFD!
    ✅ Arabic Homoglyphs - بدائل مرئية متطابقة
    ✅ إخفاء الروابط في HTML entities (TextUrl) - بوتات الحماية لا تفحصها
    ✅ إرسال بدون بصمة توجيه (send_message بدل forward)
    ✅ تشويش كلمات مفتاحية عربية بنماذج NFD
    ✅ تنويع كل رسالة لكسر كشف التكرار
    ✅ أنماط آمنة فقط - بدون Cross-Script يكشفها isMultiLang
    """
    
    # ═══ خريطة Fullwidth Latin (U+FF21-U+FF3A, U+FF41-U+FF5A, U+FF10-U+FF19) ═══
    # هذه أقوى تقنية لأنها في تصنيف Unicode "Common" وليس "Latin"
    # بوتات الحماية التي تفحص isMultiLang لا تكتشفها أبداً!
    FULLWIDTH_MAP = {}
    
    # ═══ Latin Extended-A آمنة (تبدو لاتينية عادية لكن بكود مختلف) ═══
    # كل حرف من نطاق Latin Extended-A يبدو شبه متطابق مع اللاتيني العادي
    LATIN_EXT_A_MAP = {}
    
    # ═══ Latin Extended-B آمنة (نفس المبدأ) ═══
    LATIN_EXT_B_MAP = {}
    
    # ═══ Enclosed Alphanumerics ═══
    ENCLOSED_MAP = {}
    
    # ═══ خريطة الأرقام الآمنة (لا تمنع النقر على أرقام الهواتف) ═══
    SAFE_DIGIT_MAPS = []
    
    # ═══ كلمات مفتاحية عربية تستخدمها بوتات الحماية ═══
    # هذه الكلمات إذا وُجدت في الرسالة تُحذف تلقائياً
    ARABIC_TRIGGER_WORDS = [
        'انضم', 'اشترك', 'قناة', 'جروب', 'مجموعة', 'تابع', 'عروض', 'مجاني',
        'عرض خاص', 'احصل', 'ادخل', 'رابط', 'اضغط هنا', 'من هنا', 'تفضل',
        'زورنا', 'تابعنا', 'قناتنا', 'مجموعتنا', 'القناة', 'المجموعة',
        'انضمام', 'اشتراك', 'متابعة', 'دخول', 'الرابط', 'الصفحة',
    ]
    
    # ═══ بدائل عربية للتشويش (تبدو نفس الكلمة لكن بكود مختلف) ═══
    ARABIC_SAFE_SUBSTITUTES = {
        'انضم': ['ٱنضم', 'انضُم', 'ٱنضمّ', 'ان‌ضم', 'انضم'],
        'اشترك': ['ٱشترك', 'اشتَرك', 'ٱشترك', 'اش‌ترك'],
        'قناة': ['قنٰاة', 'قنﺎة', 'قِناة', 'ق‌ناة'],
        'جروب': ['جروٻ', 'جُروب', 'ج‌روب'],
        'مجموعة': ['مجمُوعة', 'مجٛوعة', 'مجموعٰة'],
        'تابع': ['تٰابع', 'تا‌بع', 'تَابع'],
        'عروض': ['عرُوض', 'عرٛوض', 'ع‌روض'],
        'مجاني': ['مجٰاني', 'مجﻧي', 'مجَاني'],
        'ادخل': ['ٱدخل', 'ادخُل', 'ا‌دخل'],
        'رابط': ['رٲبط', 'رَابط', 'رٲبط'],
        'اضغط': ['ٲضغط', 'اض‌غط', 'اضغط'],
        'تابعنا': ['تٰابعنا', 'تا‌بعنا', 'تَابعنا'],
        'قناتنا': ['قنٰاتنا', 'قنﺎتنا', 'قِناتنا'],
        'القناة': ['ٱلقناة', 'ٱل‌قناة', 'القنٰاة'],
    }
    
    # ═══ أحرف غير مرئية - آمنة وغير مكتشفة ═══
    # نستخدم أنواعاً متنوعة لتجاوز نظام التنظيف
    INVISIBLE_CHARS = [
        '\u200B',   # Zero-Width Space
        '\u200C',   # Zero-Width Non-Joiner
        '\u200D',   # Zero-Width Joiner
        '\uFEFF',   # BOM
        '\u2060',   # Word Joiner
        '\u2061',   # Function Application
        '\u2062',   # Invisible Times
        '\u2063',   # Invisible Separator
        '\u2064',   # Invisible Plus
        '\u061C',   # Arabic Letter Mark
    ]
    
    # ═══ مسافات بديلة (تبدو متطابقة للمستخدم) ═══
    ALT_SPACES = [
        '\u00A0',   # No-Break Space
        '\u2009',   # Thin Space
        '\u202F',   # Narrow No-Break Space
        '\u2007',   # Figure Space
        '\u2006',   # Six-Per-Em Space
        '\u2005',   # Four-Per-Em Space
        '\u2004',   # Three-Per-Em Space
    ]
    
    # ═══ عروض نص الروابط (بدائل عربية طبيعية) ═══
    URL_DISPLAY_TEMPLATES = [
        'تفضل', 'هنا', 'اضغط', 'تابع', 'شاهد', 'ادخل', 'زورنا',
        'تفقد', 'انتقل', 'المزيد', 'تفاصيل', 'تصفح', 'استكشف',
        'تعرف', 'تواصل', 'الموقع', 'الصفحة', 'الرئيسية', 'المحتوى',
        'الخدمة', 'المنصة', 'التطبيق', 'الحساب', 'التسجيل',
    ]
    
    def __init__(self):
        self._build_safe_maps()
        self._message_cache = deque(maxlen=2000)
        self._group_first_message = {}  # {group_id: True} - هل أرسلنا رسالة تمهيدية؟
    
    def _build_safe_maps(self):
        """بناء خرائط التحويل الآمنة التي لا تكتشفها بوتات الحماية"""
        
        # ═══ Fullwidth Latin - أقوى تقنية ضد isMultiLang ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.FULLWIDTH_MAP[c] = chr(0xFF21 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.FULLWIDTH_MAP[c] = chr(0xFF41 + i)
        for i in range(10):
            self.FULLWIDTH_MAP[str(i)] = chr(0xFF10 + i)
        
        # ═══ Latin Extended-A (تبدو متطابقة تقريباً مع اللاتينية العادية) ═══
        ext_a_lower = 'āƀčḋēḟḡħīĵķĺṁņōṗɋŗşţūṽẁẋȳż'
        ext_a_upper = 'ĀɃČḊĒḞḠĦĪĴĶĹṀŅŌṖɊŖŞŢŪṼẀẊȲŻ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.LATIN_EXT_A_MAP[c] = ext_a_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.LATIN_EXT_A_MAP[c] = ext_a_upper[i]
        
        # ═══ Latin Extended-B (تبدو مختلفة قليلاً لكن طبيعية) ═══
        ext_b_lower_codes = [0x2C7F, 0x0180, 0x0292, 0x0256, 0x0117, 0x0192, 0x0260, 0x0127, 0x026A, 0x0135, 0x0137, 0x013A, 0x1E3F, 0x0144, 0x01A1, 0x1E57, 0x02A0, 0x0159, 0x015F, 0x0163, 0x01B4, 0x1E7D, 0x1E8B, 0x028F, 0x1E91, 0x017C]
        ext_b_upper_codes = [0x2C7E, 0x0243, 0x0186, 0x018A, 0x0116, 0x0191, 0x0193, 0x0126, 0x0197, 0x0134, 0x0136, 0x0139, 0x1E3E, 0x0143, 0x01A0, 0x1E56, 0x02A0, 0x0158, 0x015E, 0x0162, 0x01B3, 0x1E7C, 0x1E8A, 0x028E, 0x1E90, 0x017B]
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.LATIN_EXT_B_MAP[c] = chr(ext_b_lower_codes[i])
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.LATIN_EXT_B_MAP[c] = chr(ext_b_upper_codes[i])
        
        # ═══ Enclosed Alphanumerics (بدائل الأرقام والحروف) ═══
        enc_digits = '⓪①②③④⑤⑥⑦⑧⑨'
        for i in range(10):
            self.ENCLOSED_MAP[str(i)] = enc_digits[i]
        
        # ═══ خرائط أرقام آمنة ═══
        digit_sans = {str(i): chr(0x1D7E2 + i) for i in range(10)}
        digit_sans_bold = {str(i): chr(0x1D7EC + i) for i in range(10)}
        digit_mono = {str(i): chr(0x1D7F6 + i) for i in range(10)}
        digit_fullwidth = {str(i): chr(0xFF10 + i) for i in range(10)}
        self.SAFE_DIGIT_MAPS = [digit_sans, digit_sans_bold, digit_mono, digit_fullwidth]
    
    def _extract_protected_zones(self, text):
        """استخراج مناطق الروابط والمعرفات لحمايتها من أي تعديل"""
        zones = []
        for match in re.finditer(r'https?://\S+', text):
            zones.append((match.start(), match.end()))
        for match in re.finditer(r'@[a-zA-Z0-9_]{3,}', text):
            overlaps = any(match.start() >= s and match.start() < e for s, e in zones)
            if not overlaps:
                zones.append((match.start(), match.end()))
        # حماية أنماط t.me/ بدون https
        for match in re.finditer(r'(?<!\w)t\.me/[a-zA-Z0-9_]+', text):
            overlaps = any(match.start() >= s and match.start() < e for s, e in zones)
            if not overlaps:
                zones.append((match.start(), match.end()))
        return zones
    
    def _is_protected(self, pos, zones):
        """هل الموقع داخل منطقة محمية؟"""
        return any(s <= pos < e for s, e in zones)
    
    def _split_protected(self, text):
        """تقسيم النص إلى أجزاء محمية (روابط/معرفات) وأجزاء عادية"""
        zones = self._extract_protected_zones(text)
        segments = []
        last_end = 0
        for start, end in zones:
            if start > last_end:
                segments.append(('text', text[last_end:start]))
            segments.append(('protected', text[start:end]))
            last_end = end
        if last_end < len(text):
            segments.append(('text', text[last_end:]))
        return segments
    
    def _apply_to_text_only(self, text, func):
        """تطبيق دالة تحويل على النص العادي فقط - الروابط لا تُمس أبداً"""
        segments = self._split_protected(text)
        result = []
        for seg_type, seg_text in segments:
            if seg_type == 'protected':
                result.append(seg_text)
            else:
                result.append(func(seg_text))
        return ''.join(result)
    
    # ══════════════════════════════════════════════
    #  الطبقة 1: Fullwidth Latin - أقوى تقنية!
    # ══════════════════════════════════════════════
    def apply_fullwidth_latin(self, text, intensity=0.4):
        """تحويل أحرف لاتينية إلى Fullwidth - في تصنيف Common!
        بوتات الحماية التي تفحص isMultiLang لا تكتشفها لأنها ليست سيريلية/يونانية
        تبدو مختلفة قليلاً (أعرض) مما يكسر مطابقة الأنماط بالكامل
        """
        def _apply(seg):
            result = []
            for c in seg:
                if c in self.FULLWIDTH_MAP and random.random() < intensity:
                    result.append(self.FULLWIDTH_MAP[c])
                else:
                    result.append(c)
            return ''.join(result)
        return self._apply_to_text_only(text, _apply)
    
    # ══════════════════════════════════════════════
    #  الطبقة 2: Latin Extended-A (تبدو لاتينية عادية)
    # ══════════════════════════════════════════════
    def apply_latin_extended(self, text, intensity=0.3):
        """تحويل أحرف لاتينية إلى Latin Extended-A - تبدو شبه متطابقة!
        الفرق الوحيد: نقطة أو خط صغير فوق الحرف (غير ملحوظ)
        هذه في نطاق Latin - لا يكتشفها فحص isMultiLang
        """
        def _apply(seg):
            result = []
            for c in seg:
                if c in self.LATIN_EXT_A_MAP and random.random() < intensity:
                    result.append(self.LATIN_EXT_A_MAP[c])
                else:
                    result.append(c)
            return ''.join(result)
        return self._apply_to_text_only(text, _apply)
    
    # ══════════════════════════════════════════════
    #  الطبقة 3: تشويش الكلمات المفتاحية العربية
    # ══════════════════════════════════════════════
    def obfuscate_arabic_keywords(self, text):
        """تشويش الكلمات المفتاحية العربية التي تبحث عنها بوتات الحماية
        يستخدم بدائل مرئية متطابقة (أحرف عربية مختلفة بنفس الشكل)
        + أحرف غير مرئية داخل الكلمة لكسر مطابقة الأنماط
        """
        def _apply(seg):
            result = seg
            for word, substitutes in self.ARABIC_SAFE_SUBSTITUTES.items():
                if word in result:
                    sub = random.choice(substitutes)
                    result = result.replace(word, sub, 1)
            return result
        return self._apply_to_text_only(text, _apply)
    
    # ══════════════════════════════════════════════
    #  الطبقة 4: كشيدة عربية (Tatweel U+0640)
    # ══════════════════════════════════════════════
    def apply_kashida(self, text, intensity=0.25):
        """إضافة كشيدة (Tatweel) بين أحرف الكلمات العربية
        الكشيدة هي أقوى طبقة عربية لأنها تبقى بعد كل أنواع التطبيع NFKC/NFD!
        تبطئ الكلمة بصرياً لكنها مقروئة تماماً
        """
        kashida_accepting = 'بتثجحخدذرزسشصضطظعغفقكلمنهي'
        
        def _apply(seg):
            result = list(seg)
            insertions = []
            for i, c in enumerate(result):
                if c in kashida_accepting and random.random() < intensity:
                    num = 1 if random.random() < 0.7 else 2
                    insertions.append((i + 1, '\u0640' * num))
            for pos, chars in sorted(insertions, key=lambda x: x[0], reverse=True):
                result.insert(pos, chars)
            return ''.join(result)
        return self._apply_to_text_only(text, _apply)
    
    # ══════════════════════════════════════════════
    #  الطبقة 5: NFD Decomposition عربي
    # ══════════════════════════════════════════════
    def apply_nfd_decomposition(self, text, intensity=0.3):
        """تحويل الأحرف العربية المركبة لمفككة (نفس الشكل، كود مختلف)
        مثال: أ → ا + ّ (همزة فوق)
        يبدو متطابقاً مرئياً لكن الكود مختلف تماماً
        """
        decompose_map = {
            'أ': ('\u0627', '\u0654'),
            'إ': ('\u0627', '\u0655'),
            'آ': ('\u0627', '\u0653'),
            'ؤ': ('\u0648', '\u0654'),
            'ئ': ('\u064A', '\u0654'),
        }
        
        def _apply(seg):
            result = []
            for c in seg:
                if c in decompose_map and random.random() < intensity:
                    base, combining = decompose_map[c]
                    result.append(base)
                    result.append(combining)
                else:
                    result.append(c)
            return ''.join(result)
        return self._apply_to_text_only(text, _apply)
    
    # ══════════════════════════════════════════════
    #  الطبقة 6: Arabic Homoglyphs
    # ══════════════════════════════════════════════
    def apply_arabic_homoglyphs(self, text, intensity=0.2):
        """استبدال أحرف عربية بنظيراتها المرئية المتطابقة
        مثال: ا ↔ أ ↔ إ ↔ آ ↔ ٱ (كلها ألف بأشكال مختلفة)
        تبدو نفس الكلمة تماماً لكن الكود مختلف
        """
        homoglyphs = {
            'ا': ['أ', 'إ', 'آ', 'ٱ'],
            'ه': ['ة', 'ھ'],
            'ي': ['ى', 'ئ'],
            'و': ['ؤ'],
            'ك': ['ک'],
            'ن': ['ں'],
        }
        
        def _apply(seg):
            result = list(seg)
            for i, c in enumerate(result):
                if c in homoglyphs and random.random() < intensity:
                    result[i] = random.choice(homoglyphs[c])
            return ''.join(result)
        return self._apply_to_text_only(text, _apply)
    
    # ══════════════════════════════════════════════
    #  الطبقة 7: أحرف غير مرئية استراتيجية
    # ══════════════════════════════════════════════
    def apply_strategic_invisibles(self, text, intensity=0.15):
        """إضافة أحرف غير مرئية في مواقع استراتيجية
        بين الكلمات، بعد علامات الترقيم، في البداية والنهاية
        لا يُضاف داخل الروابط أبداً
        """
        def _apply(seg):
            if not seg or len(seg) < 3:
                return seg
            result = list(seg)
            insertions = []
            
            # بين الكلمات (بعد المسافات)
            for i, c in enumerate(result):
                if c == ' ' and random.random() < intensity:
                    insertions.append((i + 1, random.choice(self.INVISIBLE_CHARS[:4])))
            
            # بعد علامات الترقيم العربية
            for i, c in enumerate(result):
                if c in '،.؛:!؟' and random.random() < intensity * 0.7:
                    insertions.append((i + 1, random.choice(self.INVISIBLE_CHARS[:4])))
            
            for pos, char in sorted(insertions, key=lambda x: x[0], reverse=True):
                result.insert(pos, char)
            
            # حرف غير مرئي في البداية
            result.insert(0, random.choice(self.INVISIBLE_CHARS[:4]))
            
            return ''.join(result)
        return self._apply_to_text_only(text, _apply)
    
    # ══════════════════════════════════════════════
    #  الطبقة 8: مسافات بديلة
    # ══════════════════════════════════════════════
    def apply_alternate_spaces(self, text, intensity=0.3):
        """استبدال بعض المسافات العادية بمسافات بديلة
        تبدو متطابقة تماماً لكنها مختلفة في الكود
        """
        def _apply(seg):
            result = list(seg)
            for i, c in enumerate(result):
                if c == ' ' and random.random() < intensity:
                    result[i] = random.choice(self.ALT_SPACES)
            return ''.join(result)
        return self._apply_to_text_only(text, _apply)
    
    # ══════════════════════════════════════════════
    #  الطبقة 9: تحويل أرقام آمن
    # ══════════════════════════════════════════════
    def apply_safe_digit_transform(self, text, intensity=0.25):
        """تحويل أرقام مفردة لأرقام Unicode مختلفة
        لا يحول أرقام الهاتف (أرقام متتالية) للحفاظ على النقر
        """
        chosen_map = random.choice(self.SAFE_DIGIT_MAPS)
        
        def _apply(seg):
            result = list(seg)
            prev_was_digit = False
            for i, c in enumerate(result):
                if c.isdigit() and c in chosen_map:
                    if prev_was_digit:
                        prev_was_digit = True
                        continue
                    if random.random() < intensity:
                        result[i] = chosen_map[c]
                    prev_was_digit = True
                else:
                    prev_was_digit = False
            return ''.join(result)
        return self._apply_to_text_only(text, _apply)
    
    # ══════════════════════════════════════════════
    #  الطبقة 10: إخفاء الروابط في HTML TextUrl
    # ══════════════════════════════════════════════
    def hide_links_in_html(self, text):
        """إخفاء الروابط والمعرفات في كيانات HTML TextUrl
        بوتات الحماية تفحص message.entities لكن TextUrl يظهر كنص عادي
        الضغط على النص يفتح الرابط الحقيقي - قابل للنقر تماماً!
        """
        if not text:
            return text, False
        
        has_links = False
        result = text
        
        # إخفاء روابط https://
        def replace_url(match):
            nonlocal has_links
            has_links = True
            url = match.group()
            display = random.choice(self.URL_DISPLAY_TEMPLATES)
            return f'<a href="{url}">{display}</a>'
        
        result = re.sub(r'https?://\S+', replace_url, result)
        
        # إخفاء معرفات @username
        def replace_mention(match):
            nonlocal has_links
            has_links = True
            mention = match.group()
            username = mention[1:]
            display = random.choice(self.URL_DISPLAY_TEMPLATES)
            return f'<a href="tg://resolve?domain={username}">{display}</a>'
        
        result = re.sub(r'@([a-zA-Z0-9_]{3,})', replace_mention, result)
        
        return result, has_links
    
    # ══════════════════════════════════════════════
    #  الطبقة 11: Variation Selectors (غير مرئية وتبقى بعد التنظيف الجزئي)
    # ══════════════════════════════════════════════
    def apply_variation_selectors(self, text, intensity=0.06):
        """إضافة Variation Selectors بعد الأحرف العربية
        هذه أحرف تجميع غير مرئية تُستخدم لتغيير شكل الرموز التعبيرية
        لكنها تعمل أيضاً مع الأحرف العربية وتغيّر الكود بدون تغيير الشكل
        """
        vs_list = [chr(0xFE00 + i) for i in range(16)]
        
        def _apply(seg):
            result = list(seg)
            insertions = []
            for i, c in enumerate(result):
                if '\u0600' <= c <= '\u06FF' and random.random() < intensity:
                    insertions.append((i + 1, random.choice(vs_list)))
            for pos, char in sorted(insertions, key=lambda x: x[0], reverse=True):
                result.insert(pos, char)
            return ''.join(result)
        return self._apply_to_text_only(text, _apply)
    
    # ══════════════════════════════════════════════
    #  الطبقة 12: Tag Characters مخفية
    # ══════════════════════════════════════════════
    def apply_tag_characters(self, text):
        """إضافة Tag Characters في البداية والنهاية
        هذه أحرف من نطاق Tags (U+E0000+) غير مرئية تماماً
        لا ينظفها معظم أنظمة التنظيف لأنها ليست في نطاق Zero-Width
        """
        tag_chars = ''.join(chr(0xE0000 + ord(c)) for c in random.choice(['AG', 'BK', 'CF', 'DX']))
        text = tag_chars + text
        return text
    
    # ══════════════════════════════════════════════
    #  🛡️ الدالة الرئيسية: تجاوز شامل لبوتات الحماية
    # ══════════════════════════════════════════════
    def bypass(self, text, group_id=None):
        """تطبيق كل طبقات التجاوز على الرسالة
        
        يُرجع: (النص المعالج, use_html)
        - use_html = True إذا تم إخفاء الروابط في HTML entities
        - use_html = False إذا لم تكن هناك روابط
        
        الاستراتيجية:
        1. إخفاء الروابط أولاً في HTML TextUrl (الطبقة الأهم)
        2. تشويش الكلمات المفتاحية العربية
        3. تطبيق Kashida + NFD + Homoglyphs على النص العربي
        4. تطبيق Fullwidth/Latin Extended على النص اللاتيني
        5. أحرف غير مرئية + مسافات بديلة
        6. Variation Selectors + Tag Characters
        7. تحويل أرقام آمن
        """
        if not text or len(text) < 2:
            return text, False
        
        # التحقق من تفعيل النظام
        if get_setting('anti_guardian_enabled', 'on') != 'on':
            return text, False
        
        # تحديد كثافة التشويش حسب الوضع
        ag_mode = get_setting('anti_guardian_mode', 'smart')
        if ag_mode == 'stealth':
            # وضع خفي: تشويش خفيف جداً - للبوتات البسيطة
            kashida_int = 0.15
            nfd_int = 0.2
            homoglyph_int = 0.1
            fullwidth_int = 0.25
            latin_ext_int = 0.2
            invisible_int = 0.08
            space_int = 0.2
            digit_int = 0.15
            vs_int = 0.03
        elif ag_mode == 'aggressive':
            # وضع عدواني: تشويش قوي - للبوتات المتقدمة
            kashida_int = 0.4
            nfd_int = 0.45
            homoglyph_int = 0.35
            fullwidth_int = 0.6
            latin_ext_int = 0.5
            invisible_int = 0.25
            space_int = 0.45
            digit_int = 0.4
            vs_int = 0.1
        else:
            # وضع ذكي (الافتراضي): توازن بين المقروئية والتشويش
            kashida_int = 0.25
            nfd_int = 0.3
            homoglyph_int = 0.2
            fullwidth_int = 0.4
            latin_ext_int = 0.3
            invisible_int = 0.15
            space_int = 0.3
            digit_int = 0.25
            vs_int = 0.06
        
        # ═══ الخطوة 1: إخفاء الروابط في HTML ═══
        text, has_html_links = self.hide_links_in_html(text)
        
        # ═══ الخطوة 2: تشويش الكلمات المفتاحية العربية ═══
        text = self.obfuscate_arabic_keywords(text)
        
        # ═══ الخطوة 3: Kashida عربي (يبقى بعد NFKC!) ═══
        if get_setting('kashida_enabled', 'on') == 'on':
            text = self.apply_kashida(text, intensity=kashida_int)
        
        # ═══ الخطوة 4: NFD Decomposition ═══
        text = self.apply_nfd_decomposition(text, intensity=nfd_int)
        
        # ═══ الخطوة 5: Arabic Homoglyphs ═══
        if get_setting('arabic_homoglyph_enabled', 'on') == 'on':
            text = self.apply_arabic_homoglyphs(text, intensity=homoglyph_int)
        
        # ═══ الخطوة 6: Fullwidth Latin على الأحرف اللاتينية ═══
        if get_setting('fullwidth_latin_enabled', 'on') == 'on':
            text = self.apply_fullwidth_latin(text, intensity=fullwidth_int)
        
        # ═══ الخطوة 7: Latin Extended على الأحرف اللاتينية المتبقية ═══
        if get_setting('latin_extended_enabled', 'on') == 'on':
            text = self.apply_latin_extended(text, intensity=latin_ext_int)
        
        # ═══ الخطوة 8: أحرف غير مرئية استراتيجية ═══
        text = self.apply_strategic_invisibles(text, intensity=invisible_int)
        
        # ═══ الخطوة 9: مسافات بديلة ═══
        text = self.apply_alternate_spaces(text, intensity=space_int)
        
        # ═══ الخطوة 10: تحويل أرقام آمن ═══
        text = self.apply_safe_digit_transform(text, intensity=digit_int)
        
        # ═══ الخطوة 11: Variation Selectors ═══
        if get_setting('variation_selectors_enabled', 'on') == 'on':
            text = self.apply_variation_selectors(text, intensity=vs_int)
        
        # ═══ الخطوة 12: Tag Characters ═══
        if get_setting('tag_characters_enabled', 'on') == 'on':
            text = self.apply_tag_characters(text)
        
        # ═══ حماية البداية والنهاية ═══
        text = random.choice(self.INVISIBLE_CHARS[:4]) + text
        if random.random() < 0.3:
            text = text + random.choice(self.INVISIBLE_CHARS[:4])
        
        # ═══ علامة RTL خفية ═══
        if random.random() < 0.2:
            text = text + '\u200F'
        if random.random() < 0.1:
            text = '\u061C' + text
        
        # ═══ التأكد من عدم التكرار في نفس المجموعة ═══
        if group_id:
            cache_key = f"{group_id}:{hash(text)}"
            if cache_key in self._message_cache:
                # إضافة حرف غير مرئي إضافي لكسر التطابق
                text = random.choice(self.INVISIBLE_CHARS[:4]) + text
            self._message_cache.append(cache_key)
        
        return text, has_html_links


# إنشاء مثيل عام لنظام AntiGuardian
anti_guardian = AntiGuardianBypass()


class YayTextMesslettersObfuscator:
    """
    نظام تشويش وتشفير مدمج خارق من 6 مصادر:
    - fancy-fonts-generator: 27 نمط خط Unicode
    - text_unicoder: تحويلات رونية + يونانية + مقلوبة + أجزاء
    - telegram-fancy-fonts-bot: أنماط Cherokee + CJK + Cyrillic
    - convert-case: Zalgo + يتوسطه خط + مسطر + مقلوب
    - YayText + Messletters: أنماط إضافية
    - تقنيات مخصصة: أحرف غير مرئية + مسافات بديلة + تشويش عربي
    
    إجمالي: 45+ نمط تحويل مختلف
    كل رسالة تحصل على تركيبة عشوائية مختلفة
    يستحيل على بوتات الحماية التعرف على النص
    """

    # ══════════════════════════════════════════════
    #  خريطة الحروف اللاتينية (A-Z, a-z, 0-9)
    #  لكل نمط من أنماط Unicode
    # ══════════════════════════════════════════════
    
    # ─── Mathematical Alphanumeric Symbols (11 نمط) ───
    BOLD_MAP = {}
    ITALIC_MAP = {}
    BOLD_ITALIC_MAP = {}
    MONOSPACE_MAP = {}
    SCRIPT_MAP = {}
    BOLD_SCRIPT_MAP = {}
    FRAKTUR_MAP = {}
    BOLD_FRAKTUR_MAP = {}
    DOUBLE_STRUCK_MAP = {}
    SANS_MAP = {}
    SANS_BOLD_MAP = {}
    SANS_ITALIC_MAP = {}
    SANS_BOLD_ITALIC_MAP = {}
    SANS_MONO_MAP = {}
    
    # ─── أنماط Messletters / Fancy Fonts الإضافية ───
    FULLWIDTH_MAP = {}
    SMALL_CAPS_MAP = {}
    SUPERSCRIPT_MAP = {}
    BUBBLES_MAP = {}
    BUBBLE_BLACK_MAP = {}
    PARENTHESIS_MAP = {}
    SQUARED_MAP = {}
    
    # ─── أنماط Cross-Script (من telegram-fancy-fonts-bot) ───
    RUSSIAN_MAP = {}
    JAPANESE_MAP = {}
    ARABIC_STYLE_MAP = {}  # الآن تستخدم Latin Extended آمنة (بدون Thai/Hebrew)
    FAIRY_MAP = {}
    WIZARD_MAP = {}
    FUNKY_MAP = {}
    
    # ─── أنماط Diacritical (من fancy-fonts-generator) ───
    ACUTE_MAP = {}
    ROCK_DOTS_MAP = {}
    STROKED_MAP = {}
    INVERTED_MAP = {}
    
    # ─── أنماط آمنة جديدة (لا تكتشفها بوتات الحماية) ───
    LATIN_EXTENDED_MAP = {}     # Latin Extended-A/B - تبدو طبيعية تماماً
    ENCLOSED_MAP = {}           # Enclosed Alphanumerics
    MEDIEVAL_MAP = {}           # Latin Extended-D Medieval
    DOUBLE_STRUCK_DIGIT_MAP = {} # أرقام مزدوجة
    
    # ─── جداول أرقام Unicode ───
    DIGIT_BOLD_MAP = {}
    DIGIT_DOUBLE_STRUCK_MAP = {}
    DIGIT_SANS_MAP = {}
    DIGIT_SANS_BOLD_MAP = {}
    DIGIT_MONO_MAP = {}
    DIGIT_FULLWIDTH_MAP = {}
    DIGIT_SUPERSCRIPT_MAP = {}
    DIGIT_BUBBLES_MAP = {}
    DIGIT_INVERTED_MAP = {}
    
    # ─── أنماط آمنة إضافية ضد بوتات الحماية ───
    MEDIEVAL_LATIN_MAP = {}     # Latin Extended-D (أحرف قديمة آمنة)
    PHONETIC_MAP = {}           # IPA Phonetic (آمنة ومتنوعة)
    REGIONAL_MAP = {}           # Regional Indicator Symbols
    
    # ─── خريطة المقلوب (Upside-down) من text_unicoder ───
    UPSIDE_DOWN_MAP = {}
    
    # ─── خريطة اليونانية الصوتية من text_unicoder ───
    GREEK_MAP = {}
    
    # ─── خريطة الرونية من text_unicoder ───
    RUNE_MAP = {}

    def __init__(self):
        self._build_maps()
        self._last_style = -1
        self._build_styles_list()

    def _build_maps(self):
        """بناء كل جداول التحويل"""
        
        # ═══ Mathematical Bold (U+1D400) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.BOLD_MAP[c] = chr(0x1D400 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.BOLD_MAP[c] = chr(0x1D41A + i)
        for i in range(10):
            self.BOLD_MAP[str(i)] = chr(0x1D7CE + i)
            self.DIGIT_BOLD_MAP[str(i)] = chr(0x1D7CE + i)
        
        # ═══ Mathematical Italic (U+1D434) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.ITALIC_MAP[c] = chr(0x1D434 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.ITALIC_MAP[c] = chr(0x1D44E + i)
        self.ITALIC_MAP['h'] = '\u210F'
        
        # ═══ Mathematical Bold Italic (U+1D468) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.BOLD_ITALIC_MAP[c] = chr(0x1D468 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.BOLD_ITALIC_MAP[c] = chr(0x1D482 + i)
        
        # ═══ Mathematical Monospace (U+1D670) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.MONOSPACE_MAP[c] = chr(0x1D670 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.MONOSPACE_MAP[c] = chr(0x1D68A + i)
        for i in range(10):
            self.MONOSPACE_MAP[str(i)] = chr(0x1D7F6 + i)
            self.DIGIT_MONO_MAP[str(i)] = chr(0x1D7F6 + i)
        
        # ═══ Mathematical Script (U+1D49C) ═══
        script_exc = {'B': '\u212C', 'E': '\u2130', 'F': '\u2131',
                      'H': '\u210B', 'I': '\u2110', 'L': '\u2112',
                      'M': '\u2133', 'R': '\u211B'}
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SCRIPT_MAP[c] = script_exc.get(c, chr(0x1D49C + i))
        script_lower_exc = {'e': '\u212F', 'g': '\u210A', 'o': '\u2134'}
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SCRIPT_MAP[c] = script_lower_exc.get(c, chr(0x1D4B6 + i))
        
        # ═══ Mathematical Bold Script (U+1D4D0) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.BOLD_SCRIPT_MAP[c] = chr(0x1D4D0 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.BOLD_SCRIPT_MAP[c] = chr(0x1D4EA + i)
        
        # ═══ Mathematical Fraktur (U+1D504) ═══
        fraktur_exc = {'C': '\u212D', 'H': '\u210C', 'I': '\u2111',
                       'R': '\u211C', 'Z': '\u2128'}
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.FRAKTUR_MAP[c] = fraktur_exc.get(c, chr(0x1D504 + i))
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.FRAKTUR_MAP[c] = chr(0x1D51E + i)
        
        # ═══ Mathematical Bold Fraktur (U+1D56C) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.BOLD_FRAKTUR_MAP[c] = chr(0x1D56C + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.BOLD_FRAKTUR_MAP[c] = chr(0x1D586 + i)
        
        # ═══ Mathematical Double-Struck (U+1D538) ═══
        ds_exc = {'C': '\u2102', 'H': '\u210D', 'N': '\u2115',
                  'P': '\u2119', 'Q': '\u211A', 'R': '\u211D', 'Z': '\u2124'}
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.DOUBLE_STRUCK_MAP[c] = ds_exc.get(c, chr(0x1D538 + i))
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.DOUBLE_STRUCK_MAP[c] = chr(0x1D552 + i)
        ds_digits = {'0': '\U0001D7D8', '1': '\U0001D7D9', '2': '\U0001D7DA',
                     '3': '\U0001D7DB', '4': '\U0001D7DC', '5': '\U0001D7DD',
                     '6': '\U0001D7DE', '7': '\U0001D7DF', '8': '\U0001D7E0',
                     '9': '\U0001D7E1'}
        self.DOUBLE_STRUCK_MAP.update(ds_digits)
        self.DIGIT_DOUBLE_STRUCK_MAP = dict(ds_digits)
        
        # ═══ Mathematical Sans-Serif (U+1D5A0) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SANS_MAP[c] = chr(0x1D5A0 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SANS_MAP[c] = chr(0x1D5BA + i)
        for i in range(10):
            self.SANS_MAP[str(i)] = chr(0x1D7E2 + i)
            self.DIGIT_SANS_MAP[str(i)] = chr(0x1D7E2 + i)
        
        # ═══ Mathematical Sans-Serif Bold (U+1D5D4) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SANS_BOLD_MAP[c] = chr(0x1D5D4 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SANS_BOLD_MAP[c] = chr(0x1D5EE + i)
        for i in range(10):
            self.SANS_BOLD_MAP[str(i)] = chr(0x1D7EC + i)
            self.DIGIT_SANS_BOLD_MAP[str(i)] = chr(0x1D7EC + i)
        
        # ═══ Mathematical Sans-Serif Italic (U+1D608) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SANS_ITALIC_MAP[c] = chr(0x1D608 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SANS_ITALIC_MAP[c] = chr(0x1D622 + i)
        
        # ═══ Mathematical Sans-Serif Bold Italic (U+1D63C) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SANS_BOLD_ITALIC_MAP[c] = chr(0x1D63C + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SANS_BOLD_ITALIC_MAP[c] = chr(0x1D656 + i)
        
        # ═══ Sans-Serif Monospace ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SANS_MONO_MAP[c] = chr(0x1D6A8 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SANS_MONO_MAP[c] = chr(0x1D6C2 + i)
        
        # ═══ Fullwidth (U+FF21) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.FULLWIDTH_MAP[c] = chr(0xFF21 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.FULLWIDTH_MAP[c] = chr(0xFF41 + i)
        for i in range(10):
            self.FULLWIDTH_MAP[str(i)] = chr(0xFF10 + i)
            self.DIGIT_FULLWIDTH_MAP[str(i)] = chr(0xFF10 + i)
        
        # ═══ Small Caps ═══
        self.SMALL_CAPS_MAP = {
            'A': '\u1D00', 'B': '\u0299', 'C': '\u1D04', 'D': '\u1D05',
            'E': '\u1D07', 'F': '\uA730', 'G': '\u0262', 'H': '\u029C',
            'I': '\u026A', 'J': '\u1D0A', 'K': '\u1D0B', 'L': '\u029F',
            'M': '\u1D0D', 'N': '\u0274', 'O': '\u1D0F', 'P': '\u1D18',
            'Q': '\u01EB', 'R': '\u0280', 'S': '\uA731', 'T': '\u1D1B',
            'U': '\u1D1C', 'V': '\u1D20', 'W': '\u1D21', 'X': '\uA78D',
            'Y': '\u028F', 'Z': '\u1D22',
        }
        
        # ═══ Superscript (من fancy-fonts-generator) ═══
        sup_lower = 'ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖqʳˢᵗᵘᵛʷˣʸᶻ'
        sup_upper = 'ᴬᴮᶜᴰᴱᶠᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾQᴿˢᵀᵁⱽᵂˣʸᶻ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SUPERSCRIPT_MAP[c] = sup_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SUPERSCRIPT_MAP[c] = sup_upper[i]
        sup_digits = '⁰¹²³⁴⁵⁶⁷⁸⁹'
        for i in range(10):
            self.SUPERSCRIPT_MAP[str(i)] = sup_digits[i]
            self.DIGIT_SUPERSCRIPT_MAP[str(i)] = sup_digits[i]
        
        # ═══ Bubbles / Circled (U+24D0) ═══
        bub_lower = 'ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ'
        bub_upper = 'ⒶⒷⒸⒹⒺⒻⒼⒽⒾⒿⓀⓁⓂⓃⓄⓅⓆⓇⓈⓉⓊⓋⓌⓍⓎⓏ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.BUBBLES_MAP[c] = bub_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.BUBBLES_MAP[c] = bub_upper[i]
        bub_digits = '⓪①②③④⑤⑥⑦⑧⑨'
        for i in range(10):
            self.BUBBLES_MAP[str(i)] = bub_digits[i]
            self.DIGIT_BUBBLES_MAP[str(i)] = bub_digits[i]
        
        # ═══ Bubble Black / Negative Circled (U+1F150) ═══
        bb_lower = '🅐🅑🅒🅓🅔🅕🅖🅗🅘🅙🅚🅛🅜🅝🅞🅟🅠🅡🅢🅣🅤🅥🅦🅧🅨🅩'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.BUBBLE_BLACK_MAP[c] = bb_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.BUBBLE_BLACK_MAP[c] = bb_lower[i]
        
        # ═══ Parenthesis (U+249C) ═══
        par_lower = '⒜⒝⒞⒟⒠⒡⒢⒣⒤⒥⒦⒧⒨⒩⒪⒫⒬⒭⒮⒯⒰⒱⒲⒳⒴⒵'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.PARENTHESIS_MAP[c] = par_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.PARENTHESIS_MAP[c] = par_lower[i]
        
        # ═══ Squared (U+1F130) ═══
        sq_chars = '🄰🄱🄲🄳🄴🄵🄶🄷🄸🄹🄺🄻🄼🄽🄾🄿🅀🅁🅂🅃🅄🅅🅆🅇🅈🅉'
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SQUARED_MAP[c] = sq_chars[i]
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SQUARED_MAP[c] = sq_chars[i]
        
        # ═══ Cross-Script: Russian (Cyrillic lookalikes) ═══
        rus_lower = 'абcдёfgнїjкгѫпѳpфя$тцѵщжчз'
        rus_upper = 'АБCДЄFGHЇJКГѪЙѲPФЯ$TЦѴШЖЧЗ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.RUSSIAN_MAP[c] = rus_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.RUSSIAN_MAP[c] = rus_upper[i]
        
        # ═══ Cross-Script: Japanese (CJK lookalikes) ═══
        jap_chars = '卂乃匚ᗪ乇千Ꮆ卄丨ﾌҜㄥ爪几ㄖ卩Ɋ尺丂ㄒㄩᐯ山乂ㄚ乙'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.JAPANESE_MAP[c] = jap_chars[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.JAPANESE_MAP[c] = jap_chars[i]
        
        # ═══ Cross-Script: Safe Mixed (Latin Extended + IPA + Latin Extended-B) ═══
        # أنماط آمنة لا تكتشفها بوتات الحماية - بدون Thai/Hebrew/Persian
        safe_mixed_lower = 'ąƀčđḗᵮḡḩḭɉꝁḹḿƞǿᵽɋřşŧṵṽẇẋẏž'
        safe_mixed_upper = 'ȺɃȻĐḔᵮḠḨḬɈꝀḺḾȠǾṔɊŘŞŦṲṼẄẌỲŽ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.ARABIC_STYLE_MAP[c] = safe_mixed_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.ARABIC_STYLE_MAP[c] = safe_mixed_upper[i]
        
        # ═══ Cross-Script: Fairy (Cherokee) ═══
        fairy_chars = 'ᏗᏰፈᎴᏋᎦᎶᏂᎥᏠᏦᏝᎷᏁᎧᎮᎤᏒᏕᏖᏬᏉᏇጀᎩፚ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.FAIRY_MAP[c] = fairy_chars[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.FAIRY_MAP[c] = fairy_chars[i]
        
        # ═══ Cross-Script: Wizard (IPA/Armenian) ═══
        wiz_chars = 'ǟɮƈɖɛʄɢɦɨʝӄʟʍռօքզʀֆȶʊʋաӼʏʐ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.WIZARD_MAP[c] = wiz_chars[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.WIZARD_MAP[c] = wiz_chars[i]
        
        # ═══ Cross-Script: Funky (Greek mix) ═══
        funk_chars = 'αв¢∂єƒgнιנкℓмησρqяѕтυνωχуz'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.FUNKY_MAP[c] = funk_chars[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.FUNKY_MAP[c] = funk_chars[i]
        
        # ═══ Diacritical: Acute ═══
        acute_lower = 'ábćdéfǵhíjḱĺḿńőṕqŕśtúvẃxӳź'
        acute_upper = 'ÁBĆDÉFǴHÍJḰĹḾŃŐṔQŔŚTŰVẂXӲŹ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.ACUTE_MAP[c] = acute_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.ACUTE_MAP[c] = acute_upper[i]
        
        # ═══ Diacritical: RockDots (Umlaut) ═══
        rock_lower = 'äḅċḋëḟġḧïjḳḷṁṅöṗqṛṡẗüṿẅẍÿż'
        rock_upper = 'ÄḄĊḊËḞĠḦÏJḲḶṀṄÖṖQṚṠṪÜṾẄẌŸŻ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.ROCK_DOTS_MAP[c] = rock_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.ROCK_DOTS_MAP[c] = rock_upper[i]
        
        # ═══ Diacritical: Stroked (Barred) ═══
        stroke_lower = 'Ⱥƀȼđɇfǥħɨɉꝁłmnøᵽꝗɍsŧᵾvwxɏƶ'
        stroke_upper = 'ȺɃȻĐɆFǤĦƗɈꝀŁMNØⱣꝖɌSŦᵾVWXɎƵ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.STROKED_MAP[c] = stroke_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.STROKED_MAP[c] = stroke_upper[i]
        
        # ═══ Inverted / Upside-down ═══
        inv_lower = 'ɐqɔpǝɟƃɥıɾʞןɯuodbɹsʇnʌʍxʎz'
        inv_upper = '∀ᗺƆᗡƎℲ⅁HIſꓘ˥WNOԀტᴚS⊥∩ΛMX⅄Z'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.INVERTED_MAP[c] = inv_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.INVERTED_MAP[c] = inv_upper[i]
        inv_digits = '0ƖᘔƐ߈95ㄥ86'
        for i in range(10):
            self.INVERTED_MAP[str(i)] = inv_digits[i]
            self.DIGIT_INVERTED_MAP[str(i)] = inv_digits[i]
        
        # ═══ Homoglyphs (Cyrillic/Greek مشابهة) ═══
        self.HOMOGLYPH_MAP = {
            'a': '\u0430', 'A': '\u0410', 'c': '\u0441', 'C': '\u0421',
            'e': '\u0435', 'E': '\u0415', 'o': '\u043E', 'O': '\u041E',
            'p': '\u0440', 'P': '\u0420', 'x': '\u0445', 'X': '\u0425',
            'y': '\u0443', 'Y': '\u0423', 'i': '\u0456', 'I': '\u0406',
            'j': '\u0458', 'J': '\u0408', 's': '\u0455', 'S': '\u0405',
            'k': '\u043A', 'K': '\u041A', 'H': '\u041D', 'T': '\u0422',
            'M': '\u041C', 'B': '\u0412', 'g': '\u0493', 'G': '\u0492',
            'h': '\u04BB', 'b': '\u0431', 'd': '\u0501', 'u': '\u04AF',
        }
        
        # ═══ Upside-down map (من text_unicoder) ═══
        self.UPSIDE_DOWN_MAP = {
            'a': 'ɐ', 'b': 'q', 'c': 'ɔ', 'd': 'p', 'e': 'ǝ',
            'f': 'ɟ', 'g': 'ᵷ', 'h': 'ɥ', 'i': 'ᴉ', 'j': 'ɾ',
            'k': 'ʞ', 'm': 'ɯ', 'n': 'u', 'r': 'ɹ', 't': 'ʇ',
            'v': 'ʌ', 'w': 'ʍ', 'y': 'ʎ', '.': '˙', ',': 'ʻ',
            '!': '¡', '?': '¿', '&': '⅋', 'A': '∀', 'C': 'Ɔ',
            'E': 'Ǝ', 'F': 'Ⅎ', 'G': '⅍', 'J': 'ſ', 'L': '⅂',
            'M': 'Ɯ', 'P': 'd', 'R': 'ᴚ', 'T': 'ꚱ', 'U': '∩',
            'V': 'Λ', 'W': 'M', 'Y': '⅄', '1': 'ↂ', '3': 'Ɛ',
        }
        
        # ═══ Greek phonemic map (من text_unicoder) ═══
        self.GREEK_MAP = {
            'a': 'α', 'A': 'Α', 'b': 'β', 'B': 'Β', 'g': 'γ', 'G': 'Γ',
            'd': 'δ', 'D': 'Δ', 'e': 'ε', 'E': 'Ε', 'z': 'ζ', 'Z': 'Ζ',
            'h': 'η', 'H': 'Η', 's': 'σ', 'S': 'Σ', 't': 'τ', 'T': 'Τ',
            'y': 'υ', 'Y': 'Υ', 'f': 'φ', 'F': 'Φ', 'c': 'χ', 'C': 'Χ',
            'w': 'ψ', 'W': 'Ψ', 'u': 'ω', 'U': 'Ω', 'i': 'ι', 'I': 'Ι',
            'k': 'κ', 'K': 'Κ', 'l': 'λ', 'L': 'Λ', 'm': 'μ', 'M': 'Μ',
            'n': 'ν', 'N': 'Ν', 'o': 'ο', 'O': 'Ο', 'p': 'π', 'P': 'Π',
            'r': 'ρ', 'R': 'Ρ', 'q': 'κ', 'Q': 'Κ', 'j': 'ι', 'J': 'Ι',
            'v': '∇', 'x': 'χ', 'X': 'Χ',
        }
        
        # ═══ Rune map (Elder Futhark من text_unicoder) ═══
        self.RUNE_MAP = {
            'a': 'ᚨ', 'A': 'ᚨ', 'b': 'ᛒ', 'B': 'ᛒ', 'c': 'ᚲ', 'C': 'ᚲ',
            'd': 'ᛞ', 'D': 'ᛞ', 'e': 'ᛖ', 'E': 'ᛖ', 'f': 'ᚠ', 'F': 'ᚠ',
            'g': 'ᚷ', 'G': 'ᚷ', 'h': 'ᚺ', 'H': 'ᚺ', 'i': 'ᛁ', 'I': 'ᛁ',
            'j': 'ᛃ', 'J': 'ᛃ', 'k': 'ᚲ', 'K': 'ᚲ', 'l': 'ᛚ', 'L': 'ᛚ',
            'm': 'ᛗ', 'M': 'ᛗ', 'n': 'ᚾ', 'N': 'ᚾ', 'o': 'ᛟ', 'O': 'ᛟ',
            'p': 'ᛈ', 'P': 'ᛈ', 'q': 'ᚲ', 'r': 'ᚱ', 'R': 'ᚱ',
            's': 'ᛊ', 'S': 'ᛊ', 't': 'ᛏ', 'T': 'ᛏ', 'u': 'ᚢ', 'U': 'ᚢ',
            'v': 'ᚹ', 'V': 'ᚹ', 'w': 'ᚹ', 'W': 'ᚹ', 'x': 'ᚲᛊ', 'X': 'ᚲᛊ',
            'y': 'ᛁ', 'Y': 'ᛁ', 'z': 'ᛉ', 'Z': 'ᛉ',
        }
        
        # ═══ Latin Extended-A/B (آمنة تماماً - تبدو لاتينية عادية) ═══
        # هذه الأحرف من نطاق Latin Extended ولا تراقبها أي بوت حماية
        ext_lower = 'āƀčḋēḟḡħīĵķĺṁņōṗɋŗşţūṽẁẋȳż'
        ext_upper = 'ĀɃČḊĒḞḠĦĪĴĶĹṀŅŌṖɊŖŞŢŪṼẀẊȲŻ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.LATIN_EXTENDED_MAP[c] = ext_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.LATIN_EXTENDED_MAP[c] = ext_upper[i]
        for i in range(10):
            self.LATIN_EXTENDED_MAP[str(i)] = chr(0xFF10 + i)
        
        # ═══ Enclosed Alphanumerics (U+2460) ═══
        enc_digits = '⓪①②③④⑤⑥⑦⑧⑨'
        enc_upper = 'ⒶⒷⒸⒹⒺⒻⒼⒽⒾⒿⓀⓁⓂⓃⓄⓅⓆⓇⓈⓉⓊⓋⓌⓍⓎⓏ'
        enc_lower = 'ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ'
        for i in range(10):
            self.ENCLOSED_MAP[str(i)] = enc_digits[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.ENCLOSED_MAP[c] = enc_upper[i]
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.ENCLOSED_MAP[c] = enc_lower[i]
        
        # ═══ Medieval Latin (Latin Extended-D) - آمن ومتنوع ═══
        med_lower = 'ꜳƀꜵꜷꜹꜻꜽꜿꝁꝃꝅꝇꝉꝋꝍꝏꝑꝓꝕꝗꝙꝛꝝꝟꝡꝣ'
        med_upper = 'ꜲɃꜴꜶꜸꜺꜼꜾꝀꝂꝄꝆꝈꝊꝌꝎꝐꝒꝔꝖꝘꝚꝜꝞꝠꝢ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.MEDIEVAL_MAP[c] = med_lower[i] if i < len(med_lower) else c
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.MEDIEVAL_MAP[c] = med_upper[i] if i < len(med_upper) else c
        
        # ═══ Latin Extended-B/C/D Mixed (آمن تماماً - بناء برمجي) ═══
        ml_lower_codes = [0x2C7F, 0x0180, 0x0292, 0x0256, 0x0117, 0x0192, 0x0260, 0x0127, 0x026A, 0x0135, 0x0137, 0x013A, 0x1E3F, 0x0144, 0x01A1, 0x1E57, 0x02A0, 0x0159, 0x015F, 0x0163, 0x01B4, 0x1E7D, 0x1E8B, 0x028F, 0x1E91, 0x017C]
        ml_upper_codes = [0x2C7E, 0x0243, 0x0186, 0x018A, 0x0116, 0x0191, 0x0193, 0x0126, 0x0197, 0x0134, 0x0136, 0x0139, 0x1E3E, 0x0143, 0x01A0, 0x1E56, 0x02A0, 0x0158, 0x015E, 0x0162, 0x01B3, 0x1E7C, 0x1E8A, 0x028E, 0x1E90, 0x017B]
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.MEDIEVAL_LATIN_MAP[c] = chr(ml_lower_codes[i])
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.MEDIEVAL_LATIN_MAP[c] = chr(ml_upper_codes[i])
        
        # ═══ IPA Phonetic (مناطق آمنة بالكامل) ═══
        phon_lower = 'ɐʙɔɖɛƒɢɥɪʝʞʟɱɲɵɸʔɾʃʇʊvʍχʎʑ'
        phon_upper = 'ⱯƁƆƊƐƑƓĦƗɈĶⱠⱮƝØƤɊɌƧƮɄɅⱲӾɎƵ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.PHONETIC_MAP[c] = phon_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.PHONETIC_MAP[c] = phon_upper[i]
        
        # ═══ Regional Indicator Symbols (🇦🇧🇨...) ═══
        # كل حرف = حرفين Regional Indicator - تبدو كأحرف علم
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.REGIONAL_MAP[c] = chr(0x1F1E6 + i) + chr(0x1F1E6 + (i + 5) % 26)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.REGIONAL_MAP[c] = chr(0x1F1E6 + i) + chr(0x1F1E6 + (i + 5) % 26)
        
        # ═══ Arabic Smart Obfuscation Maps (NFD Decomposition) ═══
        # تحويل النماذج المركبة إلى مفككة - يبدو متطابقاً مرئياً لكن الكود مختلف
        # هذه التقنية أقوى من الأحرف غير المرئية لأنها تغير كود الحرف نفسه
        self.ARABIC_DECOMPOSE_MAP = {
            'أ': ('ا', '\u0654'),  # ALEF HAMZA ABOVE → ALEF + HAMZA ABOVE combining
            'إ': ('ا', '\u0655'),  # ALEF HAMZA BELOW → ALEF + HAMZA BELOW combining
            'آ': ('ا', '\u0653'),  # ALEF MADDA ABOVE → ALEF + MADDA ABOVE combining
            'ؤ': ('و', '\u0654'),  # WAW HAMZA → WAW + HAMZA ABOVE combining
            'ئ': ('ي', '\u0654'),  # YEH HAMZA → YEH + HAMZA ABOVE combining
        }
        
        # Arabic-Indic digits (تبدو نفس الأرقام لكن بكود مختلف)
        self.ARABIC_DIGIT_MAP = {
            '0': '\u0660', '1': '\u0661', '2': '\u0662', '3': '\u0663', '4': '\u0664',
            '5': '\u0665', '6': '\u0666', '7': '\u0667', '8': '\u0668', '9': '\u0669',
        }
        
        # Extended Arabic digits (أرقام أردية - آمنة ومختلفة)
        self.ARABIC_EXTENDED_DIGIT_MAP = {
            '0': '\u06F0', '1': '\u06F1', '2': '\u06F2', '3': '\u06F3', '4': '\u06F4',
            '5': '\u06F5', '6': '\u06F6', '7': '\u06F7', '8': '\u06F8', '9': '\u06F9',
        }
        
        # 🆕 Arabic Homoglyphs - بدائل مرئية متطابقة (أقوى تقنية عربية)
        self.ARABIC_HOMOGLYPHS = {
            'ا': ['أ', 'إ', 'آ', 'ٱ'],  # ألف بمختلف أشكالها
            'ه': ['ة', 'ھ'],              # هاء / تاء مربوطة
            'ي': ['ى', 'ئ'],              # ياء بمختلف أشكالها
            'و': ['ؤ'],                    # واو / واو بهمزة
            'ل': ['ﻻ', 'ﻼ'],              # لام ألف
            'ك': ['ک', 'ك'],              # كاف فارسية/عربية
            'ن': ['ں'],                    # نون غنية
            'ب': ['ٻ'],                    # باء بنقطة أسفل
        }
        
        # 🆕 Kashida positions - أحرف تقبل الكشيدة (Tatweel U+0640)
        # الكشيدة أقوى طبقة لأنها تبقى بعد كل أنواع التطبيع
        self.KASHIDA_ACCEPTING = 'بتثجحخدذرزسشصضطظعغفقكلمنهي'
        
        # 🆕 Variation Selectors (VS1-VS16: U+FE00-U+FE0F)
        # أحرف تجميع غير مرئية تبقى بعد التطبيع
        self.VARIATION_SELECTORS = [chr(0xFE00 + i) for i in range(16)]
        
        # 🆕 Arabic Presentation Forms-B (PFB)
        # تحويل الحرف العربي لكود مختلف بنفس الشكل المرئي
        self.ARABIC_PFB_MAP = {
            'ا': '\uFE8D', 'ب': '\uFE90', 'ت': '\uFE96', 'ث': '\uFE9A',
            'ج': '\uFE9E', 'ح': '\uFEA2', 'خ': '\uFEA6', 'د': '\uFEAA',
            'ذ': '\uFEAC', 'ر': '\uFEAE', 'ز': '\uFEB0', 'س': '\uFEB4',
            'ش': '\uFEB8', 'ص': '\uFEBC', 'ض': '\uFEC0', 'ط': '\uFEC4',
            'ظ': '\uFEC8', 'ع': '\uFECC', 'غ': '\uFED0', 'ف': '\uFED4',
            'ق': '\uFED8', 'ك': '\uFEDC', 'ل': '\uFEE0', 'م': '\uFEE4',
            'ن': '\uFEE8', 'ه': '\uFEEC', 'و': '\uFEF0', 'ي': '\uFEF2',
        }

    def _build_styles_list(self):
        """بناء قائمة كل الأنماط المتاحة (50+ نمط)"""
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
            ('bubbles', self.BUBBLES_MAP),
            ('bubble_black', self.BUBBLE_BLACK_MAP),
            ('parenthesis', self.PARENTHESIS_MAP),
            ('squared', self.SQUARED_MAP),
            ('superscript', self.SUPERSCRIPT_MAP),
            ('fullwidth', self.FULLWIDTH_MAP),
            ('russian', self.RUSSIAN_MAP),
            ('japanese', self.JAPANESE_MAP),
            ('arabic_style', self.ARABIC_STYLE_MAP),  # الآن آمنة - Latin Extended
            ('fairy', self.FAIRY_MAP),
            ('wizard', self.WIZARD_MAP),
            ('funky', self.FUNKY_MAP),
            ('acute', self.ACUTE_MAP),
            ('rock_dots', self.ROCK_DOTS_MAP),
            ('stroked', self.STROKED_MAP),
            ('small_caps', self.SMALL_CAPS_MAP),
            ('sans_italic', self.SANS_ITALIC_MAP),
            ('sans_bold_italic', self.SANS_BOLD_ITALIC_MAP),
            ('sans_mono', self.SANS_MONO_MAP),
            # ─── أنماط آمنة جديدة (لا تكتشفها بوتات الحماية) ───
            ('latin_extended', self.LATIN_EXTENDED_MAP),
            ('enclosed', self.ENCLOSED_MAP),
            ('medieval', self.MEDIEVAL_MAP),
            ('medieval_latin', self.MEDIEVAL_LATIN_MAP),
            ('phonetic', self.PHONETIC_MAP),
            ('regional', self.REGIONAL_MAP),
        ]
        # Special: -1 strikethrough, -2 underline, -3 inverted
        # -4 zalgo, -5 homoglyphs, -6 greek, -7 rune, -8 upside_down, -9 random_combo

    def _apply_map(self, text, char_map):
        result = []
        for c in text:
            result.append(char_map[c] if c in char_map else c)
        return ''.join(result)

    def _apply_map_preserve_digits(self, text, char_map):
        result = []
        for c in text:
            if c.isdigit():
                result.append(c)
            elif c in char_map:
                result.append(char_map[c])
            else:
                result.append(c)
        return ''.join(result)

    def _apply_arabic_smart_obfuscation(self, text, intensity=0.35):
        """تطبيق تشويش عربي خارق - 12 طبقة دفاعية متقدمة
        
        الطبقات (مرتبة من الأقوى للأخف):
        1. Arabic Homoglyphs - بدائل مرئية متطابقة (أقوى تقنية عربية 2026)
        2. كشيدة/Tatweel (U+0640) - تبقى بعد كل أنواع التطبيع NFKC/NFD
        3. PFB (Arabic Presentation Forms-B) - نفس الشكل، كود مختلف
        4. NFD Decomposition - تحويل المركب لمفكك
        5. Variation Selectors (VS1-VS16) - أحرف تجميع غير مرئية
        6. Tag Characters (U+E0000+) - ترميز مخفي كامل
        7. Arabic-Indic digits - أرقام بنفس الشكل
        8. أحرف غير مرئية استراتيجية
        9. مسافات بديلة متنوعة
        10. RTLO trick - تشويش اتجاه القراءة
        11. علامات RTL/ALM خفية
        12. حماية البداية والنهاية
        """
        if not text:
            return text
        
        # ═══ 1. Arabic Homoglyphs - أقوى طبقة عربية 🆕 ═══
        if get_setting('arabic_homoglyph_enabled', 'on') == 'on':
            result = list(text)
            for i, c in enumerate(result):
                if c in self.ARABIC_HOMOGLYPHS and random.random() < 0.25:
                    result[i] = random.choice(self.ARABIC_HOMOGLYPHS[c])
            text = ''.join(result)
        
        # ═══ 2. كشيدة/Tatweel - أقوى طبقة ثابتة (تبقى بعد NFKC!) 🆕 ═══
        if get_setting('kashida_enabled', 'on') == 'on':
            kashida_intensity = float(get_setting('kashida_intensity', '0.3'))
            result = list(text)
            insertions = []
            for i, c in enumerate(result):
                if c in self.KASHIDA_ACCEPTING and random.random() < kashida_intensity:
                    # إضافة 1-2 كشيدة (Tatweel U+0640)
                    num_kashida = 1 if random.random() < 0.7 else 2
                    insertions.append((i + 1, '\u0640' * num_kashida))
            for pos, chars in sorted(insertions, key=lambda x: x[0], reverse=True):
                result.insert(pos, chars)
            text = ''.join(result)
        
        # ═══ 3. PFB (Arabic Presentation Forms-B) 🆕 ═══
        result = list(text)
        for i, c in enumerate(result):
            if c in self.ARABIC_PFB_MAP and random.random() < 0.2:
                result[i] = self.ARABIC_PFB_MAP[c]
        text = ''.join(result)
        
        # ═══ 4. NFD Decomposition - يبدو متطابقاً لكن الكود مختلف ═══
        result = []
        for c in text:
            if c in self.ARABIC_DECOMPOSE_MAP and random.random() < intensity:
                base, combining = self.ARABIC_DECOMPOSE_MAP[c]
                result.append(base)
                result.append(combining)
            else:
                result.append(c)
        text = ''.join(result)
        
        # ═══ 5. Variation Selectors (VS1-VS16) 🆕 ═══
        if get_setting('variation_selectors_enabled', 'on') == 'on':
            result = list(text)
            insertions = []
            for i, c in enumerate(result):
                if '\u0600' <= c <= '\u06FF' and random.random() < 0.08:
                    insertions.append((i + 1, random.choice(self.VARIATION_SELECTORS)))
            for pos, char in sorted(insertions, key=lambda x: x[0], reverse=True):
                result.insert(pos, char)
            text = ''.join(result)
        
        # ═══ 6. Tag Characters (U+E0000+) - ترميز مخفي 🆕 ═══
        if get_setting('tag_characters_enabled', 'on') == 'on':
            # إضافة أحرف Tag غير مرئية في البداية
            tag_prefix = ''.join(chr(0xE0000 + ord(c)) for c in 'TG')
            tag_suffix = ''.join(chr(0xE0000 + ord(c)) for c in random.choice(['AB','CD','EF','GH']))
            text = tag_prefix + text + tag_suffix
        
        # ═══ 7. Arabic-Indic digits (أرقام مفردة فقط وليس أرقام هواتف) ═══
        result = list(text)
        prev_was_digit = False
        for i, c in enumerate(result):
            if c.isdigit() and c in self.ARABIC_DIGIT_MAP:
                if prev_was_digit:
                    prev_was_digit = True
                    continue
                if random.random() < 0.25:
                    digit_map = random.choice([self.ARABIC_DIGIT_MAP, self.ARABIC_EXTENDED_DIGIT_MAP])
                    result[i] = digit_map[c]
                prev_was_digit = True
            else:
                prev_was_digit = False
        text = ''.join(result)
        
        # ═══ 8. أحرف غير مرئية احترافية (متعددة الأنواع) ═══
        inv_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF', '\u2060', '\u061C']
        
        # حرف غير مرئي في البداية
        text = random.choice(inv_chars[:4]) + text
        
        # أحرف غير مرئية بين الكلمات العربية
        words = text.split(' ')
        new_words = []
        for i, w in enumerate(words):
            new_words.append(w)
            if i < len(words) - 1 and random.random() < 0.2:
                new_words.append(random.choice(inv_chars[:4]))
        text = ' '.join(new_words)
        
        # أحرف غير مرئية بعد علامات الترقيم العربية
        arabic_punct = '،.؛:!؟-'
        result = list(text)
        insert_positions = []
        for i, c in enumerate(result):
            if c in arabic_punct and random.random() < 0.25:
                insert_positions.append((i + 1, random.choice(inv_chars[:4])))
        for pos, char in sorted(insert_positions, key=lambda x: x[0], reverse=True):
            result.insert(pos, char)
        text = ''.join(result)
        
        # ═══ 9. مسافات بديلة متنوعة ═══
        alt_spaces = ['\u00A0', '\u2009', '\u202F', '\u2007', '\u2006', '\u2005']
        result = list(text)
        for i, c in enumerate(result):
            if c == ' ' and random.random() < 0.3:
                result[i] = random.choice(alt_spaces)
        text = ''.join(result)
        
        # ═══ 10. RTLO trick - تشويش اتجاه القراءة 🆕 ═══
        if get_setting('rtlo_enabled', 'off') == 'on':
            words = text.split(' ')
            if len(words) > 3:
                new_words = []
                for i, w in enumerate(words):
                    new_words.append(w)
                    if i < len(words) - 1 and random.random() < 0.05:
                        new_words.append('\u202E')  # RTLO
                        new_words.append('\u202D')  # LTR override (استعادة)
                text = ' '.join(new_words)
        
        # ═══ 11. علامات RTL/ALM خفية ═══
        if random.random() < 0.2:
            text = text + '\u200F'  # RTL Mark
        if random.random() < 0.1:
            text = '\u061C' + text  # Arabic Letter Mark at start
        
        # ═══ 12. حماية البداية والنهاية ═══
        text = random.choice(inv_chars[:4]) + text + random.choice(inv_chars[:4])
        
        return text

    def _apply_strikethrough(self, text):
        result = []
        for c in text:
            if c.isalpha():
                result.append(c + '\u0336')
            else:
                result.append(c)
        return ''.join(result)

    def _apply_underline(self, text):
        result = []
        for c in text:
            if c.isalpha():
                result.append(c + '\u0332')
            else:
                result.append(c)
        return ''.join(result)

    def _apply_zalgo(self, text, intensity=3):
        combining_above = list(range(0x0300, 0x0315))
        combining_below = list(range(0x0316, 0x0333))
        all_combining = combining_above + combining_below
        result = []
        for c in text:
            result.append(c)
            if c.isalpha() or c.isdigit():
                num_marks = random.randint(1, intensity)
                for _ in range(num_marks):
                    result.append(chr(random.choice(all_combining)))
        return ''.join(result)

    def _apply_inverted(self, text):
        return self._apply_map(text, self.INVERTED_MAP)

    def _apply_upside_down(self, text):
        result = []
        for c in reversed(text):
            result.append(self.UPSIDE_DOWN_MAP.get(c, c))
        return ''.join(result)

    def _apply_greek(self, text):
        return self._apply_map(text, self.GREEK_MAP)

    def _apply_rune(self, text):
        return self._apply_map(text, self.RUNE_MAP)

    def _apply_homoglyphs(self, text, intensity=0.35):
        result = []
        for c in text:
            if c in self.HOMOGLYPH_MAP and random.random() < intensity:
                result.append(self.HOMOGLYPH_MAP[c])
            else:
                result.append(c)
        return ''.join(result)

    def _apply_random_combo(self, text):
        available = list(range(len(self.STYLES)))
        num_styles = random.randint(2, 3)
        chosen = random.sample(available, min(num_styles, len(available)))
        result = text
        for idx in chosen:
            _, char_map = self.STYLES[idx]
            chars = list(result)
            for i, c in enumerate(chars):
                if c in char_map and random.random() < 0.5:
                    chars[i] = char_map[c]
            result = ''.join(chars)
        return result

    def _escape_html(self, text):
        if not text:
            return text
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        return text

    def _obfuscate_display_text(self, text, style_idx):
        """تشويش نص العرض للروابط - خفيف للحفاظ على المقروئية مع تشويش احترافي"""
        if not text or len(text) < 2:
            return text
        # أحرف غير مرئية احترافية في البداية
        inv_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF', '\u2060', '\u061C']
        result = random.choice(inv_chars[:4]) + text
        if random.random() < 0.3:
            result = random.choice(inv_chars[:4]) + result
        # مسافات بديلة متنوعة
        alt_spaces = ['\u00A0', '\u2009', '\u202F', '\u2007', '\u2006']
        chars = list(result)
        for i, c in enumerate(chars):
            if c == ' ' and random.random() < 0.3:
                chars[i] = random.choice(alt_spaces)
        result = ''.join(chars)
        # NFD decomposition خفيف للعربية (أحرف مركبة → مفككة)
        arabic_decompose = {
            'أ': ('ا', '\u0654'), 'إ': ('ا', '\u0655'),
            'آ': ('ا', '\u0653'), 'ؤ': ('و', '\u0654'),
            'ئ': ('ي', '\u0654'),
        }
        new_chars = []
        for c in result:
            if c in arabic_decompose and random.random() < 0.15:
                base, combining = arabic_decompose[c]
                new_chars.append(base)
                new_chars.append(combining)
            else:
                new_chars.append(c)
        result = ''.join(new_chars)
        # علامة RTL أو ALM خفية
        if random.random() < 0.2:
            result = result + random.choice(['\u200F', '\u061C'])
        return result

    def _create_url_display(self, url, style_idx):
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
        ]
        if 't.me/' in url:
            return random.choice(tme_displays)
        return random.choice(general_displays)

    def _create_mention_display(self, mention, style_idx):
        displays = ['اضغط هنا', 'الملف الشخصي', 'هنا', 'تفضل', 'تابعنا', 'الرابط', 'من هنا', 'تعرف علينا', 'تواصل', 'ادخل', 'الصفحة', 'اضغط']
        return random.choice(displays)

    def _apply_style_to_text(self, text, style_idx):
        """نظام تشويش ذكي محسّن - يحافظ على المقروئية العربية مع تشويش البوتات
        
        الاستراتيجية الجديدة:
        1. النص العربي: تشويش ذكي (NFD + أرقام عربية + أحرف غير مرئية + مسافات بديلة)
           - تحويل NFC→NFD يغير الكود بدون تغيير الشكل المرئي
           - أرقام عربية-هندية بدل اللاتينية
           - أحرف غير مرئية احترافية متعددة الأنواع
        2. الأحرف اللاتينية: تحويل لنمط Unicode مختلف
        3. الأرقام: تحويل لأرقام Unicode مختلفة
        4. الروابط والمعرفات: تُعالج بشكل منفصل في obfuscate()
        """
        if not text:
            return text

        # ═══ تحليل النص: هل هو عربي بالأساس؟ ═══
        arabic_chars = sum(1 for c in text if '\u0600' <= c <= '\u06FF' or '\u0750' <= c <= '\u077F' or '\uFB50' <= c <= '\uFDFF' or '\uFE70' <= c <= '\uFEFF')
        latin_chars = sum(1 for c in text if ('a' <= c <= 'z') or ('A' <= c <= 'Z'))
        total_alpha = arabic_chars + latin_chars
        is_mostly_arabic = total_alpha > 0 and arabic_chars > latin_chars
        
        # ═══ الطبقة 1: تحويل ذكي حسب نوع النص ═══
        if is_mostly_arabic:
            # نص عربي: تشويش ذكي يحافظ على المقروئية تماماً
            transformed = text
            
            # تحويل الأحرف اللاتينية الموجودة في النص العربي
            if latin_chars > 0 and style_idx >= 0:
                _, char_map = self.STYLES[style_idx]
                result = []
                for c in transformed:
                    if c in char_map:
                        result.append(char_map[c])
                    else:
                        result.append(c)
                transformed = ''.join(result)
            
            # تطبيق التشويش العربي الذكي (NFD + أرقام + أحرف غير مرئية)
            transformed = self._apply_arabic_smart_obfuscation(transformed, intensity=0.35)
            
            return transformed
        else:
            # نص لاتيني: تحويل كامل بالنمط المختار
            if style_idx >= 0:
                _, char_map = self.STYLES[style_idx]
                transformed = self._apply_map_preserve_digits(text, char_map)
            elif style_idx == -1:
                transformed = self._apply_strikethrough(text)
            elif style_idx == -2:
                transformed = self._apply_underline(text)
            elif style_idx == -3:
                transformed = self._apply_inverted(text)
            elif style_idx == -4:
                transformed = self._apply_zalgo(text, intensity=2)
            elif style_idx == -5:
                transformed = self._apply_homoglyphs(text, intensity=0.5)
            elif style_idx == -6:
                transformed = self._apply_greek(text)
            elif style_idx == -7:
                transformed = self._apply_rune(text)
            elif style_idx == -8:
                transformed = self._apply_upside_down(text)
            elif style_idx == -9:
                transformed = self._apply_random_combo(text)
            else:
                transformed = text

        # ═══ الطبقة 2: Homoglyphs خفيفة على اللاتينية فقط ═══
        if style_idx not in (-5, -6, -7) and latin_chars > 0:
            transformed = self._apply_homoglyphs_latin_only(transformed, intensity=0.2)

        # ═══ الطبقة 3: أحرف غير مرئية احترافية ═══
        inv_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF', '\u2060', '\u061C']
        
        # حرف غير مرئي في البداية
        transformed = random.choice(inv_chars[:4]) + transformed
        
        # أحرف غير مرئية بين الكلمات
        if len(transformed) > 10:
            words = transformed.split(' ')
            new_words = []
            for i, w in enumerate(words):
                new_words.append(w)
                if i < len(words) - 1 and random.random() < 0.15:
                    new_words.append(random.choice(inv_chars[:4]))
            transformed = ' '.join(new_words)

        # ═══ الطبقة 4: مسافات بديلة + تحويل أرقام (خفيف) ═══
        alt_spaces = ['\u00A0', '\u2009', '\u202F', '\u2007']
        safe_digit_maps = [
            self.DIGIT_SANS_MAP, self.DIGIT_SANS_BOLD_MAP,
            self.DIGIT_MONO_MAP, self.DIGIT_FULLWIDTH_MAP,
        ]
        chosen_digit_map = random.choice([m for m in safe_digit_maps if m])
        result_list = list(transformed)
        prev_was_digit = False
        for i, c in enumerate(result_list):
            if c == ' ' and random.random() < 0.2:
                result_list[i] = random.choice(alt_spaces)
            elif c.isdigit() and c in chosen_digit_map:
                if prev_was_digit:
                    prev_was_digit = True
                    continue
                if random.random() < 0.3:
                    result_list[i] = chosen_digit_map[c]
                prev_was_digit = True
            else:
                prev_was_digit = False
        transformed = ''.join(result_list)

        # ═══ الطبقة 5: أحرف غير مرئية بعد علامات الترقيم ═══
        if len(transformed) > 5:
            punctuation = '،.؛:!؟-.'
            result_list = list(transformed)
            insert_positions = []
            for i, c in enumerate(result_list):
                if c in punctuation and random.random() < 0.2:
                    insert_positions.append((i + 1, random.choice(inv_chars[:4])))
            for pos, char in sorted(insert_positions, key=lambda x: x[0], reverse=True):
                result_list.insert(pos, char)
            transformed = ''.join(result_list)

        # ═══ الطبقة 6: علامة RTL + حرف غير مرئي في النهاية ═══
        if random.random() < 0.15:
            transformed = transformed + '\u200F'
        if random.random() < 0.1:
            transformed = '\u061C' + transformed
        transformed = transformed + random.choice(inv_chars[:4])

        return transformed
    
    def _apply_homoglyphs_latin_only(self, text, intensity=0.2):
        """تطبيق homoglyphs على الأحرف اللاتينية فقط - لا يمس العربية"""
        result = []
        for c in text:
            if ('a' <= c <= 'z') or ('A' <= c <= 'Z'):
                if c in self.HOMOGLYPH_MAP and random.random() < intensity:
                    result.append(self.HOMOGLYPH_MAP[c])
                else:
                    result.append(c)
            else:
                result.append(c)
        return ''.join(result)

    def _get_random_style(self):
        available = list(range(len(self.STYLES)))
        if self._last_style in available and len(available) > 1:
            available.remove(self._last_style)
        available.extend([-1, -2, -3, -4, -5, -6, -7, -8, -9])
        chosen = random.choice(available)
        self._last_style = chosen
        return chosen

    def _extract_protected_segments(self, text):
        protected = []
        for match in re.finditer(r'https?://\S+', text):
            url = match.group().rstrip('\u200B\u200C\u200D\uFEFF\u2060\u2061\u2062\u2063\u00A0\u2009\u202F')
            end_pos = match.start() + len(url)
            protected.append((match.start(), end_pos, url, 'url'))
        for match in re.finditer(r'(?<![a-zA-Z0-9/:.])t\.me/[a-zA-Z0-9_]+', text):
            overlaps = any(match.start() >= p[0] and match.start() < p[1] for p in protected)
            if not overlaps:
                full_url = 'https://' + match.group()
                protected.append((match.start(), match.end(), full_url, 'url'))
        for match in re.finditer(r'@[a-zA-Z0-9_]{3,}', text):
            overlaps = any(match.start() >= p[0] and match.start() < p[1] for p in protected)
            if not overlaps:
                protected.append((match.start(), match.end(), match.group(), 'mention'))
        protected.sort(key=lambda x: x[0])
        clean = []
        for seg in protected:
            if not clean:
                clean.append(seg)
            elif seg[0] >= clean[-1][1]:
                clean.append(seg)
        return clean

    def obfuscate(self, text):
        """التحويل الرئيسي - 45+ نمط + 12 طبقة تشويش"""
        if not text or len(text) < 2:
            return text, False

        all_protected = self._extract_protected_segments(text)
        has_links = any(seg_type in ('url', 'mention') for _, _, _, seg_type in all_protected)

        segments = []
        last_end = 0
        for start, end, original, seg_type in all_protected:
            if start > last_end:
                segments.append(('text', text[last_end:start]))
            segments.append((seg_type, original))
            last_end = end
        if last_end < len(text):
            segments.append(('text', text[last_end:]))

        style_idx = self._get_random_style()
        result_parts = []

        for seg_type, seg_text in segments:
            if seg_type == 'url':
                display = self._create_url_display(seg_text, style_idx)
                display = self._obfuscate_display_text(display, style_idx)
                display = self._escape_html(display)
                result_parts.append(f'<a href="{seg_text}">{display}</a>')
            elif seg_type == 'mention':
                display = self._create_mention_display(seg_text, style_idx)
                display = self._obfuscate_display_text(display, style_idx)
                display = self._escape_html(display)
                username = seg_text[1:]
                result_parts.append(f'<a href="tg://resolve?domain={username}">{display}</a>')
            else:
                transformed = self._apply_style_to_text(seg_text, style_idx)
                transformed = self._escape_html(transformed)
                result_parts.append(transformed)

        final_text = ''.join(result_parts)
        # أحرف غير مرئية احترافية متعددة الأنواع في البداية
        inv_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF', '\u2060', '\u061C']
        final_text = random.choice(inv_chars[:4]) + final_text
        if random.random() < 0.3:
            final_text = random.choice(inv_chars[:4]) + final_text

        return final_text, has_links

    def get_style_name(self, idx=None):
        special_names = {
            -1: 'strikethrough', -2: 'underline', -3: 'inverted',
            -4: 'zalgo', -5: 'homoglyphs', -6: 'greek',
            -7: 'rune', -8: 'upside_down', -9: 'random_combo',
        }
        if idx is None:
            idx = self._last_style
        if idx >= 0 and idx < len(self.STYLES):
            return self.STYLES[idx][0]
        return special_names.get(idx, 'unknown')


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
    
    # أحرف غير مرئية احترافية متنوعة (متعددة الأنواع)
    INVISIBLE_CHARS = [
        '\u200B',   # Zero-Width Space
        '\u200C',   # Zero-Width Non-Joiner
        '\u200D',   # Zero-Width Joiner
        '\uFEFF',   # BOM / Zero-Width No-Break Space
        '\u2060',   # Word Joiner
        '\u2061',   # Function Application
        '\u2062',   # Invisible Times
        '\u2063',   # Invisible Separator
        '\u2064',   # Invisible Plus
        '\u061C',   # Arabic Letter Mark (invisible)
    ]
    
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
        الطبقة 6: تشويش النمط - إضافة أحرف غير مرئية احترافية لتغيير بصمة النص
        يمنع بوتات الحماية من مطابقة الأنماط المتكررة
        يستخدم أنواعاً متعددة من الأحرف غير المرئية لتعظيم التغيير
        """
        if not text or len(text) < 10:
            return text
        
        protected = self._extract_protected_zones(text)
        result = list(text)
        
        # إضافة 1-3 أحرف غير مرئية في بداية النص
        prefix = random.choice(self.INVISIBLE_CHARS)
        if random.random() < 0.4:
            prefix += random.choice(self.INVISIBLE_CHARS)
        if random.random() < 0.15:
            prefix += random.choice(self.INVISIBLE_CHARS)
        
        # إضافة علامة Arabic Letter Mark أحياناً في البداية
        if random.random() < 0.15:
            prefix = '\u061C' + prefix
        
        # إضافة أحرف غير مرئية بين الجمل (بعد النقاط وعلامات الترقيم)
        for i, c in enumerate(result):
            if c in '.!؟\n،؛' and not self._is_protected_zone(i, protected):
                if random.random() < 0.4:
                    result.insert(i + 1, random.choice(self.INVISIBLE_CHARS[:6]))
        
        # إضافة علامة RTL أو ALM خفية أحياناً
        if random.random() < 0.25:
            result.append(random.choice(['\u200F', '\u061C']))
        
        return prefix + ''.join(result)
    
    def apply_unicode_normalization_trick(self, text, intensity=0.15):
        """
        الطبقة 7: تحويلات Unicode عربية ذكية (بدون أحرف فارسية!)
        - NFD Decomposition: تحويل الأحرف المركبة لمفككة (نفس الشكل، كود مختلف)
        - تحويلات عربية آمنة لا تكتشفها بوتات الحماية
        """
        if not text:
            return text
        
        protected = self._extract_protected_zones(text)
        result = list(text)
        new_result = []
        
        # NFD Decomposition - آمن تماماً ويبدو متطابقاً مرئياً
        arabic_decompose = {
            'أ': ('\u0627', '\u0654'),  # ALEF HAMZA ABOVE → ALEF + combining HAMZA ABOVE
            'إ': ('\u0627', '\u0655'),  # ALEF HAMZA BELOW → ALEF + combining HAMZA BELOW
            'آ': ('\u0627', '\u0653'),  # ALEF MADDA ABOVE → ALEF + combining MADDA ABOVE
            'ؤ': ('\u0648', '\u0654'),  # WAW HAMZA → WAW + combining HAMZA ABOVE
            'ئ': ('\u064A', '\u0654'),  # YEH HAMZA → YEH + combining HAMZA ABOVE
        }
        
        i = 0
        while i < len(result):
            c = result[i]
            if c in arabic_decompose and not self._is_protected_zone(i, protected):
                if random.random() < intensity:
                    base, combining = arabic_decompose[c]
                    new_result.append(base)
                    new_result.append(combining)
                else:
                    new_result.append(c)
            else:
                new_result.append(c)
            i += 1
        
        return ''.join(new_result)
    
    def encode_message(self, text, group_id=None):
        """
        تطبيق كل طبقات التشفير والتكويد على الرسالة
        يُرجع: (النص المشفر, use_html) حيث use_html يحدد استخدام parse_mode='html'
        
        الطبقات محسّنة للحفاظ على مقروئية النص العربي:
        - الطبقة 1+2: تحويل YayText/Messletters (يتضمن NFD عربي ذكي)
        - الطبقة 3: أحرف غير مرئية احترافية (متعددة الأنواع)
        - الطبقة 4: مسافات بديلة متنوعة
        - الطبقة 5: Homoglyphs (لاتينية فقط)
        - الطبقة 6: تشويش النمط
        - الطبقة 7: تحويلات NFD عربية ذكية (بدون فارسية!)
        """
        if not text or len(text) < 2:
            return text, False
        
        # تطبيق YayText/Messletters (الطبقة 1+2)
        # يتضمن الآن تشويش عربي ذكي (NFD decomposition + أرقام عربية)
        obfuscated_text, use_html = yaytext_obfuscator.obfuscate(text)
        
        # الطبقة 3: أحرف غير مرئية احترافية (كثافة أعلى)
        obfuscated_text = self.apply_strategic_invisibles(obfuscated_text, intensity=0.2)
        
        # الطبقة 4: مسافات بديلة متنوعة
        obfuscated_text = self.apply_alternate_spaces(obfuscated_text, intensity=0.35)
        
        # الطبقة 5: Homoglyphs (لاتينية فقط - لا يمس العربية)
        obfuscated_text = self.apply_homoglyphs(obfuscated_text, intensity=0.12)
        
        # الطبقة 6: تشويش النمط
        obfuscated_text = self.apply_pattern_disruption(obfuscated_text)
        
        # الطبقة 7: تحويلات NFD عربية ذكية (بدون أحرف فارسية!)
        obfuscated_text = self.apply_unicode_normalization_trick(obfuscated_text, intensity=0.15)
        
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


# ═══════════════════════════════════════════════════════════════
#  💎 نظام التشفير الخارق - Super Encryption 2026 💎
#  أقوى طبقة تشفير: يكسر كشف بوتات الحماية بالكامل
#  الآلية: حرف + كشيدة + فاصل + كشيدة + حرف
#  النتيجة: نص مقروء بشرياً لكن مستحيل كشفه آلياً
# ═══════════════════════════════════════════════════════════════
class SuperEncryption:
    """
    💎 التشفير الخارق - أقوى نظام تشفير ضد بوتات الحماية
    
    الآلية المستوحاة من تقنيات التشفير المتقدمة:
    كل حرف عربي يُحاط بنمط: حرف + كشيدة(ـ) + فاصل + كشيدة(ـ) + حرف تالي
    
    مثال: "سلام" ← "سـ...ـلـ...ـاـ...ـم"
    
    الفواصل المتاحة:
    - نقاط: ... (ثلاث نقاط)
    - شرطات: ─ (خط أفقي)
    - نجوم: ✦ (نجمة صغيرة)
    - معين: ◆ (معين)
    - دائرة: ● (دائرة)
    - زخرفة: ⟡ (زخرفة)
    
    لماذا يعمل:
    1. بوتات الحماية تبحث عن كلمات كاملة ← الكلمات مكسورة بالفواصل
    2. Regex لا يطابق كلمة مفرقة بأحرف ← الكشيدة والفاصل يكسران النمط
    3. البشر يقرؤون الحروف المتصلة بالكشيدة ← مقروء تماماً
    4. كل رسالة تختلف بالفاصل العشوائي ← لا نمط متكرر
    """
    
    # الفواصل المتاحة (يتم اختيار واحد عشوائياً لكل رسالة)
    SEPARATORS = [
        '...',    # نقاط
        '·',      # نقطة وسط
        '─',      # خط أفقي
        '✦',      # نجمة صغيرة
        '◆',      # معين
        '●',      # دائرة
        '⟡',      # زخرفة
        '⋆',      # نجمة مفتوحة
        '᠎',      # مانجو (حرف منغولي خفي)
        '⁞',      # أربعة خطوط عمودية
        '⸱',      # نقطة كلمة
        '•',      # نقطة سوداء
    ]
    
    # الأحرف العربية التي تقبل الكشيدة (Tatweel)
    KASHIDA_ACCEPTING = set('بتثجحخدذرزسشصضطظعغفقكلمنهي')
    
    # الأحرف العربية التي لا تتصل بما بعدها (لا نضيف كشيدة بعدها)
    # لكننا نضيف الفاصل بعد كل حرف بغض النظر
    
    # الروابط والمعرفات محمية
    URL_PATTERN = re.compile(r'https?://\S+')
    MENTION_PATTERN = re.compile(r'@[a-zA-Z0-9_]{3,}')
    PHONE_PATTERN = re.compile(r'\+?\d[\d\s\-]{7,}')
    
    def _extract_protected_zones(self, text):
        """استخراج مناطق محمية (روابط، معرفات، أرقام هواتف)"""
        zones = []
        for match in self.URL_PATTERN.finditer(text):
            zones.append((match.start(), match.end()))
        for match in self.MENTION_PATTERN.finditer(text):
            if not any(match.start() >= s and match.start() < e for s, e in zones):
                zones.append((match.start(), match.end()))
        for match in self.PHONE_PATTERN.finditer(text):
            if not any(match.start() >= s and match.start() < e for s, e in zones):
                zones.append((match.start(), match.end()))
        return zones
    
    def _is_arabic_letter(self, char):
        """التحقق من أن الحرف عربي"""
        return '\u0600' <= char <= '\u06FF' or '\u0750' <= char <= '\u077F' or '\u08A0' <= char <= '\u08FF' or '\uFB50' <= char <= '\uFDFF' or '\uFE70' <= char <= '\uFEFF'
    
    def _is_ignored_char(self, char):
        """أحرف لا نعالجها (مسافات، علامات ترقيم، تشكيل، أرقام)"""
        if char.isspace():
            return True
        if char in '،.؛:!؟()-[]{}«»""\n\r\t':
            return True
        if '\u064B' <= char <= '\u065F':  # تشكيل عربي
            return True
        if char.isdigit():
            return True
        if char in self.KASHIDA_ACCEPTING:
            return False
        if self._is_arabic_letter(char):
            return False
        return True  # أحرف لاتينية وأخرى
    
    def super_encrypt(self, text, intensity=1.0):
        """
        تطبيق التشفير الخارق على النص
        
        النتيجة: نص عربي مقروء بشرياً لكنه مكسور آلياً
        كل حرف عربي يُفصل عن الذي يليه بـ: كشيدة + فاصل + كشيدة
        
        intensity: كثافة التشفير (1.0 = كل الحروف، 0.5 = نصفها)
        """
        if not text or len(text) < 2:
            return text
        
        protected = self._extract_protected_zones(text)
        
        def _is_protected(pos):
            return any(pos >= s and pos < e for s, e in protected)
        
        # اختيار فاصل عشوائي لهذه الرسالة
        separator = random.choice(self.SEPARATORS)
        
        result = []
        i = 0
        while i < len(text):
            c = text[i]
            
            # حماية الروابط والمعرفات
            if _is_protected(i):
                result.append(c)
                i += 1
                continue
            
            # الأحرف التي لا نعالجها
            if self._is_ignored_char(c):
                result.append(c)
                i += 1
                continue
            
            # الحرف العربي - إضافته
            result.append(c)
            
            # هل نضيف الفاصل بعد هذا الحرف؟
            if random.random() <= intensity:
                # البحث عن الحرف العربي التالي
                next_arabic = None
                for j in range(i + 1, len(text)):
                    if not self._is_ignored_char(text[j]) and not _is_protected(j):
                        if self._is_arabic_letter(text[j]):
                            next_arabic = j
                            break
                        else:
                            break  # حرف لاتيني - لا نضيف فاصل
                    elif text[j].isspace() or text[j] in '،.؛:!؟':
                        break  # نهاية الكلمة - لا فاصل
                
                # إضافة الفاصل فقط إذا كان الحرف التالي عربي في نفس الكلمة
                if next_arabic is not None:
                    # نمط: كشيدة + فاصل + كشيدة
                    if c in self.KASHIDA_ACCEPTING:
                        result.append('\u0640')  # كشيدة قبل الفاصل
                    result.append(separator)
                    # كشيدة بعد الفاصل تُضاف مع الحرف التالي تلقائياً
            
            i += 1
        
        return ''.join(result)
    
    def super_encrypt_full(self, text):
        """
        التشفير الخارق الكامل - يجمع كل الطبقات:
        1. تشفير خارق (فاصل بين الحروف)
        2. أحرف ZWJ غير مرئية
        3. تنويع عشوائي للفاصل
        """
        if not text or len(text) < 2:
            return text
        
        protected = self._extract_protected_zones(text)
        
        def _is_protected(pos):
            return any(pos >= s and pos < e for s, e in protected)
        
        result = []
        separator = random.choice(self.SEPARATORS)
        
        # أحرف ZWJ للتنويع
        zwj_chars = ['\u200D', '\u200C', '\u200B']
        
        i = 0
        while i < len(text):
            c = text[i]
            
            # حماية الروابط والمعرفات
            if _is_protected(i):
                result.append(c)
                i += 1
                continue
            
            # الأحرف التي لا نعالجها
            if self._is_ignored_char(c):
                result.append(c)
                i += 1
                continue
            
            # الحرف العربي
            result.append(c)
            
            # البحث عن الحرف العربي التالي في نفس الكلمة
            next_arabic = None
            for j in range(i + 1, len(text)):
                if _is_protected(j):
                    break
                if text[j].isspace() or text[j] in '،.؛:!؟\n':
                    break
                if self._is_ignored_char(text[j]):
                    continue  # تشكيل أو رقم داخل الكلمة
                if self._is_arabic_letter(text[j]):
                    next_arabic = j
                    break
                else:
                    break  # حرف لاتيني
            
            if next_arabic is not None:
                # إضافة: كشيدة + ZWJ + فاصل + ZWJ + كشيدة
                if c in self.KASHIDA_ACCEPTING:
                    result.append('\u0640')  # كشيدة
                
                # ZWJ عشوائي (50% احتمال)
                if random.random() < 0.5:
                    result.append(random.choice(zwj_chars[:2]))  # ZWJ أو ZWNJ
                
                result.append(separator)
                
                # ZWJ عشوائي بعد الفاصل (50% احتمال)
                if random.random() < 0.5:
                    result.append(random.choice(zwj_chars[:2]))
            
            i += 1
        
        # إضافة أحرف غير مرئية في البداية للتنويع الإضافي
        result.insert(0, random.choice(['\u200B', '\u200C', '\uFEFF', '\u2060']))
        
        return ''.join(result)


# إنشاء مثيل عام لنظام التشفير الخارق
super_encryption = SuperEncryption()


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
#  نظام الانضمام التلقائي المتقدم - Anti-Ban
# ═══════════════════════════════════════════════

def extract_telegram_links(text):
    """استخراج جميع أنواع روابط تيليجرام من النص
    يدعم:
    - https://t.me/channel_name
    - https://t.me/joinchat/XXXXX
    - https://t.me/+XXXXX
    - http://t.me/...
    - @username
    - t.me/channel_name (بدون https)
    - روابط دعوة خاصة طويلة
    - روابط مسبوقة بأرقام أو رموز مثل: 1-https://t.me/... أو *t.me/...
    """
    links = set()
    
    # تنظيف المحارف غير المرئية من النص
    text = re.sub(r'[\u200B\u200C\u200D\uFEFF]+', '', text)
    
    # 1. روابط t.me كاملة (https و http) - البحث المباشر بالأنماط
    pattern_invite = r'https?://t\.me/(?:joinchat/)?\+[a-zA-Z0-9_\-]+'
    pattern_public = r'https?://t\.me/[a-zA-Z][a-zA-Z0-9_]{4,}'
    pattern_joinchat = r'https?://t\.me/joinchat/[a-zA-Z0-9_\-]+'
    
    for p in [pattern_invite, pattern_public, pattern_joinchat]:
        found = re.findall(p, text)
        links.update(found)
    
    # 2. @username (باستخدام word boundary لتجنب الدمج الخاطئ)
    usernames = re.findall(r'@([a-zA-Z][a-zA-Z0-9_]{4,})\b', text)
    for u in usernames:
        links.add(f'https://t.me/{u}')
    
    # 3. البحث عن t.me/ في أي مكان بالنص (حتى لو كان مسبوقاً برموز)
    # هذا يلتقط: t.me/xxx, 1-t.me/xxx, *t.me/xxx, -t.me/xxx إلخ
    tme_pattern = r'(?:^|[\s\-_*•●▶►▷→↳\d\.\)]+)(t\.me/[^\s\-_*•●▶►▷→]+)'
    for match in re.finditer(tme_pattern, text):
        found_part = match.group(1)
        # التأكد من أنها ليست جزءاً من رابط https:// موجود بالفعل
        if not re.search(r'https?://' + re.escape(found_part), text):
            full_link = f'https://{found_part}'
            if re.match(r'https?://t\.me/', full_link):
                path = full_link.split('t.me/')[-1].split('?')[0]
                if path.startswith('+') or path.startswith('joinchat/'):
                    links.add(full_link)
                elif len(path) >= 5 and path[0].isalpha():
                    links.add(full_link)
    
    # 4. فحص كل سطر بشكل مستقل - الطريقة الأكثر دقة
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        # إزالة البادئات الشائعة مثل: 1. 2. 1- 2- * - •
        cleaned_line = re.sub(r'^[\d]+[\.\)\-]+\s*', '', line)
        cleaned_line = re.sub(r'^[\-*•●▶►▷→↳]+\s*', '', cleaned_line)
        
        # فحص كل كلمة في السطر بشكل مستقل
        for word in cleaned_line.split():
            # تنظيف الرموز المحيطة بالكلمة
            word = word.strip('.,;:!؟،؛()[]{}«»""\'"')
            if not word:
                continue
            
            if word.startswith('@'):
                username = word[1:]
                if len(username) >= 5 and username[0].isalpha():
                    links.add(f'https://t.me/{username}')
            elif 't.me/' in word:
                # استخراج جزء t.me/ من الكلمة (حتى لو كانت مسبوقة برموز)
                tme_match = re.search(r'(t\.me/.+)', word)
                if tme_match:
                    tme_part = tme_match.group(1)
                    if not tme_part.startswith('http'):
                        full_link = f'https://{tme_part}'
                    else:
                        full_link = tme_part
                    # التأكد من صحة الرابط
                    if re.match(r'https?://t\.me/', full_link):
                        path = full_link.split('t.me/')[-1].split('?')[0]
                        if path.startswith('+') or path.startswith('joinchat/'):
                            links.add(full_link)
                        elif len(path) >= 5 and path[0].isalpha():
                            links.add(full_link)
    
    # 5. تنظيف الروابط النهائية - إزالة أي محارف متبقية غير مرئية
    final_links = []
    for link in links:
        link = re.sub(r'[\u200B\u200C\u200D\uFEFF]+', '', link)
        link = link.strip()
        if link and 't.me/' in link:
            if not link.startswith('http'):
                link = 'https://' + link
            final_links.append(link)
    
    return list(set(final_links))


def is_already_joined(client, group_id):
    """التحقق مما إذا كان الحساب منضم بالفعل للمجموعة"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT 1 FROM groups WHERE group_id=?', (group_id,))
        result = c.fetchone()
        conn.close()
        return result is not None
    except:
        return False


def get_join_account_usage(acc_id):
    """الحصول على عدد الانضمامات الأخيرة للحساب - للتوزيع فقط وليس حد"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        hour_ago = datetime.now() - timedelta(hours=1)
        c.execute('SELECT COUNT(*) FROM join_history WHERE joined_by=? AND (status="success" OR status="success_retry" OR status="success_after_wait") AND joined_at>?',
                  (f'account_{acc_id}', hour_ago))
        count = c.fetchone()[0]
        conn.close()
        return count
    except:
        return 0


# متغير لتتبع آخر حساب مستخدم بالتناوب
_last_join_acc_index = 0

def get_best_join_account():
    """اختيار أفضل حساب للانضمام - توزيع بالتناوب بين الحسابات
    بدون حد ساعة - كل الحسابات تنظم بلا قيود
    فقط يوزع الروابط بالتناوب لمنع ضغط حساب واحد
    """
    global _last_join_acc_index
    
    if not user_clients:
        return None, None
    
    acc_ids = list(user_clients.keys())
    if not acc_ids:
        return None, None
    
    # تحقق من FloodWait - تخطي الحسابات التي في FloodWait
    for attempt in range(len(acc_ids)):
        # اختيار الحساب التالي بالتناوب
        idx = (_last_join_acc_index + attempt) % len(acc_ids)
        acc_id = acc_ids[idx]
        
        # تحقق من FloodWait
        flood_remaining = get_setting(f'flood_wait_{acc_id}', '0')
        if flood_remaining and flood_remaining != '0':
            flood_time = float(flood_remaining)
            if time.time() < flood_time:
                continue  # تخطي هذا الحساب - في FloodWait
        
        # هذا الحساب متاح
        _last_join_acc_index = (idx + 1) % len(acc_ids)
        return user_clients[acc_id], acc_id
    
    # كل الحسابات في FloodWait - أرجع الأقل انتظاراً
    best_acc = acc_ids[0]
    best_wait = float('inf')
    for acc_id in acc_ids:
        flood_remaining = get_setting(f'flood_wait_{acc_id}', '0')
        if flood_remaining and flood_remaining != '0':
            remaining = float(flood_remaining) - time.time()
            if remaining < best_wait:
                best_wait = remaining
                best_acc = acc_id
    
    _last_join_acc_index = (acc_ids.index(best_acc) + 1) % len(acc_ids)
    return user_clients[best_acc], best_acc


async def auto_join_links(links, progress_callback=None):
    """نظام الانضمام التلقائي - ينضم لكل الروابط بفاصل زمني فقط
    
    الميزات:
    - ينضم لكل الروابط بدون حد أقصى
    - فاصل زمني بين كل رابط فقط (بدون تأخيرات إضافية)
    - توزيع بالتناوب على الحسابات
    - تبديل تلقائي عند FloodWait
    - طابور: الروابط تُحفظ وتُعالج بالترتيب
    """
    global is_joining_active, join_cancelled, join_queue
    
    if is_joining_active:
        # إضافة الروابط للطابور بدلاً من رفضها
        join_queue.extend(links)
        return 0, 0, 0, f"📋 تم إضافة {len(links)} رابط للطابور (سيتم الانضمام بعد الانتهاء من الروابط الحالية)"
    
    is_joining_active = True
    join_cancelled = False
    
    if not user_clients:
        is_joining_active = False
        return 0, 0, 0, "❌ لا توجد حسابات متصلة"
    
    success_count = 0
    failed_count = 0
    skipped_count = 0
    
    try:
        # تنظيف الروابط وإزالة المكررات
        clean_links = []
        seen = set()
        for link in links:
            link = link.strip()
            if not link:
                continue
            # تطبيع الرابط
            link = re.sub(r'[\u200B\u200C\u200D\uFEFF]+', '', link)
            if link.startswith('@'):
                username = link[1:]
                if len(username) >= 5 and username[0].isalpha():
                    link = f'https://t.me/{username}'
            if 't.me/' in link and link not in seen:
                if not link.startswith('http'):
                    link = 'https://' + link
                seen.add(link)
                clean_links.append(link)
        
        if not clean_links:
            is_joining_active = False
            return 0, 0, 0, "❌ لا توجد روابط صالحة"
        
        total_links = len(clean_links)
        
        # الفاصل الزمني فقط - بدون أي تأخير إضافي
        base_interval = int(get_setting('join_interval', '30'))
        
        logger.info(f"🚀 بدء الانضمام لـ {total_links} رابط عبر {len(user_clients)} حساب - فاصل {base_interval}ث")
        
        for i, link in enumerate(clean_links, 1):
            # التحقق من الإلغاء
            if join_cancelled:
                # إضافة الروابط المتبقية للطابور
                remaining = clean_links[i-1:]
                if remaining:
                    join_queue.extend(remaining)
                    logger.info(f"📋 تم إضافة {len(remaining)} رابط متبقي للطابور بعد الإلغاء")
                is_joining_active = False
                # معالجة الطابور
                if join_queue:
                    asyncio.create_task(process_join_queue(progress_callback))
                return success_count, failed_count, skipped_count, f"⏹ تم الإلغاء بعد {i-1} رابط - الباقي في الطابور"
            
            # اختيار حساب بالتناوب
            client, acc_id = get_best_join_account()
            if client is None:
                logger.warning(f"⚠️ لا يوجد حساب متاح - تخطي الروابط المتبقية ({total_links - i + 1})")
                failed_count += (total_links - i + 1)
                break
            
            # الفاصل الزمني فقط (بدون تأخير بشري) - تخطي للرابط الأول
            if i > 1:
                try:
                    # فقط الفاصل المحدد + تذبذب بسيط ±3 ثواني
                    jitter = random.randint(-3, 3)
                    actual_delay = max(5, base_interval + jitter)
                    
                    # انتظار FloodWait إذا كان الحساب في انتظار
                    flood_remaining = get_setting(f'flood_wait_{acc_id}', '0')
                    if flood_remaining and flood_remaining != '0':
                        flood_time = float(flood_remaining)
                        if time.time() < flood_time:
                            wait_more = flood_time - time.time()
                            logger.info(f"⏸ حساب {acc_id} في FloodWait - انتظار {wait_more:.0f}ث")
                            if progress_callback:
                                await progress_callback(f"⏸ FloodWait حساب {acc_id}... انتظار {wait_more:.0f}ث\n📊 التقدم: {i}/{total_links}")
                            await asyncio.sleep(wait_more + 3)
                        set_setting(f'flood_wait_{acc_id}', '0')
                    
                    logger.info(f"⏸ انتظار {actual_delay}ث قبل الرابط {i}/{total_links} [حساب {acc_id}]")
                    await asyncio.sleep(actual_delay)
                
                except asyncio.CancelledError:
                    remaining = clean_links[i-1:]
                    if remaining:
                        join_queue.extend(remaining)
                    is_joining_active = False
                    return success_count, failed_count, skipped_count, f"⏹ تم الإلغاء بعد {i-1} رابط - الباقي في الطابور"
            
            # محاولة الانضمام
            group_info = None
            try:
                if "joinchat" in link or "+" in link:
                    hash_part = link.split('/')[-1].replace('+', '').replace('joinchat/', '')
                    if not hash_part:
                        failed_count += 1
                        logger.warning(f"❌ [{i}/{total_links}] رابط دعوة بدون كود: {link[:50]}")
                        save_join_history(link, 0, "رابط غير مكتمل", 'failed:empty_invite', f"account_{acc_id}")
                        continue
                    updates = await client(ImportChatInviteRequest(hash_part))
                    if updates.chats:
                        chat = updates.chats[0]
                        group_info = (chat.id, getattr(chat, 'title', 'غير معروف'))
                else:
                    username = link.split('/')[-1].split('?')[0]
                    if not username:
                        failed_count += 1
                        logger.warning(f"❌ [{i}/{total_links}] رابط بدون اسم: {link[:50]}")
                        save_join_history(link, 0, "رابط غير مكتمل", 'failed:empty_username', f"account_{acc_id}")
                        continue
                    entity = await client.get_entity(username)
                    if entity:
                        if hasattr(entity, 'left') and not entity.left:
                            skipped_count += 1
                            logger.info(f"⏭ [{i}/{total_links}] منضم بالفعل: {username}")
                            save_join_history(link, entity.id, getattr(entity, 'title', username), 'skipped', f"account_{acc_id}")
                            continue
                        
                        await client(JoinChannelRequest(entity))
                        group_info = (entity.id, getattr(entity, 'title', username))
                
                success_count += 1
                logger.info(f"✅ [{i}/{total_links}] تم الانضمام إلى {link[:60]} [حساب {acc_id}]")
                
                if group_info:
                    group_id, group_name = group_info
                    save_join_history(link, group_id, group_name[:80], 'success', f"account_{acc_id}")
                    add_group_to_db(group_id, group_name)
                else:
                    save_join_history(link, 0, "تم الانضمام", 'success', f"account_{acc_id}")
            
            except FloodWaitError as e:
                flood_seconds = e.seconds
                logger.warning(f"⏸ حساب {acc_id} في FloodWait: {flood_seconds}ث - تبديل الحساب")
                
                set_setting(f'flood_wait_{acc_id}', str(time.time() + flood_seconds))
                save_join_history(link, 0, "FloodWait", f'flood_wait:{flood_seconds}s', f"account_{acc_id}")
                
                # تبديل الحساب وإعادة المحاولة فوراً
                client2, acc_id2 = get_best_join_account()
                if client2 and acc_id2 != acc_id:
                    try:
                        logger.info(f"🔄 إعادة محاولة الرابط {i} بحساب {acc_id2}")
                        await asyncio.sleep(3)  # تأخير بسيط فقط
                        
                        if "joinchat" in link or "+" in link:
                            hash_part = link.split('/')[-1].replace('+', '').replace('joinchat/', '')
                            if not hash_part:
                                failed_count += 1
                                save_join_history(link, 0, "رابط غير مكتمل", 'failed:empty_invite_retry', f"account_{acc_id2}")
                                continue
                            updates = await client2(ImportChatInviteRequest(hash_part))
                            if updates.chats:
                                chat = updates.chats[0]
                                group_info = (chat.id, getattr(chat, 'title', 'غير معروف'))
                        else:
                            username = link.split('/')[-1].split('?')[0]
                            if not username:
                                failed_count += 1
                                save_join_history(link, 0, "رابط غير مكتمل", 'failed:empty_username_retry', f"account_{acc_id2}")
                                continue
                            entity = await client2.get_entity(username)
                            await client2(JoinChannelRequest(entity))
                            group_info = (entity.id, getattr(entity, 'title', username))
                        
                        success_count += 1
                        if group_info:
                            gid, gname = group_info
                            save_join_history(link, gid, gname[:80], 'success_retry', f"account_{acc_id2}")
                            add_group_to_db(gid, gname)
                        logger.info(f"✅ [{i}/{total_links}] نجاح بعد تبديل الحساب [حساب {acc_id2}]")
                    except FloodWaitError as e2:
                        failed_count += 1
                        logger.error(f"❌ [{i}/{total_links}] FloodWait على حسابين")
                        set_setting(f'flood_wait_{acc_id2}', str(time.time() + e2.seconds))
                        await asyncio.sleep(min(e2.seconds, 60))
                    except Exception as e3:
                        failed_count += 1
                        logger.error(f"❌ [{i}/{total_links}] فشل بعد تبديل الحساب: {e3}")
                        save_join_history(link, 0, "فشل", f'failed_retry:{str(e3)[:40]}', f"account_{acc_id2}")
                else:
                    # حساب واحد فقط - انتظار FloodWait ثم إعادة المحاولة
                    wait_time = min(flood_seconds + 3, 120)
                    logger.info(f"⏸ انتظار FloodWait {wait_time}ث ثم إعادة المحاولة")
                    if progress_callback:
                        await progress_callback(f"⏸ FloodWait {flood_seconds}ث - انتظار ثم إعادة محاولة...\n📊 التقدم: {i}/{total_links}")
                    await asyncio.sleep(wait_time)
                    try:
                        if "joinchat" in link or "+" in link:
                            hash_part = link.split('/')[-1].replace('+', '').replace('joinchat/', '')
                            if not hash_part:
                                failed_count += 1
                                continue
                            updates = await client(ImportChatInviteRequest(hash_part))
                            if updates.chats:
                                chat = updates.chats[0]
                                group_info = (chat.id, getattr(chat, 'title', 'غير معروف'))
                        else:
                            username = link.split('/')[-1].split('?')[0]
                            if not username:
                                failed_count += 1
                                continue
                            entity = await client.get_entity(username)
                            await client(JoinChannelRequest(entity))
                            group_info = (entity.id, getattr(entity, 'title', username))
                        
                        success_count += 1
                        if group_info:
                            gid, gname = group_info
                            save_join_history(link, gid, gname[:80], 'success_after_wait', f"account_{acc_id}")
                            add_group_to_db(gid, gname)
                        logger.info(f"✅ [{i}/{total_links}] نجاح بعد انتظار FloodWait [حساب {acc_id}]")
                    except UserAlreadyParticipantError:
                        skipped_count += 1
                        save_join_history(link, 0, "منضم بالفعل", 'skipped', f"account_{acc_id}")
                    except Exception as retry_e:
                        failed_count += 1
                        logger.error(f"❌ [{i}/{total_links}] فشل بعد انتظار FloodWait: {retry_e}")
                        save_join_history(link, 0, "فشل بعد انتظار", f'failed_after_wait:{str(retry_e)[:40]}', f"account_{acc_id}")
            
            except UserAlreadyParticipantError:
                skipped_count += 1
                logger.info(f"⏭ [{i}/{total_links}] منضم بالفعل: {link[:50]}")
                save_join_history(link, 0, "منضم بالفعل", 'skipped', f"account_{acc_id}")
            
            except InviteHashExpiredError:
                failed_count += 1
                save_join_history(link, 0, "رابط منتهي", 'failed:expired_invite', f"account_{acc_id}")
            
            except InviteHashInvalidError:
                failed_count += 1
                save_join_history(link, 0, "رابط غير صالح", 'failed:invalid_invite', f"account_{acc_id}")
            
            except ChannelPrivateError:
                failed_count += 1
                save_join_history(link, 0, "قناة خاصة", 'failed:private', f"account_{acc_id}")
            
            except ChannelInvalidError:
                failed_count += 1
                save_join_history(link, 0, "قناة غير صالحة", 'failed:invalid_channel', f"account_{acc_id}")
            
            except Exception as e:
                error_str = str(e)
                if 'already' in error_str.lower() or 'ALREADY' in error_str:
                    skipped_count += 1
                    save_join_history(link, 0, "منضم بالفعل", 'skipped', f"account_{acc_id}")
                else:
                    failed_count += 1
                    logger.error(f"❌ [{i}/{total_links}] فشل: {e} [حساب {acc_id}]")
                    save_join_history(link, 0, "فشل", f'failed:{error_str[:40]}', f"account_{acc_id}")
            
            # تحديث التقدم
            if progress_callback and (i % 3 == 0 or i == total_links):
                try:
                    await progress_callback(
                        f"🔄 الانضمام: {i}/{total_links}\n"
                        f"✅ نجاح: {success_count} | ⏭ تخطي: {skipped_count} | ❌ فشل: {failed_count}\n"
                        f"👤 حساب: {acc_id} | ⏱ متبقي: ~{((total_links - i) * base_interval) // 60}د"
                    )
                except:
                    pass
        
        is_joining_active = False
        
        result_msg = (
            f"✅ **اكتمل الانضمام**\n\n"
            f"📊 الإجمالي: {total_links} رابط\n"
            f"✅ نجاح: {success_count}\n"
            f"⏭ تخطي (منضم): {skipped_count}\n"
            f"❌ فشل: {failed_count}\n"
            f"📈 نسبة النجاح: {(success_count / max(total_links, 1)) * 100:.1f}%"
        )
        
        # معالجة الطابور بعد الانتهاء
        if join_queue:
            asyncio.create_task(process_join_queue(progress_callback))
        
        return success_count, failed_count, skipped_count, result_msg
    
    except Exception as outer_e:
        logger.error(f"❌ خطأ غير متوقع في الانضمام: {outer_e}")
        is_joining_active = False
        if join_queue:
            asyncio.create_task(process_join_queue(progress_callback))
        return success_count, failed_count, skipped_count, f"❌ خطأ غير متوقع: {str(outer_e)[:100]}\n✅ نجاح: {success_count} | ❌ فشل: {failed_count} | ⏭ تخطي: {skipped_count}"


async def process_join_queue(original_callback=None):
    """معالجة طابور الروابط - ينضم للروابط المحفوظة بعد الانتهاء من الدفعة الحالية"""
    global join_queue
    
    if not join_queue:
        return
    
    # أخذ الروابط من الطابور
    queued_links = join_queue.copy()
    join_queue = []
    
    logger.info(f"📋 معالجة طابور {len(queued_links)} رابط")
    
    async def queue_callback(text):
        if original_callback:
            try:
                await original_callback(f"📋 [طابور] {text}")
            except:
                pass
    
    await auto_join_links(queued_links, progress_callback=queue_callback)

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
    c.execute("SELECT COUNT(*) FROM join_history WHERE status='success' OR status='success_retry' OR status='success_after_wait'")
    success = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM join_history WHERE status LIKE 'failed%' OR status LIKE 'flood_wait%'")
    failed = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM join_history WHERE status='skipped'")
    skipped = c.fetchone()[0]
    conn.close()
    return {'total': total, 'success': success, 'failed': failed, 'skipped': skipped}

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
#  نظام النشر الشبحي 👻 (انشر → انتظر → عدّل/احذف)
# ═══════════════════════════════════════════════
async def ghost_post_worker(client, group_id, msg_id, original_content, lifetime=20, mode='replace', original_raw_content=None, all_messages=None):
    """
    نظام النشر الشبحي المحسّن:
    1. ينشر الرسالة الأصلية (الإعلان مكوّد)
    2. ينتظر عدد الثواني المحدد (المستخدمون يقرؤون الرسالة)
    3. يعدّل الرسالة بنفس الإعلان بتكويد مختلف أو بالإعلان التالي
    → بوتات الحماية تحلل الرسالة بعد التعديل = لا تجد نفس النمط
    → المستخدمون يرون الإعلان مرة أخرى بتكويد مختلف!
    """
    try:
        await asyncio.sleep(lifetime)
        
        if not is_posting_active:
            return
        
        if mode == 'delete':
            # حذف الرسالة تماماً
            try:
                await client.delete_messages(int(group_id), msg_id)
                logger.info(f"👻 شبح: حذف رسالة في {group_id}")
            except:
                pass
        elif mode == 'empty':
            # تفريغ الرسالة (تبديل بنقطة أو رمز)
            try:
                replacements = ['.', '..', '...', '👋', '✅', '👍', 'تم', 'شكراً']
                await client.edit_message(int(group_id), msg_id, random.choice(replacements))
                logger.info(f"👻 شبح: تفريغ رسالة في {group_id}")
            except:
                pass
        elif mode == 'replace':
            # 👻 التعديل بنفس الإعلان بتكويد مختلف أو بالإعلان التالي
            # النظام المحسّن: يضمن دائماً تكويد مختلف عن الأصلي
            try:
                new_content = None
                use_html = False
                stealth_on = get_setting('stealth_obfuscator_enabled', 'on') == 'on'
                yaytext_on = get_setting('yaytext_messletters_obfuscation', 'on') == 'on'
                
                # الخيار 1: استخدام الإعلان التالي (أقوى ضد البوتات)
                if all_messages and len(all_messages) > 1:
                    other_msgs = [m for m in all_messages if m[1]]  # رسائل فيها محتوى
                    if other_msgs:
                        # اختيار رسالة مختلفة عشوائياً
                        chosen = random.choice(other_msgs)
                        raw_content = chosen[1]
                        if raw_content:
                            if stealth_on:
                                new_content, use_html = stealth_obfuscator.obfuscate(raw_content, group_id)
                            elif yaytext_on:
                                old_style = yaytext_obfuscator._last_style
                                new_content, use_html = yaytext_obfuscate(raw_content)
                                retries = 0
                                while yaytext_obfuscator._last_style == old_style and retries < 5:
                                    new_content, use_html = yaytext_obfuscate(raw_content)
                                    retries += 1
                            else:
                                obfuscation_on = get_setting('obfuscation_enabled', 'on') == 'on'
                                varied = vary_text(raw_content)
                                if obfuscation_on:
                                    varied = obfuscate_for_humans(varied)
                                new_content = encrypt_text(varied, group_id)
                            logger.info(f"👻 شبح: استبدال بإعلان مختلف مكوّد في {group_id}")
                
                # الخيار 2: نفس الإعلان بتكويد جديد (نمط مختلف مضمون)
                if not new_content and original_raw_content:
                    if stealth_on:
                        new_content, use_html = stealth_obfuscator.obfuscate(original_raw_content, group_id)
                    elif yaytext_on:
                        old_style = yaytext_obfuscator._last_style
                        new_content, use_html = yaytext_obfuscate(original_raw_content)
                        retries = 0
                        while yaytext_obfuscator._last_style == old_style and retries < 5:
                            new_content, use_html = yaytext_obfuscate(original_raw_content)
                            retries += 1
                    else:
                        obfuscation_on = get_setting('obfuscation_enabled', 'on') == 'on'
                        varied = vary_text(original_raw_content)
                        if obfuscation_on:
                            varied = obfuscate_for_humans(varied)
                        new_content = encrypt_text(varied, group_id)
                    logger.info(f"👻 شبح: إعادة تكويد نفس الإعلان بنمط مختلف في {group_id}")
                
                # الخيار 3: نص محايد (fallback أخير فقط)
                if not new_content:
                    neutral_texts = ['شكراً للجميع 👍', 'تم ✅', 'شكراً', '👍', '✅', 'تمام', 'حسناً', '👌', 'thanks', 'ok', '.']
                    new_content = random.choice(neutral_texts)
                    logger.info(f"👻 شبح: استبدال بنص محايد في {group_id}")
                
                parse_mode = 'html' if use_html else None
                await client.edit_message(int(group_id), msg_id, new_content, parse_mode=parse_mode)
            except Exception as e:
                logger.debug(f"👻 شبح: فشل التعديل ({e})")
    except Exception as e:
        logger.debug(f"👻 شبح: تخطي ({e})")

# ═══════════════════════════════════════════════
#  🆕 نظام سرب الأشباح - Ghost Swarm 👻🐝
# ═══════════════════════════════════════════════
async def ghost_swarm_worker(client, group_id, msg_id, original_content, stages=3, interval=10, original_raw_content=None, all_messages=None):
    """نظام سرب الأشباح: تعديلات متتالية بتكويد مختلف كل مرة
    المرحلة 1: تعديل بنمط مختلف (بعد interval ثانية)
    المرحلة 2: تعديل بنمط مختلف آخر (بعد interval ثانية أخرى)
    المرحلة 3: تعديل بنمط مختلف أو نص محايد
    → بوتات الحماية تحلل الرسالة بعد كل تعديل = لا تجد نفس النمط أبداً!
    → مع edit_hide لا يظهر علامة "معدّل" على الرسالة!
    """
    for stage in range(stages):
        await asyncio.sleep(interval)
        if not is_posting_active:
            return
        try:
            new_content = None
            use_html = False
            stealth_on = get_setting('stealth_obfuscator_enabled', 'on') == 'on'
            yaytext_on = get_setting('yaytext_messletters_obfuscation', 'on') == 'on'
            
            # استخدام الإعلان التالي أو نفس الإعلان بتكويد مختلف
            if all_messages and len(all_messages) > 1 and random.random() < 0.5:
                other_msgs = [m for m in all_messages if m[1]]
                if other_msgs:
                    chosen = random.choice(other_msgs)
                    raw = chosen[1]
                    if raw:
                        if stealth_on:
                            new_content, use_html = stealth_obfuscator.obfuscate(raw, group_id)
                        elif yaytext_on:
                            new_content, use_html = yaytext_obfuscate(raw)
                        else:
                            new_content = encrypt_text(vary_text(raw), group_id)
            elif original_raw_content:
                if stealth_on:
                    new_content, use_html = stealth_obfuscator.obfuscate(original_raw_content, group_id)
                elif yaytext_on:
                    old_style = yaytext_obfuscator._last_style
                    new_content, use_html = yaytext_obfuscate(original_raw_content)
                    retries = 0
                    while yaytext_obfuscator._last_style == old_style and retries < 5:
                        new_content, use_html = yaytext_obfuscate(original_raw_content)
                        retries += 1
                else:
                    new_content = encrypt_text(vary_text(original_raw_content), group_id)
            
            if not new_content:
                neutral = ['✅', '👍', 'تم', 'شكراً', '👌', 'حسناً', 'تمام']
                new_content = random.choice(neutral)
                use_html = False
            
            # 🆕 استخدام edit_hide لإخفاء علامة "معدّل"
            try:
                from telethon.tl.functions.messages import EditMessageRequest
                parse_mode = 'html' if use_html else None
                if get_setting('edit_hide_enabled', 'on') == 'on':
                    await client(EditMessageRequest(
                        peer=int(group_id),
                        id=msg_id,
                        message=new_content,
                        no_webpage=True
                    ))
                else:
                    await client.edit_message(int(group_id), msg_id, new_content, parse_mode=parse_mode)
            except:
                parse_mode = 'html' if use_html else None
                await client.edit_message(int(group_id), msg_id, new_content, parse_mode=parse_mode)
            
            logger.info(f"🐝 Swarm مرحلة {stage+1}/{stages} في {group_id}")
        except Exception as e:
            logger.debug(f"🐝 Swarm مرحلة فشلت: {e}")

# ═══════════════════════════════════════════════
#  النشر السريع - ينشر بكل الحسابات لكل المجموعات + كل الرسائل + شبحي
# ═══════════════════════════════════════════════
async def fast_post_to_all_groups(messages):
    """نشر سريع: كل حساب × كل مجموعة × كل رسالة + نظام شبحي + Spintax + Human Delay + Ghost Swarm"""
    global is_posting_active

    if not isinstance(messages, list):
        messages = [messages]

    fast_delay = max(2, int(get_setting('fast_post_delay', '3')))
    obfuscation_on = get_setting('obfuscation_enabled', 'on') == 'on'
    ghost_enabled = get_setting('ghost_post_enabled', 'on') == 'on'
    ghost_lifetime = max(10, int(get_setting('ghost_post_lifetime', '20')))
    ghost_mode = get_setting('ghost_post_mode', 'replace')
    ghost_swarm_on = get_setting('ghost_swarm_enabled', 'off') == 'on'
    ghost_swarm_stages = int(get_setting('ghost_swarm_stages', '3'))
    ghost_swarm_interval = int(get_setting('ghost_swarm_interval', '10'))
    spintax_on = get_setting('spintax_enabled', 'on') == 'on'
    use_load_balancer = get_setting('load_balancer_enabled', 'on') == 'on'
    success_count = 0
    fail_count = 0
    total_posts = 0

    # حساب إجمالي المجموعات عبر كل الحسابات
    for acc_id, client in list(user_clients.items()):
        try:
            groups = await get_account_groups(client)
            total_posts += len(groups) * len(messages)
        except:
            continue

    if total_posts == 0:
        return 0, 0, 0

    logger.info(f"⚡ بدء النشر السريع: {len(user_clients)} حساب × {len(messages)} رسالة (إجمالي ~{total_posts}) 👻شبحي={'✅' if ghost_enabled else '❌'} 🐝سرب={'✅' if ghost_swarm_on else '❌'} 🎲Spintax={'✅' if spintax_on else '❌'}")

    # كل حساب ينشر في كل مجموعاته + كل الرسائل
    for acc_id, client in list(user_clients.items()):
        if not is_posting_active:
            break

        try:
            acc_groups = await get_account_groups(client)
        except Exception as e:
            logger.error(f"❌ فشل جلب مجموعات الحساب {acc_id}: {e}")
            continue

        # تنويع ترتيب الرسائل لكل حساب
        msg_order = list(messages)
        if len(msg_order) > 1:
            random.shuffle(msg_order)

        for gid, gname in acc_groups:
            if not is_posting_active:
                break

            if is_group_blacklisted(gid):
                continue

            # نشر كل رسالة بالترتيب المتنوع
            for msg in msg_order:
                if not is_posting_active:
                    break

                msg_id = msg[0]
                content = msg[1]
                media_path = msg[2]
                msg_type = msg[3]
                media_data = msg[4] if len(msg) > 4 else None

                # 🆕 تطبيق Spintax على المحتوى
                if content and spintax_on:
                    content = parse_spintax(content)

                use_html = False
                if content:
                    # 🆕 نظام التشفير الموحد (يدعم التشفير الخارق)
                    encrypted_content, use_html = prepare_content_for_sending(content, gid)
                else:
                    encrypted_content = ""

                try:
                    # 🆕 استخدام Human Delay بدل التأخير الثابت
                    if get_setting('human_delay_enabled', 'on') == 'on':
                        await human_delay()
                    else:
                        await asyncio.sleep(fast_delay)
                    if not is_posting_active:
                        break
                    
                    # إرسال الرسالة
                    sent_msg = await _send_and_get_message(client, gid, encrypted_content, msg_type, media_path, media_data, use_html)
                    success_count += 1
                    log_posting(acc_id, int(gid), msg_id, 'success')
                    logger.info(f"⚡ سريع ✅ {gname[:30]} (حساب {acc_id}) ({success_count}/{total_posts})")
                    
                    # 👻 تفعيل النشر الشبحي
                    if sent_msg and msg_type == 'text':
                        # 🆕 Ghost Swarm أو Ghost Post عادي
                        if ghost_swarm_on:
                            asyncio.create_task(ghost_swarm_worker(
                                client, gid, sent_msg.id, encrypted_content,
                                stages=ghost_swarm_stages, interval=ghost_swarm_interval,
                                original_raw_content=content, all_messages=msg_order
                            ))
                        elif ghost_enabled:
                            asyncio.create_task(ghost_post_worker(
                                client, gid, sent_msg.id, encrypted_content,
                                lifetime=ghost_lifetime, mode=ghost_mode,
                                original_raw_content=content, all_messages=msg_order
                            ))
                    
                except FloodWaitError as e:
                    logger.warning(f"⏸ FloodWait: {e.seconds}ث - انتظار ثم إعادة المحاولة")
                    try:
                        await asyncio.sleep(e.seconds + random.uniform(1, 5))
                        if not is_posting_active:
                            break
                        sent_msg = await _send_and_get_message(client, gid, encrypted_content, msg_type, media_path, media_data, use_html)
                        success_count += 1
                        log_posting(acc_id, int(gid), msg_id, 'success (retry after flood)')
                        logger.info(f"⚡ سريع ✅ (بعد FloodWait) {gname[:30]}")
                        if sent_msg and msg_type == 'text':
                            if ghost_swarm_on:
                                asyncio.create_task(ghost_swarm_worker(
                                    client, gid, sent_msg.id, encrypted_content,
                                    stages=ghost_swarm_stages, interval=ghost_swarm_interval,
                                    original_raw_content=content, all_messages=msg_order
                                ))
                            elif ghost_enabled:
                                asyncio.create_task(ghost_post_worker(
                                    client, gid, sent_msg.id, encrypted_content,
                                    lifetime=ghost_lifetime, mode=ghost_mode,
                                    original_raw_content=content, all_messages=msg_order
                                ))
                    except Exception as retry_e:
                        fail_count += 1
                        logger.error(f"❌ فشل بعد إعادة المحاولة: {retry_e}")
                except Exception as e:
                    fail_count += 1
                    logger.error(f"❌ فشل: {e}")

    return success_count, fail_count, total_posts

async def _send_and_get_message(client, group_id, encrypted_content, msg_type, media_path, media_data, use_html=False):
    """إرسال رسالة وإرجاع الرسالة المرسلة (للنشر الشبحي)"""
    parse_mode = 'html' if use_html else None
    try:
        if msg_type == 'text':
            return await client.send_message(int(group_id), encrypted_content, parse_mode=parse_mode)
        elif msg_type == 'photo' and media_path and os.path.exists(media_path):
            return await client.send_file(int(group_id), media_path, caption=encrypted_content, parse_mode=parse_mode)
        elif msg_type == 'video' and media_path and os.path.exists(media_path):
            return await client.send_file(int(group_id), media_path, caption=encrypted_content, parse_mode=parse_mode)
        elif msg_type == 'audio' and media_path and os.path.exists(media_path):
            return await client.send_file(int(group_id), media_path, caption=encrypted_content, parse_mode=parse_mode)
        elif msg_type == 'document' and media_path and os.path.exists(media_path):
            return await client.send_file(int(group_id), media_path, caption=encrypted_content, parse_mode=parse_mode)
        elif msg_type == 'contact' and media_data:
            contact_data = json.loads(media_data) if isinstance(media_data, str) else media_data
            return await send_contact_message(client, int(group_id), contact_data, encrypted_content)
        else:
            if media_path and os.path.exists(media_path):
                return await client.send_file(int(group_id), media_path, caption=encrypted_content, parse_mode=parse_mode)
            else:
                return await client.send_message(int(group_id), encrypted_content, parse_mode=parse_mode)
    except Exception as e:
        if use_html:
            clean_text = re.sub(r'<a href="[^"]*">([^<]*)</a>', r'\1', encrypted_content)
            clean_text = clean_text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
            if msg_type == 'text':
                return await client.send_message(int(group_id), clean_text)
            elif media_path and os.path.exists(media_path):
                return await client.send_file(int(group_id), media_path, caption=clean_text)
            else:
                return await client.send_message(int(group_id), clean_text)
        raise

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
        return 0, 0, 0

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
                # 🆕 نظام التشفير الموحد (يدعم التشفير الخارق)
                encrypted_content, use_html = prepare_content_for_sending(content, gid)
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
    spintax_status = "✅" if get_setting('spintax_enabled', 'on') == 'on' else "❌"
    kashida_status = "✅" if get_setting('kashida_enabled', 'on') == 'on' else "❌"
    homoglyph_status = "✅" if get_setting('arabic_homoglyph_enabled', 'on') == 'on' else "❌"
    hd_status = "✅" if get_setting('human_delay_enabled', 'on') == 'on' else "❌"
    swarm_status = "✅" if get_setting('ghost_swarm_enabled', 'off') == 'on' else "❌"
    vs_status = "✅" if get_setting('variation_selectors_enabled', 'on') == 'on' else "❌"
    tag_status = "✅" if get_setting('tag_characters_enabled', 'on') == 'on' else "❌"
    lb_status = "✅" if get_setting('load_balancer_enabled', 'on') == 'on' else "❌"
    stealth_status = "✅" if get_setting('stealth_obfuscator_enabled', 'on') == 'on' else "❌"
    se_status = "✅" if get_setting('super_encryption_enabled', 'off') == 'on' else "❌"
    he_status = "✅" if get_setting('hyper_encryption_enabled', 'on') == 'on' else "❌"
    ft_status = "✅" if get_setting('fancy_text_enabled', 'on') == 'on' else "❌"
    ft_style = get_setting('fancy_text_style', 'strikethrough')
    # أيقونة النمط الحالي
    ft_icon = fancy_engine.STYLES.get(ft_style, {}).get('icon', '✨')
    ft_name = fancy_engine.STYLES.get(ft_style, {}).get('name', 'Strikethrough')
    enc_strength = get_setting('encryption_strength', 'medium')
    strength_emoji = {'light': '🟢', 'medium': '🟡', 'aggressive': '🟠', 'insane': '🔴'}.get(enc_strength, '🟡')
    message_interval = get_setting('message_interval', '3')
    join_interval = get_setting('join_interval', '30')
    fast_delay = get_setting('fast_post_delay', '3')
    pending_sched = len(get_pending_scheduled_posts())
    return [
        [Button.inline("📝 إدارة الرسائل", b"messages")],
        [Button.inline("👥 إدارة الحسابات", b"accounts")],
        [Button.inline("⚡ نشر سريع للكل", b"fast_posting"),
         Button.inline("🚀 بدء النشر", b"start_posting"),
         Button.inline("⏹ إيقاف النشر", b"stop_posting")],
        [Button.inline(f"📅 جدولة النشر ({pending_sched})", b"scheduling")],
        # ✨ Fancy Text - ميزة جديدة (بديل HyperEncryption)
        [Button.inline(f"✨ Fancy Text {ft_status}", b"toggle_fancy_text"),
         Button.inline(f"{ft_icon} النمط: {ft_name}", b"fancy_text_menu")],
        [Button.inline("🧪 معاينة كل الأنماط (26)", b"fancy_text_preview"),
         Button.inline(f"🔬 تشويش خفي {stealth_status}", b"toggle_stealth")],
        # HyperEncryption يبقى متاح كزر منفصل
        [Button.inline(f"🔥 HyperEncryption {he_status}", b"toggle_hyper_enc"),
         Button.inline(f"{strength_emoji} قوة التشفير: {enc_strength}", b"enc_strength")],
        [Button.inline("🧪 اختبار التشفير الخارق", b"enc_test"),
         Button.inline("🛡️ إعدادات التشفير المتقدمة", b"advanced_enc_settings")],
        [Button.inline(f"🛡 التشفير {enc_status}", b"toggle_enc"),
         Button.inline(f"🎭 مكافحة الكشف {anti_status}", b"toggle_anti")],
        [Button.inline(f"💎 تشفير خارق قديم {se_status}", b"toggle_super_encryption"),
         Button.inline(f"🎭 تشويش النص {obf_status}", b"toggle_obfuscate")],
        [Button.inline(f"🔄 YayText {ym_status}", b"toggle_yaytext"),
         Button.inline(f"🎲 Spintax {spintax_status}", b"toggle_spintax")],
        [Button.inline(f"〰️ كشيدة {kashida_status}", b"toggle_kashida"),
         Button.inline(f"🔀 Homoglyphs عربي {homoglyph_status}", b"toggle_arabic_homoglyph")],
        [Button.inline(f"🔤 Variation Selectors {vs_status}", b"toggle_vs"),
         Button.inline(f"🏷️ Tag Characters {tag_status}", b"toggle_tag")],
        [Button.inline(f"🐝 Ghost Swarm {swarm_status}", b"toggle_ghost_swarm"),
         Button.inline(f"⏱️ Human Delay {hd_status}", b"toggle_human_delay")],
        [Button.inline(f"⚖️ Load Balancer {lb_status}", b"toggle_load_balancer")],
        [Button.inline("🛡️ AntiGuardian - تجاوز الحماية", b"anti_guardian_settings")],
        [Button.inline("⚙️ الإعدادات", b"settings"),
         Button.inline("📊 الإحصائيات", b"stats")],
        [Button.inline(f"🚀 انضمام تلقائي ({join_interval}ث)", b"auto_join"),
         Button.inline("📋 تقارير الانضمام", b"join_reports")],
        [Button.inline("⏹ إيقاف الانضمام", b"stop_joining"),
         Button.inline("🔗 إعدادات الانضمام", b"join_settings")],
        [Button.inline(f"⏱ مدة النشر ({message_interval}ث)", b"set_msg_interval"),
         Button.inline(f"⚡ سرعة النشر السريع ({fast_delay}ث)", b"set_fast_delay")],
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

def get_join_settings_menu():
    join_interval = get_setting('join_interval', '30')
    queue_count = len(join_queue)
    queue_info = f" ({queue_count} في الطابور)" if queue_count > 0 else ""
    return [
        [Button.inline(f"⏱ الفاصل بين الروابط ({join_interval}ث)", b"set_join_interval")],
        [Button.inline(f"📋 الطابور{queue_info}", b"view_join_queue")],
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
        [Button.inline("🔗 إعدادات الانضمام", b"join_settings")],
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
            "🛡 **بوت النشر الخارق 2026 - النسخة العالمية**\n\n"
            "✨ **12+ طبقة تشفير خارقة:**\n"
            "• 🎲 Spintax - تنويع تلقائي للرسائل\n"
            "• 🔀 Arabic Homoglyphs - بدائل متطابقة مرئياً\n"
            "• 〰️ كشيدة/Tatweel - تبقى بعد كل التطبيع!\n"
            "• 🏷️ Tag Characters - ترميز مخفي كامل\n"
            "• 🔤 Variation Selectors - أحرف تجميع غير مرئية\n"
            "• PFB + NFD + مسافات بديلة + أحرف مخفية\n\n"
            "🐝 **أنظمة متقدمة:**\n"
            "• 🐝 Ghost Swarm - تعديلات متتالية بتكويد مختلف\n"
            "• 👁️ edit_hide - يخفي علامة 'معدّل'\n"
            "• ⏱️ Human Delay - محاكاة تأخير بشري\n"
            "• ⚖️ Load Balancer - توزيع ذكي بين الحسابات\n"
            "• 📈 Exponential Backoff - تعامل احترافي مع FloodWait\n"
            "• 🔗 الروابط والمعرفات تبقى قابلة للنقر!\n\n"
            f"📅 الجدولة: مرة/يومي/أسبوعي/كل X دقيقة\n"
            f"⚡ النشر السريع ({fast_delay} ثانية) | 📌 مجدولات: {pending_sched}\n\n"
            f"📢 المجموعات: {groups_count} | ⏱ مدة النشر: {message_interval} ثانية\n\n"
            "🧪 جرب: /test_obfuscate لاختبار التشفير",
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
        encrypted = encrypt_text(obfuscated, group_id=-1001234567890)
        level = get_setting('encryption_strength', 'medium')
        he_on = get_setting('hyper_encryption_enabled', 'on') == 'on'
        info = hyper_encryption.get_strength_info() if (hyper_encryption and he_on) else None
        from hyper_encryption import char_analysis as _ca
        counts = _ca(encrypted)
        invisible = sum(v for k, v in counts.items() if k != 'visible')
        he_line = f"• 🔥 HyperEncryption: ✅ {level} ({info['active_count']}/{info['total_count']} طبقة)\n" if info else "• 🔥 HyperEncryption: ❌ معطل\n"
        # حالة Fancy Text
        ft_enabled = get_setting('fancy_text_enabled', 'on') == 'on'
        ft_style_name = fancy_engine.STYLES.get(get_setting('fancy_text_style', 'strikethrough'), {}).get('name', 'Strikethrough')
        ft_line = f"• ✨ Fancy Text: ✅ {ft_style_name}\n" if ft_enabled else "• ✨ Fancy Text: ❌ معطل\n"
        # تطبيق Fancy Text على النص الأصلي للعرض
        ft_preview = ""
        if ft_enabled:
            try:
                style_id = get_setting('fancy_text_style', 'strikethrough')
                if style_id == 'zalgo':
                    intensity = get_setting('fancy_text_zalgo_intensity', 'medium')
                    ft_preview_text = fancy_engine.zalgo(text, intensity=intensity)
                else:
                    ft_preview_text = fancy_engine.apply_style(text, style_id)
                ft_preview = f"✨ **بعد Fancy Text** ({ft_style_name}):\n{ft_preview_text}\n\n"
            except Exception:
                pass
        await event.respond(
            f"📝 **النص الأصلي:**\n{text}\n\n"
            f"{ft_preview}"
            f"🔀 **بعد التشويش:**\n{obfuscated}\n\n"
            f"🛡 **بعد التشفير الخارق** ({len(encrypted)} حرف، {invisible} غير مرئي):\n{encrypted}\n\n"
            f"📊 **الحالة:**\n{he_line}{ft_line}"
            f"💡 النص يبدو متطابقاً بصرياً - الفرق فقط في الأحرف غير المرئية التي تكسر بوتات الحماية!\n\n"
            f"جرّب أيضاً: /encrypt_test <text> لعرض كل المستويات الأربعة"
        )

    @bot.on(events.NewMessage(pattern='/encrypt_test'))
    async def encrypt_test_cmd(event):
        """اختبار شامل - يعرض النص مشفر بكل المستويات الأربعة"""
        if not is_admin(event.sender_id):
            return
        text = event.raw_text.replace('/encrypt_test', '').strip()
        if not text:
            text = "اشترك في قناتنا https://t.me/example عروض حصرية! اتصل: 0555123456"
        from hyper_encryption import HyperEncryptionEngine as _HEE, char_analysis as _ca
        msg = f"🧪 **اختبار HyperEncryption - 4 مستويات**\n\n📝 **النص الأصلي:**\n{text}\n\n"
        for level in ['light', 'medium', 'aggressive', 'insane']:
            eng = _HEE(settings_getter=lambda k, d, _lvl=level: _lvl if k == 'encryption_strength' else ('on' if k == 'encryption' else get_setting(k, d)))
            enc = eng.encrypt(text, group_id=-1001234567890, strength=level)
            counts = _ca(enc)
            invisible = sum(v for k, v in counts.items() if k != 'visible')
            emoji = {'light': '🟢', 'medium': '🟡', 'aggressive': '🟠', 'insane': '🔴'}[level]
            active_n = len(_HEE.STRENGTH_LEVELS[level])
            msg += f"{emoji} **{level.upper()}** ({active_n} طبقة، {len(enc)} حرف، {invisible} غير مرئي):\n{enc}\n\n"
        msg += "💡 كل النصوص تبدو متطابقة بصرياً مع الأصل!\n\nللتبديل: اضغط زر 'قوة التشفير' في القائمة الرئيسية"
        await event.respond(msg)

    @bot.on(events.NewMessage(pattern='/check'))
    async def check_handler(event):
        if not is_admin(event.sender_id):
            return
        groups = await get_all_groups_count()
        msgs = await get_all_messages_count()
        all_accs = await get_all_accounts()
        obf_status = '✅ مفعل' if get_setting('obfuscation_enabled', 'on') == 'on' else '❌ معطل'
        pending_sched = len(get_pending_scheduled_posts())
        enc_level = get_setting('encryption_strength', 'medium')
        he_on = get_setting('hyper_encryption_enabled', 'on') == 'on'
        info = hyper_encryption.get_strength_info() if (hyper_encryption and he_on) else None
        he_line = f"• 🔥 HyperEncryption: ✅ {enc_level} ({info['active_count']}/{info['total_count']} طبقة)\n" if info else "• 🔥 HyperEncryption: ❌ معطل\n"
        # Fancy Text status
        ft_on = get_setting('fancy_text_enabled', 'on') == 'on'
        ft_style_name = fancy_engine.STYLES.get(get_setting('fancy_text_style', 'strikethrough'), {}).get('name', 'Strikethrough')
        ft_line = f"• ✨ Fancy Text: ✅ {ft_style_name}\n" if ft_on else "• ✨ Fancy Text: ❌ معطل\n"
        await event.respond(
            f"📊 **حالة البوت:**\n"
            f"• المجموعات: {groups}\n• الرسائل: {msgs}\n"
            f"• إجمالي الحسابات: {len(all_accs)}\n"
            f"• الحسابات المتصلة: {len(user_clients)}\n"
            f"• النشر: {'🟢 نشط' if is_posting_active else '🔴 متوقف'}\n"
            f"• التشفير: {'✅ مفعل' if get_setting('encryption', 'on') == 'on' else '❌ معطل'}\n"
            f"{he_line}{ft_line}"
            f"• مكافحة الكشف: {'✅ مفعلة' if get_setting('anti_detect', 'on') == 'on' else '❌ معطلة'}\n"
            f"• تشويش النص: {obf_status}\n"
            f"• 📅 منشورات مجدولة معلقة: {pending_sched}"
        )

    @bot.on(events.NewMessage(pattern='/test'))
    async def test_handler(event):
        if not is_admin(event.sender_id):
            return
        await event.respond("✅ بوت النشر الخارق 2026 يعمل!\n🎲 Spintax | 🐝 Ghost Swarm | ⚖️ Load Balancer\n〰️ كشيدة | 🔤 VS | 🏷️ Tags | 🔀 Homoglyphs | ⏱️ Human Delay")

    # 🆕 أمر اختبار التشفير
    @bot.on(events.NewMessage(pattern='/test_obfuscate'))
    async def test_obfuscate_handler(event):
        if not is_admin(event.sender_id):
            return
        test_text = "أحد عنده حرمان تبي تشيل الحرمان بدوامك ذي تسوي لكم سكليف معتمد حتى لو عندك غياب قديم الي يبي يكلمها https://wa.me/+966571482466"
        if get_setting('spintax_enabled', 'on') == 'on':
            test_text = parse_spintax("أحد عنده حرمان تبي تشيل الحرمان بدوامك ذي تسوي لكم سكليف معتمد حتى لو عندك غياب قديم الي يبي يكلمها https://wa.me/+966571482466")
        
        # اختبار التشويش الخفي
        stealth_on = get_setting('stealth_obfuscator_enabled', 'on') == 'on'
        if stealth_on:
            stealth_text, stealth_html = stealth_obfuscator.obfuscate(test_text)
            await event.respond(
                f"🔬 **اختبار التشويش الخفي StealthObfuscator**\n\n"
                f"📝 **الأصل:**\n{test_text}\n\n"
                f"🔬 **بعد التشويش الخفي:**\n{stealth_text}\n\n"
                f"💡 النص يبدو متطابقاً تماماً - الفرق غير مرئي!\n"
                f"البوتات لا تستطيع قراءة النص لأنه مليء بأحرف خفية\n\n"
                f"📊 **الأنظمة المفعلة:**\n"
                f"• 🔬 تشويش خفي: {'✅' if stealth_on else '❌'}\n"
                f"• 🛡️ التشفير: {'✅' if get_setting('encryption','on')=='on' else '❌'}\n"
                f"• 🎭 مكافحة الكشف: {'✅' if get_setting('anti_detect','on')=='on' else '❌'}\n"
                f"• 🛡️ AntiGuardian: {'✅' if get_setting('anti_guardian_enabled','on')=='on' else '❌'}\n"
                f"• 🔄 YayText: {'✅' if get_setting('yaytext_messletters_obfuscation','on')=='on' else '❌'}\n"
                f"• 🎲 Spintax: {'✅' if get_setting('spintax_enabled','on')=='on' else '❌'}\n"
                f"• 👁️ edit_hide: {'✅' if get_setting('edit_hide_enabled','on')=='on' else '❌'}\n"
                f"• 📈 Exponential Backoff: {'✅' if get_setting('exponential_backoff','on')=='on' else '❌'}",
                parse_mode='html' if stealth_html else None
            )
        else:
            encrypted, use_html = yaytext_obfuscate(test_text)
            style_name = yaytext_obfuscator.get_style_name()
            await event.respond(
                f"🧪 **اختبار التشفير القديم**\n\n"
                f"📝 الأصلي:\n{test_text}\n\n"
                f"🔒 المشفر (نمط: {style_name}):\n{encrypted}\n\n"
                f"💡 لتفعيل التشويش الخفي: اضغط زر 🔬 تشويش خفي في القائمة"
            )

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
        c.execute("SELECT id, content, media_path, msg_type, media_data FROM messages")
        msgs = c.fetchall()
        conn.close()
        if not msgs:
            await event.respond("⚠️ لا توجد رسائل! أضف رسالة أولاً")
            return
        if is_posting_active:
            await event.respond("⚠️ النشر يعمل بالفعل!")
            return
        is_posting_active = True
        fast_delay = get_setting('fast_post_delay', '3')
        await event.respond(f"⚡ بدء النشر السريع لكل المجموعات وكل الرسائل ({len(msgs)} رسالة) (كل {fast_delay} ثانية)...")
        # نمرر كل الرسائل دفعة واحدة - الدالة ستخلط ترتيبها لكل حساب
        success, fails, total = await fast_post_to_all_groups(msgs)
        is_posting_active = False
        await event.respond(f"✅ اكتمل النشر السريع!\n✅ نجاح: {success}\n❌ فشل: {fails}\n📢 من أصل {total} مجموعة\n📝 عدد الرسائل: {len(msgs)}")

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
        global is_posting_active, join_cancelled, hyper_encryption
        if not is_admin(event.sender_id):
            await event.answer("⛔ غير مصرح", alert=True)
            return
        data = event.data.decode('utf-8')

        if data == 'back':
            groups_count = await get_all_groups_count()
            message_interval = get_setting('message_interval', '3')
            join_interval = get_setting('join_interval', '30')
            pending_sched = len(get_pending_scheduled_posts())
            queue_count = len(join_queue)
            queue_info = f"\n📋 طابور الانضمام: {queue_count} رابط" if queue_count > 0 else ""
            await event.edit(
                "🛡 **لوحة التحكم**\n\n"
                f"📢 المجموعات: {groups_count}\n"
                f"⏱ مدة النشر: {message_interval} ثانية\n"
                f"🚀 فاصل الانضمام: {join_interval} ثانية\n"
                f"📅 منشورات مجدولة: {pending_sched}{queue_info}",
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
            # نمرر كل الرسائل دفعة واحدة - الدالة ستخلط ترتيبها لكل حساب
            success, fails, total = await fast_post_to_all_groups(msgs)
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
                f"🚀 فاصل الانضمام: {get_setting('join_interval', '30')} ثانية\n"
                f"📋 طابور الانضمام: {len(join_queue)} رابط\n"
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
            await event.edit("⏱ أرسل الفاصل الزمني بين الروابط (5-300 ثانية، الافتراضي: 30):\n/cancel للإلغاء")
            set_setting('awaiting_join_interval', 'true')
        elif data == 'toggle_enc':
            current = get_setting('encryption', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('encryption', new_val)
            await event.answer(f"التشفير: {'مفعل' if new_val == 'on' else 'معطل'}")
            await event.edit("⚙️ الإعدادات", buttons=get_settings_menu())
        elif data == 'toggle_stealth':
            current = get_setting('stealth_obfuscator_enabled', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('stealth_obfuscator_enabled', new_val)
            if new_val == 'on':
                example = "أحد عنده حرمان تبي تشيل الحرمان https://wa.me/+966571482466"
                stealth_text, _ = stealth_obfuscator.obfuscate(example)
                await event.answer("🔬 تشويش خفي: مفعل ✨")
                await event.edit(
                    f"🔬 **تشويش خفي StealthObfuscator: مفعل** ✅\n\n"
                    f"النص يبقى مقروءاً 100% - بدون كشيدة بدون PFB بدون homoglyphs!\n\n"
                    f"📝 **الأصل:**\n{example}\n\n"
                    f"🔬 **بعد التشويش الخفي:**\n{stealth_text}\n\n"
                    f"💡 الفرق غير مرئي للعين لكن البوتات لا تستطيع قراءته!",
                    buttons=get_main_menu()
                )
            else:
                await event.answer("🔬 تشويش خفي: معطل")
                await event.edit("🔬 **تشويش خفي StealthObfuscator: معطل** ❌\n\nالنظام القديم (AntiGuardian/YayText) سيعمل بدلاً منه.", buttons=get_main_menu())

        elif data == 'toggle_super_encryption':
            current = get_setting('super_encryption_enabled', 'off')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('super_encryption_enabled', new_val)
            if new_val == 'on':
                example = "سلام عليكم تابعونا https://wa.me/+966568479168"
                encrypted = super_encryption.super_encrypt_full(example)
                await event.answer("💎 التشفير الخارق: مفعل ✨")
                await event.edit(
                    f"💎 **التشفير الخارق Super Encryption: مفعل** ✅\n\n"
                    f"أقوى تشفير ضد بوتات الحماية!\n"
                    f"كل حرف عربي يُفصل بنمط كشيدة + فاصل + كشيدة\n"
                    f"النص مقروء بشرياً لكن مستحيل كشفه آلياً 🛡️\n\n"
                    f"📝 **الأصل:**\n{example}\n\n"
                    f"💎 **بعد التشفير الخارق:**\n{encrypted}\n\n"
                    f"💡 الفواصل تُختار عشوائياً لكل رسالة!",
                    buttons=get_main_menu()
                )
            else:
                await event.answer("💎 التشفير الخارق: معطل")
                await event.edit("💎 **التشفير الخارق: معطل** ❌\n\nسيتم استخدام التشفير العادي بدلاً منه.", buttons=get_main_menu())

        elif data == 'toggle_hyper_enc':
            current = get_setting('hyper_encryption_enabled', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('hyper_encryption_enabled', new_val)
            if new_val == 'on':
                example = "اشترك في قناتنا https://t.me/example عروض حصرية! اتصل: 0555123456"
                encrypted = encrypt_text(example, group_id=-1001234567890)
                info = hyper_encryption.get_strength_info() if hyper_encryption else {}
                from hyper_encryption import char_analysis as _ca
                counts = _ca(encrypted)
                invisible = sum(v for k, v in counts.items() if k != 'visible')
                await event.answer("🔥 HyperEncryption: مفعل ✨")
                await event.edit(
                    f"🔥 **HyperEncryptionEngine v2.1: مفعل** ✅\n\n"
                    f"محرك تشفير خارق بـ 26 طبقة متقدمة (8 طبقات جديدة!):\n"
                    f"• Homoglyph (عربي + لاتيني + أرقام)\n"
                    f"• Zero-width chars (5 أنواع)\n"
                    f"• Tatweel + Harakat عربي\n"
                    f"• Combining diacritical marks\n"
                    f"• Space variants (7 أنواع)\n"
                    f"• Directional marks (LRM/RLM)\n"
                    f"• Variation selectors\n"
                    f"• Link + Mention obfuscation\n"
                    f"• Per-group hash + trailing invisibles\n"
                    f"• Mid-word ZWSP (يكسر keyword matching)\n"
                    f"• Keyword heavy + Numeric + Punctuation subs\n"
                    f"🆕 **طبقات v2.1 الجديدة:**\n"
                    f"• L19: Tag Characters (U+E0000) - إخفاء كامل\n"
                    f"• L20: Hangul Fillers - أحرف كورية غير مرئية\n"
                    f"• L21: Bidi Isolates (FSI/PDI) - يكسر regex\n"
                    f"• L22: Math Symbols (Fraktur/Script/Double-struck)\n"
                    f"• L23: Smart Punctuation (smart quotes/dashes)\n"
                    f"• L24: Expanded Confusables Database\n"
                    f"• L25: Emoji Variation Sequences\n"
                    f"• L26: Hash-busting Padding (يكسر hash matching)\n\n"
                    f"📊 المستوى الحالي: **{info.get('level', 'medium')}** ({info.get('active_count', '?')}/{info.get('total_count', 26)} طبقة)\n\n"
                    f"📝 **الأصل:**\n{example}\n\n"
                    f"🔥 **بعد HyperEncryption** ({len(encrypted)} حرف، {invisible} غير مرئي):\n{encrypted}\n\n"
                    f"💡 النص يبدو متطابقاً بصرياً - الفرق فقط في الأحرف غير المرئية!",
                    buttons=get_main_menu()
                )
            else:
                await event.answer("🔥 HyperEncryption: معطل")
                await event.edit("🔥 **HyperEncryptionEngine: معطل** ❌\n\nسيتم استخدام UltimateAntiDetection القديم.", buttons=get_main_menu())

        elif data == 'enc_strength':
            current = get_setting('encryption_strength', 'medium')
            levels = ['light', 'medium', 'aggressive', 'insane']
            try:
                idx = levels.index(current)
            except ValueError:
                idx = 1
            new_level = levels[(idx + 1) % len(levels)]
            set_setting('encryption_strength', new_level)
            # تحديث المحرك لالتقاط الإعداد الجديد
            if hyper_encryption is not None:
                hyper_encryption.get_setting = get_setting
            info = hyper_encryption.get_strength_info() if hyper_encryption else {}
            emojis = {'light': '🟢', 'medium': '🟡', 'aggressive': '🟠', 'insane': '🔴'}
            descriptions = {
                'light': 'أخف تمويه - 9 طبقات (للحسابات الحساسة)',
                'medium': 'متوازن - 17 طبقة (افتراضي)',
                'aggressive': 'قوي - 24 طبقة (يكسر بوتات قوية)',
                'insane': 'أقصى تمويه - 26 طبقة (كل الطبقات مفعلة)',
            }
            await event.answer(f"{emojis[new_level]} قوة التشفير: {new_level}")
            await event.edit(
                f"{emojis[new_level]} **قوة التشفير: {new_level}**\n\n"
                f"📊 الطبقات المفعلة: {info.get('active_count', '?')}/{info.get('total_count', 26)}\n"
                f"📝 {descriptions[new_level]}\n\n"
                f"اضغط الزر مرة أخرى للتبديل للمستوى التالي.",
                buttons=get_main_menu()
            )

        elif data == 'enc_test':
            sample = "اشترك في قناتنا https://t.me/example عروض حصرية! اتصل: 0555123456"
            from hyper_encryption import HyperEncryptionEngine as _HEE, char_analysis as _ca
            msg = f"🧪 **اختبار HyperEncryption - 4 مستويات**\n\n📝 **النص الأصلي:**\n{sample}\n\n"
            for level in ['light', 'medium', 'aggressive', 'insane']:
                eng = _HEE(settings_getter=lambda k, d, _lvl=level: _lvl if k == 'encryption_strength' else ('on' if k == 'encryption' else get_setting(k, d)))
                enc = eng.encrypt(sample, group_id=-1001234567890, strength=level)
                counts = _ca(enc)
                invisible = sum(v for k, v in counts.items() if k != 'visible')
                emoji = {'light': '🟢', 'medium': '🟡', 'aggressive': '🟠', 'insane': '🔴'}[level]
                active_n = len(_HEE.STRENGTH_LEVELS[level])
                msg += f"{emoji} **{level.upper()}** ({active_n} طبقة، {len(enc)} حرف، {invisible} غير مرئي):\n{enc}\n\n"
            msg += "💡 كل النصوص تبدو متطابقة بصرياً مع الأصل!\n\nاختر مستوى القوة من زر 'قوة التشفير' في القائمة الرئيسية."
            await event.edit(msg, buttons=[[Button.inline("🔙 رجوع", b"back")]])

        # ═══════════════════════════════════════════════════════════
        #  ✨ Fancy Text - محرك الأنماط النصية الخارق (26 نمط)
        # ═══════════════════════════════════════════════════════════

        elif data == 'toggle_fancy_text':
            current = get_setting('fancy_text_enabled', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('fancy_text_enabled', new_val)
            current_style = get_setting('fancy_text_style', 'strikethrough')
            style_info = fancy_engine.STYLES.get(current_style, {})
            if new_val == 'on':
                example = "اشترك في قناتنا https://t.me/example عروض حصرية!"
                transformed = fancy_engine.apply_style(example, current_style)
                await event.answer("✨ Fancy Text: مفعل")
                await event.edit(
                    f"✨ **FancyTextEngine: مفعل** ✅\n\n"
                    f"محرك 26 نمط بصري مستوحى من FSymbols:\n"
                    f"• 8 أنماط تشكيل (Strikethrough/Underline/Overline...)\n"
                    f"• 4 أنماط إحاطة (Boxed/Circled/Squared/Bubble)\n"
                    f"• 9 أنماط استبدال (Fraktur/Script/Monospace...)\n"
                    f"• 5 أنماط متقدمة (Mirrored/Upside Down/Zalgo...)\n\n"
                    f"📊 النمط الحالي: **{style_info.get('name', current_style)}** ({style_info.get('ar', '')})\n\n"
                    f"📝 **الأصل:**\n{example}\n\n"
                    f"✨ **بعد التطبيق:**\n{transformed}\n\n"
                    f"💡 اختر نمطاً مختلفاً من زر 'النمط' في القائمة الرئيسية.",
                    buttons=get_main_menu()
                )
            else:
                await event.answer("✨ Fancy Text: معطل")
                await event.edit("✨ **FancyTextEngine: معطل** ❌\n\nسيتم استخدام HyperEncryption فقط.", buttons=get_main_menu())

        elif data == 'fancy_text_menu':
            # قائمة اختيار النمط - مقسمة حسب التصنيف
            current_style = get_setting('fancy_text_style', 'strikethrough')
            current_intensity = get_setting('fancy_text_zalgo_intensity', 'medium')
            # بناء الأزرار حسب التصنيف
            buttons = []
            categories = fancy_engine.get_categories()
            for cat_id, cat_name in categories.items():
                # عنوان التصنيف
                buttons.append([Button.inline(f"── {cat_name} ──", b"fancy_text_noop")])
                # أنماط هذا التصنيف (زر لكل اثنين)
                styles_in_cat = [(k, v) for k, v in fancy_engine.STYLES.items() if v['category'] == cat_id]
                row = []
                for style_id, style_info in styles_in_cat:
                    mark = "✅" if style_id == current_style else "  "
                    btn_text = f"{style_info['icon']} {style_info['name']}"
                    if len(btn_text) > 22:
                        btn_text = btn_text[:22]
                    row.append(Button.inline(btn_text, f"fts_{style_id}".encode()))
                    if len(row) == 2:
                        buttons.append(row)
                        row = []
                if row:
                    buttons.append(row)
            # شريط التحكم بالشدة لـ Zalgo
            buttons.append([Button.inline(f"⚡ شدة Zalgo: {current_intensity}", b"fancy_text_zalgo_level")])
            buttons.append([Button.inline("🔙 رجوع للقائمة الرئيسية", b"back")])
            await event.edit(
                f"✨ **اختيار نمط Fancy Text**\n\n"
                f"📊 النمط الحالي: **{fancy_engine.STYLES.get(current_style, {}).get('name', current_style)}**\n"
                f"⚡ شدة Zalgo: **{current_intensity}**\n\n"
                f"اختر نمطاً من القائمة أدناه:",
                buttons=buttons
            )

        elif data == 'fancy_text_zalgo_level':
            current = get_setting('fancy_text_zalgo_intensity', 'medium')
            levels = ['light', 'medium', 'heavy', 'insane']
            try:
                idx = levels.index(current)
            except ValueError:
                idx = 1
            new_level = levels[(idx + 1) % len(levels)]
            set_setting('fancy_text_zalgo_intensity', new_level)
            await event.answer(f"⚡ شدة Zalgo: {new_level}")
            # إعادة عرض قائمة Fancy Text
            current_style = get_setting('fancy_text_style', 'strikethrough')
            buttons = []
            categories = fancy_engine.get_categories()
            for cat_id, cat_name in categories.items():
                buttons.append([Button.inline(f"── {cat_name} ──", b"fancy_text_noop")])
                styles_in_cat = [(k, v) for k, v in fancy_engine.STYLES.items() if v['category'] == cat_id]
                row = []
                for style_id, style_info in styles_in_cat:
                    mark = "✅" if style_id == current_style else "  "
                    btn_text = f"{style_info['icon']} {style_info['name']}"
                    if len(btn_text) > 22:
                        btn_text = btn_text[:22]
                    row.append(Button.inline(btn_text, f"fts_{style_id}".encode()))
                    if len(row) == 2:
                        buttons.append(row)
                        row = []
                if row:
                    buttons.append(row)
            buttons.append([Button.inline(f"⚡ شدة Zalgo: {new_level}", b"fancy_text_zalgo_level")])
            buttons.append([Button.inline("🔙 رجوع للقائمة الرئيسية", b"back")])
            await event.edit(
                f"✨ **اختيار نمط Fancy Text**\n\n"
                f"📊 النمط الحالي: **{fancy_engine.STYLES.get(current_style, {}).get('name', current_style)}**\n"
                f"⚡ شدة Zalgo: **{new_level}**\n\n"
                f"اختر نمطاً من القائمة أدناه:",
                buttons=buttons
            )

        elif data == 'fancy_text_noop':
            # زر غير قابل للنقر (عنوان فقط)
            await event.answer("علامة تبويب", alert=False)

        elif data == 'fancy_text_preview':
            # معاينة كل الأنماط على نص تجريبي
            sample = "اشترك في قناتنا https://t.me/example عروض حصرية! Hello World"
            current_style = get_setting('fancy_text_style', 'strikethrough')
            current_intensity = get_setting('fancy_text_zalgo_intensity', 'medium')
            msg = f"🧪 **معاينة كل الأنماط (26 نمط)**\n\n📝 **النص الأصلي:**\n{sample}\n\n"
            categories = fancy_engine.get_categories()
            for cat_id, cat_name in categories.items():
                msg += f"\n📂 **{cat_name}**\n"
                styles_in_cat = [(k, v) for k, v in fancy_engine.STYLES.items() if v['category'] == cat_id]
                for style_id, style_info in styles_in_cat:
                    try:
                        if style_id == 'zalgo':
                            transformed = fancy_engine.zalgo(sample, intensity=current_intensity)
                        else:
                            transformed = fancy_engine.apply_style(sample, style_id)
                        mark = "✅" if style_id == current_style else "  "
                        msg += f"\n{mark} {style_info['icon']} **{style_info['name']}** ({style_info['ar']}):\n{transformed}\n"
                    except Exception as e:
                        msg += f"\n❌ {style_info['name']}: خطأ - {e}\n"
            msg += f"\n💡 النمط الحالي محدد بـ ✅. اضغط 'اختيار النمط' للتغيير."
            await event.edit(
                msg,
                buttons=[
                    [Button.inline("🎯 اختيار نمط", b"fancy_text_menu"),
                     Button.inline("⚡ شدة Zalgo", b"fancy_text_zalgo_level")],
                    [Button.inline("🔙 رجوع", b"back")]
                ]
            )

        elif data.startswith('fts_'):
            # اختيار نمط معين
            style_id = data[4:]  # إزالة بادئة 'fts_'
            if style_id in fancy_engine.STYLES:
                set_setting('fancy_text_style', style_id)
                style_info = fancy_engine.STYLES[style_id]
                # تطبيق النمط على نص تجريبي
                example = "اشترك في قناتنا https://t.me/example عروض حصرية! Hello"
                if style_id == 'zalgo':
                    intensity = get_setting('fancy_text_zalgo_intensity', 'medium')
                    transformed = fancy_engine.zalgo(example, intensity=intensity)
                else:
                    transformed = fancy_engine.apply_style(example, style_id)
                await event.answer(f"✅ تم اختيار: {style_info['name']}")
                await event.edit(
                    f"✅ **تم اختيار النمط: {style_info['name']}**\n\n"
                    f"📊 الوصف: {style_info['ar']}\n"
                    f"📂 التصنيف: {fancy_engine.get_categories().get(style_info['category'], '')}\n\n"
                    f"📝 **النص الأصلي:**\n{example}\n\n"
                    f"✨ **بعد التطبيق ({style_info['name']}):**\n{transformed}\n\n"
                    f"💡 هذا النمط سيُطبق على كل الإعلانات المنشورة.",
                    buttons=[
                        [Button.inline("🧪 معاينة كل الأنماط", b"fancy_text_preview"),
                         Button.inline("🎯 اختيار نمط آخر", b"fancy_text_menu")],
                        [Button.inline("🔙 رجوع للقائمة الرئيسية", b"back")]
                    ]
                )

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

        # 🆕 تبديل Spintax
        elif data == 'toggle_spintax':
            current = get_setting('spintax_enabled', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('spintax_enabled', new_val)
            await event.answer(f"Spintax: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}")
            await event.edit(
                f"🎲 **Spintax: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}**\n\n"
                f"📝 **صيغة Spintax:** {{خيار1|خيار2|خيار3}}\n"
                f"مثال: {{مرحباً|أهلاً|سلام}} بكم في {{قناتنا|مجموعتنا}}\n\n"
                f"كل رسالة تُرسل تختار خيارات مختلفة تلقائياً\n"
                f"→ بوتات الحماية لا تجد نفس النص مرتين أبداً!",
                buttons=get_main_menu()
            )

        # 🆕 تبديل كشيدة
        elif data == 'toggle_kashida':
            current = get_setting('kashida_enabled', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('kashida_enabled', new_val)
            await event.answer(f"كشيدة: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}")
            await event.edit(
                f"〰️ **كشيدة/Tatweel: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}**\n\n"
                f"أقوى طبقة تشفير عربية - تبقى بعد كل أنواع التطبيع!\n"
                f"تضيف أحرف ـ (Tatweel U+0640) بين الحروف العربية\n"
                f"→ النص يبقى مقروءاً طبيعياً\n"
                f"→ بوتات الحماية لا تستطيع إزالتها",
                buttons=get_main_menu()
            )

        # 🆕 تبديل Arabic Homoglyphs
        elif data == 'toggle_arabic_homoglyph':
            current = get_setting('arabic_homoglyph_enabled', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('arabic_homoglyph_enabled', new_val)
            await event.answer(f"Homoglyphs عربي: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}")
            await event.edit(
                f"🔀 **Homoglyphs عربي: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}**\n\n"
                f"يبدل الأحرف العربية ببدائل متطابقة مرئياً:\n"
                f"• ا ↔ أ ↔ إ ↔ آ ↔ ٱ\n"
                f"• ه ↔ ة ↔ ھ\n"
                f"• ي ↔ ى ↔ ئ\n"
                f"• و ↔ ؤ\n"
                f"→ تبدو نفس الحروف لكن بكود Unicode مختلف!",
                buttons=get_main_menu()
            )

        # 🆕 تبديل Variation Selectors
        elif data == 'toggle_vs':
            current = get_setting('variation_selectors_enabled', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('variation_selectors_enabled', new_val)
            await event.answer(f"Variation Selectors: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}")
            await event.edit(
                f"🔤 **Variation Selectors: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}**\n\n"
                f"أحرف تجميع غير مرئية (VS1-VS16)\n"
                f"تُضاف بعد الحروف العربية بشكل عشوائي\n"
                f"→ غير مرئية تماماً للمستخدم\n"
                f"→ تبقى بعد تطبيع Unicode",
                buttons=get_main_menu()
            )

        # 🆕 تبديل Tag Characters
        elif data == 'toggle_tag':
            current = get_setting('tag_characters_enabled', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('tag_characters_enabled', new_val)
            await event.answer(f"Tag Characters: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}")
            await event.edit(
                f"🏷️ **Tag Characters: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}**\n\n"
                f"أحرف Unicode Tag (U+E0000+) مخفية تماماً\n"
                f"تُضاف في بداية ونهاية النص\n"
                f"→ غير مرئية للمستخدم\n"
                f"→ تُغيّر بصمة النص كلياً",
                buttons=get_main_menu()
            )

        # 🆕 تبديل Ghost Swarm
        elif data == 'toggle_ghost_swarm':
            current = get_setting('ghost_swarm_enabled', 'off')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('ghost_swarm_enabled', new_val)
            stages = get_setting('ghost_swarm_stages', '3')
            interval = get_setting('ghost_swarm_interval', '10')
            await event.answer(f"Ghost Swarm: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}")
            await event.edit(
                f"🐝 **Ghost Swarm: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}**\n\n"
                f"نظام سرب الأشباح: تعديلات متتالية بتكويد مختلف\n"
                f"• المراحل: {stages} تعديلات متتالية\n"
                f"• الفاصل: كل {interval} ثانية\n"
                f"• كل مرحلة تستخدم نمط تشفير مختلف\n"
                f"• مع edit_hide لا تظهر علامة 'معدّل'!\n\n"
                f"→ بوتات الحماية تحلل الرسالة بعد كل تعديل = لا تجد نفس النمط أبداً!",
                buttons=get_main_menu()
            )

        # 🆕 تبديل Human Delay
        elif data == 'toggle_human_delay':
            current = get_setting('human_delay_enabled', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('human_delay_enabled', new_val)
            min_d = get_setting('human_delay_min', '3')
            max_d = get_setting('human_delay_max', '15')
            await event.answer(f"Human Delay: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}")
            await event.edit(
                f"⏱️ **Human Delay: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}**\n\n"
                f"محاكاة تأخير بشري واقعي:\n"
                f"• التأخير: {min_d}-{max_d} ثانية عشوائية\n"
                f"• 10% احتمال توقف أطول (محاكاة تشتت)\n"
                f"• 5% احتمال إرسال سريع\n\n"
                f"→ يمنع بوتات الحماية من كشف النمط الآلي!",
                buttons=get_main_menu()
            )

        # 🆕 تبديل Load Balancer
        elif data == 'toggle_load_balancer':
            current = get_setting('load_balancer_enabled', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('load_balancer_enabled', new_val)
            await event.answer(f"Load Balancer: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}")
            await event.edit(
                f"⚖️ **Load Balancer: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}**\n\n"
                f"توزيع ذكي للرسائل عبر الحسابات:\n"
                f"• الحد: 40 رسالة/ساعة و 10/دقيقة لكل حساب\n"
                f"• يختار الحساب الأقل استخداماً تلقائياً\n\n"
                f"→ يمنع حظر الحسابات ويقلل FloodWait!",
                buttons=get_main_menu()
            )

        # 🆕 إعدادات التشفير المتقدمة
        elif data == 'advanced_enc_settings':
            kashida_i = get_setting('kashida_intensity', '0.3')
            swarm_s = get_setting('ghost_swarm_stages', '3')
            swarm_i = get_setting('ghost_swarm_interval', '10')
            hd_min = get_setting('human_delay_min', '3')
            hd_max = get_setting('human_delay_max', '15')
            rtlo_s = "✅" if get_setting('rtlo_enabled', 'off') == 'on' else "❌"
            eh_s = "✅" if get_setting('edit_hide_enabled', 'on') == 'on' else "❌"
            eb_s = "✅" if get_setting('exponential_backoff', 'on') == 'on' else "❌"
            await event.edit(
                f"🛡️ **إعدادات التشفير المتقدمة**\n\n"
                f"〰️ كثافة الكشيدة: {kashida_i}\n"
                f"🐝 مراحل Swarm: {swarm_s}\n"
                f"🐝 فاصل Swarm: {swarm_i}ث\n"
                f"⏱️ Human Delay: {hd_min}-{hd_max}ث\n"
                f"↔️ RTLO: {rtlo_s}\n"
                f"👁️ edit_hide: {eh_s}\n"
                f"📈 Exponential Backoff: {eb_s}",
                buttons=[
                    [Button.inline("〰️ كثافة الكشيدة", b"set_kashida_intensity")],
                    [Button.inline("🐝 مراحل Swarm", b"set_swarm_stages"),
                     Button.inline("🐝 فاصل Swarm", b"set_swarm_interval")],
                    [Button.inline("⏱️ Human Delay Min", b"set_hd_min"),
                     Button.inline("⏱️ Human Delay Max", b"set_hd_max")],
                    [Button.inline(f"↔️ RTLO {rtlo_s}", b"toggle_rtlo"),
                     Button.inline(f"👁️ edit_hide {eh_s}", b"toggle_edit_hide"),
                     Button.inline(f"📈 Backoff {eb_s}", b"toggle_backoff")],
                    [Button.inline("🔙 رجوع", b"back")],
                ]
            )

        # 🆕 معالجات الإعدادات المتقدمة
        elif data == 'set_kashida_intensity':
            set_setting('awaiting_kashida_intensity', 'true')
            await event.edit("〰️ أرسل كثافة الكشيدة (0.1 - 0.8):\nمثال: 0.3\n/cancel للإلغاء")
        elif data == 'set_swarm_stages':
            set_setting('awaiting_swarm_stages', 'true')
            await event.edit("🐝 أرسل عدد مراحل Swarm (1-10):\nمثال: 3\n/cancel للإلغاء")
        elif data == 'set_swarm_interval':
            set_setting('awaiting_swarm_interval', 'true')
            await event.edit("🐝 أرسل فاصل Swarm بالثواني (5-120):\nمثال: 10\n/cancel للإلغاء")
        elif data == 'set_hd_min':
            set_setting('awaiting_hd_min', 'true')
            await event.edit("⏱️ أرسل الحد الأدنى لـ Human Delay بالثواني (1-30):\nمثال: 3\n/cancel للإلغاء")
        elif data == 'set_hd_max':
            set_setting('awaiting_hd_max', 'true')
            await event.edit("⏱️ أرسل الحد الأقصى لـ Human Delay بالثواني (5-60):\nمثال: 15\n/cancel للإلغاء")
        elif data == 'toggle_rtlo':
            current = get_setting('rtlo_enabled', 'off')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('rtlo_enabled', new_val)
            await event.answer(f"RTLO: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}")
            await event.edit(f"↔️ **RTLO: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}**\n⚠️ قد يؤثر على عرض النص!", buttons=[[Button.inline("🔙 رجوع", b"advanced_enc_settings")]])
        elif data == 'toggle_edit_hide':
            current = get_setting('edit_hide_enabled', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('edit_hide_enabled', new_val)
            await event.answer(f"edit_hide: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}")
            await event.edit(f"👁️ **edit_hide: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}**\nيخفي علامة 'معدّل' عند تعديل الرسائل!", buttons=[[Button.inline("🔙 رجوع", b"advanced_enc_settings")]])
        elif data == 'toggle_backoff':
            current = get_setting('exponential_backoff', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('exponential_backoff', new_val)
            await event.answer(f"Exponential Backoff: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}")
            await event.edit(f"📈 **Exponential Backoff: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}**\nتراجع أسي ذكي عند FloodWait!", buttons=[[Button.inline("🔙 رجوع", b"advanced_enc_settings")]])

        # 🛡️ إعدادات AntiGuardian - تجاوز بوتات الحماية المتقدمة
        elif data == 'anti_guardian_settings':
            ag_status = "✅" if get_setting('anti_guardian_enabled', 'on') == 'on' else "❌"
            fw_status = "✅" if get_setting('fullwidth_latin_enabled', 'on') == 'on' else "❌"
            le_status = "✅" if get_setting('latin_extended_enabled', 'on') == 'on' else "❌"
            ag_mode = get_setting('anti_guardian_mode', 'smart')
            mode_labels = {'smart': 'ذكي 🧠', 'stealth': 'خفي 👻', 'aggressive': 'عدواني ⚔️'}
            await event.edit(
                f"🛡️ **AntiGuardian - تجاوز بوتات الحماية**\n\n"
                f"🎯 البوتات المستهدفة:\n"
                f"  @GoldenkidKbot @GHClone3Bot\n"
                f"  @Deevill07bot @GHSecurity2Bot\n"
                f"  @Jabal_RoBot @PMU_Securitybot\n"
                f"  @TaifUniTu1_BoT72638\n\n"
                f"🔄 النظام: {ag_status}\n"
                f"🧠 الوضع: {mode_labels.get(ag_mode, ag_mode)}\n"
                f"🔤 Fullwidth Latin: {fw_status}\n"
                f"🔤 Latin Extended: {le_status}\n\n"
                f"📋 **التقنيات المستخدمة:**\n"
                f"  1️⃣ Fullwidth Latin (لا يكشفه isMultiLang!)\n"
                f"  2️⃣ Latin Extended-A/B (تبدو لاتينية عادية)\n"
                f"  3️⃣ تشويش كلمات مفتاحية عربية\n"
                f"  4️⃣ كشيدة + NFD + Homoglyphs عربي\n"
                f"  5️⃣ إخفاء الروابط في HTML TextUrl\n"
                f"  6️⃣ أحرف غير مرئية + مسافات بديلة\n"
                f"  7️⃣ Variation Selectors + Tag Chars\n"
                f"  8️⃣ تحويل أرقام آمن",
                buttons=[
                    [Button.inline(f"🔄 AntiGuardian {ag_status}", b"toggle_anti_guardian"),
                     Button.inline(f"🧠 الوضع: {mode_labels.get(ag_mode, ag_mode)}", b"cycle_ag_mode")],
                    [Button.inline(f"🔤 Fullwidth {fw_status}", b"toggle_fullwidth"),
                     Button.inline(f"🔤 Latin Ext {le_status}", b"toggle_latin_ext")],
                    [Button.inline("🔙 رجوع", b"back")],
                ]
            )
        elif data == 'toggle_anti_guardian':
            current = get_setting('anti_guardian_enabled', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('anti_guardian_enabled', new_val)
            await event.answer(f"AntiGuardian: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}")
            # إعادة عرض صفحة AntiGuardian
            await event.click(data='anti_guardian_settings')
        elif data == 'toggle_fullwidth':
            current = get_setting('fullwidth_latin_enabled', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('fullwidth_latin_enabled', new_val)
            await event.answer(f"Fullwidth Latin: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}")
            await event.click(data='anti_guardian_settings')
        elif data == 'toggle_latin_ext':
            current = get_setting('latin_extended_enabled', 'on')
            new_val = 'off' if current == 'on' else 'on'
            set_setting('latin_extended_enabled', new_val)
            await event.answer(f"Latin Extended: {'مفعل ✅' if new_val == 'on' else 'معطل ❌'}")
            await event.click(data='anti_guardian_settings')
        elif data == 'cycle_ag_mode':
            modes = ['smart', 'stealth', 'aggressive']
            current = get_setting('anti_guardian_mode', 'smart')
            idx = modes.index(current) if current in modes else 0
            new_mode = modes[(idx + 1) % len(modes)]
            set_setting('anti_guardian_mode', new_mode)
            mode_labels = {'smart': 'ذكي 🧠', 'stealth': 'خفي 👻', 'aggressive': 'عدواني ⚔️'}
            await event.answer(f"الوضع: {mode_labels[new_mode]}")
            await event.click(data='anti_guardian_settings')

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
                f"🔗 انضمام: {join_stats['total']} (✅{join_stats['success']} ⏭{join_stats.get('skipped', 0)} ❌{join_stats['failed']})\n"
                f"🎭 تشويش النص: {obf_status}\n"
                f"📅 مجدولة: {sched_count}",
                buttons=[[Button.inline("🔙 رجوع", b"back")]]
            )

        elif data == 'auto_join':
            acc_count = len(user_clients)
            join_interval = get_setting('join_interval', '30')
            queue_count = len(join_queue)
            queue_info = f"\n  📋 روابط في الطابور: {queue_count}" if queue_count > 0 else ""
            await event.edit(
                f"🚀 **الانضمام التلقائي**\n\n"
                f"📤 أرسل الروابط مباشرة (يدعم مئات الروابط)\n"
                f"🔗 الأنواع المدعومة:\n"
                f"  • https://t.me/channel\n"
                f"  • https://t.me/+invite\n"
                f"  • https://t.me/joinchat/xxx\n"
                f"  • @username\n"
                f"\n📊 الإعدادات:\n"
                f"  ⏱ الفاصل بين الروابط: {join_interval}ث\n"
                f"  👥 حسابات متاحة: {acc_count}{queue_info}\n\n"
                f"💡 أرسل الروابط الآن /cancel للإلغاء\n"
                f"💡 الروابط تُحفظ في الطابور تلقائياً إذا كان هناك انضمام جاري"
            )
            set_setting('awaiting_auto_join', 'true')
        elif data == 'stop_joining':
            join_cancelled = True
            await event.edit("⏹ جاري إيقاف الانضمام...", buttons=get_main_menu())
        elif data == 'join_settings':
            await event.edit("🔗 **إعدادات الانضمام**", buttons=get_join_settings_menu())
        elif data == 'join_reports':
            await event.edit("🔗 **تقارير الانضمام**", buttons=get_join_reports_menu())
        elif data == 'join_stats':
            stats = get_join_stats()
            success = stats['success']
            skipped = stats['skipped']
            failed = stats['failed']
            total = success + skipped + failed
            await event.edit(
                f"📊 **إحصائيات الانضمام**\n\n"
                f"📌 المجموع: {total}\n"
                f"✅ نجاح: {success}\n"
                f"⏭ تخطي (منضم): {skipped}\n"
                f"❌ فشل: {failed}\n"
                f"📈 نسبة النجاح: {(success / max(total, 1)) * 100:.1f}%",
                buttons=get_join_reports_menu()
            )
        elif data == 'join_history':
            history = get_join_history(30)
            if not history:
                await event.edit("📭 لا توجد سجلات", buttons=get_join_reports_menu())
            else:
                text = "🔗 **آخر عمليات الانضمام:**\n\n"
                for link, group_name, joined_at, joined_by, status in history[:15]:
                    if status in ('success', 'success_retry', 'success_after_wait'):
                        icon = "✅"
                    elif status == 'skipped':
                        icon = "⏭"
                    elif status.startswith('flood_wait'):
                        icon = "⏸"
                    else:
                        icon = "❌"
                    text += f"{icon} {group_name[:25]}\n   🔗 {link[:40]}\n   👤 {joined_by}\n\n"
                await event.edit(text, buttons=get_join_reports_menu())
        elif data == 'set_join_limit':
            # تم إزالة حد الساعة - الحسابات تنظم بدون حد
            await event.edit("✅ لا يوجد حد على عدد الانضمامات - الحسابات تنظم بلا قيود\nالفاصل الزمني فقط هو المحدد", buttons=get_join_settings_menu())
        elif data == 'toggle_join_human_delay':
            # تم إزالة التأخير البشري - فقط الفاصل الزمني
            await event.edit("✅ التأخير البشري تمت إزالته\nيُستخدم فقط الفاصل الزمني المحدد بين الروابط", buttons=get_join_settings_menu())
        elif data == 'view_join_queue':
            queue_count = len(join_queue)
            if queue_count == 0:
                await event.edit("📋 **طابور الروابط**\n\n✅ الطابور فارغ\n💡 أرسل روابط أثناء عملية انضمام جارية وستُحفظ في الطابور تلقائياً", buttons=get_join_settings_menu())
            else:
                text = f"📋 **طابور الروابط**\n\n🔢 عدد الروابط: {queue_count}\n\n"
                for idx, link in enumerate(join_queue[:20], 1):
                    text += f"{idx}. {link[:50]}\n"
                if queue_count > 20:
                    text += f"\n... و{queue_count - 20} رابط آخر"
                await event.edit(text, buttons=get_join_settings_menu())

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
                set_setting('join_interval', '30')
                set_setting('join_per_account_limit', '15')
                set_setting('join_human_delay', 'on')
                set_setting('encryption', 'on')
                set_setting('anti_detect', 'on')
                set_setting('obfuscation_enabled', 'on')
                set_setting('yaytext_messletters_obfuscation', 'on')
                set_setting('super_encryption_enabled', 'off')
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
                       'awaiting_slow_join', 'awaiting_auto_join', 'awaiting_join_limit', 'awaiting_del_msg', 'awaiting_del_acc',
                       'awaiting_msg_interval', 'awaiting_join_interval',
                       'awaiting_fast_delay', 'awaiting_add_blacklist', 'awaiting_del_blacklist',
                       'awaiting_schedule', 'awaiting_schedule_delete',
                       'awaiting_kashida_intensity', 'awaiting_swarm_stages',
                       'awaiting_swarm_interval', 'awaiting_hd_min', 'awaiting_hd_max']:
                set_setting(key, '')
            if event.sender_id in temp_sessions:
                try:
                    await temp_sessions[event.sender_id]["client"].disconnect()
                except:
                    pass
                del temp_sessions[event.sender_id]
            await event.respond("تم الإلغاء", buttons=get_main_menu())
            return

        # ═══════════════════════════════════════════
        #  🔴 أولوية قصوى: إضافة حساب (phone/code/password)
        #  يجب أن تكون أول شيء يُفحص لمنع اعتراض الرسالة
        # ═══════════════════════════════════════════

        # إضافة حساب - رقم الهاتف
        if get_setting('awaiting_phone') == 'true':
            set_setting('awaiting_phone', '')
            phone = event.raw_text.strip()
            # تنظيف الرقم: إزالة المسافات والشرطات
            phone_clean = re.sub(r'[\s\-\(\)]', '', phone)
            if not re.match(r'^\+?\d{8,15}$', phone_clean):
                await event.respond("❌ رقم غير صالح! مثال: +966512345678\nأعد الإرسال أو /cancel")
                set_setting('awaiting_phone', 'true')  # إعادة التفعيل للمحاولة مرة أخرى
                return
            try:
                client = TelegramClient(StringSession(), API_ID, API_HASH)
                await client.connect()
                result = await client.send_code_request(phone_clean)
                temp_sessions[event.sender_id] = {
                    "phone": phone_clean,
                    "client": client,
                    "phone_code_hash": result.phone_code_hash
                }
                set_setting('awaiting_code', 'true')
                await event.respond(f"📩 تم إرسال الرمز إلى {phone_clean}\nأرسل الرمز:")
            except Exception as e:
                error_msg = str(e)[:300]
                await event.respond(f"❌ خطأ: {error_msg}\n\n💡 جرب مرة أخرى أو /cancel")
                set_setting('awaiting_phone', 'true')  # إعادة التفعيل للمحاولة مرة أخرى
            return

        # إضافة حساب - رمز التحقق
        if get_setting('awaiting_code') == 'true':
            set_setting('awaiting_code', '')
            code = event.raw_text.strip()
            session_data = temp_sessions.get(event.sender_id)
            if not session_data:
                await event.respond("❌ انتهت الجلسة! اضغط إضافة حساب مرة أخرى", buttons=get_main_menu())
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
                await event.respond("🔐 الحساب محمي بكلمة مرور\nأرسل كلمة المرور:")
            except PhoneCodeInvalidError:
                await event.respond("❌ رمز غير صحيح! أعد الإرسال:")
                set_setting('awaiting_code', 'true')  # إعادة التفعيل للمحاولة مرة أخرى
            except PhoneCodeExpiredError:
                await event.respond("❌ انتهت صلاحية الرمز! اضغط إضافة حساب مرة أخرى", buttons=get_main_menu())
            except FloodWaitError as e:
                await event.respond(f"⏸ انتظر {e.seconds} ثانية ثم حاول مرة أخرى")
            except Exception as e:
                error_msg = str(e)[:300]
                await event.respond(f"❌ خطأ: {error_msg}\n\n💡 حاول مرة أخرى أو /cancel")
                set_setting('awaiting_code', 'true')
            return

        # إضافة حساب - كلمة المرور
        if get_setting('awaiting_password') == 'true':
            set_setting('awaiting_password', '')
            password = event.raw_text.strip()
            session_data = temp_sessions.get(event.sender_id)
            if not session_data:
                await event.respond("❌ انتهت الجلسة! اضغط إضافة حساب مرة أخرى", buttons=get_main_menu())
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
                error_msg = str(e)[:300]
                await event.respond(f"❌ خطأ: {error_msg}\n\n💡 حاول مرة أخرى أو /cancel")
                set_setting('awaiting_password', 'true')
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

        # 🆕 كثافة الكشيدة
        if get_setting('awaiting_kashida_intensity') == 'true':
            set_setting('awaiting_kashida_intensity', '')
            try:
                val = float(event.raw_text.strip())
                if 0.1 <= val <= 0.8:
                    set_setting('kashida_intensity', str(val))
                    await event.respond(f"✅ تم ضبط كثافة الكشيدة إلى {val}", buttons=get_main_menu())
                else:
                    await event.respond("❌ بين 0.1 و 0.8", buttons=get_main_menu())
            except:
                await event.respond("❌ أرسل رقماً عشرياً", buttons=get_main_menu())
            return

        # 🆕 مراحل Swarm
        if get_setting('awaiting_swarm_stages') == 'true':
            set_setting('awaiting_swarm_stages', '')
            try:
                val = int(event.raw_text.strip())
                if 1 <= val <= 10:
                    set_setting('ghost_swarm_stages', str(val))
                    await event.respond(f"✅ تم ضبط مراحل Swarm إلى {val}", buttons=get_main_menu())
                else:
                    await event.respond("❌ بين 1 و 10", buttons=get_main_menu())
            except:
                await event.respond("❌ أرسل رقماً صحيحاً", buttons=get_main_menu())
            return

        # 🆕 فاصل Swarm
        if get_setting('awaiting_swarm_interval') == 'true':
            set_setting('awaiting_swarm_interval', '')
            try:
                val = int(event.raw_text.strip())
                if 5 <= val <= 120:
                    set_setting('ghost_swarm_interval', str(val))
                    await event.respond(f"✅ تم ضبط فاصل Swarm إلى {val} ثانية", buttons=get_main_menu())
                else:
                    await event.respond("❌ بين 5 و 120", buttons=get_main_menu())
            except:
                await event.respond("❌ أرسل رقماً صحيحاً", buttons=get_main_menu())
            return

        # 🆕 Human Delay Min
        if get_setting('awaiting_hd_min') == 'true':
            set_setting('awaiting_hd_min', '')
            try:
                val = int(event.raw_text.strip())
                if 1 <= val <= 30:
                    set_setting('human_delay_min', str(val))
                    await event.respond(f"✅ تم ضبط الحد الأدنى لـ Human Delay إلى {val} ثانية", buttons=get_main_menu())
                else:
                    await event.respond("❌ بين 1 و 30", buttons=get_main_menu())
            except:
                await event.respond("❌ أرسل رقماً صحيحاً", buttons=get_main_menu())
            return

        # 🆕 Human Delay Max
        if get_setting('awaiting_hd_max') == 'true':
            set_setting('awaiting_hd_max', '')
            try:
                val = int(event.raw_text.strip())
                if 5 <= val <= 60:
                    set_setting('human_delay_max', str(val))
                    await event.respond(f"✅ تم ضبط الحد الأقصى لـ Human Delay إلى {val} ثانية", buttons=get_main_menu())
                else:
                    await event.respond("❌ بين 5 و 60", buttons=get_main_menu())
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
                if 5 <= val <= 300:
                    set_setting('join_interval', str(val))
                    await event.respond(f"✅ تم ضبط الفاصل بين الروابط إلى {val} ثانية", buttons=get_main_menu())
                else:
                    await event.respond("❌ بين 5 و 300 ثانية", buttons=get_main_menu())
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

        # 🆕 حد الانضمام لكل حساب
        if get_setting('awaiting_join_limit') == 'true':
            set_setting('awaiting_join_limit', '')
            try:
                val = int(event.raw_text.strip())
                if 5 <= val <= 50:
                    set_setting('join_per_account_limit', str(val))
                    await event.respond(f"✅ تم ضبط حد الانضمام إلى {val} لكل حساب/ساعة", buttons=get_main_menu())
                else:
                    await event.respond("❌ بين 5 و 50", buttons=get_main_menu())
            except:
                await event.respond("❌ رقم غير صالح", buttons=get_main_menu())
            return

        # ═══════════════════════════════════════════
        #  🟡 أولوية ثانية: إضافة رسالة (قبل الروابط!)
        #  يجب أن يكون قبل كشف الروابط التلقائي
        # ═══════════════════════════════════════════

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

        # 🚀 الانضمام التلقائي المتقدم
        if get_setting('awaiting_auto_join') == 'true':
            set_setting('awaiting_auto_join', '')
            # استخراج الروابط المتقدمة
            extracted_links = extract_telegram_links(event.raw_text)
            # محاولة بسيطة: كل سطر يحتوي على t.me/
            if not extracted_links:
                extracted_links = [l.strip() for l in event.raw_text.split('\n') if l.strip() and 't.me/' in l]
            if extracted_links:
                progress_msg = await event.respond(
                    f"🚀 **بدء الانضمام التلقائي**\n\n"
                    f"📡 تم اكتشاف {len(extracted_links)} رابط\n"
                    f"👥 حسابات متاحة: {len(user_clients)}\n"
                    f"⏱ الفاصل الزمني: {get_setting('join_interval', '30')}ث\n\n"
                    f"⏳ جاري المعالجة..."
                )
                # دالة تحديث التقدم
                async def update_progress(text):
                    try:
                        await progress_msg.edit(text)
                    except:
                        pass
                
                success, failed, skipped, result_msg = await auto_join_links(extracted_links, progress_callback=update_progress)
                try:
                    await progress_msg.edit(result_msg, buttons=get_main_menu())
                except:
                    await event.respond(result_msg, buttons=get_main_menu())
            else:
                await event.respond("❌ لم يتم العثور على روابط تيليجرام صالحة\n💡 أرسل الروابط مرة أخرى أو /cancel", buttons=get_main_menu())
                set_setting('awaiting_auto_join', 'true')  # إعادة التفعيل
            return

        # الروابط - انضمام تلقائي مباشر (إرسال روابط بدون الضغط على زر)
        # فقط إذا لم يكن هناك أي حالة انتظار مفعلة
        any_awaiting = any(get_setting(k) == 'true' for k in [
            'awaiting_msg', 'awaiting_phone', 'awaiting_code', 'awaiting_password',
            'awaiting_auto_join', 'awaiting_join_limit', 'awaiting_slow_join',
            'awaiting_del_msg', 'awaiting_del_acc', 'awaiting_msg_interval',
            'awaiting_join_interval', 'awaiting_fast_delay', 'awaiting_add_blacklist',
            'awaiting_del_blacklist', 'awaiting_schedule', 'awaiting_schedule_delete'
        ])
        if not any_awaiting and user_clients and not is_joining_active:
            auto_detected_links = extract_telegram_links(event.raw_text)
            # إذا كانت الرسالة تحتوي على رابط تيليجرام واحد أو أكثر - انضمام تلقائي فوري
            if len(auto_detected_links) >= 1:
                progress_msg = await event.respond(
                    f"🚀 **انضمام تلقائي**\n\n"
                    f"📡 تم اكتشاف {len(auto_detected_links)} رابط\n"
                    f"👥 حسابات: {len(user_clients)}\n"
                    f"⏱ الفاصل الزمني: {get_setting('join_interval', '30')}ث\n\n"
                    f"⏳ جاري المعالجة..."
                )
                async def update_progress2(text):
                    try:
                        await progress_msg.edit(text)
                    except:
                        pass
                
                success, failed, skipped, result_msg = await auto_join_links(auto_detected_links, progress_callback=update_progress2)
                try:
                    await progress_msg.edit(result_msg, buttons=get_main_menu())
                except:
                    await event.respond(result_msg, buttons=get_main_menu())
                return
        
        # إذا كانت هناك روابط لكن عملية انضمام جارية بالفعل - أضفها للطابور
        if not any_awaiting and is_joining_active:
            auto_detected_links = extract_telegram_links(event.raw_text)
            if len(auto_detected_links) >= 1:
                join_queue.extend(auto_detected_links)
                await event.respond(f"📋 **تم إضافة {len(auto_detected_links)} رابط للطابور**\n\n⏳ عملية انضمام جارية - سيتم الانضمام للروابط تلقائياً بعد الانتهاء\n📋 إجمالي الطابور: {len(join_queue)} رابط")
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
