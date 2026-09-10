"""
🛡️ Link Guard v4.3 - درع الروابط + الارتباط التشعبي (وضع المستخدم اليدوي)

أحدث طلب من المستخدم (يُلغي الاكتشاف التلقائي في v4.2):
  "الرقم الذي يضعه في ارتباط تشعبي خليني اقدر احدده انا
   اذا ما حددتوش انا ما يضيفش اي رقم من عنده يعني يكون الاضافه من عندي
   اذا مافيش لا يضيف اي شي من عنده حتى المعرف او اي شي اخر
   اذا وجد يضيف ارتباط مالم لا يضيف
   لانه بضيف تحيان اعلانات بدون يوزرات او ارتباطات او ارقام"

السلوك النهائي الصارم:
──────────────────────
1) المستخدم وحده يحدد أهداف الارتباط (يوزر/هاتف/رابط) من قائمة البوت.
2) لم يحدد المستخدم شيئاً؟ → البوت لا يضيف ولا يستبدل ولا يكتشف شيئاً أبداً.
3) حدد أهدافاً؟ → فقط عندما يُعثر على الهدف نفسه نصاً في الإعلان
   يستبدله بنص الزر (للطلب اضغط هنا) المرتبط بالوجهة التي حددها المستخدم.
4) الإعلان بلا يوزرات/أرقام/روابط؟ → لا يُضاف أي شيء إطلاقاً.

لماذا هذا يُصلح مشكلة "اليوزر ما ينضغط" أيضاً؟
─────────────────────────────────────────────
- الأحرف الخفية لا تُحقن أبداً داخل الرموز الحساسة (قرار معماري):
  @username يبقى نصاً نظيفاً → تيليجرام يتعرف عليه → قابل للضغط.
- وعند الاستبدال بزر ارتباط: كيان MessageEntityTextUrl رسمي - أضمن أنواع
  الروابط في تيليجرام 100%.
- كما نُصدر كيان MessageEntityMention صريحاً لكل يوزر متبقٍ لضمان
  قابلية الضغط حتى لو التقت أحرف خفية مجاورة.

الإزاحات (offsets) بوحدات UTF-16 حسب معيار Telegram API
(الحروف غير BMP = وحدتا UTF-16 - محسوبة بدقة).
"""

import re

# ═══════════════════════════════════════════════
# ⚙️ الإعدادات الافتراضية (تُقرأ من قاعدة البيانات عبر bot.py)
# ═══════════════════════════════════════════════

DEFAULT_ANCHOR = "للطلب اضغط هنا"
DEFAULT_COUNTRY_CODE = "967"

ANCHOR_PRESETS = [
    "للطلب اضغط هنا",
    "للتواصل اضغط هنا",
    "اضغط هنا للطلب",
    "تواصل معنا",
    "راسلنا الآن",
]

COUNTRY_PRESETS = [
    ("967", "اليمن 🇾🇪"),
    ("966", "السعودية 🇸🇦"),
    ("971", "الإمارات 🇦🇪"),
    ("965", "الكويت 🇰🇼"),
    ("973", "البحرين 🇧🇭"),
    ("974", "قطر 🇶🇦"),
    ("968", "عمان 🇴🇲"),
    ("964", "العراق 🇮🇶"),
    ("90",  "تركيا 🇹🇷"),
    ("20",  "مصر 🇪🇬"),
]

# ═══════════════════════════════════════════════
# 🔎 كشف الرموز الحساسة (ترتيب البدائل مهم: الرابط قبل اليوزر)
# ═══════════════════════════════════════════════

SENSITIVE_TOKEN_RE = re.compile(
    r'(?P<url>'                                   # 1) روابط
    r'(?:https?://|www\.)\S+'
    r'|(?<![\w@.])(?:t\.me|wa\.me)/\S+'
    r')'
    r'|(?P<mention>@[a-zA-Z0-9_]{4,32})'          # 2) يوزرات تيليجرام
    r'|(?P<phone>\+?[0-9\u0660-\u0669\u06F0-\u06F9](?:[0-9\u0660-\u0669\u06F0-\u06F9\s\-()]{7,})[0-9\u0660-\u0669\u06F0-\u06F9])'  # 3) أرقام
)

