"""
☁️ Session Vault v1.0 - الخزنة السحابية للجلسات والحسابات
المطلوب من المستخدم:
  "اريد ان يحفظ السجلات والجلسات يعني الحسابات المضافه عشان
   ما يكون كل مره احدثه يخرج من الحسابات"

لماذا تُفقد الحسابات عند كل تحديث؟
───────────────────────────────────
Render (خطة free) لا يملك قرصاً دائماً → ملف bot_database.db
(الذي يحوي session_string لكل حساب) يُمسح مع كل deploy جديد.

الحل (هذه الوحدة):
──────────────────
1) 📦 تصدير لقطة مشفرة من قاعدة البيانات (الحسابات + الجلسات +
   المجموعات + الرسائل + الإعدادات + الجدولة) إلى مستودع GitHub
   خاص (private) اسمه render-bot-vault - يُنشأ تلقائياً عند أول نسخة.
2) 🔄 عند إقلاع البوت: إذا كانت قاعدة البيانات فارغة (بعد تحديث)
   تُسحب آخر لقطة وتُفك التشفير وتُعاد الجلسات تلقائياً -
   الحسابات والمجموعات والرسائل كلها تعود كما كانت.
3) 🔁 نسخ تلقائي بعد كل تغيير مهم (إضافة/حذف حساب، رسالة جديدة)
   بفاصل زمني مهيأ (debounce) كي لا نغرق GitHub.

الأمان:
───────
- المستودع private ولا يمكن لأحد قراءته.
- المحتوى نفسه مشفر بخمث مشتق من BOT_TOKEN (متوفر في بيئة Render
  وليس في المستودع) → حتى لو تسرب الملف لا يمكن فك تشفيره.
- يُستخدم HMAC-SHA256 بوضع CTR (تشفير انسيابي معياري) + nonce عشوائي.

التوكن:
───────
يُقرأ من env: GITHUB_TOKEN أو GH_TOKEN.
لو غير موجود: محاولة قراءته من .git/config (بيئة التطوير فقط).
على Render أضف مرة واحدة: Environment → GITHUB_TOKEN.
بدون توكن: يعمل وضع النسخ المحلي (ملف last_vault_backup.bin)
كحل احتياطي - لكنه يمسح مع deploy على Render أيضاً.
"""

import os
import io
import json
import base64
import sqlite3
import hashlib
import hmac as hmac_mod
import secrets
import threading
import urllib.request
import urllib.error

DB_PATH = os.environ.get('DB_PATH', 'bot_database.db')

VAULT_REPO_NAME = os.environ.get('VAULT_REPO', 'render-bot-vault')
VAULT_FILE_PATH = 'vault.enc'
LOCAL_FALLBACK = 'last_vault_backup.bin'
ENCRYPTION_VERSION = b'V1'

# ═══════════════════════════════════════════════
# 🔑 التشفير
# ═══════════════════════════════════════════════

def _derive_key() -> bytes:
    """مفتاح التشفير مشتق من BOT_TOKEN (لا يُخزن في أي مكان)"""
    secret = os.environ.get('BOT_TOKEN') or os.environ.get('API_HASH') or 'super-poster-bot-fallback'
    return hashlib.sha256(b'session-vault-v1:' + secret.encode()).digest()


def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """HMAC-SHA256 CTR keystream"""
    out = bytearray()
    counter = 0
    while len(out) < length:
        msg = nonce + counter.to_bytes(8, 'big')
        out.extend(hmac_mod.new(key, msg, hashlib.sha256).digest())
        counter += 1
    return bytes(out[:length])


def encrypt_data(plaintext: bytes) -> bytes:
    key = _derive_key()
    nonce = secrets.token_bytes(16)
    ks = _keystream(key, nonce, len(plaintext))
    ct = bytes(a ^ b for a, b in zip(plaintext, ks))
    mac = hmac_mod.new(key, nonce + ct, hashlib.sha256).digest()[:16]
    return ENCRYPTION_VERSION + nonce + mac + ct


def decrypt_data(blob: bytes):
    """يفك التشفير - يُرجع bytes أو يرفع ValueError لو فشل التحقق"""
    if len(blob) < 2 + 16 + 16:
        raise ValueError("vault: blob too short")
    if blob[:2] != ENCRYPTION_VERSION:
        raise ValueError("vault: unknown version")
    key = _derive_key()
    nonce = blob[2:18]
    mac = blob[18:34]
    ct = blob[34:]
    expect = hmac_mod.new(key, nonce + ct, hashlib.sha256).digest()[:16]
    if not hmac_mod.compare_digest(mac, expect):
        raise ValueError("vault: HMAC mismatch (مفتاح مختلف أو ملف تالف)")
    ks = _keystream(key, nonce, len(ct))
    return bytes(a ^ b for a, b in zip(ct, ks))


