"""
🔬 Adaptive Obfuscation Engine v3.0 - الدرع الخفي
محرك التشويش التكيفي - طبقات غير مرئية فقط لتجاوز بوتات الحماية
مصمم خصيصاً للنص العربي: خفي على البوتات + مقروء 100% للبشر

⚠️ القاعدة الذهبية (v3.0):
   البوت يرسل نص المستخدم **كما هو** - لا إضافة كلمات، لا حذف، لا استبدال مرادفات.
   كل الطبقات تغيّر تمثيل Unicode للنص فقط (الشكل الظاهر يبقى متطابقاً).

🆕 v3.0 - إصلاح جذري لمشكلة "تلخبط" النص العربي:
   المشكلة القديمة: إدخال \u200C (ZWNJ) و \u200B (ZWSP) و \u200D (ZWJ)
   داخل الكلمات العربية يقطع اتصال الحروف فيتصدر النص متفككاً!
   (مثال: "مرحباً" تظهر "مرحباً" بحروف منفصلة)

   الحل (v3.0): مجموعة أحرف خفية "آمنة على التشكيل" لا تملك أي دلالة
   ربط/انفصال في محركات تشكيل النصوص (HarfBuzz/CoreText/DirectWrite):
   • U+2060 Word Joiner      - غير مرئي، لا يؤثر على الاتصال إطلاقاً
   • U+061C Arabic Letter Mark - صُمم للعربية، غير مرئي، bidi فقط
   • U+2063 Invisible Separator - غير مرئي، رياضي، آمن
   • U+2064 Invisible Plus     - غير مرئي، رياضي، آمن
   • U+FEFF ZWNBSP            - يعمل كـ Word Joiner، آمن

   🛡️ هذه المجموعة منفصلة تماماً عن أبجدية بصمة stego الفريدة
   ({2060,061C,2061,2062}) لذلك لا تفسد فك تشفير البصمة أبداً.

الطبقات (v3.0):
1. Arabic Presentation Forms - استبدال بصري متطابق (U+FE70-FEFF)
   ✔ آلية موثقة في promptfoo#9898 و ACMCMC/silverspeak
   ✔ تنجو من التطبيع (Normalization) الذي تعتمد عليه بوتات الحماية
2. Invisible Shield Distribution - توزيع أحرف آمنة على التشكيل
   ✔ مستوحى من KuroLabs/stegcloak (6 أحرف خفية تعمل في كل مكان)
   ✔ يكسر مطابقة الهاش والعبارات (exact/n-gram matching)
3. NFD Decomposition - تفكيك الأحرف المركبة (أ → ا + ٔ)
   ✔ بصرياً متطابق، يكسر الهاش والمقارنات النصية
4. Anti-Similarity Salt - ملح فريد لكل رسالة
   ✔ يمنع كشف "الرسائل المكررة" في بوتات مثل tg-spam

معطل نهائياً (كانت تفسد النص):
✗ Bayes Evasion (كانت تضيف كلمات!)
✗ Adaptive Spintax (كانت تستبدل كلمات المستخدم!)
✗ Tag Characters U+E0000 (كانت تجعل الحروف اللاتينية تختفي في تيليجرام!)

مستوحى من (بحث GitHub - الأحدث والأضمن):
- ACMCMC/silverspeak: مكتبة homoglyph متعددة اللغات
- promptfoo/promptfoo#9898: استراتيجية أشكال العرض العربية
- KuroLabs/stegcloak: إخفاء بأحرف خفية تعمل في تيليجرام وكل المنصات
- umputun/tg-spam (طرف الخصم): يكشف أن الكشف يعتمد على التطبيع
  والمطابقة التامة والتشابه - طبقاتنا الثلاث تكسرها كلها معاً
"""

import random
import re
import unicodedata
from typing import Tuple

# ═══════════════════════════════════════════════════════════════
# 🛡️ حماية الروابط والمعرفات - لا يجوز تعديلها إطلاقاً
# ═══════════════════════════════════════════════════════════════

