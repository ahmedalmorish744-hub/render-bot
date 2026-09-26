#!/usr/bin/env python3
"""Patch bot.py: replace is_admin gates with multi-user registration + ban check"""
import re
from pathlib import Path

p = Path('/home/z/my-project/bot.py')
src = p.read_text(encoding='utf-8')

# Pattern 1: simple "if not is_admin(event.sender_id):\n            return"
# Replace with: register_user + ban check + set_current_user
old_simple = """if not is_admin(event.sender_id):
            return"""

new_simple = """set_current_user(event.sender_id)
        try:
            _s = await event.get_sender()
            multiuser.register_user(DB_PATH, event.sender_id,
                                    getattr(_s, 'username', '') or '',
                                    getattr(_s, 'first_name', '') or '',
                                    getattr(_s, 'last_name', '') or '')
        except Exception:
            pass
        if multiuser.is_banned(DB_PATH, event.sender_id):
            await event.respond("🚫 تم حظر حسابك من استخدام البوت.")
            return"""

count1 = src.count(old_simple)
src = src.replace(old_simple, new_simple)
print(f"Pattern 1 (simple return): replaced {count1}")

# Pattern 2: "if not is_admin(event.sender_id):\n            await event.answer(...)\n            return"
# This is for callback_handler
old_with_answer = """if not is_admin(event.sender_id):
            await event.answer("⛔ غير مصرح", alert=True)
            return"""

new_with_answer = """set_current_user(event.sender_id)
        try:
            _s = await event.get_sender()
            multiuser.register_user(DB_PATH, event.sender_id,
                                    getattr(_s, 'username', '') or '',
                                    getattr(_s, 'first_name', '') or '',
                                    getattr(_s, 'last_name', '') or '')
        except Exception:
            pass
        if multiuser.is_banned(DB_PATH, event.sender_id):
            await event.answer("🚫 تم حظر حسابك", alert=True)
            return"""

count2 = src.count(old_with_answer)
src = src.replace(old_with_answer, new_with_answer)
print(f"Pattern 2 (with answer): replaced {count2}")

# Pattern 3: for callback_handler the indentation might be 8 spaces (inside elif chain)
# Actually, the callback_handler is different - it's the @bot.on(events.CallbackQuery)
# Let me check for that
old_callback = """async def callback_handler(event):
        if not is_admin(event.sender_id):
            await event.answer("⛔ غير مصرح", alert=True)
            return"""

# This may have already been replaced; check
if old_callback in src:
    print("Pattern 3 (callback_handler entry) - already partially handled")

# Now handle the special message_handler entry point (different position)
old_msg_handler = """async def message_handler(event):
        if not is_admin(event.sender_id):
            return"""

new_msg_handler = """async def message_handler(event):
        # 👥 v5.0: تسجيل تلقائي + فحص حظر
        set_current_user(event.sender_id)
        try:
            _s = await event.get_sender()
            multiuser.register_user(DB_PATH, event.sender_id,
                                    getattr(_s, 'username', '') or '',
                                    getattr(_s, 'first_name', '') or '',
                                    getattr(_s, 'last_name', '') or '')
        except Exception:
            pass
        if multiuser.is_banned(DB_PATH, event.sender_id):
            await event.respond("🚫 تم حظر حسابك من استخدام البوت.")
            return"""

count3 = src.count(old_msg_handler)
src = src.replace(old_msg_handler, new_msg_handler)
print(f"Pattern 3 (message_handler entry): replaced {count3}")

p.write_text(src, encoding='utf-8')
print("✅ Patched bot.py")
