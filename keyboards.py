"""
keyboards.py
تمام کیبوردهای Inline و Reply ربات. هیچ handlerای نباید خودش InlineKeyboardMarkup
بسازد؛ همه از این فایل صدا زده می‌شوند تا تغییر ظاهر منو در یک‌جا متمرکز باشد.
"""

from config import MARZBAN_ENABLED, PASARGAD_ENABLED, ONLINE_PAYMENT_MIN_AMOUNT
import payments
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton as _RealInlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton as _RealKeyboardButton,
    CopyTextButton,
)

import logging

import database as db
import bot_info
import vpn_panel

logger = logging.getLogger(__name__)


def copy_text_button(label: str, value: str, style: str = "primary"):
    """دکمهٔ بومی Telegram برای کپی مستقیم متن در کلیپ‌بورد."""
    return InlineKeyboardButton(
        text=label,
        copy_text=CopyTextButton(text=str(value)),
        style=style,
    )


def payment_copy_keyboard(amount_toman: int, card_number: str | None = None, cards: list[str] | None = None):
    # اگر cards از متن فاکتور پاس شده باشد دقیقاً همان کارت‌ها برای دکمه‌های کپی استفاده می‌شوند؛
    # در حالت قدیمی، انتخاب کارت طبق تنظیمات bot_info انجام می‌شود.
    if cards is None:
        cards = bot_info.get_cards_for_invoice() if hasattr(bot_info, 'get_cards_for_invoice') else ([card_number] if card_number else [])
    rows=[[copy_text_button(db.get_text_override("invoice_copy_amount", "📋 کپی مبلغ به ریال"), f"{int(amount_toman) * 10:,}", "primary")]]
    for i,card in enumerate(cards,1):
        label=db.get_text_override("invoice_copy_card", "💳 کپی شماره کارت")
        if len(cards)>1: label=f"{label} {i}"
        rows.append([copy_text_button(label, card, "success")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def crypto_payment_copy_keyboard(amount_crypto: str, asset: str, wallet: str):
    """دکمه‌های کپی فاکتور ارزی؛ مبلغ دقیق همان ارز را کپی می‌کند."""
    asset = str(asset or "").upper()
    label = db.get_text_override("crypto_copy_amount", "📋 کپی مبلغ {asset}").replace("{asset}", asset)
    return InlineKeyboardMarkup(inline_keyboard=[
        [copy_text_button(label, str(amount_crypto), "primary")],
        [copy_text_button(db.get_text_override("crypto_copy_wallet", "👛 کپی ولت"), wallet, "success")],
        [InlineKeyboardButton(
            text=db.get_text_override("crypto_choose_asset", "🔙 انتخاب ارز"), callback_data="crypto_choose_asset", style="primary")],
    ])


def crypto_asset_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=db.get_text_override("crypto_asset_ton", "🟣 TON"), callback_data="crypto_asset_ton", style="primary")],
        [InlineKeyboardButton(
            text=db.get_text_override("crypto_asset_trx", "🔴 TRX"), callback_data="crypto_asset_trx", style="primary")],
        [InlineKeyboardButton(
            text=db.get_text_override("crypto_asset_usdt", "🟢 USDT (TRC20)"), callback_data="crypto_asset_usdt", style="primary")],
        [InlineKeyboardButton(
            text=db.get_text_override("back", "🔙 بازگشت"), callback_data="back", style="danger")],
    ])


def crypto_payment_detail_keyboard(asset: str):
    # جزئیات واقعی مبلغ/ولت در همان صفحه هستند؛ دکمه‌های CopyText در handler ساخته می‌شوند.
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=db.get_text_override("crypto_receipt_hint", "📨 ارسال رسید / Hash"),
                              callback_data="crypto_receipt_hint", style="success")],
        [InlineKeyboardButton(
            text=db.get_text_override("crypto_choose_asset", "🔙 انتخاب ارز"), callback_data="crypto_choose_asset", style="primary")],
    ])


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
def _button_premium_emoji_kwargs(kwargs):
    """در صورت وجود Premium Emoji ذخیره‌شده برای متن دکمه، آن را به icon رسمی تلگرام وصل می‌کند.

    🐛 تاریخچه‌ی این تابع (برای این‌که دوباره از اول باگ نسازیم):
    ۱) اول متنِ دکمه هنگام ساخت icon حذف می‌شد → با فشردن دکمه متنِ ناقص
       برمی‌گشت و هیچ فیلتری match نمی‌شد.
    ۲) بعد از این‌که متن را دست‌نخورده نگه داشتیم، مشخص شد خودِ تلگرام وقتی
       هم `text` (که با همان ایموجی شروع می‌شود) و هم `icon_custom_emoji_id`
       روی یک دکمه ست باشند، همان کاراکتر ابتدای متن را خودش حذف می‌کند تا
       ایموجی دوبار نمایش داده نشود؛ و باز هم متنِ برگشتی با متنِ ذخیره‌شده
       مطابقت نداشت.
    برای همین icon_custom_emoji_id کلاً حذف شده بود — ولی نتیجه‌اش این شد که
    ایموجی‌های پرمیوم/انیمیشنی روی هیچ دکمه‌ای نمایش داده نمی‌شدند (حتی روی
    دکمه‌های Inline که اصلاً این مشکل را نداشتند، چون فشردن دکمه‌ی Inline
    همیشه با callback_data تشخیص داده می‌شود، نه با متن).
    راه‌حل نهایی: icon_custom_emoji_id دوباره فعال است (برای هم Inline و هم
    Reply Keyboard)، اما حالا `_MenuButtonText` در handlers/menu.py یک لایه‌ی
    محافظتی دارد که پیشوند ایموجیِ حذف‌شده توسط تلگرام را نادیده می‌گیرد؛
    یعنی حتی اگر تلگرام دوباره همان کاراکتر را از متنِ دکمه‌های Reply Keyboard
    حذف کند، دکمه باز هم درست تشخیص داده می‌شود. دکمه‌های Inline از اول هم
    ریسکی نداشتند چون تشخیصشان از طریق callback_data است.
    """
    if kwargs.get("icon_custom_emoji_id"):
        return kwargs
    text = kwargs.get("text")
    if text:
        try:
            display_text, emoji_id = db.get_button_premium_emoji_for_text(str(text))
            if emoji_id:
                # وقتی آیکن Premium فعال است، ایموجی معمولی ابتدای متن نباید
                # همزمان باقی بماند؛ در غیر این صورت Telegram آن را کنار آیکن
                # سفارشی هم نمایش می‌دهد (مثل «🛒 + Premium Emoji»).
                # فقط همان خوشه‌ی ایموجی ابتدایی حذف می‌شود و متن واقعی دکمه
                # دست‌نخورده می‌ماند؛ callback_data اصلاً تغییر نمی‌کند.
                kwargs["text"] = _strip_leading_emoji_cluster(display_text)
                kwargs["icon_custom_emoji_id"] = emoji_id
        except Exception:
            # Premium Emoji نباید باعث خراب‌شدن هیچ دکمه‌ای شود.
            pass
    return kwargs


def _strip_leading_emoji_cluster(value: str) -> str:
    """حذف فقط ایموجی/نماد ابتدای متن برای جایگزینی با Premium Emoji.

    این تابع عمداً فقط ابتدای متن را لمس می‌کند تا ایموجی‌های داخل عنوان،
    اعداد، علائم فارسی و متن دکمه تغییر نکنند. ZWJ/VS16 و modifierهای بعد از
    ایموجی هم همراه همان خوشه حذف می‌شوند.
    """
    import unicodedata

    if not value:
        return value

    def is_emojiish(ch: str) -> bool:
        cp = ord(ch)
        cat = unicodedata.category(ch)
        # همه‌ی بلوک‌های رایج Emoji/Symbol + کاراکترهایی که تلگرام
        # معمولاً به‌عنوان fallback یک Custom/Premium Emoji استفاده می‌کند.
        # هدف این تابع فقط حذف fallback ابتدای متن است؛ متن فارسی/لاتین
        # و اعداد دست‌نخورده می‌مانند.
        return (
            0x1F000 <= cp <= 0x1FAFF
            or 0x1FC00 <= cp <= 0x1FFFF
            or 0x2300 <= cp <= 0x23FF
            or 0x2600 <= cp <= 0x27BF
            or 0x2B00 <= cp <= 0x2BFF
            or 0x2E80 <= cp <= 0x2EFF
            or 0x3000 <= cp <= 0x303F
            or 0xFE0E <= cp <= 0xFE0F
            or cat in {"So", "Sk"}
        )

    i = 0
    n = len(value)
    started = False

    # Keycap emoji مثل 1️⃣ / #️⃣ / *️⃣ با کاراکتر ASCII شروع می‌شوند؛
    # اگر Premium Emoji روی چنین دکمه‌ای فعال باشد، خود کاراکتر آزاد نباید
    # کنار آیکن Premium باقی بماند.
    if n >= 3 and value[0] in "0123456789#*" and value[1] in ("\ufe0e", "\ufe0f") and value[2] == "\u20e3":
        i = 3
        started = True

    while i < n:
        ch = value[i]
        cp = ord(ch)
        if is_emojiish(ch):
            started = True
            i += 1
            continue
        if started and cp in (0xFE0E, 0xFE0F, 0x200D, 0x20E3):
            i += 1
            continue
        if started and 0x1F3FB <= cp <= 0x1F3FF:
            i += 1
            continue
        break
    if not started:
        return value
    # اگر بعد از ایموجی یک فاصله آمده، همان فاصله هم حذف شود.
    return value[i:].lstrip()


def InlineKeyboardButton(*args, **kwargs):
    """
    Wrapper مرکزی دکمه‌های Inline.
    Premium/Custom Emoji فقط ظاهر دکمه است و نباید هیچ‌وقت callback_data
    یا ساخت خود دکمه را خراب کند. اگر Telegram/aiogram آیکن سفارشی را
    نپذیرفت، همان دکمه بدون آیکن سفارشی ساخته می‌شود.
    """
    if kwargs.get("callback_data") is not None:
        kwargs["callback_data"] = _safe_callback_data(kwargs["callback_data"])

    kwargs = _button_premium_emoji_kwargs(kwargs)

    try:
        return _RealInlineKeyboardButton(*args, **kwargs)
    except Exception:
        # ظاهر دکمه نباید باعث از کار افتادن callback شود.
        kwargs.pop("icon_custom_emoji_id", None)
        return _RealInlineKeyboardButton(*args, **kwargs)


def KeyboardButton(*args, **kwargs):
    """Wrapper مرکزی Reply Keyboard؛ Premium Emoji نباید رفتار دکمه را خراب کند."""
    kwargs = _button_premium_emoji_kwargs(kwargs)
    try:
        return _RealKeyboardButton(*args, **kwargs)
    except Exception:
        kwargs.pop("icon_custom_emoji_id", None)
        return _RealKeyboardButton(*args, **kwargs)