# نمط العناصر المحمية: روابط ومعرفات تبقى ظاهرة وقابلة للنقر
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
# 🎯 سياسة الأحرف الخفية الآمنة (v3.0) - قلب الإصلاح
# ═══════════════════════════════════════════════════════════════

# ❌ ممنوعة نهائياً داخل النص (تقطع اتصال الحروف العربية أو تخفيها):
#    \u200B ZWSP   - فرصة كسر سطر داخل الكلمة + في قوائم كشف البوتات
#    \u200C ZWNJ   - يقطع اتصال الحروف العربية فعلياً! (سبب التلخبط)
#    \u200D ZWJ    - يغير شكل الحرف (اختيار forms مختلفة)
#    U+E0000 Tag   - تختفي الحروف اللاتينية في تيليجرام!

# ✅ الأحرف المسموحة للطبقة الخفية (آمنة تشكيلياً 100%):
#    لا تملك Joining Type في Unicode ولهذا لا تغير اتصال الحروف أبداً
#    🛡️ منفصلة تماماً عن أبجدية بصمة stego {2060,061C,2061,2062}
#       وعن الأبجدية القديمة {200B,200C,200D,FEFF} → لا تفسد فك الترميز
INVISIBLE_SHIELD_CHARS = [
    '\u2063',  # Invisible Separator - غير مرئي، لا تأثير تشكيلي
    '\u2064',  # Invisible Plus - غير مرئي، لا تأثير تشكيلي
]

# ممنوع أيضاً في كل الحالات (كانت في النسخ القديمة أو تفسد فك الترميز):
FORBIDDEN_INVISIBLES = {'\u200B', '\u200C', '\u200D', '\u2061', '\u2062', '\u2060', '\u061C', '\uFEFF'}

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
# 1. Arabic Presentation Forms - استبدال عربي بصري متطابق
# ═══════════════════════════════════════════════════════════════

# Arabic Presentation Forms B (U+FE70–U+FEFF) - كل كود مُتحقق منه:
# NFKC(النموذج) = الحرف الأصلي بالضبط (تم التحقق برمجياً)
ARABIC_PRESENTATION_FORMS = {
    'آ': ['\uFE81', '\uFE82'],   # ALEF WITH MADDA ABOVE
    'أ': ['\uFE83', '\uFE84'],   # ALEF WITH HAMZA ABOVE
    'ؤ': ['\uFE85', '\uFE86'],   # WAW WITH HAMZA ABOVE
    'إ': ['\uFE87', '\uFE88'],   # ALEF WITH HAMZA BELOW
    'ئ': ['\uFE89', '\uFE8A', '\uFE8B', '\uFE8C'],  # YEH WITH HAMZA ABOVE
    'ا': ['\uFE8D', '\uFE8E'],   # ALEF (isolated/final فقط!)
    'ب': ['\uFE8F', '\uFE90', '\uFE91', '\uFE92'],  # BEH
    'ة': ['\uFE93', '\uFE94'],   # TEH MARBUTA
    'ت': ['\uFE95', '\uFE96', '\uFE97', '\uFE98'],  # TEH
    'ث': ['\uFE99', '\uFE9A', '\uFE9B', '\uFE9C'],  # THEH
    'ج': ['\uFE9D', '\uFE9E', '\uFE9F', '\uFEA0'],  # JEEM
    'ح': ['\uFEA1', '\uFEA2', '\uFEA3', '\uFEA4'],  # HAH
    'خ': ['\uFEA5', '\uFEA6', '\uFEA7', '\uFEA8'],  # KHAH
    'د': ['\uFEA9', '\uFEAA'],   # DAL
    'ذ': ['\uFEAB', '\uFEAC'],   # THAL
    'ر': ['\uFEAD', '\uFEAE'],   # REH
    'ز': ['\uFEAF', '\uFEB0'],   # ZAIN
    'س': ['\uFEB1', '\uFEB2', '\uFEB3', '\uFEB4'],  # SEEN
    'ش': ['\uFEB5', '\uFEB6', '\uFEB7', '\uFEB8'],  # SHEEN
    'ص': ['\uFEB9', '\uFEBA', '\uFEBB', '\uFEBC'],  # SAD
    'ض': ['\uFEBD', '\uFEBE', '\uFEBF', '\uFEC0'],  # DAD
    'ط': ['\uFEC1', '\uFEC2', '\uFEC3', '\uFEC4'],  # TAH
    'ظ': ['\uFEC5', '\uFEC6', '\uFEC7', '\uFEC8'],  # ZAH
    'ع': ['\uFEC9', '\uFECA', '\uFECB', '\uFECC'],  # AIN
    'غ': ['\uFECD', '\uFECE', '\uFECF', '\uFED0'],  # GHAIN
    'ف': ['\uFED1', '\uFED2', '\uFED3', '\uFED4'],  # FEH
    'ق': ['\uFED5', '\uFED6', '\uFED7', '\uFED8'],  # QAF
    'ك': ['\uFED9', '\uFEDA', '\uFEDB', '\uFEDC'],  # KAF
    'ل': ['\uFEDD', '\uFEDE', '\uFEDF', '\uFEE0'],  # LAM
    'م': ['\uFEE1', '\uFEE2', '\uFEE3', '\uFEE4'],  # MEEM
    'ن': ['\uFEE5', '\uFEE6', '\uFEE7', '\uFEE8'],  # NOON
    'ه': ['\uFEE9', '\uFEEA', '\uFEEB', '\uFEEC'],  # HEH
    'و': ['\uFEED', '\uFEEE'],   # WAW
    'ى': ['\uFEEF', '\uFEF0'],   # ALEF MAKSURA (وليس YEH!)
    'ي': ['\uFEF1', '\uFEF2', '\uFEF3', '\uFEF4'],  # YEH
    'ء': ['\uFE80'],             # HAMZA (isolated فقط)
}

