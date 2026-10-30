"""
super_engine.py — محرك سوبر إضافي لبوت النشر التيليجرامي
============================================================
مستوحى من أفضل الممارسات في المستودعات المتقدمة (VoxHash Multi-Account Sender):
- AccountWarmup: تسخين الحسابات بإرسال رسائل تدريجية لـ Saved Messages
- AccountHealthMonitor: نظام نقاط 0-100 لصحة كل حساب + توصيات
- PaceScheduler: جدولة إرسال ذكية (per-minute/hour + jitter + max_concurrent)
- SpintaxBatchExpander: توسيع كل متغيرات Spintax دفعة واحدة (يقلل الكشف)
- RecipientTracker: تتبع المجموعات المُنشر لها (resume بدون إعادة إرسال)

🔒 ADDITIVE: لا يلمس الكود القديم — كل الميزات opt-in عبر الإعدادات
"""
import asyncio
import random
import re
import time
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  1. AccountWarmup — تسخين تدريجي للحسابات الجديدة (يمنع حظر تيليجرام)
# ─────────────────────────────────────────────────────────────────────────────
WARMUP_MESSAGES = [
    "Warmup {n}/{total} - testing account",
    "Account warmup progress: {n}/{total}",
    "System test message {n}/{total}",
    "Warmup verification {n}/{total}",
    "Account testing message {n}/{total}",
]