_AR_DIGITS_MAP = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')
_TRAILING_PUNCT = '.,،!؟:;)]»"\'…-'
_MIN_PHONE_DIGITS = 9
_MAX_PHONE_DIGITS = 15

# أحرف خفية قد تلزق بالرموز من طبقات أخرى - تُنظف عند المطابقة
_INVISIBLE_RE = re.compile(
    '[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u206f\ufe00-\ufe0f'
    '\U0001d173-\U0001d17a\U000e0000-\U000e0fff\U000e0100-\U000e01ef]')


def u16len(s: str) -> int:
    """طول النص بوحدات UTF-16 (معيار إزاحات كيانات Telegram)"""
    return len(s.encode('utf-16-le')) // 2


def _normalize_digits(s: str) -> str:
    return s.translate(_AR_DIGITS_MAP)


def _strip_invisible(s: str) -> str:
    return _INVISIBLE_RE.sub('', s)


def _clean_url(raw: str) -> str:
    url = raw.rstrip(_TRAILING_PUNCT)
    if url.startswith('www.'):
        url = 'https://' + url
    elif url.startswith('t.me/'):
        url = 'https://' + url
    elif url.startswith('wa.me/'):
        url = 'https://' + url
    return url


def _clean_phone(raw: str, country_code: str) -> str:
    """
    تطبيع رقم الهاتف إلى صيغة دولية لـ wa.me
    0777123456    → 967777123456  (كود الدولة 967)
    +967777123456 → 967777123456
    00967777123456 → 967777123456
    """
    digits = _normalize_digits(raw)
    digits = re.sub(r'\D', '', digits)
    cc = re.sub(r'\D', '', _normalize_digits(country_code)) or DEFAULT_COUNTRY_CODE
    if digits.startswith('00'):
        digits = digits[2:]
    elif digits.startswith('0'):
        digits = digits.lstrip('0')
        digits = cc + digits
    elif not digits.startswith(cc):
        digits = cc + digits
    return digits


def _digits_only(raw: str) -> str:
    return re.sub(r'\D', '', _normalize_digits(raw))


def _build_target(kind: str, token: str, country_code: str):
    """بناء وجهة الارتباط التشعبي حسب نوع الرمز - يُرجع url أو None"""
    if kind == 'mention':
        username = token[1:]
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', username):
            return None
        return f"https://t.me/{username}"
    if kind == 'url':
        return _clean_url(token)
    if kind == 'phone':
        n = len(_digits_only(token))
        if n < _MIN_PHONE_DIGITS or n > _MAX_PHONE_DIGITS:
            return None
        return f"https://wa.me/{_clean_phone(token, country_code)}"
    return None


# ═══════════════════════════════════════════════
# 🎯 الأهداف اليدوية (مصدرها المستخدم فقط)
# ═══════════════════════════════════════════════

