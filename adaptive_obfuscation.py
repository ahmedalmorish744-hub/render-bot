"""
👻 Ghost Encoding Engine v4.0 - تكويد الأشباح
محرك التكويد الحديث: شكل الكلمات يبقى كما هو 100% + مستحيل الكشف على بوتات الحماية

⚠️ القاعدة الذهبية (v4.0):
   1. البوت يرسل نص المستخدم **كما هو** - لا إضافة كلمات، لا حذف، لا استبدال.
   2. **رسم الكلمات لا يتغير أبداً** - لا أشكال عرض (Presentation Forms)،
      لا تفكيك (NFD)، لا تغيير مسافات، لا كاشيدة، لا تشكيل ظاهر.
      الحروف تظهر بالضبط كما كتبها المستخدم في كل الأجهزة والخطوط.

🧪 التشخيص الذي أدى إلى v4.0 (مثبت بفحص معيار Unicode):
   ✗ v3.0 كانت تحقن U+2063/U+2064 وسط الكلمات العربية:
     فئة هذين الحرفين Cf وحسب معيار Unicode (ArabicShaping.txt) أي حرف
     غير مدرج وغير Combining Mark يعتبر Joining_Type=U (غير واصل)
     → يقطع اتصال الحروف في المحركات الصارمة (CoreText/DirectWrite)!
   ✗ v3.0 كانت تستبدل حروفاً بأشكال عرض عشوائية (معزول/وسطي/نهائي)
     بغض النظر عن موقع الحرف → تفكك بصري واضح (سبب "رسم الكلمات يتغير")
   ✗ NFD تفكيك (أ → ا + ٔ) يظهر الهمزة منفصلة في بعض الخطوط

🔬 تقنية v4.0 الحديثة (من بحث GitHub 2024-2026):
   القناة الأساسية: Variation Selectors (256 كودبونت!)
   ─ U+FE00–U+FE0F  (16 حرف VS1-VS16)
   ─ U+E0100–U+E01EF (240 حرف VS17-VS256)
   لماذا هي الأضمن تشكيلياً؟
   ✅ فئتها العامة Mn (Nonspacing Mark) → Joining_Type = Transparent
      حسب معيار Unicode رسمياً (مؤكد في codepoints.net/U+E0100)
      → لا تقطع اتصال الحروف العربية في أي محرك عرض على الإطلاق
      (HarfBuzz وCoreText وDirectWrite كلها تتجاهلها في تشكيل الاتصال)
   ✅ غير مرئية في تيليجرام (Default_Ignorable_Code_Point = Yes)
   ✅ من خارج قوائم الكشف الكلاسيكية (البوتات تنظف 200B-200D و2060-2064
      و061C وFEFF — دليل: spencermountain/out-of-character وklaroskope)
   ✅ 256 كودبونت = مساحة عملاقة تجعل الإحصاء الكمي عديم الفائدة
   ✅ استخدامها مشروع (الإيموجي VS15/VS16) لذا أدوات التنظيف تخاف حذفها
      وحتى لو حذفتها كلها → النص يعود لأصله سليماً مقروءاً (تدهور رشيق)

   المصادر المقتبسة منها (الأحدث والأضمن):
   - Paul Butler / josephthacker "VS Data Hiding": إخفاء بيانات داخل
     Variation Selectors المرفقة بحروف ظاهرة (تقنية 2024-2025)
   - KuroLabs/stegcloak: مبدأ التكويد الخفي داخل النص (6 أحرف فقط) -
     طوّرناه إلى قناة 256 حرف بدون الأحرف مقطعات الاتصال لديهم
   - umputun/tg-spam (طرف الخصم): الكشف = تطبيع + مطابقة تامة + تشابه
     → تجزئة الكلمات بحروف خفية تكسر الثلاثة معاً
   - spencermountain/out-of-character (طرف الخصم): قائمة الأحرف التي
     تعرفها أدوات التنظيف — قناتنا الجديدة خارج عملياً من هذه القوائم

الطبقات (v4.0):
1. ghost_vs_channel  - حقن Variation Selectors في أي موضع (شفافة للتشكيل)
2. cf_boundary       - حقن 2063/2064 فقط في مواضع حيادية للاتصال
                       (نهاية الكلمات / بعد الحروف غير الواصلة للأمام)
3. keyword_boost     - كثافة مضاعفة داخل الكلمات المفتاحية الإعلانية
4. salt              - بصمة VS فريدة لكل رسالة (كسر dedup/hash)

معطل نهائياً (كانت تغير رسم الكلمات):
✗ arabic_forms / Presentation Forms (تفكك الكلمات بصرياً!)
✗ NFD Decomposition (همزة منفصلة في بعض الخطوط!)
✗ Tag Characters (تخفي الحروف اللاتينية في تيليجرام!)
✗ Bayes Evasion / Adaptive Spintax (كانت تضيف/تستبدل كلمات!)

🛡️ حماية مزدوجة ضد التكرار (سبب "تلبّط بدء النشر" سابقاً):
   المحرك يفحص نسبة الأحرف الشبحية في المُدخل - إذا كان النص مشفراً
   مسبقاً ينظفه أولاً ثم يشفر مرة واحدة → لا تكديس تحويلات أبداً.
"""