# ---------------------------------------------------------------------------
# عضویت اجباری
# ---------------------------------------------------------------------------
def join_channels_keyboard(channels):
    """کیبورد عضویت اجباری.

    این کیبورد عمداً ساده و مستقل از style دکمه‌ها ساخته می‌شود تا اگر
    نسخه Bot API/aiogram روی سرور از style پشتیبانی نکرد، کل فرم عضویت
    به خاطر یک پارامتر ظاهری از بین نرود. همچنین فقط کانال‌های معتبر را
    به دکمه تبدیل می‌کنیم و دکمه «عضو شدم» همیشه وجود دارد.
    """
    rows = []
    for ch in channels or []:
        if not isinstance(ch, dict):
            continue
        name = str(ch.get("name") or "کانال")
        url = str(ch.get("url") or "").strip()
        if not url:
            continue
        if not url.startswith(("https://", "http://", "tg://")):
            if url.startswith(("t.me/", "telegram.me/")):
                url = "https://" + url
            elif url.startswith("@"):
                url = "https://t.me/" + url[1:]
            else:
                url = "https://t.me/" + url.lstrip("/")
        try:
            rows.append([InlineKeyboardButton(text=f"{name}", url=url, style="primary")])
        except Exception:
            logger.exception("خطا در ساخت دکمه کانال عضویت اجباری: %r", ch)

    rows.append([InlineKeyboardButton(text="✅ عضو شدم", callback_data="check_join", style="success")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# منوی پایین صفحه (Reply Keyboard) — همیشه در دسترس کاربر
# ---------------------------------------------------------------------------
def main_reply_keyboard():
    hidden = db.get_hidden_main_user_menu_buttons()
    specs = [
        ("main_buy", "🛒 خرید اشتراک", "success"),
        ("main_free_test", "🎁 تست رایگان", "success"),
        ("main_configs", "📱 سرویس‌های من", "primary"),
        ("main_wallet", "💰 کیف پول", "primary"),
        ("main_referral", "👥 دعوت دوستان و کسب درآمد", "primary"),
        ("main_profile", "👤 پروفایل من", "primary"),
        ("main_support", "👨‍💻 پشتیبانی", "primary"),
        ("main_guides", "📚 راهنما", "primary"),
        ("main_agency", "🤝 درخواست نمایندگی", "danger"),
    ]
    buttons = {key: KeyboardButton(text=db.get_text_override(key, default), style=style)
               for key, default, style in specs if key not in hidden}
    rows = []
    for keys in (("main_buy", "main_free_test"), ("main_configs", "main_wallet"),
                 ("main_referral", "main_profile"), ("main_support", "main_guides"),
                 ("main_agency",)):
        row = [buttons[k] for k in keys if k in buttons]
        if row:
            rows.append(row)
    return ReplyKeyboardMarkup(
        keyboard=rows, resize_keyboard=True, is_persistent=True, one_time_keyboard=False,
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
        if allowed(a_perm):
            row.append(a_btn)
        if b_btn is not None and allowed(b_perm):
            row.append(b_btn)
        if row:
            rows.append(row)

    add_pair("stats", KeyboardButton(text="📊 آمار", style="primary"),
             "requests", KeyboardButton(text="📥 صف درخواست‌ها", style="primary"))
    add_pair("tickets", KeyboardButton(text="🎫 تیکت‌های بی‌پاسخ", style="primary"))
    add_pair("users", KeyboardButton(text="👥 لیست کاربران", style="primary"),
             "users", KeyboardButton(text="🔍 جستجوی کاربر", style="primary"))
    add_pair("broadcast", KeyboardButton(text="📢 پیام همگانی", style="primary"),
             "discounts", KeyboardButton(text="🎟 مدیریت تخفیف", style="primary"))
    add_pair("agency", KeyboardButton(text="🤝 نمایندگی (تخفیف VIP)", style="primary"),
             "plans", KeyboardButton(text="🗂 دسته‌بندی‌های VIP", style="primary"))
    add_pair("vpn_panel", KeyboardButton(text="🖥 مدیریت پنل‌های VPN", style="primary"))
    add_pair("referrals", KeyboardButton(text="🤝 مدیریت دعوت‌ها", style="primary"),
             "guides", KeyboardButton(text="📚 مدیریت راهنما", style="primary"))
    add_pair("logs", KeyboardButton(text="🦖 لاگ خطاها", style="primary"),
             "botinfo", KeyboardButton(text="ℹ️ اطلاعات ربات", style="primary"))
    add_pair("texts", KeyboardButton(
        text="🎛 مدیریت منوی اصلی کاربر", style="primary"))
    add_pair("stickers", KeyboardButton(text="🎬 استیکرهای منو", style="primary"),
             "backup", KeyboardButton(text="💾 بکاپ", style="primary"))
    add_pair("settings", KeyboardButton(
        text="🎁 تنظیم تست رایگان", style="primary"))
    if allowed("orders_toggle"):
        toggle_btn = (KeyboardButton(text="🔴 خاموش کردن سفارشات", style="danger")
                      if orders_enabled else KeyboardButton(text="🟢 روشن کردن سفارشات", style="success"))
        rows.append([toggle_btn])
    if is_main_admin:
        rows.append([KeyboardButton(text="👮 مدیریت ادمین‌ها", style="danger")])
    if not rows:
        rows = [[KeyboardButton(text="⛔ بدون دسترسی", style="danger")]]
    # 🆕 فیکس نهایی: همان دلیل بالا در main_reply_keyboard — is_persistent=True برگردانده شد
    # تا دکمه‌ی چهارخونه همیشه (حتی بدون بازبودن کیبورد تایپ) در دسترس باشد.
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=False,
        one_time_keyboard=False
    )


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
    collect(admin_reply_keyboard(orders_enabled=True,
            permissions=None, is_main_admin=True))
    collect(admin_reply_keyboard(orders_enabled=False,
            permissions=None, is_main_admin=True))
    collect(admin_reply_keyboard(orders_enabled=True,
            permissions=set(), is_main_admin=False))
    return texts


# ---------------------------------------------------------------------------
# منوی اصلی (Inline) — کاربر عادی
# ---------------------------------------------------------------------------
def main_menu():
    hidden = db.get_hidden_main_user_menu_buttons()
    buttons = []
    styles = {
        "main_buy": "success", "main_free_test": "success",
        "main_configs": "primary", "main_wallet": "primary",
        "main_referral": "primary", "main_profile": "primary",
        "main_support": "primary", "main_guides": "primary",
        "main_agency": "danger",
    }
    for key, item in db.MAIN_USER_MENU_BUTTONS.items():
        # «درخواست نمایندگی» فعلاً فقط در Reply Keyboard وجود دارد؛
        # برای جلوگیری از ساخت دکمه‌ای با callback ناشناخته، در Inline نمی‌آید.
        if key == "main_agency" or key in hidden:
            continue
        buttons.append([InlineKeyboardButton(text=db.get_text_override(key, item["label"]),
                                             callback_data=item["callback"], style=styles.get(key, "primary"))])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_button(callback_data: str = "back", text: str = "🏠 بازگشت به منوی اصلی"):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=callback_data, style="danger")]])


def profile_menu():
    # 🆕 به درخواست کاربر: فقط «تاریخچه خرید»، «تاریخچه تراکنش» و «بازگشت» نگه داشته شد؛
    # «کیف پول آزاد»، «کیف پول مسدود» و «لینک دعوت اختصاصی» از این منو حذف شدند
    # (این اطلاعات هنوز از جاهای دیگر مثل «کیف پول» و «دعوت دوستان» در دسترس‌اند).
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=db.get_text_override("profile_history", "🛒 تاریخچه خرید"), callback_data="purchase_history", style="primary")],
        [InlineKeyboardButton(text=db.get_text_override("profile_transactions", "📋 تاریخچه تراکنش"),
                              callback_data="transactions", style="primary")],
        [InlineKeyboardButton(text=db.get_text_override("main_back", "🏠 بازگشت به منوی اصلی"),
                              callback_data="back", style="danger")],
    ])


def wallet_menu():
    # 🆕 به درخواست کاربر: فقط «شارژ کیف پول» و «بازگشت» نگه داشته شد؛
    # «ثبت کد تخفیف» و «تراکنش‌های من» از این منو حذف شدند.
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=db.get_text_override("wallet_charge", "💳 شارژ کیف پول"),
                              callback_data="charge", style="success")],
        [InlineKeyboardButton(text=db.get_text_override("main_back", "🏠 بازگشت به منوی اصلی"),
                              callback_data="back", style="danger")],
    ])


def charge_amount_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=db.get_text_override("charge_50000", "💰 ۵۰,۰۰۰ تومان"),
                              callback_data="charge_50000", style="primary")],
        [InlineKeyboardButton(text=db.get_text_override("charge_100000", "💰 ۱۰۰,۰۰۰ تومان"),
                              callback_data="charge_100000", style="primary")],
        [InlineKeyboardButton(text=db.get_text_override("charge_200000", "💰 ۲۰۰,۰۰۰ تومان"),
                              callback_data="charge_200000", style="primary")],
        [InlineKeyboardButton(text=db.get_text_override("charge_custom", "💵 مبلغ دلخواه"),
                              callback_data="charge_custom", style="primary")],
        [InlineKeyboardButton(
            text=db.get_text_override("back", "🔙 بازگشت"), callback_data="wallet", style="danger")],
    ])


def charge_payment_method_keyboard(amount: int):
    """انتخاب روش پرداخت برای شارژ کیف پول. دکمه‌ی «پرداخت آنلاین» فقط وقتی
    نمایش داده می‌شود که درگاه فعال باشد و مبلغ بیشتر از
    ONLINE_PAYMENT_MIN_AMOUNT باشد (برای مبالغ مساوی یا کمتر، درگاه آنلاین
    اصلاً پیشنهاد نمی‌شود و فقط کارت‌به‌کارت در دسترس است)."""
    buttons = []
    if bot_info.payment_method_enabled("online") and payments.online_payment_enabled() and amount > payments.online_payment_min_amount():
        buttons.append(
            [InlineKeyboardButton(text=db.get_text_override("pay_online", "🌐 پرداخت آنلاین (تایید خودکار)"),
                                  callback_data=f"chargepay_online_{amount}", style="success")]
        )
    if bot_info.payment_method_enabled("card"):
        buttons.append([InlineKeyboardButton(text=db.get_text_override("pay_card", "💳 پرداخت کارت به کارت"),
                       callback_data=f"chargepay_card_{amount}", style="success")])
    buttons.append([InlineKeyboardButton(text=db.get_text_override("back", "🔙 بازگشت"),
                   callback_data="charge", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def online_payment_wallet_keyboard(payment_link: str, online_payment_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=db.get_text_override("online_payment_button", db.get_text_override("online_pay", "💳 پرداخت آنلاین")), url=payment_link, style="success")],
        [InlineKeyboardButton(text=db.get_text_override("online_payment_check", db.get_text_override("online_check", "✅ بررسی پرداخت")),
                              callback_data=f"checkpay_{online_payment_id}", style="success")],
        [InlineKeyboardButton(
            text=db.get_text_override("online_payment_cancel", db.get_text_override("online_cancel", "🔙 انصراف")), callback_data="wallet", style="danger")],
    ])


def referral_menu(invite_link: str | None = None):
    buttons = []
    if invite_link:
        buttons.append([copy_text_button("📋 کپی لینک دعوت", invite_link)])
    buttons.append([InlineKeyboardButton(
        text=db.get_text_override("main_back", "🏠 بازگشت به منوی اصلی"), callback_data="back", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def support_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=db.get_text_override("support_ticket", "🎫 ارسال تیکت"),
                              callback_data="ticket", style="primary")],
        [InlineKeyboardButton(text=db.get_text_override("support_channels", "📢 کانال اصلی و پشتیبان"),
                              url=bot_info.get_support_url(), style="primary")],
        [InlineKeyboardButton(text=db.get_text_override("main_back", "🏠 بازگشت به منوی اصلی"),
                              callback_data="back", style="danger")],
    ])


# ---------------------------------------------------------------------------
# سرویس‌ها / خرید اشتراک
# ---------------------------------------------------------------------------
def plans_menu():
    """🧹 دیگر مستقیماً استفاده نمی‌شود: دکمهٔ «🛒 خرید اشتراک» مستقیماً دسته‌بندی‌های VIP را باز می‌کند (vip_categories_keyboard)."""
    return vip_categories_keyboard()


