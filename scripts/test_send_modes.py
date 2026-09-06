"""
اختبار التكامل الكامل - Send Modes مع محتوى واقعي
"""
import sys
sys.path.insert(0, '/home/z/my-project')

from stego_engine import (
    stego_engine, SEND_MODES, parse_spintax_advanced,
    zero_width_hide, zero_width_reveal,
    diacritic_hide, diacritic_reveal, has_spintax
)

print("=" * 70)
print("🧪 اختبار تكامل أوضاع الإرسال مع محتوى إعلاني واقعي")
print("=" * 70)

# محتوى واقعي مثل رسائل الإعلانات
test_messages = [
    "اشترك في قناتنا الحصرية t.me/mychannel عروض اليوم فقط!",
    "{مرحباً|أهلاً|سلام} {بكم|بالجميع} في {قناتنا|مجموعتنا} الجديدة t.me/newchannel",
    "🔥 عرض خاص! خصم 50% على كل المنتجات - زوروا الموقع الآن https://example.com",
    "تطبيقنا الجديد متوفر الآن @myapp - حمّله مجاناً",
]

print("\n1️⃣ اختبار Spintax المتداخل:")
nested = "{مرحباً|أهلاً} {بكم|{بالجميع|معكم}} في {قناتنا|{مجموعتنا|فضائنا}}"
for i in range(4):
    print(f"   [{i+1}] {parse_spintax_advanced(nested)}")

print("\n2️⃣ اختبار الأوضاع على رسائل واقعية:")
for mode in SEND_MODES:
    stego_engine.set_mode(mode)
    print(f"\n   {'─' * 60}")
    print(f"   🎛 الوضع: {mode}")
    msg = test_messages[1]  # الرسالة مع spintax
    result, info = stego_engine.process(msg)
    visible_preview = result[:80].replace('\u200b', '').replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '')
    print(f"   📥 الأصل:    {msg[:70]}")
    print(f"   📤 الناتج:   {visible_preview}...")
    print(f"   📏 الطول:    {len(msg)} → {len(result)}")
    if mode == 'stego':
        revealed = zero_width_reveal(result)
        print(f"   🔍 الكشف:    {'✅ ' + revealed[:60] if revealed else '❌'}")
    elif mode == 'diacritic':
        revealed = diacritic_reveal(result)
        print(f"   🔍 الكشف:    {'✅ ' + revealed[:60] if revealed else '❌ (طبيعي - لا يوجد نص إنجليزي مستخرج)'}")

print("\n3️⃣ اختبار استقرار Zero-Width (10 رسائل):")
stego_engine.set_mode('stego')
all_ok = True
for i in range(10):
    secret = f"رسالة إعلانية رقم {i} - اشترك الآن t.me/test{i}"
    hidden = zero_width_hide(secret)
    revealed = zero_width_reveal(hidden)
    if revealed != secret:
        print(f"   ❌ فشل في المحاولة {i+1}")
        all_ok = False
print(f"   {'✅ كل المحاولات نجحت' if all_ok else '❌ هناك فشل'}")

print("\n4️⃣ اختبار استقرار Diacritic (5 رسائل):")
all_ok = True
for i in range(5):
    secret = f"t.me/channel{i}"
    hidden = diacritic_hide(secret)  # غلاف تلقائي
    revealed = diacritic_reveal(hidden)
    if revealed != secret:
        print(f"   ❌ فشل: {revealed}")
        all_ok = False
print(f"   {'✅ كل المحاولات نجحت' if all_ok else '❌ هناك فشل'}")

print("\n5️⃣ فحص القابلية للقراءة (محاكاة عضو يقرأ):")
stego_engine.set_mode('stego')
result, _ = stego_engine.process(test_messages[0])
# إزالة الأحرف الصفرية - هذا ما يراه العضو فعلياً في تيليجرام
human_view = ''.join(ch for ch in result if ch not in ['\u200b', '\u200c', '\u200d', '\ufeff'])
print(f"   📤 ما يراه العضو في stego: {human_view[:80]}")
print(f"   💡 ملاحظة: العضو يرى نص الغلاف فقط")

stego_engine.set_mode('spintax')
result, _ = stego_engine.process(test_messages[1])
print(f"   📤 ما يراه العضو في spintax: {result[:80]}")
print(f"   💡 نص واضح ومقروء 100%")

print("\n" + "=" * 70)
print("✅ اكتمل الاختبار الشامل!")