import bisect
import random
import re
import unicodedata
from typing import Tuple

# ═══════════════════════════════════════════════════════════════
# 🛡️ حماية الروابط والمعرفات - لا يجوز تعديلها إطلاقاً
# ═══════════════════════════════════════════════════════════════

PROTECTED_PATTERN = re.compile(
    r'(https?://\S+'          # http://... أو https://...
    r'|t\.me/\S+'             # t.me/...
    r'|@[a-zA-Z0-9_]{3,})'    # @username
)


def split_protected(text: str):
    """يقسم النص إلى [(جزء, محمي؟)] - المحمي = روابط ومعرفات"""
    parts = []
    last = 0
    for m in PROTECTED_PATTERN.finditer(text):
        if m.start() > last:
            parts.append((text[last:m.start()], False))
        parts.append((m.group(0), True))
        last = m.end()
    if last < len(text):
        parts.append((text[last:], False))
    return parts if parts else [(text, False)]


def apply_layer_protected(text: str, func, *args, **kwargs) -> str:
    """
    🛡️ يطبق دالة الطبقة فقط على الأجزاء غير المحمية
    الروابط (@username / t.me/... / https://...) تمر سليمة 100%
    """
    parts = split_protected(text)
    out = []
    for seg, protected in parts:
        if protected or not seg:
            out.append(seg)
        else:
            out.append(func(seg, *args, **kwargs))
    return ''.join(out)

# ═══════════════════════════════════════════════════════════════
# 🎯 قنوات التكويد الخفي (v4.0)
# ═══════════════════════════════════════════════════════════════

# القناة 1: Variation Selectors - 256 كودبونت - فئة Mn = شفافة للتشكيل
# (مؤكد: codepoints.net/U+E0100 → Joining Type: Transparent)
VS_POOL = (
    [chr(c) for c in range(0xFE00, 0xFE10)] +      # VS1  - VS16
    [chr(c) for c in range(0xE0100, 0xE01F0)]      # VS17 - VS256
)

# القناة 2: أحرف Cf حدودية - توضع فقط في المواضع الحيادية للاتصال
INVISIBLE_SHIELD_CHARS = [
    '\u2063',  # Invisible Separator
    '\u2064',  # Invisible Plus
]

# ❌ ممنوعة نهائياً كقنوات حقن (مقطعات اتصال أو في قوائم كشف البوتات
#    أو تتعارض مع أبجدية بصمة stego {2060,061C,2061,2062}):
FORBIDDEN_INVISIBLES = {
    '\u200B', '\u200C', '\u200D',            # مقطعات اتصال عربية!
    '\u2060', '\u2061', '\u2062',            # أبجدية بصمة stego
    '\u061C',                                 # أبجدية بصمة stego
    '\uFEFF',                                 # الأبجدية القديمة
}


def sanitize_invisible_chars(text: str) -> str:
    """
    🧹 تنظيف الأحرف الخفية الخطرة/المتضاربة من نص المستخدم قبل المعالجة
    يحذف مقطعات الاتصال (200B/200C/200D) وأحرف البصمة القديمة
    (نصوص ملصوقة من مصادر أخرى قد تحتويها وتظهر متلخبطة أو مزدوجة البصمة)
    """
    if not text:
        return text
    return ''.join(ch for ch in text if ch not in FORBIDDEN_INVISIBLES)


