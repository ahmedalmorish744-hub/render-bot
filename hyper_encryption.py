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
#  طبقات متقدمة جديدة (v2.1) - مستوحاة من مستودعات GitHub
#  Sources: unicode-confusables, confusable_homoglyphs, anti-detection-bots
# ════════════════════════════════════════════════════════════════

# L19: Tag Characters (Language Tags block U+E0000-U+E007F) - كاملة الإخفاء
# هذه الأحرف "وسوم لغة" غير مرئية تماماً في كل المحررات المعروفة
# لكنها تمرر bytes إضافية تكسر hash matching و keyword regex
# ملاحظة: U+E0001 أكبر من U+FFFF لذا نستخدم \U (8 خانات) بدل \u (4 خانات)
TAG_CHARS = [
    '\U000E0001',  # LANGUAGE TAG
    '\U000E0020',  # TAG SPACE
    '\U000E0041', '\U000E0042', '\U000E0043', '\U000E0044', '\U000E0045',  # TAG A-E
    '\U000E0061', '\U000E0062', '\U000E0063', '\U000E0064', '\U000E0065',  # TAG a-e
    '\U000E007F',  # CANCEL TAG
]

# L20: Hangul Fillers - أحرف كورية غير مرئية
HANGUL_FILLERS = [
    '\u3164',  # HANGUL FILLER
    '\u115F',  # HANGUL CHOSEONG FILLER
    '\u1160',  # HANGUL JUNGSEONG FILLER
]

# L21: Bidirectional Isolation marks (Unicode 6.3+) - جديد وغير معروف لمعظم البوتات
BIDI_ISOLATES = [
    '\u2068',  # FIRST STRONG ISOLATE (FSI)
    '\u2069',  # POP DIRECTIONAL ISOLATE (PDI)
    # LRI / RLI تُستخدم بحذر شديد - قد تكسر العرض
]
LRI = '\u2066'  # LEFT-TO-RIGHT ISOLATE
RLI = '\u2067'  # RIGHT-TO-LEFT ISOLATE

# L22: Mathematical Alphanumeric Symbols (U+1D400-U+1D7FF)
# أحرف لاتينية بنمط Fraktur/Script/Double-struck/Sans-serif - تبدو مختلفة لكنها مقروءة
MATH_FRAKTUR = {  # نمط قوطي - مفيد جداً لتمويه الكلمات المفتاحية الإنجليزية
    'a': '\U0001D51E', 'b': '\U0001D51F', 'c': '\U0001D520', 'd': '\U0001D521',
    'e': '\U0001D522', 'f': '\U0001D523', 'g': '\U0001D524', 'h': '\U0001D525',
    'i': '\U0001D526', 'j': '\U0001D527', 'k': '\U0001D528', 'l': '\U0001D529',
    'm': '\U0001D52A', 'n': '\U0001D52B', 'o': '\U0001D52C', 'p': '\U0001D52D',
    'q': '\U0001D52E', 'r': '\U0001D52F', 's': '\U0001D530', 't': '\U0001D531',
    'u': '\U0001D532', 'v': '\U0001D533', 'w': '\U0001D534', 'x': '\U0001D535',
    'y': '\U0001D536', 'z': '\U0001D537',
}
MATH_SCRIPT = {  # نمط سكربت (Script) - أنيق ومختلف بصرياً
    'a': '\U0001D4B6', 'b': '\U0001D4B7', 'c': '\U0001D4B8', 'd': '\U0001D4B9',
    'e': '\U0001D4BA', 'f': '\U0001D4BB', 'g': '\U0001D4BC', 'h': '\U0001D4BD',
    'i': '\U0001D4BE', 'j': '\U0001D4BF', 'k': '\U0001D4C0', 'l': '\U0001D4C1',
    'm': '\U0001D4C2', 'n': '\U0001D4C3', 'o': '\U0001D4C4', 'p': '\U0001D4C5',
    'q': '\U0001D4C6', 'r': '\U0001D4C7', 's': '\U0001D4C8', 't': '\U0001D4C9',
    'u': '\U0001D4CA', 'v': '\U0001D4CB', 'w': '\U0001D4CC', 'x': '\U0001D4CD',
    'y': '\U0001D4CE', 'z': '\U0001D4CF',
}
MATH_DOUBLE_STRUCK = {  # نمط مزدوج الحواف (Double-struck) - يستخدم في الرياضيات
    'a': '\U0001D552', 'b': '\U0001D553', 'c': '\U0001D554', 'd': '\U0001D555',
    'e': '\U0001D556', 'f': '\U0001D557', 'g': '\U0001D558', 'h': '\U0001D559',
    'i': '\U0001D55A', 'j': '\U0001D55B', 'k': '\U0001D55C', 'l': '\U0001D55D',
    'm': '\U0001D55E', 'n': '\U0001D55F', 'o': '\U0001D560', 'p': '\U0001D561',
    'q': '\U0001D562', 'r': '\U0001D563', 's': '\U0001D564', 't': '\U0001D565',
    'u': '\U0001D566', 'v': '\U0001D567', 'w': '\U0001D568', 'x': '\U0001D569',
    'y': '\U0001D56A', 'z': '\U0001D56B',
}
MATH_STYLE_MAPS = [MATH_FRAKTUR, MATH_SCRIPT, MATH_DOUBLE_STRUCK]

