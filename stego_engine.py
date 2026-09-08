"""
🫥 Stego Engine v2.0 - محرك الحماية النصي (سلامة النص أولاً)
=============================================================

⚠️ القاعدة الذهبية (v2.0):
   البوت يرسل **بالضبط** النص الذي كتبه المستخدم.
   لا يُضاف أي كلمة، ولا يُحذف أي كلمة، ولا يُستبدل النص بنص غلاف.
   كل المعالجات غير مرئية فقط (Unicode خفي لا يغير شكل النص).

المميزات:
1. Spintax متداخل - {خيار1|خيار2|{خيار3|خيار4}} (يُحل فقط إذا كتبه المستخدم)
2. ZW Fingerprint - حقن أحرف صفرية خفية داخل نص المستخدم نفسه
   (النص يبقى ظاهراً ومقروءاً 100% - كل نسخة تحصل على بصمة فريدة)
3. نظام أوضاع موحد - normal / spintax / stego

المصادر المستوحاة:
- Afynjv2963/ZeroWidthStego (أحرف العرض الصفري)
- AceLewis/spintax (تحليل Spintax المتداخل)
"""

import random
import re
from typing import List, Tuple, Optional

# ═══════════════════════════════════════════════════════════════
# 1️⃣ SPINTAX - التنويع اللغوي المتداخل
# ═══════════════════════════════════════════════════════════════

def parse_spintax_advanced(text: str, max_iterations: int = 50) -> str:
    """
    تحليل Spintax متداخل: {خيار1|خيار2|خيار3}
    يدعم التداخل العميق: {مرحباً|أهلاً} {بالجميع|{بكم|معكم}}
    
    مثال:
        parse_spintax_advanced("{مرحباً|أهلاً} بكم في {قناتنا|مجموعتنا}")
        → "مرحباً بكم في قناتنا" أو "أهلاً بكم في مجموعتنا" ...
    """
    if not text or '{' not in text or '}' not in text:
        return text
    
    iterations = 0
    while '{' in text and '}' in text and iterations < max_iterations:
        # استبدال الأقواس الداخلية أولاً (الأعمق)
        new_text = re.sub(
            r'\{([^{}]*)\}',
            lambda m: random.choice(m.group(1).split('|')),
            text
        )
        if new_text == text:
            break  # لا توجد تغييرات - أقواس غير متوازنة
        text = new_text
        iterations += 1
    
    return text


def count_spintax_variations(text: str) -> int:
    """حساب عدد التركيبات الممكنة في نص Spintax"""
    if not text or '{' not in text:
        return 1
    
    # إيجاد الأقواس الداخلية
    inner_blocks = re.findall(r'\{([^{}]*)\}', text)
    if not inner_blocks:
        return 1
    
    total = 1
    for block in inner_blocks:
        options = block.split('|')
        total *= max(len(options), 1)
    return total


def has_spintax(text: str) -> bool:
    """فحص إذا كان النص يحتوي على صيغة Spintax صالحة"""
    return bool(re.search(r'\{[^{}]+\|[^{}]*\}', text))


# ═══════════════════════════════════════════════════════════════
# 2️⃣ ZERO-WIDTH STEGANOGRAPHY - إخفاء نص داخل نص
# ═══════════════════════════════════════════════════════════════

# 🛡️ v4.1 - أبجدية البصمة المطورة (قناة Variation Selectors):
#   ❌ الأبجدية v3.0 (2060/061C/2061/2062) حروف Cf غير واصلة حسب معيار
#      Unicode (ArabicShaping.txt) - لو زُرعت وسط كلمة عربية تقطع اتصال
#      الحروف في المحركات الصارمة (سبب تلبّط إضافي في وضع stego)!
#   ✅ الأبجدية الجديدة VS17+ (E0100-E0103) فئتها Mn = Joining Transparent
#      → لا تقطع الاتصال في أي محرك عرض، وغير مرئية 100%، وخارج قوائم
#      التنظيف المعروفة (out-of-character وغيرها)
# نظام 2-bit: 4 أحرف = 4 حالات = بتان لكل حرف
FINGERPRINT_ALPHABET = [
    '\U0001E0100',  # 00 - VS17
    '\U0001E0101',  # 01 - VS18
    '\U0001E0102',  # 10 - VS19
    '\U0001E0103',  # 11 - VS20
]