def _plans_keyboard(plans_dict: dict, icon: str, discount_percent: int = 0):
    buttons = []
    for key, plan in plans_dict.items():
        price = plan["price"]
        if discount_percent:
            price = int(price * (1 - discount_percent / 100))
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {plan['name']} — {price:,} تومان",
            callback_data=f"buy_{key}", style="success")])
    buttons.append([InlineKeyboardButton(text=db.get_text_override("back", "🔙 بازگشت"),
                   callback_data="plans", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def vip_categories_keyboard():
    """مرحله‌ی اول خرید VIP: فقط دسته‌های ریشه‌ایِ فعال نمایش داده می‌شوند."""
    buttons = []
    for cat in db.get_vip_categories(enabled_only=True):
        buttons.append([InlineKeyboardButton(
            text=f"{cat['name']}", callback_data=f"vipcat_{cat['key']}", style="primary")])
    if not buttons:
        buttons.append([InlineKeyboardButton(
            text=db.get_text_override("vip_category_empty", "😔 فعلاً هیچ دسته‌ای موجود نیست"), callback_data="noop", style="primary")])
    buttons.append([InlineKeyboardButton(text=db.get_text_override("back", "🔙 بازگشت"),
                   callback_data="back", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def vip_category_plans_keyboard(category_key: str, discount_percent: int = 0):
    """یک سطح از درخت VIP را نشان می‌دهد؛ زیر‌دسته‌ها اختیاری‌اند و
    دکمه‌ی «لیست پلن‌های همین دسته» همیشه امکان رد کردن آن مرحله را می‌دهد."""
    cat = db.get_vip_category(category_key)
    plans = db.get_vip_plans(cat["id"]) if cat else []
    children = db.get_vip_category_children(cat["id"], enabled_only=True) if cat else []
    buttons = []

    for child in children:
        buttons.append([InlineKeyboardButton(
            text=f"📁 {child['name']}", callback_data=f"vipcat_{child['key']}", style="primary")])

    if plans:
        price_label = "📦 لیست پلن‌های همین دسته"
        buttons.append([InlineKeyboardButton(text=price_label, callback_data=f"vipcatplans_{category_key}", style="success")])
    elif not children:
        buttons.append([InlineKeyboardButton(
            text=db.get_text_override("vip_plans_empty", "😔 فعلاً هیچ پلنی در این دسته نیست"),
            callback_data="noop", style="primary")])

    parent_cb = "plans_vip"
    if cat and cat.get("parent_id"):
        parent = db.get_vip_category(int(cat["parent_id"]))
        if parent:
            parent_cb = f"vipcat_{parent['key']}"

    buttons.append([InlineKeyboardButton(
        text=db.get_text_override("vip_plans_back", "🔙 بازگشت"), callback_data=parent_cb, style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def vip_category_direct_plans_keyboard(category_key: str, discount_percent: int = 0):
    """فقط پلن‌های یک دسته؛ این صفحه همان «پرش از زیر‌دسته‌ها» است."""
    cat = db.get_vip_category(category_key)
    plans = db.get_vip_plans(cat["id"]) if cat else []
    buttons = []
    for plan in plans:
        price = plan["price"]
        if discount_percent:
            price = int(price * (1 - discount_percent / 100))
        buttons.append([InlineKeyboardButton(
            text=f"{plan['name']} — {price:,} تومان", callback_data=f"buy_{plan['plan_key']}", style="primary")])
    if not buttons:
        buttons.append([InlineKeyboardButton(
            text=db.get_text_override("vip_plans_empty", "😔 فعلاً هیچ پلنی در این دسته نیست"), callback_data="noop", style="primary")])
    parent_cb = "plans_vip"
    if cat and cat.get("parent_id"):
        parent = db.get_vip_category(int(cat["parent_id"]))
        if parent:
            parent_cb = f"vipcat_{parent['key']}"
    buttons.append([InlineKeyboardButton(text=db.get_text_override("vip_plans_back", "🔙 بازگشت"), callback_data=parent_cb, style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def all_plans_discount_keyboard(discount_percent: int):
    return _plans_keyboard(db.get_all_plans(), "📅", discount_percent)


def purchase_payment_keyboard(plan_key: str, show_discount: bool = True):
    actions={
        "card":[InlineKeyboardButton(text=db.get_text_override("pay_card", "💳 پرداخت کارت به کارت"), callback_data=f"pay_card_{plan_key}", style="success")],
        "online":[InlineKeyboardButton(text=db.get_text_override("pay_online", "🌐 پرداخت آنلاین (تایید خودکار)"), callback_data=f"pay_online_{plan_key}", style="success")],
        "crypto":[InlineKeyboardButton(text=db.get_text_override("pay_crypto", "💱 پرداخت ارزی"), callback_data=f"pay_crypto_{plan_key}", style="success")],
        "wallet":[InlineKeyboardButton(text=db.get_text_override("pay_wallet", "👛 پرداخت از کیف پول"), callback_data=f"pay_wallet_{plan_key}", style="success")],
    }
    enabled={
        "card": bot_info.payment_method_enabled("card"),
        "online": bot_info.payment_method_enabled("online") and payments.online_payment_enabled(),
        "crypto": bot_info.payment_method_enabled("crypto") and bot_info.crypto_payment_enabled(),
        "wallet": bot_info.payment_method_enabled("wallet"),
    }
    try: order=[x.strip().lower() for x in bot_info.get("payment_methods_order").split(",") if x.strip()]
    except Exception: order=["card","online","crypto","wallet"]
    buttons=[actions[x] for x in order if x in actions and enabled.get(x)]
    if show_discount: buttons.append([InlineKeyboardButton(text=db.get_text_override("pay_discount", "🎟 ثبت کد تخفیف"), callback_data=f"discount_plan_{plan_key}", style="primary")])
    buttons.append([InlineKeyboardButton(text=db.get_text_override("back", "🔙 بازگشت"), callback_data="back", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def online_payment_keyboard(payment_link: str, online_payment_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=db.get_text_override("online_payment_button", db.get_text_override("online_pay", "💳 پرداخت آنلاین")), url=payment_link, style="primary")],
        [InlineKeyboardButton(text=db.get_text_override("online_payment_check", db.get_text_override("online_check", "✅ بررسی پرداخت")),
                              callback_data=f"checkpay_{online_payment_id}", style="success")],
        [InlineKeyboardButton(
            text=db.get_text_override("online_payment_cancel", db.get_text_override("online_cancel", "🔙 انصراف")), callback_data="plans", style="danger")],
    ])


def insufficient_balance_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=db.get_text_override("insufficient_charge", "💵 شارژ کیف پول"),
                              callback_data="wallet", style="primary")],
        [InlineKeyboardButton(
            text=db.get_text_override("back", "🔙 بازگشت"), callback_data="plans", style="danger")],
    ])


def config_name_reply_keyboard():
    """دکمه‌های مرحله انتخاب نام را Inline نگه می‌دارد تا Reply Keyboard اصلی هیچ‌وقت جایگزین نشود."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=db.get_text_override("config_name_auto", "🤖 انتخاب خودکار نام"), callback_data="config_name_auto", style="success")],
        [InlineKeyboardButton(text=db.get_text_override("config_name_back", "🔙 بازگشت به مرحله قبل"), callback_data="config_name_back", style="primary")],
    ])

def service_search_reply_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=db.get_text_override("service_search_cancel", "🔙 بازگشت"), callback_data="service_search_cancel", style="primary")]])

# ---------------------------------------------------------------------------
# سرویس‌های من
# ---------------------------------------------------------------------------
def my_configs_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=db.get_text_override("service_search", "🔎 جستجوی سرویس"), callback_data="service_search", style="primary")],
        [InlineKeyboardButton(text=db.get_text_override("main_back", "🏠 بازگشت به منوی اصلی"), callback_data="back", style="danger")],
    ])


def my_configs_list_keyboard(configs, icon: str = "", back_callback: str = "back", page: int = 0, page_size: int = 6):
    """لیست سرویس‌ها با صفحه‌بندی. نام دکمه دقیقاً service_name ثبت‌شده هنگام
    ساخت سرویس است و هرگز به نام داخلی plan/subscription تبدیل نمی‌شود."""
    configs = list(configs or [])
    total_pages = max(1, (len(configs) + page_size - 1) // page_size)
    page = max(0, min(int(page), total_pages - 1))
    chunk = configs[page * page_size:(page + 1) * page_size]
    buttons = []
    for cfg in chunk:
        name = str(cfg.get("service_name") or "").strip()
        if not name:
            name = str(cfg.get("plan") or "سرویس").split(" | ", 1)[0]
        buttons.append([InlineKeyboardButton(
            text=f"{icon}{name}", callback_data=f"viewconfig_{cfg['id']}", style="primary"
        )])
    buttons.append([InlineKeyboardButton(text=db.get_text_override("service_search", "🔎 جستجوی سرویس"),
                                         callback_data="service_search", style="primary")])
    if total_pages > 1:
        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="⬅️ قبلی", callback_data=f"svcpage_{page-1}", style="primary"))
        nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop", style="primary"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="بعدی ➡️", callback_data=f"svcpage_{page+1}", style="primary"))
        buttons.append(nav)
    buttons.append([InlineKeyboardButton(text=db.get_text_override("back", "🔙 بازگشت"),
                                         callback_data=back_callback, style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def config_detail_keyboard(cfg_id, sub_link_url=None, has_qr=False, back_callback="back", service_id=None, disabled=False):
    """جزئیات سرویس با چیدمان دو ستونه مطابق UI مرجع؛ همه‌ی عملیات روی همان
    service_id/panel_id ذخیره‌شده‌ی سرویس اجرا می‌شوند."""
    rows = [
        [
            InlineKeyboardButton(text=db.get_text_override("config_sub", "🔗 لینک اشتراک"),
                                 url=sub_link_url, style="success") if sub_link_url else
            InlineKeyboardButton(text="🔗 لینک اشتراک", callback_data=f"viewconfig_{cfg_id}", style="primary"),
            InlineKeyboardButton(text="➕ خرید حجم اضافه", callback_data=f"cfgaddvol_{cfg_id}", style="primary"),
        ],
        [
            InlineKeyboardButton(text=db.get_text_override("config_revoke", "⚙️ تغییر لینک"),
                                 callback_data=f"cfgrevokesub_{cfg_id}", style="primary"),
            InlineKeyboardButton(text="⏳ تمدید زمان", callback_data=f"cfgadddays_{cfg_id}", style="primary"),
        ],
        [
            InlineKeyboardButton(text="📤 انتقال سرویس", callback_data=f"cfgtransfer_{cfg_id}", style="primary"),
            InlineKeyboardButton(
                text=("✅ روشن کردن اکانت" if disabled else "❌ خاموش کردن اکانت"),
                callback_data=(f"cfgenable_{cfg_id}" if disabled else f"cfgdisable_{cfg_id}"),
                style="success" if disabled else "danger",
            ),
        ],
    ]
    if has_qr:
        rows.append([InlineKeyboardButton(text=db.get_text_override("config_qr", "🖼 مشاهده کیو آر کد"),
                                          callback_data=f"viewqr_{cfg_id}", style="primary")])
    rows.append([InlineKeyboardButton(text=db.get_text_override("config_refresh", "🔄 بروزرسانی اطلاعات"),
                                      callback_data=f"viewconfig_{cfg_id}", style="primary")])
    rows.append([
        InlineKeyboardButton(text=db.get_text_override("config_delete", "🗑 حذف سرویس"),
                             callback_data=f"delconfig_{cfg_id}", style="danger"),
        InlineKeyboardButton(text=db.get_text_override("back", "🔙 بازگشت به لیست سرویس‌ها"),
                             callback_data=back_callback, style="primary"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_delete_config_keyboard(cfg_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=db.get_text_override("confirm_delete_yes", "✅ بله، حذف کن"), callback_data=f"delconfirm_{cfg_id}", style="danger")],
        [InlineKeyboardButton(
            text=db.get_text_override("confirm_delete_no", "❌ انصراف"), callback_data=f"viewconfig_{cfg_id}", style="danger")],
    ])


def confirm_disable_service_keyboard(cfg_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=db.get_text_override("confirm_disable_yes", "✅ بله، غیرفعال کن"), callback_data=f"cfgdisabledo_{cfg_id}", style="danger")],
        [InlineKeyboardButton(
            text=db.get_text_override("confirm_disable_no", "❌ انصراف"), callback_data=f"viewconfig_{cfg_id}", style="danger")],
    ])


def confirm_revoke_sub_keyboard(cfg_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=db.get_text_override("confirm_revoke_yes", "✅ بله، لینک جدید بساز"),
                              callback_data=f"cfgrevokesubdo_{cfg_id}", style="danger")],
        [InlineKeyboardButton(
            text=db.get_text_override("confirm_revoke_no", "❌ انصراف"), callback_data=f"viewconfig_{cfg_id}", style="danger")],
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
            buttons.append(InlineKeyboardButton(
                text=text, callback_data=callback_data, style=style))

    add("📊 آمار", "admin_stats", "stats")
    add("📥 صف درخواست‌ها", "admin_request_queue", "requests", "success")
    add("🎫 تیکت‌های بی‌پاسخ", "admintickets", "tickets")
    add("👥 لیست کاربران", "admin_userlist", "users")
    add("🔍 جستجوی حرفه‌ای", "admin_search", "users")
    add("🎟 مدیریت تخفیف", "admin_discount", "discounts")
    add("🤝 نمایندگی (تخفیف VIP)", "admin_agency", "agency")
    add("🗂 دسته‌بندی‌های VIP", "admin_vip_categories", "plans")
    add("🖥 مدیریت پنل‌های VPN", "admin_vpn_panels", "vpn_panel")
    add("ℹ️ اطلاعات ربات", "admin_botinfo", "botinfo")
    add("🎬 استیکرهای منو", "admin_stickers", "stickers")
    add("🤝 مدیریت دعوت‌ها", "admin_referrals", "referrals")
    add("📚 مدیریت راهنما", "admin_guides", "guides")
    add("📝 مدیریت متن‌های کاربر", "admin_texts", "texts")
    add("🎛 مدیریت منوی اصلی کاربر", "admin_main_user_menu", "texts")
    add("📢 پیام همگانی", "admin_broadcast", "broadcast")
    add("💾 بکاپ", "admin_backup", "backup")
    if is_main_admin:
        buttons.append(InlineKeyboardButton(
            text="👮 مدیریت ادمین‌ها", callback_data="admin_manage_admins", style="danger"))
    if allowed("orders_toggle"):
        buttons.append(InlineKeyboardButton(text=("🔴 خاموش کردن سفارشات" if orders_enabled else "🟢 روشن کردن سفارشات"), callback_data=(
            "admin_orders_off" if orders_enabled else "admin_orders_on"), style=("danger" if orders_enabled else "success")))
    if not buttons:
        buttons.append(InlineKeyboardButton(
            text="⛔ هیچ دسترسی فعالی ندارید", callback_data="noop", style="danger"))

    # دو دکمه در هر ردیف؛ ساختار موردنیاز Telegram InlineKeyboardMarkup
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_main_user_menu_keyboard():
    hidden = db.get_hidden_main_user_menu_buttons()
    buttons = []
    for key, item in db.MAIN_USER_MENU_BUTTONS.items():
        is_hidden = key in hidden
        buttons.append([InlineKeyboardButton(
            text=("🟢 فعال — " if is_hidden else "🔴 مخفی — ") + item["label"],
            callback_data=f"mainmenu_toggle_{key}",
            style="success" if is_hidden else "danger",
        )])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",
                   callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_stats_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 ریست فروش امروز",callback_data="stats_reset_today",style="primary")],
        [InlineKeyboardButton(text="🔄 ریست فروش هفته",callback_data="stats_reset_week",style="primary")],
        [InlineKeyboardButton(text="🔄 ریست فروش ماه",callback_data="stats_reset_month",style="primary")],
        [InlineKeyboardButton(text="🔄 ریست همه آمار فروش",callback_data="stats_reset_all",style="danger")],
        [InlineKeyboardButton(text="🔙 بازگشت",callback_data="admin_back",style="primary")],
    ])

def admin_back_button():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back", style="primary")]])


def admin_userlist_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 مشتریان فعال (خریدکرده)",
                              callback_data="admin_userlist_active", style="success")],
        [InlineKeyboardButton(text="👥 کل کاربران", callback_data="admin_userlist_all", style="primary")],
        [InlineKeyboardButton(text="🚫 بن با آیدی عددی", callback_data="admin_ban_id", style="danger")],
        [InlineKeyboardButton(
            text="🔙 بازگشت", callback_data="admin_back", style="primary")],
    ])


def admin_discount_menu(discounts: list | None = None):
    buttons = []
    for d in (discounts or []):
        value_text = f"{d['amount']:,}ت" if d.get(
            "discount_type") == "amount" else f"{d['percent']}٪"
        buttons.append([InlineKeyboardButton(
            text=f"🎟 {d['code']} | {value_text} | 🔁 {d['uses']}",
            callback_data=f"discdetail_{d['id']}", style="primary",
        )])
    buttons.append([InlineKeyboardButton(
        text="➕ ساخت کد تخفیف جدید", callback_data="new_discount", style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",
                   callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def discount_detail_keyboard(discount_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💯 ویرایش مقدار تخفیف",
                              callback_data=f"discedit_value_{discount_id}", style="primary")],
        [InlineKeyboardButton(text="👤 ویرایش کاربران مجاز",
                              callback_data=f"discedit_users_{discount_id}", style="primary")],
        [InlineKeyboardButton(text="🎯 ویرایش پلن‌های مجاز",
                              callback_data=f"discedit_plans_{discount_id}", style="primary")],
        [InlineKeyboardButton(text="🔁 ویرایش تعداد استفاده",
                              callback_data=f"discedit_uses_{discount_id}", style="success")],
        [InlineKeyboardButton(text="💰 ویرایش حداقل مبلغ سفارش",
                              callback_data=f"discedit_minorder_{discount_id}", style="primary")],
        [InlineKeyboardButton(text="🔂 ویرایش سقف استفاده هر کاربر",
                              callback_data=f"discedit_maxuser_{discount_id}", style="primary")],
        [InlineKeyboardButton(text="⏰ ویرایش تاریخ انقضا",
                              callback_data=f"discedit_expiry_{discount_id}", style="primary")],
        [InlineKeyboardButton(
            text="🗑 حذف کد تخفیف", callback_data=f"discdelete_{discount_id}", style="danger")],
        [InlineKeyboardButton(text="🔙 بازگشت به لیست",
                              callback_data="admin_discount", style="primary")],
    ])


def discount_delete_confirm_keyboard(discount_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ بله، حذف کن", callback_data=f"discdeleteconfirm_{discount_id}", style="danger")],
        [InlineKeyboardButton(
            text="❌ انصراف", callback_data=f"discdetail_{discount_id}", style="danger")],
    ])


def admin_user_actions_keyboard(uid: str, is_blocked: bool = False, show_pm_link: bool = True):
    block_btn = (
        InlineKeyboardButton(text="✅ رفع مسدودیت کاربر",
                             callback_data=f"toggleblock_{uid}", style="success")
        if is_blocked else
        InlineKeyboardButton(text="🚫 مسدود کردن کاربر",
                             callback_data=f"toggleblock_{uid}", style="danger")
    )
    pm_row = [InlineKeyboardButton(
        text="✉️ پیام خصوصی به کاربر", callback_data=f"pm_{uid}", style="primary")]
    # دکمه‌ی "رفتن به پیوی کاربر" (لینک tg://user) برای برخی کاربران با تنظیمات حریم‌خصوصی محدودتر
    # توسط تلگرام رد می‌شود، پس handlers/admin.py در صورت خطای BUTTON_USER_PRIVACY_RESTRICTED همین کیبورد را با
    # show_pm_link=False دوباره می‌سازد تا فقط همین دکمه حذف شود.
    if show_pm_link:
        pm_row.append(InlineKeyboardButton(
            text="💬 رفتن به پیوی کاربر", url=f"tg://user?id={uid}", style="primary"))
    return InlineKeyboardMarkup(inline_keyboard=[
        pm_row,
        [InlineKeyboardButton(text="💰 شارژ دستی",
                              callback_data=f"custom_{uid}", style="primary")],
        [InlineKeyboardButton(text="📒 حسابداری کاربر (تراکنش‌ها/منشأ پول)",
                              callback_data=f"accounting_{uid}_0", style="primary")],
        [InlineKeyboardButton(text="ارسال کانفیگ VIP",
                              callback_data=f"sendvip_{uid}", style="primary")],
        [InlineKeyboardButton(text="📦 مشاهده و مدیریت سرویس‌های کاربر",
                              callback_data=f"svcs_{uid}", style="primary")],
        [block_btn],
        [InlineKeyboardButton(
            text="🔙 بازگشت", callback_data="admin_back", style="primary")],
    ])


def admin_pm_cancel_keyboard(uid: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ انصراف از پیام خصوصی",
                              callback_data=f"useropen_{uid}", style="danger")],
    ])


def admin_charge_approval_keyboard(uid: str, amount: int, receipt_id: int):
    # 🐛 فیکس: قبلاً callback_data فقط uid+amount بود که برای دو رسید متفاوت با همان مبلغ
    # یکسان می‌شد و قفل دائمی ضدتکرار (claim_admin_action) بعد از اولین بار همیشه برای
    # همان کاربر+مبلغ پیام «قبلاً پردازش شده» می‌داد. اضافه‌کردن receipt_id هر دکمه
    # را منحصربه‌فرد می‌کند.
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"✅ تأیید {amount:,}", callback_data=f"approve_{uid}_{amount}_{receipt_id}", style="success")],
        [InlineKeyboardButton(text="💵 مبلغ دلخواه",
                              callback_data=f"custom_{uid}", style="primary")],
        [InlineKeyboardButton(
            text="❌ رد", callback_data=f"reject_{uid}_{receipt_id}", style="danger")],
    ])


def admin_purchase_card_approval_keyboard(uid: str, plan_key: str, price: int, receipt_id: int):
    # 🐛 فیکس: همان دلیل بالا — receipt_id را اضافه می‌کنیم تا دو رسید برای همان کاربر/پلن/قیمت با هم تداخل نکنند.
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"✅ تأیید پرداخت ({price:,} ت)", callback_data=f"approvepay|{uid}|{plan_key}|{price}|{receipt_id}", style="success")],
        [InlineKeyboardButton(
            text="❌ رد رسید", callback_data=f"rejectpay|{uid}|{receipt_id}", style="danger")],
    ])


def admin_purchase_notify_keyboard(uid: str, plan_key: str | None = None, order_id: int | None = None):
    suffix = f"|{order_id}" if order_id else ""
    oid = order_id or 0

    # اگر پنل مرزبان فعال است و برای دسته‌بندی این پلن یک planSlug نگاشت شده
    # باشد، دکمه‌ی «ارسال خودکار از پنل» هم علاوه‌بر روش دستی (که هیچ تغییری
    # نکرده) نمایش داده می‌شود؛ انتخاب نهایی همیشه با ادمین است.
    auto_row = []
    if plan_key:
        mapping = db.get_panel_map_for_plan_key(plan_key)
        if mapping and mapping.get("enabled"):
            auto_row = [[InlineKeyboardButton(
                text="📤 ارسال خودکار از پنل", callback_data=f"marzbansend|{uid}|{plan_key}|{oid}", style="primary")]]

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ارسال کانفیگ VIP — دستی",
                              callback_data=f"sendvip_{uid}{suffix}", style="primary")],
        *auto_row,
    ])


def config_delivery_keyboard(guide_url: str, apps_url: str | None = None, is_test: bool = False):
    """کیبورد تحویل سرویس دقیقاً مثل قالب تحویلی: فقط دکمه سبز بازگشت به منوی اصلی.
    متن دکمه از پنل مدیریت متن قابل ویرایش است."""
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
        text=db.get_text_override("config_delivery_back", "🟢 بازگشت به منو اصلی"),
        callback_data="back", style="success")]])


def ticket_reply_keyboard(uid: str, ticket_id: int | None = None):
    callback = f"ticketreply|{int(ticket_id)}" if ticket_id else f"replyticket_{uid}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="↩️ پاسخ", callback_data=callback, style="primary")],
    ])


# ---------------------------------------------------------------------------
# 📦 مدیریت سرویس‌های کاربران توسط ادمین
# ---------------------------------------------------------------------------
def admin_services_list_keyboard(configs, uid: str):
    buttons = []
    for cfg in configs:
        is_vip = cfg.get("type", "vip") == "vip"
        icon = "" if is_vip else "🎮"
        mark = "❌ " if cfg.get("deleted") else ""
        label = f"{mark}{icon + ' ' if icon else ''}{cfg['plan']}"
        buttons.append([InlineKeyboardButton(
            text=label, callback_data=f"svcdetail_{cfg['id']}", style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",
                   callback_data=f"useractions_{uid}", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_service_detail_keyboard(cfg: dict, uid: str):
    cfg_id = cfg["id"]
    is_deleted = bool(cfg.get("deleted"))
    is_vip = cfg.get("type", "vip") == "vip"
    buttons = []

    if is_deleted:
        buttons.append([InlineKeyboardButton(text="♻️ بازگردانی سرویس",
                       callback_data=f"svcrestore_{cfg_id}", style="primary")])
        buttons.append([InlineKeyboardButton(text="🗑 حذف همیشگی (غیرقابل بازگشت)",
                       callback_data=f"svcpurge_{cfg_id}", style="danger")])
    else:
        buttons.append([InlineKeyboardButton(text="✏️ تغییر لینک ساب",
                       callback_data=f"svcedit_link_{cfg_id}", style="primary")])
        if is_vip:
            buttons.append([InlineKeyboardButton(
                text="🖼 تغییر عکس کیوآرکد", callback_data=f"svcedit_qr_{cfg_id}", style="primary")])
        else:
            buttons.append([InlineKeyboardButton(
                text="📁 مدیریت فایل‌های کانفیگ", callback_data=f"svcfiles_{cfg_id}", style="primary")])

        if cfg.get("source") in ("marzban", "pasargad") and cfg.get("service_id"):
            buttons.append([InlineKeyboardButton(
                text="🔁 تمدید از پنل", callback_data=f"marzbanrenew_{cfg_id}", style="success")])
            buttons.append([InlineKeyboardButton(text="⏸ غیرفعال‌کردن در پنل",
                           callback_data=f"marzbandisable_{cfg_id}", style="danger")])
            buttons.append([InlineKeyboardButton(text="▶️ فعال‌کردن در پنل",
                           callback_data=f"marzbanenable_{cfg_id}", style="primary")])
            buttons.append([InlineKeyboardButton(text="🔄 ساخت لینک ساب جدید (خودکار از پنل)",
                           callback_data=f"svcrevokesub_{cfg_id}", style="danger")])

        buttons.append([InlineKeyboardButton(text="🗑 حذف سرویس (مخفی از کاربر)",
                       callback_data=f"svcdelete_{cfg_id}", style="danger")])

    buttons.append([InlineKeyboardButton(
        text="🔙 بازگشت به لیست سرویس‌ها", callback_data=f"svcs_{uid}", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_purge_confirm_keyboard(cfg_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله، برای همیشه حذف کن",
                              callback_data=f"svcpurgeconfirm_{cfg_id}", style="danger")],
        [InlineKeyboardButton(
            text="❌ انصراف", callback_data=f"svcdetail_{cfg_id}", style="danger")],
    ])


def admin_request_queue_menu(order_count: int = 0, receipt_count: int = 0):
    order_label = f"📦 سفارش‌های در انتظار ({order_count})" if order_count else "📦 سفارش‌های در انتظار"
    receipt_label = f"🧾 رسیدهای در انتظار تایید ({receipt_count})" if receipt_count else "🧾 رسیدهای در انتظار تایید"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=order_label, callback_data="admin_order_queue", style="primary")],
        [InlineKeyboardButton(
            text=receipt_label, callback_data="admin_pending_receipts", style="primary")],
        [InlineKeyboardButton(
            text="🔙 بازگشت", callback_data="admin_back", style="primary")],
    ])


def admin_pending_receipts_keyboard(receipts):
    buttons = []
    for r in receipts:
        kind = r.get("kind")
        if kind == "charge":
            label = f"💰 شارژ — 🆔 {r['telegram_id']} — {r['amount']:,} ت"
        elif kind == "custom_card":
            label = f"🛠 سرویس سفارشی — 🆔 {r['telegram_id']} — {r['amount']:,} ت"
        elif kind == "plan_crypto":
            label = f"💱 ارزی — 🆔 {r['telegram_id']} — {r['amount']:,} ت"
        else:
            label = f"💳 {r.get('label') or 'خرید سرویس'} — 🆔 {r['telegram_id']} — {r['amount']:,} ت"
        buttons.append([InlineKeyboardButton(
            text=label, callback_data=f"receiptview|{int(r['id'])}", style="primary"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",
                   callback_data="admin_request_queue", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_clear_receipts_confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله، همه رو علامت بزن",
                              callback_data="clearreceipts_do", style="danger")],
        [InlineKeyboardButton(
            text="❌ انصراف", callback_data="admin_pending_receipts", style="danger")],
    ])


def admin_order_queue_keyboard(orders):
    buttons = []
    for o in orders:
        uid = o.get("telegram_id") or ""
        kind = o.get("_kind", "plan")
        oid = int(o["id"])
        if kind == "custom":
            label = f"🛠 🆔 {uid} — {o.get('price', 0):,} ت — {o.get('volume_gb', 0)}GB/{o.get('days', 0)}روز"
        else:
            label = f"📦 🆔 {uid} — {o.get('plan_name','سرویس')} — {o.get('price',0):,} ت"
        buttons.append([InlineKeyboardButton(
            text=label, callback_data=f"deliverydetail|{kind}|{oid}", style="primary"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",
                   callback_data="admin_request_queue", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_delivery_detail_keyboard(item: dict):
    kind = item.get("_kind", "plan")
    oid = int(item["id"])
    uid = str(item.get("telegram_id") or "")
    buttons = []
    if kind == "custom":
        buttons.append([InlineKeyboardButton(
            text="📤 ارسال دستی", callback_data=f"sendcustomorder_{oid}", style="primary")])
        buttons.append([InlineKeyboardButton(
            text="⚡ ارسال خودکار از پنل", callback_data=f"marzbancustom_{oid}", style="success")])
    else:
        plan_key = item.get("plan_key") or ""
        buttons.append([InlineKeyboardButton(
            text="📤 ارسال دستی", callback_data=f"sendvip_{uid}|{oid}", style="primary")])
        mapping = db.get_panel_map_for_plan_key(plan_key) if plan_key else None
        if mapping and mapping.get("enabled"):
            buttons.append([InlineKeyboardButton(
                text="⚡ ارسال خودکار از پنل", callback_data=f"marzbansend|{uid}|{plan_key}|{oid}", style="success")])
    buttons.append([InlineKeyboardButton(text="🗑 حذف از صف", callback_data=f"dismissdelivery|{kind}|{oid}", style="danger")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_order_queue", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_ticket_list_keyboard(tickets):
    buttons=[]
    for tkt in tickets:
        text=f"🎫 #{tkt['id']} — 🆔 {tkt['telegram_id']}"
        if tkt.get("user_name"): text += f" — {str(tkt['user_name'])[:24]}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"ticketadmin|{int(tkt['id'])}", style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_ticket_detail_keyboard(ticket_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ پاسخ به تیکت", callback_data=f"ticketreply|{int(ticket_id)}", style="success")],
        [InlineKeyboardButton(text="🗑 حذف تیکت", callback_data=f"ticketdelete|{int(ticket_id)}", style="danger")],
        [InlineKeyboardButton(text="🔙 لیست تیکت‌ها", callback_data="admintickets", style="primary")],
    ])

def admin_clear_orders_confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ بله، همه رو پاک کن",
                              callback_data="clearorders_do", style="danger")],
        [InlineKeyboardButton(
            text="❌ انصراف", callback_data="admin_order_queue", style="danger")],
    ])


# ---------------------------------------------------------------------------
# 👥 لیست کاربران با صفحه‌بندی ۱۰تا۱۰تا (مرتب‌شده بر اساس بیشترین خرید)
# ---------------------------------------------------------------------------
def admin_userlist_page_keyboard(users: list, page: int, has_next: bool, list_kind: str = "active"):
    buttons = []
    for u in users:
        buttons.append([InlineKeyboardButton(
            text=f"👤 {u['name']} | 🆔 {u['telegram_id']}" + (f" | @{u.get('telegram_username')}" if u.get('telegram_username') else ""),
            callback_data=f"useropen_{u['telegram_id']}", style="primary",
        )])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ صفحه قبل", callback_data=f"userpage_{list_kind}_{page - 1}", style="primary"))
    if has_next:
        nav_row.append(InlineKeyboardButton(
            text="➡️ صفحه بعد", callback_data=f"userpage_{list_kind}_{page + 1}", style="primary"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",
                   callback_data="admin_userlist", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ---------------------------------------------------------------------------
# 📚 راهنما و اموزش — فهرست قابل‌رشد از پنل ادمین (متن/عکس/فیلم)
# ---------------------------------------------------------------------------
def user_guides_menu(guides: list):
    if not guides:
        buttons = []
    else:
        buttons = [
            [InlineKeyboardButton(
                text=f"📖 {g['title']}", callback_data=f"guideopen_{g['id']}", style="primary")]
            for g in guides
        ]
    buttons.append([InlineKeyboardButton(
        text=db.get_text_override("guides_back", "🏠 بازگشت به منوی اصلی"), callback_data="back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def user_guide_detail_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=db.get_text_override("guide_detail_back", "🔙 بازگشت به لیست راهنما"),
                              callback_data="user_guides", style="primary")],
    ])


def admin_guides_menu(guides: list):
    buttons = []
    for i, g in enumerate(guides):
        buttons.append([InlineKeyboardButton(
            text=f"📖 {g['title']}",
            callback_data=f"guideadminopen_{g['id']}",
            style="primary",
        )])
        move_row = []
        if i > 0:
            move_row.append(InlineKeyboardButton(
                text="⬆️",
                callback_data=f"guidemove_{g['id']}_up",
                style="primary",
            ))
        if i < len(guides) - 1:
            move_row.append(InlineKeyboardButton(
                text="⬇️",
                callback_data=f"guidemove_{g['id']}_down",
                style="primary",
            ))
        if move_row:
            buttons.append(move_row)

    buttons.append([InlineKeyboardButton(
        text="➕ افزودن راهنما/اموزش جدید", callback_data="guidenew", style="success")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",
                   callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_guide_detail_keyboard(guide_id: int, index: int, total: int):
    move_row = []
    if index > 0:
        move_row.append(InlineKeyboardButton(
            text="⬆️ بالاتر", callback_data=f"guidemove_{guide_id}_up", style="primary"))
    if index < total - 1:
        move_row.append(InlineKeyboardButton(
            text="⬇️ پایین‌تر", callback_data=f"guidemove_{guide_id}_down", style="primary"))
    buttons = [move_row] if move_row else []
    buttons += [
        [InlineKeyboardButton(
            text="✏️ ویرایش عنوان", callback_data=f"guideeditname_{guide_id}", style="primary")],
        [InlineKeyboardButton(text="📝 ویرایش محتوا (متن/عکس/فیلم)",
                              callback_data=f"guideeditcontent_{guide_id}", style="primary")],
        [InlineKeyboardButton(
            text="🗑 حذف این راهنما", callback_data=f"guidedelete_{guide_id}", style="danger")],
        [InlineKeyboardButton(text="🔙 بازگشت به لیست راهنما",
                              callback_data="admin_guides", style="primary")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_guide_delete_confirm_keyboard(guide_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ بله، حذف کن", callback_data=f"guidedeleteconfirm_{guide_id}", style="danger")],
        [InlineKeyboardButton(
            text="❌ انصراف", callback_data=f"guideadminopen_{guide_id}", style="danger")],
    ])


def admin_guide_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❌ انصراف", callback_data="admin_guides", style="danger")],
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
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",
                   callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_sticker_detail_keyboard(section_key: str, has_custom: bool, is_enabled: bool):
    buttons = [
        [InlineKeyboardButton(text="📤 آپلود/تغییر استیکر",
                              callback_data=f"stickerset_{section_key}", style="success")],
    ]
    if is_enabled:
        buttons.append([InlineKeyboardButton(text="🛑 غیرفعال کردن (بدون استیکر)",
                       callback_data=f"stickeroff_{section_key}", style="danger")])
    else:
        buttons.append([InlineKeyboardButton(text="✅ فعال‌سازی دوباره",
                       callback_data=f"stickeron_{section_key}", style="success")])
    if has_custom:
        buttons.append([InlineKeyboardButton(text="♻️ بازگرداندن به پیش‌فرض",
                       callback_data=f"stickerreset_{section_key}", style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به لیست بخش‌ها",
                   callback_data="admin_stickers", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_sticker_cancel_keyboard(section_key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="❌ انصراف", callback_data=f"stickeropen_{section_key}", style="danger")],
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
        buttons.append([InlineKeyboardButton(
            text="🗑 این لاگ پاک‌سازیشون", callback_data="errlogclear", style="danger")])
    buttons.append([InlineKeyboardButton(text="🔄 به‌روزرسانی",
                   callback_data="errlogrefresh", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_error_log_detail_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 بازگشت به لیست لاگ‌ها",
                              callback_data="errlogrefresh", style="primary")],
    ])


def admin_error_logs_clear_confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ بله، پاکشون", callback_data="errlogclearconfirm", style="danger")],
        [InlineKeyboardButton(
            text="❌ انصراف", callback_data="errlogrefresh", style="danger")],
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
        nav_row.append(InlineKeyboardButton(text="⬅️ صفحه قبل",
                       callback_data=f"refpage_{page - 1}", style="primary"))
    if has_next:
        nav_row.append(InlineKeyboardButton(text="➡️ صفحه بعد",
                       callback_data=f"refpage_{page + 1}", style="primary"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",
                   callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_referred_detail_keyboard(referrer_uid: str, back_page: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 مشاهدهی کامل کاربر دعوت‌کننده",
                              callback_data=f"useropen_{referrer_uid}", style="primary")],
        [InlineKeyboardButton(text="🔙 بازگشت به لیست دعوت‌کنندگان",
                              callback_data=f"refpage_{back_page}", style="primary")],
    ])


def admin_accounting_keyboard(uid: str, page: int, has_next: bool):
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="⬅️ قبل", callback_data=f"accounting_{uid}_{page - 1}", style="primary"))
    if has_next:
        nav_row.append(InlineKeyboardButton(
            text="➡️ بعد", callback_data=f"accounting_{uid}_{page + 1}", style="primary"))
    buttons = [nav_row] if nav_row else []
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به کاربر",
                   callback_data=f"useropen_{uid}", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ---------------------------------------------------------------------------
# 🎟 ساخت کد تخفیف — نوع تخفیف و پلن‌های قابل‌اعمال
# ---------------------------------------------------------------------------
def discount_type_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💯 درصدی", callback_data="disctype_percent", style="primary")],
        [InlineKeyboardButton(text="💵 مبلغ ثابت (تومان)",
                              callback_data="disctype_amount", style="primary")],
    ])


def discount_plans_select_keyboard(selected: list):
    """با هر بار زدن روی یک پلن، انتخاب/عدم‌انتخابش toggle می‌شود؛ ✅ همه یعنی روی همه‌ی پلن‌ها اعمال شود."""
    buttons = [[InlineKeyboardButton(
        text="✅ همه‌ی پلن‌ها (بدون محدودیت)" if not selected else "☑️ همه‌ی پلن‌ها (بدون محدودیت)",
        callback_data="discplan_all", style="success",
    )]]
    for key, plan in db.get_all_plans().items():
        mark = "☑️" if key in selected else "⬜️"
        buttons.append([InlineKeyboardButton(
            text=f"{mark} {plan['name']}", callback_data=f"discplan_{key}", style="primary")])
    buttons.append([InlineKeyboardButton(text="✅ تأیید و ادامه",
                   callback_data="discplan_done", style="success")])
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
        buttons.append([InlineKeyboardButton(
            text=f"{mark} {plan['name']}", callback_data=f"discplaned_{discount_id}_{key}", style="primary")])
    buttons.append([InlineKeyboardButton(
        text="✅ ذخیره", callback_data=f"discplaned_{discount_id}_done", style="success")])
    buttons.append([InlineKeyboardButton(
        text="🔙 انصراف", callback_data=f"discdetail_{discount_id}", style="primary")])
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
    buttons.append([InlineKeyboardButton(text="➕ افزودن نماینده",
                   callback_data="new_agent", style="success")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",
                   callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_agent_row_keyboard(telegram_id: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🗑 حذف این نماینده", callback_data=f"deleteagent_{telegram_id}", style="danger")],
        [InlineKeyboardButton(
            text="🔙 بازگشت", callback_data="admin_agency", style="primary")],
    ])


def admin_agent_actions_keyboard(uid: str):
    """دقیقاً همان کیبورد مدیریت کاربر (admin_user_actions_keyboard)، به‌علاوه‌ی
    یک دکمه‌ی اضافه برای تغییر درصد تخفیف نمایندگی؛ دکمه‌ی بازگشت هم به لیست
    نمایندگان برمی‌گردد (نه لیست کلی کاربران)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💯 تغییر درصد تخفیف نمایندگی",
                              callback_data=f"editagentpercent_{uid}", style="primary")],
        [InlineKeyboardButton(text="💰 شارژ دستی",
                              callback_data=f"custom_{uid}", style="primary")],
        [InlineKeyboardButton(text="📒 حسابداری کاربر (تراکنش‌ها/منشأ پول)",
                              callback_data=f"accounting_{uid}_0", style="primary")],
        [InlineKeyboardButton(text="ارسال کانفیگ VIP",
                              callback_data=f"sendvip_{uid}", style="primary")],
        [InlineKeyboardButton(text="📦 مشاهده و مدیریت سرویس‌های کاربر",
                              callback_data=f"svcs_{uid}", style="primary")],
        [InlineKeyboardButton(
            text="🗑 حذف این نماینده", callback_data=f"deleteagent_{uid}", style="danger")],
        [InlineKeyboardButton(text="🔙 بازگشت به لیست نمایندگان",
                              callback_data="admin_agency", style="primary")],
    ])


# ---------------------------------------------------------------------------
# 🗂 دسته‌بندی‌های VIP (پنل ادمین) — افزودن دسته‌ی جدید، ورود به هر دسته برای
# افزودن/ویرایش/حذف پلن‌های داخلش + تغییر ترتیب نمایش (⬆️/⬇️) دسته‌ها و پلن‌ها.
# ---------------------------------------------------------------------------
def admin_vip_categories_keyboard(parent_key: str | None = None):
    """مدیریت درخت دسته‌بندی VIP. هر دسته می‌تواند زیر‌دسته‌ی اختیاری داشته باشد."""
    parent = db.get_vip_category(parent_key) if parent_key else None
    parent_id = parent["id"] if parent else None
    cats = db.get_vip_categories(parent_id=parent_id)
    buttons = []
    for cat in cats:
        child_count = len(db.get_vip_category_children(cat["id"]))
        plan_count = len(db.get_vip_plans(cat["id"]))
        state = "🟢" if cat.get("enabled", 1) else "🔴"
        buttons.append([InlineKeyboardButton(
            text=f"{state} {cat['name']} ({plan_count} پلن"
                 + (f" | {child_count} زیر‌دسته" if child_count else "") + ")",
            callback_data=f"admincat_{cat['key']}", style="primary")])
    if parent:
        buttons.append([InlineKeyboardButton(text=db.get_text_override("admin_vip_new_subcategory", "➕ زیر‌دسته جدید"),
                                             callback_data=f"newvipsubcat_{parent['key']}", style="success")])
        buttons.append([InlineKeyboardButton(text=db.get_text_override("admin_vip_back_level", "🔙 بازگشت به سطح قبل"),
                                             callback_data=(f"admincat_{db.get_vip_category(parent['parent_id'])['key']}"
                                                           if parent.get("parent_id") and db.get_vip_category(parent["parent_id"])
                                                           else "admin_vip_categories"),
                                             style="primary")])
    else:
        buttons.append([InlineKeyboardButton(text=db.get_text_override("admin_vip_new_root_category", "➕ دسته‌بندی اصلی جدید"),
                                             callback_data="newvipcat", style="success")])
        buttons.append([InlineKeyboardButton(text=db.get_text_override("admin_vip_back", "🔙 بازگشت"),
                                             callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_vip_category_detail_keyboard(category_key: str):
    cat = db.get_vip_category(category_key)
    buttons = []
    if cat:
        children = db.get_vip_category_children(cat["id"])
        plans = db.get_vip_plans(cat["id"])
        for child in children:
            state = "🟢" if child.get("enabled", 1) else "🔴"
            buttons.append([InlineKeyboardButton(
                text=f"{state} 📁 {child['name']}",
                callback_data=f"admincat_{child['key']}", style="primary")])
        for plan in plans:
            buttons.append([InlineKeyboardButton(
                text=f"📦 {plan['name']} — {plan['price']:,} ت",
                callback_data=f"vipplan_{plan['plan_key']}", style="primary")])
    if cat:
        buttons.append([InlineKeyboardButton(text=db.get_text_override("admin_vip_create_subcategory", "➕ ساخت زیر‌دسته (اختیاری)"),
                                             callback_data=f"newvipsubcat_{category_key}", style="success")])
        buttons.append([InlineKeyboardButton(text=db.get_text_override("admin_vip_add_direct_plan", "➕ افزودن پلن مستقیم به این دسته"),
                                             callback_data=f"newvipplan_{category_key}", style="success")])
        buttons.append([InlineKeyboardButton(
            text=(db.get_text_override("admin_vip_disable_category", "🔴 غیرفعال کردن این دسته") if cat.get("enabled", 1) else db.get_text_override("admin_vip_enable_category", "🟢 فعال کردن این دسته")),
            callback_data=f"togglevipcat_{category_key}", style="danger" if cat.get("enabled", 1) else "success")])
        buttons.append([InlineKeyboardButton(text=db.get_text_override("admin_vip_rename_category", "✏️ تغییر نام این دسته"),
                                             callback_data=f"renamevipcat_{category_key}", style="primary")])
        buttons.append([InlineKeyboardButton(text=db.get_text_override("admin_vip_delete_category", "🗑 حذف این دسته"),
                                             callback_data=f"delvipcat_{category_key}", style="danger")])
        parent_cb = (f"admincat_{db.get_vip_category(cat['parent_id'])['key']}"
                     if cat.get("parent_id") and db.get_vip_category(cat["parent_id"])
                     else "admin_vip_categories")
        buttons.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data=parent_cb, style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_vip_plan_detail_keyboard(plan_key: str, category_key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ ویرایش نام", callback_data=f"vipplanname_{plan_key}", style="primary")],
        [InlineKeyboardButton(text="💰 ویرایش قیمت", callback_data=f"vipplanprice_{plan_key}", style="primary")],
        [InlineKeyboardButton(text="📦 ویرایش حجم (گیگ)", callback_data=f"vipplangb_{plan_key}", style="primary")],
        [InlineKeyboardButton(text="⏳ ویرایش مدت (روز، ۰=نامحدود)", callback_data=f"vipplandays_{plan_key}", style="primary")],
        [InlineKeyboardButton(text="👥 ویرایش سقف کاربر (۰ تا ۱۰، 0=نامحدود)", callback_data=f"vipplanuserlimit_{plan_key}", style="primary")],
        [InlineKeyboardButton(text="🗑 حذف این پلن", callback_data=f"delvipplan_{plan_key}", style="danger")],
        [InlineKeyboardButton(text="🔙 بازگشت به دسته", callback_data=f"admincat_{category_key}", style="primary")],
    ])


# ---------------------------------------------------------------------------
# 🔗 اتصال پنل مرزبان
# ---------------------------------------------------------------------------
def admin_marzban_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📡 تست اتصال (/me)",
                              callback_data="marzban_test", style="primary")],
        [InlineKeyboardButton(text="🚦 ترافیک/مصرف برند (/traffic)",
                              callback_data="marzban_traffic", style="primary")],
        [InlineKeyboardButton(text="📦 مشاهده‌ی بسته‌های پنل فعال (/plans)",
                              callback_data="marzban_plans", style="primary")],
        [InlineKeyboardButton(text="🗂 نگاشت دسته‌بندی‌های VIP",
                              callback_data="marzban_map_vip", style="primary")],
        [InlineKeyboardButton(text="🧪 نگاشت پیش‌فرض «تست رایگان»",
                              callback_data="marzban_map_free_test", style="primary")],
        [InlineKeyboardButton(
            text="🔙 بازگشت", callback_data="admin_back", style="primary")],
    ])


def marzban_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔙 بازگشت", callback_data="admin_marzban", style="primary")],
    ])


