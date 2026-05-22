"""
بوت النشر الخارق v4.0 - Super Poster Bot
نسخة الاستضافة السحابية (Render / Railway)
جميع الإعدادات الحساسة تُقرأ من متغيرات البيئة
"""

import os
import re
import ast
import json
import time
import random
import string
import sqlite3
import asyncio
import logging
from threading import Thread
from datetime import datetime

from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
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
    c.execute('''CREATE TABLE IF NOT EXISTS joined_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        link TEXT, group_id INTEGER,
        status TEXT DEFAULT 'pending',
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        message_id INTEGER, interval_minutes INTEGER,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
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
        "bot": "Super Poster Bot v4.0",
        "uptime": datetime.now().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

def run_web():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# ═══════════════════════════════════════════════
#  نظام مكافحة الكشف (Anti-Detection)
# ═══════════════════════════════════════════════
ARABIC_SYNONYMS = {
    'مجاني': ['بدون مقابل', 'مجاناً', 'بلا تكلفة', 'بدون رسوم'],
    'احصل': ['نل', 'اطلب', 'استلم', 'حصل على'],
    'الآن': ['فوراً', 'حالاً', 'في الحال', 'بسرعة'],
    'عرض': ['فرصة', 'تخفيض', 'مناسبة', 'صفقة'],
    'رائع': ['مميز', 'استثنائي', 'فريد', 'رائع جداً'],
    'سعر': ['تكلفة', 'قيمة', 'مبلغ', 'ثمن'],
    'اشترِ': ['اقتنِ', 'اطلب', 'احصل على', 'امتلك'],
    'جديد': ['حديث', 'عصري', 'مستحدث', 'آخر إصدار'],
    'خصم': ['تخفيض', 'حسم', 'تخفيضات', 'خصومات'],
    'فرصة': ['مناسبة', 'عرض', 'فرصة ذهبية', 'فرصة نادرة'],
}

INVISIBLE_CHARS = [
    '\u200b',  # Zero-width space
    '\u200c',  # Zero-width non-joiner
    '\u200d',  # Zero-width joiner
    '\u2060',  # Word joiner
    '\ufeff',  # BOM
]

def add_invisible_chars(text):
    """إضافة أحرف غير مرئية للنص لتخطي كشف التكرار"""
    words = text.split()
    result = []
    for word in words:
        if random.random() < 0.3:
            inv_char = random.choice(INVISIBLE_CHARS)
            pos = random.randint(0, len(word))
            word = word[:pos] + inv_char + word[pos:]
        result.append(word)
    return ' '.join(result)

def replace_synonyms(text):
    """استبدال الكلمات بمرادفاتها"""
    words = text.split()
    result = []
    for word in words:
        clean = word.strip('.,!؟،:')
        if clean in ARABIC_SYNONYMS and random.random() < 0.5:
            synonym = random.choice(ARABIC_SYNONYMS[clean])
            prefix = word[:len(word)-len(clean)] if not word.startswith(clean) else ''
            suffix = word[len(clean)+len(prefix):]
            result.append(prefix + synonym + suffix)
        else:
            result.append(word)
    return ' '.join(result)

def disguise_links(text):
    """تمويه الروابط لتخطي الفلاتر"""
    link_pattern = r'(https?://[^\s]+)'
    links = re.findall(link_pattern, text)
    for link in links:
        if random.random() < 0.5:
            disguised = link.replace('://', '://\u200b')
            text = text.replace(link, disguised)
    return text

def generate_text_variation(text):
    """إنشاء نسخة مختلفة من النص"""
    text = replace_synonyms(text)
    text = add_invisible_chars(text)
    text = disguise_links(text)
    return text

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
posting_task = None

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
#  نظام الانضمام البطيء للمجموعات
# ═══════════════════════════════════════════════
async def slow_join_groups(bot, links, account_id=None):
    """الانضمام التدريجي للمجموعات"""
    if account_id and account_id in user_clients:
        client = user_clients[account_id]
    else:
        active_ids = list(user_clients.keys())
        if not active_ids:
            return 0, "لا توجد حسابات نشطة"
        client = user_clients[random.choice(active_ids)]

    joined = 0
    for link in links:
        link = link.strip()
        if not link:
            continue
        try:
            await client(JoinChannelRequest(link))
            joined += 1
            save_joined_link(link, 'success')
            delay = random.uniform(30, 120)
            await asyncio.sleep(delay)
        except Exception as e:
            save_joined_link(link, f'failed: {str(e)[:50]}')
            logger.error(f"فشل الانضمام لـ {link}: {e}")

    return joined, f"تم الانضمام لـ {joined} مجموعة"

def save_joined_link(link, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO joined_links (link, group_id, status)
                 VALUES (?, 0, ?)''', (link, status))
    conn.commit()
    conn.close()