# 🔁 مجمع الحقن العشوائي للبصمة (النسخة الكاملة 240 حرف VS17+)
# يُستخدم في inject_zw_fingerprint لزيادة الإنتروبيا ضد الإحصاء الكمي
FINGERPRINT_POOL = [chr(c) for c in range(0xE0100, 0xE01F0)]

# الأبجدية v3.0 القديمة (لفتح ترميز الرسائل القديمة فقط)
LEGACY_FINGERPRINT_ALPHABET = [
    '\u2060',  # 00 - Word Joiner
    '\u061C',  # 01 - Arabic Letter Mark
    '\u2061',  # 10 - Function Application
    '\u2062',  # 11 - Invisible Times
]

# الأبجدية الأقدم (للترميز اليدوي القديم وفك ترميزه فقط)
ZW_CHARS = [
    '\u200B',  # 00 - Zero Width Space
    '\u200C',  # 01 - Zero Width Non-Joiner
    '\u200D',  # 10 - Zero Width Joiner
    '\uFEFF',  # 11 - Zero Width No-Break Space
]

# خريطة فك الترميز الموحدة (جديد + قديم + أقدم)
_DECODE_MAP = {}
for _i, _c in enumerate(FINGERPRINT_ALPHABET):
    _DECODE_MAP[_c] = format(_i, '02b')
for _i, _c in enumerate(LEGACY_FINGERPRINT_ALPHABET):
    _DECODE_MAP.setdefault(_c, format(_i, '02b'))
for _i, _c in enumerate(ZW_CHARS):
    _DECODE_MAP.setdefault(_c, format(_i, '02b'))

# كل الأحرف الخفية المعروفة (للفحص)
ALL_INVISIBLES = (set(FINGERPRINT_ALPHABET) | set(LEGACY_FINGERPRINT_ALPHABET)
                  | set(ZW_CHARS))


def _text_to_bits(text: str) -> str:
    """تحويل نص إلى سلسلة بتات UTF-8"""
    data = text.encode('utf-8')
    return ''.join(format(byte, '08b') for byte in data)


def _bits_to_text(bits: str) -> Optional[str]:
    """تحويل بتات إلى نص UTF-8"""
    if len(bits) % 8 != 0:
        bits = bits[:len(bits) - (len(bits) % 8)]
    if not bits:
        return None
    try:
        data = bytes(int(bits[i:i+8], 2) for i in range(0, len(bits), 8))
        return data.decode('utf-8', errors='strict')
    except (UnicodeDecodeError, ValueError):
        return None


def inject_zw_fingerprint(text: str, density: float = 0.06) -> str:
    """
    🫥 حقن بصمة صفرية خفية داخل نص المستخدم نفسه (v3.0 آمن على العربية)

    ⚠️ القاعدة الذهبية: النص يبقى ظاهراً ومقروءاً 100% كما كتبه المستخدم.
       تُضاف أحرف غير مرئية فقط بين الحروف/الكلمات لتصبح كل رسالة
       ذات بصمة Unicode فريدة لا تستطيع بوتات الحماية مطابقتها برسائل سابقة.

    🆕 v4.1: مجمع الحقن = قناة VS17+ كاملة (240 حرف):
       فئة Mn → Joining Transparent → لا تقطع اتصال الحروف العربية أبداً
       (عكس 2060/061C/2061/2062 القديمة التي كانت تقطعه في المحركات الصارمة،
        وعكس 200C الأقدم التي كانت تفسدها في كل المحركات!)

    🛡️ الروابط والمعرفات (t.me/... / https://... / @username) محمية
       تماماً - لا تُحقن فيها أحرف كي تبقى قابلة للنقر والنسخ.

    Args:
        text: نص المستخدم (يظل كما هو تماماً في الشكل)
        density: كثافة الحقن (نسبة من مواضع الحروف)

    Returns:
        نفس النص + أحرف غير مرئية موزعة (الشكل الظاهر لم يتغير)
    """
    if not text or len(text) < 4 or density <= 0:
        return text

    # 🛡️ حماية الروابط والمعرفات من الحقن
    protected_re = re.compile(r'(https?://\S+|t\.me/\S+|@[a-zA-Z0-9_]{3,})')
    parts = []
    last = 0
    for m in protected_re.finditer(text):
        if m.start() > last:
            parts.append((text[last:m.start()], False))
        parts.append((m.group(0), True))
        last = m.end()
    if last < len(text):
        parts.append((text[last:], False))
    if not parts:
        parts = [(text, False)]

    result = []
    for seg, protected in parts:
        if protected:
            result.append(seg)
            continue
        for ch in seg:
            result.append(ch)
            # لا نضيف بعد مسافات أو أسطر مباشرة كي لا يتغير التنسيق
            if ch not in (' ', '\n', '\t') and random.random() < density:
                result.append(random.choice(FINGERPRINT_POOL))
    return ''.join(result)


