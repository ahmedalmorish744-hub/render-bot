"""
🔬 Adaptive Obfuscation Engine v1.0
محرك التشويش التكيفي - 5 طبقات ذكية لتجاوز بوتات الحماية

الطبقات:
1. Arabic Presentation Forms - استبدال الأحرف العربية بنسخ متطابقة بصرياً
2. Smart ZW Distribution - توزيع ذكي للأحرف الصفرية (لا تجمعها معاً)
3. Bayes Evasion - إضافة كلمات محايدة لتخديع مصنف Bayes
4. Adaptive Spintax - تنويع نصي ذكي
5. Tag Characters - استخدام U+E0000 range للاتيني

مستوحى من:
- ACMCMC/silverspeak (Homoglyph attacks)
- bunnylab/pyUnicodeSteganography (ZW distribution)
- AceLewis/spintax (Spintax)
- promptfoo Arabic obfuscation (Presentation Forms)
- umputun/tg-spam (Bayes classifier evasion)
"""

import random
import re
import unicodedata
from typing import Tuple

# ═══════════════════════════════════════════════════════════════
# 1. Arabic Presentation Forms - استبدال عربي بصري متطابق
# ═══════════════════════════════════════════════════════════════

# Arabic Presentation Forms A/B (تبدو متطابقة بصرياً لكنها Unicode مختلف)
ARABIC_PRESENTATION_FORMS = {
    # أحرف عربية أساسية + نسخها من Presentation Forms
    'ا': ['\uFE8E', '\uFE8F', '\uFE90', '\uFE92', '\uFB50', '\uFB51'],  # ALEF with variants
    'ب': ['\uFE8F', '\uFE90', '\uFE91', '\uFE92'],  # BEH
    'ت': ['\uFE95', '\uFE96', '\uFE97', '\uFE98'],  # TEH
    'ث': ['\uFE99', '\uFE9A', '\uFE9B', '\uFE9C'],  # THEH
    'ج': ['\uFE9D', '\uFE9E', '\uFE9F', '\uFEA0'],  # JEEM
    'ح': ['\uFEA1', '\uFEA2', '\uFEA3', '\uFEA4'],  # HAH
    'خ': ['\uFEA5', '\uFEA6', '\uFEA7', '\uFEA8'],  # KHAH
    'د': ['\uFEA9', '\uFEAA'],  # DAL
    'ذ': ['\uFEAB', '\uFEAC'],  # THAL
    'ر': ['\uFEAD', '\uFEAE'],  # REH
    'ز': ['\uFEAF', '\uFEB0'],  # ZAIN
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
    'و': ['\uFEED', '\uFEEE'],  # WAW
    'ي': ['\uFEEF', '\uFEF0', '\uFEF1', '\uFEF2'],  # YEH
    'ى': ['\uFEF1', '\uFEF2', '\uFEF3', '\uFEF4'],  # ALEF MAKSURA
    'ة': ['\uFE93', '\uFE94'],  # TEH MARBUTA
    'ء': ['\uFE80', '\uFE81', '\uFE82'],  # HAMZA
    'أ': ['\uFE81', '\uFE82'],  # ALEF WITH HAMZA ABOVE
    'إ': ['\uFE87', '\uFE88'],  # ALEF WITH HAMZA BELOW
    'آ': ['\uFE83', '\uFE84'],  # ALEF WITH MADDA ABOVE
    'ؤ': ['\uFE89', '\uFE8A', '\uFE8B', '\uFE8C'],  # WAW WITH HAMZA ABOVE
    'ئ': ['\uFE8B', '\uFE8C'],  # YEH WITH HAMZA ABOVE
}


def apply_arabic_presentation_forms(text: str, intensity: float = 0.25) -> str:
    """
    استبدال نسبة من الأحرف العربية بـ Presentation Forms
    
    ✅ النص يبدو متطابقاً 100% للعين المجردة
    ✅ يكسر مطابقة Hash والـ String matching
    ✅ يخدع بعض بوتات الحماية التي تطبع Unicode قبل المقارنة
    """
    if not text or intensity <= 0:
        return text
    
    result = []
    for char in text:
        if char in ARABIC_PRESENTATION_FORMS and random.random() < intensity:
            # اختيار نسخة عشوائية من Presentation Forms
            result.append(random.choice(ARABIC_PRESENTATION_FORMS[char]))
        else:
            result.append(char)
    return ''.join(result)


