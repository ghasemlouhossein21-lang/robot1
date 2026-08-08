"""
vpn_panel.py
لایه‌ی یکپارچه‌ی پنل VPN — بین دو پنل پشتیبانی‌شده مرزبان (marzban.py) و پاسارگارد
(pasargad.py) بر اساس تنظیم «پنل فعال» (از پنل ادمین قابل‌انتخاب) یکی از این دو را
انتخاب می‌کند.

همه‌جای پروژه که لازم است یک کاربر در پنل ساخته/تمدید/غیرفعال/فعال‌شود باید از
همین‌جا (نه مستقیم از marzban.py یا pasargad.py) استفاده کند تا هروقت ادمین پنل فعال را
تغییر داد، تمام عملیات بدون هیچ تغییری دیگر به سمت پنل جدید بروند.
"""

import database as db
import config
import marzban
import pasargad

ACTIVE_PANEL_SETTING_KEY = "active_vpn_panel"
DEFAULT_PANEL = "marzban"

_PANELS = {
    "marzban": marzban,
    "pasargad": pasargad,
}

PANEL_LABELS = {
    "marzban": "مرزبان (Marzban)",
    "pasargad": "پاسارگارد (PasarGuard)",
}


def available_panels() -> list:
    panels = []
    if config.MARZBAN_ENABLED:
        panels.append("marzban")
    if config.PASARGAD_ENABLED:
        panels.append("pasargad")
    return panels


def active_panel() -> str | None:
    """نام پنل فعلاً فعال را برمی‌گرداند (اگر هیچ پنلی وصل نباشد None)."""
    panels = available_panels()
    if not panels:
        return None
    chosen = db.get_setting(ACTIVE_PANEL_SETTING_KEY, DEFAULT_PANEL)
    if chosen in panels:
        return chosen
    return panels[0]


def set_active_panel(name: str) -> None:
    if name not in _PANELS:
        raise ValueError(f"پنل نامعتبر: {name}")
    db.set_setting(ACTIVE_PANEL_SETTING_KEY, name)


def _active_module():
    name = active_panel()
    if not name:
        return None
    return _PANELS[name]


_NOT_CONNECTED_MSG = "هیچ پنل VPNی به ربات وصل نیست. از بخش «اتصال پنل VPN» در پنل ادمین یکی از پنل‌ها را وصل کنید."


async def test_connection():
    mod = _active_module()
    if mod is None:
        return False, None, _NOT_CONNECTED_MSG
    return await mod.test_connection()


async def get_system_stats():
    mod = _active_module()
    if mod is None:
        return False, None, _NOT_CONNECTED_MSG
    return await mod.get_system_stats()


async def get_templates():
    mod = _active_module()
    if mod is None:
        return False, None, _NOT_CONNECTED_MSG
    return await mod.get_templates()


async def get_template(template_id: int):
    mod = _active_module()
    if mod is None:
        return False, None, _NOT_CONNECTED_MSG
    return await mod.get_template(template_id)


async def create_user_from_template(template_id: int, username: str):
    mod = _active_module()
    if mod is None:
        return False, None, _NOT_CONNECTED_MSG
    return await mod.create_user_from_template(template_id, username)


async def create_user_custom(template_id: int, username: str, volume_gb, days):
    """🆕 مثل create_user_from_template ولی حجم/مدت را مستقیماً از پلن/سفارش می‌گیرد، نه از روی تمپلیت."""
    mod = _active_module()
    if mod is None:
        return False, None, _NOT_CONNECTED_MSG
    return await mod.create_user_custom(template_id, username, volume_gb, days)


async def renew_user(username: str, template_id: int):
    mod = _active_module()
    if mod is None:
        return False, None, _NOT_CONNECTED_MSG
    return await mod.renew_user(username, template_id)


async def renew_user_custom(username: str, volume_gb, days):
    """🆕 تمدید با حجم/مدت دقیق (بدون نیاز به انتخاب تمپلیت)."""
    mod = _active_module()
    if mod is None:
        return False, None, _NOT_CONNECTED_MSG
    return await mod.renew_user_custom(username, volume_gb, days)


async def get_user(username: str):
    mod = _active_module()
    if mod is None:
        return False, None, _NOT_CONNECTED_MSG
    return await mod.get_user(username)


async def disable_user(username: str):
    mod = _active_module()
    if mod is None:
        return False, None, _NOT_CONNECTED_MSG
    return await mod.disable_user(username)


async def enable_user(username: str):
    mod = _active_module()
    if mod is None:
        return False, None, _NOT_CONNECTED_MSG
    return await mod.enable_user(username)


async def revoke_sub(username: str):
    mod = _active_module()
    if mod is None:
        return False, None, _NOT_CONNECTED_MSG
    return await mod.revoke_sub(username)


async def delete_user(username: str):
    mod = _active_module()
    if mod is None:
        return False, None, _NOT_CONNECTED_MSG
    return await mod.delete_user(username)


def extract_link_and_username(payload: dict):
    mod = _active_module()
    if mod is None:
        return None, None
    return mod.extract_link_and_username(payload)


async def warmup_cache():
    """🆕 فیکس سرعت: فقط توکن ادمین و لیست تمپلیت‌های پنل فعال را از قبل در کش تازه نگه می‌دارد
    (فراخوانده‌شده از یک حلقه‌ی پس‌زمینه‌ی دوره‌ای در bot.py). با این کار
    وقتی یک مشتری درخواست ساخت سرویس می‌دهد، تقریباً همیشه هر دو کش (توکن
    و تمپلیت‌ها) از قبل گرم هستند و تنها همان یک درخواست واقعی ساخت (POST /api/user)
    باقی می‌ماند — دقیقاً همان ۲-۳ ثانیه‌ای که کاربر انتظار دارد.
    بی‌ضرر است (مثلاً پنل لحظه‌ای در دسترس نباشد) را بی‌سروصدا رد می‌کند و دفعه‌ی بعدی
    درخواست واقعی مشتری همان مسیر معمولی (توکن/تمپلیت که زمانش رسیده) را طی می‌کند.
    """
    mod = _active_module()
    if mod is None:
        return
    try:
        await mod.get_templates()
    except Exception:
        pass
