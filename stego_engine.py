"""
🫥 Stego Engine v1.0 - محرك الإخفاء المتقدم
=============================================
نظام إخفاء رسائل إعلانية داخل نصوص تبدو عادية تماماً

المميزات:
1. Spintax متداخل - {خيار1|خيار2|{خيار3|خيار4}}
2. Zero-Width Steganography - إخفاء نص داخل نص غلاف
3. Arabic Diacritic Steganography - إخفاء رسالة إنجليزية داخل تشكيل عربي
4. نظام أوضاع موحد - normal / spintax / stego / diacritic / spintax+stego

القاعدة الذهبية:
✅ النص الناتج يظهر طبيعياً ومقروءاً 100% للأعضاء
✅ بوتات الحماية لا تستطيع ربط الرسائل ببعضها (كل رسالة بصمة مختلفة)
✅ الروابط والمعرفات تبقى واضحة وقابلة للنقر

المصادر المستوحاة:
- mabutaha/diasteg (الإخفاء بالتشكيل العربي)
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


def zero_width_hide(secret: str, cover: str = "") -> str:
    """
    إخفاء نص سري داخل نص غلاف باستخدام أحرف العرض الصفري
    
    Args:
        secret: النص السري المراد إخفاؤه (الرسالة الإعلانية + الرابط)
        cover: نص الغلاف الظاهر (إذا فاضي، يُولد تلقائياً)
    
    Returns:
        نص الغلاف + الأحرف الصفرية المحتوية على السر
    
    مثال:
        zero_width_hide("اشترك t.me/mychannel", "مرحباً بالجميع 🌟")
        → "مرحباً بالجميع 🌟‌‍‌..." (يبدو كنص الغلاف فقط)
    """
    if not secret:
        return cover
    
    # توليد نص غلاف افتراضي إذا لم يُحدد
    if not cover:
        covers = [
            "مرحباً بكم 🌟 نتمنى لكم يوماً سعيداً",
            "سلام عليكم ورحمة الله وبركاته 🌸",
            "مساء الخير أصدقائي 🌙",
            "صباح الخير 🌞 أتمنى لكم يوم رائعاً",
            "شكراً لكم على ثقتكم الغالية 💙",
            "نتمنى لكم دوام التوفيق والنجاح 🎉",
        ]
        cover = random.choice(covers)
    
    # تحويل السر إلى بتات
    bits = _text_to_bits(secret)
    
    # تحويل كل بتين إلى حرف صفري واحد
    zw_encoded = ''
    for i in range(0, len(bits), 2):
        pair = bits[i:i+2].ljust(2, '0')
        index = int(pair, 2)
        zw_encoded += ZW_CHARS[index]
    
    # إدراج الأحرف الصفرية بعد أول كلمة من الغلاف (تبدو طبيعية)
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
    إخفاء رسالة إنجليزية (رابط أو كود) داخل نص عربي مشكول
    
    Args:
        secret: الرسالة السرية (بالإنجليزية - مثل رابط t.me)
        cover: النص العربي الظاهر (سيُشكَّل تلقائياً)
    
    Returns:
        نص عربي مشكول طبيعياً + الرسالة السرية مخفية في التشكيل
    
    مثال:
        diacritic_hide("t.me/mychannel", "القناة الرسمية للمحتوى الحصري")
        → "الْقَنَاةُ الرَّسْمِيَّةُ..." (يبدو نصاً عربياً مشكولاً عادياً)
    """
    if not secret:
        return cover
    
    # توليد نص عربي غلاف إذا لم يُحدد
    if not cover:
        covers = [
            "السلام عليكم ورحمة الله وبركاته أهلاً بكم في قناتنا الرسمية نتمنى لكم طيباً",
            "مرحباً بكم أصدقائي الأعزاء نوفر لكم أفضل المحتوى الحصري بجودة عالية دائماً",
            "أهلاً وسهلاً بكم في فضائنا نحرص على تقديم كل جديد ومفيد لكم دوماً بحب",
            "يسعدنا انضمامكم إلينا سنتواصل معكم بأهم الأخبار والعروض المميزة قريباً",
            "نرحب بجميع الأعضاء الكرام نتمنى لكم الفائدة والاستفادة القصوى دائماً",
        ]
        cover = random.choice(covers)
    
    # تحويل السر إلى بتات
    bits = _english_to_diacritic_bits(secret)
    needed_chars = (len(bits) + 1) // 2  # كل 2 بت = حرف مشكول
    
    # 🔄 توسيع الغلاف تلقائياً إذا كان قصيراً
    arabic_letters_count = sum(1 for ch in cover if '\u0600' <= ch <= '\u06FF')
    if arabic_letters_count < needed_chars:
        extra_sentences = [
            " فمعكم ستجدون كل ما هو جديد ومفيد ومميز فلا تفوتوا الفرصة السانحة",
            " ونؤكد لكم أننا نقدم المحتوى بجودة عالية ومجانية تماماً للأبد بإذن الله",
            " كما أننا نحدث القناة يومياً بأهم المعلومات والعروض الحصرية المميزة",
            " ونطمح لأن نكون الخيار الأول لكم في كل المجالات المتخصصة والمهمة",
            " شكراً لثقتكم الغالية ونسعد بتفاعلكم الدائم مع محتوانا المتواضع",
            " ولا تنسوا مشاركة القناة مع أصدقائكم وأحبائكم لتحصلوا على المزيد",
        ]
        idx = 0
        while arabic_letters_count < needed_chars and idx < len(extra_sentences):
            cover += extra_sentences[idx]
            arabic_letters_count += sum(1 for ch in extra_sentences[idx] if '\u0600' <= ch <= '\u06FF')
            idx += 1
    
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

