"""
keyboards.py
تمام کیبوردهای Inline و Reply ربات. هیچ handlerای نباید خودش InlineKeyboardMarkup
بسازد؛ همه از این فایل صدا زده می‌شوند تا تغییر ظاهر منو در یک‌جا متمرکز باشد.
"""

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton as _RealInlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

import database as db
import bot_info
import vpn_panel
from config import UNIQUEPAY_ENABLED, MARZBAN_ENABLED, PASARGAD_ENABLED, ONLINE_PAYMENT_MIN_AMOUNT


# fix: callback_data محدودیت 64 بایت دارد (محدودیت Telegram Bot API).
# نام دسته/پلن توسط ادمین قابل‌ساخت است و ممکن است طولانی باشد،
# به همین دلیل هر callback_data قبل استفاده از این تابع رد می‌شود.
def _safe_callback_data(data: str) -> str:
    encoded = data.encode("utf-8")
    if len(encoded) <= 64:
        return data
    return encoded[:64].decode("utf-8", errors="ignore")


# fix: به‌جای ویرایش تک‌تک ۱۵۰+ محلی که InlineKeyboardButton ساخته می‌شود،
# یک Wrapper مرکزی می‌سازیم تا callback_data همه‌ی دکمه‌ها همیشه از این تابع
# رد شود و هیچ دکمه‌ای هرگز به‌خاطر طول callback_data توسط تلگرام رد نشود.
def InlineKeyboardButton(*args, **kwargs):
    if kwargs.get("callback_data") is not None:
        kwargs["callback_data"] = _safe_callback_data(kwargs["callback_data"])
    return _RealInlineKeyboardButton(*args, **kwargs)



# ---------------------------------------------------------------------------
# عضویت اجباری
# ---------------------------------------------------------------------------
def join_channels_keyboard(channels):
    buttons = [[InlineKeyboardButton(text=f"📢 {ch['name']}", url=ch["url"], style="primary")] for ch in channels]
    buttons.append([InlineKeyboardButton(text="✅ عضو شدم", callback_data="check_join", style="success")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ---------------------------------------------------------------------------
# منوی پایین صفحه (Reply Keyboard) — همیشه در دسترس کاربر
# ---------------------------------------------------------------------------
def main_reply_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 خرید اشتراک", style="success"), KeyboardButton(text="🎁 تست رایگان", style="success")],
            [KeyboardButton(text="📱 سرویس‌های من", style="primary"), KeyboardButton(text="💰 کیف پول", style="primary")],
            [KeyboardButton(text="👥 دعوت دوستان", style="primary"), KeyboardButton(text="👤 پروفایل من", style="primary")],
            [KeyboardButton(text="👨‍💻 پشتیبانی", style="primary"), KeyboardButton(text="📚 راهنما", style="primary")],
            [KeyboardButton(text="🤝 درخواست نمایندگی", style="danger")],
        ],
        resize_keyboard=True,
        # 🆕 فیکس نهایی: is_persistent=True برگردانده شد تا دکمه‌ی چهارخونه‌ی پنهان/نمایان
        # کردن منو همیشه در کنار صفحه باقی بماند (حتی وقتی که کیبورد تایپ بسته است)،
        # نه فقط وقتی کیبورد تایپ باز باشد.
        is_persistent=True,
    )


def admin_reply_keyboard(orders_enabled: bool | None = None, permissions: set[str] | None = None, is_main_admin: bool = True):
    """Reply keyboard پنل ادمین. برای ادمین فرعی فقط دکمه‌هایی که مجوز دارد نمایش داده می‌شود."""
    def allowed(perm: str) -> bool:
        return is_main_admin or permissions is None or perm in permissions

    if orders_enabled is None:
        try:
            orders_enabled = db.is_orders_enabled()
        except Exception:
            orders_enabled = True
    rows = []
    def add_pair(a_perm, a_btn, b_perm=None, b_btn=None):
        row = []
        if allowed(a_perm): row.append(a_btn)
        if b_btn is not None and allowed(b_perm): row.append(b_btn)
        if row: rows.append(row)

    add_pair("stats", KeyboardButton(text="📊 آمار", style="primary"), "requests", KeyboardButton(text="📥 صف درخواست‌ها", style="primary"))
    add_pair("users", KeyboardButton(text="👥 لیست کاربران", style="primary"), "users", KeyboardButton(text="🔍 جستجوی کاربر", style="primary"))
    add_pair("broadcast", KeyboardButton(text="📢 پیام همگانی", style="primary"), "discounts", KeyboardButton(text="🎟 مدیریت تخفیف", style="primary"))
    add_pair("agency", KeyboardButton(text="🤝 نمایندگی (تخفیف VIP)", style="primary"), "plans", KeyboardButton(text="🗂 دسته‌بندی‌های VIP", style="primary"))
    add_pair("plans", KeyboardButton(text="🎮 دسته‌بندی‌های Gaming", style="primary"), "vpn_panel", KeyboardButton(text="📦 نگاشت پلن‌ها به پنل فعال", style="primary"))
    add_pair("vpn_panel", KeyboardButton(text="🛡️ اتصال پنل پاسارگارد", style="primary"), "vpn_panel", KeyboardButton(text="🔀 انتخاب پنل VPN فعال", style="primary"))
    add_pair("referrals", KeyboardButton(text="🤝 مدیریت دعوت‌ها", style="primary"), "guides", KeyboardButton(text="📚 مدیریت راهنما", style="primary"))
    add_pair("logs", KeyboardButton(text="🦖 لاگ خطاها", style="primary"), "botinfo", KeyboardButton(text="ℹ️ اطلاعات ربات", style="primary"))
    add_pair("stickers", KeyboardButton(text="🎬 استیکرهای منو", style="primary"), "backup", KeyboardButton(text="💾 بکاپ", style="primary"))
    add_pair("settings", KeyboardButton(text="🎁 تنظیم تست رایگان", style="primary"), "settings", KeyboardButton(text="🧩 تنظیم بساز سرویس خودت", style="primary"))
    if allowed("orders_toggle"):
        toggle_btn = (KeyboardButton(text="🔴 خاموش کردن سفارشات", style="danger") if orders_enabled else KeyboardButton(text="🟢 روشن کردن سفارشات", style="success"))
        rows.append([toggle_btn])
    if is_main_admin:
        rows.append([KeyboardButton(text="👮 مدیریت ادمین‌ها", style="danger")])
    if not rows:
        rows = [[KeyboardButton(text="⛔ بدون دسترسی", style="danger")]]
    # 🆕 فیکس نهایی: همان دلیل بالا در main_reply_keyboard — is_persistent=True برگردانده شد
    # تا دکمه‌ی چهارخونه همیشه (حتی بدون بازبودن کیبورد تایپ) در دسترس باشد.
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)


# ---------------------------------------------------------------------------
# 🆕 فیکس گیرکردن FSM: تمام متن‌های ممکنِ دکمه‌های ثابت منوی پایین صفحه (کاربر
# عادی + ادمین اصلی/فرعی، در همه‌ی حالت‌های ممکنِ سوییچ سفارشات/سطح دسترسی) را
# برمی‌گرداند. bot.py از این مجموعه استفاده می‌کند تا تشخیص دهد یک پیام متنی
# واقعاً فشردن یکی از دکمه‌های ثابت منو بوده؛ در آن صورت هر state ناتمام
# (مثلاً «منتظر عکس کیوآرکد» یا «منتظر رسید شارژ کیف پول») پاک می‌شود تا آن
# دکمه بلافاصله توسط handler خودش پردازش شود، نه با تکرار سوال قبلی FSM.
# ---------------------------------------------------------------------------
def all_reply_menu_texts() -> set[str]:
    texts: set[str] = set()

    def collect(markup: ReplyKeyboardMarkup) -> None:
        for row in markup.keyboard:
            for btn in row:
                if getattr(btn, "text", None):
                    texts.add(btn.text)

    collect(main_reply_keyboard())
    collect(admin_reply_keyboard(orders_enabled=True, permissions=None, is_main_admin=True))
    collect(admin_reply_keyboard(orders_enabled=False, permissions=None, is_main_admin=True))
    collect(admin_reply_keyboard(orders_enabled=True, permissions=set(), is_main_admin=False))
    return texts



# ---------------------------------------------------------------------------
# منوی اصلی (Inline) — کاربر عادی
# ---------------------------------------------------------------------------
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 خرید اشتراک", callback_data="plans", style="success")],
        [InlineKeyboardButton(text="🎁 تست رایگان", callback_data="buy_plan_test", style="success")],
        [InlineKeyboardButton(text="📱 سرویس‌های من", callback_data="my_configs", style="primary")],
        [InlineKeyboardButton(text="💰 کیف پول", callback_data="wallet", style="primary")],
        [InlineKeyboardButton(text="👥 دعوت دوستان و کسب درآمد", callback_data="referral", style="primary")],
        [InlineKeyboardButton(text="👤 پروفایل من", callback_data="profile", style="primary")],
        [InlineKeyboardButton(text="👨‍💻 پشتیبانی", callback_data="support", style="primary")],
        [InlineKeyboardButton(text="📚 راهنما", callback_data="user_guides", style="primary")],
       
    ])