# L23: Smart Punctuation - استبدال علامات الترقيم بنسخ ذكية
SMART_PUNCT = {
    "'": '\u2019',  # ' RIGHT SINGLE QUOTATION MARK
    '"': '\u201D',  # " RIGHT DOUBLE QUOTATION MARK
    '`': '\u2018',  # ' LEFT SINGLE QUOTATION MARK
    '-': '\u2010',  # ‐ HYPHEN
    '--': '\u2013', # – EN DASH
    '---': '\u2014',# — EM DASH
    '...': '\u2026',# … HORIZONTAL ELLIPSIS
    '<<': '\u00AB', # «
    '>>': '\u00BB', # »
}

# L24: Expanded Confusables Database (مستوحى من unicode-confusables على GitHub)
# إضافة أحرف لاتينية أكثر من قائمة Unicode Confusables الرسمية
EXPANDED_LATIN_CONFUSABLES = {
    # أحرف شائعة إضافية
    'a': ['\u0430', '\u00E0', '\u00E1', '\u00E2', '\u00E3', '\u00E4', '\u00E5'],
    'A': ['\u0410', '\u00C0', '\u00C1', '\u00C2', '\u00C3', '\u00C4', '\u00C5'],
    'b': ['\u042C', '\u0253'],
    'B': ['\u0392', '\u0181'],
    'c': ['\u0441', '\u0188', '\u023C'],
    'C': ['\u0421', '\u00C7', '\u0187'],
    'd': ['\u0501', '\u0257'],
    'D': ['\u010A', '\u0189'],
    'e': ['\u0435', '\u00E8', '\u00E9', '\u00EA', '\u00EB', '\u0259'],
    'E': ['\u0415', '\u00C8', '\u00C9', '\u00CA', '\u00CB'],
    'f': ['\u0192'],
    'F': ['\u03DC'],
    'g': ['\u0261', '\u011D'],
    'G': ['\u0120', '\u0262'],
    'h': ['\u04BB', '\u0125'],
    'H': ['\u041D', '\u0124'],
    'i': ['\u0456', '\u00EC', '\u00ED', '\u00EE', '\u00EF', '\u0131'],
    'I': ['\u0406', '\u00CC', '\u00CD', '\u00CE', '\u00CF'],
    'j': ['\u0458', '\u0135'],
    'J': ['\u0408'],
    'k': ['\u043A', '\u0137'],
    'K': ['\u041A'],
    'l': ['\u04CF', '\u013A', '\u013C', '\u013E'],
    'L': ['\u013B', '\u013D'],
    'm': ['\u028D', '\u0271'],
    'M': ['\u041C', '\u039C'],
    'n': ['\u03B7', '\u00F1', '\u0144', '\u0146', '\u0148'],
    'N': ['\u039D', '\u00D1', '\u0143', '\u0145', '\u0147'],
    'o': ['\u043E', '\u00F2', '\u00F3', '\u00F4', '\u00F5', '\u00F6', '\u00F8'],
    'O': ['\u041E', '\u00D2', '\u00D3', '\u00D4', '\u00D5', '\u00D6', '\u00D8'],
    'p': ['\u0440', '\u00FE'],
    'P': ['\u0420', '\u00DE'],
    'q': ['\u051B'],
    'Q': ['\u051A'],
    'r': ['\u0433', '\u0157', '\u0159'],
    'R': ['\u0413', '\u0156', '\u0158'],
    's': ['\u0455', '\u015B', '\u015D', '\u015F', '\u0161'],
    'S': ['\u0405', '\u015A', '\u015C', '\u015E', '\u0160'],
    't': ['\u0163', '\u0165', '\u0167'],
    'T': ['\u0422', '\u0162', '\u0164', '\u0166'],
    'u': ['\u0443', '\u00F9', '\u00FA', '\u00FB', '\u00FC', '\u016B'],
    'U': ['\u0423', '\u00D9', '\u00DA', '\u00DB', '\u00DC', '\u016A'],
    'v': ['\u03BD', '\u028B'],
    'V': ['\u039D', '\u0474'],
    'w': ['\u0282'],
    'W': ['\u0428'],
    'x': ['\u0445', '\u00D7'],
    'X': ['\u0425', '\u00D7'],
    'y': ['\u0443', '\u00FD', '\u00FF', '\u0177', '\u028F'],
    'Y': ['\u0423', '\u00DD', '\u0176', '\u0178'],
    'z': ['\u017A', '\u017C', '\u017E'],
    'Z': ['\u0179', '\u017B', '\u017D'],
}