def normalize_target_input(raw: str, country_code: str = DEFAULT_COUNTRY_CODE):
    """
    تطبيع هدف أدخله المستخدم في القائمة.
    يقبل:
      @ppppokl | ppppokl | https://t.me/ppppokl | t.me/ppppokl   → منشن
      0777123456 | +967777123456 | 967777123456 | 00967777123456 → هاتف
      https://example.com | www.example.com | https://wa.me/967… → رابط
    يُرجع dict {raw, kind, key, url, label} أو None لو غير صالح.
      key: معرّف مطابقة موحّد (المنشن والرابط t.me لهما نفس المفتاح)
      url: وجهة الضغط النهائية
    """
    if not raw:
        return None
    raw = _strip_invisible(str(raw)).strip()
    if not raw or len(raw) > 200:
        return None
    raw = raw.rstrip(_TRAILING_PUNCT)
    low = raw.lower()

    # 1) روابط
    if low.startswith(('http://', 'https://', 'www.')):
        url = _clean_url(raw)
        # رابط تيليجرام؟ → طبّعه كيوزر (نفس وجهة المنشن)
        m = re.match(r'https?://(?:t\.me|telegram\.me)/(@?[a-zA-Z0-9_]{3,64})/?$', url)
        if m:
            username = m.group(1).lstrip('@')
            if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', username):
                username = None
            if username:
                return {'raw': raw, 'kind': 'mention', 'key': f'tg:{username.lower()}',
                        'url': f'https://t.me/{username}',
                        'label': f'@{username} (تيليجرام)'}
        return {'raw': raw, 'kind': 'url', 'key': f'url:{url.lower()}',
                'url': url, 'label': url[:60]}
    if re.match(r'^(?:t\.me|telegram\.me)/', low):
        url = _clean_url(raw)
        m = re.match(r'https?://(?:t\.me|telegram\.me)/(@?[a-zA-Z0-9_]{3,64})/?$', url)
        if m:
            username = m.group(1).lstrip('@')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', username):
                return {'raw': raw, 'kind': 'mention', 'key': f'tg:{username.lower()}',
                        'url': f'https://t.me/{username}',
                        'label': f'@{username} (تيليجرام)'}
        return {'raw': raw, 'kind': 'url', 'key': f'url:{url.lower()}',
                'url': url, 'label': url[:60]}
    if re.match(r'^wa\.me/', low):
        url = 'https://' + raw
        return {'raw': raw, 'kind': 'url', 'key': f'url:{url.lower()}',
                'url': url, 'label': url[:60]}

    # 2) منشن (مع أو بدون @)
    if raw.startswith('@') or (raw[0].isalpha() and re.match(r'^[a-zA-Z][a-zA-Z0-9_]{2,31}$', raw)
                               and not raw.isdigit()):
        username = raw.lstrip('@')
        if re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', username) and 3 <= len(username) <= 32:
            return {'raw': raw, 'kind': 'mention', 'key': f'tg:{username.lower()}',
                    'url': f'https://t.me/{username}',
                    'label': f'@{username} (تيليجرام)'}
        return None

    # 3) هاتف (أرقام فقط مع رموز فصل شائعة)
    if re.match(r'^[+0-9][0-9\u0660-\u0669\u06F0-\u06F9\s\-()]{6,}$', raw):
        digits = _digits_only(raw)
        n = len(digits)
        if _MIN_PHONE_DIGITS <= n <= _MAX_PHONE_DIGITS:
            intl = _clean_phone(raw, country_code)
            return {'raw': raw, 'kind': 'phone', 'key': f'wa:{intl}',
                    'url': f'https://wa.me/{intl}',
                    'label': f'{digits} (واتساب)'}
        return None

    return None


def parse_targets(config_str: str, country_code: str = DEFAULT_COUNTRY_CODE):
    """
    تحويل نص الإعدادات المحفوظ (سطر لكل هدف أو مفصولة بفواصل)
    إلى قائمة أهداف مطبّعة. لا يضيف شيئاً من عنده أبداً.
    """
    targets = []
    if not config_str:
        return targets
    for part in re.split(r'[\n,،;]+', str(config_str)):
        part = part.strip()
        if not part:
            continue
        t = normalize_target_input(part, country_code)
        if t and not any(t['key'] == x['key'] for x in targets):
            targets.append(t)
    return targets


def targets_summary(targets) -> str:
    """أسطر عرض الأهداف في القائمة"""
    icons = {'mention': '👤', 'phone': '📱', 'url': '🔗'}
    return "\n".join(f"{icons.get(t['kind'], '•')} {t['label']}  ←  {t['url']}"
                     for t in targets)


def _token_key(kind: str, token: str, country_code: str):
    """مفتاح مطابقة الرمز المكتشف في النص (نفس منطق normalize_target_input)"""
    if kind == 'mention':
        return f'tg:{token[1:].lower()}'
    if kind == 'url':
        url = _clean_url(token)
        m = re.match(r'https?://(?:t\.me|telegram\.me)/(@?[a-zA-Z0-9_]{3,64})/?$', url)
        if m:
            username = m.group(1).lstrip('@')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', username):
                return f'tg:{username.lower()}'
        return f'url:{url.lower()}'
    if kind == 'phone':
        digits = _digits_only(token)
        n = len(digits)
        if n < _MIN_PHONE_DIGITS or n > _MAX_PHONE_DIGITS:
            return None
        return f'wa:{_clean_phone(token, country_code)}'
    return None