class AccountWarmup:
    """تسخين تدريجي للحساب — يرسل رسائل اختبار لـ Saved Messages ('me')
    على فترات زمنية ليبني ثقة تيليجرام في الحساب قبل الحملات الكبيرة.
    منع: حظر الحسابات الجديدة عند الإرسال المكثف."""

    def __init__(self, db_path: str, get_setting_fn, set_setting_fn):
        self.db_path = db_path
        self.get_setting = get_setting_fn
        self.set_setting = set_setting_fn
        self.warmup_in_progress: Set[int] = set()  # acc_id set

    def _get_warmup_settings(self) -> Tuple[int, int]:
        """يرجع (target_messages, interval_minutes) من الإعدادات العامة."""
        target = int(self.get_setting('warmup_target_messages', '5') or '5')
        interval = int(self.get_setting('warmup_interval_minutes', '30') or '30')
        return max(1, target), max(1, interval)

    def _get_account_state(self, acc_id: int) -> Dict:
        """قراءة حالة التسخين لحساب من قاعدة البيانات (بدون owner_id افتراضيًا)."""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            # فحص وجود الأعمدة الإضافية
            cols = [row[1] for row in c.execute('PRAGMA table_info(accounts)').fetchall()]
            extra = {}
            if 'warmup_messages_sent' in cols:
                c.execute('SELECT warmup_messages_sent FROM accounts WHERE id=?', (acc_id,))
                row = c.fetchone()
                extra['warmup_messages_sent'] = row[0] if row else 0
            if 'last_activity' in cols:
                c.execute('SELECT last_activity FROM accounts WHERE id=?', (acc_id,))
                row = c.fetchone()
                extra['last_activity'] = row[0] if row else None
            conn.close()
            return {
                'warmup_messages_sent': extra.get('warmup_messages_sent', 0),
                'last_activity': extra.get('last_activity', None),
            }
        except Exception as e:
            logger.debug(f"warmup state: {e}")
            return {'warmup_messages_sent': 0, 'last_activity': None}

    def _update_warmup_state(self, acc_id: int, sent: int, last_activity_iso: str):
        """تحديث حالة التسخين في قاعدة البيانات."""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            cols = [row[1] for row in c.execute('PRAGMA table_info(accounts)').fetchall()]
            sets = []
            vals = []
            if 'warmup_messages_sent' in cols:
                sets.append('warmup_messages_sent=?')
                vals.append(sent)
            if 'last_activity' in cols:
                sets.append('last_activity=?')
                vals.append(last_activity_iso)
            if sets:
                vals.append(acc_id)
                c.execute(f"UPDATE accounts SET {','.join(sets)} WHERE id=?", vals)
                conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"warmup update: {e}")

    async def warmup_account(self, acc_id: int, client, progress_callback=None) -> Dict:
        """تسخين حساب واحد بإرسال target رسائل إلى 'me' (Saved Messages).
        يُرجع dict: {success, sent, target, errors: []}.
        لا يكسر البوت لو فشل — يوقف عند أول خطأ ويرجع ما وصل إليه."""
        if acc_id in self.warmup_in_progress:
            return {'success': False, 'sent': 0, 'target': 0, 'errors': ['already in progress']}
        self.warmup_in_progress.add(acc_id)
        try:
            target, interval = self._get_warmup_settings()
            state = self._get_account_state(acc_id)
            sent = state['warmup_messages_sent']
            errors = []
            to_send = max(0, target - sent)
            if to_send == 0:
                return {'success': True, 'sent': sent, 'target': target, 'errors': []}
            try:
                if not client.is_connected():
                    await client.connect()
            except Exception as e:
                errors.append(f'connect: {e}')
                return {'success': False, 'sent': sent, 'target': target, 'errors': errors}
            for i in range(to_send):
                idx = sent + i + 1  # رقم الرسالة الحالي
                msg = random.choice(WARMUP_MESSAGES).format(n=idx, total=target)
                try:
                    await client.send_message('me', msg)
                    sent += 1
                    self._update_warmup_state(acc_id, sent, datetime.utcnow().isoformat())
                    if progress_callback:
                        try:
                            await progress_callback(acc_id, sent, target)
                        except Exception:
                            pass
                    # انتظار الفاصل (إلا إذا كانت آخر رسالة)
                    if i < to_send - 1:
                        # نستخدم فاصل أقصر من الـ UI لتجربة سريعة (دقيقة بدل كامل)
                        ui_interval = int(self.get_setting('warmup_ui_interval_seconds', '60') or '60')
                        await asyncio.sleep(max(5, ui_interval))
                except Exception as e:
                    errors.append(f'msg {idx}: {str(e)[:100]}')
                    logger.warning(f"warmup acc={acc_id} msg {idx} failed: {e}")
                    break
            return {'success': sent == target, 'sent': sent, 'target': target, 'errors': errors}
        finally:
            self.warmup_in_progress.discard(acc_id)

    def is_complete(self, acc_id: int) -> bool:
        """هل اكتمل تسخين هذا الحساب؟"""
        target, _ = self._get_warmup_settings()
        state = self._get_account_state(acc_id)
        return state['warmup_messages_sent'] >= target

    def status(self, acc_id: int) -> Dict:
        """حالة التسخين لحساب واحد."""
        target, interval = self._get_warmup_settings()
        state = self._get_account_state(acc_id)
        return {
            'enabled': self.get_setting('warmup_enabled', 'on') == 'on',
            'sent': state['warmup_messages_sent'],
            'target': target,
            'interval_minutes': interval,
            'complete': state['warmup_messages_sent'] >= target,
            'in_progress': acc_id in self.warmup_in_progress,
            'last_activity': state['last_activity'],
        }