def marzban_map_category_pick_keyboard(categories: list[dict], scope: str):
    """لیست دسته‌بندی‌های VIP برای انتخاب اینکه کدام‌یک نگاشت شود."""
    buttons = []
    for cat in categories:
        mapping = db.get_marzban_plan_map(scope, cat["id"])
        mark = f" ✅ ({mapping['plan_slug']})" if mapping else ""
        buttons.append([InlineKeyboardButton(
            text=f"{cat['name']}{mark}", callback_data=f"marzbanmapcat_{scope}_{cat['id']}", style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",
                   callback_data="admin_marzban", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def marzban_map_vip_category_pick_keyboard(categories: list[dict]):
    """قدم اول نگاشت اختصاصی VIP: انتخاب دسته‌بندی (فقط برای رفتن به لیست
    پلن‌های داخل آن دسته، نه ذخیره‌ی مستقیم نگاشت)."""
    buttons = [
        [InlineKeyboardButton(
            text=cat["name"], callback_data=f"marzbanmapvipcat_{cat['id']}", style="primary")]
        for cat in categories
    ]
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",
                   callback_data="admin_marzban", style="primary")])
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
            text=label, callback_data=f"marzbanmapvipplan_{category_id}_{p['id']}", style="primary")])
    buttons.append([InlineKeyboardButton(
        text="🗂 نگاشت پیش‌فرض کل این دسته (اختیاری)",
        callback_data=f"marzbanmapcat_vip_category_{category_id}", style="primary",
    )])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",
                   callback_data="marzban_map_vip", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def marzban_plan_pick_keyboard(plans: list[dict], callback_prefix: str):
    """لیست بسته‌های واقعی مرزبان (از /plans) برای انتخاب — plans باید هرکدام
    حداقل کلید 'idx' (اندیس محلی در state) و متن نمایشی 'label' داشته باشند."""
    buttons = [
        [InlineKeyboardButton(
            text=p["label"], callback_data=f"{callback_prefix}_{p['idx']}", style="primary")]
        for p in plans
    ]
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",
                   callback_data="admin_marzban", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ---------------------------------------------------------------------------