# ═══════════════════════════════════════════════
# 🔎 أدوات الكشف (للاستخدام العام والمعاينة)
# ═══════════════════════════════════════════════

def find_sensitive_tokens(text: str):
    """قائمة (بداية, نهاية, نوع, النص) لكل الرموز الحساسة في النص"""
    tokens = []
    for m in SENSITIVE_TOKEN_RE.finditer(text):
        kind = 'url' if m.group('url') else ('mention' if m.group('mention') else 'phone')
        tokens.append((m.start(), m.end(), kind, m.group(0)))
    return tokens


def find_clean_mentions(text: str):
    """
    يوزرات نظيفة (بلا أحرف خفية داخلها) - تُستخدم لإصدار كيان Mention صريح
    يضمن قابلية الضغط على اليوزر حتى مع وجود أحرف خفية مجاورة له.
    يُرجع [(offset_utf16, length_utf16, username)]
    """
    out = []
    for m in re.finditer(r'(?<![\w@.])@([a-zA-Z][a-zA-Z0-9_]{3,31})', text):
        tok = m.group(0)
        if _INVISIBLE_RE.search(tok):
            continue  # يوزر ملوث بأحرف خفية → كيان Mention لن يعمل، تجاوز
        out.append((u16len(text[:m.start()]), u16len(tok), m.group(1)))
    return out


def analyze(text: str, country_code: str = DEFAULT_COUNTRY_CODE, targets=None):
    """
    تحليل إعلان ضد الأهداف المحددة من المستخدم (وضع يدوي صرف):
    يُرجع قائمة (النص, النوع, الوجهة) للرموز التي ستتحول لأزرار.
    targets=None → فارغة (لا شيء يُستبدل).
    """
    results = []
    if not targets:
        return results
    keys = {t['key']: t for t in targets}
    for s, e, kind, tok in find_sensitive_tokens(text):
        key = _token_key(kind, tok, country_code)
        if key and key in keys:
            results.append((tok, kind, keys[key]['url']))
    return results


# ═══════════════════════════════════════════════
# 🛡 الدرع الرئيسي
# ═══════════════════════════════════════════════

def apply_link_guard(text: str,
                     anchor: str = DEFAULT_ANCHOR,
                     country_code: str = DEFAULT_COUNTRY_CODE,
                     targets=None):
    """
    🛡️ الدرع - الوضع اليدوي الصرف (v4.3):

    targets فارغة/None → يُرجع النص كما هو بلا أي تعديل أو إضافة.
    (الالتزام الحرفي بطلب المستخدم: "اذا مافيش لا يضيف اي شي من عنده")

    targets موجودة → فقط الرموز المطابقة لأهداف المستخدم تُستبدل بنص الزر
    المرتبط بالوجهة التي حددها المستخدم. ما لم يُعثر عليه لا يُضاف.

    المدخل: النص بعد Ghost Encoding (الرموز الحساسة تمر نظيفة -
    لا تُحقن أحرف خفية داخلها أبداً حسب القرار المعماري v4.2+).

    المخرج: (النص الجديد, قائمة كيانات (offset_u16, length_u16, url))
    """
    if not text or not anchor or not targets:
        return text, []

    keys = {t['key']: t for t in targets}

    out_parts = []
    entities = []
    u16_pos = 0
    last = 0

    for m in SENSITIVE_TOKEN_RE.finditer(text):
        token = m.group(0)
        kind = 'url' if m.group('url') else ('mention' if m.group('mention') else 'phone')
        key = _token_key(kind, token, country_code)
        target = keys.get(key) if key else None
        if not target:
            continue  # ليس من أهداف المستخدم → يبقى نصاً كما هو (لا إضافة من البوت)

        if m.start() > last:
            seg = text[last:m.start()]
            out_parts.append(seg)
            u16_pos += u16len(seg)

        # الزر (نص الارتباط) - نظيف تماماً بلا أحرف خفية
        out_parts.append(anchor)
        entities.append((u16_pos, u16len(anchor), target['url']))
        u16_pos += u16len(anchor)

        last = m.end()

    tail = text[last:]
    out_parts.append(tail)

    return ''.join(out_parts), entities


