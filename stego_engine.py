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

# أحرف العرض الصفري (4 أحرف = نظام ثنائي 2-bit)
ZW_CHARS = [
    '\u200B',  # 00 - Zero Width Space
    '\u200C',  # 01 - Zero Width Non-Joiner
    '\u200D',  # 10 - Zero Width Joiner
    '\uFEFF',  # 11 - Zero Width No-Break Space
]

# أحرف إضافية متوافقة مع تيليجرام (وضع موسع)
ZW_EXTENDED = ['\u2061', '\u2062', '\u2063']


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
    🫥 حقن بصمة صفرية خفية داخل نص المستخدم نفسه
    
    ⚠️ القاعدة الذهبية: النص يبقى ظاهراً ومقروءاً 100% كما كتبه المستخدم.
       تُضاف أحرف غير مرئية فقط بين الحروف/الكلمات لتصبح كل رسالة
       ذات بصمة Unicode فريدة لا تستطيع بوتات الحماية مطابقتها برسائل سابقة.
    
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
                result.append(random.choice(ZW_CHARS))
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
    
    Returns:
        النص السري أو None إذا لم يوجد شيء
    """
    if not stego_text:
        return None
    
    # استخراج جميع أحرف العرض الصفري
    zw_found = ''.join(ch for ch in stego_text if ch in ZW_CHARS)
    if len(zw_found) < 4:  # أقل من حرفين = لا يوجد سر
        return None
    
    # تحويل الأحرف الصفرية إلى بتات
    bits = ''
    for ch in zw_found:
        index = ZW_CHARS.index(ch)
        bits += format(index, '02b')
    
    return _bits_to_text(bits)


def has_zero_width(text: str) -> bool:
    """فحص وجود أحرف عرض صفري كثيرة (مؤشر إخفاء)"""
    count = sum(1 for ch in text if ch in ZW_CHARS)
    return count > 8  # أكثر من 8 أحرف صفرية = يوجد سر


# ═══════════════════════════════════════════════════════════════
# 3️⃣ ARABIC DIACRITIC STEGANOGRAPHY - إخفاء بالتشكيل العربي
# ═══════════════════════════════════════════════════════════════

# علامات التشكيل العربية (4 علامات أساسية = نظام 2-bit)
DIACRITICS = {
    '\u064E': '00',  # فتحة (Fathatan Fatha)
    '\u064F': '01',  # ضمة (Damma)
    '\u0650': '10',  # كسرة (Kasra)
    '\u0651': '11',  # شدة (Shadda)
    # '\u0652': ' sukun' - سكون (يُستخدم للنهاية)
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
            pair = bits[bit_index:bit_index+2].ljust(2, '0')
            diacritic = _bits_to_diacritic(pair)
            if diacritic:
                result.append(ch + diacritic)
            else:
                result.append(ch)
            bit_index += 2
        else:
            result.append(ch)
    
    return ''.join(result)


def _bits_to_diacritic(bits: str) -> Optional[str]:
    """تحويل بتات إلى حرف تشكيل"""
    mapping = {'00': '\u064E', '01': '\u064F', '10': '\u0650', '11': '\u0651'}
    return mapping.get(bits)


def _diacritic_to_bits(diacritic: str) -> Optional[str]:
    """تحويل حرف تشكيل إلى بتات"""
    mapping = {'\u064E': '00', '\u064F': '01', '\u0650': '10', '\u0651': '11'}
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