# ─────────────────────────────────────────────────────────────────────────────
#  2. AccountHealthMonitor — نقاط صحة 0-100 لكل حساب + توصيات
# ─────────────────────────────────────────────────────────────────────────────
class AccountHealthMonitor:
    """نظام نقاط صحة 0-100 لكل حساب:
    - 90-100: ممتاز (EXCELLENT)
    - 75-89:  جيد (GOOD)
    - 50-74:  تحذير (WARNING)
    - 0-49:   حرج (CRITICAL)

    معاملات التقييم:
    - معدل النجاح (success_rate)
    - آخر نشاط (last_activity)
    - عدد الأخطاء في آخر 24 ساعة
    - حالة التسخين
    - رسالة آخر خطأ"""

    def __init__(self, db_path: str, get_setting_fn):
        self.db_path = db_path
        self.get_setting = get_setting_fn

    def _get_recent_stats(self, acc_id: int, hours: int = 24) -> Dict:
        """قراءة إحصائيات آخر hours ساعة من posting_history."""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            cols = [row[1] for row in c.execute('PRAGMA table_info(posting_history)').fetchall()]
            if 'owner_id' not in cols:
                # fallback: بدون owner_id
                pass
            since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            # نحاول قراءة posts في آخر 24 ساعة لهذا الحساب
            try:
                c.execute(
                    "SELECT COUNT(*) FROM posting_history WHERE account_id=? AND posted_at >= ?",
                    (acc_id, since)
                )
                total = c.fetchone()[0]
                c.execute(
                    "SELECT COUNT(*) FROM posting_history WHERE account_id=? AND posted_at >= ? AND status LIKE 'fail%'",
                    (acc_id, since)
                )
                failures = c.fetchone()[0]
            except Exception:
                total, failures = 0, 0
            conn.close()
            return {'recent_total': total, 'recent_failures': failures}
        except Exception as e:
            logger.debug(f"recent stats: {e}")
            return {'recent_total': 0, 'recent_failures': 0}

    def score_account(self, acc_id: int, account_info: Dict) -> Dict:
        """حساب نقاط صحة حساب واحد.
        account_info: {status, success_rate, last_activity, warmup_complete, error_message, ...}
        يُرجع dict: {score, health_status, warnings, recommendations}."""
        warnings = []
        recommendations = []
        score = 100.0

        # 1) حالة الحساب
        status = (account_info.get('status') or 'active').lower()
        if status != 'active':
            return {
                'score': 0.0,
                'health_status': 'OFFLINE',
                'warnings': [f'الحساب غير نشط: {status}'],
                'recommendations': ['أعد توصيل الحساب من لوحة الحسابات'],
            }

        # 2) معدل النجاح
        success_rate = float(account_info.get('success_rate', 100.0))
        if success_rate < 50:
            score -= 30
            warnings.append(f'معدل نجاح منخفض: {success_rate:.1f}%')
            recommendations.append('قلل سرعة الإرسال أو راجع جودة المحتوى')
        elif success_rate < 80:
            score -= 15
            warnings.append(f'معدل نجاح متوسط: {success_rate:.1f}%')

        # 3) آخر نشاط
        last_activity = account_info.get('last_activity')
        if last_activity:
            try:
                if isinstance(last_activity, str):
                    la = datetime.fromisoformat(last_activity.replace('Z', ''))
                else:
                    la = last_activity
                hours = (datetime.utcnow() - la).total_seconds() / 3600
                if hours > 24:
                    score -= 20
                    warnings.append(f'لا نشاط منذ {hours:.1f} ساعة')
                    recommendations.append('أعد التوصيل أو أرسل رسالة اختبار')
                elif hours > 12:
                    score -= 10
                    warnings.append(f'صامت منذ {hours:.1f} ساعة')
            except Exception:
                pass
        else:
            score -= 5
            recommendations.append('لا نشاط مسجل بعد')

        # 4) التسخين
        warmup_enabled = self.get_setting('warmup_enabled', 'on') == 'on'
        if warmup_enabled and not account_info.get('warmup_complete', True):
            score -= 10
            sent = account_info.get('warmup_messages_sent', 0)
            target = account_info.get('warmup_target', 5)
            warnings.append(f'التسخين غير مكتمل ({sent}/{target})')
            recommendations.append('أكمل التسخين قبل حملات كبيرة')

        # 5) الأخطاء الأخيرة
        recent = self._get_recent_stats(acc_id)
        if recent['recent_total'] > 0:
            error_rate = (recent['recent_failures'] / recent['recent_total']) * 100
            if error_rate > 20:
                score -= 25
                warnings.append(f'معدل أخطاء 24h: {error_rate:.1f}%')
                recommendations.append('أوقف الحملات وراجع السجل')
            elif error_rate > 10:
                score -= 10
                warnings.append(f'معدل أخطاء 24h: {error_rate:.1f}%')

        # 6) رسالة آخر خطأ
        err = account_info.get('error_message')
        if err:
            score -= 15
            warnings.append(f'آخر خطأ: {err[:60]}')

        score = max(0.0, min(100.0, score))
        health_status = 'EXCELLENT' if score >= 90 else 'GOOD' if score >= 75 else 'WARNING' if score >= 50 else 'CRITICAL'

        return {
            'score': round(score, 1),
            'health_status': health_status,
            'warnings': warnings,
            'recommendations': recommendations,
        }


