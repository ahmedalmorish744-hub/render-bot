class YayTextMesslettersObfuscator:
    """
    نظام تشويش وتشفير مدمج خارق من 6 مصادر:
    - fancy-fonts-generator: 27 نمط خط Unicode
    - text_unicoder: تحويلات رونية + يونانية + مقلوبة + أجزاء
    - telegram-fancy-fonts-bot: أنماط Cherokee + CJK + Cyrillic
    - convert-case: Zalgo + يتوسطه خط + مسطر + مقلوب
    - YayText + Messletters: أنماط إضافية
    - تقنيات مخصصة: أحرف غير مرئية + مسافات بديلة + تشويش عربي
    
    إجمالي: 45+ نمط تحويل مختلف
    كل رسالة تحصل على تركيبة عشوائية مختلفة
    يستحيل على بوتات الحماية التعرف على النص
    """

    # ══════════════════════════════════════════════
    #  خريطة الحروف اللاتينية (A-Z, a-z, 0-9)
    #  لكل نمط من أنماط Unicode
    # ══════════════════════════════════════════════
    
    # ─── Mathematical Alphanumeric Symbols (11 نمط) ───
    BOLD_MAP = {}
    ITALIC_MAP = {}
    BOLD_ITALIC_MAP = {}
    MONOSPACE_MAP = {}
    SCRIPT_MAP = {}
    BOLD_SCRIPT_MAP = {}
    FRAKTUR_MAP = {}
    BOLD_FRAKTUR_MAP = {}
    DOUBLE_STRUCK_MAP = {}
    SANS_MAP = {}
    SANS_BOLD_MAP = {}
    SANS_ITALIC_MAP = {}
    SANS_BOLD_ITALIC_MAP = {}
    SANS_MONO_MAP = {}
    
    # ─── أنماط Messletters / Fancy Fonts الإضافية ───
    FULLWIDTH_MAP = {}
    SMALL_CAPS_MAP = {}
    SUPERSCRIPT_MAP = {}
    BUBBLES_MAP = {}
    BUBBLE_BLACK_MAP = {}
    PARENTHESIS_MAP = {}
    SQUARED_MAP = {}
    
    # ─── أنماط Cross-Script (من telegram-fancy-fonts-bot) ───
    RUSSIAN_MAP = {}
    JAPANESE_MAP = {}
    ARABIC_STYLE_MAP = {}
    FAIRY_MAP = {}
    WIZARD_MAP = {}
    FUNKY_MAP = {}
    
    # ─── أنماط Diacritical (من fancy-fonts-generator) ───
    ACUTE_MAP = {}
    ROCK_DOTS_MAP = {}
    STROKED_MAP = {}
    INVERTED_MAP = {}
    
    # ─── جداول أرقام Unicode ───
    DIGIT_BOLD_MAP = {}
    DIGIT_DOUBLE_STRUCK_MAP = {}
    DIGIT_SANS_MAP = {}
    DIGIT_SANS_BOLD_MAP = {}
    DIGIT_MONO_MAP = {}
    DIGIT_FULLWIDTH_MAP = {}
    DIGIT_SUPERSCRIPT_MAP = {}
    DIGIT_BUBBLES_MAP = {}
    DIGIT_INVERTED_MAP = {}
    
    # ─── Homoglyphs سيريلية/يونانية ───
    HOMOGLYPH_MAP = {}
    
    # ─── خريطة المقلوب (Upside-down) من text_unicoder ───
    UPSIDE_DOWN_MAP = {}
    
    # ─── خريطة اليونانية الصوتية من text_unicoder ───
    GREEK_MAP = {}
    
    # ─── خريطة الرونية من text_unicoder ───
    RUNE_MAP = {}

    def __init__(self):
        self._build_maps()
        self._last_style = -1
        self._build_styles_list()

    def _build_maps(self):
        """بناء كل جداول التحويل"""
        
        # ═══ Mathematical Bold (U+1D400) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.BOLD_MAP[c] = chr(0x1D400 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.BOLD_MAP[c] = chr(0x1D41A + i)
        for i in range(10):
            self.BOLD_MAP[str(i)] = chr(0x1D7CE + i)
            self.DIGIT_BOLD_MAP[str(i)] = chr(0x1D7CE + i)
        
        # ═══ Mathematical Italic (U+1D434) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.ITALIC_MAP[c] = chr(0x1D434 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.ITALIC_MAP[c] = chr(0x1D44E + i)
        self.ITALIC_MAP['h'] = '\u210F'
        
        # ═══ Mathematical Bold Italic (U+1D468) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.BOLD_ITALIC_MAP[c] = chr(0x1D468 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.BOLD_ITALIC_MAP[c] = chr(0x1D482 + i)
        
        # ═══ Mathematical Monospace (U+1D670) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.MONOSPACE_MAP[c] = chr(0x1D670 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.MONOSPACE_MAP[c] = chr(0x1D68A + i)
        for i in range(10):
            self.MONOSPACE_MAP[str(i)] = chr(0x1D7F6 + i)
            self.DIGIT_MONO_MAP[str(i)] = chr(0x1D7F6 + i)
        
        # ═══ Mathematical Script (U+1D49C) ═══
        script_exc = {'B': '\u212C', 'E': '\u2130', 'F': '\u2131',
                      'H': '\u210B', 'I': '\u2110', 'L': '\u2112',
                      'M': '\u2133', 'R': '\u211B'}
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SCRIPT_MAP[c] = script_exc.get(c, chr(0x1D49C + i))
        script_lower_exc = {'e': '\u212F', 'g': '\u210A', 'o': '\u2134'}
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SCRIPT_MAP[c] = script_lower_exc.get(c, chr(0x1D4B6 + i))
        
        # ═══ Mathematical Bold Script (U+1D4D0) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.BOLD_SCRIPT_MAP[c] = chr(0x1D4D0 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.BOLD_SCRIPT_MAP[c] = chr(0x1D4EA + i)
        
        # ═══ Mathematical Fraktur (U+1D504) ═══
        fraktur_exc = {'C': '\u212D', 'H': '\u210C', 'I': '\u2111',
                       'R': '\u211C', 'Z': '\u2128'}
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.FRAKTUR_MAP[c] = fraktur_exc.get(c, chr(0x1D504 + i))
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.FRAKTUR_MAP[c] = chr(0x1D51E + i)
        
        # ═══ Mathematical Bold Fraktur (U+1D56C) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.BOLD_FRAKTUR_MAP[c] = chr(0x1D56C + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.BOLD_FRAKTUR_MAP[c] = chr(0x1D586 + i)
        
        # ═══ Mathematical Double-Struck (U+1D538) ═══
        ds_exc = {'C': '\u2102', 'H': '\u210D', 'N': '\u2115',
                  'P': '\u2119', 'Q': '\u211A', 'R': '\u211D', 'Z': '\u2124'}
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.DOUBLE_STRUCK_MAP[c] = ds_exc.get(c, chr(0x1D538 + i))
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.DOUBLE_STRUCK_MAP[c] = chr(0x1D552 + i)
        ds_digits = {'0': '\U0001D7D8', '1': '\U0001D7D9', '2': '\U0001D7DA',
                     '3': '\U0001D7DB', '4': '\U0001D7DC', '5': '\U0001D7DD',
                     '6': '\U0001D7DE', '7': '\U0001D7DF', '8': '\U0001D7E0',
                     '9': '\U0001D7E1'}
        self.DOUBLE_STRUCK_MAP.update(ds_digits)
        self.DIGIT_DOUBLE_STRUCK_MAP = dict(ds_digits)
        
        # ═══ Mathematical Sans-Serif (U+1D5A0) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SANS_MAP[c] = chr(0x1D5A0 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SANS_MAP[c] = chr(0x1D5BA + i)
        for i in range(10):
            self.SANS_MAP[str(i)] = chr(0x1D7E2 + i)
            self.DIGIT_SANS_MAP[str(i)] = chr(0x1D7E2 + i)
        
        # ═══ Mathematical Sans-Serif Bold (U+1D5D4) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SANS_BOLD_MAP[c] = chr(0x1D5D4 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SANS_BOLD_MAP[c] = chr(0x1D5EE + i)
        for i in range(10):
            self.SANS_BOLD_MAP[str(i)] = chr(0x1D7EC + i)
            self.DIGIT_SANS_BOLD_MAP[str(i)] = chr(0x1D7EC + i)
        
        # ═══ Mathematical Sans-Serif Italic (U+1D608) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SANS_ITALIC_MAP[c] = chr(0x1D608 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SANS_ITALIC_MAP[c] = chr(0x1D622 + i)
        
        # ═══ Mathematical Sans-Serif Bold Italic (U+1D63C) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SANS_BOLD_ITALIC_MAP[c] = chr(0x1D63C + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SANS_BOLD_ITALIC_MAP[c] = chr(0x1D656 + i)
        
        # ═══ Sans-Serif Monospace ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SANS_MONO_MAP[c] = chr(0x1D6A8 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SANS_MONO_MAP[c] = chr(0x1D6C2 + i)
        
        # ═══ Fullwidth (U+FF21) ═══
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.FULLWIDTH_MAP[c] = chr(0xFF21 + i)
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.FULLWIDTH_MAP[c] = chr(0xFF41 + i)
        for i in range(10):
            self.FULLWIDTH_MAP[str(i)] = chr(0xFF10 + i)
            self.DIGIT_FULLWIDTH_MAP[str(i)] = chr(0xFF10 + i)
        
        # ═══ Small Caps ═══
        self.SMALL_CAPS_MAP = {
            'A': '\u1D00', 'B': '\u0299', 'C': '\u1D04', 'D': '\u1D05',
            'E': '\u1D07', 'F': '\uA730', 'G': '\u0262', 'H': '\u029C',
            'I': '\u026A', 'J': '\u1D0A', 'K': '\u1D0B', 'L': '\u029F',
            'M': '\u1D0D', 'N': '\u0274', 'O': '\u1D0F', 'P': '\u1D18',
            'Q': '\u01EB', 'R': '\u0280', 'S': '\uA731', 'T': '\u1D1B',
            'U': '\u1D1C', 'V': '\u1D20', 'W': '\u1D21', 'X': '\uA78D',
            'Y': '\u028F', 'Z': '\u1D22',
        }
        
        # ═══ Superscript (من fancy-fonts-generator) ═══
        sup_lower = 'ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖqʳˢᵗᵘᵛʷˣʸᶻ'
        sup_upper = 'ᴬᴮᶜᴰᴱᶠᴳᴴᴵᴶᴷᴸᴹᴺᴼᴾQᴿˢᵀᵁⱽᵂˣʸᶻ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SUPERSCRIPT_MAP[c] = sup_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SUPERSCRIPT_MAP[c] = sup_upper[i]
        sup_digits = '⁰¹²³⁴⁵⁶⁷⁸⁹'
        for i in range(10):
            self.SUPERSCRIPT_MAP[str(i)] = sup_digits[i]
            self.DIGIT_SUPERSCRIPT_MAP[str(i)] = sup_digits[i]
        
        # ═══ Bubbles / Circled (U+24D0) ═══
        bub_lower = 'ⓐⓑⓒⓓⓔⓕⓖⓗⓘⓙⓚⓛⓜⓝⓞⓟⓠⓡⓢⓣⓤⓥⓦⓧⓨⓩ'
        bub_upper = 'ⒶⒷⒸⒹⒺⒻⒼⒽⒾⒿⓀⓁⓂⓃⓄⓅⓆⓇⓈⓉⓊⓋⓌⓍⓎⓏ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.BUBBLES_MAP[c] = bub_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.BUBBLES_MAP[c] = bub_upper[i]
        bub_digits = '⓪①②③④⑤⑥⑦⑧⑨'
        for i in range(10):
            self.BUBBLES_MAP[str(i)] = bub_digits[i]
            self.DIGIT_BUBBLES_MAP[str(i)] = bub_digits[i]
        
        # ═══ Bubble Black / Negative Circled (U+1F150) ═══
        bb_lower = '🅐🅑🅒🅓🅔🅕🅖🅗🅘🅙🅚🅛🅜🅝🅞🅟🅠🅡🅢🅣🅤🅥🅦🅧🅨🅩'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.BUBBLE_BLACK_MAP[c] = bb_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.BUBBLE_BLACK_MAP[c] = bb_lower[i]
        
        # ═══ Parenthesis (U+249C) ═══
        par_lower = '⒜⒝⒞⒟⒠⒡⒢⒣⒤⒥⒦⒧⒨⒩⒪⒫⒬⒭⒮⒯⒰⒱⒲⒳⒴⒵'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.PARENTHESIS_MAP[c] = par_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.PARENTHESIS_MAP[c] = par_lower[i]
        
        # ═══ Squared (U+1F130) ═══
        sq_chars = '🄰🄱🄲🄳🄴🄵🄶🄷🄸🄹🄺🄻🄼🄽🄾🄿🅀🅁🅂🅃🅄🅅🅆🅇🅈🅉'
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.SQUARED_MAP[c] = sq_chars[i]
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.SQUARED_MAP[c] = sq_chars[i]
        
        # ═══ Cross-Script: Russian (Cyrillic lookalikes) ═══
        rus_lower = 'абcдёfgнїjкгѫпѳpфя$тцѵщжчз'
        rus_upper = 'АБCДЄFGHЇJКГѪЙѲPФЯ$TЦѴШЖЧЗ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.RUSSIAN_MAP[c] = rus_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.RUSSIAN_MAP[c] = rus_upper[i]
        
        # ═══ Cross-Script: Japanese (CJK lookalikes) ═══
        jap_chars = '卂乃匚ᗪ乇千Ꮆ卄丨ﾌҜㄥ爪几ㄖ卩Ɋ尺丂ㄒㄩᐯ山乂ㄚ乙'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.JAPANESE_MAP[c] = jap_chars[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.JAPANESE_MAP[c] = jap_chars[i]
        
        # ═══ Cross-Script: Arabic Style (Thai/Hebrew lookalikes) ═══
        ar_chars = 'ค๒ς๔єŦﻮђเןкl๓ภ๏קợгรtยשฬץאz'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.ARABIC_STYLE_MAP[c] = ar_chars[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.ARABIC_STYLE_MAP[c] = ar_chars[i]
        
        # ═══ Cross-Script: Fairy (Cherokee) ═══
        fairy_chars = 'ᏗᏰፈᎴᏋᎦᎶᏂᎥᏠᏦᏝᎷᏁᎧᎮᎤᏒᏕᏖᏬᏉᏇጀᎩፚ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.FAIRY_MAP[c] = fairy_chars[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.FAIRY_MAP[c] = fairy_chars[i]
        
        # ═══ Cross-Script: Wizard (IPA/Armenian) ═══
        wiz_chars = 'ǟɮƈɖɛʄɢɦɨʝӄʟʍռօքզʀֆȶʊʋաӼʏʐ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.WIZARD_MAP[c] = wiz_chars[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.WIZARD_MAP[c] = wiz_chars[i]
        
        # ═══ Cross-Script: Funky (Greek mix) ═══
        funk_chars = 'αв¢∂єƒgнιנкℓмησρqяѕтυνωχуz'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.FUNKY_MAP[c] = funk_chars[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.FUNKY_MAP[c] = funk_chars[i]
        
        # ═══ Diacritical: Acute ═══
        acute_lower = 'ábćdéfǵhíjḱĺḿńőṕqŕśtúvẃxӳź'
        acute_upper = 'ÁBĆDÉFǴHÍJḰĹḾŃŐṔQŔŚTŰVẂXӲŹ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.ACUTE_MAP[c] = acute_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.ACUTE_MAP[c] = acute_upper[i]
        
        # ═══ Diacritical: RockDots (Umlaut) ═══
        rock_lower = 'äḅċḋëḟġḧïjḳḷṁṅöṗqṛṡẗüṿẅẍÿż'
        rock_upper = 'ÄḄĊḊËḞĠḦÏJḲḶṀṄÖṖQṚṠṪÜṾẄẌŸŻ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.ROCK_DOTS_MAP[c] = rock_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.ROCK_DOTS_MAP[c] = rock_upper[i]
        
        # ═══ Diacritical: Stroked (Barred) ═══
        stroke_lower = 'Ⱥƀȼđɇfǥħɨɉꝁłmnøᵽꝗɍsŧᵾvwxɏƶ'
        stroke_upper = 'ȺɃȻĐɆFǤĦƗɈꝀŁMNØⱣꝖɌSŦᵾVWXɎƵ'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.STROKED_MAP[c] = stroke_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.STROKED_MAP[c] = stroke_upper[i]
        
        # ═══ Inverted / Upside-down ═══
        inv_lower = 'ɐqɔpǝɟƃɥıɾʞןɯuodbɹsʇnʌʍxʎz'
        inv_upper = '∀ᗺƆᗡƎℲ⅁HIſꓘ˥WNOԀტᴚS⊥∩ΛMX⅄Z'
        for i, c in enumerate('abcdefghijklmnopqrstuvwxyz'):
            self.INVERTED_MAP[c] = inv_lower[i]
        for i, c in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ'):
            self.INVERTED_MAP[c] = inv_upper[i]
        inv_digits = '0ƖᘔƐ߈95ㄥ86'
        for i in range(10):
            self.INVERTED_MAP[str(i)] = inv_digits[i]
            self.DIGIT_INVERTED_MAP[str(i)] = inv_digits[i]
        
        # ═══ Homoglyphs (Cyrillic/Greek مشابهة) ═══
        self.HOMOGLYPH_MAP = {
            'a': '\u0430', 'A': '\u0410', 'c': '\u0441', 'C': '\u0421',
            'e': '\u0435', 'E': '\u0415', 'o': '\u043E', 'O': '\u041E',
            'p': '\u0440', 'P': '\u0420', 'x': '\u0445', 'X': '\u0425',
            'y': '\u0443', 'Y': '\u0423', 'i': '\u0456', 'I': '\u0406',
            'j': '\u0458', 'J': '\u0408', 's': '\u0455', 'S': '\u0405',
            'k': '\u043A', 'K': '\u041A', 'H': '\u041D', 'T': '\u0422',
            'M': '\u041C', 'B': '\u0412', 'g': '\u0493', 'G': '\u0492',
            'h': '\u04BB', 'b': '\u0431', 'd': '\u0501', 'u': '\u04AF',
        }
        
        # ═══ Upside-down map (من text_unicoder) ═══
        self.UPSIDE_DOWN_MAP = {
            'a': 'ɐ', 'b': 'q', 'c': 'ɔ', 'd': 'p', 'e': 'ǝ',
            'f': 'ɟ', 'g': 'ᵷ', 'h': 'ɥ', 'i': 'ᴉ', 'j': 'ɾ',
            'k': 'ʞ', 'm': 'ɯ', 'n': 'u', 'r': 'ɹ', 't': 'ʇ',
            'v': 'ʌ', 'w': 'ʍ', 'y': 'ʎ', '.': '˙', ',': 'ʻ',
            '!': '¡', '?': '¿', '&': '⅋', 'A': '∀', 'C': 'Ɔ',
            'E': 'Ǝ', 'F': 'Ⅎ', 'G': '⅍', 'J': 'ſ', 'L': '⅂',
            'M': 'Ɯ', 'P': 'd', 'R': 'ᴚ', 'T': 'ꚱ', 'U': '∩',
            'V': 'Λ', 'W': 'M', 'Y': '⅄', '1': 'ↂ', '3': 'Ɛ',
        }
        
        # ═══ Greek phonemic map (من text_unicoder) ═══
        self.GREEK_MAP = {
            'a': 'α', 'A': 'Α', 'b': 'β', 'B': 'Β', 'g': 'γ', 'G': 'Γ',
            'd': 'δ', 'D': 'Δ', 'e': 'ε', 'E': 'Ε', 'z': 'ζ', 'Z': 'Ζ',
            'h': 'η', 'H': 'Η', 's': 'σ', 'S': 'Σ', 't': 'τ', 'T': 'Τ',
            'y': 'υ', 'Y': 'Υ', 'f': 'φ', 'F': 'Φ', 'c': 'χ', 'C': 'Χ',
            'w': 'ψ', 'W': 'Ψ', 'u': 'ω', 'U': 'Ω', 'i': 'ι', 'I': 'Ι',
            'k': 'κ', 'K': 'Κ', 'l': 'λ', 'L': 'Λ', 'm': 'μ', 'M': 'Μ',
            'n': 'ν', 'N': 'Ν', 'o': 'ο', 'O': 'Ο', 'p': 'π', 'P': 'Π',
            'r': 'ρ', 'R': 'Ρ', 'q': 'κ', 'Q': 'Κ', 'j': 'ι', 'J': 'Ι',
            'v': '∇', 'x': 'χ', 'X': 'Χ',
        }
        
        # ═══ Rune map (Elder Futhark من text_unicoder) ═══
        self.RUNE_MAP = {
            'a': 'ᚨ', 'A': 'ᚨ', 'b': 'ᛒ', 'B': 'ᛒ', 'c': 'ᚲ', 'C': 'ᚲ',
            'd': 'ᛞ', 'D': 'ᛞ', 'e': 'ᛖ', 'E': 'ᛖ', 'f': 'ᚠ', 'F': 'ᚠ',
            'g': 'ᚷ', 'G': 'ᚷ', 'h': 'ᚺ', 'H': 'ᚺ', 'i': 'ᛁ', 'I': 'ᛁ',
            'j': 'ᛃ', 'J': 'ᛃ', 'k': 'ᚲ', 'K': 'ᚲ', 'l': 'ᛚ', 'L': 'ᛚ',
            'm': 'ᛗ', 'M': 'ᛗ', 'n': 'ᚾ', 'N': 'ᚾ', 'o': 'ᛟ', 'O': 'ᛟ',
            'p': 'ᛈ', 'P': 'ᛈ', 'q': 'ᚲ', 'r': 'ᚱ', 'R': 'ᚱ',
            's': 'ᛊ', 'S': 'ᛊ', 't': 'ᛏ', 'T': 'ᛏ', 'u': 'ᚢ', 'U': 'ᚢ',
            'v': 'ᚹ', 'V': 'ᚹ', 'w': 'ᚹ', 'W': 'ᚹ', 'x': 'ᚲᛊ', 'X': 'ᚲᛊ',
            'y': 'ᛁ', 'Y': 'ᛁ', 'z': 'ᛉ', 'Z': 'ᛉ',
        }

    def _build_styles_list(self):
        """بناء قائمة كل الأنماط المتاحة (45+ نمط)"""
        self.STYLES = [
            ('bold', self.BOLD_MAP),
            ('italic', self.ITALIC_MAP),
            ('bold_italic', self.BOLD_ITALIC_MAP),
            ('monospace', self.MONOSPACE_MAP),
            ('script', self.SCRIPT_MAP),
            ('bold_script', self.BOLD_SCRIPT_MAP),
            ('fraktur', self.FRAKTUR_MAP),
            ('bold_fraktur', self.BOLD_FRAKTUR_MAP),
            ('double_struck', self.DOUBLE_STRUCK_MAP),
            ('sans', self.SANS_MAP),
            ('sans_bold', self.SANS_BOLD_MAP),
            ('bubbles', self.BUBBLES_MAP),
            ('bubble_black', self.BUBBLE_BLACK_MAP),
            ('parenthesis', self.PARENTHESIS_MAP),
            ('squared', self.SQUARED_MAP),
            ('superscript', self.SUPERSCRIPT_MAP),
            ('fullwidth', self.FULLWIDTH_MAP),
            ('russian', self.RUSSIAN_MAP),
            ('japanese', self.JAPANESE_MAP),
            ('arabic_style', self.ARABIC_STYLE_MAP),
            ('fairy', self.FAIRY_MAP),
            ('wizard', self.WIZARD_MAP),
            ('funky', self.FUNKY_MAP),
            ('acute', self.ACUTE_MAP),
            ('rock_dots', self.ROCK_DOTS_MAP),
            ('stroked', self.STROKED_MAP),
            ('small_caps', self.SMALL_CAPS_MAP),
            ('sans_italic', self.SANS_ITALIC_MAP),
            ('sans_bold_italic', self.SANS_BOLD_ITALIC_MAP),
            ('sans_mono', self.SANS_MONO_MAP),
        ]
        # Special: -1 strikethrough, -2 underline, -3 inverted
        # -4 zalgo, -5 homoglyphs, -6 greek, -7 rune, -8 upside_down, -9 random_combo

    def _apply_map(self, text, char_map):
        result = []
        for c in text:
            result.append(char_map[c] if c in char_map else c)
        return ''.join(result)

    def _apply_map_preserve_digits(self, text, char_map):
        result = []
        for c in text:
            if c.isdigit():
                result.append(c)
            elif c in char_map:
                result.append(char_map[c])
            else:
                result.append(c)
        return ''.join(result)

    def _apply_strikethrough(self, text):
        result = []
        for c in text:
            if c.isalpha():
                result.append(c + '\u0336')
            else:
                result.append(c)
        return ''.join(result)

    def _apply_underline(self, text):
        result = []
        for c in text:
            if c.isalpha():
                result.append(c + '\u0332')
            else:
                result.append(c)
        return ''.join(result)

    def _apply_zalgo(self, text, intensity=3):
        combining_above = list(range(0x0300, 0x0315))
        combining_below = list(range(0x0316, 0x0333))
        all_combining = combining_above + combining_below
        result = []
        for c in text:
            result.append(c)
            if c.isalpha() or c.isdigit():
                num_marks = random.randint(1, intensity)
                for _ in range(num_marks):
                    result.append(chr(random.choice(all_combining)))
        return ''.join(result)

    def _apply_inverted(self, text):
        return self._apply_map(text, self.INVERTED_MAP)

    def _apply_upside_down(self, text):
        result = []
        for c in reversed(text):
            result.append(self.UPSIDE_DOWN_MAP.get(c, c))
        return ''.join(result)

    def _apply_greek(self, text):
        return self._apply_map(text, self.GREEK_MAP)

    def _apply_rune(self, text):
        return self._apply_map(text, self.RUNE_MAP)

    def _apply_homoglyphs(self, text, intensity=0.35):
        result = []
        for c in text:
            if c in self.HOMOGLYPH_MAP and random.random() < intensity:
                result.append(self.HOMOGLYPH_MAP[c])
            else:
                result.append(c)
        return ''.join(result)

    def _apply_random_combo(self, text):
        available = list(range(len(self.STYLES)))
        num_styles = random.randint(2, 3)
        chosen = random.sample(available, min(num_styles, len(available)))
        result = text
        for idx in chosen:
            _, char_map = self.STYLES[idx]
            chars = list(result)
            for i, c in enumerate(chars):
                if c in char_map and random.random() < 0.5:
                    chars[i] = char_map[c]
            result = ''.join(chars)
        return result

    def _escape_html(self, text):
        if not text:
            return text
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        return text

    def _obfuscate_display_text(self, text, style_idx):
        if not text or len(text) < 2:
            return text
        inv_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF', '\u2060', '\u2061']
        result = random.choice(inv_chars) + text
        alt_spaces = ['\u00A0', '\u2009', '\u202F', '\u2008']
        chars = list(result)
        for i, c in enumerate(chars):
            if c == ' ' and random.random() < 0.4:
                chars[i] = random.choice(alt_spaces)
        result = ''.join(chars)
        space_positions = [i for i, c in enumerate(result) if c in [' ', '\u00A0', '\u2009', '\u202F']]
        for pos in space_positions:
            if random.random() < 0.25:
                result = result[:pos+1] + random.choice(inv_chars) + result[pos+1:]
        arabic_variants = {'ي': '\u06CC', 'ك': '\u06A9', 'ه': '\u0647', 'ة': '\u0629'}
        chars = list(result)
        for i, c in enumerate(chars):
            if c in arabic_variants and random.random() < 0.06:
                chars[i] = arabic_variants[c]
        result = ''.join(chars)
        if random.random() < 0.2:
            result = result + '\u200F'
        return result

    def _create_url_display(self, url, style_idx):
        tme_displays = [
            'تابع القناة', 'انضم لنا', 'القناة هنا', 'زورنا',
            'ادخل القناة', 'اشترك معنا', 'تفضل بالدخول', 'الرابط',
            'من هنا', 'اضغط', 'تابعنا', 'قناتنا',
            'انضم الآن', 'هنا', 'ادخل هنا', 'شاهد',
            'تفضل', 'تابع التحديثات', 'آخر الأخبار هنا', 'صحبتنا',
            'محتوى مميز', 'تواصل معنا', 'تعرف علينا', 'انضمام',
            'القناة الرسمية', 'متابعة', 'دخول', 'رابط القناة',
        ]
        general_displays = [
            'اضغط هنا', 'الرابط', 'من هنا', 'تفضل',
            'شاهد', 'تابع', 'ادخل', 'هنا',
            'تفاصيل أكثر', 'المزيد', 'زورنا', 'اضغط',
            'معلومات إضافية', 'تفقد الرابط', 'انتقل', 'الموقع',
        ]
        if 't.me/' in url:
            return random.choice(tme_displays)
        return random.choice(general_displays)

    def _create_mention_display(self, mention, style_idx):
        displays = ['اضغط هنا', 'الملف الشخصي', 'هنا', 'تفضل', 'تابعنا', 'الرابط', 'من هنا', 'تعرف علينا', 'تواصل', 'ادخل', 'الصفحة', 'اضغط']
        return random.choice(displays)

    def _apply_style_to_text(self, text, style_idx):
        """12 طبقة تشويش متراكبة"""
        if not text:
            return text

        # الطبقة 1: نمط Unicode أساسي
        if style_idx >= 0:
            _, char_map = self.STYLES[style_idx]
            transformed = self._apply_map_preserve_digits(text, char_map)
        elif style_idx == -1:
            transformed = self._apply_strikethrough(text)
        elif style_idx == -2:
            transformed = self._apply_underline(text)
        elif style_idx == -3:
            transformed = self._apply_inverted(text)
        elif style_idx == -4:
            transformed = self._apply_zalgo(text, intensity=2)
        elif style_idx == -5:
            transformed = self._apply_homoglyphs(text, intensity=0.5)
        elif style_idx == -6:
            transformed = self._apply_greek(text)
        elif style_idx == -7:
            transformed = self._apply_rune(text)
        elif style_idx == -8:
            transformed = self._apply_upside_down(text)
        elif style_idx == -9:
            transformed = self._apply_random_combo(text)
        else:
            transformed = text

        # الطبقة 2: Homoglyphs إضافية
        if style_idx not in (-5, -6, -7):
            transformed = self._apply_homoglyphs(transformed, intensity=0.15)

        # الطبقة 3: أحرف غير مرئية بين الكلمات
        inv_chars = ['\u200B', '\u200C', '\u200D', '\uFEFF', '\u2060', '\u2061', '\u2062', '\u2063']
        words = transformed.split(' ')
        new_words = []
        for i, w in enumerate(words):
            new_words.append(w)
            if i < len(words) - 1 and random.random() < 0.2:
                new_words.append(random.choice(inv_chars))
        transformed = ' '.join(new_words)

        # الطبقة 4: مسافات بديلة
        alt_spaces = ['\u00A0', '\u2009', '\u202F', '\u2008', '\u2007', '\u2006', '\u2005', '\u2004']
        result_list = list(transformed)
        for i, c in enumerate(result_list):
            if c == ' ' and random.random() < 0.35:
                result_list[i] = random.choice(alt_spaces)
        transformed = ''.join(result_list)

        # الطبقة 5: تحويلات عربية خفيفة
        arabic_variants = {'ي': '\u06CC', 'ك': '\u06A9', 'ه': '\u0647', 'ة': '\u0629', 'أ': '\u0623', 'إ': '\u0625', 'آ': '\u0622'}
        result_list = list(transformed)
        for i, c in enumerate(result_list):
            if c in arabic_variants and random.random() < 0.05:
                result_list[i] = arabic_variants[c]
        transformed = ''.join(result_list)

        # الطبقة 6: أحرف غير مرئية حول علامات الترقيم
        if len(transformed) > 5:
            punctuation = '،.؛:!؟-'
            result_list = list(transformed)
            insert_positions = []
            for i, c in enumerate(result_list):
                if c in punctuation and random.random() < 0.3:
                    insert_positions.append((i + 1, random.choice(inv_chars[:4])))
            for pos, char in sorted(insert_positions, key=lambda x: x[0], reverse=True):
                result_list.insert(pos, char)
            transformed = ''.join(result_list)

        # الطبقة 7: علامة RTL خفية
        if random.random() < 0.2:
            transformed = transformed + '\u200F'

        # الطبقة 8: أحرف غير مرئية كثيفة
        words = transformed.split(' ')
        dense_words = []
        for i, w in enumerate(words):
            dense_words.append(w)
            if i < len(words) - 1:
                num_inv = random.randint(0, 2)
                for _ in range(num_inv):
                    dense_words.append(random.choice(inv_chars))
        transformed = ' '.join(dense_words)

        # الطبقة 9: أحرف غير مرئية بعد أحرف عربية
        if len(transformed) > 10:
            chars = list(transformed)
            insert_positions = []
            for i in range(len(chars)):
                if '\u0600' <= chars[i] <= '\u06FF' and random.random() < 0.06:
                    insert_positions.append((i + 1, random.choice(inv_chars[:4])))
            for pos, char in sorted(insert_positions, key=lambda x: x[0], reverse=True):
                chars.insert(pos, char)
            transformed = ''.join(chars)

        # الطبقة 10: Zero-width joiner عشوائي
        if random.random() < 0.15 and len(transformed) > 15:
            pos = random.randint(5, len(transformed) - 5)
            transformed = transformed[:pos] + '\u200D' + transformed[pos:]

        # الطبقة 11: تداخل نمط ثانوي
        if style_idx >= 0 and random.random() < 0.3:
            secondary = random.choice([-1, -2, -4, -5])
            if secondary == -1:
                chars = list(transformed)
                for i, c in enumerate(chars):
                    if c.isalpha() and random.random() < 0.08:
                        chars[i] = c + '\u0336'
                transformed = ''.join(chars)
            elif secondary == -2:
                chars = list(transformed)
                for i, c in enumerate(chars):
                    if c.isalpha() and random.random() < 0.06:
                        chars[i] = c + '\u0332'
                transformed = ''.join(chars)
            elif secondary == -4:
                transformed = self._apply_zalgo(transformed, intensity=1)
            elif secondary == -5:
                transformed = self._apply_homoglyphs(transformed, intensity=0.1)

        # الطبقة 12: بصمة غير مرئية نهائية
        transformed = random.choice(inv_chars) + transformed + random.choice(inv_chars)

        return transformed

    def _get_random_style(self):
        available = list(range(len(self.STYLES)))
        if self._last_style in available and len(available) > 1:
            available.remove(self._last_style)
        available.extend([-1, -2, -3, -4, -5, -6, -7, -8, -9])
        chosen = random.choice(available)
        self._last_style = chosen
        return chosen

    def _extract_protected_segments(self, text):
        protected = []
        for match in re.finditer(r'https?://\S+', text):
            url = match.group().rstrip('\u200B\u200C\u200D\uFEFF\u2060\u2061\u2062\u2063\u00A0\u2009\u202F')
            end_pos = match.start() + len(url)
            protected.append((match.start(), end_pos, url, 'url'))
        for match in re.finditer(r'(?<![a-zA-Z0-9/:.])t\.me/[a-zA-Z0-9_]+', text):
            overlaps = any(match.start() >= p[0] and match.start() < p[1] for p in protected)
            if not overlaps:
                full_url = 'https://' + match.group()
                protected.append((match.start(), match.end(), full_url, 'url'))
        for match in re.finditer(r'@[a-zA-Z0-9_]{3,}', text):
            overlaps = any(match.start() >= p[0] and match.start() < p[1] for p in protected)
            if not overlaps:
                protected.append((match.start(), match.end(), match.group(), 'mention'))
        protected.sort(key=lambda x: x[0])
        clean = []
        for seg in protected:
            if not clean:
                clean.append(seg)
            elif seg[0] >= clean[-1][1]:
                clean.append(seg)
        return clean

    def obfuscate(self, text):
        """التحويل الرئيسي - 45+ نمط + 12 طبقة تشويش"""
        if not text or len(text) < 2:
            return text, False

        all_protected = self._extract_protected_segments(text)
        has_links = any(seg_type in ('url', 'mention') for _, _, _, seg_type in all_protected)

        segments = []
        last_end = 0
        for start, end, original, seg_type in all_protected:
            if start > last_end:
                segments.append(('text', text[last_end:start]))
            segments.append((seg_type, original))
            last_end = end
        if last_end < len(text):
            segments.append(('text', text[last_end:]))

        style_idx = self._get_random_style()
        result_parts = []

        for seg_type, seg_text in segments:
            if seg_type == 'url':
                display = self._create_url_display(seg_text, style_idx)
                display = self._obfuscate_display_text(display, style_idx)
                display = self._escape_html(display)
                result_parts.append(f'<a href="{seg_text}">{display}</a>')
            elif seg_type == 'mention':
                display = self._create_mention_display(seg_text, style_idx)
                display = self._obfuscate_display_text(display, style_idx)
                display = self._escape_html(display)
                username = seg_text[1:]
                result_parts.append(f'<a href="tg://resolve?domain={username}">{display}</a>')
            else:
                transformed = self._apply_style_to_text(seg_text, style_idx)
                transformed = self._escape_html(transformed)
                result_parts.append(transformed)

        final_text = ''.join(result_parts)
        inv_char = random.choice(['\u200B', '\u200C', '\uFEFF'])
        final_text = inv_char + final_text

        return final_text, has_links

    def get_style_name(self, idx=None):
        special_names = {
            -1: 'strikethrough', -2: 'underline', -3: 'inverted',
            -4: 'zalgo', -5: 'homoglyphs', -6: 'greek',
            -7: 'rune', -8: 'upside_down', -9: 'random_combo',
        }
        if idx is None:
            idx = self._last_style
        if idx >= 0 and idx < len(self.STYLES):
            return self.STYLES[idx][0]
        return special_names.get(idx, 'unknown')


yaytext_obfuscator = YayTextMesslettersObfuscator()