# ℹ️ اطلاعات ربات (قالب فروشی)
# ---------------------------------------------------------------------------
def admin_botinfo_menu():
    labels = bot_info.labels()
    buttons = []
    for key, label in labels.items():
        buttons.append([InlineKeyboardButton(
            text=f"✏️ {label}", callback_data=f"botinfoedit_{key}", style="primary")])
    buttons.append([InlineKeyboardButton(text="⚙️ تنظیمات پرداخت‌ها",
                   callback_data="botinfo_payment_settings", style="success")])
    buttons.append([InlineKeyboardButton(text="🟣 تنظیمات Tronado",
                   callback_data="botinfo_tronado", style="primary")])
    buttons.append([InlineKeyboardButton(text="🟠 تنظیمات FrenzyEx",
                   callback_data="botinfo_frenzyex", style="primary")])
    buttons.append([InlineKeyboardButton(text="📢 مدیریت کانال‌های اجباری",
                   callback_data="botinfochannels", style="primary")])
    buttons.append([InlineKeyboardButton(text="💱 قیمت‌های پشتیبان پرداخت ارزی",
                   callback_data="admin_crypto_fallback", style="primary")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",
                   callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)




def admin_gateway_settings_menu(provider: str):
    if provider == "tronado":
        rows = [
            [InlineKeyboardButton(text="✏️ فعال/غیرفعال کردن Tronado", callback_data="botinfoedit_tronado_enabled", style="primary")],
            [InlineKeyboardButton(text="🔑 وارد کردن API Key ترنادو", callback_data="botinfoedit_tronado_api_key", style="primary")],
            [InlineKeyboardButton(text="💳 کیف پول TRX مقصد", callback_data="botinfoedit_tronado_wallet", style="primary")],
            [InlineKeyboardButton(text="🔗 Callback URL", callback_data="botinfoedit_tronado_callback_url", style="primary")],
            [InlineKeyboardButton(text="🔐 IPN Signing Key", callback_data="botinfoedit_tronado_ipn_signing_key", style="primary")],
            [InlineKeyboardButton(text="🌐 آدرس API", callback_data="botinfoedit_tronado_base_url", style="primary")],
            [InlineKeyboardButton(text="💸 سهم کارمزد (0-100)", callback_data="botinfoedit_tronado_wage_percentage", style="primary")],
            [InlineKeyboardButton(text="🧪 تست اتصال Tronado", callback_data="gateway_test_tronado", style="success")],
        ]
    elif provider == "frenzyex":
        rows = [
            [InlineKeyboardButton(text="✏️ فعال/غیرفعال کردن FrenzyEx", callback_data="botinfoedit_frenzy_enabled", style="primary")],
            [InlineKeyboardButton(text="🔑 وارد کردن Merchant API Key", callback_data="botinfoedit_frenzy_api_key", style="primary")],
            [InlineKeyboardButton(text="🔐 Callback Secret", callback_data="botinfoedit_frenzy_callback_secret", style="primary")],
            [InlineKeyboardButton(text="🌐 آدرس API", callback_data="botinfoedit_frenzy_base_url", style="primary")],
            [InlineKeyboardButton(text="💳 روش پرداخت auto/standard/nowpay", callback_data="botinfoedit_frenzy_payment_method", style="primary")],
            [InlineKeyboardButton(text="🧪 تست اتصال FrenzyEx", callback_data="gateway_test_frenzyex", style="success")],
        ]
    else:
        rows = []
    rows.append([InlineKeyboardButton(text="🔙 بازگشت به اطلاعات ربات", callback_data="admin_botinfo", style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_payment_settings_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 کارت‌به‌کارت: تغییر وضعیت", callback_data="payment_toggle_card", style="primary"),
         InlineKeyboardButton(text="🌐 آنلاین: تغییر وضعیت", callback_data="payment_toggle_online", style="primary")],
        [InlineKeyboardButton(text="💱 ارز: تغییر وضعیت", callback_data="payment_toggle_crypto", style="primary"),
         InlineKeyboardButton(text="👛 کیف پول: تغییر وضعیت", callback_data="payment_toggle_wallet", style="primary")],
        [InlineKeyboardButton(text="↕️ ترتیب روش‌های پرداخت", callback_data="botinfoedit_payment_methods_order", style="success")],
        [InlineKeyboardButton(text="🎲 نحوه نمایش شماره کارت‌ها", callback_data="botinfoedit_card_display_mode", style="primary")],
        [InlineKeyboardButton(text="💳 مدیریت شماره کارت‌ها", callback_data="botinfoedit_card_numbers", style="primary")],
        [InlineKeyboardButton(text="💰 حداقل شارژ کیف پول", callback_data="botinfoedit_wallet_min", style="primary")],
        [InlineKeyboardButton(text="💰 حداکثر شارژ کیف پول", callback_data="botinfoedit_wallet_max", style="primary")],
        [InlineKeyboardButton(text="🌐 انتخاب درگاه آنلاین فعال", callback_data="botinfoedit_online_gateway", style="success")],
        [InlineKeyboardButton(text="🔙 بازگشت به اطلاعات ربات", callback_data="admin_botinfo", style="danger")],
    ])


def admin_botinfo_field_keyboard(key: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔙 بازگشت", callback_data="admin_botinfo", style="primary")],
    ])


