# -*- coding: utf-8 -*-
"""
اختبار شامل v4.3:
1) الوضع اليدوي الصرف: بدون أهداف → لا تغيير إطلاقاً
2) مع أهداف المستخدم → استبدال الهدف فقط وبقية النص كما هو
3) إعلان المستخدم الحقيقي (اعذار طبية + @ppppokl)
4) كيانات Mention صريحة لليوزرات المتبقية
5) الخزنة السحابية: تصدير → مسح → استعادة → مطابقة
6) تكامل المسار الموحد prepare_content_for_sending
"""
import os
import sys
import json
import sqlite3

sys.path.insert(0, '/home/z/my-project')
os.chdir('/home/z/my-project')

PASS = 0
FAIL = 0

def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"✅ {name}")
    else:
        FAIL += 1
        print(f"❌ {name} {detail}")

# ═══════════════════════════════════════
# 1) link_guard: الوضع اليدوي
# ═══════════════════════════════════════
import link_guard as lg

user_ad = ("✅اعذار طبية تطبيق صحتي\n"
           "✅يوم /يومين /اسبوع\n"
           "✅تقرير طبي\n"
           "✅مرافق @ppppokl اتصل 0777123456\n"
           "السعر 1500 ريال\n"
           "قناة: t.me/myshop")

# حالة أ: بدون أهداف - القاعدة الصارمة (ما يضيف شي من عنده)
t, e = lg.apply_link_guard(user_ad)
check("بدون أهداف: النص مطابق 100%", t == user_ad)
check("بدون أهداف: صفر كيانات", e == [])

# حالة ب: هدف واحد @ppppokl
targets = lg.parse_targets("@ppppokl")
check("تطبيع @ppppokl", targets and targets[0]['url'] == 'https://t.me/ppppokl', str(targets))
t, e = lg.apply_link_guard(user_ad, targets=targets)
check("هدف واحد: اليوزر استُبدل", "@ppppokl" not in t and "للطلب اضغط هنا" in t)
check("هدف واحد: الهاتف بقي نصاً (لم يحدده المستخدم)", "0777123456" in t)
check("هدف واحد: الرابط بقي نصاً (لم يحدده المستخدم)", "t.me/myshop" in t)
check("هدف واحد: السعر بقي نصاً", "1500" in t)
check("هدف واحد: كيان واحد t.me/ppppokl", len(e) == 1 and e[0][2] == 'https://t.me/ppppokl')

# حالة ج: كل الأنواع
targets_all = lg.parse_targets("@ppppokl, 0777123456\nt.me/myshop")
check("ثلاثة أهداف مقبولة", len(targets_all) == 3, str(len(targets_all)))
t, e = lg.apply_link_guard(user_ad, targets=targets_all)
check("ثلاثة أهداف: الثلاثة استُبدلت",
      t.count("للطلب اضغط هنا") == 3 and "@ppppokl" not in t and "0777123456" not in t)
urls = sorted(x[2] for x in e)
check("الوجهات صحيحة",
      urls == ['https://t.me/myshop', 'https://t.me/ppppokl', 'https://wa.me/967777123456'], str(urls))

# حالة د: تنويعات الرقم نفسه
for variant in ["+967777123456", "967777123456", "00967777123456"]:
    tg = lg.parse_targets(variant)
    t2, e2 = lg.apply_link_guard(user_ad, targets=tg)
    check(f"مطابقة الرقم بصيغة {variant}", "0777123456" not in t2)

# حالة هـ: إزاحات UTF-16 مع إيموجي ونص عربي
mixed = "✅اعذار طبية 😊 @ppppokl تجربة 0777123456 نهاية"
targets = lg.parse_targets("@ppppokl\n0777123456")
tn, en = lg.apply_link_guard(mixed, targets=targets)
ok_offsets = True
for off, lnn, url in en:
    chunk = tn.encode('utf-16-le')[off*2:(off+lnn)*2].decode('utf-16-le')
    if chunk != "للطلب اضغط هنا":
        ok_offsets = False
        print(f"   إزاحة خاطئة: {chunk!r}")
check("إزاحات UTF-16 دقيقة مع إيموجي", ok_offsets)

# ═══════════════════════════════════════
# 2) كيانات Mention الصريحة
# ═══════════════════════════════════════
text2 = "✅اعذار طبية @ppppokl مرافق @other_user اتصل"
ments = lg.find_clean_mentions(text2)
names = [u for _, _, u in ments]
check("كشف اليوزرين النظيفين", set(names) == {'ppppokl', 'other_user'}, str(names))
ok_u16 = all(text2.encode('utf-16-le')[o*2:(o+l)*2].decode('utf-16-le').startswith('@')
             for o, l, _ in ments)