def zero_width_hide(secret: str, cover: str = "") -> str:
    """
    🛡️ v2.0: لم يعد يولّد نصوص غلاف تلقائية أبداً
    
    - إذا وُفر cover: يخفي السر بداخله (الغلاف الظاهر - أداة يدوية فقط)
    - إذا لم يُوفر cover: يُرجع النص نفسه مع بصمة ZW خفية
      (النص الظاهر = نص المستخدم بالضبط)
    """
    if not secret:
        return cover
    
    # بدون غلاف → النص الظاهر هو نص المستخدم نفسه + بصمة خفية
    if not cover:
        return inject_zw_fingerprint(secret)
    
    # تحويل السر إلى بتات
    bits = _text_to_bits(secret)
    
    # تحويل كل بتين إلى حرف صفري واحد
    zw_encoded = ''
    for i in range(0, len(bits), 2):
        pair = bits[i:i+2].ljust(2, '0')
        index = int(pair, 2)
        zw_encoded += ZW_CHARS[index]
    
    # إدراج الأحرف الصفرية داخل نص الغلاف المحدد من المستخدم
    words = cover.split(' ')
    if len(words) > 2:
        pos = 1 + random.randint(0, len(words) - 2)
        result_words = words[:pos] + [words[pos] + zw_encoded] + words[pos+1:]
        return ' '.join(result_words)
    else:
        return cover + zw_encoded


def zero_width_reveal(stego_text: str) -> Optional[str]:
    """
    استخراج النص المخفي من نص مشفر

    🆕 v4.1: يفهم الأبجدية الجديدة VS17+ (E0100-E0103)
       والأبجدية القديمة (2060/061C/2061/2062) والأقدم (200B/200C/200D/FEFF)
       للتوافق مع الرسائل القديمة

    Returns:
        النص السري أو None إذا لم يوجد شيء
    """
    if not stego_text:
        return None

    # استخراج كل الأحرف الخفية المعروفة بالترتيب
    bits = ''.join(_DECODE_MAP[ch] for ch in stego_text if ch in _DECODE_MAP)
    if len(bits) < 8:  # أقل من 8 بتات = لا يوجد سر
        return None

    return _bits_to_text(bits)


def has_zero_width(text: str) -> bool:
    """فحص وجود أحرف عرض صفري كثيرة (مؤشر إخفاء)"""
    count = sum(1 for ch in text if ch in ALL_INVISIBLES)
    return count > 8  # أكثر من 8 أحرف صفرية = يوجد سر


# ═══════════════════════════════════════════════════════════════
# 3️⃣ ARABIC DIACRITIC STEGANOGRAPHY - إخفاء بالتشكيل العربي
# ═══════════════════════════════════════════════════════════════