def admin_crypto_fallback_menu(values: dict[str, str | None]):
    buttons = [
        [InlineKeyboardButton(text=f"🟣 TON — {values.get('TON') or 'تنظیم نشده'} تومان",
                              callback_data="crypto_fallback_edit_TON", style="primary")],
        [InlineKeyboardButton(text=f"🔴 TRX — {values.get('TRX') or 'تنظیم نشده'} تومان",
                              callback_data="crypto_fallback_edit_TRX", style="primary")],
        [InlineKeyboardButton(text=f"🟢 USDT — {values.get('USDT') or 'تنظیم نشده'} تومان",
                              callback_data="crypto_fallback_edit_USDT", style="primary")],
        [InlineKeyboardButton(
            text="🔙 بازگشت", callback_data="admin_botinfo", style="primary")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_botinfo_channels_menu(channels: list[dict]):
    buttons = []
    for ch in channels:
        buttons.append([InlineKeyboardButton(
            text=f"❌ {ch.get('name') or ch.get('id')}",
            callback_data=f"botinfochdel_{ch.get('id')}", style="danger",
        )])
    buttons.append([InlineKeyboardButton(text="➕ افزودن کانال جدید",
                   callback_data="botinfochadd", style="success")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",
                   callback_data="admin_botinfo", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ---------------------------------------------------------------------------
# 🛡️ اتصال پنل پاسارگارد (پنل VPN)
# ---------------------------------------------------------------------------
def admin_pasargad_menu(status_text: str, panels=None):
    buttons = [
        [InlineKeyboardButton(text="➕ افزودن پنل پاسارگارد",
                              callback_data="pasargad_add", style="success")],
    ]
    for p in (panels or []):
        mark = " ✅" if p.get("is_active") else ""
        buttons.append([InlineKeyboardButton(
            text=f"🛡️ {p.get('name') or p.get('base_url')}{mark}",
            callback_data=f"pasargad_edit_{p['id']}", style="primary"
        )])
    buttons += [
        [InlineKeyboardButton(text="🔌 تست اتصال پنل فعال",
                              callback_data="pasargadtest", style="primary")],
        [InlineKeyboardButton(
            text="🔙 بازگشت", callback_data="admin_back", style="primary")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_pasargad_panel_actions(panel: dict):
    mark = " ✅ فعال" if panel.get("is_active") else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"🛡️ {panel.get('name') or 'پنل'}{mark}", callback_data="noop", style="primary")],
        [InlineKeyboardButton(
            text="✏️ ویرایش اطلاعات", callback_data=f"pasargad_editform_{panel['id']}", style="primary")],
        [InlineKeyboardButton(text="✅ فعال کردن این پنل",
                              callback_data=f"pasargad_activate_{panel['id']}", style="success")],
        [InlineKeyboardButton(
            text="🔌 تست اتصال", callback_data=f"pasargad_test_{panel['id']}", style="primary")],
        [InlineKeyboardButton(text="🔙 لیست پنل‌ها",
                              callback_data="admin_pasargad", style="primary")],
    ])


def admin_pasargad_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 لغو", callback_data="admin_pasargad", style="danger")]])

# ---------------------------------------------------------------------------
# 🔀 انتخاب پنل VPN فعال (وقتی هردو پنل مرزبان و پاسارگارد متصل باشند)
# ---------------------------------------------------------------------------


def admin_panel_choose_menu(available: list, active: str | None):
    labels = {"marzban": "🔗 مرزبان (Marzban)",
              "pasargad": "🛡️ پاسارگارد (PasarGuard)"}
    buttons = []
    for key in ("marzban", "pasargad"):
        if key not in available:
            continue
        mark = " ✅" if key == active else ""
        buttons.append([InlineKeyboardButton(
            text=f"{labels[key]}{mark}", callback_data=f"panelchoose_{key}", style="success" if key == active else "primary",
        )])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",
                   callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_manage_admins_keyboard(admins=None):
    buttons = []
    for a in (admins or []):
        buttons.append([InlineKeyboardButton(
            text=f"👤 {a.get('name') or a['telegram_id']} — {a['telegram_id']}", callback_data=f"subadm_{a['telegram_id']}", style="primary")])
    buttons.append([InlineKeyboardButton(
        text="➕ افزودن ادمین فرعی", callback_data="subadm_add", style="success")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت",
                   callback_data="admin_back", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_permissions_keyboard(admin_id: str, selected=None):
    selected = set(selected or [])
    buttons = []
    for key, label in db.ADMIN_PERMISSIONS.items():
        mark = "✅" if key in selected else "☑️"
        # رفع باگ: از ':' به‌جای '_' برای جدا کردن آیدی از نام قابلیت استفاده می‌شود، چون خود
        # کلیدهای قابلیت مثل "vpn_panel" و "orders_toggle" داخلشان زیرخط دارند و با split قبلی قاطی می‌شدند.
        buttons.append([InlineKeyboardButton(
            text=f"{mark} {label}", callback_data=f"subadmperm_{admin_id}:{key}", style="success" if key in selected else "primary")])
    buttons.append([InlineKeyboardButton(text="🗑 حذف این ادمین",
                   callback_data=f"subadmdel_{admin_id}", style="danger")])
    buttons.append([InlineKeyboardButton(text="🔙 لیست ادمین‌ها",
                   callback_data="admin_manage_admins", style="primary")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ---------------------------------------------------------------------------
# 🧩 کیبوردهای پرداخت سفارشی/ارزی (برای سازگاری با handlerهای خرید)
# ---------------------------------------------------------------------------
def admin_crypto_approval_keyboard(uid: str, plan_key: str, price: int, receipt_id: int, txid: str | None, asset: str):
    # callback_data تلگرام حداکثر 64 بایت است؛ TXID و plan_key را داخل callback قرار نمی‌دهیم.
    # تمام اطلاعات رسید از روی receipt_id در handlers/admin.py خوانده می‌شود.
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"✅ تأیید پرداخت {asset.upper()} — {price:,} ت",
            callback_data=f"approvecrypto|{receipt_id}",
            style="success",
        )],
        [InlineKeyboardButton(
            text="❌ رد رسید ارزی",
            callback_data=f"rejectcrypto|{receipt_id}",
            style="danger",
        )],
    ])


def custom_build_payment_keyboard():
    # 🆕 هماهنگ با ترتیب purchase_payment_keyboard: کارت به کارت اول، آنلاین دوم، کیف پول آخر.
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💳 کارت به کارت", callback_data="cbuild_pay_card", style="success")],
        [InlineKeyboardButton(
            text="🌐 پرداخت آنلاین", callback_data="cbuild_pay_online", style="primary")],
        [InlineKeyboardButton(text="👛 پرداخت از کیف پول",
                              callback_data="cbuild_pay_wallet", style="success")],
        [InlineKeyboardButton(
            text="🔙 لغو", callback_data="back", style="danger")],
    ])


