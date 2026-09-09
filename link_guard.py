"""
🛡️ Link Guard v4.2 - درع الروابط والارتباط التشعبي الذكي
الميزة المطلوبة من المستخدم:
  "المفترض عند الضغط على اليوزر ينقلني لليوزر - الان اليوزر ما ينضغط"
  "يمكنك ان تجعل عندنا يوزر او رقم هاتف او وتس يعملهم كا ارتباط تشعبي
   بكلمة مثلا (للطلب اضغط هنا) ومجرد الضغط على الكلمة ينقله اما لليوزر
   او الرقم او الخ... حسب ما هو في الاعلان"

لماذا هذا الحل أقوى من حقن VS داخل اليوزر (v4.1)؟
─────────────────────────────────────────────────────────────────
✗ v4.1 (حقن VS داخل @ppppokl):
  - تخفي اليوزر من regex البوتات ✅
  - لكن تكسر كشف @mention في تيليجرام → الزر لا يعمل ❌
  - واليوزر يبقى ظاهراً نصاً → بوتات متقدمة قد تفحص الأحرف

✓ v4.2 (الارتباط التشعبي - هذه الوحدة):
  - @ppppokl  → [للطلب اضغط هنا]  → يفتح https://t.me/ppppokl
  - 0777123456 → [للطلب اضغط هنا]  → يفتح https://wa.me/967777123456
  - https://.. → [للطلب اضغط هنا]  → يفتح الرابط نفسه
  ✅ قابل للضغط 100% (كيان TextUrl رسمي في تيليجرام - أضمن أنواع الروابط)
  ✅ نص اليوزر/الرقم/الرابط يختفي تماماً من نص الرسالة
     → regex البوتات (@username / أرقام / روابط) لا يجد شيئاً إطلاقاً
  ✅ الرسالة تبدو إعلاناً طبيعياً أنيقاً (زر عربي واضح بدل رموز خام)
  ✅ البشر يضغطون الزر وينتقلون - البوتات لا ترى شيئاً تخفيه البصريات

⚖️ يعمل جنباً إلى جنب مع Ghost Encoding: بقية النص يبقى مشفراً بالأحرف
   الخفية، والأزرار نفسها نظيفة (كيانات Telegram لا تحتمل التشويش).

📊 الإزاحات (offsets) محسوبة بوحدات UTF-16 حسب معيار Telegram API
   (الحروف الخفية E0100+ = وحدتين في UTF-16 - محسوبة بدقة).
"""

import re

# ═══════════════════════════════════════════════════════════════
# ⚙️ الإعدادات الافتراضية (تُقرأ من قاعدة البيانات عبر bot.py)
# ═══════════════════════════════════════════════════════════════

DEFAULT_ANCHOR = "للطلب اضغط هنا"
DEFAULT_COUNTRY_CODE = "967"

# أنصاف قطر مقترحة في القائمة (زر النص)
ANCHOR_PRESETS = [
    "للطلب اضغط هنا",
    "للتواصل اضغط هنا",
    "اضغط هنا للطلب",
    "تواصل معنا",
    "راسلنا الآن",
]

# أكواد دول مقترحة (زر كود الدولة)
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

# ═══════════════════════════════════════════════════════════════
# 🔎 كشف الرموز الحساسة (ترتيب البدائل مهم: الرابط قبل اليوزر)
# ═══════════════════════════════════════════════════════════════

SENSITIVE_TOKEN_RE = re.compile(
    r'(?P<url>'                                   # 1) روابط
    r'(?:https?://|www\.)\S+'
    r'|(?<![\w@.])(?:t\.me|wa\.me)/\S+'
    r')'
    r'|(?P<mention>@[a-zA-Z0-9_]{4,32})'          # 2) يوزرات تيليجرام
    r'|(?P<phone>\+?[0-9\u0660-\u0669\u06F0-\u06F9](?:[0-9\u0660-\u0669\u06F0-\u06F9\s\-()]{7,})[0-9\u0660-\u0669\u06F0-\u06F9])'  # 3) أرقام
)

# أرقام عربية/فارسية → غربية
_AR_DIGITS_MAP = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')

# علامات ترقيم قد تلحق آخر الرابط - تُنظف
_TRAILING_PUNCT = '.,،!؟:;)]»"\'…-'

_MIN_PHONE_DIGITS = 9   # أقل عدد أرقام يعتبر هاتفاً (يستبعد الأسعار والتواريخ)
_MAX_PHONE_DIGITS = 15  # أقصى عدد حسب معيار E.164


def u16len(s: str) -> int:
    """طول النص بوحدات UTF-16 (معيار إزاحات كيانات Telegram)"""
    return len(s.encode('utf-16-le')) // 2


def _normalize_digits(s: str) -> str:
    """تحويل كل الأرقام العربية/الفارسية إلى غربية"""
    return s.translate(_AR_DIGITS_MAP)