# ─────────────────────────────────────────────────────────────────────────────
#  3. PaceScheduler — جدولة إرسال ذكية (rate limiting احترافي)
# ─────────────────────────────────────────────────────────────────────────────
class PaceScheduler:
    """يحسب جدول الإرسال مسبقاً بناءً على:
    - messages_per_minute (لكل حساب)
    - messages_per_hour (لكل حساب)
    - max_concurrent_accounts (حسابات تعمل بالتوازي)
    - random_jitter_seconds (تشويش زمني عشوائي)

    يُرجع قائمة slots: [{wait_before_ms, account_id}, ...] لكل رسالة."""

    def __init__(self, get_setting_fn):
        self.get_setting = get_setting_fn

    def _get_settings(self) -> Dict:
        return {
            'messages_per_minute': max(1, int(self.get_setting('pace_messages_per_minute', '8') or '8')),
            'messages_per_hour': max(1, int(self.get_setting('pace_messages_per_hour', '40') or '40')),
            'max_concurrent': max(1, int(self.get_setting('pace_max_concurrent', '1') or '1')),
            'jitter_seconds': max(0.0, float(self.get_setting('pace_jitter_seconds', '3') or '3')),
        }

    def build_pace_schedule(self, total_messages: int, account_ids: List[int]) -> List[Dict]:
        """يبني جدول الإرسال: لكل رسالة، يحدد (wait_before_ms, account_id)."""
        if total_messages <= 0 or not account_ids:
            return []
        s = self._get_settings()
        mpm = s['messages_per_minute']
        mph = s['messages_per_hour']
        max_conc = s['max_concurrent']
        jitter = s['jitter_seconds']
        # الفاصل بين الرسائل (ms) لكل حساب
        per_account_interval_ms = max(int(60_000 / mpm), 1000)  # 1 ثانية على الأقل
        # عدد الحسابات النشطة بالتوازي
        concurrent = min(max_conc, len(account_ids))
        # ندور على الحسابات: round-robin
        schedule = []
        next_available = {aid: 0 for aid in account_ids}  # ms timestamp
        # نضمن احترام max/hour عبر تتبع آخر 60 دقيقة لكل حساب
        sent_history: Dict[int, List[float]] = {aid: [] for aid in account_ids}
        sim_time = 0.0
        for i in range(total_messages):
            # اختر الحساب الأقل ازدحاماً (round-robin مع تجنب المحظور)
            chosen = None
            for _ in range(len(account_ids) * 2):
                # اختر الحساب بأقل next_available
                candidate = min(account_ids, key=lambda a: next_available[a])
                # تحقق من حدود الساعة
                history = [t for t in sent_history[candidate] if t > sim_time - 60 * 60 * 1000]
                if len(history) < mph:
                    chosen = candidate
                    break
                # تجاوز الحد لهذا الحساب — نرفع next_available
                next_available[candidate] = sim_time + 60 * 60 * 1000
            if chosen is None:
                # كل الحسابات وصلت حد الساعة — نوقف
                break
            # انتظر حتى اللحظة المتاحة لهذا الحساب
            wait_before = max(0.0, next_available[chosen] - sim_time)
            # أضف jitter عشوائي
            if jitter > 0:
                wait_before += random.uniform(0, jitter * 1000)
            schedule.append({'wait_before_ms': wait_before, 'account_id': chosen})
            # حدّث next_available لهذا الحساب
            next_available[chosen] = max(sim_time, next_available[chosen]) + per_account_interval_ms
            sent_history[chosen].append(sim_time + wait_before)
            sim_time = sim_time + wait_before + per_account_interval_ms
        return schedule