# علامات التشكيل العربية (8 علامات = نظام 3-bit)
# 🆕 v3.0: توسيع من 4 إلى 8 علامات → السعة ×1.5
# (40 حرف عربي × 3 بت = 15 بايت تكفي رابط t.me كامل)
DIACRITICS = {
    '\u064E': '000',  # فتحة
    '\u064F': '001',  # ضمة
    '\u0650': '010',  # كسرة
    '\u0651': '011',  # شدة
    '\u0652': '100',  # سكون
    '\u064B': '101',  # فتحتان
    '\u064C': '110',  # ضمتان
    '\u064D': '111',  # كسرتان
}

DIACRITICS_LIST = list(DIACRITICS.keys())
DIACRITICS_SET = set(DIACRITICS.keys())


def _english_to_diacritic_bits(text: str) -> str:
    """تحويل نص إنجليزي إلى بتات"""
    data = text.encode('ascii', errors='ignore')
    return ''.join(format(byte, '08b') for byte in data)


def diacritic_hide(secret: str, cover: str = "") -> str:
    """
    🛡️ v2.0: أداة يدوية فقط - لا تُستخدم في مسار النشر التلقائي
    🆕 v3.0: نظام 3-bit (8 علامات) - السعة ×1.5
    
    إخفاء رسالة إنجليزية (رابط أو كود) داخل نص عربي مشكول **من المستخدم**
    لا يولّد نصوص غلاف تلقائية أبداً.
    
    Args:
        secret: الرسالة السرية (بالإنجليزية - مثل رابط t.me)
        cover: النص العربي الظاهر (يجلبه المستخدم - إجباري)
    
    Returns:
        نص عربي مشكول طبيعياً + الرسالة السرية مخفية في التشكيل
        أو النص مع بصمة ZW إذا لم يُوفر غلاف عربي صالح
    """
    if not secret:
        return cover
    
    # 🛡️ v2.0: لا نصوص غلاف تلقائية - التشكيل يحتاج نصاً عربياً من المستخدم
    if not cover or not any('\u0600' <= ch <= '\u06FF' for ch in cover):
        return inject_zw_fingerprint(secret if not cover else (cover + ' ' + secret))
    
    # تحويل السر إلى بتات
    bits = _english_to_diacritic_bits(secret)
    # 🛡️ v2.0: لا توسيع تلقائي بجمل جاهزة - نُشكّل ما يتسع فقط (أداة يدوية)
    
    # تطبيق التشكيل على الحروف العربية
    result = []
    bit_index = 0
    for ch in cover:
        if '\u0600' <= ch <= '\u06FF' and bit_index < len(bits):
            # إضافة حرف التشكيل المناسب
            triplet = bits[bit_index:bit_index+3].ljust(3, '0')
            diacritic = _bits_to_diacritic(triplet)
            if diacritic:
                result.append(ch + diacritic)
            else:
                result.append(ch)
            bit_index += 3
        else:
            result.append(ch)
    
    return ''.join(result)


def _bits_to_diacritic(bits: str) -> Optional[str]:
    """تحويل بتات إلى حرف تشكيل (نظام 3-bit)"""
    mapping = {
        '000': '\u064E', '001': '\u064F', '010': '\u0650', '011': '\u0651',
        '100': '\u0652', '101': '\u064B', '110': '\u064C', '111': '\u064D',
    }
    return mapping.get(bits)


def _diacritic_to_bits(diacritic: str) -> Optional[str]:
    """تحويل حرف تشكيل إلى بتات (نظام 3-bit)"""
    mapping = {
        '\u064E': '000', '\u064F': '001', '\u0650': '010', '\u0651': '011',
        '\u0652': '100', '\u064B': '101', '\u064C': '110', '\u064D': '111',
    }
    return mapping.get(diacritic)


def diacritic_reveal(stego_text: str) -> Optional[str]:
    """
    استخراج الرسالة الإنجليزية المخفية من التشكيل العربي
    
    Returns:
        الرسالة السرية أو None
    """
    if not stego_text:
        return None
    
    # استخراج علامات التشكيل بالترتيب
    bits = ''
    for ch in stego_text:
        if ch in DIACRITICS_SET:
            bit_pair = _diacritic_to_bits(ch)
            if bit_pair:
                bits += bit_pair
    
    if len(bits) < 8:
        return None
    
    # تحويل البتات إلى نص
    if len(bits) % 8 != 0:
        bits = bits[:len(bits) - (len(bits) % 8)]
    
    try:
        data = bytes(int(bits[i:i+8], 2) for i in range(0, len(bits), 8))
        return data.decode('ascii', errors='strict')
    except (UnicodeDecodeError, ValueError):
        return None