check("إزاحات Mention بوحدات UTF-16", ok_u16)
# يوزر ملوث بأحرف خفية → يُتجاهل (لا كيان خاطئ)
dirty = "تواصل @p\U000E0100ppokl هنا"
ments2 = lg.find_clean_mentions(dirty)
check("اليوزر الملوث يُتجاهل", all(u != 'ppppokl' for _, _, u in ments2), str(ments2))

# ═══════════════════════════════════════
# 3) الخزنة السحابية (دورة كاملة)
# ═══════════════════════════════════════
import session_vault as sv
import time

TEST_DB = '/home/z/my-project/scripts/test_vault.db'
FAKE_SESSION = "1BQANOTEuMTA4Lnc1Vlc3Rlci1mYWtlLXNlc3Npb24tZGF0YQ"
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)
sv.DB_PATH = TEST_DB

def seed_db():
    conn = sqlite3.connect(TEST_DB)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, "
              "session_string TEXT, phone TEXT, status TEXT DEFAULT 'active', "
              "added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    c.execute("CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, "
              "group_id INTEGER, group_name TEXT, username TEXT, member_count INTEGER, "
              "added_by TEXT, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, "
              "content TEXT, media_path TEXT, msg_type TEXT DEFAULT 'text', media_data TEXT, "
              "created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    c.execute("CREATE TABLE IF NOT EXISTS scheduled_posts (id INTEGER PRIMARY KEY AUTOINCREMENT, "
              "message_id INTEGER, post_time TEXT NOT NULL, repeat_type TEXT DEFAULT 'once', "
              "repeat_interval INTEGER DEFAULT 0, post_mode TEXT DEFAULT 'fast', "
              "status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
              "last_run TEXT DEFAULT NULL, next_run TEXT DEFAULT NULL)")
    c.execute("CREATE TABLE IF NOT EXISTS blacklist (group_id TEXT PRIMARY KEY, group_name TEXT, "
              "added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    fake_session = FAKE_SESSION
    c.execute("INSERT INTO accounts (session_string, phone, status) VALUES (?,?,?)",
              (fake_session, '+967777123456', 'active'))
    c.execute("INSERT INTO groups (group_id, group_name, member_count, added_by) VALUES (?,?,?,?)",
              (-1001234567890, 'مجموعة اختبار', 500, 'account_1'))
    c.execute("INSERT INTO settings (key, value) VALUES ('link_guard_targets', '@ppppokl')")
    c.execute("INSERT INTO messages (content, msg_type) VALUES (?, 'text')",
              ("✅اعذار طبية @ppppokl",))
    conn.commit()
    conn.close()

seed_db()
snap1 = sv.build_snapshot()
check("لقطة: 1 حساب", len(snap1['accounts']) == 1)
check("لقطة: المجموعات", len(snap1['groups']) == 1)
check("لقطة: الإعدادات تحوي الأهداف",
      snap1['settings'].get('link_guard_targets') == '@ppppokl')
check("لقطة: الرسائل", len(snap1['messages']) == 1)

# تشفير/فك
blob = sv.encrypt_data(json.dumps(snap1, ensure_ascii=False).encode())
restored = json.loads(sv.decrypt_data(blob).decode())
check("تشفير وفك اللقطة", restored['accounts'][0]['phone'] == '+967777123456')

# مسح DB ثم استعادة (محاكاة deploy جديد)
os.remove(TEST_DB)
check("استعادة تُرفض بدون حسابات؟ لا - restore_if_empty يعمل على DB فارغ", sv.count_active_accounts() == 0)
sv.restore_snapshot(snap1)
snap2 = sv.build_snapshot()
check("بعد الاستعادة: الحساب عاد", snap2['accounts'] and
      snap2['accounts'][0]['session_string'] == FAKE_SESSION)
check("بعد الاستعادة: الإعدادات عادت",
      snap2['settings'].get('link_guard_targets') == '@ppppokl')
check("بعد الاستعادة: الرسالة عادت", len(snap2['messages']) == 1)
os.remove(TEST_DB)

# ═══════════════════════════════════════
# 4) دورة تصدير حقيقية إلى GitHub (إن توفر توكن)
# ═══════════════════════════════════════
if sv.resolve_github_token():
    seed_db()
    ok, msg = sv.export_to_github()
    check("تصدير سحابي حقيقي", ok, msg)
    print(f"   ↳ {msg}")
    if ok:
        # مسح ثم استعادة من السحابة
        os.remove(TEST_DB)
        r_ok, r_msg = sv.restore_if_empty()
        check("استعادة سحابية حقيقية", r_ok, r_msg)
        print(f"   ↳ {r_msg}")
        os.remove(TEST_DB)
else:
    print("⚠️ لا توكن GitHub - تخطي الاختبار السحابي الحقيقي")

# ═══════════════════════════════════════
# النتيجة
# ═══════════════════════════════════════
print(f"\n{'='*45}")
print(f"النتيجة: {PASS} نجح | {FAIL} فشل")
sys.exit(1 if FAIL else 0)