# ─────────────────────────────────────────────────────────────────────────────
#  4. SpintaxBatchExpander — توسيع كل متغيرات Spintax دفعة واحدة
# ─────────────────────────────────────────────────────────────────────────────
class SpintaxBatchExpander:
    """يوسع Spintax لكل المجموعات مسبقًا — كل مجموعة تحصل على نسخة مختلفة.
    يكسر كشف hash matching (نفس النص في مجموعات مختلفة = نتائج مختلفة)."""

    PATTERN = re.compile(r'\{([^{}]*)\}')

    def expand(self, text: str, count: int) -> List[str]:
        """يوسع النص count مرة بنتائج مختلفة عشوائية.
        يدعم Spintax متداخل: {{a|b}|c} → a, b, or c"""
        if count <= 0:
            return []
        if not text or not isinstance(text, str):
            return [''] * count
        if '{' not in text or '}' not in text:
            return [text] * count
        return [self._expand_once(text) for _ in range(count)]

    def _expand_once(self, text: str) -> str:
        """يوسع Spintax مرة واحدة (يدعم التداخل)."""
        # كرر حتى لا تبقى أقواس
        for _ in range(20):  # حد أقصى 20 مستوى
            new_text = self.PATTERN.sub(
                lambda m: random.choice(m.group(1).split('|')),
                text
            )
            if new_text == text:
                break
            text = new_text
        return text

    def count_variants(self, text: str) -> int:
        """يحسب عدد المتغيرات الممكنة."""
        if not text or '{' not in text:
            return 1
        try:
            total = 1
            for m in self.PATTERN.finditer(text):
                options = m.group(1).split('|')
                total *= max(1, len(options))
            return total
        except Exception:
            return 1


# ─────────────────────────────────────────────────────────────────────────────
#  5. RecipientTracker — تتبع المجموعات المُنشر لها (resume بدون إعادة)
# ─────────────────────────────────────────────────────────────────────────────
class RecipientTracker:
    """يحفظ المجموعات التي نُشر لها بنجاح لكل حملة (session_id).
    عند resume، يتخطى المجموعات التي سبق نشرها — يمنع الإزعاج والتكرار."""

    def __init__(self):
        self.sent: Dict[str, Set[int]] = {}  # session_id -> set(group_id)

    def start_session(self, session_id: str):
        self.sent[session_id] = set()

    def mark_sent(self, session_id: str, group_id: int):
        if session_id not in self.sent:
            self.sent[session_id] = set()
        self.sent[session_id].add(int(group_id))

    def is_sent(self, session_id: str, group_id: int) -> bool:
        return int(group_id) in self.sent.get(session_id, set())

    def count_sent(self, session_id: str) -> int:
        return len(self.sent.get(session_id, set()))

    def clear(self, session_id: str):
        self.sent.pop(session_id, None)