def has_diacritics(text: str) -> bool:
    """فحص وجود تشكيل كثير (مؤشر إخفاء)"""
    count = sum(1 for ch in text if ch in DIACRITICS_SET)
    return count > 10


# ═══════════════════════════════════════════════════════════════
# 4️⃣ إدارة الأوضاع الموحدة - Send Mode Manager
# ═══════════════════════════════════════════════════════════════

# الأوضاع المدعومة (v2.0 - كل الأوضاع تحافظ على نص المستخدم كما هو)
SEND_MODES = {
    'normal': {
        'name': 'نص عادي',
        'icon': '📝',
        'description': 'إرسال النص كما هو تماماً بدون أي معالجة إضافية',
    },
    'spintax': {
        'name': 'Spintax - تنويع لغوي',
        'icon': '🔄',
        'description': 'يحل صيغة {خيار1|خيار2} إذا كتبتها أنت - كل رسالة فريدة بنفس كلماتك',
    },
    'stego': {
        'name': 'بصمة خفية (ZW Fingerprint)',
        'icon': '🫥',
        'description': 'نصك يظهر كما هو 100% + أحرف خفية غير مرئية تعطي كل رسالة بصمة فريدة',
    },
}

DEFAULT_MODE = 'normal'


class StegoEngine:
    """
    محرك الإخفاء الرئيسي - يدير كل تقنيات الإخفاء والأوضاع
    """
    
    def __init__(self):
        self.mode = DEFAULT_MODE
        self.stats = {
            'sent_normal': 0,
            'sent_spintax': 0,
            'sent_stego': 0,
        }
    
    def set_mode(self, mode: str) -> bool:
        """تغيير وضع الإرسال"""
        if mode in SEND_MODES:
            self.mode = mode
            return True
        return False
    
    def get_mode(self) -> str:
        """الوضع الحالي"""
        return self.mode
    
    def get_mode_info(self, mode: str = None) -> dict:
        """معلومات وضع معين"""
        return SEND_MODES.get(mode or self.mode, SEND_MODES[DEFAULT_MODE])
    
    def process(self, content: str, mode: str = None, cover_text: str = None) -> Tuple[str, dict]:
        """
        معالجة النص حسب الوضع المحدد
        
        🛡️ v2.0 القاعدة الذهبية: النص الظاهر الناتج = نص المستخدم دائماً.
        لا كلمات مضافة، لا حذف، لا نصوص غلاف - كل شيء غير مرئي فقط.
        
        Args:
            content: النص الأصلي (قد يحتوي spintax كتبه المستخدم)
            mode: الوضع (إذا لم يُحدد، يستخدم الوضع الحالي)
            cover_text: غير مستخدم في v2.0 (توافق مع الواجهة القديمة فقط)
        
        Returns:
            (النص النهائي, معلومات المعالجة)
        """
        use_mode = mode or self.mode
        info = {'mode': use_mode, 'original_length': len(content)}
        
        if not content:
            return content, info
        
        # تطبيق الوضع
        if use_mode == 'spintax':
            # حل صيغة {خيار1|خيار2} التي كتبها المستخدم فقط
            result = parse_spintax_advanced(content) if has_spintax(content) else content
            self.stats['sent_spintax'] += 1
            info['spintax_resolved'] = has_spintax(content)
            
        elif use_mode == 'stego':
            # 1) حل spintax إن كتبه المستخدم
            clean = parse_spintax_advanced(content) if has_spintax(content) else content
            # 2) حقن بصمة ZW خفية داخل نص المستخدم نفسه (يظل ظاهراً 100%)
            result = inject_zw_fingerprint(clean)
            self.stats['sent_stego'] += 1
            info['fingerprint'] = True
            
        else:
            # normal - النص كما هو تماماً
            result = content
            self.stats['sent_normal'] += 1
        
        info['final_length'] = len(result)
        info['visible_text_preserved'] = True  # نص المستخدم محفوظ دائماً
        
        return result, info
    
    def _extract_english_part(self, content: str) -> Optional[str]:
        """استخراج الجزء الإنجليزي (روابط، معرفات) من المحتوى"""
        links = re.findall(r'(?:https?://\S+|t\.me/\S+)', content)
        mentions = re.findall(r'@[a-zA-Z0-9_]{3,}', content)
        
        parts = links + mentions
        if parts:
            return ' '.join(parts)
        
        # إذا لم يوجد رابط - استخدم النص كاملاً إذا كان إنجليزياً
        if content and all(ord(ch) < 128 for ch in content.strip()):
            return content.strip()
        
        return None
    
    def get_stats(self) -> dict:
        """إحصائيات المحرك"""
        return {**self.stats, 'current_mode': self.mode}
    
    def get_mode_list(self) -> str:
        """قائمة الأوضاع كنص للعرض"""
        text = "🎛 **أوضاع الإرسال المتاحة:**\n\n"
        for mode_key, mode_info in SEND_MODES.items():
            current = " ← (الحالي)" if mode_key == self.mode else ""
            text += f"{mode_info['icon']} **{mode_key}**{current}\n"
            text += f"   {mode_info['description']}\n\n"
        return text