def custom_duration_keyboard():
    raw=bot_info.get("duration_options") or "30:یک ماهه,60:دو ماهه,90:سه ماهه"
    rows=[]
    for item in raw.split(",")[:6]:
        try:
            a,b=item.split(":",1); d=int(a.strip()); label=b.strip() or f"{d} روزه"
            if d==30: label=db.get_text_override("duration_30",label)
            elif d==60: label=db.get_text_override("duration_60",label)
            elif d==90: label=db.get_text_override("duration_90",label)
            if d>0: rows.append([InlineKeyboardButton(text=label,callback_data=f"custom_days_{d}",style="primary")])
        except Exception: continue
    rows.append([InlineKeyboardButton(text=db.get_text_override("back", "🔙 بازگشت"),callback_data="cbuild_cancel",style="danger")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def custom_build_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=db.get_text_override("custom_cancel", "❌ لغو"), callback_data="back", style="danger")],
    ])


def admin_custom_order_card_approval_keyboard(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ تأیید سفارش", callback_data=f"approvecustom_{order_id}", style="success")],
        [InlineKeyboardButton(
            text="❌ رد سفارش", callback_data=f"rejectcustom_{order_id}", style="danger")],
    ])


def admin_custom_order_notify_keyboard(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📦 مدیریت سفارش", callback_data=f"customorder_{order_id}", style="primary")],
    ])