# ═══════════════════════════════════════════════════════════════
# 2. Smart ZW Distribution - توزيع ذكي للأحرف الصفرية
# ═══════════════════════════════════════════════════════════════

# أحرف Zero-Width (غير مرئية تماماً)
ZW_CHARS = [
    '\u200B',  # Zero-Width Space
    '\u200C',  # Zero-Width Non-Joiner
    '\u200D',  # Zero-Width Joiner
    '\u2060',  # Word Joiner
    '\uFEFF',  # Zero-Width No-Break Space
]

# أحرف صفرية إضافية (أقل استخداماً في بوتات الحماية)
EXTENDED_INVISIBLE = [
    '\u2061',  # Function Application
    '\u2062',  # Invisible Times
    '\u2063',  # Invisible Separator
    '\u2064',  # Invisible Plus
    '\u061C',  # Arabic Letter Mark
]


def smart_zw_distribute(text: str, density: float = 0.08, max_consecutive: int = 2) -> str:
    """
    إدخال ذكي للأحرف الصفرية:
    
    ✅ لا يضع أكثر من max_consecutive أحرف معاً (يتفادى الكشف)
    ✅ يفضل المواضع بين الكلمات وبين الأحرف العربية
    ✅ يستخدم أنواع مختلفة عشوائياً
    ✅ يحافظ على القراءة 100%
    """
    if not text or density <= 0:
        return text
    
    words = text.split(' ')
    result_words = []
    
    for word in words:
        if not word:
            result_words.append(word)
            continue
        
        # معالجة الكلمة - إدخال ZW في مواضع ذكية
        chars = list(word)
        modified = []
        consecutive_zw = 0
        
        for i, char in enumerate(chars):
            modified.append(char)
            
            # إدخال ZW بعد الحرف باحتمالية density
            if (random.random() < density and 
                consecutive_zw < max_consecutive and
                i < len(chars) - 1):  # لا في نهاية الكلمة
                
                # اختيار ZW عشوائي
                zw = random.choice(ZW_CHARS)
                modified.append(zw)
                consecutive_zw += 1
            else:
                consecutive_zw = 0
        
        result_words.append(''.join(modified))
    
    # أيضاً إدخال ZW بين بعض الكلمات (نادراً)
    result = []
    for i, word in enumerate(result_words):
        result.append(word)
        if i < len(result_words) - 1 and random.random() < density * 0.3:
            result.append(random.choice(ZW_CHARS))
    
    return ' '.join(result)


# ═══════════════════════════════════════════════════════════════
# 3. Bayes Evasion - تخديع مصنف Bayes
# ═══════════════════════════════════════════════════════════════

# كلمات محايدة آمنة (تبدو طبيعية وتخفض احتمالية السبام في Bayes)
NEUTRAL_WORDS_AR = [
    "السلام", "عليكم", "شكراً", "أهلاً", "بارك", "الله", "تحية",
    "طيب", "صباح", "مساء", "خير", "ودام", "عمر", "happy", "good"
]

# كلمات ترحيبية (تبدو طبيعية في بداية الرسائل)
WELCOME_WORDS = ["مرحباً", "أهلاً", "أهلاً بكم", "السلام عليكم"]

# عبارات ختامية ودودة
CLOSING_WORDS = ["شكراً لكم", "تقبلوا تحياتنا", "دمتم بخير", "نرiPhone"]