# إنشاء instance عالمي
stego_engine = StegoEngine()


# ═══════════════════════════════════════════════════════════════
# 🧪 اختبار المحرك
# ═══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print("=" * 60)
    print("🫥 اختبار Stego Engine")
    print("=" * 60)
    
    # 1. اختبار Spintax
    print("\n1️⃣ اختبار Spintax:")
    test_spin = "{مرحباً|أهلاً|سلام} بكم في {قناتنا|مجموعتنا} الحصرية"
    for i in range(3):
        print(f"   محاولة {i+1}: {parse_spintax_advanced(test_spin)}")
    print(f"   عدد التركيبات: {count_spintax_variations(test_spin)}")
    
    # 2. اختبار Zero-Width Stego
    print("\n2️⃣ اختبار Zero-Width Stego:")
    secret_msg = "اشترك في قناتنا t.me/mychannel"
    cover_msg = "مرحباً بكم 🌟 نتمنى لكم يوماً سعيداً"
    hidden = zero_width_hide(secret_msg, cover_msg)
    revealed = zero_width_reveal(hidden)
    print(f"   السر: {secret_msg}")
    print(f"   الغلاف: {cover_msg}")
    print(f"   المشفر (يظهر): {hidden[:50]}...")
    print(f"   بعد الكشف: {revealed}")
    print(f"   ✅ نجح: {revealed == secret_msg}")
    
    # 3. اختبار Diacritic Stego
    print("\n3️⃣ اختبار Diacritic Stego:")
    secret_en = "t.me/mychannel"
    cover_ar = "القناة الرسمية للمحتوى الحصري والأخبار العاجلة"
    hidden_ar = diacritic_hide(secret_en, cover_ar)
    revealed_en = diacritic_reveal(hidden_ar)
    print(f"   السر: {secret_en}")
    print(f"   الغلاف: {cover_ar}")
    print(f"   المشفر: {hidden_ar}")
    print(f"   بعد الكشف: {revealed_en}")
    print(f"   ✅ نجح: {revealed_en == secret_en}")
    
    # 4. اختبار الأوضاع
    print("\n4️⃣ اختبار الأوضاع:")
    test_content = "اشترك في {قناتنا|قناتنا الرسمية} t.me/example"
    for mode in SEND_MODES:
        stego_engine.set_mode(mode)
        result, info = stego_engine.process(test_content)
        print(f"   [{mode}] → {result[:60]}...")
    
    print("\n" + "=" * 60)
    print("✅ اكتمل الاختبار!")