# الأوضاع المدعومة
SEND_MODES = {
    'normal': {
        'name': 'نص عادي',
        'icon': '📝',
        'description': 'إرسال النص كما هو بدون أي معالجة (آمن تماماً - لا إخفاء)',
    },
    'spintax': {
        'name': 'Spintax - تنويع لغوي',
        'icon': '🔄',
        'description': 'يحل صيغة {خيار1|خيار2} ويختار عشوائياً - كل رسالة فريدة',
    },
    'stego': {
        'name': 'Zero-Width Stego',
        'icon': '🫥',
        'description': 'يخفي الرسالة داخل نص غلاف عادي - النص المخفي يظهر عند النسخ',
    },
    'diacritic': {
        'name': 'إخفاء بالتشكيل العربي',
        'icon': '🕌',
        'description': 'يخفي رسالة إنجليزية داخل تشكيل نص عربي - يبدو نصاً مشكولاً عادياً',
    },
    'spintax+stego': {
        'name': 'Spintax + Stego (طبقتان)',
        'icon': '🧬',
        'description': 'يحل Spintax أولاً ثم يخفي الناتج في نص غلاف - أقوى حماية',
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
            'sent_diacritic': 0,
            'sent_spintax_stego': 0,
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
        
        Args:
            content: النص الأصلي (قد يحتوي spintax)
            mode: الوضع (إذا لم يُحدد، يستخدم الوضع الحالي)
            cover_text: نص غلاف اختياري لـ stego/diacritic
        
        Returns:
            (النص النهائي, معلومات المعالجة)
        """
        use_mode = mode or self.mode
        info = {'mode': use_mode, 'original_length': len(content)}
        
        if not content:
            return content, info
        
        # تطبيق الوضع
        if use_mode == 'normal':
            result = content
            self.stats['sent_normal'] += 1
            
        elif use_mode == 'spintax':
            result = parse_spintax_advanced(content) if has_spintax(content) else content
            self.stats['sent_spintax'] += 1
            
        elif use_mode == 'stego':
            # السر = النص الأصلي بعد حل spintax إن وجد
            secret = parse_spintax_advanced(content) if has_spintax(content) else content
            result = zero_width_hide(secret, cover_text or "")
            self.stats['sent_stego'] += 1
            
        elif use_mode == 'diacritic':
            # طبقة 1: حل Spintax أولاً (إن وجد)
            clean = parse_spintax_advanced(content) if has_spintax(content) else content
            # طبقة 2: استخراج الرابط/النص الإنجليزي
            secret = self._extract_english_part(clean)
            if secret:
                # فصل النص العربي عن الإنجليزي (يُستخدم كغلاف)
                arabic_part = re.sub(r'(https?://\S+|t\.me/\S+|@[a-zA-Z0-9_]+)', '', clean).strip()
                # إزالة أقواس spintax المتبقية
                arabic_part = arabic_part.replace('{', '').replace('}', '').replace('|', ' ')
                result = diacritic_hide(secret, arabic_part if arabic_part else "")
            else:
                # لا يوجد نص إنجليزي - نرسل النص العادي بعد حل spintax
                result = clean
            self.stats['sent_diacritic'] += 1
            
        elif use_mode == 'spintax+stego':
            # طبقة 1: حل Spintax
            spun = parse_spintax_advanced(content) if has_spintax(content) else content
            # طبقة 2: إخفاء الناتج
            result = zero_width_hide(spun, cover_text or "")
            self.stats['sent_spintax_stego'] += 1
        else:
            result = content
        
        info['final_length'] = len(result)
        info['hidden'] = use_mode in ('stego', 'diacritic', 'spintax+stego')
        
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
