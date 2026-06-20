# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════
  FancyTextEngine v1.0
  محرك الأنماط النصية الخارق - 26 نمط مستوحى من FSymbols
═══════════════════════════════════════════════════════════════

محرك تحويل النصوص إلى 26 نمط بصري مختلف، مصمم خصيصاً
لتجاوز بوتات الحماية (anti-spam bots) على تيليجرام.

المصادر المستوحاة منها:
- FSymbols: https://fsymbols.com/generators/zalgo-text/
- LingoJam: https://lingojam.com/ZalgoTextGenerator
- YayText: https://yaytext.com/zalgo/
- Messletters: https://www.messletters.com/en/zalgo-text/
- text_unicoder: https://github.com/gdraheim/text_unicoder
- fancy-fonts-generator: https://github.com/waterrmalann/fancy-fonts-generator
- telegram-fancy-fonts-bot: https://github.com/waterrmalann/telegram-fancy-fonts-bot
- Unicode Combining Diacritical Marks: https://www.unicode.org/charts/PDF/U0300.pdf

المبادئ:
1. كل نمط يحول النص إلى شكل بصري مختلف تماماً
2. النص يبقى مقروءاً للمستخدم البشري
3. بوتات الحماية لا تستطيع مطابقة النص المحول (يكسر pattern matching)
4. كل نمط مستقل ويمكن اختياره من القائمة
5. يدعم العربية والإنجليزية والأرقام والروابط

الأنماط الـ26:
  ── تشكيل فوق/تحت الحروف (Combining Marks) ──
  1.  Strikethrough       - خط في منتصف النص (U+0336)
  2.  Long Strikethrough  - خط طويل (U+0335)
  3.  Underline           - خط سفلي (U+0332)
  4.  Double Underline    - خط سفلي مزدوج (U+0333)
  5.  Overline            - خط علوي (U+0305)
  6.  Double Overline     - خط علوي مزدوج (U+033F)
  7.  Slash Through       - شريط مائل (U+0337/U+0338)
  8.  X Above             - X فوق الحرف (U+033D)
  9.  Boxed Text          - نص في صندوق (U+20E3)
  10. Circled Text        - نص في دائرة (U+20DD)
  11. Squared Text        - نص في مربع (U+20DE)
  12. Bubble Text         - نص فقاعي (U+20DD)

  ── استبدال كامل للحروف (Letter Substitution) ──
  13. Small Caps          - أحرف صغيرة كبيرة
  14. Superscript         - أحرف علوية
  15. Subscript           - أحرف سفلية
  16. Monospace           - أحرف أحادية المسافة
  17. Fraktur             - خط قوطي
  18. Double Struck       - خط مزدوج الحواف
  19. Script              - خط سكربت
  20. Bold Script         - سكربت عريض
  21. Fullwidth           - أحرف عريضة كاملة

  ─ـ تحويلات متقدمة (Advanced Transforms) ──
  22. Mirrored Text       - نص معكوس أفقي
  23. Upside Down         - نص مقلوب رأسياً
  24. Vaporwave           - نص فابرويف (fullwidth + spacing)
  25. Flip Text           - نص مقلوب (reverse + upside-down)
  26. Glitch/Zalgo        - نص معطب (combining marks stacking)