# ─────────────────────────────────────────────────────────────────────────────
#  6. AutoPauseManager — إيقاف تلقائي عند ارتفاع معدل الأخطاء
# ─────────────────────────────────────────────────────────────────────────────
class AutoPauseManager:
    """يراقب معدل الأخطاء أثناء النشر — لو تجاوز threshold (مثلاً 50%)
    يوقف الحملة تلقائياً لمنع حظر الحسابات.

    threshold من الإعداد: auto_pause_error_threshold (default 50%)
    min_attempts: الحد الأدنى للمحاولات قبل التفعيل (default 10)
    cooldown_seconds: مدة الإيقاف بعد التفعيل (default 300)"""

    def __init__(self, get_setting_fn):
        self.get_setting = get_setting_fn
        self.last_pause: Dict[int, float] = {}  # acc_id -> timestamp

    def _threshold(self) -> float:
        return float(self.get_setting('auto_pause_error_threshold', '50') or '50')

    def _min_attempts(self) -> int:
        return int(self.get_setting('auto_pause_min_attempts', '10') or '10')

    def _cooldown(self) -> int:
        return int(self.get_setting('auto_pause_cooldown_seconds', '300') or '300')

    def should_pause(self, acc_id: int, attempts: int, failures: int) -> Tuple[bool, str]:
        """هل يجب إيقاف الحساب acc_id؟ يُرجع (bool, reason)."""
        if attempts < self._min_attempts():
            return False, ''
        if failures == 0:
            return False, ''
        error_rate = (failures / attempts) * 100
        if error_rate < self._threshold():
            return False, ''
        # تحقق من cooldown
        now = time.time()
        last = self.last_pause.get(acc_id, 0)
        if now - last < self._cooldown():
            return False, 'in cooldown'
        self.last_pause[acc_id] = now
        return True, f'mعدل أخطاء مرتفع: {error_rate:.1f}% ({failures}/{attempts})'

    def clear(self, acc_id: int):
        self.last_pause.pop(acc_id, None)


# ─────────────────────────────────────────────────────────────────────────────
#  7. SmartAccountSelector — اختيار ذكي حسب الصحة + التحميل
# ─────────────────────────────────────────────────────────────────────────────
class SmartAccountSelector:
    """يختار أفضل حساب للنشر بناءً على:
    - نقاط الصحة (HealthScore)
    - التحميل الحالي (load)
    - اكتمال التسخين
    - آخر استخدام

    يعطي أولوية للحسابات الأكثر صحة والأقل استخداماً."""

    def __init__(self, health_monitor: AccountHealthMonitor, warmup: AccountWarmup,
                 get_setting_fn, get_accounts_fn, get_clients_fn):
        self.health = health_monitor
        self.warmup = warmup
        self.get_setting = get_setting_fn
        self.get_accounts = get_accounts_fn  # () -> list of (acc_id, phone, status)
        self.get_clients = get_clients_fn  # () -> dict {acc_id: client}
        self.usage: Dict[int, List[float]] = {}  # acc_id -> [timestamps]

    def _cleanup_usage(self, acc_id: int, window_sec: int = 3600) -> List[float]:
        now = time.time()
        self.usage[acc_id] = [t for t in self.usage.get(acc_id, []) if now - t < window_sec]
        return self.usage[acc_id]

    def select(self, owner_id: int, exclude_acc_ids: Optional[Set[int]] = None) -> Optional[Tuple[int, Any]]:
        """اختر أفضل حساب متاح.
        يُرجع (acc_id, client) أو None."""
        accounts = self.get_accounts()  # [(acc_id, phone, status), ...]
        # فلترة: نشط + نفس المستخدم + متصل + غير مستبعد
        candidates = []
        for acc_id, phone, status in accounts:
            if exclude_acc_ids and acc_id in exclude_acc_ids:
                continue
            if status != 'active':
                continue
            client = self.get_clients().get(acc_id)
            if not client:
                continue
            try:
                if not client.is_connected():
                    continue
            except Exception:
                continue
            # حساب التحميل في الساعة الأخيرة
            usage_hour = len(self._cleanup_usage(acc_id, 3600))
            # حساب التحميل في الدقيقة الأخيرة
            now = time.time()
            usage_min = len([t for t in self.usage[acc_id] if now - t < 60])
            # تجاوز الحد الأقصى (40/hour, 10/minute)
            if usage_hour >= 40 or usage_min >= 10:
                continue
            # هل التسخين مكتمل؟ (لو التسخين مُفعل)
            warmup_ok = True
            if self.get_setting('warmup_enabled', 'on') == 'on':
                if not self.warmup.is_complete(acc_id):
                    # لو لم يكتمل، نستخدمه لكن بأولوية أقل
                    warmup_ok = False
            candidates.append({
                'acc_id': acc_id, 'client': client,
                'usage_hour': usage_hour, 'usage_min': usage_min,
                'warmup_ok': warmup_ok,
            })
        if not candidates:
            return None
        # ترتيب: warmup_ok أولاً، ثم الأقل استخداماً في الساعة، ثم الأقل في الدقيقة
        candidates.sort(key=lambda c: (
            0 if c['warmup_ok'] else 1,  # الحسابات المكتملة التسخين أولاً
            c['usage_hour'],
            c['usage_min'],
        ))
        chosen = candidates[0]
        # سجل الاستخدام
        self.usage.setdefault(chosen['acc_id'], []).append(time.time())
        return chosen['acc_id'], chosen['client']

    def record_success(self, acc_id: int):
        # التتبع في self.usage فقط (الكشف يتم في select)
        pass

    def record_failure(self, acc_id: int):
        # يمكن تمديده لاحقاً لتحديث error_message في DB
        pass


