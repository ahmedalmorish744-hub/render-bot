# -*- coding: utf-8 -*-
"""تشخيص فروق المستويات العالية"""
import sys, unicodedata
sys.path.insert(0, '/home/z/my-project')
from adaptive_obfuscation import AdaptiveObfuscationEngine

USER_MSG = "[ إجازة مرضية ﺳﻛﻟﻳف معتمد ] لطلب واتساب: 🌲 خا.، ـااااص @ppppokl"

def strip_inv(t):
    return ''.join(c for c in t if unicodedata.category(c) not in ('Cf', 'Mn'))

norm_orig = unicodedata.normalize('NFKC', USER_MSG)
print(f"الأصلي (مطبّع): {norm_orig!r}")
print(f"طول الأصلي المطبّع: {len(norm_orig)}")

for profile in ['medium', 'aggressive', 'insane']:
    engine = AdaptiveObfuscationEngine(profile=profile)
    # طبقة طبقة لمعرفة المصدر
    from adaptive_obfuscation import (adaptive_spintax, bayes_evade,
        apply_arabic_presentation_forms, apply_tag_chars,
        smart_zw_distribute, apply_nfd_decomposition)
    result = USER_MSG
    layers = [
        ('spintax', lambda t: adaptive_spintax(t, engine.config['spintax_intensity'])),
        ('bayes', lambda t: bayes_evade(t, engine.config['bayes_intensity'])),
        ('arabic_forms', lambda t: apply_arabic_presentation_forms(t, engine.config['arabic_forms'])),
        ('tag_chars', lambda t: apply_tag_chars(t, engine.config['tag_intensity'])),
        ('zw_dist', lambda t: smart_zw_distribute(t, engine.config['zw_density'])),
        ('nfd', lambda t: apply_nfd_decomposition(t, engine.config['nfd_intensity'])),
    ]
    print(f"\n=== {profile} ===")
    for name, fn in layers:
        result = fn(result)
        norm_proc = unicodedata.normalize('NFKC', strip_inv(result))
        if norm_proc != norm_orig:
            # إيجاد أول اختلاف
            for i, (a, b) in enumerate(zip(norm_orig, norm_proc)):
                if a != b:
                    print(f"  ❌ بعد [{name}]: أول فرق عند {i}: أصلي={a!r} (U+{ord(a):04X}) vs معالج={b!r} (U+{ord(b):04X})")
                    print(f"     سياق أصلي: ...{norm_orig[max(0,i-10):i+10]!r}")
                    print(f"     سياق معالج: ...{norm_proc[max(0,i-10):i+10]!r}")
                    break
            else:
                print(f"  ❌ بعد [{name}]: طول مختلف {len(norm_orig)} vs {len(norm_proc)}")
        else:
            print(f"  ✅ [{name}] مطابق")