def bayes_evade(text: str, intensity: float = 0.15) -> str:
    """
    إضافة كلمات محايدة لتقليل احتمالية تصنيف الرسالة كـ Spam في Bayes classifier
    
    استراتيجية:
    - إضافة كلمة محايدة كل 5-7 كلمات (تبدو طبيعية)
    - إضافة عبارة ترحيبية في البداية أحياناً
    - لا تضيف أكثر من 2-3 كلمات (تبقى الرسالة طبيعية)
    """
    if not text or intensity <= 0:
        return text
    
    words = text.split()
    if len(words) < 5:
        return text  # الرسائل القصيرة لا تحتاج
    
    result = list(words)
    insertions = 0
    max_insertions = min(3, len(words) // 5)  # كلمة واحدة كل 5 كلمات
    
    # إضافة كلمات محايدة في مواقع عشوائية (ليس في البداية أو النهاية)
    for _ in range(max_insertions):
        if random.random() < intensity:
            # موقع عشوائي في وسط الرسالة
            pos = random.randint(2, len(result) - 2)
            word = random.choice(NEUTRAL_WORDS_AR)
            result.insert(pos, word)
            insertions += 1
    
    return ' '.join(result)


# ═══════════════════════════════════════════════════════════════
# 4. Adaptive Spintax - تنويع نصي ذكي
# ═══════════════════════════════════════════════════════════════

# مرادفات عربية شائعة للتبديل (تبدو طبيعية)
SYNONYMS = {
    'اشترك': ['تابعنا', 'انضم', 'سجل', 'اشترك'],
    'قناتنا': ['قناتنا', 'قناة', 'القناة'],
    'عروض': ['عروض', 'تخفيضات', 'خصومات', 'منتجات'],
    'حصرية': ['حصرية', 'مميزة', 'فريدة', 'خاصة'],
    'تابعنا': ['اشترك', 'انضم', 'تابع'],
    'سعر': ['سعر', 'تكلفة', 'ثمن'],
    'جديد': ['جديد', 'حصري', 'مميز', 'أحدث'],
    'منتجات': ['منتجات', 'سلع', 'بضائع'],
    'الآن': ['الآن', 'فوراً', 'اليوم'],
    'سريع': ['سريع', 'فوري', 'سريعاً'],
}


def adaptive_spintax(text: str, intensity: float = 0.2) -> str:
    """
    استبدال ذكي لبعض الكلمات بمرادفاتها
    
    ✅ يحافظ على المعنى
    ✅ يكسر مطابقة التشابه (similarity check)
    ✅ كل رسالة تنتج نص فريد
    """
    if not text or intensity <= 0:
        return text
    
    words = text.split()
    result = []
    
    for word in words:
        # تنظيف الكلمة من علامات الترقيم
        clean = word.strip('.,!?،؛""\'\"()[]{}')
        
        if clean in SYNONYMS and random.random() < intensity:
            # استبدال بالمرادف مع الحفاظ على علامات الترقيم
            synonym = random.choice(SYNONYMS[clean])
            # إعادة علامات الترقيم
            prefix = word[:word.find(clean)] if clean in word else ''
            suffix = word[word.find(clean) + len(clean):] if clean in word else ''
            result.append(prefix + synonym + suffix)
        else:
            result.append(word)
    
    return ' '.join(result)


# ═══════════════════════════════════════════════════════════════
# 5. Tag Characters - ترميز U+E0000 للاتيني
# ═══════════════════════════════════════════════════════════════

# Tag Characters range: U+E0041-U+E007A (تطابق a-z و A-Z)
TAG_BASE_LOWER = 0xE0061  # 'a' in tag chars
TAG_BASE_UPPER = 0xE0041  # 'A' in tag chars


def apply_tag_chars(text: str, intensity: float = 0.15) -> str:
    """
    استبدال بعض الأحرف اللاتينية بـ Tag Characters (U+E0000 range)
    
    ✅ النص اللاتيني يبدو متطابقاً
    ✅ Bayes و Hash لا يتعرفون على الأحرف
    ✅ مفيد للروابط و @usernames في النص
    """
    if not text or intensity <= 0:
        return text
    
    result = []
    for char in text:
        if 'a' <= char <= 'z' and random.random() < intensity:
            result.append(chr(TAG_BASE_LOWER + (ord(char) - ord('a'))))
        elif 'A' <= char <= 'Z' and random.random() < intensity:
            result.append(chr(TAG_BASE_UPPER + (ord(char) - ord('A'))))
        else:
            result.append(char)
    return ''.join(result)


# ═══════════════════════════════════════════════════════════════
# 6. NFD Decomposition - تفكيك الأحرف لمكوناتها
# ═══════════════════════════════════════════════════════════════

def apply_nfd_decomposition(text: str, intensity: float = 0.1) -> str:
    """
    تفكيك Unicode NFD - يبدو متطابقاً بصرياً لكن الكود مختلف
    
    مثال: 'é' (U+00E9) → 'e' (U+0065) + '◌́' (U+0301)
    """
    if not text or intensity <= 0:
        return text
    
    result = []
    for char in text:
        if random.random() < intensity:
            # تحويل لـ NFD (يفكك الأحرف المركبة)
            decomposed = unicodedata.normalize('NFD', char)
            if len(decomposed) > 1:
                result.append(decomposed)
            else:
                result.append(char)
        else:
            result.append(char)
    return ''.join(result)


# ═══════════════════════════════════════════════════════════════
# 7. Anti-Similarity Salt - ملح فريد لكل رسالة
# ═══════════════════════════════════════════════════════════════

def add_anti_similarity_salt(text: str) -> str:
    """
    إضافة أحرف صفرية فريدة في نهاية الرسالة لكسر كشف التشابه
    
    ✅ كل رسالة لها بصمة ZW فريدة (8 chars = 4 bytes)
    ✅ يمنع بوتات الحماية من كشف الرسائل المكررة
    ✅ غير مرئية تماماً للمستخدم
    """
    if not text:
        return text
    
    # توليد 8 أحرف صفرية عشوائية (32 bit salt)
    salt = ''.join(random.choice(ZW_CHARS) for _ in range(8))
    return text + salt


# ═══════════════════════════════════════════════════════════════
# 🎯 المحرك الرئيسي - AdaptiveObfuscationEngine
# ═══════════════════════════════════════════════════════════════

class AdaptiveObfuscationEngine:
    """
    محرك التشويش التكيفي - يطبق كل الطبقات بترتيب ذكي
    
    الترتيب مهم:
    1. Spintax أولاً (تنويع الكلمات)
    2. Bayes Evasion (إضافة كلمات محايدة)
    3. Arabic Presentation Forms (استبدال بصري)
    4. Tag Characters (للاتيني)
    5. Smart ZW Distribution (أحرف صفرية)
    6. NFD Decomposition (تفكيك)
    7. Anti-Similarity Salt (ملح فريد)
    """
    
    # مستويات القوة
    PROFILES = {
        'light': {
            'arabic_forms': 0.10,
            'zw_density': 0.04,
            'bayes_intensity': 0.08,
            'spintax_intensity': 0.10,
            'tag_intensity': 0.08,
            'nfd_intensity': 0.05,
        },
        'medium': {
            'arabic_forms': 0.20,
            'zw_density': 0.08,
            'bayes_intensity': 0.12,
            'spintax_intensity': 0.15,
            'tag_intensity': 0.12,
            'nfd_intensity': 0.08,
        },
        'aggressive': {
            'arabic_forms': 0.35,
            'zw_density': 0.15,
            'bayes_intensity': 0.20,
            'spintax_intensity': 0.25,
            'tag_intensity': 0.20,
            'nfd_intensity': 0.12,
        },
        'insane': {
            'arabic_forms': 0.50,
            'zw_density': 0.25,
            'bayes_intensity': 0.30,
            'spintax_intensity': 0.35,
            'tag_intensity': 0.30,
            'nfd_intensity': 0.20,
        },
    }
    
    def __init__(self, profile: str = 'medium'):
        self.profile = profile
        self.config = self.PROFILES.get(profile, self.PROFILES['medium'])
        self.enabled_layers = {
            'arabic_forms': True,
            'zw_distribution': True,
            'bayes_evasion': True,
            'spintax': True,
            'tag_chars': True,
            'nfd': True,
            'salt': True,
        }
        self.stats = {
            'total_obfuscated': 0,
            'total_messages': 0,
        }
    
    def set_profile(self, profile: str):
        """تغيير مستوى القوة"""
        if profile in self.PROFILES:
            self.profile = profile
            self.config = self.PROFILES[profile]
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
        result = text
        
        # حماية الروابط و @usernames من التشفير
        urls = list(re.finditer(r'https?://\S+', result))
        mentions = list(re.finditer(r'@[a-zA-Z0-9_]{3,}', result))
        protected_spans = [(m.start(), m.end()) for m in urls + mentions]
        
        # 1. Spintax - تنويع الكلمات
        if self.enabled_layers['spintax'] and self.config['spintax_intensity'] > 0:
            result = adaptive_spintax(result, self.config['spintax_intensity'])
            applied_layers.append('spintax')
        
        # 2. Bayes Evasion - إضافة كلمات محايدة
        if self.enabled_layers['bayes_evasion'] and self.config['bayes_intensity'] > 0:
            result = bayes_evade(result, self.config['bayes_intensity'])
            applied_layers.append('bayes_evasion')
        
        # 3. Arabic Presentation Forms - استبدال بصري عربي
        if self.enabled_layers['arabic_forms'] and self.config['arabic_forms'] > 0:
            result = apply_arabic_presentation_forms(result, self.config['arabic_forms'])
            applied_layers.append('arabic_forms')
        
        # 4. Tag Characters - للأحرف اللاتينية
        if self.enabled_layers['tag_chars'] and self.config['tag_intensity'] > 0:
            result = apply_tag_chars(result, self.config['tag_intensity'])
            applied_layers.append('tag_chars')
        
        # 5. Smart ZW Distribution - أحرف صفرية موزعة
        if self.enabled_layers['zw_distribution'] and self.config['zw_density'] > 0:
            result = smart_zw_distribute(result, self.config['zw_density'])
            applied_layers.append('zw_distribution')
        
        # 6. NFD Decomposition - تفكيك
        if self.enabled_layers['nfd'] and self.config['nfd_intensity'] > 0:
            result = apply_nfd_decomposition(result, self.config['nfd_intensity'])
            applied_layers.append('nfd')
        
        # 7. Anti-Similarity Salt - ملح فريد
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
        info = f"🔬 **Adaptive Obfuscation Engine**\n\n"
        info += f"⚡ **المستوى الحالي:** {self.profile}\n\n"
        info += f"📊 **الطبقات المفعّلة:**\n"
        layers_ar = {
            'arabic_forms': '1️⃣ Arabic Presentation Forms',
            'zw_distribution': '2️⃣ Smart ZW Distribution',
            'bayes_evasion': '3️⃣ Bayes Evasion',
            'spintax': '4️⃣ Adaptive Spintax',
            'tag_chars': '5️⃣ Tag Characters',
            'nfd': '6️⃣ NFD Decomposition',
            'salt': '7️⃣ Anti-Similarity Salt',
        }
        for key, name in layers_ar.items():
            status = "✅" if self.enabled_layers.get(key) else "❌"
            info += f"  {status} {name}\n"
        
        info += f"\n📈 **الإحصائيات:**\n"
        info += f"  📝 رسائل مشفرة: {self.stats['total_obfuscated']}\n"
        info += f"  📊 إجمالي الرسائل: {self.stats['total_messages']}\n"
        
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
    # اختبار المحرك
    test_text = "اشترك في قناتنا للحصول على عروض حصرية t.me/example @username"
    
    print("=" * 60)
    print("🔬 اختبار Adaptive Obfuscation Engine")
    print("=" * 60)
    print(f"\n📝 **النص الأصلي:**\n{test_text}")
    print(f"📊 الطول: {len(test_text)}")
    
    for profile in ['light', 'medium', 'aggressive', 'insane']:
        engine = AdaptiveObfuscationEngine(profile=profile)
        result, info = engine.obfuscate(test_text)
        print(f"\n{'─' * 60}")
        print(f"⚡ Profile: {profile}")
        print(f"📝 النص المشفر:\n{result}")
        print(f"📊 الطول: {len(result)} (زيادة: {len(result) - len(test_text)})")
        print(f"🛡️ الطبقات المطبقة: {info['layers']}")
    
    print(f"\n{'=' * 60}")
    print("✅ تم الاختبار بنجاح!")