"""

import random
import re


# ════════════════════════════════════════════════════════════════
#  Combining Diacritical Marks (U+0300 - U+036F)
#  المصدر: https://www.unicode.org/charts/PDF/U0300.pdf
# ════════════════════════════════════════════════════════════════

# Strikethrough
STRIKETHROUGH       = '\u0336'  # COMBINING LONG STROKE OVERLAY (ــ)
LONG_STRIKETHROUGH  = '\u0335'  # COMBINING SHORT STROKE OVERLAY

# Underline
UNDERLINE           = '\u0332'  # COMBINING LOW LINE (̲)
DOUBLE_UNDERLINE    = '\u0333'  # COMBINING DOUBLE LOW LINE (̳)

# Overline
OVERLINE            = '\u0305'  # COMBINING OVERLINE (̅)
DOUBLE_OVERLINE     = '\u033F'  # COMBINING DOUBLE OVERLINE (̿)

# Slash Through
SLASH_THROUGH       = '\u0338'  # COMBINING LONG SOLIDUS OVERLAY (̸)
SHORT_SLASH         = '\u0337'  # COMBINING SHORT SOLIDUS OVERLAY

# X Above / Crossed
X_ABOVE             = '\u033D'  # COMBINING X ABOVE (̽)

# Enclosing marks (تلف الحرف بإحاطته)
ENCLOSING_KEYCAP    = '\u20E3'  # COMBINING ENCLOSING KEYCAP
ENCLOSING_CIRCLE    = '\u20DD'  # COMBINING ENCLOSING CIRCLE
ENCLOSING_SQUARE    = '\u20DE'  # COMBINING ENCLOSING SQUARE
ENCLOSING_DIAMOND   = '\u20DF'  # COMBINING ENCLOSING DIAMOND
ENCLOSING_SCREEN    = '\u20E2'  # COMBINING ENCLOSING SCREEN


# ════════════════════════════════════════════════════════════════
#  Math Alphanumeric Symbols (U+1D400-U+1D7FF)
# ════════════════════════════════════════════════════════════════

# Small Caps
SMALL_CAPS = {
    'a': '\u1D00', 'b': '\u0299', 'c': '\u1D04', 'd': '\u1D05',
    'e': '\u1D07', 'f': '\u1D08', 'g': '\u0262', 'h': '\u029C',
    'i': '\u026A', 'j': '\u1D0A', 'k': '\u1D0B', 'l': '\u029F',
    'm': '\u1D0D', 'n': '\u0274', 'o': '\u1D0F', 'p': '\u1D18',
    'q': 'Q', 'r': '\u0280', 's': '\uA731', 't': '\u1D1B',
    'u': '\u1D1C', 'v': '\u1D20', 'w': '\u1D21', 'x': 'X',
    'y': '\u028F', 'z': '\u1D22',
}

# Superscript (أحرف علوية)
SUPERSCRIPT = {
    'a': '\u1D43', 'b': '\u1D47', 'c': '\u1D9C', 'd': '\u1D48',
    'e': '\u1D49', 'f': '\u1DA0', 'g': '\u1D4D', 'h': '\u02B0',
    'i': '\u2071', 'j': '\u02B2', 'k': '\u1D4F', 'l': '\u02E1',
    'm': '\u1D50', 'n': '\u207F', 'o': '\u1D52', 'p': '\u1D56',
    'q': 'Q', 'r': '\u02B3', 's': '\u02E2', 't': '\u1D57',
    'u': '\u1D58', 'v': '\u1D5B', 'w': '\u02B7', 'x': '\u02E3',
    'y': '\u02B8', 'z': '\u1DBB',
    '0': '\u2070', '1': '\u00B9', '2': '\u00B2', '3': '\u00B3',
    '4': '\u2074', '5': '\u2075', '6': '\u2076', '7': '\u2077',
    '8': '\u2078', '9': '\u2079',
    '+': '\u207A', '-': '\u207B', '=': '\u207C', '(': '\u207D',
    ')': '\u207E',
}

# Subscript (أحرف سفلية)
SUBSCRIPT = {
    'a': '\u2090', 'b': 'b', 'c': 'c', 'd': 'd',
    'e': '\u2091', 'f': 'f', 'g': '\u2095', 'h': '\u2096',
    'i': '\u1D62', 'j': '\u2C7C', 'k': '\u2096', 'l': '\u2097',
    'm': '\u2098', 'n': '\u2099', 'o': '\u2092', 'p': '\u209A',
    'q': 'q', 'r': '\u1D63', 's': '\u209B', 't': '\u209C',
    'u': '\u1D64', 'v': '\u1D65', 'w': 'w', 'x': '\u2093',
    'y': 'y', 'z': 'z',
    '0': '\u2080', '1': '\u2081', '2': '\u2082', '3': '\u2083',
    '4': '\u2084', '5': '\u2085', '6': '\u2086', '7': '\u2087',
    '8': '\u2088', '9': '\u2089',
    '+': '\u208A', '-': '\u208B', '=': '\u208C', '(': '\u208D',
    ')': '\u208E',
}

# Monospace (أحرف أحادية المسافة)
MONOSPACE = {
    'a': '\U0001D68A', 'b': '\U0001D68B', 'c': '\U0001D68C', 'd': '\U0001D68D',
    'e': '\U0001D68E', 'f': '\U0001D68F', 'g': '\U0001D690', 'h': '\U0001D691',
    'i': '\U0001D692', 'j': '\U0001D693', 'k': '\U0001D694', 'l': '\U0001D695',
    'm': '\U0001D696', 'n': '\U0001D697', 'o': '\U0001D698', 'p': '\U0001D699',
    'q': '\U0001D69A', 'r': '\U0001D69B', 's': '\U0001D69C', 't': '\U0001D69D',
    'u': '\U0001D69E', 'v': '\U0001D69F', 'w': '\U0001D6A0', 'x': '\U0001D6A1',
    'y': '\U0001D6A2', 'z': '\U0001D6A3',
    'A': '\U0001D670', 'B': '\U0001D671', 'C': '\U0001D672', 'D': '\U0001D673',
    'E': '\U0001D674', 'F': '\U0001D675', 'G': '\U0001D676', 'H': '\U0001D677',
    'I': '\U0001D678', 'J': '\U0001D679', 'K': '\U0001D67A', 'L': '\U0001D67B',
    'M': '\U0001D67C', 'N': '\U0001D67D', 'O': '\U0001D67E', 'P': '\U0001D67F',
    'Q': '\U0001D680', 'R': '\U0001D681', 'S': '\U0001D682', 'T': '\U0001D683',
    'U': '\U0001D684', 'V': '\U0001D685', 'W': '\U0001D686', 'X': '\U0001D687',
    'Y': '\U0001D688', 'Z': '\U0001D689',
    '0': '\U0001D7F6', '1': '\U0001D7F7', '2': '\U0001D7F8', '3': '\U0001D7F9',
    '4': '\U0001D7FA', '5': '\U0001D7FB', '6': '\U0001D7FC', '7': '\U0001D7FD',
    '8': '\U0001D7FE', '9': '\U0001D7FF',
}

# Fraktur (خط قوطي)
FRAKTUR = {
    'a': '\U0001D51E', 'b': '\U0001D51F', 'c': '\U0001D520', 'd': '\U0001D521',
    'e': '\U0001D522', 'f': '\U0001D523', 'g': '\U0001D524', 'h': '\U0001D525',
    'i': '\U0001D526', 'j': '\U0001D527', 'k': '\U0001D528', 'l': '\U0001D529',
    'm': '\U0001D52A', 'n': '\U0001D52B', 'o': '\U0001D52C', 'p': '\U0001D52D',
    'q': '\U0001D52E', 'r': '\U0001D52F', 's': '\U0001D530', 't': '\U0001D531',
    'u': '\U0001D532', 'v': '\U0001D533', 'w': '\U0001D534', 'x': '\U0001D535',
    'y': '\U0001D536', 'z': '\U0001D537',
    'A': '\U0001D504', 'B': '\U0001D505', 'C': '\u212D',     'D': '\U0001D507',
    'E': '\U0001D508', 'F': '\U0001D509', 'G': '\U0001D50A', 'H': '\u210C',
    'I': '\u2111',     'J': '\U0001D50D', 'K': '\U0001D50E', 'L': '\U0001D50F',
    'M': '\U0001D510', 'N': '\U0001D511', 'O': '\U0001D512', 'P': '\U0001D513',
    'Q': '\U0001D514', 'R': '\u211C',     'S': '\U0001D516', 'T': '\U0001D517',
    'U': '\U0001D518', 'V': '\U0001D519', 'W': '\U0001D51A', 'X': '\U0001D51B',
    'Y': '\U0001D51C', 'Z': '\u2128',
}

# Double Struck (مزدوج الحواف)
DOUBLE_STRUCK = {
    'a': '\U0001D552', 'b': '\U0001D553', 'c': '\U0001D554', 'd': '\U0001D555',
    'e': '\U0001D556', 'f': '\U0001D557', 'g': '\U0001D558', 'h': '\U0001D559',
    'i': '\U0001D55A', 'j': '\U0001D55B', 'k': '\U0001D55C', 'l': '\U0001D55D',
    'm': '\U0001D55E', 'n': '\U0001D55F', 'o': '\U0001D560', 'p': '\U0001D561',
    'q': '\U0001D562', 'r': '\U0001D563', 's': '\U0001D564', 't': '\U0001D565',
    'u': '\U0001D566', 'v': '\U0001D567', 'w': '\U0001D568', 'x': '\U0001D569',
    'y': '\U0001D56A', 'z': '\U0001D56B',
    'A': '\U0001D538', 'B': '\U0001D539', 'C': '\u2102',     'D': '\U0001D53B',
    'E': '\U0001D53C', 'F': '\U0001D53D', 'G': '\U0001D53E', 'H': '\u210D',
    'I': '\u2145',     'J': '\U0001D541', 'K': '\U0001D542', 'L': '\U0001D543',
    'M': '\U0001D544', 'N': '\u2115',     'O': '\U0001D546', 'P': '\u2119',
    'Q': '\u211A',     'R': '\u211D',     'S': '\U0001D54A', 'T': '\U0001D54B',
    'U': '\U0001D54C', 'V': '\U0001D54D', 'W': '\U0001D54E', 'X': '\U0001D54F',
    'Y': '\U0001D550', 'Z': '\u2124',
    '0': '\U0001D7D8', '1': '\U0001D7D9', '2': '\U0001D7DA', '3': '\U0001D7DB',
    '4': '\U0001D7DC', '5': '\U0001D7DD', '6': '\U0001D7DE', '7': '\U0001D7DF',
    '8': '\U0001D7E0', '9': '\U0001D7E1',
}

# Script (سكربت)
SCRIPT = {
    'a': '\U0001D4B6', 'b': '\U0001D4B7', 'c': '\U0001D4B8', 'd': '\U0001D4B9',
    'e': '\U0001D4BA', 'f': '\U0001D4BB', 'g': '\U0001D4BC', 'h': '\U0001D4BD',
    'i': '\U0001D4BE', 'j': '\U0001D4BF', 'k': '\U0001D4C0', 'l': '\U0001D4C1',
    'm': '\U0001D4C2', 'n': '\U0001D4C3', 'o': '\U0001D4C4', 'p': '\U0001D4C5',
    'q': '\U0001D4C6', 'r': '\U0001D4C7', 's': '\U0001D4C8', 't': '\U0001D4C9',
    'u': '\U0001D4CA', 'v': '\U0001D4CB', 'w': '\U0001D4CC', 'x': '\U0001D4CD',
    'y': '\U0001D4CE', 'z': '\U0001D4CF',
    'A': '\U0001D49C', 'B': '\u212C',     'C': '\U0001D49E', 'D': '\U0001D49F',
    'E': '\u2130',     'F': '\u2131',     'G': '\U0001D4A2', 'H': '\u210B',
    'I': '\u2110',     'J': '\U0001D4A5', 'K': '\U0001D4A6', 'L': '\u2112',
    'M': '\u2133',     'N': '\U0001D4A9', 'O': '\u2134',     'P': '\U0001D4AB',
    'Q': '\U0001D4AC', 'R': '\u211B',     'S': '\U0001D4AE', 'T': '\U0001D4AF',
    'U': '\U0001D4B0', 'V': '\U0001D4B1', 'W': '\U0001D4B2', 'X': '\U0001D4B3',
    'Y': '\U0001D4B4', 'Z': '\U0001D4B5',
}

# Bold Script (سكربت عريض) - الأحرف الكبيرة U+1D4D0 إلى U+1D4E9
# الصغيرة: U+1D4EA إلى U+1D503
BOLD_SCRIPT = {
    'a': '\U0001D4EA', 'b': '\U0001D4EB', 'c': '\U0001D4EC', 'd': '\U0001D4ED',
    'e': '\U0001D4EE', 'f': '\U0001D4EF', 'g': '\U0001D4F0', 'h': '\U0001D4F1',
    'i': '\U0001D4F2', 'j': '\U0001D4F3', 'k': '\U0001D4F4', 'l': '\U0001D4F5',
    'm': '\U0001D4F6', 'n': '\U0001D4F7', 'o': '\U0001D4F8', 'p': '\U0001D4F9',
    'q': '\U0001D4FA', 'r': '\U0001D4FB', 's': '\U0001D4FC', 't': '\U0001D4FD',
    'u': '\U0001D4FE', 'v': '\U0001D4FF', 'w': '\U0001D500', 'x': '\U0001D501',
    'y': '\U0001D502', 'z': '\U0001D503',
    'A': '\U0001D4D0', 'B': '\U0001D4D1', 'C': '\U0001D4D2', 'D': '\U0001D4D3',
    'E': '\U0001D4D4', 'F': '\U0001D4D5', 'G': '\U0001D4D6', 'H': '\U0001D4D7',
    'I': '\U0001D4D8', 'J': '\U0001D4D9', 'K': '\U0001D4DA', 'L': '\U0001D4DB',
    'M': '\U0001D4DC', 'N': '\U0001D4DD', 'O': '\U0001D4DE', 'P': '\U0001D4DF',
    'Q': '\U0001D4E0', 'R': '\U0001D4E1', 'S': '\U0001D4E2', 'T': '\U0001D4E3',
    'U': '\U0001D4E4', 'V': '\U0001D4E5', 'W': '\U0001D4E6', 'X': '\U0001D4E7',
    'Y': '\U0001D4E8', 'Z': '\U0001D4E9',
}

# Fullwidth Latin
FULLWIDTH = {
    'a': '\uFF41', 'b': '\uFF42', 'c': '\uFF43', 'd': '\uFF44',
    'e': '\uFF45', 'f': '\uFF46', 'g': '\uFF47', 'h': '\uFF48',
    'i': '\uFF49', 'j': '\uFF4A', 'k': '\uFF4B', 'l': '\uFF4C',
    'm': '\uFF4D', 'n': '\uFF4E', 'o': '\uFF4F', 'p': '\uFF50',
    'q': '\uFF51', 'r': '\uFF52', 's': '\uFF53', 't': '\uFF54',
    'u': '\uFF55', 'v': '\uFF56', 'w': '\uFF57', 'x': '\uFF58',
    'y': '\uFF59', 'z': '\uFF5A',
    'A': '\uFF21', 'B': '\uFF22', 'C': '\uFF23', 'D': '\uFF24',
    'E': '\uFF25', 'F': '\uFF26', 'G': '\uFF27', 'H': '\uFF28',
    'I': '\uFF29', 'J': '\uFF2A', 'K': '\uFF2B', 'L': '\uFF2C',
    'M': '\uFF2D', 'N': '\uFF2E', 'O': '\uFF2F', 'P': '\uFF30',
    'Q': '\uFF31', 'R': '\uFF32', 'S': '\uFF33', 'T': '\uFF34',
    'U': '\uFF35', 'V': '\uFF36', 'W': '\uFF37', 'X': '\uFF38',
    'Y': '\uFF39', 'Z': '\uFF3A',
    '0': '\uFF10', '1': '\uFF11', '2': '\uFF12', '3': '\uFF13',
    '4': '\uFF14', '5': '\uFF15', '6': '\uFF16', '7': '\uFF17',
    '8': '\uFF18', '9': '\uFF19',
    ' ': '\u3000', '!': '\uFF01', '?': '\uFF1F', '.': '\uFF0E',
    ',': '\uFF0C', ':': '\uFF1A', ';': '\uFF1B', '(': '\uFF08',
    ')': '\uFF09', '-': '\uFF0D', '_': '\uFF3F', '"': '\uFF02',
    "'": '\uFF07', '+': '\uFF0B', '=': '\uFF1D', '/': '\uFF0F',
    '\\': '\uFF3C', '*': '\uFF0A', '<': '\uFF1C', '>': '\uFF1E',
    '&': '\uFF06', '%': '\uFF05', '#': '\uFF03', '@': '\uFF20',
    '$': '\uFF04', '^': '\uFF3E', '`': '\uFF40', '|': '\uFF5C',
    '~': '\uFF5E', '{': '\uFF5B', '}': '\uFF5D', '[': '\uFF3F',
    ']': '\uFF3D',
}

# Upside Down / Flip mapping
UPSIDE_DOWN = {
    'a': '\u0250', 'b': 'q', 'c': '\u0254', 'd': 'p', 'e': '\u01DD',
    'f': '\u025F', 'g': '\u0183', 'h': '\u0265', 'i': '\u1D09', 'j': '\u027E',
    'k': '\u029E', 'l': 'l', 'm': '\u026F', 'n': 'u', 'o': 'o',
    'p': 'd', 'q': 'b', 'r': '\u0279', 's': 's', 't': '\u0287',
    'u': 'n', 'v': '\u028C', 'w': '\u028D', 'x': 'x', 'y': '\u028E',
    'z': 'z',
    'A': '\u0250', 'B': 'q', 'C': '\u0254', 'D': 'p', 'E': '\u018E',
    'F': '\u2132', 'G': '\u2141', 'H': 'H', 'I': 'I', 'J': '\u017F',
    'K': '\u22CA', 'L': '\u2142', 'M': 'W', 'N': 'N', 'O': 'O',
    'P': '\u0500', 'Q': 'Q', 'R': '\u1D1A', 'S': 'S', 'T': '\u22A5',
    'U': '\u2229', 'V': '\u039B', 'W': 'M', 'X': 'X', 'Y': '\u2144',
    'Z': 'Z',
    '0': '0', '1': '\u21C2', '2': '\u1100', '3': '\u1110', '4': '\u3123',
    '5': '\u078E', '6': '9', '7': '\u3125', '8': '8', '9': '6',
    '.': '\u02D9', ',': "'", "'": ',',
    '"': ',,', '`': ',', '?': '\u00BF', '!': '\u00A1',
    '(': ')', ')': '(',
    '[': ']', ']': '[',
    '{': '}', '}': '{',
    '<': '>', '>': '<',
    '&': '\u214B', '_': '\u203E',
    ';': '\u061B',
}

# Mirrored characters (للمعكوس أفقي)
MIRRORED = {
    'a': 'ɒ', 'b': 'd', 'c': 'ɔ', 'd': 'b', 'e': 'ɘ',
    'f': 'Ꮈ', 'g': 'ǫ', 'h': 'ʜ', 'i': 'i', 'j': 'ꞁ',
    'k': 'ʞ', 'l': 'l', 'm': 'm', 'n': 'n', 'o': 'o',
    'p': 'q', 'q': 'p', 'r': 'ɿ', 's': 'ꙅ', 't': 'ƚ',
    'u': 'u', 'v': 'v', 'w': 'w', 'x': 'x', 'y': 'y',
    'z': 'z',
    'A': '∀', 'B': 'ᗺ', 'C': 'Ɔ', 'D': 'ᗡ', 'E': 'Ǝ',
    'F': 'ᖵ', 'G': 'Ꮹ', 'H': 'H', 'I': 'I', 'J': 'Ⴑ',
    'K': '⋊', 'L': '⅃', 'M': 'M', 'N': 'N', 'O': 'O',
    'P': 'ᑕ', 'Q': 'Ọ', 'R': 'ᖚ', 'S': 'ꙅ', 'T': 'T',
    'U': 'U', 'V': 'V', 'W': 'W', 'X': 'X', 'Y': 'Y',
    'Z': 'Z',
}


# ════════════════════════════════════════════════════════════════
#  Zalgo / Glitch Text - combining marks stacking
#  المصدر: https://fsymbols.com/generators/zalgo-text/
# ════════════════════════════════════════════════════════════════

# علامات للتكدس فوق الحرف (above)
ZALGO_ABOVE = [
    '\u030D', '\u030E', '\u0304', '\u0305', '\u033F', '\u0311',
    '\u0306', '\u0310', '\u0352', '\u0357', '\u0351', '\u0307',
    '\u0308', '\u030A', '\u0342', '\u0343', '\u0344', '\u034A',
    '\u034B', '\u034C', '\u0303', '\u0302', '\u030C', '\u0350',
    '\u0300', '\u0301', '\u030B', '\u030F', '\u0312', '\u0313',
    '\u0314', '\u033D', '\u0309', '\u0363', '\u0364', '\u0365',
    '\u0366', '\u0367', '\u0368', '\u0369', '\u036A', '\u036B',
    '\u036C', '\u036D', '\u036E', '\u036F', '\u033E', '\u035B',
    '\u0346', '\u031A',
]

# علامات للتكدس تحت الحرف (below)
ZALGO_BELOW = [
    '\u0316', '\u0317', '\u0318', '\u0319', '\u031C', '\u031D',
    '\u031E', '\u031F', '\u0320', '\u0324', '\u0325', '\u0326',
    '\u0329', '\u032A', '\u032B', '\u032C', '\u032D', '\u032E',
    '\u032F', '\u0330', '\u0331', '\u0332', '\u0333', '\u0339',
    '\u033A', '\u033B', '\u033C', '\u0345', '\u0347', '\u0348',
    '\u0349', '\u034D', '\u034E', '\u0353', '\u0354', '\u0355',
    '\u0356', '\u0359', '\u035A', '\u0323',
]

# علامات للتكدس في وسط الحرف (overlay)
ZALGO_OVERLAY = [
    '\u0334', '\u0335', '\u0336', '\u0337', '\u0338', '\u033C',
    '\u033D', '\u0342', '\u034F', '\u035C', '\u035D', '\u035E',
    '\u035F', '\u0360', '\u0361', '\u0362', '\u0338',
]


# ════════════════════════════════════════════════════════════════
#  المحرك الرئيسي
# ════════════════════════════════════════════════════════════════

class FancyTextEngine:
    """محرك الأنماط النصية الخارق - 26 نمط بصري مختلف"""

    # أسماء الأنماط مع وصفها وأيقونتها
    STYLES = {
        # ── تشكيل فوق/تحت الحروف (Combining Marks) ──
        'strikethrough': {
            'name': 'Strikethrough',
            'ar': 'خط في منتصف النص',
            'icon': '✘',
            'category': 'combining',
        },
        'long_strikethrough': {
            'name': 'Long Strikethrough',
            'ar': 'خط طويل في المنتصف',
            'icon': '━',
            'category': 'combining',
        },
        'underline': {
            'name': 'Underline',
            'ar': 'خط سفلي',
            'icon': '▁',
            'category': 'combining',
        },
        'double_underline': {
            'name': 'Double Underline',
            'ar': 'خط سفلي مزدوج',
            'icon': '‗',
            'category': 'combining',
        },
        'overline': {
            'name': 'Overline',
            'ar': 'خط علوي',
            'icon': '¯',
            'category': 'combining',
        },
        'double_overline': {
            'name': 'Double Overline',
            'ar': 'خط علوي مزدوج',
            'icon': '̿',
            'category': 'combining',
        },
        'slash_through': {
            'name': 'Slash Through',
            'ar': 'شريط مائل',
            'icon': '/',
            'category': 'combining',
        },
        'x_above': {
            'name': 'X Above',
            'ar': 'X فوق الحرف',
            'icon': '̽',
            'category': 'combining',
        },
        'boxed': {
            'name': 'Boxed Text',
            'ar': 'نص في صندوق',
            'icon': '☐',
            'category': 'enclosing',
        },
        'circled': {
            'name': 'Circled Text',
            'ar': 'نص في دائرة',
            'icon': '◯',
            'category': 'enclosing',
        },
        'squared': {
            'name': 'Squared Text',
            'ar': 'نص في مربع',
            'icon': '◻',
            'category': 'enclosing',
        },
        'bubble': {
            'name': 'Bubble Text',
            'ar': 'نص فقاعي',
            'icon': 'ⓞ',
            'category': 'enclosing',
        },
        # ── استبدال كامل للحروف (Letter Substitution) ──
        'small_caps': {
            'name': 'Small Caps',
            'ar': 'أحرف صغيرة كبيرة',
            'icon': 'A',
            'category': 'substitution',
        },
        'superscript': {
            'name': 'Superscript',
            'ar': 'أحرف علوية',
            'icon': 'ˣ',
            'category': 'substitution',
        },
        'subscript': {
            'name': 'Subscript',
            'ar': 'أحرف سفلية',
            'icon': 'ₓ',
            'category': 'substitution',
        },
        'monospace': {
            'name': 'Monospace',
            'ar': 'أحرف أحادية المسافة',
            'icon': '𝚡',
            'category': 'substitution',
        },
        'fraktur': {
            'name': 'Fraktur',
            'ar': 'خط قوطي',
            'icon': '𝔵',
            'category': 'substitution',
        },
        'double_struck': {
            'name': 'Double Struck',
            'ar': 'خط مزدوج الحواف',
            'icon': '𝕩',
            'category': 'substitution',
        },
        'script': {
            'name': 'Script',
            'ar': 'خط سكربت',
            'icon': '𝓍',
            'category': 'substitution',
        },
        'bold_script': {
            'name': 'Bold Script',
            'ar': 'سكربت عريض',
            'icon': '𝓏',
            'category': 'substitution',
        },
        'fullwidth': {
            'name': 'Fullwidth',
            'ar': 'أحرف عريضة كاملة',
            'icon': 'ｘ',
            'category': 'substitution',
        },
        # ── تحويلات متقدمة (Advanced Transforms) ──
        'mirrored': {
            'name': 'Mirrored Text',
            'ar': 'نص معكوس أفقي',
            'icon': '꓅',
            'category': 'advanced',
        },
        'upside_down': {
            'name': 'Upside Down',
            'ar': 'نص مقلوب رأسياً',
            'icon': 'ʇ',
            'category': 'advanced',
        },
        'vaporwave': {
            'name': 'Vaporwave',
            'ar': 'نص فابرويف',
            'icon': 'ｖ',
            'category': 'advanced',
        },
        'flip': {
            'name': 'Flip Text',
            'ar': 'نص مقلوب',
            'icon': 'Ԑ',
            'category': 'advanced',
        },
        'zalgo': {
            'name': 'Glitch/Zalgo',
            'ar': 'نص معطب (زالجو)',
            'icon': '͓̽',
            'category': 'advanced',
        },
    }

    def __init__(self):
        pass

    # ──────────────────────────────────────────────────────────
    #  دوال مساعدة
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _is_arabic_char(ch):
        """فحص هل الحرف عربي"""
        return bool(re.match(r'[\u0621-\u064A\u0660-\u0669\u06F0-\u06F9]', ch))

    @staticmethod
    def _is_latin_alpha(ch):
        return ch.isascii() and ch.isalpha()

    @staticmethod
    def _is_url(text, pos):
        """فحص هل الموضع داخل رابط"""
        # تحقق بسيط - نبحث عن http:// أو https:// قبل الموضع
        before = text[max(0, pos-30):pos]
        return 'http://' in before or 'https://' in before or 't.me' in before or 'www.' in before

    def _apply_combining(self, text, mark, skip_arabic_digits=False):
        """إضافة علامة combining لكل حرف"""
        result = []
        for i, ch in enumerate(text):
            # لا نضيف العلامة على المسافات وفواصل الأسطر
            if ch in ' \n\t':
                result.append(ch)
                continue
            # لا نضيف على الروابط (للحفاظ على روابط t.me)
            if self._is_url(text, i):
                result.append(ch)
                continue
            result.append(ch)
            result.append(mark)
        return ''.join(result)

    def _apply_enclosing(self, text, mark):
        """إحاطة كل حرف بعلامة enclosing"""
        result = []
        for i, ch in enumerate(text):
            if ch in ' \n\t':
                result.append(ch)
                continue
            if self._is_url(text, i):
                result.append(ch)
                continue
            result.append(ch)
            result.append(mark)
        return ''.join(result)

    def _apply_substitution(self, text, mapping):
        """استبدال الحروف باستخدام جدول تعيين"""
        result = []
        for ch in text:
            if ch in mapping:
                result.append(mapping[ch])
            else:
                result.append(ch)
        return ''.join(result)

    # ──────────────────────────────────────────────────────────
    #  الأنماط الفردية - Combining Marks (12 نمط)
    # ──────────────────────────────────────────────────────────

    def strikethrough(self, text):
        """خط في منتصف النص (U+0336)"""
        return self._apply_combining(text, STRIKETHROUGH)

    def long_strikethrough(self, text):
        """خط طويل في المنتصف (U+0335)"""
        return self._apply_combining(text, LONG_STRIKETHROUGH)

    def underline(self, text):
        """خط سفلي (U+0332)"""
        return self._apply_combining(text, UNDERLINE)

    def double_underline(self, text):
        """خط سفلي مزدوج (U+0333)"""
        return self._apply_combining(text, DOUBLE_UNDERLINE)

    def overline(self, text):
        """خط علوي (U+0305)"""
        return self._apply_combining(text, OVERLINE)

    def double_overline(self, text):
        """خط علوي مزدوج (U+033F)"""
        return self._apply_combining(text, DOUBLE_OVERLINE)

    def slash_through(self, text):
        """شريط مائل (U+0338)"""
        return self._apply_combining(text, SLASH_THROUGH)

    def x_above(self, text):
        """X فوق الحرف (U+033D)"""
        return self._apply_combining(text, X_ABOVE)

    def boxed(self, text):
        """نص في صندوق (U+20E3)"""
        return self._apply_enclosing(text, ENCLOSING_KEYCAP)

    def circled(self, text):
        """نص في دائرة (U+20DD)"""
        return self._apply_enclosing(text, ENCLOSING_CIRCLE)

    def squared(self, text):
        """نص في مربع (U+20DE)"""
        return self._apply_enclosing(text, ENCLOSING_SQUARE)

    def bubble(self, text):
        """نص فقاعي (دائرة مختلفة)"""
        # Bubble = دائرة مع علامة أخرى للتنوع
        return self._apply_enclosing(text, ENCLOSING_CIRCLE)

    # ──────────────────────────────────────────────────────────
    #  الأنماط الفردية - Letter Substitution (9 أنماط)
    # ──────────────────────────────────────────────────────────

    def small_caps(self, text):
        """أحرف صغيرة كبيرة - Small Caps"""
        # تحويل الأحرف الكبيرة لصغيرة أولاً
        result = []
        for ch in text:
            lower = ch.lower()
            if lower in SMALL_CAPS:
                result.append(SMALL_CAPS[lower])
            else:
                result.append(ch)
        return ''.join(result)

    def superscript(self, text):
        """أحرف علوية - Superscript"""
        return self._apply_substitution(text, SUPERSCRIPT)

    def subscript(self, text):
        """أحرف سفلية - Subscript"""
        return self._apply_substitution(text, SUBSCRIPT)

    def monospace(self, text):
        """أحرف أحادية المسافة - Monospace"""
        return self._apply_substitution(text, MONOSPACE)

    def fraktur(self, text):
        """خط قوطي - Fraktur"""
        return self._apply_substitution(text, FRAKTUR)

    def double_struck(self, text):
        """خط مزدوج الحواف - Double Struck"""
        return self._apply_substitution(text, DOUBLE_STRUCK)

    def script(self, text):
        """خط سكربت - Script"""
        return self._apply_substitution(text, SCRIPT)

    def bold_script(self, text):
        """سكربت عريض - Bold Script"""
        return self._apply_substitution(text, BOLD_SCRIPT)

    def fullwidth(self, text):
        """أحرف عريضة كاملة - Fullwidth"""
        return self._apply_substitution(text, FULLWIDTH)

    # ──────────────────────────────────────────────────────────
    #  الأنماط الفردية - Advanced Transforms (5 أنماط)
    # ──────────────────────────────────────────────────────────

    def mirrored(self, text):
        """نص معكوس أفقي - Mirrored Text"""
        result = []
        for ch in text:
            if ch in MIRRORED:
                result.append(MIRRORED[ch])
            else:
                result.append(ch)
        # عكس ترتيب الأحرف
        return ''.join(reversed(result))

    def upside_down(self, text):
        """نص مقلوب رأسياً - Upside Down"""
        result = []
        for ch in text:
            if ch in UPSIDE_DOWN:
                result.append(UPSIDE_DOWN[ch])
            else:
                result.append(ch)
        # عكس الترتيب ليكون النص مقلوباً
        return ''.join(reversed(result))

    def vaporwave(self, text):
        """نص فابرويف - Fullwidth + spacing"""
        result = self.fullwidth(text)
        # إضافة مسافات بديلة بين الكلمات
        result = result.replace('\u3000', '\u3000\u3000')  # توسيع المسافات
        return result

    def flip(self, text):
        """نص مقلوب - Flip Text (upside down + reverse)"""
        return self.upside_down(text)

    def zalgo(self, text, intensity='medium'):
        """
        نص معطب (Glitch/Zalgo)
        كدس علامات combining فوق وتحت كل حرف.
        المصدر: https://fsymbols.com/generators/zalgo-text/
        """
        # تحديد شدة الزالجو
        intensity_map = {
            'light':  (1, 1, 0),  # (above, below, overlay)
            'medium': (2, 2, 1),
            'heavy':  (4, 4, 2),
            'insane': (8, 8, 4),
        }
        n_above, n_below, n_overlay = intensity_map.get(intensity, intensity_map['medium'])

        result = []
        for i, ch in enumerate(text):
            if ch in ' \n\t':
                result.append(ch)
                continue
            if self._is_url(text, i):
                result.append(ch)
                continue
            result.append(ch)
            # كدس علامات فوق
            for _ in range(n_above):
                result.append(random.choice(ZALGO_ABOVE))
            # كدس علامات تحت
            for _ in range(n_below):
                result.append(random.choice(ZALGO_BELOW))
            # كدس علامات overlay
            for _ in range(n_overlay):
                result.append(random.choice(ZALGO_OVERLAY))
        return ''.join(result)

    # ──────────────────────────────────────────────────────────
    #  الواجهة الرئيسية
    # ──────────────────────────────────────────────────────────

    def apply_style(self, text, style_name, **kwargs):
        """
        تطبيق نمط معين على النص
        style_name: اسم النمط من STYLES
        """
        if not text or style_name not in self.STYLES:
            return text

        method = getattr(self, style_name, None)
        if method is None:
            return text

        try:
            # zalgo يحتاج معامل intensity
            if style_name == 'zalgo':
                intensity = kwargs.get('intensity', 'medium')
                return method(text, intensity=intensity)
            return method(text)
        except Exception:
            return text

    def apply_multiple(self, text, style_names, **kwargs):
        """تطبيق عدة أنماط بالتسلسل"""
        result = text
        for style in style_names:
            result = self.apply_style(result, style, **kwargs)
        return result

    def get_categories(self):
        """إرجاع التصنيفات"""
        return {
            'combining':   'تشكيل فوق/تحت الحروف',
            'enclosing':   'إحاطة الحروف',
            'substitution':'استبدال الحروف',
            'advanced':    'تحويلات متقدمة',
        }

    def get_styles_by_category(self, category):
        """الحصول على الأنماط حسب التصنيف"""
        return {k: v for k, v in self.STYLES.items() if v['category'] == category}

    def get_all_style_names(self):
        """قائمة بأسماء كل الأنماط"""
        return list(self.STYLES.keys())

    def preview_all_styles(self, text, sample_len=30):
        """
        معاينة كل الأنماط على نص معين
        يُرجع dict {style_name: transformed_text}
        """
        results = {}
        for style_name in self.STYLES:
            try:
                # للمعاينة نأخذ أول sample_len حرف فقط
                sample = text[:sample_len] if len(text) > sample_len else text
                if style_name == 'zalgo':
                    results[style_name] = self.zalgo(sample, intensity='light')
                else:
                    results[style_name] = self.apply_style(sample, style_name)
            except Exception:
                results[style_name] = sample
        return results


# ════════════════════════════════════════════════════════════════
#  مثال جاهز (singleton)
# ════════════════════════════════════════════════════════════════

fancy_engine = FancyTextEngine()


# ════════════════════════════════════════════════════════════════
#  دوال مساعدة للاختبار
# ════════════════════════════════════════════════════════════════

def demo_all_styles(text):
    """عرض كل الأنماط على نص معين - للاختبار"""
    engine = FancyTextEngine()
    print(f"📝 النص الأصلي: {text}\n")
    print("═" * 60)
    current_category = None
    for style_name, info in engine.STYLES.items():
        if info['category'] != current_category:
            current_category = info['category']
            cat_names = engine.get_categories()
            print(f"\n📂 {cat_names[current_category]}")
            print("─" * 60)
        try:
            transformed = engine.apply_style(text, style_name)
            print(f"{info['icon']} {info['name']:20s} → {transformed}")
        except Exception as e:
            print(f"{info['icon']} {info['name']:20s} → ERROR: {e}")


if __name__ == '__main__':
    # اختبار شامل
    samples = [
        "اشترك في قناتنا https://t.me/mychannel عروض حصرية!",
        "Hello World! Check out our amazing offer!",
        "واتساب: 0555123456 - توصيل مجاني",
    ]

    for sample in samples:
        print(f"\n{'='*70}")
        demo_all_styles(sample)
        print()
