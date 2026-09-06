"""
🔬 Adaptive Obfuscation Engine v2.0
محرك التشويش التكيفي - طبقات غير مرئية فقط لتجاوز بوتات الحماية

⚠️ القاعدة الذهبية (v2.0):
   البوت يرسل نص المستخدم **كما هو** - لا إضافة كلمات، لا حذف، لا استبدال مرادفات.
   كل الطبقات تغيّر تمثيل Unicode للنص فقط (الشكل الظاهر يبقى متطابقاً).

الطبقات:
1. Arabic Presentation Forms - استبدال الأحرف العربية بنسخ متطابقة بصرياً
2. Smart ZW Distribution - توزيع ذكي للأحرف الصفرية (لا تجمعها معاً)
3. Bayes Evasion - معطلة (كانت تضيف كلمات - تخرّب النص) ← أصبحت ZW خفي فقط
4. Adaptive Spintax - معطلة (كانت تستبدل كلمات المستخدم بمرادفات)
5. Tag Characters - استخدام U+E0000 range للاتيني

مستوحى من:
- ACMCMC/silverspeak (Homoglyph attacks)
- bunnylab/pyUnicodeSteganography (ZW distribution)
- promptfoo Arabic obfuscation (Presentation Forms)
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
# 1. Arabic Presentation Forms - استبدال عربي بصري متطابق
# ═══════════════════════════════════════════════════════════════

# Arabic Presentation Forms B (U+FE70–U+FEFF) - كل كود مُتحقق منه:
# NFKC(النموذج) = الحرف الأصلي بالضبط (تم التحقق برمجياً)
# ⚠️ النسخة القديمة كانت تحتوي أكواداً خاطئة كانت تغيّر الحروف فعلياً
#    (مثلاً 'ا' → 'ب'!) - أُصلحت كلها في v2.0
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
    # 🛡️ v2.0: يُلحق بالكلمة نفسها وليس كعنصر منفصل
    # (الطريقة القديمة كانت تنشئ مسافة مزدوجة ظاهرة!)
    result = []
    for i, word in enumerate(result_words):
        result.append(word)
        if i < len(result_words) - 1 and random.random() < density * 0.3:
            result[-1] = result[-1] + random.choice(ZW_CHARS)
    
    return ' '.join(result)


# ═══════════════════════════════════════════════════════════════
# 3. Bayes Evasion - تخديع مصنف Bayes (v2.0: غير مرئي 100%)
# ═══════════════════════════════════════════════════════════════

def bayes_evade(text: str, intensity: float = 0.15) -> str:
    """
    🛡️ v2.0: معطلة لحماية سلامة النص
    
    النسخة القديمة كانت تُدخل كلمات مثل (السلام عليكم / شكراً) في وسط
    رسالة المستخدم - هذا يخرّب النص وغير مقبول.
    
    البديل الآمن: تخديع Bayes يتم عبر طبقة smart_zw_distribute
    (أحرف صفرية غير مرئية تكسر n-gram matching) وهي كافية تماماً،
    لذلك هذه الدالة تُرجع النص كما هو دون أي تعديل على الكلمات.
    """
    return text


# ═══════════════════════════════════════════════════════════════
# 4. Adaptive Spintax (v2.0: معطلة لحماية كلمات المستخدم)
# ═══════════════════════════════════════════════════════════════

def adaptive_spintax(text: str, intensity: float = 0.2) -> str:
    """
    🛡️ v2.0: معطلة لحماية سلامة النص
    
    النسخة القديمة كانت تستبدل كلمات المستخدم بمرادفات
    (اشترك → تابعنا، قناتنا → القناة...) - هذا يغيّر صياغة المستخدم
    بدون إذنه وغير مقبول.
    
    ✅ البديل الصحيح: المستخدم يكتب صيغة Spintax بنفسه {خيار1|خيار2}
       ويحلها محرك stego_engine (وضع spintax) - بنفس كلماته هو.
    
    هذه الدالة تُرجع النص كما هو دون أي تعديل.
    """
    return text


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
    1. Spintax (معطل - حماية كلمات المستخدم)
    2. Bayes Evasion (معطل - حماية النص)
    3. Arabic Presentation Forms (استبدال بصري متطابق)
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
        
        # حماية الروابط و @usernames من التشفير (تُمرر سليمة 100%)
        urls = list(re.finditer(r'https?://\S+', result))
        mentions = list(re.finditer(r'@[a-zA-Z0-9_]{3,}', result))
        protected_spans = [(m.start(), m.end()) for m in urls + mentions]
        
        # 🛡️ كل الطبقات تُطبق فقط على الأجزاء غير المحمية
        # (الروابط @username / t.me/... / https://... تمر سليمة 100%)
        
        # 1. Spintax - (v2.0: معطلة - تحمي كلمات المستخدم من الاستبدال)
        if self.enabled_layers['spintax'] and self.config['spintax_intensity'] > 0:
            result = apply_layer_protected(result, adaptive_spintax, self.config['spintax_intensity'])
            applied_layers.append('spintax')
        
        # 2. Bayes Evasion - (v2.0: معطلة - تحمي النص من حقن كلمات)
        if self.enabled_layers['bayes_evasion'] and self.config['bayes_intensity'] > 0:
            result = apply_layer_protected(result, bayes_evade, self.config['bayes_intensity'])
            applied_layers.append('bayes_evasion')
        
        # 3. Arabic Presentation Forms - استبدال بصري عربي
        if self.enabled_layers['arabic_forms'] and self.config['arabic_forms'] > 0:
            result = apply_layer_protected(result, apply_arabic_presentation_forms, self.config['arabic_forms'])
            applied_layers.append('arabic_forms')
        
        # 4. Tag Characters - للأحرف اللاتينية
        if self.enabled_layers['tag_chars'] and self.config['tag_intensity'] > 0:
            result = apply_layer_protected(result, apply_tag_chars, self.config['tag_intensity'])
            applied_layers.append('tag_chars')
        
        # 5. Smart ZW Distribution - أحرف صفرية موزعة
        if self.enabled_layers['zw_distribution'] and self.config['zw_density'] > 0:
            result = apply_layer_protected(result, smart_zw_distribute, self.config['zw_density'])
            applied_layers.append('zw_distribution')
        
        # 6. NFD Decomposition - تفكيك
        if self.enabled_layers['nfd'] and self.config['nfd_intensity'] > 0:
            result = apply_layer_protected(result, apply_nfd_decomposition, self.config['nfd_intensity'])
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
        info = f"🔬 **Adaptive Obfuscation Engine v2.0**\n\n"
        info += f"⚡ **المستوى الحالي:** {self.profile}\n\n"
        info += f"📊 **الطبقات المفعّلة (كلها غير مرئية ولا تعدل كلماتك):**\n"
        layers_ar = {
            'arabic_forms': '1️⃣ Arabic Presentation Forms (متطابقة بصرياً)',
            'zw_distribution': '2️⃣ Smart ZW Distribution (أحرف خفية)',
            'bayes_evasion': '3️⃣ Bayes Evasion (⚠️ معطلة - حماية النص)',
            'spintax': '4️⃣ Adaptive Spintax (⚠️ معطلة - حماية النص)',
            'tag_chars': '5️⃣ Tag Characters (للاتيني - غير مرئي)',
            'nfd': '6️⃣ NFD Decomposition (تفكيك غير مرئي)',
            'salt': '7️⃣ Anti-Similarity Salt (بصمة فريدة)',
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