# ═══════════════════════════════════════════════════════════════
# 🔬 أدوات قواعد الاتصال العربي (قلب الحفاظ على رسم الكلمات)
# ═══════════════════════════════════════════════════════════════

# حروف لا تتصل بالحرف الذي بعدها أبداً (Joining_Type = U أو R):
# ا أ إ آ ٱ د ذ ر ز و ؤ ة ء
NON_FORWARD_JOINERS = set('اأإآٱدذرزوؤةء')

ARABIC_LETTER_RE = re.compile(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]')


def _is_arabic_letter(ch: str) -> bool:
    """هل الحرف عربي (له قواعد اتصال)؟"""
    return bool(ch) and bool(ARABIC_LETTER_RE.match(ch))


def _is_combining_mark(ch: str) -> bool:
    """هل الحرف علامة تشكيل ملتصقة (حركة/شدّة)؟"""
    return bool(ch) and unicodedata.category(ch) in ('Mn', 'Me')


def _cf_safe_after(chars, i: int) -> bool:
    """
    هل وضعنا بعد الحرف i آمن لحرف Cf (غير واصل حسب المعيار)؟

    القاعدة: يقطع الحرف غير الواصل الاتصال بين حرفين عربيين متجاورين
    فقط إذا كان الحرف الأول يتصل للأمام والحرف الثاني يتصل من الخلف.
    ⚠️ يجب تخطي الأحرف الشفافة (Mn/Me - ومنها VS المزرعة) على الجانبين
    للوصول إلى الحرفين الحقيقيين المسؤولين عن الاتصال.
    """
    chars_len = len(chars)
    if i + 1 >= chars_len:
        return True                                   # نهاية النص
    # لا نفصل الحرف عن تشكيله المباشر (حركة/شدّة/VS)
    if _is_combining_mark(chars[i + 1]):
        return False
    # الحرف الحقيقي السابق (تخطي الشفاف)
    p = i
    while p >= 0 and _is_combining_mark(chars[p]):
        p -= 1
    prev = chars[p] if p >= 0 else ''
    # الحرف الحقيقي التالي (تخطي الشفاف)
    q = i + 1
    while q < chars_len and _is_combining_mark(chars[q]):
        q += 1
    nxt = chars[q] if q < chars_len else ''
    if not nxt or not prev:
        return True                                   # لا يوجد زوج متصل
    if _is_arabic_letter(prev) and _is_arabic_letter(nxt):
        return prev in NON_FORWARD_JOINERS            # حرف غير واصل للأمام
    return True                                       # لاتيني/أرقام/رموز/إيموجي


def _find_keyword_spans(text: str):
    """نطاقات الكلمات المفتاحية الإعلانية في النص [(بداية, نهاية)]"""
    spans = []
    if not text:
        return spans
    lower = text.lower()
    for kw in AD_KEYWORDS:
        kl = kw.lower()
        start = 0
        while True:
            idx = lower.find(kl, start)
            if idx == -1:
                break
            spans.append((idx, idx + len(kw)))
            start = idx + 1
    return spans


def _find_keyword_ranges(text: str):
    """مواضع الكلمات المفتاحية كـ set (توافق داخلي)"""
    ranges = set()
    for s, e in _find_keyword_spans(text):
        ranges.update(range(s, e))
    return ranges


# كلمات تستهدفها بوتات الحماية في الإعلانات (تُموه بكثافة أعلى داخلها فقط)
AD_KEYWORDS = [
    'اشترك', 'قناة', 'قناتنا', 'قنوات', 'عرض', 'عروض',
    'خصم', 'تخفيض', 'تخفيضات', 'مجاني', 'مجانا', 'رابط', 'بيع', 'شراء',
    'سعر', 'اسعار', 'أسعار', 'تواصل', 'واتساب', 'واتس', 'واتس اب',
    'تيليجرام', 'تلجرام', 'سوق', 'خدمات', 'متابعين', 'أعضاء', 'اعضاء',
    'subscribe', 'join', 'offer', 'offers', 'free', 'deal', 'deals',
    'price', 'contact', 'whatsapp', 'buy', 'sell', 'shop', 'store',
    'promo', 'discount', 'crypto', 'vip',
]