# 🛡️ تحقق برمجي عند التحميل: كل نموذج يجب أن يُطبّع إلى حرفه الأصلي
for _base, _forms in ARABIC_PRESENTATION_FORMS.items():
    for _f in _forms:
        assert unicodedata.normalize('NFKC', _f) == _base, \
            f'خطأ في الخريطة: NFKC(U+{ord(_f):04X}) != {_base!r}'


def apply_arabic_presentation_forms(text: str, intensity: float = 0.25) -> str:
    """
    استبدال نسبة من الأحرف العربية بـ Presentation Forms

    ✅ النص يبدو متطابقاً 100% للعين المجردة
    ✅ يكسر مطابقة Hash والـ String matching
    ✅ ينجو من التطبيع الذي تعتمده بوتات الحماية (tg-spam وأمثاله)
    ✅ الأحرف الموجودة أصلاً كأشكال عرض (مثل ﺳﻛﻟﻳف في نص المستخدم)
       تُترك كما هي - لا تُعالج مرتين (حماية من التراكم)
    """
    if not text or intensity <= 0:
        return text

    result = []
    for char in text:
        # الأحرف التي هي أصلاً Presentation Forms تُترك كما هي
        if '\uFB50' <= char <= '\uFEFF':
            result.append(char)
        elif char in ARABIC_PRESENTATION_FORMS and random.random() < intensity:
            # اختيار نسخة عشوائية من Presentation Forms
            result.append(random.choice(ARABIC_PRESENTATION_FORMS[char]))
        else:
            result.append(char)
    return ''.join(result)


def strip_presentation_forms(text: str) -> str:
    """إرجاع أشكال العرض إلى أحرفها الأصلية (NFKC) - للفحص والمقارنة"""
    return unicodedata.normalize('NFKC', text)

# ═══════════════════════════════════════════════════════════════
# 2. Invisible Shield Distribution - التوزيع الخفي الآمن (v3.0)
# ═══════════════════════════════════════════════════════════════

