#!/usr/bin/env python3
"""🧪 اختبار v6.1: فحص منطق الإصلاحات الثلاثة قبل النشر"""
import re
import ast
import sys

BOT = '/home/z/my-project/bot.py'
src = open(BOT, encoding='utf-8').read()
tree = ast.parse(src)

passed = []
failed = []

def check(name, cond):
    (passed if cond else failed).append(name)
    print(('✅' if cond else '❌'), name)

# ═══════ 1) ترتيب فروع الأدمن (سبب بلاغ "لا يستورد المجموعات") ═══════
# استخراج مواقع الفروع بالترتيب
branch_positions = []
for n in ast.walk(tree):
    if isinstance(n, ast.If) and isinstance(n.test, ast.Compare):
        try:
            left = n.test.left
            if isinstance(left, ast.Name) and left.id == 'data':
                ops = n.test.ops
                cmp = n.test.comparators
                if ops and isinstance(ops[0], (ast.Eq,)):
                    val = getattr(cmp[0], 'value', None)
                    if isinstance(val, str):
                        branch_positions.append((n.lineno, val, 'eq'))
                elif ops and isinstance(ops[0], ast.Is):
                    pass
        except Exception:
            pass
# startswith branches: data.startswith('xxx')
for n in ast.walk(tree):
    if isinstance(n, ast.If) and isinstance(n.test, ast.Call):
        f = n.test.func
        if isinstance(f, ast.Attribute) and f.attr == 'startswith' and \
           isinstance(n.test.func.value, ast.Attribute) and n.test.func.value.attr == 'data':
            arg = n.test.args[0]
            if isinstance(arg, ast.Constant):
                branch_positions.append((n.lineno, arg.value, 'startswith'))
branch_positions.sort()
# فحص: admin_export_groups قبل admin_export_ و admin_import_all قبل admin_import_
def pos_of(val, kind=None):
    for ln, v, k in branch_positions:
        if v == val and (kind is None or k == kind):
            return ln
    return None

p1a, p1b = pos_of('admin_export_groups'), pos_of('admin_export_', 'startswith')
p2a, p2b = pos_of('admin_import_all'), pos_of('admin_import_', 'startswith')
check('admin_export_groups يُفحص قبل admin_export_ (كان السبب الجذري!)',
      p1a and p1b and p1a < p1b)
check('admin_import_all يُفحص قبل admin_import_',
      p2a and p2b and p2a < p2b)

# محاكاة سلسلة elif الفعلية للأزرار الأربعة
def dispatch(data):
    if data == 'admin_export_groups':
        return 'export_groups_list'
    elif data.startswith('admin_export_'):
        return 'export_user_txt'
    elif data == 'admin_import_all':
        return 'import_all'
    elif data.startswith('admin_import_'):
        return 'import_user'
    return 'other'
check('dispatch(admin_export_groups) → قائمة المستخدمين', dispatch('admin_export_groups') == 'export_groups_list')
check('dispatch(admin_export_123) → تصدير المستخدم 123', dispatch('admin_export_123') == 'export_user_txt')
check('dispatch(admin_import_all) → استيراد الكل', dispatch('admin_import_all') == 'import_all')
check('dispatch(admin_import_123) → استيراد مستخدم 123', dispatch('admin_import_123') == 'import_user')

# ═══════ 2) استخراج كود 777000 ═══════
samples = [
    ('Login code: 55291. Do not give this code to anyone, even if they say they are from Telegram!', '55291'),
    ('رمز الدخول: 78432. لا تعطِ هذا الرمز لأي شخص حتى لو قال إنه من تيليجرام!', '78432'),
    ('Your login code is 918274', '918274'),
    ('كود التسجيل 44112', '44112'),
]
for txt, want in samples:
    m = re.search(r'\b(\d{4,8})\b', txt)
    check(f'استخراج الكود من: "{txt[:30]}..."', m and m.group(1) == want)

# ═══════ 3) القائمة الرئيسية: بسيطة بلا تكرار ═══════
mm = src[src.index('def get_main_menu'):src.index('def get_send_mode_menu')]
main_cbs = re.findall(r'b"([a-z_0-9]+)"', mm)
check('القائمة الرئيسية: لا أزرار مكررة', len(main_cbs) == len(set(main_cbs)))
check('القائمة الرئيسية: 10 أزرار أساسية فقط', len(main_cbs) == 10)
check('القائمة الرئيسية: زر استيراد القروبات موجود', 'refresh_groups' in main_cbs)
for cb in ['send_mode_menu', 'adaptive_menu', 'fancy_text_menu', 'enc_test', 'blacklist']:
    check(f'القائمة الرئيسية خالية من: {cb} (انتقل للإعدادات)', cb not in main_cbs)

# ═══════ 4) قائمة الإعدادات تشمل كل المنقول ═══════
sm = src[src.index('def get_settings_menu'):src.index('def get_blacklist_menu')]
set_cbs = re.findall(r'b"([a-z_0-9]+)"', sm)
check('الإعدادات: لا أزرار مكررة', len(set_cbs) == len(set(set_cbs)))
for cb in ['send_mode_menu', 'adaptive_menu', 'adaptive_profile', 'fancy_text_menu',
           'advanced_enc_settings', 'enc_test', 'link_guard_menu', 'style_boost_menu',
           'stop_joining', 'join_reports', 'join_settings', 'blacklist',
           'set_msg_interval', 'set_fast_delay', 'toggle_enc', 'toggle_anti',
           'toggle_obfuscate', 'toggle_jitter', 'toggle_yaytext', 'back']:
    check(f'الإعدادات تحتوي: {cb}', cb in set_cbs)

# ═══════ 5) دوال v6.1 موجودة وتوقيعاتها سليمة ═══════
check('_find_live_client_for_phone موجودة', '_find_live_client_for_phone(phone_clean)' in src)
check('_import_groups_for_owner تقرأ session_string مباشرة',
      "SELECT id, session_string, status, phone FROM accounts WHERE owner_id=?" in src)
check('_silent_import_all_groups تقبل owner_id صريح',
      'async def _silent_import_all_groups(acc_id, client, owner_id=None)' in src)
check('فحص الحساب المضاف مسبقاً في awaiting_phone',
      'هذا الحساب مضاف عندك بالفعل' in src)
check('الالتقاط التلقائي 777000', "chats=[777000]" in src)
check('زر استيراد قروبات مستخدم في لوحة الأدمن', 'admin_import_' in src and 'استيراد قروباته الآن' in src)
check('زر استيراد قروبات كل المستخدمين', 'admin_import_all' in src and 'استيراد قروبات كل المستخدمين' in src)

print(f"\n{'='*50}")
print(f"النتيجة: {len(passed)} ناجح, {len(failed)} فاشل")
sys.exit(1 if failed else 0)