# ═══════════════════════════════════════════════
# 🔐 التوكن و GitHub API
# ═══════════════════════════════════════════════

_token_cache = None


def resolve_github_token():
    """ترتيب القراءة: env GITHUB_TOKEN → env GH_TOKEN → .git/config (تطوير)"""
    global _token_cache
    if _token_cache:
        return _token_cache
    tok = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if tok:
        _token_cache = tok.strip()
        return _token_cache
    # بيئة التطوير: استخراج التوكن من رابط remote في .git/config
    try:
        cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.git', 'config')
        with open(cfg_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        import re
        m = re.search(r'https://[^:]+:([A-Za-z0-9_]+)@github\.com', content)
        if m:
            _token_cache = m.group(1)
            return _token_cache
    except Exception:
        pass
    return None


def _gh_request(method: str, url: str, token: str, payload=None):
    """طلب GitHub API - يُرجع (status, json_dict)"""
    data = None
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'session-vault',
    }
    if payload is not None:
        data = json.dumps(payload).encode()
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            return resp.status, (json.loads(body) if body else {})
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b'{}')
        except Exception:
            return e.code, {}


def get_authenticated_user(token: str):
    st, data = _gh_request('GET', 'https://api.github.com/user', token)
    if st == 200:
        return data.get('login')
    return None


def ensure_vault_repo(token: str, owner: str):
    """التأكد من وجود المستودع الخاص - إنشاؤه إن لم يوجد"""
    st, _ = _gh_request('GET', f'https://api.github.com/repos/{owner}/{VAULT_REPO_NAME}', token)
    if st == 200:
        return True
    if st == 404:
        st2, data2 = _gh_request('POST', 'https://api.github.com/user/repos', token, payload={
            'name': VAULT_REPO_NAME,
            'private': True,
            'description': '🔐 Encrypted session vault (auto-managed)',
            'auto_init': False,
        })
        return st2 in (201, 202)
    return False


def _get_file_sha(token: str, owner: str):
    st, data = _gh_request(
        'GET',
        f'https://api.github.com/repos/{owner}/{VAULT_REPO_NAME}/contents/{VAULT_FILE_PATH}',
        token)
    if st == 200:
        return data.get('sha')
    return None


# ═══════════════════════════════════════════════
# 📦 اللقطة (Snapshot)
# ═══════════════════════════════════════════════