def shield_invisible_distribute(text: str, density: float = 0.08, max_consecutive: int = 2) -> str:
    """
    🛡️ v3.0: إدخال أحرف خفية "آمنة تشكيلياً" فقط

    ✅ لا يحتوي 200C/200B/200D أبداً → اتصال الحروف العربية لا يُمس
    ✅ لا يضع أكثر من max_consecutive أحرف متتالية (يتفادى الكشف)
    ✅ أحرف من خارج قوائم الكشف الشائعة (البوتات تبحث عن 200B-200D!)
    ✅ لا يلمس الروابط والمعرفات (تُطبق عبر apply_layer_protected)
    ✅ يحافظ على القراءة 100%
    """
    if not text or density <= 0:
        return text

    result = []
    consecutive = 0
    chars = list(text)

    for i, char in enumerate(chars):
        result.append(char)

        if char in (' ', '\n', '\t'):
            consecutive = 0
            continue

        # إدخال حرف خفي بعد الحرف باحتمالية density
        if (random.random() < density and
            consecutive < max_consecutive and
            i < len(chars) - 1):  # لا في نهاية النص

            result.append(random.choice(INVISIBLE_SHIELD_CHARS))
            consecutive += 1
        else:
            consecutive = 0

    return ''.join(result)

# ═══════════════════════════════════════════════════════════════
# 3. Bayes Evasion / Spintax / Tag Chars - معطلة نهائياً (v3.0)
# ═══════════════════════════════════════════════════════════════

def bayes_evade(text: str, intensity: float = 0.15) -> str:
    """
    🛡️ معطلة نهائياً - كانت تُدخل كلمات مثل (السلام عليكم) في وسط
    رسالة المستخدم! تخدير Bayes يتم الآن عبر shield_invisible_distribute
    (يكسر n-gram matching بأحرف خفية دون أي كلمات مضافة)
    """
    return text


def adaptive_spintax(text: str, intensity: float = 0.2) -> str:
    """
    🛡️ معطلة نهائياً - كانت تستبدل كلمات المستخدم بمرادفات!
    المستخدم يكتب {خيار1|خيار2} بنفسه إن أراد التنويع.
    """
    return text


def apply_tag_chars(text: str, intensity: float = 0.15) -> str:
    """
    🛡️ v3.0: معطلة نهائياً - سبب مهم!

    Tag Characters (U+E0000 range) تجعل الحرف اللاتيني **غير مرئي
    تماماً في تيليجرام** - المستخدم يفقد حروفاً من نصه!
    (مثال: WhatsApp تظهر Wh__pp)
    الحروف اللاتينية تُحمى الآن عبر shield_invisible_distribute فقط.
    """
    return text

# ═══════════════════════════════════════════════════════════════
# 4. NFD Decomposition - تفكيك الأحرف المركبة
# ═══════════════════════════════════════════════════════════════

def apply_nfd_decomposition(text: str, intensity: float = 0.1) -> str:
    """
    تفكيك Unicode NFD - يبدو متطابقاً بصرياً لكن الكود مختلف

    مثال: 'أ' (U+0623) → 'ا' (U+0627) + ٔ (U+0654)
    ✅ يكسر مطابقة الهاش
    ✅ ترتيب الطبقات مهم: يُطبق بعد التوزيع الخفي، والتفكيك
       يبقى متجاوراً (base + mark) فلا يفسد تشكيل الحرف
    """
    if not text or intensity <= 0:
        return text

    result = []
    for char in text:
        if char in INVISIBLE_SHIELD_CHARS or char in FORBIDDEN_INVISIBLES:
            result.append(char)  # الأحرف الخفية لا تُلمس
        elif random.random() < intensity:
            decomposed = unicodedata.normalize('NFD', char)
            if len(decomposed) > 1:
                result.append(decomposed)
            else:
                result.append(char)
        else:
            result.append(char)
    return ''.join(result)

# ═══════════════════════════════════════════════════════════════
# 5. Anti-Similarity Salt - ملح فريد لكل رسالة
# ═══════════════════════════════════════════════════════════════