def back_button(callback_data: str = "back", text: str = "🏠 بازگشت به منوی اصلی"):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=callback_data, style="danger")]])


def profile_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 کیف پول آزاد", callback_data="wallet_free", style="primary")],
        [InlineKeyboardButton(text="🔒 کیف پول مسدود", callback_data="wallet_locked", style="danger")],
        [InlineKeyboardButton(text="🛒 تاریخچه خرید", callback_data="purchase_history", style="primary")],
        [InlineKeyboardButton(text="📋 تاریخچه تراکنش", callback_data="transactions", style="primary")],
        [InlineKeyboardButton(text="🔗 لینک دعوت اختصاصی", callback_data="referral", style="success")],
        [InlineKeyboardButton(text="🏠 بازگشت به منوی اصلی", callback_data="back", style="danger")],
    ])


def wallet_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 شارژ کیف پول", callback_data="charge", style="success")],
        [InlineKeyboardButton(text="🎟 ثبت کد تخفیف", callback_data="use_discount", style="success")],
        [InlineKeyboardButton(text="📋 تراکنش‌های من", callback_data="transactions", style="primary")],
        [InlineKeyboardButton(text="🏠 بازگشت به منوی اصلی", callback_data="back", style="danger")],
    ])


def charge_amount_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 ۵۰,۰۰۰ تومان", callback_data="charge_50000", style="primary")],
        [InlineKeyboardButton(text="💰 ۱۰۰,۰۰۰ تومان", callback_data="charge_100000", style="primary")],
        [InlineKeyboardButton(text="💰 ۲۰۰,۰۰۰ تومان", callback_data="charge_200000", style="primary")],
        [InlineKeyboardButton(text="💵 مبلغ دلخواه", callback_data="charge_custom", style="primary")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="wallet", style="danger")],
    ])


def charge_payment_method_keyboard(amount: int):
    """انتخاب روش پرداخت برای شارژ کیف پول. دکمه‌ی «پرداخت آنلاین» فقط وقتی
    نمایش داده می‌شود که درگاه فعال باشد و مبلغ بیشتر از
    ONLINE_PAYMENT_MIN_AMOUNT باشد (برای مبالغ مساوی یا کمتر، درگاه آنلاین
    اصلاً پیشنهاد نمی‌شود و فقط کارت‌به‌کارت در دسترس است)."""
    buttons = []
    if UNIQUEPAY_ENABLED and amount > ONLINE_PAYMENT_MIN_AMOUNT:
        buttons.append(
            [InlineKeyboardButton(text="🌐 پرداخت آنلاین (تایید خودکار)", callback_data=f"chargepay_online_{amount}", style="success")]
        )
    buttons.append([InlineKeyboardButton(text="💳 پرداخت کارت به کارت", callback_data=f"chargepay_card_{amount}", style="success")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="charge", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def online_payment_wallet_keyboard(payment_link: str, online_payment_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 پرداخت (کارت به کارت خودکار)", url=payment_link, style="success")],
        [InlineKeyboardButton(text="✅ پرداخت را انجام دادم / بررسی کن", callback_data=f"checkpay_{online_payment_id}", style="success")],
        [InlineKeyboardButton(text="🔙 انصراف", callback_data="wallet", style="danger")],
    ])


def referral_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 بازگشت به منوی اصلی", callback_data="back", style="danger")],
    ])


def support_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎫 ارسال تیکت", callback_data="ticket", style="primary")],
        [InlineKeyboardButton(text="📢 کانال اصلی و پشتیبان", url=bot_info.get_support_url(), style="primary")],
        [InlineKeyboardButton(text="🏠 بازگشت به منوی اصلی", callback_data="back", style="danger")],
    ])


# ---------------------------------------------------------------------------
# سرویس‌ها / خرید اشتراک
# ---------------------------------------------------------------------------
def plans_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 سرور VIP (V2Ray)", callback_data="plans_vip", style="success")],
        [InlineKeyboardButton(text="🌐 سرور Gaming (WireGuard)", callback_data="plans_gaming", style="success")],
        [InlineKeyboardButton(text="✨〰️〰️〰️〰️〰️✨", callback_data="noop")],
        [InlineKeyboardButton(text="🚀 کانفیگ خودتو بساز (ویژه VIP) 🛠", callback_data="cbuild_start", style="primary")],
        [InlineKeyboardButton(text="✨〰️〰️〰️〰️〰️✨", callback_data="noop")],
        [InlineKeyboardButton(text="🏠 بازگشت به منوی اصلی", callback_data="back", style="danger")],
    ])