# ═══════════════════════════════════════════════
#  لوحة التحكم الرئيسية
# ═══════════════════════════════════════════════
def get_main_menu():
    return [
        [Button.inline("📝 إدارة الرسائل", b"messages")],
        [Button.inline("👥 إدارة الحسابات", b"accounts")],
        [Button.inline("📢 إدارة المجموعات", b"groups")],
        [Button.inline("🚀 بدء النشر", b"start_posting"),
         Button.inline("⏹ إيقاف النشر", b"stop_posting")],
        [Button.inline("⚙️ الإعدادات", b"settings"),
         Button.inline("📊 الإحصائيات", b"stats")],
        [Button.inline("🔗 الانضمام البطيء", b"slow_join")],
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
            "🤖 **بوت النشر الخارق v4.0**\n\n"
            "مرحباً بك في لوحة التحكم الرئيسية!\n"
            "اختر من القائمة أدناه:",
            buttons=get_main_menu()
        )

    # ─── التعامل مع الأزرار ───
    @bot.on(events.CallbackQuery)
    async def callback_handler(event):
        if event.sender_id != ADMIN_ID:
            return

        data = event.data.decode('utf-8')

        if data == 'messages':
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
                "1. اذهب إلى @SessionStringBot\n"
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
            is_posting_active = True
            await event.edit("🚀 **تم بدء النشر!**\n\nسيتم النشر في المجموعات بالتناوب.", buttons=[
                [Button.inline("⏹ إيقاف النشر", b"stop_posting")],
                [Button.inline("🔙 رجوع", b"back")],
            ])
            # بدء النشر في الخلفية
            asyncio.create_task(auto_posting_loop(bot))

        elif data == 'stop_posting':
            is_posting_active = False
            await event.edit("⏹ **تم إيقاف النشر**", buttons=[
                [Button.inline("🔙 رجوع", b"back")]
            ])

        elif data == 'settings':
            min_delay = get_setting('min_delay', '3')
            max_delay = get_setting('max_delay', '8')
            anti_detect = get_setting('anti_detect', 'on')
            await event.edit(
                "⚙️ **الإعدادات**\n\n"
                f"⏱ تأخير أدنى: {min_delay} ثانية\n"
                f"⏱ تأخير أقصى: {max_delay} ثانية\n"
                f"🛡 مكافحة الكشف: {anti_detect}\n\n"
                "للتعديل أرسل الأمر:\n"
                "• /set_min_delay <رقم>\n"
                "• /set_max_delay <رقم>\n"
                "• /toggle_anti_detect",
                buttons=[
                    [Button.inline("🔙 رجوع", b"back")]
                ]
            )

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
            conn.close()
            await event.edit(
                "📊 **الإحصائيات**\n\n"
                f"📝 الرسائل: {msg_count}\n"
                f"👥 الحسابات النشطة: {acc_count}\n"
                f"📢 المجموعات: {grp_count}\n"
                f"✅ عمليات نشر ناجحة: {success_count}\n"
                f"❌ عمليات نشر فاشلة: {fail_count}",
                buttons=[
                    [Button.inline("🔙 رجوع", b"back")]
                ]
            )

        elif data == 'slow_join':
            await event.edit(
                "🔗 **الانضمام البطيء للمجموعات**\n\n"
                "أرسل روابط المجموعات (رابط في كل سطر):\n\n"
                "مثال:\n"
                "https://t.me/group1\n"
                "https://t.me/group2\n\n"
                "استخدم /cancel للإلغاء"
            )
            set_setting('awaiting_links', 'true')

        elif data == 'back':
            await event.edit(
                "🤖 **بوت النشر الخارق v4.0**\n\n"
                "اختر من القائمة أدناه:",
                buttons=get_main_menu()
            )

    # ─── التعامل مع الرسائل النصية ───
    @bot.on(events.NewMessage)
    async def message_handler(event):
        if event.sender_id != ADMIN_ID:
            return

        text = event.raw_text

        if text == '/cancel':
            set_setting('awaiting_msg', '')
            set_setting('awaiting_session', '')
            set_setting('awaiting_links', '')
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

        # الانضمام البطيء
        if get_setting('awaiting_links') == 'true':
            set_setting('awaiting_links', '')
            links = text.strip().split('\n')
            links = [l.strip() for l in links if l.strip()]
            await event.respond(f"🔗 جاري الانضمام لـ {len(links)} مجموعة...")
            joined, msg = await slow_join_groups(bot, links)
            await event.respond(f"✅ {msg}", buttons=get_main_menu())
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

    @bot.on(events.NewMessage(pattern='/toggle_anti_detect'))
    async def toggle_anti_detect(event):
        if event.sender_id != ADMIN_ID:
            return
        current = get_setting('anti_detect', 'on')
        new_val = 'off' if current == 'on' else 'on'
        set_setting('anti_detect', new_val)
        await event.respond(f"✅ مكافحة الكشف: {new_val}")

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