# ---------------------------------------------------------------------------
# 🖥️ کیبوردهای مدیریت چندنمونه‌ای پنل‌ها
# ---------------------------------------------------------------------------
def admin_vpn_panel_types_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛡️ مرزبان", callback_data="vpntype|marzban"), InlineKeyboardButton(text="🔐 پاسارگارد", callback_data="vpntype|pasargad")],
        [InlineKeyboardButton(text="🦋 Rebecca", callback_data="vpntype|rebecca"), InlineKeyboardButton(text="🧩 ثنایی", callback_data="vpntype|sanaei")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin_back")],
    ])

def admin_vpn_panel_list_keyboard(panel_type, instances):
    rows=[[InlineKeyboardButton(text=f"{'🟢' if p.get('enabled') else '🔴'} {p.get('name') or p['id']}", callback_data=f"vpndetail|{p['id']}")] for p in instances]
    rows.append([InlineKeyboardButton(text="➕ افزودن نمونه", callback_data=f"vpnadd|{panel_type}")])
    rows.append([InlineKeyboardButton(text="🔙 انواع پنل‌ها", callback_data="admin_vpn_panels")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_vpn_panel_detail_keyboard(panel):
    pid=panel['id']
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗂 نگاشت پلن‌ها", callback_data=f"vpnmap|{pid}"), InlineKeyboardButton(text="🔌 تست اتصال", callback_data=f"vpntest|{pid}")],
        [InlineKeyboardButton(text="✏️ ویرایش", callback_data=f"vpnedit|{pid}"), InlineKeyboardButton(text=("🔴 غیرفعال" if panel.get('enabled') else "🟢 فعال"), callback_data=f"vpntoggle|{pid}")],
        [InlineKeyboardButton(text="🗑 حذف", callback_data=f"vpndelete|{pid}")],
        [InlineKeyboardButton(text="🔙 لیست پنل‌ها", callback_data=f"vpntype|{panel.get('panel_type')}")],
    ])

def admin_vpn_panel_delete_confirm_keyboard(panel_id):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🗑 بله، حذف کن", callback_data=f"vpndeleteconfirm|{panel_id}")],[InlineKeyboardButton(text="🔙 انصراف", callback_data=f"vpndetail|{panel_id}")]])

def admin_vpn_panel_edit_menu_keyboard(panel):
    pid=panel['id']; rows=[]
    fields=[("name","🏷 نام"),("base_url","🌐 آدرس")]
    if panel.get('panel_type')=='rebecca':
        fields.append(("api_key","🔐 API Key"))
    elif panel.get('panel_type') in {'pasargad','sanaei'}:
        # این دو پنل می‌توانند بسته به نسخه/تنظیمات با یوزرنیم/رمز یا
        # API Token کار کنند؛ هر دو مسیر برای ویرایش در دسترس می‌مانند.
        fields.extend([
            ("username","👤 نام کاربری"),
            ("password","🔑 رمز عبور"),
            ("api_key","🔐 API Key / Token"),
        ])
    else:
        fields.extend([("username","👤 نام کاربری"),("password","🔑 رمز عبور")])
    for field,label in fields:
        rows.append([InlineKeyboardButton(text=f"{label}", callback_data=f"vpneditfield|{pid}|{field}")])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"vpndetail|{pid}")]); return InlineKeyboardMarkup(inline_keyboard=rows)

def vpn_panel_back_keyboard(panel_id): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"vpndetail|{panel_id}")]])
def admin_vpn_panel_types_cancel_keyboard(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ انصراف", callback_data="admin_vpn_panels")]])
def admin_vpn_panel_map_menu_keyboard(panel_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗂 نگاشت پلن‌های VIP", callback_data=f"vpnmapvip|{panel_id}")],
        [InlineKeyboardButton(text="🧩 نگاشت «بساز سرویس خودت»", callback_data=f"vpnmapcustom|{panel_id}")],
        [InlineKeyboardButton(text="🧪 نگاشت تست رایگان", callback_data=f"vpnmapfreetest|{panel_id}")],
        [InlineKeyboardButton(text="🔙 جزئیات پنل", callback_data=f"vpndetail|{panel_id}")],
    ])
def vpn_map_vip_category_pick_keyboard(categories,panel_id):
    rows=[[InlineKeyboardButton(text=f"📁 {c.get('name') or c.get('key')}",callback_data=f"vpnmapvipcat|{panel_id}|{c['id']}")] for c in categories]
    rows.append([InlineKeyboardButton(text="🔙 بازگشت",callback_data=f"vpnmap|{panel_id}")]); return InlineKeyboardMarkup(inline_keyboard=rows)
def vpn_map_vip_plans_keyboard(category_id,plans,panel_id):
    rows=[]
    for p in plans:
        m=db.get_panel_plan_map('vip_plan',p['id']); mark='✅' if m and int(m.get('panel_id',-1))==int(panel_id) else '⚪'
        rows.append([InlineKeyboardButton(text=f"{mark} {p.get('name') or p['plan_key']}",callback_data=f"vpnmapvipplan|{panel_id}|{category_id}|{p['id']}")])
    m=db.get_panel_plan_map('vip_category',category_id); rows.append([InlineKeyboardButton(text=f"{'🗑' if m else '⚪'} نگاشت پیش‌فرض دسته",callback_data=f"vpnmapcatset|{panel_id}|{category_id}")])
    rows.append([InlineKeyboardButton(text="🔙 دسته‌ها",callback_data=f"vpnmapvip|{panel_id}")]); return InlineKeyboardMarkup(inline_keyboard=rows)

def vpn_map_method_keyboard(panel_id: int, scope: str, scope_id: int, category_id: int | None = None):
    """انتخاب روش نگاشت: دریافت واقعی از API پنل یا ثبت مستقیم شناسه.
    برای Sanaei ثبت مستقیم یعنی Inbound ID؛ برای پنل‌های دیگر می‌تواند Template/Remote ID باشد."""
    back = f"vpnmapvipcat|{panel_id}|{category_id}" if category_id else f"vpnmap|{panel_id}"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📡 دریافت و انتخاب از خود پنل", callback_data=f"vpnmapmethod|{panel_id}|{scope}|{scope_id}|{category_id or 0}|catalog", style="success")],
        [InlineKeyboardButton(text="🔌 ثبت مستقیم Inbound / شناسه", callback_data=f"vpnmapmethod|{panel_id}|{scope}|{scope_id}|{category_id or 0}|manual", style="primary")],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data=back, style="danger")],
    ])

def vpn_catalog_pick_keyboard(choices, panel_id):
    """کیبورد انتخاب Template/Service برای نگاشت یک سرویس به پنل."""
    rows = []
    for item in (choices or []):
        if not isinstance(item, dict):
            continue
        idx = item.get("idx")
        if idx is None:
            continue
        name = str(item.get("name") or item.get("title") or item.get("ref") or f"گزینه {idx}")
        # نام‌های خیلی بلند باعث خطای Telegram (markup too long) نشوند.
        if len(name) > 55:
            name = name[:52] + "..."
        rows.append([InlineKeyboardButton(text=f"📦 {name}", callback_data=f"vpnmapchoose|{int(panel_id)}|{int(idx)}")])
    rows.append([InlineKeyboardButton(text="🔙 بازگشت", callback_data=f"vpnmap|{int(panel_id)}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_vpn_panel_auth_keyboard(panel_type: str):
    """انتخاب روش احراز هویت برای پنل‌هایی که هم یوزرنیم/رمز و هم API دارند."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 نام کاربری و رمز عبور", callback_data=f"vpnauth|{panel_type}|password", style="primary")],
        [InlineKeyboardButton(text="🔑 API Key / Token", callback_data=f"vpnauth|{panel_type}|api", style="success")],
        [InlineKeyboardButton(text="🔙 لغو", callback_data="admin_vpn_panels", style="danger")],
    ])