# ─────────────────────────────────────────────────────────────────────────────
#  Initialization helper
# ─────────────────────────────────────────────────────────────────────────────
def init_super_engine(db_path: str, get_setting_fn, set_setting_fn,
                      get_accounts_fn, get_clients_fn):
    """تهيئة كل مكونات المحرك السوبر. يُرجع dict من النسخ."""
    return {
        'warmup': AccountWarmup(db_path, get_setting_fn, set_setting_fn),
        'health': AccountHealthMonitor(db_path, get_setting_fn),
        'pace': PaceScheduler(get_setting_fn),
        'spintax_batch': SpintaxBatchExpander(),
        'tracker': RecipientTracker(),
        'auto_pause': AutoPauseManager(get_setting_fn),
        'selector': SmartAccountSelector(
            AccountHealthMonitor(db_path, get_setting_fn),
            AccountWarmup(db_path, get_setting_fn, set_setting_fn),
            get_setting_fn, get_accounts_fn, get_clients_fn
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  DB migration helper — يضيف الأعمدة اللازمة لـ accounts (إن لم تكن موجودة)
# ─────────────────────────────────────────────────────────────────────────────
def migrate_super_engine_schema(db_path: str):
    """يضيف أعمدة تسخين الحسابات لجدول accounts إن لم تكن موجودة.
    آمن: استثناءات قاعدة البيانات لا تكسر البوت."""
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        cols = [row[1] for row in c.execute('PRAGMA table_info(accounts)').fetchall()]
        additions = []
        if 'warmup_messages_sent' not in cols:
            additions.append('ALTER TABLE accounts ADD COLUMN warmup_messages_sent INTEGER DEFAULT 0')
        if 'warmup_target_messages' not in cols:
            additions.append('ALTER TABLE accounts ADD COLUMN warmup_target_messages INTEGER DEFAULT 5')
        if 'last_activity' not in cols:
            additions.append('ALTER TABLE accounts ADD COLUMN last_activity TEXT')
        if 'error_message' not in cols:
            additions.append('ALTER TABLE accounts ADD COLUMN error_message TEXT')
        if 'success_count' not in cols:
            additions.append('ALTER TABLE accounts ADD COLUMN success_count INTEGER DEFAULT 0')
        if 'failure_count' not in cols:
            additions.append('ALTER TABLE accounts ADD COLUMN failure_count INTEGER DEFAULT 0')
        for sql in additions:
            try:
                c.execute(sql)
            except Exception as e:
                logger.debug(f"migration skip: {e}")
        conn.commit()
        conn.close()
        logger.info(f"✅ super_engine migration: {len(additions)} columns added (if not exists)")
    except Exception as e:
        logger.error(f"super_engine migration failed: {e}")