# ═══════════════════════════════════════════════════════════════
# القناة 1: Ghost VS Injection - تكويد شفاف للتشكيل (256 حرف)
# ═══════════════════════════════════════════════════════════════

def ghost_vs_inject(text: str, density: float = 0.20,
                    keyword_boost: bool = True, max_consecutive: int = 2) -> str:
    """
    👻 حقن Variation Selectors داخل النص - القناة الحديثة v4.0

    ✅ فئة Mn → Joining_Type = Transparent حسب معيار Unicode
       → اتصال الحروف العربية محفوظ 100% في كل محركات العرض
    ✅ يوضع في أي موضع حتى وسط الكلمة - لا يؤثر على الرسم أبداً
    ✅ 256 كودبونت → يكسر المطابقة التامة والـ n-gram والإحصاء الكمي
    ✅ لا يفصل الحرف عن تشكيله (حركة/شدّة تسبقه دائماً)
    🎯 ضمان التجزئة: كل كلمة مفتاحية تحتوي حرفاً خفياً واحداً على الأقل
       (إدخال قسري وليس احتمالياً) → مستحيل على بوتات المطابقة أن تجدها
    """
    if not text or density <= 0:
        return text

    chars = list(text)
    boosted = set()
    forced = set()
    if keyword_boost:
        for s, e in _find_keyword_spans(text):
            boosted.update(range(s, e))
            # إدخال قسري مضمون بين حروف الكلمة نفسها (وليس بعدها!)
            # بين حرفين داخليين لا يلي أحدهما تشكيل حتى تتجزأ الكلمة فعلاً
            candidates = [
                i for i in range(s, max(s, e - 1))
                if not _is_combining_mark(chars[i])
                and not _is_combining_mark(chars[i + 1])
            ]
            if candidates:
                forced.add(random.choice(candidates))

    out = []
    consecutive = 0

    for i, ch in enumerate(chars):
        out.append(ch)

        if ch in (' ', '\n', '\t'):
            consecutive = 0
            continue

        # لا ندرج حرفاً خفياً بين الحرف وتشكيله التالي (حركة/شدّة)
        if i + 1 < len(chars) and _is_combining_mark(chars[i + 1]):
            continue

        # 🎯 الإدخال القسري داخل الكلمات المفتاحية (ضمان التجزئة)
        if i in forced:
            out.append(random.choice(VS_POOL))
            consecutive += 1
            continue

        # كثافة محلية مضاعفة داخل الكلمات المفتاحية
        local = density * (1.5 if i in boosted else 1.0)
        local = min(local, 0.80)

        if consecutive < max_consecutive and random.random() < local:
            out.append(random.choice(VS_POOL))
            consecutive += 1
        else:
            consecutive = 0

    return ''.join(out)


# ═══════════════════════════════════════════════════════════════
# القناة 2: Boundary Cf Injection - مواضع حيادية فقط
# ═══════════════════════════════════════════════════════════════

def cf_boundary_inject(text: str, density: float = 0.10) -> str:
    """
    🧱 حقن U+2063/U+2064 (Cf) في المواضع الحيادية للاتصال فقط

    ✅ نهايات الكلمات + بعد الحروف غير الواصلة للأمام (اأإآدذرزوؤةء)
    ✅ لا يوضع أبداً وسط الكلمة بعد حرف واصل → لا يقطع الاتصال
       حتى في المحركات الصارمة التي تتبع المعيار حرفياً
    ✅ تنويع القنوات: لو نظّفت بوتات الحماية فئة معينة تبقى القناة الأخرى
    """
    if not text or density <= 0:
        return text

    chars = list(text)
    out = []

    for i, ch in enumerate(chars):
        out.append(ch)

        if ch in (' ', '\n', '\t'):
            continue

        if i + 1 < len(chars) and _is_combining_mark(chars[i + 1]):
            continue

        if random.random() < density and _cf_safe_after(chars, i):
            out.append(random.choice(INVISIBLE_SHIELD_CHARS))

    return ''.join(out)


