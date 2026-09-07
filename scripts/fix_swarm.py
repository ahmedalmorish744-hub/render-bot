#!/usr/bin/env python3
"""إصلاح ghost_swarm_worker: استخدام المسار الموحد + إزالة النصوص الوهمية"""
import re

BOT = '/home/z/my-project/bot.py'
with open(BOT, 'r', encoding='utf-8') as f:
    src = f.read()

# منطقة داخل ghost_swarm_worker: من "try:" بعد الحلقة حتى "use_html = False" قبل edit_hide
pattern = re.compile(
    r"        try:\n"
    r"            new_content = None\n"
    r"            use_html = False\n"
    r"            stealth_on = get_setting\('stealth_obfuscator_enabled', 'on'\) == 'on'\n"
    r"            yaytext_on = get_setting\('yaytext_messletters_obfuscation', 'on'\) == 'on'\n"
    r"[^\n]*\n[^\n]*\n"  # سطر التعليق
    r"(?P<body>.*?)"       # الجسم القديم
    r"            if not new_content:\n"
    r"                neutral = \[[^\]]*\]\n"
    r"                new_content = random\.choice\(neutral\)\n"
    r"                use_html = False\n",
    re.DOTALL
)

new_block = (
    "        try:\n"
    "            new_content = None\n"
    "            use_html = False\n\n"
    "            # 🛡️ v3.0: يستخدم المسار الموحد prepare_content_for_sending\n"
    "            # استخدام الإعلان التالي أو نفس الإعلان بتكويد مختلف\n"
    "            if all_messages and len(all_messages) > 1 and random.random() < 0.5:\n"
    "                other_msgs = [m for m in all_messages if m[1]]\n"
    "                if other_msgs:\n"
    "                    chosen = random.choice(other_msgs)\n"
    "                    raw = chosen[1]\n"
    "                    if raw:\n"
    "                        new_content, use_html = prepare_content_for_sending(raw, group_id)\n"
    "            elif original_raw_content:\n"
    "                new_content, use_html = prepare_content_for_sending(original_raw_content, group_id)\n\n"
    "            if not new_content:\n"
    "                # القاعدة الذهبية: لا نصوص وهمية أبداً - نقطة فقط\n"
    "                new_content = '.'\n"
    "                use_html = False\n"
)

m = pattern.search(src)
if not m:
    print('❌ لم يتم العثور على النمط في ghost_swarm_worker')
    raise SystemExit(1)

# تأكد أننا داخل ghost_swarm_worker (قبل موضع fast_post_to_all_groups)
if m.start() > src.find('async def fast_post_to_all_groups'):
    print('❌ الموضع خارج ghost_swarm_worker!')
    raise SystemExit(1)

src = src[:m.start()] + new_block + src[m.end():]
with open(BOT, 'w', encoding='utf-8') as f:
    f.write(src)
print('✅ تم إصلاح ghost_swarm_worker')