def custom_build_payment_keyboard():
    buttons = [
        [InlineKeyboardButton(text="👛 پرداخت از کیف پول", callback_data="cbuild_pay_wallet", style="success")],
    ]
    if UNIQUEPAY_ENABLED:
        buttons.append(
            [InlineKeyboardButton(text="🌐 پرداخت آنلاین (تایید خودکار)", callback_data="cbuild_pay_online", style="success")]
        )
    buttons.append([InlineKeyboardButton(text="💳 پرداخت کارت به کارت", callback_data="cbuild_pay_card", style="success")])
    buttons.append([InlineKeyboardButton(text="🔙 انصراف", callback_data="plans", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def custom_build_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 انصراف", callback_data="plans", style="danger")],
    ])


def _plans_keyboard(plans_dict: dict, icon: str, discount_percent: int = 0):
    buttons = []
    for key, plan in plans_dict.items():
        price = plan["price"]
        if discount_percent:
            price = int(price * (1 - discount_percent / 100))
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {plan['name']} — {price:,} تومان",
            callback_data=f"buy_{key}"
        , style="success")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="plans", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def vip_categories_keyboard():
    """مرحله‌ی اول خرید VIP: لیست دسته‌بندی‌ها (بعداً از پنل ادمین می‌توان دسته‌ی
    جدید اضافه کرد؛ همه‌شان اینجا خودکار ظاهر می‌شوند)."""
    buttons = []
    for cat in db.get_vip_categories():
        buttons.append([InlineKeyboardButton(text=f"🚀 {cat['name']}", callback_data=f"vipcat_{cat['key']}", style="primary")])
    if not buttons:
        buttons.append([InlineKeyboardButton(text="😔 فعلاً هیچ دسته‌ای موجود نیست", callback_data="noop", style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="plans", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def vip_category_plans_keyboard(category_key: str, discount_percent: int = 0):
    """مرحله‌ی دوم: پلن‌های داخل یک دسته‌ی VIP خاص."""
    cat = db.get_vip_category(category_key)
    plans = db.get_vip_plans(cat["id"]) if cat else []
    buttons = []
    for plan in plans:
        price = plan["price"]
        if discount_percent:
            price = int(price * (1 - discount_percent / 100))
        buttons.append([InlineKeyboardButton(
            text=f"🚀 {plan['name']} — {price:,} تومان", callback_data=f"buy_{plan['plan_key']}"
        , style="primary")])
    if not buttons:
        buttons.append([InlineKeyboardButton(text="😔 فعلاً هیچ پلنی در این دسته نیست", callback_data="noop", style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به دسته‌بندی‌ها", callback_data="plans_vip", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def gaming_categories_keyboard():
    """مرحله‌ی اول خرید Gaming: لیست دسته‌بندی‌ها (دقیقاً مثل VIP، از پنل ادمین
    قابل مدیریت است)."""
    buttons = []
    for cat in db.get_gaming_categories():
        buttons.append([InlineKeyboardButton(text=f"🎮 {cat['name']}", callback_data=f"gamingcat_{cat['key']}", style="primary")])
    if not buttons:
        buttons.append([InlineKeyboardButton(text="😔 فعلاً هیچ دسته‌ای موجود نیست", callback_data="noop", style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="plans", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def gaming_category_plans_keyboard(category_key: str, discount_percent: int = 0):
    """مرحله‌ی دوم: پلن‌های داخل یک دسته‌ی Gaming خاص."""
    cat = db.get_gaming_category(category_key)
    plans = db.get_gaming_plans(cat["id"]) if cat else []
    buttons = []
    for plan in plans:
        price = plan["price"]
        if discount_percent:
            price = int(price * (1 - discount_percent / 100))
        buttons.append([InlineKeyboardButton(
            text=f"🌐 {plan['name']} — {price:,} تومان", callback_data=f"buy_{plan['plan_key']}"
        , style="primary")])
    if not buttons:
        buttons.append([InlineKeyboardButton(text="😔 فعلاً هیچ پلنی در این دسته نیست", callback_data="noop", style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به دسته‌بندی‌ها", callback_data="plans_gaming", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def all_plans_discount_keyboard(discount_percent: int):
    return _plans_keyboard(db.get_all_plans(), "📅", discount_percent)


def purchase_payment_keyboard(plan_key: str, show_discount: bool = True):
    buttons = [
        [InlineKeyboardButton(text="👛 پرداخت از کیف پول", callback_data=f"pay_wallet_{plan_key}", style="success")],
    ]
    if UNIQUEPAY_ENABLED:
        buttons.append(
            [InlineKeyboardButton(text="🌐 پرداخت آنلاین (تایید خودکار)", callback_data=f"pay_online_{plan_key}", style="success")]
        )
    buttons.append([InlineKeyboardButton(text="💳 پرداخت کارت به کارت", callback_data=f"pay_card_{plan_key}", style="success")])
    if show_discount:
        buttons.append([InlineKeyboardButton(text="🎟 ثبت کد تخفیف", callback_data=f"discount_plan_{plan_key}", style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="plans", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def online_payment_keyboard(payment_link: str, online_payment_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 پرداخت (کارت به کارت خودکار)", url=payment_link, style="primary")],
        [InlineKeyboardButton(text="✅ پرداخت را انجام دادم / بررسی کن", callback_data=f"checkpay_{online_payment_id}", style="success")],
        [InlineKeyboardButton(text="🔙 انصراف", callback_data="plans", style="danger")],
    ])


def insufficient_balance_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 شارژ کیف پول", callback_data="wallet", style="primary")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="plans", style="danger")],
    ])


# ---------------------------------------------------------------------------
# سرویس‌های من
# ---------------------------------------------------------------------------
def my_configs_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 سرویس‌های VIP من", callback_data="my_configs_vip", style="primary")],
        [InlineKeyboardButton(text="🎮 سرویس‌های گیمینگ من", callback_data="my_configs_gaming", style="primary")],
        [InlineKeyboardButton(text="🏠 بازگشت به منوی اصلی", callback_data="back", style="danger")],
    ])


def my_configs_list_keyboard(configs, icon: str, back_callback: str):
    buttons = [
        [InlineKeyboardButton(text=f"{icon} {cfg['plan']}", callback_data=f"viewconfig_{cfg['id']}", style="primary")]
        for cfg in configs
    ]
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data=back_callback, style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def config_detail_keyboard(cfg_id, sub_link_url: str | None = None, has_qr: bool = False, back_callback: str = "my_configs_vip", service_id: str | None = None, disabled: bool = False):
    """کیبورد جزئیات سرویس VIP: تمدید + کیوآرکد + لینک ساب + حذف سرویس."""
    buttons = [
        [InlineKeyboardButton(text="🔁 تمدید سرویس", callback_data=f"renew_{cfg_id}", style="success")],
    ]
    row = []
    if has_qr:
        row.append(InlineKeyboardButton(text="🖼 مشاهده کیوآرکد", callback_data=f"viewqr_{cfg_id}", style="primary"))
    if sub_link_url:
        row.append(InlineKeyboardButton(text="🔗 باز کردن لینک ساب", url=sub_link_url, style="primary"))
    if row:
        buttons.append(row)
    if sub_link_url:
        buttons.append([InlineKeyboardButton(text="🔗 دریافت کانفیگ‌های تکی", callback_data=f"mirrorconfigs_{cfg_id}", style="success")])
    if service_id:
        if disabled:
            buttons.append([InlineKeyboardButton(text="▶️ فعال‌سازی سرویس", callback_data=f"cfgenable_{cfg_id}", style="success")])
        else:
            buttons.append([InlineKeyboardButton(text="⏸ غیرفعال‌سازی سرویس", callback_data=f"cfgdisable_{cfg_id}", style="danger")])
        buttons.append([InlineKeyboardButton(text="🔄 ساخت لینک ساب جدید", callback_data=f"cfgrevokesub_{cfg_id}", style="danger")])
    buttons.append([InlineKeyboardButton(text="🗑 حذف سرویس", callback_data=f"delconfig_{cfg_id}", style="danger")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به سرویس‌های VIP من", callback_data=back_callback, style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def gaming_config_detail_keyboard(cfg_id, sub_link_url: str | None = None, back_callback: str = "my_configs_gaming", service_id: str | None = None, disabled: bool = False):
    """کیبورد جزئیات سرویس گیمینگ: دریافت فایل‌ها + لینک ساب + حذف سرویس."""
    buttons = [
        [InlineKeyboardButton(text="📥 دریافت دوباره فایل‌های کانفیگ", callback_data=f"redownload_{cfg_id}", style="success")],
    ]
    if sub_link_url:
        buttons.append([InlineKeyboardButton(text="🔗 باز کردن لینک ساب", url=sub_link_url, style="primary")])
    if service_id:
        if disabled:
            buttons.append([InlineKeyboardButton(text="▶️ فعال‌سازی سرویس", callback_data=f"cfgenable_{cfg_id}", style="success")])
        else:
            buttons.append([InlineKeyboardButton(text="⏸ غیرفعال‌سازی سرویس", callback_data=f"cfgdisable_{cfg_id}", style="danger")])
        buttons.append([InlineKeyboardButton(text="🔄 ساخت لینک ساب جدید", callback_data=f"cfgrevokesub_{cfg_id}", style="danger")])
    buttons.append([InlineKeyboardButton(text="🗑 حذف سرویس", callback_data=f"delconfig_{cfg_id}", style="danger")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به سرویس‌های گیمینگ من", callback_data=back_callback, style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_delete_config_keyboard(cfg_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله، حذف کن", callback_data=f"delconfirm_{cfg_id}", style="danger")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data=f"viewconfig_{cfg_id}", style="danger")],
    ])


def confirm_disable_service_keyboard(cfg_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله، غیرفعال کن", callback_data=f"cfgdisabledo_{cfg_id}", style="danger")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data=f"viewconfig_{cfg_id}", style="danger")],
    ])


def confirm_revoke_sub_keyboard(cfg_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله، لینک جدید بساز", callback_data=f"cfgrevokesubdo_{cfg_id}", style="danger")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data=f"viewconfig_{cfg_id}", style="danger")],
    ])


def gaming_ready_keyboard(config_id):
    """زیر پیام «کانفیگ شما آماده شد» که بلافاصله بعد از تأیید ادمین ارسال می‌شود."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 دریافت کانفیگ‌های سرویس", callback_data=f"redownload_{config_id}", style="success")],
    ])


# ---------------------------------------------------------------------------
# پنل ادمین
# ---------------------------------------------------------------------------
def admin_panel_menu(orders_enabled: bool = True, permissions: set[str] | None = None, is_main_admin: bool = True):
    """Inline admin panel (دکمه‌های شیشه‌ای). برای ادمین فرعی دکمه‌های بدون مجوز اصلاً نمایش داده نمی‌شود."""
    def allowed(perm: str) -> bool:
        return is_main_admin or permissions is None or perm in permissions

    buttons = []
    def add(text, callback_data, perm, style="primary"):
        if allowed(perm):
            buttons.append([InlineKeyboardButton(text=text, callback_data=callback_data, style=style)])

    add("📊 آمار", "admin_stats", "stats")
    add("📥 صف درخواست‌ها", "admin_request_queue", "requests", "success")
    add("👥 لیست کاربران", "admin_userlist", "users")
    add("🔍 جستجوی حرفه‌ای", "admin_search", "users")
    add("🎟 مدیریت تخفیف", "admin_discount", "discounts")
    add("🤝 نمایندگی (تخفیف VIP)", "admin_agency", "agency")
    add("🗂 دسته‌بندی‌های VIP", "admin_vip_categories", "plans")
    add("🎮 دسته‌بندی‌های Gaming", "admin_gaming_categories", "plans")
    add("📦 نگاشت پلن‌ها به پنل فعال", "admin_marzban", "vpn_panel")
    add("🛡️ اتصال پنل پاسارگارد", "admin_pasargad", "vpn_panel")
    add("🔀 انتخاب پنل VPN فعال", "admin_panel_choose", "vpn_panel")
    add("ℹ️ اطلاعات ربات", "admin_botinfo", "botinfo")
    add("🎬 استیکرهای منو", "admin_stickers", "stickers")
    add("🤝 مدیریت دعوت‌ها", "admin_referrals", "referrals")
    add("📚 مدیریت راهنما", "admin_guides", "guides")
    add("📢 پیام همگانی", "admin_broadcast", "broadcast")
    add("💾 بکاپ", "admin_backup", "backup")
    if is_main_admin:
        buttons.append([InlineKeyboardButton(text="👮 مدیریت ادمین‌ها", callback_data="admin_manage_admins", style="danger")])
    if allowed("orders_toggle"):
        buttons.append([InlineKeyboardButton(text=("🔴 خاموش کردن سفارشات" if orders_enabled else "🟢 روشن کردن سفارشات"), callback_data=("admin_orders_off" if orders_enabled else "admin_orders_on"), style=("danger" if orders_enabled else "success"))])
    if not buttons:
        buttons.append([InlineKeyboardButton(text="⛔ هیچ دسترسی فعالی ندارید", callback_data="noop", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_back_button():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back", style="primary")]])


def admin_userlist_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 مشتریان فعال (خریدکرده)", callback_data="admin_userlist_active", style="success")],
        [InlineKeyboardButton(text="👥 کل کاربران", callback_data="admin_userlist_all", style="primary")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back", style="primary")],
    ])


def admin_discount_menu(discounts: list | None = None):
    buttons = []
    for d in (discounts or []):
        value_text = f"{d['amount']:,}ت" if d.get("discount_type") == "amount" else f"{d['percent']}٪"
        buttons.append([InlineKeyboardButton(
            text=f"🎟 {d['code']} | {value_text} | 🔁 {d['uses']}",
            callback_data=f"discdetail_{d['id']}", style="primary",
        )])
    buttons.append([InlineKeyboardButton(text="➕ ساخت کد تخفیف جدید", callback_data="new_discount", style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def discount_detail_keyboard(discount_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💯 ویرایش مقدار تخفیف", callback_data=f"discedit_value_{discount_id}", style="primary")],
        [InlineKeyboardButton(text="👤 ویرایش کاربران مجاز", callback_data=f"discedit_users_{discount_id}", style="primary")],
        [InlineKeyboardButton(text="🎯 ویرایش پلن‌های مجاز", callback_data=f"discedit_plans_{discount_id}", style="primary")],
        [InlineKeyboardButton(text="🔁 ویرایش تعداد استفاده", callback_data=f"discedit_uses_{discount_id}", style="success")],
        [InlineKeyboardButton(text="💰 ویرایش حداقل مبلغ سفارش", callback_data=f"discedit_minorder_{discount_id}", style="primary")],
        [InlineKeyboardButton(text="🔂 ویرایش سقف استفاده هر کاربر", callback_data=f"discedit_maxuser_{discount_id}", style="primary")],
        [InlineKeyboardButton(text="⏰ ویرایش تاریخ انقضا", callback_data=f"discedit_expiry_{discount_id}", style="primary")],
        [InlineKeyboardButton(text="🗑 حذف کد تخفیف", callback_data=f"discdelete_{discount_id}", style="danger")],
        [InlineKeyboardButton(text="🔙 بازگشت به لیست", callback_data="admin_discount", style="primary")],
    ])


def discount_delete_confirm_keyboard(discount_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله، حذف کن", callback_data=f"discdeleteconfirm_{discount_id}", style="danger")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data=f"discdetail_{discount_id}", style="danger")],
    ])


def admin_user_actions_keyboard(uid: str, is_blocked: bool = False, show_pm_link: bool = True):
    block_btn = (
        InlineKeyboardButton(text="✅ رفع مسدودیت کاربر", callback_data=f"toggleblock_{uid}", style="success")
        if is_blocked else
        InlineKeyboardButton(text="🚫 مسدود کردن کاربر", callback_data=f"toggleblock_{uid}", style="danger")
    )
    pm_row = [InlineKeyboardButton(text="✉️ پیام خصوصی به کاربر", callback_data=f"pm_{uid}", style="primary")]
    # دکمه‌ی "رفتن به پیوی کاربر" (لینک tg://user) برای برخی کاربران با تنظیمات حریم‌خصوصی محدودتر
    # توسط تلگرام رد می‌شود، پس handlers/admin.py در صورت خطای BUTTON_USER_PRIVACY_RESTRICTED همین کیبورد را با
    # show_pm_link=False دوباره می‌سازد تا فقط همین دکمه حذف شود.
    if show_pm_link:
        pm_row.append(InlineKeyboardButton(text="💬 رفتن به پیوی کاربر", url=f"tg://user?id={uid}", style="primary"))
    return InlineKeyboardMarkup(inline_keyboard=[
        pm_row,
        [InlineKeyboardButton(text="💰 شارژ دستی", callback_data=f"custom_{uid}", style="primary")],
        [InlineKeyboardButton(text="📒 حسابداری کاربر (تراکنش‌ها/منشأ پول)", callback_data=f"accounting_{uid}_0", style="primary")],
        [InlineKeyboardButton(text="🚀 ارسال کانفیگ VIP (QR)", callback_data=f"sendvip_{uid}", style="primary")],
        [InlineKeyboardButton(text="🎮 ارسال کانفیگ گیمینگ", callback_data=f"sendgaming_{uid}", style="primary")],
        [InlineKeyboardButton(text="📦 مشاهده و مدیریت سرویس‌های کاربر", callback_data=f"svcs_{uid}", style="primary")],
        [block_btn],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back", style="primary")],
    ])


def admin_pm_cancel_keyboard(uid: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ انصراف از پیام خصوصی", callback_data=f"useropen_{uid}", style="danger")],
    ])


def admin_charge_approval_keyboard(uid: str, amount: int, receipt_id: int):
    # 🐛 فیکس: قبلاً callback_data فقط uid+amount بود که برای دو رسید متفاوت با همان مبلغ
    # یکسان می‌شد و قفل دائمی ضدتکرار (claim_admin_action) بعد از اولین بار همیشه برای
    # همان کاربر+مبلغ پیام «قبلاً پردازش شده» می‌داد. اضافه‌کردن receipt_id هر دکمه
    # را منحصربه‌فرد می‌کند.
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ تأیید {amount:,}", callback_data=f"approve_{uid}_{amount}_{receipt_id}", style="success")],
        [InlineKeyboardButton(text="💵 مبلغ دلخواه", callback_data=f"custom_{uid}", style="primary")],
        [InlineKeyboardButton(text="❌ رد", callback_data=f"reject_{uid}_{receipt_id}", style="danger")],
    ])


def admin_purchase_card_approval_keyboard(uid: str, plan_key: str, price: int, receipt_id: int):
    # 🐛 فیکس: همان دلیل بالا — receipt_id را اضافه می‌کنیم تا دو رسید برای همان کاربر/پلن/قیمت با هم تداخل نکنند.
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ تأیید پرداخت ({price:,} ت)", callback_data=f"approvepay|{uid}|{plan_key}|{price}|{receipt_id}", style="success")],
        [InlineKeyboardButton(text="❌ رد رسید", callback_data=f"rejectpay|{uid}|{receipt_id}", style="danger")],
    ])


def admin_purchase_notify_keyboard(uid: str, plan_key: str | None = None, order_id: int | None = None):
    suffix = f"|{order_id}" if order_id else ""
    oid = order_id or 0

    # اگر پنل مرزبان فعال است، این پلن VIP باشد (نه Gaming) و برای دسته‌بندی‌اش
    # یک planSlug نگاشت شده باشد، دکمه‌ی «ارسال خودکار از پنل» هم علاوه‌بر روش
    # دستی (که هیچ تغییری نکرده) نمایش داده می‌شود؛ انتخاب نهایی همیشه با ادمین
    # است. Gaming عمداً اینجا کنار گذاشته شده: طبق تصمیم صریح، بخش گیمینگ
    # کاملاً جداست و همیشه ۱۰۰٪ دستی باقی می‌ماند و هرگز دکمه‌ی خودکار نمی‌گیرد.
    is_gaming = bool(plan_key) and db.plan_type(plan_key) == "gaming"
    auto_row = []
    if vpn_panel.active_panel() and plan_key and not is_gaming:
        mapping = db.get_marzban_plan_map_for_plan_key(plan_key)
        if mapping:
            auto_row = [[InlineKeyboardButton(
                text="📤 ارسال خودکار از پنل فعال", callback_data=f"marzbansend|{uid}|{plan_key}|{oid}"
            , style="primary")]]

    if is_gaming:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎮 ارسال کانفیگ گیمینگ", callback_data=f"sendgaming_{uid}{suffix}", style="primary")],
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 ارسال کانفیگ VIP (QR) — دستی", callback_data=f"sendvip_{uid}{suffix}", style="primary")],
        *auto_row,
    ])


def admin_custom_order_card_approval_keyboard(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ تأیید پرداخت", callback_data=f"approvecustom_{order_id}", style="success")],
        [InlineKeyboardButton(text="❌ رد رسید", callback_data=f"rejectcustom_{order_id}", style="danger")],
    ])


def admin_custom_order_notify_keyboard(order_id: int):
    buttons = [
        [InlineKeyboardButton(text="📤 شروع ارسال کانفیگ — دستی", callback_data=f"sendcustomorder_{order_id}", style="primary")],
    ]
    if vpn_panel.active_panel():
        buttons.append([InlineKeyboardButton(
            text="🧩 ساخت خودکار از پنل فعال (کانفیگ خودتو بساز)",
            callback_data=f"marzbancustom_{order_id}", style="primary",
        )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_gaming_files_done_keyboard(callback_data: str = "gamingfiles_done"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ پایان ارسال فایل‌ها", callback_data=callback_data, style="success")],
    ])


def config_delivery_keyboard(guide_url: str):
    buttons = []
    if guide_url and guide_url.strip().lower().startswith(("http://", "https://")):
        buttons.append([InlineKeyboardButton(text="🧑‍🦯 دریافت روش اتصال", url=guide_url, style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None


def ticket_reply_keyboard(uid: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ پاسخ", callback_data=f"replyticket_{uid}", style="primary")],
    ])


# ---------------------------------------------------------------------------
# 📦 مدیریت سرویس‌های کاربران توسط ادمین
# ---------------------------------------------------------------------------
def admin_services_list_keyboard(configs, uid: str):
    buttons = []
    for cfg in configs:
        icon = "🚀" if cfg.get("type", "vip") == "vip" else "🎮"
        mark = "❌ " if cfg.get("deleted") else ""
        buttons.append([InlineKeyboardButton(
            text=f"{mark}{icon} {cfg['plan']}", callback_data=f"svcdetail_{cfg['id']}"
        , style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"useractions_{uid}", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_service_detail_keyboard(cfg: dict, uid: str):
    cfg_id = cfg["id"]
    is_deleted = bool(cfg.get("deleted"))
    is_vip = cfg.get("type", "vip") == "vip"
    buttons = []

    if is_deleted:
        buttons.append([InlineKeyboardButton(text="♻️ بازگردانی سرویس", callback_data=f"svcrestore_{cfg_id}", style="primary")])
        buttons.append([InlineKeyboardButton(text="🗑 حذف همیشگی (غیرقابل بازگشت)", callback_data=f"svcpurge_{cfg_id}", style="danger")])
    else:
        buttons.append([InlineKeyboardButton(text="✏️ تغییر لینک ساب", callback_data=f"svcedit_link_{cfg_id}", style="primary")])
        if is_vip:
            buttons.append([InlineKeyboardButton(text="🖼 تغییر عکس کیوآرکد", callback_data=f"svcedit_qr_{cfg_id}", style="primary")])
        else:
            buttons.append([InlineKeyboardButton(text="📁 مدیریت فایل‌های کانفیگ", callback_data=f"svcfiles_{cfg_id}", style="primary")])

        if cfg.get("source") in ("marzban", "pasargad") and cfg.get("service_id"):
            buttons.append([InlineKeyboardButton(text="🔁 تمدید از پنل", callback_data=f"marzbanrenew_{cfg_id}", style="success")])
            buttons.append([InlineKeyboardButton(text="⏸ غیرفعال‌کردن در پنل", callback_data=f"marzbandisable_{cfg_id}", style="danger")])
            buttons.append([InlineKeyboardButton(text="▶️ فعال‌کردن در پنل", callback_data=f"marzbanenable_{cfg_id}", style="primary")])
            buttons.append([InlineKeyboardButton(text="🔄 ساخت لینک ساب جدید (خودکار از پنل)", callback_data=f"svcrevokesub_{cfg_id}", style="danger")])

        buttons.append([InlineKeyboardButton(text="🗑 حذف سرویس (مخفی از کاربر)", callback_data=f"svcdelete_{cfg_id}", style="danger")])

    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به لیست سرویس‌ها", callback_data=f"svcs_{uid}", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_gaming_files_manage_keyboard(cfg_id: int, files: list[dict]):
    buttons = []
    for f in files:
        label = f.get("file_name") or "فایل"
        if f.get("caption"):
            label += f" ({f['caption']})"
        buttons.append([InlineKeyboardButton(text=f"🗑 {label}", callback_data=f"svcfiledel_{f['id']}_{cfg_id}", style="primary")])
    buttons.append([InlineKeyboardButton(text="➕ افزودن فایل جدید", callback_data=f"svcaddfile_{cfg_id}", style="success")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"svcdetail_{cfg_id}", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_purge_confirm_keyboard(cfg_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله، برای همیشه حذف کن", callback_data=f"svcpurgeconfirm_{cfg_id}", style="danger")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data=f"svcdetail_{cfg_id}", style="danger")],
    ])


def admin_request_queue_menu(order_count: int = 0, receipt_count: int = 0):
    order_label = f"📦 سفارش‌های در انتظار ({order_count})" if order_count else "📦 سفارش‌های در انتظار"
    receipt_label = f"🧾 رسیدهای در انتظار تایید ({receipt_count})" if receipt_count else "🧾 رسیدهای در انتظار تایید"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=order_label, callback_data="admin_order_queue", style="primary")],
        [InlineKeyboardButton(text=receipt_label, callback_data="admin_pending_receipts", style="primary")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back", style="primary")],
    ])


def admin_pending_receipts_keyboard(receipts, custom_receipts):
    """receipts: ردیف‌های جدول pending_receipts (kind='charge' یا 'plan_card').
    custom_receipts: ردیف‌های custom_orders با status='pending' (بساز سرویس خودت)."""
    buttons = []
    for r in receipts:
        # 🐛 فیکس: r["id"] (شناسه‌ی خود ردیف pending_receipts) را هم در callback_data می‌فرستیم تا در
        # صف رسیدهای در انتظار هم که کاربر/مبلغشان یکسان است، قفل ضدتکرار با هم تداخل نکند.
        if r["kind"] == "charge":
            label = f"💰 شارژ {r['amount']:,} ت — {r['telegram_id']}"
            buttons.append([
                InlineKeyboardButton(text=f"✅ {label}", callback_data=f"approve_{r['telegram_id']}_{r['amount']}_{r['id']}", style="success"),
                InlineKeyboardButton(text="❌", callback_data=f"reject_{r['telegram_id']}_{r['id']}", style="danger"),
            ])
        else:  # plan_card
            label = f"💳 {r['label']} — {r['amount']:,} ت — {r['telegram_id']}"
            buttons.append([
                InlineKeyboardButton(text=f"✅ {label}", callback_data=f"approvepay|{r['telegram_id']}|{r['extra']}|{r['amount']}|{r['id']}", style="success"),
                InlineKeyboardButton(text="❌", callback_data=f"rejectpay|{r['telegram_id']}|{r['id']}", style="danger"),
            ])
    for co in custom_receipts:
        buttons.append([
            InlineKeyboardButton(
                text=f"🛠 سفارشی {co['volume_gb']}GB/{co['days']}روز — {co['price']:,} ت",
                callback_data=f"approvecustom_{co['id']}",
                style="success",
            ),
            InlineKeyboardButton(text="❌", callback_data=f"rejectcustom_{co['id']}", style="danger"),
        ])
    if receipts or custom_receipts:
        buttons.append([InlineKeyboardButton(text="🧹 علامت‌گذاری همه به‌عنوان بررسی‌شده", callback_data="clearreceipts_confirm", style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_request_queue", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_clear_receipts_confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله، همه رو علامت بزن", callback_data="clearreceipts_do", style="danger")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data="admin_pending_receipts", style="danger")],
    ])


def admin_order_queue_keyboard(orders, custom_orders):
    """orders: هر آیتم باید کلید 'telegram_id' هم داشته باشد (توسط admin.py قبل از صدا زدن اضافه می‌شود)."""
    buttons = []
    for o in orders:
        icon = "🎮" if o["order_type"] == "gaming" else "🚀"
        prefix = "sendgaming" if o["order_type"] == "gaming" else "sendvip"
        buttons.append([
            InlineKeyboardButton(
                text=f"{icon} {o['plan_name']} — {o['price']:,} ت",
                callback_data=f"{prefix}_{o['telegram_id']}|{o['id']}", style="primary",
            ),
            InlineKeyboardButton(text="🗑", callback_data=f"dismissorder_{o['id']}", style="danger"),
        ])
    for co in custom_orders:
        buttons.append([
            InlineKeyboardButton(
                text=f"🛠 سفارش سفارشی #{co['id']} — {co['volume_gb']}GB/{co['days']}روز",
                callback_data=f"sendcustomorder_{co['id']}", style="primary",
            ),
            InlineKeyboardButton(text="🗑", callback_data=f"dismisscustomorder_{co['id']}", style="danger"),
        ])
    if orders or custom_orders:
        buttons.append([InlineKeyboardButton(text="🧹 پاک کردن همه‌ی سفارش‌های این صف", callback_data="clearorders_confirm", style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_request_queue", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_clear_orders_confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله، همه رو پاک کن", callback_data="clearorders_do", style="danger")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data="admin_order_queue", style="danger")],
    ])


# ---------------------------------------------------------------------------
# 👥 لیست کاربران با صفحه‌بندی ۱۰تا۱۰تا (مرتب‌شده بر اساس بیشترین خرید)
# ---------------------------------------------------------------------------
def admin_userlist_page_keyboard(users: list, page: int, has_next: bool, list_kind: str = "active"):
    buttons = []
    for u in users:
        buttons.append([InlineKeyboardButton(
            text=f"👤 {u['name']} | 🆔 {u['telegram_id']} | 🛒 {u['total_purchase']:,} ت",
            callback_data=f"useropen_{u['telegram_id']}", style="primary",
        )])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ صفحه قبل", callback_data=f"userpage_{list_kind}_{page - 1}", style="primary"))
    if has_next:
        nav_row.append(InlineKeyboardButton(text="➡️ صفحه بعد", callback_data=f"userpage_{list_kind}_{page + 1}", style="primary"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_userlist", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ---------------------------------------------------------------------------
# 📚 راهنما و اموزش — فهرست قابل‌رشد از پنل ادمین (متن/عکس/فیلم)
# ---------------------------------------------------------------------------
def user_guides_menu(guides: list):
    if not guides:
        buttons = []
    else:
        buttons = [
            [InlineKeyboardButton(text=f"📖 {g['title']}", callback_data=f"guideopen_{g['id']}", style="primary")]
            for g in guides
        ]
    buttons.append([InlineKeyboardButton(text="🏠 بازگشت به منوی اصلی", callback_data="back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def user_guide_detail_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت به لیست راهنما", callback_data="user_guides", style="primary")],
    ])


def admin_guides_menu(guides: list):
    buttons = []
    for i, g in enumerate(guides):
        buttons.append([InlineKeyboardButton(text=f"📖 {g['title']}", callback_data=f"guideadminopen_{g['id']}", style="primary")])
    buttons.append([InlineKeyboardButton(text="➕ افزودن راهنما/اموزش جدید", callback_data="guidenew", style="success")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_guide_detail_keyboard(guide_id: int, index: int, total: int):
    move_row = []
    if index > 0:
        move_row.append(InlineKeyboardButton(text="⬆️ بالاتر", callback_data=f"guidemove_{guide_id}_up", style="primary"))
    if index < total - 1:
        move_row.append(InlineKeyboardButton(text="⬇️ پایین‌تر", callback_data=f"guidemove_{guide_id}_down", style="primary"))
    buttons = [move_row] if move_row else []
    buttons += [
        [InlineKeyboardButton(text="✏️ ویرایش عنوان", callback_data=f"guideeditname_{guide_id}", style="primary")],
        [InlineKeyboardButton(text="📝 ویرایش محتوا (متن/عکس/فیلم)", callback_data=f"guideeditcontent_{guide_id}", style="primary")],
        [InlineKeyboardButton(text="🗑 حذف این راهنما", callback_data=f"guidedelete_{guide_id}", style="danger")],
        [InlineKeyboardButton(text="🔙 بازگشت به لیست راهنما", callback_data="admin_guides", style="primary")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_guide_delete_confirm_keyboard(guide_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله، حذف کن", callback_data=f"guidedeleteconfirm_{guide_id}", style="danger")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data=f"guideadminopen_{guide_id}", style="danger")],
    ])


def admin_guide_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ انصراف", callback_data="admin_guides", style="danger")],
    ])


def admin_stickers_menu(sections: list[dict]):
    """sections: [{"key": ..., "label": ..., "status_emoji": ...}, ...]"""
    buttons = [
        [InlineKeyboardButton(
            text=f"{s['status_emoji']} {s['label']}",
            callback_data=f"stickeropen_{s['key']}",
            style="primary",
        )]
        for s in sections
    ]
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_sticker_detail_keyboard(section_key: str, has_custom: bool, is_enabled: bool):
    buttons = [
        [InlineKeyboardButton(text="📤 آپلود/تغییر استیکر", callback_data=f"stickerset_{section_key}", style="success")],
    ]
    if is_enabled:
        buttons.append([InlineKeyboardButton(text="🛑 غیرفعال کردن (بدون استیکر)", callback_data=f"stickeroff_{section_key}", style="danger")])
    else:
        buttons.append([InlineKeyboardButton(text="✅ فعال‌سازی دوباره", callback_data=f"stickeron_{section_key}", style="success")])
    if has_custom:
        buttons.append([InlineKeyboardButton(text="♻️ بازگرداندن به پیش‌فرض", callback_data=f"stickerreset_{section_key}", style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به لیست بخش‌ها", callback_data="admin_stickers", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_sticker_cancel_keyboard(section_key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ انصراف", callback_data=f"stickeropen_{section_key}", style="danger")],
    ])


def admin_error_logs_keyboard(logs: list):
    buttons = []
    for log in logs:
        ts = str(log.get("occurred_at") or "")[:16]
        buttons.append([InlineKeyboardButton(
            text=f"⚠️ {ts} | {log['error_type']}",
            callback_data=f"errlogdetail_{log['id']}", style="danger",
        )])
    if logs:
        buttons.append([InlineKeyboardButton(text="🗑 این لاگ پاک‌سازیشون", callback_data="errlogclear", style="danger")])
    buttons.append([InlineKeyboardButton(text="🔄 به‌روزرسانی", callback_data="errlogrefresh", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_error_log_detail_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت به لیست لاگ‌ها", callback_data="errlogrefresh", style="primary")],
    ])


def admin_error_logs_clear_confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله، پاکشون", callback_data="errlogclearconfirm", style="danger")],
        [InlineKeyboardButton(text="❌ انصراف", callback_data="errlogrefresh", style="danger")],
    ])


def admin_referrers_page_keyboard(users: list, page: int, has_next: bool):
    buttons = []
    for u in users:
        buttons.append([InlineKeyboardButton(
            text=f"🤝 {u['name']} | 👥 دعوت: {u['invited_count']} | ✅ موفق: {u['successful_invites']}",
            callback_data=f"refdetail_{u['telegram_id']}_{page}", style="primary",
        )])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ صفحه قبل", callback_data=f"refpage_{page - 1}", style="primary"))
    if has_next:
        nav_row.append(InlineKeyboardButton(text="➡️ صفحه بعد", callback_data=f"refpage_{page + 1}", style="primary"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_referred_detail_keyboard(referrer_uid: str, back_page: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 مشاهدهی کامل کاربر دعوت‌کننده", callback_data=f"useropen_{referrer_uid}", style="primary")],
        [InlineKeyboardButton(text="🔙 بازگشت به لیست دعوت‌کنندگان", callback_data=f"refpage_{back_page}", style="primary")],
    ])


def admin_accounting_keyboard(uid: str, page: int, has_next: bool):
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ قبل", callback_data=f"accounting_{uid}_{page - 1}", style="primary"))
    if has_next:
        nav_row.append(InlineKeyboardButton(text="➡️ بعد", callback_data=f"accounting_{uid}_{page + 1}", style="primary"))
    buttons = [nav_row] if nav_row else []
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به کاربر", callback_data=f"useropen_{uid}", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ---------------------------------------------------------------------------
# 🎟 ساخت کد تخفیف — نوع تخفیف و پلن‌های قابل‌اعمال
# ---------------------------------------------------------------------------
def discount_type_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💯 درصدی", callback_data="disctype_percent", style="primary")],
        [InlineKeyboardButton(text="💵 مبلغ ثابت (تومان)", callback_data="disctype_amount", style="primary")],
    ])


def discount_plans_select_keyboard(selected: list):
    """با هر بار زدن روی یک پلن، انتخاب/عدم‌انتخابش toggle می‌شود؛ ✅ همه یعنی روی همه‌ی پلن‌ها اعمال شود."""
    buttons = [[InlineKeyboardButton(
        text="✅ همه‌ی پلن‌ها (بدون محدودیت)" if not selected else "☑️ همه‌ی پلن‌ها (بدون محدودیت)",
        callback_data="discplan_all", style="success",
    )]]
    for key, plan in db.get_all_plans().items():
        mark = "☑️" if key in selected else "⬜️"
        buttons.append([InlineKeyboardButton(text=f"{mark} {plan['name']}", callback_data=f"discplan_{key}", style="primary")])
    buttons.append([InlineKeyboardButton(text="✅ تأیید و ادامه", callback_data="discplan_done", style="success")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def discount_plans_edit_keyboard(discount_id: int, selected: list):
    """نسخه‌ی ویرایشِ کد تخفیف موجود؛ همان discount_plans_select_keyboard است اما با
    callback_data متفاوت (discplaned_) تا با مسیر ساخت کد جدید تداخل نکند."""
    buttons = [[InlineKeyboardButton(
        text="✅ همه‌ی پلن‌ها (بدون محدودیت)" if not selected else "☑️ همه‌ی پلن‌ها (بدون محدودیت)",
        callback_data=f"discplaned_{discount_id}_all", style="success",
    )]]
    for key, plan in db.get_all_plans().items():
        mark = "☑️" if key in selected else "⬜️"
        buttons.append([InlineKeyboardButton(text=f"{mark} {plan['name']}", callback_data=f"discplaned_{discount_id}_{key}", style="primary")])
    buttons.append([InlineKeyboardButton(text="✅ ذخیره", callback_data=f"discplaned_{discount_id}_done", style="success")])
    buttons.append([InlineKeyboardButton(text="🔙 انصراف", callback_data=f"discdetail_{discount_id}", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ---------------------------------------------------------------------------
# 🤝 نمایندگی — تخفیف خودکار روی VIP برای آیدی عددی‌های خاص
# ---------------------------------------------------------------------------
def admin_agency_menu(agents: list | None = None):
    """لیست نمایندگان به‌صورت دکمه؛ با زدن روی هرکدام دقیقاً همان صفحه‌ی
    مدیریت کاربر (مثل بخش «کاربران») باز می‌شود، به‌علاوه‌ی گزینه‌ی تغییر درصد تخفیف."""
    buttons = []
    for a in (agents or []):
        buttons.append([InlineKeyboardButton(
            text=f"🆔 {a['telegram_id']} | 💯 {a['vip_discount_percent']}٪",
            callback_data=f"agentopen_{a['telegram_id']}", style="primary",
        )])
    buttons.append([InlineKeyboardButton(text="➕ افزودن نماینده", callback_data="new_agent", style="success")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_agent_row_keyboard(telegram_id: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑 حذف این نماینده", callback_data=f"deleteagent_{telegram_id}", style="danger")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_agency", style="primary")],
    ])


def admin_agent_actions_keyboard(uid: str):
    """دقیقاً همان کیبورد مدیریت کاربر (admin_user_actions_keyboard)، به‌علاوه‌ی
    یک دکمه‌ی اضافه برای تغییر درصد تخفیف نمایندگی؛ دکمه‌ی بازگشت هم به لیست
    نمایندگان برمی‌گردد (نه لیست کلی کاربران)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💯 تغییر درصد تخفیف نمایندگی", callback_data=f"editagentpercent_{uid}", style="primary")],
        [InlineKeyboardButton(text="💰 شارژ دستی", callback_data=f"custom_{uid}", style="primary")],
        [InlineKeyboardButton(text="📒 حسابداری کاربر (تراکنش‌ها/منشأ پول)", callback_data=f"accounting_{uid}_0", style="primary")],
        [InlineKeyboardButton(text="🚀 ارسال کانفیگ VIP (QR)", callback_data=f"sendvip_{uid}", style="primary")],
        [InlineKeyboardButton(text="🎮 ارسال کانفیگ گیمینگ", callback_data=f"sendgaming_{uid}", style="primary")],
        [InlineKeyboardButton(text="📦 مشاهده و مدیریت سرویس‌های کاربر", callback_data=f"svcs_{uid}", style="primary")],
        [InlineKeyboardButton(text="🗑 حذف این نماینده", callback_data=f"deleteagent_{uid}", style="danger")],
        [InlineKeyboardButton(text="🔙 بازگشت به لیست نمایندگان", callback_data="admin_agency", style="primary")],
    ])


# ---------------------------------------------------------------------------
# 🗂 دسته‌بندی‌های VIP (پنل ادمین) — افزودن دسته‌ی جدید، ورود به هر دسته برای
# افزودن/ویرایش/حذف پلن‌های داخلش + تغییر ترتیب نمایش (⬆️/⬇️) دسته‌ها و پلن‌ها.
# ---------------------------------------------------------------------------
def admin_vip_categories_keyboard():
    buttons = []
    cats = db.get_vip_categories()
    for i, cat in enumerate(cats):
        n = len(db.get_vip_plans(cat["id"]))
        buttons.append([InlineKeyboardButton(
            text=f"🚀 {cat['name']} ({n} پلن)", callback_data=f"admincat_{cat['key']}"
        , style="primary")])
        move_row = []
        if i > 0:
            move_row.append(InlineKeyboardButton(text="⬆️", callback_data=f"movevipcat_{cat['key']}_up", style="primary"))
        if i < len(cats) - 1:
            move_row.append(InlineKeyboardButton(text="⬇️", callback_data=f"movevipcat_{cat['key']}_down", style="primary"))
        if move_row:
            buttons.append(move_row)
    buttons.append([InlineKeyboardButton(text="➕ دسته‌بندی جدید", callback_data="newvipcat", style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_vip_category_detail_keyboard(category_key: str):
    cat = db.get_vip_category(category_key)
    buttons = []
    if cat:
        plans = db.get_vip_plans(cat["id"])
        for i, plan in enumerate(plans):
            buttons.append([InlineKeyboardButton(
                text=f"📦 {plan['name']} — {plan['price']:,} ت", callback_data=f"vipplan_{plan['plan_key']}"
            , style="primary")])
            move_row = []
            if i > 0:
                move_row.append(InlineKeyboardButton(text="⬆️", callback_data=f"movevipplan_{plan['plan_key']}_up", style="primary"))
            if i < len(plans) - 1:
                move_row.append(InlineKeyboardButton(text="⬇️", callback_data=f"movevipplan_{plan['plan_key']}_down", style="primary"))
            if move_row:
                buttons.append(move_row)
    buttons.append([InlineKeyboardButton(text="➕ افزودن پلن به این دسته", callback_data=f"newvipplan_{category_key}", style="success")])
    buttons.append([InlineKeyboardButton(text="🗑 حذف این دسته (فقط اگر خالی باشد)", callback_data=f"delvipcat_{category_key}", style="danger")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_vip_categories", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_vip_plan_detail_keyboard(plan_key: str, category_key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ ویرایش نام", callback_data=f"vipplanname_{plan_key}", style="primary")],
        [InlineKeyboardButton(text="💰 ویرایش قیمت", callback_data=f"vipplanprice_{plan_key}", style="primary")],
        [InlineKeyboardButton(text="📦 ویرایش حجم (گیگ)", callback_data=f"vipplangb_{plan_key}", style="primary")],
        [InlineKeyboardButton(text="⏳ ویرایش مدت (روز، ۰=نامحدود)", callback_data=f"vipplandays_{plan_key}", style="primary")],
        [InlineKeyboardButton(text="🗑 حذف این پلن", callback_data=f"delvipplan_{plan_key}", style="danger")],
        [InlineKeyboardButton(text="🔙 بازگشت به دسته", callback_data=f"admincat_{category_key}", style="primary")],
    ])


# ---------------------------------------------------------------------------
# 🎮 دسته‌بندی‌های Gaming (پنل ادمین) — دقیقاً مثل VIP بالا: افزودن دسته‌ی
# جدید، افزودن/ویرایش/حذف پلن داخل هر دسته + تغییر ترتیب نمایش (⬆️/⬇️).
# ---------------------------------------------------------------------------
def admin_gaming_categories_keyboard():
    buttons = []
    cats = db.get_gaming_categories()
    for i, cat in enumerate(cats):
        n = len(db.get_gaming_plans(cat["id"]))
        buttons.append([InlineKeyboardButton(
            text=f"🌐 {cat['name']} ({n} پلن)", callback_data=f"admingamingcat_{cat['key']}"
        , style="primary")])
        move_row = []
        if i > 0:
            move_row.append(InlineKeyboardButton(text="⬆️", callback_data=f"movegamingcat_{cat['key']}_up", style="primary"))
        if i < len(cats) - 1:
            move_row.append(InlineKeyboardButton(text="⬇️", callback_data=f"movegamingcat_{cat['key']}_down", style="primary"))
        if move_row:
            buttons.append(move_row)
    buttons.append([InlineKeyboardButton(text="➕ دسته‌بندی جدید", callback_data="newgamingcat", style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_gaming_category_detail_keyboard(category_key: str):
    cat = db.get_gaming_category(category_key)
    buttons = []
    if cat:
        plans = db.get_gaming_plans(cat["id"])
        for i, plan in enumerate(plans):
            buttons.append([InlineKeyboardButton(
                text=f"📦 {plan['name']} — {plan['price']:,} ت", callback_data=f"gamingplan_{plan['plan_key']}"
            , style="primary")])
            move_row = []
            if i > 0:
                move_row.append(InlineKeyboardButton(text="⬆️", callback_data=f"movegamingplan_{plan['plan_key']}_up", style="primary"))
            if i < len(plans) - 1:
                move_row.append(InlineKeyboardButton(text="⬇️", callback_data=f"movegamingplan_{plan['plan_key']}_down", style="primary"))
            if move_row:
                buttons.append(move_row)
    buttons.append([InlineKeyboardButton(text="➕ افزودن پلن به این دسته", callback_data=f"newgamingplan_{category_key}", style="success")])
    buttons.append([InlineKeyboardButton(text="🗑 حذف این دسته (فقط اگر خالی باشد)", callback_data=f"delgamingcat_{category_key}", style="danger")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_gaming_categories", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_gaming_plan_detail_keyboard(plan_key: str, category_key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ ویرایش نام", callback_data=f"gamingplanname_{plan_key}", style="primary")],
        [InlineKeyboardButton(text="💰 ویرایش قیمت", callback_data=f"gamingplanprice_{plan_key}", style="primary")],
        [InlineKeyboardButton(text="📦 ویرایش حجم (گیگ)", callback_data=f"gamingplangb_{plan_key}", style="primary")],
        [InlineKeyboardButton(text="⏳ ویرایش مدت (روز، ۰=نامحدود)", callback_data=f"gamingplandays_{plan_key}", style="primary")],
        [InlineKeyboardButton(text="🗑 حذف این پلن", callback_data=f"delgamingplan_{plan_key}", style="danger")],
        [InlineKeyboardButton(text="🔙 بازگشت به دسته", callback_data=f"admingamingcat_{category_key}", style="primary")],
    ])


# ---------------------------------------------------------------------------
# 🔗 اتصال پنل مرزبان
# ---------------------------------------------------------------------------
def admin_marzban_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📡 تست اتصال (/me)", callback_data="marzban_test", style="primary")],
        [InlineKeyboardButton(text="🚦 ترافیک/مصرف برند (/traffic)", callback_data="marzban_traffic", style="primary")],
        [InlineKeyboardButton(text="📦 مشاهده‌ی بسته‌های پنل فعال (/plans)", callback_data="marzban_plans", style="primary")],
        [InlineKeyboardButton(text="🗂 نگاشت دسته‌بندی‌های VIP", callback_data="marzban_map_vip", style="primary")],
        [InlineKeyboardButton(text="🧩 نگاشت پیش‌فرض «بساز سرویس خودت»", callback_data="marzban_map_custom_build", style="primary")],
        [InlineKeyboardButton(text="🧪 نگاشت پیش‌فرض «تست رایگان»", callback_data="marzban_map_free_test", style="primary")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back", style="primary")],
    ])


def marzban_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_marzban", style="primary")],
    ])


def marzban_map_category_pick_keyboard(categories: list[dict], scope: str):
    """لیست دسته‌بندی‌های VIP یا Gaming برای انتخاب اینکه کدام‌یک نگاشت شود."""
    buttons = []
    for cat in categories:
        mapping = db.get_marzban_plan_map(scope, cat["id"])
        mark = f" ✅ ({mapping['plan_slug']})" if mapping else ""
        buttons.append([InlineKeyboardButton(
            text=f"{cat['name']}{mark}", callback_data=f"marzbanmapcat_{scope}_{cat['id']}"
        , style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_marzban", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def marzban_map_vip_category_pick_keyboard(categories: list[dict]):
    """قدم اول نگاشت اختصاصی VIP: انتخاب دسته‌بندی (فقط برای رفتن به لیست
    پلن‌های داخل آن دسته، نه ذخیره‌ی مستقیم نگاشت)."""
    buttons = [
        [InlineKeyboardButton(text=cat["name"], callback_data=f"marzbanmapvipcat_{cat['id']}", style="primary")]
        for cat in categories
    ]
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_marzban", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def marzban_map_vip_plans_keyboard(category_id: int, plans: list[dict]):
    """قدم دوم نگاشت اختصاصی VIP: لیست تک‌تک پلن‌های داخل یک دسته، هرکدام با
    نگاشت اختصاصی خودشان (اگر قبلاً ست شده باشد). همچنین یک گزینه‌ی اختیاری
    برای «نگاشت پیش‌فرض کل دسته» (رفتار قدیمی، برای وقتی همه‌ی پلن‌های آن
    دسته واقعاً باید یک بسته‌ی مرزبان یکسان بگیرند)."""
    buttons = []
    for p in plans:
        mapping = db.get_marzban_plan_map("vip_plan", p["id"])
        mark = f" ✅ ({mapping['plan_slug']})" if mapping else " ⚪️ نگاشت‌نشده"
        label = f"{p['name']} — {p['volume_gb']}GB/{p['days']}روز{mark}"
        if len(label) > 64:
            label = label[:61] + "..."
        buttons.append([InlineKeyboardButton(
            text=label, callback_data=f"marzbanmapvipplan_{category_id}_{p['id']}"
        , style="primary")])
    buttons.append([InlineKeyboardButton(
        text="🗂 نگاشت پیش‌فرض کل این دسته (اختیاری)",
        callback_data=f"marzbanmapcat_vip_category_{category_id}", style="primary",
    )])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="marzban_map_vip", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def marzban_plan_pick_keyboard(plans: list[dict], callback_prefix: str):
    """لیست بسته‌های واقعی مرزبان (از /plans) برای انتخاب — plans باید هرکدام
    حداقل کلید 'idx' (اندیس محلی در state) و متن نمایشی 'label' داشته باشند."""
    buttons = [
        [InlineKeyboardButton(text=p["label"], callback_data=f"{callback_prefix}_{p['idx']}", style="primary")]
        for p in plans
    ]
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_marzban", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ---------------------------------------------------------------------------
# ℹ️ اطلاعات ربات (قالب فروشی)
# ---------------------------------------------------------------------------
def admin_botinfo_menu():
    labels = bot_info.labels()
    buttons = []
    for key, label in labels.items():
        buttons.append([InlineKeyboardButton(text=f"✏️ {label}", callback_data=f"botinfoedit_{key}", style="primary")])
    buttons.append([InlineKeyboardButton(text="📢 مدیریت کانال‌های اجباری", callback_data="botinfochannels", style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_botinfo_field_keyboard(key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_botinfo", style="primary")],
    ])


def admin_botinfo_channels_menu(channels: list[dict]):
    buttons = []
    for ch in channels:
        buttons.append([InlineKeyboardButton(
            text=f"❌ {ch.get('name') or ch.get('id')}",
            callback_data=f"botinfochdel_{ch.get('id')}", style="danger",
        )])
    buttons.append([InlineKeyboardButton(text="➕ افزودن کانال جدید", callback_data="botinfochadd", style="success")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_botinfo", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ---------------------------------------------------------------------------
# 🛡️ اتصال پنل پاسارگارد (پنل VPN)
# ---------------------------------------------------------------------------
def admin_pasargad_menu(status_text: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔌 تست اتصال", callback_data="pasargadtest", style="primary")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back", style="primary")],
    ])


# ---------------------------------------------------------------------------
# 🔀 انتخاب پنل VPN فعال (وقتی هردو پنل مرزبان و پاسارگارد متصل باشند)
# ---------------------------------------------------------------------------
def admin_panel_choose_menu(available: list, active: str | None):
    labels = {"marzban": "🔗 مرزبان (Marzban)", "pasargad": "🛡️ پاسارگارد (PasarGuard)"}
    buttons = []
    for key in ("marzban", "pasargad"):
        if key not in available:
            continue
        mark = " ✅" if key == active else ""
        buttons.append([InlineKeyboardButton(
            text=f"{labels[key]}{mark}", callback_data=f"panelchoose_{key}", style="success" if key == active else "primary",
        )])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_manage_admins_keyboard(admins=None):
    buttons = []
    for a in (admins or []):
        buttons.append([InlineKeyboardButton(text=f"👤 {a.get('name') or a['telegram_id']} — {a['telegram_id']}", callback_data=f"subadm_{a['telegram_id']}", style="primary")])
    buttons.append([InlineKeyboardButton(text="➕ افزودن ادمین فرعی", callback_data="subadm_add", style="success")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_permissions_keyboard(admin_id: str, selected=None):
    selected = set(selected or [])
    buttons = []
    for key, label in db.ADMIN_PERMISSIONS.items():
        mark = "✅" if key in selected else "☑️"
        # رفع باگ: از ':' به‌جای '_' برای جدا کردن آیدی از نام قابلیت استفاده می‌شود، چون خود
        # کلیدهای قابلیت مثل "vpn_panel" و "orders_toggle" داخلشان زیرخط دارند و با split قبلی قاطی می‌شدند.
        buttons.append([InlineKeyboardButton(text=f"{mark} {label}", callback_data=f"subadmperm_{admin_id}:{key}", style="success" if key in selected else "primary")])
    buttons.append([InlineKeyboardButton(text="🗑 حذف این ادمین", callback_data=f"subadmdel_{admin_id}", style="danger")])
    buttons.append([InlineKeyboardButton(text="🔙 لیست ادمین‌ها", callback_data="admin_manage_admins", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