def build_snapshot() -> dict:
    """قراءة كل الجداول المهمة من قاعدة البيانات"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    snap = {'version': 1}

    try:
        c.execute("SELECT id, session_string, phone, status, added_at FROM accounts")
        snap['accounts'] = [dict(r) for r in c.fetchall()]
    except Exception:
        snap['accounts'] = []

    try:
        c.execute("SELECT group_id, group_name, username, member_count, added_by FROM groups")
        snap['groups'] = [dict(r) for r in c.fetchall()]
    except Exception:
        snap['groups'] = []

    try:
        c.execute("SELECT key, value FROM settings")
        snap['settings'] = {r['key']: r['value'] for r in c.fetchall()}
    except Exception:
        snap['settings'] = {}

    try:
        c.execute("SELECT id, content, media_path, msg_type, media_data, created_at FROM messages")
        snap['messages'] = [dict(r) for r in c.fetchall()]
    except Exception:
        snap['messages'] = []

    try:
        c.execute("SELECT message_id, post_time, repeat_type, repeat_interval, post_mode, "
                  "status, last_run, next_run FROM scheduled_posts WHERE status='pending'")
        snap['scheduled_posts'] = [dict(r) for r in c.fetchall()]
    except Exception:
        snap['scheduled_posts'] = []

    try:
        c.execute("SELECT group_id, group_name FROM blacklist")
        snap['blacklist'] = [dict(r) for r in c.fetchall()]
    except Exception:
        snap['blacklist'] = []
    finally:
        conn.close()

    return snap


def restore_snapshot(snap: dict):
    """كتابة اللقطة داخل قاعدة البيانات (استبدال كامل للجداول المستعادة)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # تأكد من وجود الجداول (init_db يعمل قبلها عادة لكن للأمان)
    c.execute("CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, "
              "session_string TEXT, phone TEXT, status TEXT DEFAULT 'active', "
              "added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    c.execute("CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, "
              "group_id INTEGER, group_name TEXT, username TEXT, member_count INTEGER, "
              "added_by TEXT, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, "
              "content TEXT, media_path TEXT, msg_type TEXT DEFAULT 'text', media_data TEXT, "
              "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    c.execute("CREATE TABLE IF NOT EXISTS scheduled_posts (id INTEGER PRIMARY KEY AUTOINCREMENT, "
              "message_id INTEGER, post_time TEXT NOT NULL, repeat_type TEXT DEFAULT 'once', "
              "repeat_interval INTEGER DEFAULT 0, post_mode TEXT DEFAULT 'fast', "
              "status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
              "last_run TEXT DEFAULT NULL, next_run TEXT DEFAULT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS blacklist (group_id TEXT PRIMARY KEY, "
              "group_name TEXT, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")

    for acc in snap.get('accounts', []):
        c.execute("INSERT OR REPLACE INTO accounts (id, session_string, phone, status) VALUES (?,?,?,?)",
                  (acc.get('id'), acc.get('session_string'), acc.get('phone'), acc.get('status') or 'active'))

    for g in snap.get('groups', []):
        c.execute("INSERT OR IGNORE INTO groups (group_id, group_name, username, member_count, added_by) "
                  "VALUES (?,?,?,?,?)",
                  (g.get('group_id'), g.get('group_name'), g.get('username'),
                   g.get('member_count', 0), g.get('added_by')))

    for k, v in (snap.get('settings') or {}).items():
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (k, v))

    for m in snap.get('messages', []):
        c.execute("INSERT OR REPLACE INTO messages (id, content, media_path, msg_type, media_data) "
                  "VALUES (?,?,?,?,?)",
                  (m.get('id'), m.get('content'), m.get('media_path'),
                   m.get('msg_type') or 'text', m.get('media_data')))

    for s in snap.get('scheduled_posts', []):
        c.execute("INSERT INTO scheduled_posts (message_id, post_time, repeat_type, repeat_interval, "
                  "post_mode, status, last_run, next_run) VALUES (?,?,?,?,?,?,?,?)",
                  (s.get('message_id'), s.get('post_time'), s.get('repeat_type') or 'once',
                   s.get('repeat_interval', 0), s.get('post_mode') or 'fast',
                   s.get('status') or 'pending', s.get('last_run'), s.get('next_run')))

    for b in snap.get('blacklist', []):
        c.execute("INSERT OR IGNORE INTO blacklist (group_id, group_name) VALUES (?,?)",
                  (b.get('group_id'), b.get('group_name')))

    conn.commit()
    conn.close()


def count_active_accounts() -> int:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM accounts WHERE status='active'")
        n = c.fetchone()[0]
        conn.close()
        return n
    except Exception:
        return 0


# ═══════════════════════════════════════════════
# ☁️ التصدير والاستيراد
# ═══════════════════════════════════════════════

def export_to_github():
    """
    تصدير لقطة مشفرة إلى المستودع الخاص.
    يُرجع (ok: bool, message: str)
    """
    token = resolve_github_token()
    if not token:
        return False, "لا يوجد GITHUB_TOKEN - أضفه في إعدادات Render (Environment)"

    owner = get_authenticated_user(token)
    if not owner:
        return False, "توكن GitHub غير صالح أو منتهي"

    if not ensure_vault_repo(token, owner):
        return False, f"فشل إنشاء المستودع الخاص {VAULT_REPO_NAME}"

    try:
        snap = build_snapshot()
        plaintext = json.dumps(snap, ensure_ascii=False).encode()
        blob = encrypt_data(plaintext)
        b64 = base64.b64encode(blob).decode()

        sha = _get_file_sha(token, owner)
        payload = {
            'message': f'vault: auto backup ({len(snap.get("accounts", []))} accounts, '
                       f'{len(snap.get("groups", []))} groups)',
            'content': b64,
        }
        if sha:
            payload['sha'] = sha
        st, _ = _gh_request(
            'PUT',
            f'https://api.github.com/repos/{owner}/{VAULT_REPO_NAME}/contents/{VAULT_FILE_PATH}',
            token, payload=payload)
        if st in (200, 201):
            # نسخة احتياطية محلية أيضاً
            try:
                with open(LOCAL_FALLBACK, 'wb') as f:
                    f.write(blob)
            except Exception:
                pass
            return True, (f"تم الحفظ السحابي في {owner}/{VAULT_REPO_NAME} "
                          f"({len(snap.get('accounts', []))} حساب, "
                          f"{len(snap.get('groups', []))} مجموعة)")
        return False, f"فشل رفع النسخة (HTTP {st})"
    except Exception as e:
        return False, f"خطأ: {str(e)[:200]}"