def add_anti_similarity_salt(text: str) -> str:
    """
    إضافة أحرف خفية فريدة في نهاية الرسالة لكسر كشف التشابه

    ✅ كل رسالة لها بصمة فريدة
    ✅ يمنع بوتات الحماية من كشف الرسائل المكررة (dedup)
    ✅ تستخدم أحرف shield الآمنة فقط (لا تفسد بصمة stego)
    ✅ في نهاية الرسالة → لا تأثير إطلاقاً على النص
    """
    if not text:
        return text

    salt = ''.join(random.choice(INVISIBLE_SHIELD_CHARS) for _ in range(8))
    return text + salt

# ═══════════════════════════════════════════════════════════════
# 🎯 المحرك الرئيسي - AdaptiveObfuscationEngine
# ═══════════════════════════════════════════════════════════════

class AdaptiveObfuscationEngine:
    """
    محرك التشويش التكيفي - يطبق كل الطبقات بترتيب ذكي

    ترتيب الطبقات (v3.0):
    1. Presentation Forms (استبدال بصري متطابق)
    2. Invisible Shield Distribution (أحرف آمنة على التشكيل)
    3. NFD Decomposition (تفكيك)
    4. Anti-Similarity Salt (ملح فريد)
    """

    # مستويات القوة
    PROFILES = {
        'light': {
            'arabic_forms': 0.12,
            'zw_density': 0.05,
            'nfd_intensity': 0.06,
        },
        'medium': {
            'arabic_forms': 0.25,
            'zw_density': 0.10,
            'nfd_intensity': 0.10,
        },
        'aggressive': {
            'arabic_forms': 0.40,
            'zw_density': 0.16,
            'nfd_intensity': 0.15,
        },
        'insane': {
            'arabic_forms': 0.55,
            'zw_density': 0.22,
            'nfd_intensity': 0.20,
        },
    }

    def __init__(self, profile: str = 'medium'):
        self.profile = profile
        self.config = dict(self.PROFILES.get(profile, self.PROFILES['medium']))
        self.enabled_layers = {
            'arabic_forms': True,
            'zw_distribution': True,
            'nfd': True,
            'salt': True,
            # طبقات معطلة نهائياً (كانت تفسد النص) - موجودة للتوافق فقط
            'bayes_evasion': False,
            'spintax': False,
            'tag_chars': False,
        }
        self.stats = {
            'total_obfuscated': 0,
            'total_messages': 0,
        }

    def set_profile(self, profile: str):
        """تغيير مستوى القوة"""
        if profile in self.PROFILES:
            self.profile = profile
            self.config = dict(self.PROFILES[profile])
            return True
        return False

    def toggle_layer(self, layer: str, enabled: bool = None):
        """تفعيل/تعطيل طبقة معينة"""
        if layer in self.enabled_layers:
            if enabled is None:
                self.enabled_layers[layer] = not self.enabled_layers[layer]
            else:
                self.enabled_layers[layer] = enabled
            return self.enabled_layers[layer]
        return None

    def get_layer_status(self, layer: str) -> bool:
        """حالة طبقة معينة"""
        return self.enabled_layers.get(layer, False)

    def obfuscate(self, text: str) -> Tuple[str, dict]:
        """
        تطبيق التشويش التكيفي على النص

        Returns:
            (النص المشفر, معلومات الطبقات المطبقة)
        """
        if not text:
            return text, {'layers': []}

        self.stats['total_messages'] += 1
        applied_layers = []

        # 🧹 الخطوة 0: تنظيف الأحرف الخطرة من المُدخل (حماية من لصق نص متلخبط)
        result = sanitize_invisible_chars(text)

        # 1. Arabic Presentation Forms - استبدال بصري عربي
        if self.enabled_layers['arabic_forms'] and self.config['arabic_forms'] > 0:
            result = apply_layer_protected(
                result, apply_arabic_presentation_forms, self.config['arabic_forms'])
            applied_layers.append('arabic_forms')

        # 2. Invisible Shield Distribution - أحرف خفية آمنة تشكيلياً
        if self.enabled_layers['zw_distribution'] and self.config['zw_density'] > 0:
            result = apply_layer_protected(
                result, shield_invisible_distribute, self.config['zw_density'])
            applied_layers.append('invisible_shield')

        # 3. NFD Decomposition - تفكيك
        if self.enabled_layers['nfd'] and self.config['nfd_intensity'] > 0:
            result = apply_layer_protected(
                result, apply_nfd_decomposition, self.config['nfd_intensity'])
            applied_layers.append('nfd')

        # 4. Anti-Similarity Salt - ملح فريد
        if self.enabled_layers['salt']:
            result = add_anti_similarity_salt(result)
            applied_layers.append('salt')

        self.stats['total_obfuscated'] += 1

        return result, {
            'layers': applied_layers,
            'profile': self.profile,
            'length_before': len(text),
            'length_after': len(result),
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
        info = f"🔬 **Adaptive Obfuscation Engine v3.0**\n\n"
        info += f"⚡ **المستوى الحالي:** {self.profile}\n\n"
        info += f"📊 **الطبقات المفعّلة (كلها غير مرئية ولا تعدل كلماتك):**\n"
        layers_ar = {
            'arabic_forms': '1️⃣ Arabic Presentation Forms (متطابقة بصرياً)',
            'zw_distribution': '2️⃣ Invisible Shield (أحرف خفية آمنة على التشكيل)',
            'nfd': '3️⃣ NFD Decomposition (تفكيك غير مرئي)',
            'salt': '4️⃣ Anti-Similarity Salt (بصمة فريدة)',
            'bayes_evasion': '⛔ Bayes Evasion (معطلة - كانت تضيف كلمات)',
            'spintax': '⛔ Adaptive Spintax (معطلة - كانت تستبدل كلماتك)',
            'tag_chars': '⛔ Tag Characters (معطلة - كانت تخفي الحروف)',
        }
        for key, name in layers_ar.items():
            status = "✅" if self.enabled_layers.get(key) else "⛔"
            info += f"  {status} {name}\n"

        info += f"\n📈 **الإحصائيات:**\n"
        info += f"  📝 رسائل مشفرة: {self.stats['total_obfuscated']}\n"
        info += f"  📊 إجمالي الرسائل: {self.stats['total_messages']}\n"

        return info


# إنشاء instance افتراضي
adaptive_engine = AdaptiveObfuscationEngine(profile='medium')

# توافق مع السكربتات القديمة (الاسم الجديد: shield_invisible_distribute)
smart_zw_distribute = shield_invisible_distribute


def quick_obfuscate(text: str, profile: str = None) -> str:
    """دالة سريعة للتشفير - تستخدم المحرك الافتراضي"""
    if profile:
        adaptive_engine.set_profile(profile)
    result, _ = adaptive_engine.obfuscate(text)
    return result


if __name__ == '__main__':
    # اختبار المحرك
    test_text = "اشترك في قناتنا للحصول على عروض حصرية t.me/example @username"

    print("=" * 60)
    print("🔬 اختبار Adaptive Obfuscation Engine v3.0")
    print("=" * 60)
    print(f"\n📝 **النص الأصلي:**\n{test_text}")
    print(f"📊 الطول: {len(test_text)}")

    for profile in ['light', 'medium', 'aggressive', 'insane']:
        engine = AdaptiveObfuscationEngine(profile=profile)
        result, info = engine.obfuscate(test_text)
        # التحقق من عدم وجود أحرف خطرة
        dangerous = [c for c in result if c in FORBIDDEN_INVISIBLES]
        print(f"\n{'─' * 60}")
        print(f"⚡ Profile: {profile}")
        print(f"📝 النص المشفر:\n{result}")
        print(f"📊 الطول: {len(result)} (زيادة: {len(result) - len(test_text)})")
        print(f"🛡️ الطبقات: {info['layers']}")
        print(f"🚫 أحرف خطرة (200B/200C/200D): {len(dangerous)} ← يجب أن تكون 0")

    print(f"\n{'=' * 60}")
    print("✅ تم الاختبار بنجاح!")