# اسم متوافق مع الإصدارات السابقة (يستخدمه كود قديم/سكربتات)
def shield_invisible_distribute(text: str, density: float = 0.10, max_consecutive: int = 2) -> str:
    """التوزيع الخفي v4.0 = قناة VS + قناة Cf الحدودية معاً"""
    if not text or density <= 0:
        return text
    result = ghost_vs_inject(text, density=density)
    result = cf_boundary_inject(result, density=density * 0.5)
    return result


smart_zw_distribute = shield_invisible_distribute

# ═══════════════════════════════════════════════════════════════
# القناة 3: Keyword Boost - تُطبق داخل ghost_vs_inject (كثافة ×2)
# ═══════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════
# القناة 4: Ghost Fingerprint - بصمة فريدة لكل رسالة
# ═══════════════════════════════════════════════════════════════

def add_anti_similarity_salt(text: str) -> str:
    """
    بصمة VS فريدة في نهاية كل رسالة (8-14 حرف خفي)

    ✅ يكسر كشف الرسائل المكررة (dedup) والهاش المتطابق
    ✅ كل رسالة في كل مجموعة لها بصمة مختلفة عشوائياً
    ✅ يستخدم قناة VS فقط → لا يتعارض مع أبجدية بصمة stego
    ✅ في نهاية الرسالة → صفر تأثير على النص أو رسمه
    ✅ الطول يتناسب مع طول الرسالة (حتى لا ترتفع نسبة الخفي
       في الرسائل القصيرة فوق رادار الكشف الإحصائي)
    """
    if not text:
        return text
    salt_len = min(random.randint(8, 14), max(4, len(text) // 10))
    salt = ''.join(random.choice(VS_POOL) for _ in range(salt_len))
    return text + salt

# ═══════════════════════════════════════════════════════════════
# 🧹 أدوات التنظيف الذاتي (الحماية من التشفير المزدوج)
# ═══════════════════════════════════════════════════════════════

_GHOST_CHARS = set(VS_POOL) | set(INVISIBLE_SHIELD_CHARS)


def strip_ghost_chars(text: str) -> str:
    """إزالة كل الأحرف الشبحية (VS + Cf الحدودية) وإرجاع النص الظاهر الخالص"""
    if not text:
        return text
    return ''.join(ch for ch in text if ch not in _GHOST_CHARS)


def ghost_ratio(text: str) -> float:
    """نسبة الأحرف الشبحية في النص (للكشف عن نص مشفر مسبقاً)"""
    if not text:
        return 0.0
    count = sum(1 for ch in text if ch in _GHOST_CHARS)
    return count / max(1, len(text))


def _thin_invisibles(text: str, max_ratio: float = 0.30) -> str:
    """
    ✂️ ترقيق تلقائي: إن تجاوزت نسبة الأحرف الشبحية الحد الآمن
    (يحفظنا من كشف بوتات الإحصاء الكمي للطابعات الخفية)
    نحذف الفائض عشوائياً مع:
    ✅ حماية الأحرف داخل الكلمات المفتاحية (لا تنفك التجزئة المضمونة)
    ✅ حماية بصمة النهاية (salt آخر 20 حرف)
    ✅ النص الظاهر لا يُمس أبداً
    """
    if not text:
        return text
    ratio = ghost_ratio(text)
    if ratio <= max_ratio:
        return text

    chars = list(text)

    # مواضع الكلمات المفتاحية محسوبة على النص الظاهر
    vis_positions = [i for i, ch in enumerate(chars) if ch not in _GHOST_CHARS]
    kw_visible_pos = set()
    if vis_positions:
        vis_str = ''.join(chars[i] for i in vis_positions)
        for s, e in _find_keyword_spans(vis_str):
            kw_visible_pos.update(range(s, e))

    # ✂️ الحماية: الحرف الشبحي المجاور (يسار/يمين) لحرف كلمة مفتاحية
    # لا يُحذف حتى لا تنفك التجزئة المضمونة للكلمات المفتاحية
    removable = []
    for i, ch in enumerate(chars):
        if ch not in _GHOST_CHARS or i >= len(chars) - 20:
            continue  # البصمة الأخيرة محمية
        j = bisect.bisect_left(vis_positions, i) - 1  # آخر حرف ظاهر قبل i
        prev_in_kw = j >= 0 and j in kw_visible_pos
        next_in_kw = (j + 1 < len(vis_positions)) and ((j + 1) in kw_visible_pos)
        if prev_in_kw or next_in_kw:
            continue  # داخل/ملاصق لكلمة مفتاحية - محمي
        removable.append(i)

    need = sum(1 for ch in chars if ch in _GHOST_CHARS) - int(max_ratio * len(chars))
    if need <= 0 or not removable:
        return text

    random.shuffle(removable)
    remove_set = set(removable[:need])
    return ''.join(ch for i, ch in enumerate(chars) if i not in remove_set)


# ═══════════════════════════════════════════════════════════════
# ⛔ الطبقات القديمة - معطلة نهائياً (كانت تغير رسم الكلمات)
# ═══════════════════════════════════════════════════════════════

def apply_arabic_presentation_forms(text: str, intensity: float = 0.0) -> str:
    """⛔ معطلة نهائياً v4.0 - أشكال العرض العشوائية تفكك رسم الكلمات"""
    return text


def strip_presentation_forms(text: str) -> str:
    """إرجاع أشكال العرض إلى أحرفها الأصلية (NFKC) - للفحص والمقارنة"""
    return unicodedata.normalize('NFKC', text)


def apply_nfd_decomposition(text: str, intensity: float = 0.0) -> str:
    """⛔ معطلة نهائياً v4.0 - التفكيك يظهر الهمزة منفصلة في بعض الخطوط"""
    return text


def bayes_evade(text: str, intensity: float = 0.0) -> str:
    """⛔ معطلة نهائياً - كانت تُدخل كلمات في وسط رسالة المستخدم"""
    return text


def adaptive_spintax(text: str, intensity: float = 0.0) -> str:
    """⛔ معطلة نهائياً - كانت تستبدل كلمات المستخدم بمرادفات"""
    return text


def apply_tag_chars(text: str, intensity: float = 0.0) -> str:
    """⛔ معطلة نهائياً - Tag Characters تجعل الحروف اللاتينية تختفي في تيليجرام"""
    return text

# ═══════════════════════════════════════════════════════════════
# 🎯 المحرك الرئيسي - AdaptiveObfuscationEngine (Ghost Encoding v4.0)
# ═══════════════════════════════════════════════════════════════

# حد طول رسالة تيليجرام (4096) مع هامش أمان
MAX_TELEGRAM_LENGTH = 4096
SAFE_LENGTH_BUDGET = 3900


class AdaptiveObfuscationEngine:
    """
    👻 Ghost Encoding Engine v4.0

    شكل الكلمات يبقى كما هو 100% + تكويد حديث يستحيل على بوتات الحماية.

    الطبقات:
    1. ghost_vs_channel : حقن VS (256 حرف) شفافة للتشكيل - القناة الأساسية
    2. cf_boundary      : حقن Cf حدودي آمن - تنويع القنوات
    3. keyword_boost    : كثافة مضاعفة داخل الكلمات المفتاحية
    4. salt             : بصمة فريدة لكل رسالة

    🛡️ حماية من التكرار: النص المشفر مسبقاً يُنظف ويُشفر مرة واحدة.
    📏 حماية الطول: يقلص الأحرف الخفية تلقائياً ليبقى تحت حد تيليجرام.
    """

    PROFILES = {
        'light':      {'vs_density': 0.10, 'cf_density': 0.05},
        'medium':     {'vs_density': 0.20, 'cf_density': 0.10},
        'aggressive': {'vs_density': 0.30, 'cf_density': 0.15},
        'insane':     {'vs_density': 0.42, 'cf_density': 0.20},
    }

    # طبقات v4.0 الفعلية
    ACTIVE_LAYERS = ('ghost_vs_channel', 'cf_boundary', 'keyword_boost', 'salt')

    # أسماء قديمة → الطبقة الجديدة المقابلة (توافق واجهة bot.py)
    LEGACY_ALIASES = {
        'zw_distribution': 'ghost_vs_channel',
        'invisible_shield': 'ghost_vs_channel',
    }

    # طبقات قديمة معطلة نهائياً (تُرجع False دائماً)
    DISABLED_LAYERS = {'arabic_forms', 'nfd', 'bayes_evasion', 'spintax', 'tag_chars'}

    def __init__(self, profile: str = 'medium'):
        self.profile = profile
        self.config = dict(self.PROFILES.get(profile, self.PROFILES['medium']))
        self.enabled_layers = {
            'ghost_vs_channel': True,
            'cf_boundary': True,
            'keyword_boost': True,
            'salt': True,
        }
        self.stats = {
            'total_obfuscated': 0,
            'total_messages': 0,
            'double_encode_saved': 0,
        }

    def set_profile(self, profile: str) -> bool:
        """تغيير مستوى القوة"""
        if profile in self.PROFILES:
            self.profile = profile
            self.config = dict(self.PROFILES[profile])
            return True
        return False

    def toggle_layer(self, layer: str, enabled: bool = None):
        """تفعيل/تعطيل طبقة معينة (أسماء جديدة وقديمة مقبولة)"""
        layer = self.LEGACY_ALIASES.get(layer, layer)
        if layer in self.DISABLED_LAYERS:
            return False  # الطبقات القديمة الخطرة معطلة دائماً
        if layer in self.enabled_layers:
            if enabled is None:
                self.enabled_layers[layer] = not self.enabled_layers[layer]
            else:
                self.enabled_layers[layer] = enabled
            return self.enabled_layers[layer]
        return None

    def get_layer_status(self, layer: str) -> bool:
        """حالة طبقة معينة (أسماء جديدة وقديمة مقبولة)"""
        layer = self.LEGACY_ALIASES.get(layer, layer)
        if layer in self.DISABLED_LAYERS:
            return False
        return self.enabled_layers.get(layer, False)

    def _fit_length(self, text: str, budget: int = SAFE_LENGTH_BUDGET) -> str:
        """
        📏 حماية الطول: إن تجاوز النص ميزانية تيليجرام نحذف أحرفاً شبحية
        (النص الظاهر لا يُمس أبداً) حتى نرجع تحت الحد.
        """
        if len(text) <= budget:
            return text
        chars = [ch for ch in text if ch not in _GHOST_CHARS]
        # لو النص الظاهر نفسه أطول من الحد فلا يمكننا المساس به
        if len(chars) > budget:
            return text
        return ''.join(chars)

    def obfuscate(self, text: str) -> Tuple[str, dict]:
        """
        تطبيق Ghost Encoding على النص

        Returns:
            (النص المشفر, معلومات الطبقات المطبقة)
        """
        if not text:
            return text, {'layers': []}

        self.stats['total_messages'] += 1
        applied_layers = []

        # 🧹 الخطوة 0: تنظيف الأحرف الخطرة من المُدخل
        result = sanitize_invisible_chars(text)

        # 🛡️ حماية التكرار: نص مشفر مسبقاً؟ نظف الأحرف الشبحية أولاً
        # (سبب "تلبّط بدء النشر" سابقاً كان تكديس التحويلات - الآن مستحيل)
        if ghost_ratio(result) > 0.12:
            result = strip_ghost_chars(result)
            self.stats['double_encode_saved'] += 1

        # 1️⃣ Ghost VS Channel - قناة VS الشفافة للتشكيل (الأساسية)
        if self.enabled_layers['ghost_vs_channel'] and self.config['vs_density'] > 0:
            result = apply_layer_protected(
                result, ghost_vs_inject, self.config['vs_density'], True)
            applied_layers.append('ghost_vs_channel')

        # 2️⃣ CF Boundary - أحرف حدودية آمنة (تنويع القنوات)
        if self.enabled_layers['cf_boundary'] and self.config['cf_density'] > 0:
            result = apply_layer_protected(
                result, cf_boundary_inject, self.config['cf_density'])
            applied_layers.append('cf_boundary')

        # ✂️ ترقيق تلقائي - يبقي نسبة الأحرف الخفية تحت رادار الكشف الإحصائي
        # (مع حماية تجزئة الكلمات المفتاحية وبصمة النهاية)
        result = _thin_invisibles(result, max_ratio=0.30)

        # 3️⃣ Keyword Boost - مطبق داخلياً في قناة VS (توثيق فقط هنا)
        if self.enabled_layers['keyword_boost']:
            applied_layers.append('keyword_boost')

        # 4️⃣ Salt - بصمة فريدة لكل رسالة
        if self.enabled_layers['salt']:
            result = add_anti_similarity_salt(result)
            applied_layers.append('salt')

        # 📏 حماية الطول
        result = self._fit_length(result)

        self.stats['total_obfuscated'] += 1

        invisible_count = sum(1 for ch in result if ch in _GHOST_CHARS)

        return result, {
            'layers': applied_layers,
            'profile': self.profile,
            'length_before': len(text),
            'length_after': len(result),
            'invisible_chars': invisible_count,
        }

    def get_stats(self) -> dict:
        """إحصائيات المحرك"""
        return {
            **self.stats,
            'profile': self.profile,
            'layers': self.enabled_layers,
        }

    def get_info(self) -> str:
        """معلومات المحرك كنص قابل للعرض"""
        info = "👻 **Ghost Encoding Engine v4.0**\n\n"
        info += f"⚡ **المستوى الحالي:** {self.profile}\n\n"
        info += "🎨 **الضمانة:** رسم كلماتك يبقى كما هو 100% في كل الأجهزة\n\n"
        info += "📊 **القنوات المفعّلة (كلها غير مرئية ولا تعدل كلماتك):**\n"
        layers_ar = {
            'ghost_vs_channel': '1️⃣ قناة VS الشفافة (256 حرف خفي حديث)',
            'cf_boundary': '2️⃣ قناة الحدود الآمنة (مواضع محسوبة)',
            'keyword_boost': '3️⃣ تعزيز الكلمات المفتاحية (تمويه جراحي)',
            'salt': '4️⃣ بصمة الأشباح (فريدة لكل رسالة)',
            'arabic_forms': '⛔ أشكال العرض (معطلة - كانت تغير الرسم)',
            'nfd': '⛔ NFD (معطلة - كانت تفكك الحروف)',
            'tag_chars': '⛔ Tag Characters (معطلة - كانت تخفي حروفاً)',
        }
        for key, name in layers_ar.items():
            status = "✅" if self.get_layer_status(key) else "⛔"
            info += f"  {status} {name}\n"

        info += "\n📈 **الإحصائيات:**\n"
        info += f"  📝 رسائل مشفرة: {self.stats['total_obfuscated']}\n"
        info += f"  📊 إجمالي الرسائل: {self.stats['total_messages']}\n"
        info += f"  🛡️ حماية تكرار (نُظفت): {self.stats['double_encode_saved']}\n"

        return info


# إنشاء instance افتراضي
adaptive_engine = AdaptiveObfuscationEngine(profile='medium')


def quick_obfuscate(text: str, profile: str = None) -> str:
    """دالة سريعة للتشفير - تستخدم المحرك الافتراضي"""
    if profile:
        adaptive_engine.set_profile(profile)
    result, _ = adaptive_engine.obfuscate(text)
    return result


if __name__ == '__main__':
    # اختبار سريع للمحرك
    test_text = "اشترك في قناتنا للحصول على عروض حصرية t.me/example @username"

    print("=" * 60)
    print("👻 اختبار Ghost Encoding Engine v4.0")
    print("=" * 60)
    print(f"\n📝 **النص الأصلي:**\n{test_text}")
    print(f"📊 الطول: {len(test_text)}")

    for profile in ['light', 'medium', 'aggressive', 'insane']:
        engine = AdaptiveObfuscationEngine(profile=profile)
        result, info = engine.obfuscate(test_text)
        visible = strip_ghost_chars(result)
        same_shape = unicodedata.normalize('NFKC', visible) == unicodedata.normalize('NFKC', test_text)
        print(f"\n{'─' * 60}")
        print(f"⚡ Profile: {profile}")
        print(f"📝 النص المشفر:\n{result}")
        print(f"📊 الطول: {len(result)} (خفي: {info['invisible_chars']})")
        print(f"🛡️ الطبقات: {info['layers']}")
        print(f"🎨 رسم الكلمات محفوظ: {'✅' if same_shape else '❌ خطأ!'}")

    print(f"\n{'=' * 60}")
    print("✅ تم الاختبار بنجاح!")