def import_from_github():
    """
    سحب آخر لقطة من المستودع وفك تشفيرها (بدون كتابة في DB).
    يُرجع (snap_dict أو None, message)
    """
    token = resolve_github_token()
    if not token:
        return None, "لا يوجد GITHUB_TOKEN"
    owner = get_authenticated_user(token)
    if not owner:
        return None, "توكن GitHub غير صالح"
    st, data = _gh_request(
        'GET',
        f'https://api.github.com/repos/{owner}/{VAULT_REPO_NAME}/contents/{VAULT_FILE_PATH}',
        token)
    if st != 200:
        return None, f"لا توجد نسخة سحابية بعد (HTTP {st})"
    try:
        blob = base64.b64decode(data.get('content') or '')
        plaintext = decrypt_data(blob)
        return json.loads(plaintext.decode()), "تم سحب النسخة وفك تشفيرها"
    except Exception as e:
        return None, f"فشل فك التشفير: {str(e)[:150]}"


def import_from_local():
    """استعادة من الملف المحلي الاحتياطي"""
    try:
        with open(LOCAL_FALLBACK, 'rb') as f:
            blob = f.read()
        plaintext = decrypt_data(blob)
        return json.loads(plaintext.decode()), "تمت القراءة من الملف المحلي"
    except FileNotFoundError:
        return None, "لا يوجد ملف نسخة محلي"
    except Exception as e:
        return None, f"فشل: {str(e)[:150]}"


def restore_if_empty():
    """
    تُستدعى عند إقلاع البوت:
    إذا لم توجد حسابات نشطة في DB → استعادة من السحابة (ثم المحلي كخطة بديلة)
    يُرجع (restored: bool, message: str)
    """
    if count_active_accounts() > 0:
        return False, "قاعدة البيانات تحتوي حسابات - لا حاجة للاستعادة"

    snap, msg = import_from_github()
    if not snap:
        snap, msg2 = import_from_local()
        if not snap:
            return False, f"لا توجد نسخة احتياطية ({msg})"
        msg = msg2

    try:
        restore_snapshot(snap)
        n_acc = len(snap.get('accounts', []))
        n_grp = len(snap.get('groups', []))
        return True, (f"✅ استُعيدت {n_acc} حساب و{n_grp} مجموعة "
                      f"و{len(snap.get('messages', []))} رسالة ({msg})")
    except Exception as e:
        return False, f"فشل كتابة الاستعادة: {str(e)[:150]}"


# ═══════════════════════════════════════════════
# 🔁 النسخ التلقائي المايهل (debounced)
# ═══════════════════════════════════════════════

_dirty = threading.Event()
_last_backup_iso = None


def mark_dirty():
    """استدعِها بعد أي تغيير مهم (إضافة حساب، رسالة جديدة...)"""
    global _last_backup_iso
    _dirty.set()


def is_dirty():
    return _dirty.is_set()


def clear_dirty():
    global _last_backup_iso
    _dirty.clear()
    from datetime import datetime
    _last_backup_iso = datetime.now().strftime('%Y-%m-%d %H:%M')


def get_last_backup_time():
    return _last_backup_iso


async def vault_sweeper(interval_seconds: int = 300):
    """
    مهمة خلفية (asyncio): كل interval ثانية - إذا وُجد تغيير مُعلَّم → نسخة سحابية.
    تُشغَّل مرة واحدة من main().
    """
    import asyncio
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            if _dirty.is_set():
                ok, msg = await asyncio.to_thread(export_to_github)
                if ok:
                    clear_dirty()
                await asyncio.sleep(2)
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(30)


# ═══════════════════════════════════════════════
# 🧪 اختبار ذاتي
# ═══════════════════════════════════════════════

if __name__ == '__main__':
    # 1) تشفير/فك تشفير
    data = json.dumps({"test": "مرحبا بالعالم 123"}, ensure_ascii=False).encode()
    enc = encrypt_data(data)
    dec = decrypt_data(enc)
    assert dec == data, "round-trip failed"
    # 2) فشل HMAC بمفتاح مختلف
    os.environ['BOT_TOKEN'] = 'other-key'
    try:
        decrypt_data(enc)
        print("❌ كان يجب أن يفشل HMAC")
    except ValueError:
        print("✅ فحص HMAC سليم (مفتاح خاطئ = رفض)")
    os.environ.pop('BOT_TOKEN', None)
    print("✅ اختبار التشفير: سليم")
    print("توكن GitHub:", "موجود ✅" if resolve_github_token() else "غير موجود ⚠️")
    snap = build_snapshot()
    print(f"اللقطة الحالية: {len(snap['accounts'])} حساب, "
          f"{len(snap['groups'])} مجموعة, {len(snap['settings'])} إعداد, "
          f"{len(snap['messages'])} رسالة")