def build_telethon_entities(entities):
    """تحويل الكيانات الخام إلى كيانات Telethon (MessageEntityTextUrl)"""
    if not entities:
        return None
    try:
        from telethon.tl.types import MessageEntityTextUrl
        return [MessageEntityTextUrl(offset=off, length=length, url=url)
                for off, length, url in entities]
    except Exception:
        return entities


def build_mention_entities(mentions):
    """تحويل قائمة find_clean_mentions إلى كيانات Telethon MessageEntityMention"""
    if not mentions:
        return None
    try:
        from telethon.tl.types import MessageEntityMention
        return [MessageEntityMention(offset=off, length=length)
                for off, length, _user in mentions]
    except Exception:
        return None


if __name__ == '__main__':
    # ─── اختبار الوضع اليدوي ───
    ad = ("✅اعذار طبية تطبيق صحتي\n"
          "✅يوم /يومين /اسبوع\n"
          "✅تقرير طبي\n"
          "✅مرافق @ppppokl اتصل 0777123456\n"
          "قناة: t.me/myshop السعر 1500")

    # 1) بدون أهداف → لا شيء يُستبدل (القاعدة الصارمة)
    t1, e1 = apply_link_guard(ad)
    assert t1 == ad and e1 == [], "❌ بدون أهداف يجب ألا يتغير شيء!"
    print("✅ بدون أهداف من المستخدم: النص لم يُمَس ولم يُضف شيء")

    # 2) أهداف المستخدم: اليوزر فقط
    targets = parse_targets("@ppppokl")
    t2, e2 = apply_link_guard(ad, targets=targets)
    assert "@ppppokl" not in t2 and "للطلب اضغط هنا" in t2, "❌ اليوزر لم يستبدل"
    assert "0777123456" in t2 and "t.me/myshop" in t2, "❌ ما لم يحدده المستخدم يجب أن يبقى!"
    print("✅ مع هدف واحد (@ppppokl): استبدل اليوزر فقط وبقي الباقي")

    # 3) يوزر + هاتف
    targets = parse_targets("@ppppokl\n0777123456")
    t3, e3 = apply_link_guard(ad, targets=targets)
    assert "@ppppokl" not in t3 and "0777123456" not in t3
    assert e3[0][2] == "https://t.me/ppppokl"
    assert e3[1][2] == "https://wa.me/967777123456", e3[1][2]
    print("✅ يوزر + هاتف: الوجهات صحيحة (t.me / wa.me بكود الدولة)")

    # 4) مطابقة بصيغ مختلفة للرقم نفسه
    targets = parse_targets("+967777123456")
    t4, e4 = apply_link_guard(ad, targets=targets)
    assert "0777123456" not in t4, "❌ 0777123456 يجب أن يطابق +967777123456"
    print("✅ مطابقة الأرقام بصيغها المختلفة (0/+967/967/00967)")

    # 5) تلميح t.me يطابق يوزر
    targets = parse_targets("t.me/myshop")
    t5, e5 = apply_link_guard(ad, targets=targets)
    assert "t.me/myshop" not in t5
    print("✅ رابط t.me في الإعلان يطابق هدف المستخدم")

    # 6) كيانات منشن صريحة لليوزر المتبقي
    ments = find_clean_mentions("تواصل @user_one او @x1 @ok_ay")
    assert any(u == 'user_one' for _, _, u in ments)
    print("✅ كشف اليوزرات النظيفة لكيان Mention الصريح")

    # 7) إزاحات UTF-16 صحيحة مع نص عربي + إيموجي
    text = "✅اعذار @ppppokl طبية 😊 0777123456"
    targets = parse_targets("@ppppokl\n0777123456")
    tn, en = apply_link_guard(text, targets=targets)
    for off, ln, url in en:
        chunk = tn.encode('utf-16-le')[off*2:(off+ln)*2].decode('utf-16-le')
        assert chunk == "للطلب اضغط هنا", f"❌ إزاحة خاطئة: {chunk!r}"
    print("✅ الإزاحات UTF-16 دقيقة حتى مع الإيموجي والعربي")

    print("\n🎉 كل اختبارات الوضع اليدوي نجحت")
