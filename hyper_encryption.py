# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════
  HyperEncryptionEngine v2.0
  محرك التشفير والتمويه الخارق - متعدد الطبقات
═══════════════════════════════════════════════════════════════

محرك تشفير متطور مكون من 15+ طبقة مستقلة، مصمم خصيصاً
لتجاوز بوتات الحماية (anti-spam bots) على تيليجرام.

المبادئ:
1. كل طبقة غير مرئية (أو شبه غير مرئية) للمستخدم العادي
2. كل طبقة قابلة للتحكم بشكل مستقل عبر settings
3. يدعم العربية والإنجليزية والأرقام والروابط
4. كل رسالة تحصل على بصمة فريدة (يكسر مطابقة الـ hash)
5. كل مجموعة تحصل على بصمة فريدة (يكسر مطابقة النمط)
6. النص يبقى قابلاً للقراءة 100% للمستخدم العادي

الطبقات:
  L01: Homoglyph substitution (عربي + لاتيني + أرقام)
  L02: Zero-width chars بين الكلمات والأحرف
  L03: Arabic Tatweel (ـ) بين الحروف العربية
  L04: Arabic Harakat (تشكيل خفيف جداً)
  L05: Combining diacritical marks على اللاتيني
  L06: Space variants (NBSP/thin/narrow/figure/punctuation)
  L07: Directional marks (LRM/RLM/embeds)
  L08: Variation selectors (VS1-VS16)
  L09: Link obfuscation (fullwidth ./, fraction slash)
  L10: Mention obfuscation (ZWJ بعد @)
  L11: Per-group deterministic variation (seed by hash)
  L12: Trailing invisible chars (defeats hash matching)
  L13: Line break variants (\n + invisible)
  L14: Paragraph separator insertion (rare)
  L15: Keyword heavy obfuscation (كلمات مفتاحية)
  L16: Numeric substitution (Arabic-Indic/Persian digits)
  L17: Punctuation substitution (fullwidth Arabic)
  L18: Mid-word ZWSP (يكسر تطابق الكلمات المفتاحية)

مستويات القوة:
  light:       L01,02,06,09,10,11,12  (خفيف - للحسابات الحساسة)
  medium:      +L03,05,13,16,17,18    (متوسط - افتراضي)
  aggressive:  +L04,07,15             (عدواني - بوتات قوية)
  insane:      +L08,14                (هائج - أقصى تمويه)