# L25: Emoji variation sequences - إضافة VS15/VS16 بعد الإيموجي لكسر hash matching
EMOJI_VS_RANGE = list(range(0x1F300, 0x1FAFF))  # نطاق الإيموجي الشائع

# L26: Hash-busting padding - إضافة padding عشوائي في بداية ونهاية الرسالة
# لكسر مطابقة الـ hash حتى لو تطابقت كل الطبقات الأخرى
HASH_BUSTING_PADS = [
    '\u200B\u200C\u200D',  # ZWSP+ZWNJ+ZWJ
    '\u2060\uFEFF',        # WJ+BOM
    '\u200E\u200F',        # LRM+RLM
    '\U000E0001\U000E007F',  # TAG+CANCEL_TAG
    '\u3164',              # Hangul Filler
    '\u2068\u2069',        # FSI+PDI
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
        # ── طبقات متقدمة جديدة v2.1 ──
        'L19_tag_chars':       'Tag Characters (U+E0000) - إخفاء كامل',
        'L20_hangul_filler':   'Hangul Fillers - أحرف كورية غير مرئية',
        'L21_bidi_isolates':   'Bidirectional Isolates (FSI/PDI) - يكسر regex',
        'L22_math_symbols':    'Math Symbols (Fraktur/Script/Double-struck)',
        'L23_smart_punct':     'علامات ترقيم ذكية (smart quotes/dashes)',
        'L24_expanded_confusables': 'قاعدة Unicode Confusables الموسعة',
        'L25_emoji_vs':        'Emoji Variation Sequences (يكسر hash)',
        'L26_hash_bust':       'Hash-busting padding (يكسر hash matching)',
    }

    # مستويات القوة
    STRENGTH_LEVELS = {
        'light': [
            'L01_homoglyph', 'L02_zero_width', 'L06_space_variant',
            'L09_link_obf', 'L10_mention_obf', 'L11_pergroup_hash', 'L12_trailing',
            'L24_expanded_confusables', 'L26_hash_bust',
        ],
        'medium': [
            'L01_homoglyph', 'L02_zero_width', 'L03_tatweel',
            'L05_combining', 'L06_space_variant', 'L09_link_obf',
            'L10_mention_obf', 'L11_pergroup_hash', 'L12_trailing',
            'L13_linebreak_var', 'L16_numeric_sub', 'L17_punct_sub', 'L18_midword_zwsp',
            'L19_tag_chars', 'L23_smart_punct', 'L24_expanded_confusables',
            'L26_hash_bust',
        ],
        'aggressive': [
            'L01_homoglyph', 'L02_zero_width', 'L03_tatweel',
            'L04_harakat', 'L05_combining', 'L06_space_variant',
            'L07_directional', 'L09_link_obf', 'L10_mention_obf',
            'L11_pergroup_hash', 'L12_trailing', 'L13_linebreak_var',
            'L15_keyword_heavy', 'L16_numeric_sub', 'L17_punct_sub', 'L18_midword_zwsp',
            'L19_tag_chars', 'L20_hangul_filler', 'L21_bidi_isolates',
            'L22_math_symbols', 'L23_smart_punct', 'L24_expanded_confusables',
            'L25_emoji_vs', 'L26_hash_bust',
        ],
        'insane': [
            'L01_homoglyph', 'L02_zero_width', 'L03_tatweel',
            'L04_harakat', 'L05_combining', 'L06_space_variant',
            'L07_directional', 'L08_variation_sel', 'L09_link_obf',
            'L10_mention_obf', 'L11_pergroup_hash', 'L12_trailing',
            'L13_linebreak_var', 'L14_paragraph_sep', 'L15_keyword_heavy',
            'L16_numeric_sub', 'L17_punct_sub', 'L18_midword_zwsp',
            'L19_tag_chars', 'L20_hangul_filler', 'L21_bidi_isolates',
            'L22_math_symbols', 'L23_smart_punct', 'L24_expanded_confusables',
            'L25_emoji_vs', 'L26_hash_bust',
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

    # ═══════════════════════════════════════════════════════════
    #  طبقات متقدمة جديدة v2.1 (L19-L26)
    #  مستوحاة من: confusable_homoglyphs، unicode-tools،
    #  anti-spam-bypass، telegram-ad-evasion على GitHub
    # ═══════════════════════════════════════════════════════════

    def _L19_tag_chars(self, text, rng):
        """
        Tag Characters (U+E0000-U+E007F) - كاملة الإخفاء
        هذه الأحرف وسوم لغة معرّفة في Unicode لكنها غير مرئية تماماً.
        تستخدمها بوتات الحماية نادراً في فلاتر الكشف.
        """
        if len(text) < 5:
            return text
        result = []
        # إدراج tag char في البداية (Language Tag opener + space + closer)
        if rng.random() < 0.60:
            result.append('\U000E0001')  # LANGUAGE TAG opener
            result.append(rng.choice(['\U000E0041', '\U000E0061', '\U000E0042', '\U000E0062']))  # TAG letter
            result.append('\U000E007F')  # CANCEL TAG
        for i, ch in enumerate(text):
            result.append(ch)
            # بعد المسافة: 8% احتمال إدراج tag char
            if ch == ' ' and rng.random() < 0.08:
                result.append(rng.choice(TAG_CHARS))
        # في النهاية
        if rng.random() < 0.40:
            result.append(rng.choice(TAG_CHARS))
        return ''.join(result)

    def _L20_hangul_filler(self, text, rng):
        """
        Hangul Fillers (U+3164, U+115F, U+1160) - أحرف كورية غير مرئية
        تظهر كمسافات فارغة في معظم الخطوط لكنها bytes إضافية تكسر pattern matching.
        """
        if len(text) < 10:
            return text
        result = []
        words = text.split(' ')
        for i, word in enumerate(words):
            result.append(word)
            if i < len(words) - 1:
                # استبدال بعض المسافات بـ Hangul filler (غير مرئي)
                if rng.random() < 0.15:
                    result.append(rng.choice(HANGUL_FILLERS))
                else:
                    result.append(' ')
        # إضافة filler في النهاية أحياناً
        if rng.random() < 0.30:
            result.append(rng.choice(HANGUL_FILLERS))
        return ''.join(result)

    def _L21_bidi_isolates(self, text, rng):
        """
        Bidirectional Isolation marks (FSI/PDI - U+2068/U+2069)
        تقنية جديدة من Unicode 6.3+ لا يعرفها معظم بوتات الحماية القديمة.
        تعزل اتجاه النص دون التأثير على العرض البصري.
        """
        if len(text) < 15:
            return text
        result = []
        # إحاطة بعض الكلمات بـ FSI...PDI
        words = text.split(' ')
        for i, word in enumerate(words):
            # 12% من الكلمات نحيطها بـ bidi isolates
            if rng.random() < 0.12 and len(word) > 2:
                result.append('\u2068')  # FSI
                result.append(word)
                result.append('\u2069')  # PDI
            else:
                result.append(word)
            if i < len(words) - 1:
                result.append(' ')
        return ''.join(result)

    def _L22_math_symbols(self, text, rng):
        """
        Mathematical Alphanumeric Symbols (Fraktur/Script/Double-struck)
        يحول بعض الأحرف اللاتينية إلى أنماط رياضية مميزة.
        النص يبقى مقروءاً لكنه يبدو مختلفاً تماماً عن النص العادي.
        مفيد جداً للكلمات المفتاحية الإنجليزية.
        """
        result = []
        # اختيار نمط عشوائي واحد لكل رسالة (للتناسق البصري)
        style_map = rng.choice(MATH_STYLE_MAPS)
        for ch in text:
            lower = ch.lower()
            if lower in style_map and rng.random() < 0.20:
                result.append(style_map[lower])
            else:
                result.append(ch)
        return ''.join(result)

    def _L23_smart_punct(self, text, rng):
        """
        Smart Punctuation - استبدال علامات الترقيم بنسخ ذكية
        مستوحى من تقنية smart_quotes في معالجات النصوص الحديثة.
        """
        # استبدال التسلسلات الطويلة أولاً
        for orig, smart in sorted(SMART_PUNCT.items(), key=lambda x: -len(x[0])):
            if orig in text and rng.random() < 0.70:
                text = text.replace(orig, smart, 1)
        # استبدال علامات مفردة
        result = []
        in_url = False
        for i, ch in enumerate(text):
            # كشف URL - لا نلمس علامات الترقيم داخل الروابط
            if text[max(0, i-7):i].lower().endswith(('http://', 'https:/')):
                in_url = True
            if in_url and ch == ' ':
                in_url = False
            if in_url:
                result.append(ch)
                continue
            if ch in SMART_PUNCT and len(ch) == 1 and rng.random() < 0.50:
                result.append(SMART_PUNCT[ch])
            else:
                result.append(ch)
        return ''.join(result)

    def _L24_expanded_confusables(self, text, rng):
        """
        Expanded Confusables Database - قاعدة بيانات Unicode Confusables الموسعة
        مستوحاة من مستودع: https://github.com/woodward/confusable_homoglyphs
        يحاول استخدام بدائل إضافية للحروف اللاتينية.
        """
        result = []
        for ch in text:
            if ch in EXPANDED_LATIN_CONFUSABLES and rng.random() < 0.25:
                # اختيار بديل عشوائي من القائمة الموسعة
                alternatives = EXPANDED_LATIN_CONFUSABLES[ch]
                result.append(rng.choice(alternatives))
            else:
                result.append(ch)
        return ''.join(result)

    def _L25_emoji_vs(self, text, rng):
        """
        Emoji Variation Sequences - إضافة VS15/VS16 بعد الإيموجي
        يكسر مطابقة الـ hash للرسائل التي تحتوي إيموجي.
        VS15 = عرض كنص، VS16 = عرض كإيموجي.
        """
        result = []
        for ch in text:
            result.append(ch)
            cp = ord(ch)
            # إذا كان الإيموجي في النطاق الشائع
            if (0x1F300 <= cp <= 0x1FAFF) or (0x2600 <= cp <= 0x27BF):
                # 70% احتمال إضافة VS15 أو VS16
                if rng.random() < 0.70:
                    result.append(rng.choice([VS15, VS16]))
        return ''.join(result)

    def _L26_hash_bust(self, text, rng):
        """
        Hash-busting Padding - إضافة padding عشوائي في البداية والنهاية
        يكسر مطابقة الـ hash حتى لو تطابقت كل الطبقات الأخرى.
        كل رسالة تحصل على padding فريد = hash فريد.
        """
        if not text:
            return text
        # padding في البداية (1-2 chars)
        prefix = ''
        if rng.random() < 0.85:
            n_pad = rng.randint(1, 2)
            for _ in range(n_pad):
                prefix += rng.choice(HASH_BUSTING_PADS)
        # padding في النهاية (1-3 chars)
        suffix = ''
        if rng.random() < 0.85:
            n_pad = rng.randint(1, 3)
            for _ in range(n_pad):
                suffix += rng.choice(HASH_BUSTING_PADS)
        return prefix + text + suffix

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
            'L22_math_symbols',   # Math symbols (للكلمات الإنجليزية)
            'L24_expanded_confusables',  # بدائل لاتينية موسعة
            'L01_homoglyph',      # استبدال الحروف الأساسي
            'L16_numeric_sub',    # استبدال الأرقام
            'L18_midword_zwsp',   # ZWSP داخل الكلمات
            'L23_smart_punct',    # علامات ترقيم ذكية
            'L17_punct_sub',      # علامات الترقيم fullwidth
            'L09_link_obf',       # تمويه الروابط
            'L10_mention_obf',    # تمويه الإشارات
            'L03_tatweel',        # الكاشيدة
            'L04_harakat',        # التشكيل
            'L05_combining',      # Combining marks
            'L06_space_variant',  # مسافات بديلة
            'L20_hangul_filler',  # Hangul fillers (بعد المسافات)
            'L21_bidi_isolates',  # Bidi isolates حول الكلمات
            'L02_zero_width',     # ZW chars بين الكلمات
            'L13_linebreak_var',  # تنويع الأسطر
            'L14_paragraph_sep',  # فواصل الفقرات
            'L07_directional',    # علامات اتجاه
            'L08_variation_sel',  # Variation selectors
            'L25_emoji_vs',       # Emoji variation sequences
            'L19_tag_chars',      # Tag chars (تقريباً نهاية الرسالة)
            'L11_pergroup_hash',  # بصمة المجموعة
            'L12_trailing',       # ذيل غير مرئي
            'L26_hash_bust',      # Hash-busting padding (الأخير دائماً)
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
        'tag_chars': 0,
        'hangul_fillers': 0,
        'bidi_isolates': 0,
        'math_symbols': 0,
        'other_invisible': 0,
    }
    all_invisible = set(ZERO_WIDTH_CHARS + DIRECTIONAL_MARKS + COMBINING_MARKS +
                         SPACE_VARIANTS + [VS15, VS16] + ARABIC_HARAKAT_LIST + [TATWEEL] +
                         TAG_CHARS + HANGUL_FILLERS + BIDI_ISOLATES + [LRI, RLI])
    math_chars = set()
    for m in MATH_STYLE_MAPS:
        math_chars.update(m.values())
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
        elif ch in TAG_CHARS:
            counts['tag_chars'] += 1
        elif ch in HANGUL_FILLERS:
            counts['hangul_fillers'] += 1
        elif ch in BIDI_ISOLATES or ch in [LRI, RLI]:
            counts['bidi_isolates'] += 1
        elif ch in math_chars:
            counts['math_symbols'] += 1
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