def _clean_url(raw: str) -> str:
    """تنظيف الرابط من علامات الترقيم الملحقة"""
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
    0777123456   → 967777123456  (كود الدولة 967)
    +967777123456 → 967777123456
    00967777123456 → 967777123456
    777123456    → 967777123456
    """
    digits = _normalize_digits(raw)
    digits = re.sub(r'\D', '', digits)          # حذف المسافات/الأقواس/الشرطات
    if digits.startswith('00'):
        digits = digits[2:]
    elif digits.startswith('0'):
        digits = digits.lstrip('0')
        cc = re.sub(r'\D', '', _normalize_digits(country_code)) or DEFAULT_COUNTRY_CODE
        digits = cc + digits
    elif not digits.startswith(re.sub(r'\D', '', _normalize_digits(country_code)) or DEFAULT_COUNTRY_CODE):
        cc = re.sub(r'\D', '', _normalize_digits(country_code)) or DEFAULT_COUNTRY_CODE
        digits = cc + digits
    return digits


def _build_target(kind: str, token: str, country_code: str):
    """بناء وجهة الارتباط التشعبي حسب نوع الرمز - يُرجع url أو None"""
    if kind == 'mention':
        username = token[1:]
        # أسماء تيليجرام تبدأ بحرف وتحوي أحرفاً/أرقام/شرطة سفلية فقط
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', username):
            return None
        return f"https://t.me/{username}"
    if kind == 'url':
        return _clean_url(token)
    if kind == 'phone':
        digits = _normalize_digits(token)
        digits = re.sub(r'\D', '', digits)
        # فلترة الأرقام القصيرة (أسعار/تواريخ/كميات)
        if len(digits.lstrip('+')) < _MIN_PHONE_DIGITS:
            return None
        if len(digits.lstrip('+')) > _MAX_PHONE_DIGITS:
            return None
        intl = _clean_phone(token, country_code)
        return f"https://wa.me/{intl}"
    return None


def find_sensitive_tokens(text: str):
    """قائمة (بداية, نهاية, نوع, النص) لكل الرموز الحساسة في النص"""
    tokens = []
    for m in SENSITIVE_TOKEN_RE.finditer(text):
        kind = 'url' if m.group('url') else ('mention' if m.group('mention') else 'phone')
        tokens.append((m.start(), m.end(), kind, m.group(0)))
    return tokens


def analyze(text: str, country_code: str = DEFAULT_COUNTRY_CODE):
    """
    تحليل إعلان: ما الرموز الحساسة التي سيحوّلها الدرع إلى أزرار؟
    يُرجع قائمة (النص, النوع, الوجهة) - للمعاينة في القوائم
    """
    results = []
    for s, e, kind, tok in find_sensitive_tokens(text):
        url = _build_target(kind, tok, country_code)
        if url:
            results.append((tok, kind, url))
    return results


def apply_link_guard(text: str,
                     anchor: str = DEFAULT_ANCHOR,
                     country_code: str = DEFAULT_COUNTRY_CODE):
    """
    🛡️ الدرع الرئيسي: تحويل اليوزرات/الهواتف/الروابط إلى أزرار ارتباط تشعبي

    المدخل:  النص بعد Ghost Encoding (الأحرف الخفية لا تعيق الكشف -
             الرموز الحساسة تمر نظيفة من المحرك عبر cloak_sensitive=False)

    المخرج:  (النص الجديد, قائمة كيانات)
             كيان = MessageEntityTextUrl(offset, length, url)
             بالإزاحات بوحدات UTF-16 محسوبة على النص النهائي

    مثال:
        ✅مرافق @ppppokl اتصل 0777123456
        يصبح:
        ✅مرافق للطلب اضغط هنا اتصل للطلب اضغط هنا
        (الزر الأول → t.me/ppppokl | الثاني → wa.me/967777123456)
    """
    if not text or not anchor:
        return text, []

    out_parts = []          # أجزاء النص النهائي
    entities = []           # (offset_utf16, length_utf16, url)
    u16_pos = 0             # موضع التقدم بوحدات UTF-16
    last = 0

    for m in SENSITIVE_TOKEN_RE.finditer(text):
        token = m.group(0)
        kind = 'url' if m.group('url') else ('mention' if m.group('mention') else 'phone')
        url = _build_target(kind, token, country_code)
        if not url:
            continue  # رقم قصير (سعر/تاريخ) - يبقى نصاً ظاهراً عادياً

        # الجزء العادي قبل الرمز
        if m.start() > last:
            seg = text[last:m.start()]
            out_parts.append(seg)
            u16_pos += u16len(seg)

        # الزر (نص الارتباط) - نظيف تماماً بلا أحرف خفية
        out_parts.append(anchor)
        entities.append((u16_pos, u16len(anchor), url))
        u16_pos += u16len(anchor)

        last = m.end()

    # الذيل بعد آخر رمز
    tail = text[last:]
    out_parts.append(tail)

    return ''.join(out_parts), entities


def build_telethon_entities(entities):
    """
    تحويل الكيانات إلى كيانات Telethon (MessageEntityTextUrl)
    لو telethon غير متاح يُرجع الصيغة الخام كما هي
    """
    if not entities:
        return None
    try:
        from telethon.tl.types import MessageEntityTextUrl
        return [
            MessageEntityTextUrl(offset=off, length=length, url=url)
            for off, length, url in entities
        ]
    except Exception:
        return entities


if __name__ == '__main__':
    # اختبار سريع
    ad = ("✅اعذار طبية تطبيق صحتي\n"
          "✅يوم /يومين /اسبوع\n"
          "✅تقرير طبي\n"
          "✅مرافق @ppppokl اتصل 0777123456\n"
          "قناة: t.me/myshop السعر 1500")
    new_text, ents = apply_link_guard(ad)
    print("النص الأصلي:")
    print(ad)
    print("\nبعد الدرع:")
    print(new_text)
    print("\nالكيانات:")
    for off, ln, url in ents:
        print(f"  offset={off} length={ln} url={url}")
        # التحقق من صحة الإزاحة
        b = new_text.encode('utf-16-le')
        print(f"  النص عند الإزاحة: {b[off*2:(off+ln)*2].decode('utf-16-le')!r}")