"""

import re
import random
import hashlib
import unicodedata


# ════════════════════════════════════════════════════════════════
#  جداول الأحرف البديلة (Homoglyph Maps)
# ════════════════════════════════════════════════════════════════

# لاتيني → سيريلي/يوناني (تبدو متطابقة)
LATIN_HOMOGLYPHS = {
    'a': '\u0430', 'A': '\u0410',
    'e': '\u0435', 'E': '\u0415',
    'o': '\u043E', 'O': '\u041E',
    'c': '\u0441', 'C': '\u0421',
    'p': '\u0440', 'P': '\u0420',
    'x': '\u0445', 'X': '\u0425',
    'i': '\u0456',
    'j': '\u0458',
    's': '\u0455', 'S': '\u0405',
    'y': '\u0443', 'Y': '\u0423',
    'H': '\u041D',
    'B': '\u0412',
    'T': '\u0422',
    'K': '\u041A',
    'M': '\u041C',
    'n': '\u03B7',  # eta
    'v': '\u03BD',  # nu
}

# عربي → أحرف عربية متشابهة بصرياً
ARABIC_HOMOGLYPHS = {
    'ي': '\u064A',  # Arabic Yeh → نفس الشكل في معظم الخطوط (مؤمن)
    'ك': '\u0643',  # Arabic Kaf
    'ه': '\u0647',  # Arabic Heh
    # نستخدم بدائل من العائلة العربية الموسعة:
    'ء': '\u0621',
    'ا': '\u0627',  # alef → alef normal (مع إمكانية إضافة hamza above)
}

# بدائل عربية أقوى (استخدام أشكال presentation forms بصرية مماثلة)
ARABIC_PRESENTATION_FORMS = {
    'ل': '\uFEFB',  # Lam-Alef Isolated
    'لا': '\uFEFB',
}

# أحرف عربية مرئية التطابق من كتل مختلفة (Arabic Extended-A)
ARABIC_EXTENDED_LOOKALIKES = {
    'ي': '\u06CC',  # Arabic Yeh → Farsi Yeh (مرئي مماثل في معظم الخطوط)
    'ك': '\u06A9',  # Arabic Kaf → Keheh (مرئي مماثل)
    'ه': '\u06C0',  # Arabic Heh → Heh with Hamza above (شبه مماثل)
    'ت': '\u062A',  # باقي
}

# أرقام لاتينية → بدائل (Arabic-Indic + Persian + Fullwidth)
DIGIT_HOMOGLYPHS = {
    '0': ['\u0660', '\u06F0', '\uFF10'],  # ٠ ۰ ０
    '1': ['\u0661', '\u06F1', '\uFF11'],  # ١ ۱ １
    '2': ['\u0662', '\u06F2', '\uFF12'],
    '3': ['\u0663', '\u06F3', '\uFF13'],
    '4': ['\u0664', '\u06F4', '\uFF14'],
    '5': ['\u0665', '\u06F5', '\uFF15'],
    '6': ['\u0666', '\u06F6', '\uFF16'],
    '7': ['\u0667', '\u06F7', '\uFF17'],
    '8': ['\u0668', '\u06F8', '\uFF18'],
    '9': ['\u0669', '\u06F9', '\uFF19'],
}

# Fullwidth الأحرف اللاتينية (للروابط والكلمات المفتاحية)
FULLWIDTH_LATIN = {
    'a': '\uFF41', 'b': '\uFF42', 'c': '\uFF43', 'd': '\uFF44',
    'e': '\uFF45', 'f': '\uFF46', 'g': '\uFF47', 'h': '\uFF48',
    'i': '\uFF49', 'j': '\uFF4A', 'k': '\uFF4B', 'l': '\uFF4C',
    'm': '\uFF4D', 'n': '\uFF4E', 'o': '\uFF4F', 'p': '\uFF50',
    'q': '\uFF51', 'r': '\uFF52', 's': '\uFF53', 't': '\uFF54',
    'u': '\uFF55', 'v': '\uFF56', 'w': '\uFF57', 'x': '\uFF58',
    'y': '\uFF59', 'z': '\uFF5A',
}


# ════════════════════════════════════════════════════════════════
#  الأحرف غير المرئية
# ════════════════════════════════════════════════════════════════

# Zero-width chars
ZWSP = '\u200B'  # Zero Width Space
ZWNJ = '\u200C'  # Zero Width Non-Joiner
ZWJ  = '\u200D'  # Zero Width Joiner
WJ   = '\u2060'  # Word Joiner
BOM  = '\uFEFF'  # Zero Width No-Break Space (BOM)

ZERO_WIDTH_CHARS = [ZWSP, ZWNJ, ZWJ, WJ, BOM]

# Directional marks
LRM  = '\u200E'  # Left-to-Right Mark
RLM  = '\u200F'  # Right-to-Left Mark
LRE  = '\u202A'  # Left-to-Right Embedding
RLE  = '\u202B'  # Right-to-Left Embedding
PDF  = '\u202C'  # Pop Directional Formatting
LRO  = '\u202D'  # Left-to-Right Override
RLO  = '\u202E'  # Right-to-Left Override

DIRECTIONAL_MARKS = [LRM, RLM]  # الإدراج آمن (لا يكسر النص)
DIRECTIONAL_EMBEDS = [LRE, RLE, PDF]  # أخطر، نستخدمها بحذر

# Variation selectors
VS1_VS16 = [chr(0xFE00 + i) for i in range(16)]
VS15 = '\uFE0E'  # Text variation selector (آمن)
VS16 = '\uFE0F'  # Emoji variation selector (آمن نسبياً)

# Combining diacritical marks (للأحرف اللاتينية)
COMBINING_MARKS = [
    '\u0300',  # Combining Grave Accent
    '\u0301',  # Combining Acute Accent
    '\u0302',  # Combining Circumflex Accent
    '\u0303',  # Combining Tilde
    '\u0304',  # Combining Macron
    '\u0306',  # Combining Breve
    '\u0307',  # Combining Dot Above
    '\u0308',  # Combining Diaeresis
    '\u030A',  # Combining Ring Above
    '\u030B',  # Combining Double Acute Accent
    '\u030C',  # Combining Caron
    '\u0310',  # Combining Candrabindu
    '\u0311',  # Combining Inverted Breve
    '\u0312',  # Combining Turned Comma Above
    '\u0313',  # Combining Comma Above
    '\u031B',  # Combining Horn
    '\u0323',  # Combining Dot Below
    '\u0326',  # Combining Comma Below
    '\u0327',  # Combining Cedilla
    '\u0328',  # Combining Ogonek
    '\u0331',  # Combining Macron Below
    '\u0335',  # Combining Short Stroke Overlay
    '\u0336',  # Combining Long Stroke Overlay
    '\u0337',  # Combining Short Solidus Overlay
    '\u0338',  # Combining Long Solidus Overlay
    '\u0342',  # Combining Greek Perispomeni
    '\u0345',  # Combining Greek Ypogegrammeni
    '\u034A',  # Combining Not Tilde Above
    '\u034B',  # Combining HomOTHETIC Above
    '\u034C',  # Combining Almost Equal to Below
    '\u0350',  # Combining Left Arrowhead Above
    '\u0351',  # Combining Right Arrowhead Above
    '\u0352',  # Combining Left Right Arrowhead Above
    '\u0353',  # Combining Left Arrowhead Below
    '\u0354',  # Combining Right Arrowhead Below
    '\u0355',  # Combining Left Right Arrowhead Below
    '\u0358',  # Combining Dot Above Right
    '\u035C',  # Combining Double Breve Below
    '\u035D',  # Combining Double Breve
    '\u035E',  # Combining Double Macron
    '\u035F',  # Combining Double Macron Below
    '\u0360',  # Combining Double Tilde
    '\u0361',  # Combining Double Inverted Breve
    '\u0362',  # Combining Double Rightwards Arrow Below
    '\u0363', '\u0364', '\u0365', '\u0366',  # Combining Latin letters
    '\u0367', '\u0368', '\u0369', '\u036A',
    '\u036B', '\u036C', '\u036D', '\u036E',
    '\u036F',
]

# مسافات بديلة
SPACE_VARIANTS = [
    '\u00A0',  # NBSP
    '\u2009',  # Thin Space
    '\u202F',  # Narrow No-Break Space
    '\u2007',  # Figure Space
    '\u2008',  # Punctuation Space
    '\u200A',  # Hair Space
    '\u205F',  # Medium Mathematical Space
]

# التشكيل العربي (Harakat)
ARABIC_HARAKAT = {
    'fatha':   '\u064E',  # َ
    'damma':   '\u064F',  # ُ
    'kasra':   '\u0650',  # ِ
    'sukun':   '\u0652',  # ْ
    'shadda':  '\u0651',  # ّ
    'fathatan':'\u064B',  # ً
    'dammatan':'\u064C',  # ٌ
    'kasratan':'\u064D',  # ٍ
    'superscript_alef': '\u0670',  # ٰ
}
ARABIC_HARAKAT_LIST = list(ARABIC_HARAKAT.values())

# Tatweel (كاشيدة عربية)
TATWEEL = '\u0640'  # ـ

# Arabic Letters (لمعرفة متى نطبق Tatweel/Harakat)
ARABIC_LETTER_RE = re.compile(r'[\u0621-\u064A\u0660-\u0669\u06F0-\u06F9]')

# Punctuation عربي/لاتيني للتمويه
PUNCTUATION_SUBSTITUTIONS = {
    '!': '\uFF01',  # ！ fullwidth
    '?': '\uFF1F',  # ？ fullwidth
    '.': '\uFF0E',  # ． fullwidth (للروابط فقط - يطبق بحذر)
    ',': '\uFF0C',  # ， fullwidth
    ':': '\uFF1A',  # ： fullwidth
    ';': '\uFF1B',  # ； fullwidth
    '(': '\uFF08',
    ')': '\uFF09',
}

# كلمات مفتاحية شائعة في الإعلانات (نطبق عليها تمويه أقوى)
KEYWORD_HEAVY_LIST = [
    'اشترك', 'اشتراك', 'تليفون', 'قناة', 'قناتي', 'قناتنا',
    'عروض', 'عرض', 'تخفيض', 'مجاني', 'مجاناً', 'تخفيضات',
    'واتساب', 'واتس', 'تيليجرام', 'انستقرام', 'سناب',
    'سعر', 'السعر', 'للبيع', 'للإيجار', 'شراء',
    'توصيل', 'توصيل مجاني', 'كاش', 'دفع',
    'عميل', 'عملاء', 'مشترك', 'مشتركين',
    'رابط', 'الرابط', 'اضغط', 'اضغط هنا',
    'أهلاً', 'اهلا', 'مرحبا', 'السلام',
    'العرض', 'العروض', 'الخصم', 'الهدية',
    'الوصف', 'التواصل', 'للتواصل',
    'follow', 'subscribe', 'channel', 'free', 'offer',
    'discount', 'sale', 'buy', 'shop', 'link', 'click',
]


# ════════════════════════════════════════════════════════════════
#  المحرك الرئيسي
# ════════════════════════════════════════════════════════════════

class HyperEncryptionEngine:
    """
    محرك التشفير والتمويه الخارق - متعدد الطبقات
    """

    # تعريف الطبقات
    LAYERS = {
        'L01_homoglyph':       'استبدال الحروف بنظيراتها المرئية المتطابقة',
        'L02_zero_width':      'إدراج أحرف غير مرئية بين الكلمات',
        'L03_tatweel':         'إضافة كاشيدة عربية بين الحروف',
        'L04_harakat':         'تشكيل عربي خفيف جداً',
        'L05_combining':       'دمج علامات تشكيل لاتينية',
        'L06_space_variant':   'استبدال المسافات بمسافات بديلة',
        'L07_directional':     'إدراج علامات اتجاه (LRM/RLM)',
        'L08_variation_sel':   'محددات الشكل (Variation Selectors)',
        'L09_link_obf':        'تمويه الروابط',
        'L10_mention_obf':     'تمويه الإشارات (@)',
        'L11_pergroup_hash':   'بصمة فريدة لكل مجموعة',
        'L12_trailing':        'أحرف غير مرئية في النهاية',
        'L13_linebreak_var':   'تنويع فواصل الأسطر',
        'L14_paragraph_sep':   'فواصل فقرات نادرة',
        'L15_keyword_heavy':   'تمويه أقوى للكلمات المفتاحية',
        'L16_numeric_sub':     'استبدال الأرقام',
        'L17_punct_sub':       'استبدال علامات الترقيم',
        'L18_midword_zwsp':    'ZWSP داخل الكلمات الطويلة',
    }

    # مستويات القوة
    STRENGTH_LEVELS = {
        'light': [
            'L01_homoglyph', 'L02_zero_width', 'L06_space_variant',
            'L09_link_obf', 'L10_mention_obf', 'L11_pergroup_hash', 'L12_trailing',
        ],
        'medium': [
            'L01_homoglyph', 'L02_zero_width', 'L03_tatweel',
            'L05_combining', 'L06_space_variant', 'L09_link_obf',
            'L10_mention_obf', 'L11_pergroup_hash', 'L12_trailing',
            'L13_linebreak_var', 'L16_numeric_sub', 'L17_punct_sub', 'L18_midword_zwsp',
        ],
        'aggressive': [
            'L01_homoglyph', 'L02_zero_width', 'L03_tatweel',
            'L04_harakat', 'L05_combining', 'L06_space_variant',
            'L07_directional', 'L09_link_obf', 'L10_mention_obf',
            'L11_pergroup_hash', 'L12_trailing', 'L13_linebreak_var',
            'L15_keyword_heavy', 'L16_numeric_sub', 'L17_punct_sub', 'L18_midword_zwsp',
        ],
        'insane': [
            'L01_homoglyph', 'L02_zero_width', 'L03_tatweel',
            'L04_harakat', 'L05_combining', 'L06_space_variant',
            'L07_directional', 'L08_variation_sel', 'L09_link_obf',
            'L10_mention_obf', 'L11_pergroup_hash', 'L12_trailing',
            'L13_linebreak_var', 'L14_paragraph_sep', 'L15_keyword_heavy',
            'L16_numeric_sub', 'L17_punct_sub', 'L18_midword_zwsp',
        ],
    }

    def __init__(self, settings_getter=None, settings_setter=None):
        """
        settings_getter: callable(key, default) -> str
        settings_setter: callable(key, value) -> None
        """
        self.get_setting = settings_getter or (lambda k, d: d)
        self.set_setting = settings_setter or (lambda k, v: None)
        self.sent_cache = {}  # group_id -> set of text hashes

    # ──────────────────────────────────────────────────────────
    #  أدوات مساعدة
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _seed_for_group(text, group_id):
        """إنشاء seed ثابت لنص+مجموعة معينة (للتغيير المتناسق)"""
        key = f"{group_id or 'none'}::{text}"
        h = hashlib.md5(key.encode('utf-8')).hexdigest()
        return int(h[:8], 16)

    @staticmethod
    def _is_arabic_char(ch):
        return bool(ARABIC_LETTER_RE.match(ch))

    @staticmethod
    def _is_latin_alpha(ch):
        return ch.isascii() and ch.isalpha()

    def _active_layers(self):
        """إرجاع قائمة الطبقات المفعلة حسب مستوى القوة"""
        level = self.get_setting('encryption_strength', 'medium')
        active_set = set(self.STRENGTH_LEVELS.get(level, self.STRENGTH_LEVELS['medium']))

        # إضافة/إزالة طبقات مخصصة (toggles)
        for layer_id in self.LAYERS:
            toggle_key = f'enc_{layer_id}'
            toggle_val = self.get_setting(toggle_key, 'auto')
            if toggle_val == 'on':
                active_set.add(layer_id)
            elif toggle_val == 'off':
                active_set.discard(layer_id)
        return active_set

    # ──────────────────────────────────────────────────────────
    #  الطبقات الفردية
    # ──────────────────────────────────────────────────────────

    def _L01_homoglyph(self, text, rng):
        """استبدال الحروف اللاتينية بنظيراتها (بنسبة منخفضة)"""
        result = []
        for ch in text:
            if self._is_latin_alpha(ch) and ch in LATIN_HOMOGLYPHS:
                if rng.random() < 0.35:
                    result.append(LATIN_HOMOGLYPHS[ch])
                    continue
            # استبدال عربي (ي → يه فارسية، ك → كاف فارسية)
            if ch == 'ي' and rng.random() < 0.25:
                result.append(ARABIC_EXTENDED_LOOKALIKES['ي'])
                continue
            if ch == 'ك' and rng.random() < 0.25:
                result.append(ARABIC_EXTENDED_LOOKALIKES['ك'])
                continue
            result.append(ch)
        return ''.join(result)

    def _L02_zero_width(self, text, rng):
        """إدراج أحرف غير مرئية بين الكلمات وبعد علامات الترقيم"""
        if len(text) < 3:
            return text
        result = []
        for i, ch in enumerate(text):
            result.append(ch)
            # بعد المسافة: 35% احتمال إدراج ZW char
            if ch == ' ' and rng.random() < 0.35:
                result.append(rng.choice(ZERO_WIDTH_CHARS))
            # بعد علامة ترقيم: 25%
            elif ch in '.!?,،؛:؛' and rng.random() < 0.25:
                result.append(rng.choice(ZERO_WIDTH_CHARS))
            # بعد سطر جديد: 40%
            elif ch == '\n' and rng.random() < 0.40:
                result.append(rng.choice(ZERO_WIDTH_CHARS))
        return ''.join(result)

    def _L03_tatweel(self, text, rng):
        """إضافة كاشيدة عربية (ـ) بين الحروف العربية"""
        if not ARABIC_LETTER_RE.search(text):
            return text
        result = []
        prev_arabic = False
        for ch in text:
            is_ar = self._is_arabic_char(ch)
            if prev_arabic and is_ar and rng.random() < 0.15:
                # إدراج 1-2 tatweel
                n = rng.randint(1, 2)
                result.append(TATWEEL * n)
            result.append(ch)
            prev_arabic = is_ar
        return ''.join(result)

    def _L04_harakat(self, text, rng):
        """تشكيل عربي خفيف جداً (لا يغير المعنى)"""
        if not ARABIC_LETTER_RE.search(text):
            return text
        result = []
        for ch in text:
            result.append(ch)
            # 8% احتمال إضافة haraka على حرف عربي
            if self._is_arabic_char(ch) and rng.random() < 0.08:
                # نستخدم fatha/kasra/damma فقط (الأخف بصرياً)
                light_harakat = [ARABIC_HARAKAT['fatha'], ARABIC_HARAKAT['kasra'],
                                  ARABIC_HARAKAT['damma'], ARABIC_HARAKAT['sukun']]
                result.append(rng.choice(light_harakat))
        return ''.join(result)

    def _L05_combining(self, text, rng):
        """دمج علامات تشكيل لاتينية على الأحرف اللاتينية"""
        result = []
        for ch in text:
            result.append(ch)
            if self._is_latin_alpha(ch) and rng.random() < 0.10:
                result.append(rng.choice(COMBINING_MARKS[:20]))  # الأخف فقط
        return ''.join(result)

    def _L06_space_variant(self, text, rng):
        """استبدال بعض المسافات بمسافات بديلة (غير مرئي)"""
        result = []
        for ch in text:
            if ch == ' ':
                if rng.random() < 0.45:
                    result.append(rng.choice(SPACE_VARIANTS))
                else:
                    result.append(ch)
            else:
                result.append(ch)
        return ''.join(result)

    def _L07_directional(self, text, rng):
        """إدراج علامات اتجاه LRM/RLM (غير مرئية)"""
        if len(text) < 5:
            return text
        result = []
        # في البداية
        if rng.random() < 0.50:
            result.append(rng.choice([LRM, RLM]))
        for i, ch in enumerate(text):
            result.append(ch)
            # بعد مسافة: 10%
            if ch == ' ' and rng.random() < 0.10:
                result.append(rng.choice([LRM, RLM]))
        # في النهاية
        if rng.random() < 0.50:
            result.append(rng.choice([LRM, RLM]))
        return ''.join(result)

    def _L08_variation_sel(self, text, rng):
        """إدراج محددات الشكل (Variation Selectors)"""
        result = []
        for i, ch in enumerate(text):
            result.append(ch)
            if rng.random() < 0.05:
                result.append(rng.choice([VS15, VS16]))
        return ''.join(result)

    def _L09_link_obf(self, text, rng):
        """تمويه الروابط - إخفاء الأنماط المعروفة"""
        # تمويه t.me
        def obf_t_me(match):
            full = match.group(0)
            return 't' + rng.choice(ZERO_WIDTH_CHARS) + '.m' + rng.choice(ZERO_WIDTH_CHARS) + 'e'

        text = re.sub(r't\.me', obf_t_me, text, flags=re.IGNORECASE)

        # تمويه https://
        text = re.sub(r'https://', lambda m: 'https:' + rng.choice(ZERO_WIDTH_CHARS) + '//', text)
        text = re.sub(r'http://', lambda m: 'http:' + rng.choice(ZERO_WIDTH_CHARS) + '//', text)

        # تمويه www.
        text = re.sub(r'www\.', lambda m: 'www' + rng.choice(ZERO_WIDTH_CHARS) + '.', text)

        # تمويه النقاط داخل الدومين (لا تلمس المسار)
        def obf_domain_dots(match):
            scheme = match.group(1) or ''
            domain = match.group(2)
            # لا نغير النقاط داخل الدومين لأنها تكسر الروابط
            # بدلاً من ذلك نضيف ZWJ بعد النقطة
            new_domain = re.sub(r'\.', lambda x: '.' + rng.choice(ZERO_WIDTH_CHARS), domain)
            return scheme + new_domain

        text = re.sub(r'(https?://[^\s/]*?)([a-zA-Z0-9][a-zA-Z0-9\.\-]*\.[a-zA-Z]{2,})',
                       obf_domain_dots, text)

        return text

    def _L10_mention_obf(self, text, rng):
        """تمويه الإشارات @username"""
        def replace_mention(match):
            username = match.group(1)
            # ZWJ بعد @ يكسر pattern matching للبوتات
            return '@' + rng.choice(ZERO_WIDTH_CHARS) + username
        return re.sub(r'@([a-zA-Z0-9_]{3,})', replace_mention, text)

    def _L11_pergroup_hash(self, text, group_id, rng):
        """بصمة فريدة لكل مجموعة (seeded random)"""
        if not group_id:
            return text
        # إضافة ZWSP في مواضع ثابتة لنفس النص+المجموعة
        seed = self._seed_for_group(text, group_id)
        per_rng = random.Random(seed)
        result = list(text)
        # إدراج 2-4 أحرف غير مرئية في مواضع ثابتة
        positions = sorted(per_rng.sample(range(1, len(text)), min(4, len(text) - 1)))
        for pos in reversed(positions):
            result.insert(pos, per_rng.choice(ZERO_WIDTH_CHARS))
        return ''.join(result)

    def _L12_trailing(self, text, rng):
        """أحرف غير مرئية في نهاية الرسالة"""
        n = rng.randint(1, 3)
        trail = ''.join(rng.choice(ZERO_WIDTH_CHARS) for _ in range(n))
        return text + trail

    def _L13_linebreak_var(self, text, rng):
        """تنويع فواصل الأسطر بإضافة ZW chars"""
        if '\n' not in text:
            return text
        result = []
        for ch in text:
            if ch == '\n' and rng.random() < 0.30:
                result.append(ch)
                result.append(rng.choice(ZERO_WIDTH_CHARS))
            else:
                result.append(ch)
        return ''.join(result)

    def _L14_paragraph_sep(self, text, rng):
        """إدراج فواصل فقرات نادرة (U+2029)"""
        if '\n\n' not in text:
            return text
        # استبدال بعض \n\n بـ \u2029 (نادر الاستخدام - يكسر hash matching)
        return re.sub(r'\n\n', lambda m: '\n' + rng.choice(ZERO_WIDTH_CHARS) + '\n' if rng.random() < 0.5 else '\n\n',
                       text)

    def _L15_keyword_heavy(self, text, rng):
        """تمويه أقوى للكلمات المفتاحية الشائعة"""
        for kw in KEYWORD_HEAVY_LIST:
            if kw in text:
                # تطبيق homoglyph + ZWSP داخل الكلمة
                def heavy_replace(match):
                    word = match.group(0)
                    result = []
                    for i, ch in enumerate(word):
                        if i > 0 and i < len(word) - 1 and rng.random() < 0.5:
                            result.append(rng.choice(ZERO_WIDTH_CHARS))
                        # استبدال لاتيني
                        if self._is_latin_alpha(ch) and ch.lower() in LATIN_HOMOGLYPHS and rng.random() < 0.5:
                            result.append(LATIN_HOMOGLYPHS[ch.lower()])
                        else:
                            result.append(ch)
                    return ''.join(result)
                # معالجة case-insensitive للإنجليزية
                if kw.isascii():
                    text = re.sub(re.escape(kw), heavy_replace, text, flags=re.IGNORECASE)
                else:
                    text = text.replace(kw, heavy_replace(re.match(re.escape(kw), kw)))
        return text

    def _L16_numeric_sub(self, text, rng):
        """استبدال الأرقام ببدائل عربية/فارسية"""
        result = []
        for ch in text:
            if ch.isdigit() and ch in DIGIT_HOMOGLYPHS:
                # 35% احتمال الاستبدال
                if rng.random() < 0.35:
                    result.append(rng.choice(DIGIT_HOMOGLYPHS[ch]))
                    continue
            result.append(ch)
        return ''.join(result)

    def _L17_punct_sub(self, text, rng):
        """استبدال علامات الترقيم بنسخ fullwidth"""
        # استبدال بحذر - فقط علامات لا تكسر الروابط
        result = []
        in_url = False
        for i, ch in enumerate(text):
            # كشف URL
            if text[max(0, i-7):i].lower().endswith(('http://', 'https:/')):
                in_url = True
            if in_url and ch == ' ':
                in_url = False
            if in_url:
                result.append(ch)
                continue
            if ch in PUNCTUATION_SUBSTITUTIONS and rng.random() < 0.40:
                # لا نستبدل . داخل النصوص العادية كثيراً (قد يكسر الجمل)
                if ch == '.' and rng.random() < 0.20:
                    result.append(ch)
                else:
                    result.append(PUNCTUATION_SUBSTITUTIONS[ch])
            else:
                result.append(ch)
        return ''.join(result)

    def _L18_midword_zwsp(self, text, rng):
        """إدراج ZWSP داخل الكلمات الطويلة (يكسر keyword matching)"""
        def process_word(match):
            word = match.group(0)
            if len(word) < 4:
                return word
            # إدراج ZWSP بعد الحرف الثاني أو الثالث
            pos = rng.randint(1, len(word) - 2)
            return word[:pos] + ZWSP + word[pos:]

        # كلمات عربية وإنجليزية
        text = re.sub(r'[a-zA-Z]{4,}', process_word, text)
        text = re.sub(r'[\u0621-\u064A]{4,}', process_word, text)
        return text

    # ──────────────────────────────────────────────────────────
    #  الواجهة الرئيسية
    # ──────────────────────────────────────────────────────────

    def encrypt(self, text, group_id=None, strength=None):
        """
        تطبيق جميع الطبقات المفعلة على النص
        strength: تجاوز مستوى القوة المحفوظ (اختياري)
        """
        if not text:
            return text

        # التحقق من تفعيل التشفير
        if self.get_setting('encryption', 'on') != 'on':
            return text

        # تحديد الطبقات النشطة
        if strength:
            active = set(self.STRENGTH_LEVELS.get(strength, self.STRENGTH_LEVELS['medium']))
        else:
            active = self._active_layers()

        # إنشاء RNG بقاعدة group_id + نص للحصول على تنوع متناسق
        seed = self._seed_for_group(text, group_id) if group_id else random.randint(0, 2**32)
        rng = random.Random(seed)
        # إضافة عشوائية لكل رسالة (لمنع التطابق الكامل)
        rng.seed(seed ^ random.randint(0, 2**16))

        result = text

        # ترتيب الطبقات (مهم - بعض الطبقات يجب أن تُطبق قبل غيرها)
        order = [
            'L15_keyword_heavy',  # الكلمات المفتاحية أولاً
            'L01_homoglyph',      # استبدال الحروف
            'L16_numeric_sub',    # استبدال الأرقام
            'L18_midword_zwsp',   # ZWSP داخل الكلمات
            'L17_punct_sub',      # علامات الترقيم
            'L09_link_obf',       # تمويه الروابط
            'L10_mention_obf',    # تمويه الإشارات
            'L03_tatweel',        # الكاشيدة
            'L04_harakat',        # التشكيل
            'L05_combining',      # Combining marks
            'L06_space_variant',  # مسافات بديلة
            'L02_zero_width',     # ZW chars بين الكلمات
            'L13_linebreak_var',  # تنويع الأسطر
            'L14_paragraph_sep',  # فواصل الفقرات
            'L07_directional',    # علامات اتجاه
            'L08_variation_sel',  # Variation selectors
            'L11_pergroup_hash',  # بصمة المجموعة
            'L12_trailing',       # ذيل غير مرئي
        ]

        for layer in order:
            if layer not in active:
                continue
            try:
                if layer == 'L11_pergroup_hash':
                    result = self._L11_pergroup_hash(result, group_id, rng)
                else:
                    method = getattr(self, f'_{layer}')
                    result = method(result, rng)
            except Exception as e:
                # لا نكسر النشر بسبب خطأ في طبقة
                continue

        # التحقق من حد طول الرسالة (4096)
        if len(result) > 4096:
            # اقتطاع ذكي - نحتفظ بالأصل إذا كان التشفير ضاعف الطول بشكل مفرط
            if len(result) > len(text) * 2:
                # إعادة التشفير بمستوى أخف
                return self.encrypt(text, group_id, strength='light')

        return result

    def get_active_layers_description(self):
        """إرجاع وصف الطبقات المفعلة"""
        active = self._active_layers()
        lines = []
        for lid, desc in self.LAYERS.items():
            mark = '✅' if lid in active else '⬜'
            lines.append(f"{mark} {lid}: {desc}")
        return '\n'.join(lines)

    def get_strength_info(self):
        """معلومات مستوى القوة الحالي"""
        level = self.get_setting('encryption_strength', 'medium')
        active = self._active_layers()
        return {
            'level': level,
            'active_count': len(active),
            'total_count': len(self.LAYERS),
            'active_layers': sorted(active),
        }


# ════════════════════════════════════════════════════════════════
#  دوال مساعدة (للاختبار والعرض)
# ════════════════════════════════════════════════════════════════

def demo_encryption(text, group_id=None):
    """عرض النص مشفر بكل المستويات الأربعة - للاختبار"""
    # إنشاء محرك بسيط بلا settings
    class SimpleGetter:
        def __init__(self, level):
            self.level = level
        def __call__(self, k, d):
            if k == 'encryption':
                return 'on'
            if k == 'encryption_strength':
                return self.level
            return d

    results = {}
    for level in ['light', 'medium', 'aggressive', 'insane']:
        engine = HyperEncryptionEngine(settings_getter=SimpleGetter(level))
        results[level] = engine.encrypt(text, group_id=group_id, strength=level)
    return results


def char_analysis(text):
    """تحليل أنواع الأحرف في النص - للاختبار"""
    counts = {
        'visible': 0,
        'zero_width': 0,
        'directional': 0,
        'combining': 0,
        'space_variants': 0,
        'variation_selectors': 0,
        'arabic_harakat': 0,
        'tatweel': 0,
        'other_invisible': 0,
    }
    all_invisible = set(ZERO_WIDTH_CHARS + DIRECTIONAL_MARKS + COMBINING_MARKS +
                         SPACE_VARIANTS + [VS15, VS16] + ARABIC_HARAKAT_LIST + [TATWEEL])
    for ch in text:
        if ch in ZERO_WIDTH_CHARS:
            counts['zero_width'] += 1
        elif ch in DIRECTIONAL_MARKS:
            counts['directional'] += 1
        elif ch in COMBINING_MARKS:
            counts['combining'] += 1
        elif ch in SPACE_VARIANTS:
            counts['space_variants'] += 1
        elif ch in [VS15, VS16]:
            counts['variation_selectors'] += 1
        elif ch in ARABIC_HARAKAT_LIST:
            counts['arabic_harakat'] += 1
        elif ch == TATWEEL:
            counts['tatweel'] += 1
        elif ch in all_invisible:
            counts['other_invisible'] += 1
        elif ch == ' ':
            counts['visible'] += 1
        else:
            counts['visible'] += 1
    return counts


if __name__ == '__main__':
    # اختبار سريع
    sample = "اشترك في قناتنا https://t.me/mychannel للحصول على عروض حصرية! اتصل: 0555123456"
    print(f"النص الأصلي ({len(sample)} حرف):")
    print(sample)
    print()
    results = demo_encryption(sample, group_id=-1001234567890)
    for level, encrypted in results.items():
        counts = char_analysis(encrypted)
        invisible = sum(v for k, v in counts.items() if k != 'visible')
        print(f"─ {level.upper()} ({len(encrypted)} حرف، {invisible} غير مرئي):")
        print(encrypted)
        print(f"  تحليل: {counts}")
        print()
