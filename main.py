import asyncio
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import CommandStart

from database import supabase

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

VALID_ROLES = ["approved_customer", "content_contributor", "admin"]
PRODUCT_LIST_PAGE_SIZE = 20

# همه حالت‌های انتظار اینجا نگهداری می‌شود
USER_STATE = {}


def set_state(telegram_id: int, state_type: str, data: dict | None = None):
    USER_STATE[telegram_id] = {"type": state_type, **(data or {})}


def get_state(telegram_id: int):
    return USER_STATE.get(telegram_id)


def clear_waiting_states(telegram_id: int):
    USER_STATE.pop(telegram_id, None)


def register_user(message: Message):
    telegram_id = message.from_user.id
    full_name = message.from_user.full_name
    username = message.from_user.username

    existing_user = (
        supabase.table("app_users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .execute()
    )

    if existing_user.data:
        supabase.table("app_users").update({
            "full_name": full_name,
            "username": username,
        }).eq("telegram_id", telegram_id).execute()

        return existing_user.data[0]

    new_user = supabase.table("app_users").insert({
        "telegram_id": telegram_id,
        "full_name": full_name,
        "username": username,
        "role": "approved_customer",
        "is_active": False,
    }).execute()

    return new_user.data[0]


def get_current_user(telegram_id: int):
    result = (
        supabase.table("app_users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .execute()
    )

    if result.data:
        return result.data[0]

    return None


def is_admin(telegram_id: int):
    user = get_current_user(telegram_id)
    return user and user.get("role") == "admin"


def can_manage_content(telegram_id: int):
    user = get_current_user(telegram_id)
    return user and user.get("is_active") and user.get("role") in ["admin", "content_contributor"]


def can_view_content(telegram_id: int):
    user = get_current_user(telegram_id)
    return user and user.get("is_active")


def get_role_label(role: str):
    if role == "admin":
        return "ادمین"
    if role == "content_contributor":
        return "ویراستار / واردکننده اطلاعات"
    if role == "approved_customer":
        return "مشتری تأییدشده"
    return role or "نامشخص"


def get_menu(role: str):
    if role == "admin":
        buttons = [
            [KeyboardButton(text="👥 مدیریت کاربران")],
            [KeyboardButton(text="📦 مدیریت محصولات")],
            [KeyboardButton(text="🛡 مدیریت ابجکشن‌ها")],
            [KeyboardButton(text="🎓 مدیریت آموزش‌ها")],
            [KeyboardButton(text="❓ سوالات بی‌جواب")],
        ]
    elif role == "content_contributor":
        buttons = [
            [KeyboardButton(text="📦 مدیریت محصولات")],
            [KeyboardButton(text="🛡 مدیریت ابجکشن‌ها")],
            [KeyboardButton(text="🎓 مدیریت آموزش‌ها")],
            [KeyboardButton(text="❓ سوالات بی‌جواب")],
            [KeyboardButton(text="📝 افزودن محتوا")],
        ]
    else:
        buttons = [
            [KeyboardButton(text="📦 محصولات")],
            [KeyboardButton(text="🛡 پاسخ به ابجکشن‌ها")],
            [KeyboardButton(text="🎓 آموزش‌ها")],
            [KeyboardButton(text="🔎 جستجو")],
            [KeyboardButton(text="✍️ ارسال سوال")],
            [KeyboardButton(text="❓ سوالات پرتکرار")],
        ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_users_menu():
    buttons = [
        [KeyboardButton(text="📋 لیست کاربران")],
        [KeyboardButton(text="🔙 بازگشت به منوی اصلی")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_products_menu():
    buttons = [
        [KeyboardButton(text="➕ افزودن محصول")],
        [KeyboardButton(text="🖼 افزودن عکس محصول")],
        [KeyboardButton(text="🎥 افزودن ویدئو محصول")],
        [KeyboardButton(text="📄 افزودن کاتالوگ محصول")],
        [KeyboardButton(text="❓ افزودن سوال محصول")],
        [KeyboardButton(text="📲 افزودن/ویرایش کپشن و استوری محصول")],
        [KeyboardButton(text="✏️ ویرایش محصول")],
        [KeyboardButton(text="📦 محصولات")],
        [KeyboardButton(text="🔙 بازگشت به منوی اصلی")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_objections_menu():
    buttons = [
        [KeyboardButton(text="➕ افزودن پاسخ ابجکشن")],
        [KeyboardButton(text="🛡 پاسخ به ابجکشن‌ها")],
        [KeyboardButton(text="🔙 بازگشت به منوی اصلی")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_questions_menu():
    buttons = [
        [KeyboardButton(text="📋 سوالات جدید")],
        [KeyboardButton(text="✅ سوالات پاسخ‌داده‌شده")],
        [KeyboardButton(text="🗂 سوالات آرشیو")],
        [KeyboardButton(text="🔙 بازگشت به منوی اصلی")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_trainings_menu():
    buttons = [
        [KeyboardButton(text="✏️ ویرایش محتوای آموزش")],
        [KeyboardButton(text="✏️ ویرایش عنوان مرحله")],
        [KeyboardButton(text="✏️ ویرایش توضیح سطح")],
        [KeyboardButton(text="📄 افزودن PDF آموزش")],
        [KeyboardButton(text="🎥 افزودن ویدئو آموزش")],
        [KeyboardButton(text="🖼 افزودن عکس آموزش")],
        [KeyboardButton(text="🗑 حذف/غیرفعال کردن فایل آموزش")],
        [KeyboardButton(text="🎓 آموزش‌ها")],
        [KeyboardButton(text="🔙 بازگشت به منوی اصلی")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def parse_product_text(text: str):
    data = {
        "code": "",
        "fa_name": "",
        "en_name": "",
        "volume": "",
        "category": "",
        "features": "",
        "benefits": "",
        "usage_method": "",
        "important_notes": "",
        "intro_text": "",
    }

    for line in text.splitlines():
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        if key == "کد محصول":
            data["code"] = value
        elif key == "نام فارسی":
            data["fa_name"] = value
        elif key == "نام انگلیسی":
            data["en_name"] = value
        elif key == "حجم":
            data["volume"] = value
        elif key in ["دسته بندی", "دسته‌بندی"]:
            data["category"] = value
        elif key == "ویژگی‌ها":
            data["features"] = value
        elif key == "مزایا":
            data["benefits"] = value
        elif key == "نحوه استفاده":
            data["usage_method"] = value
        elif key == "نکات مهم":
            data["important_notes"] = value
        elif key == "متن معرفی":
            data["intro_text"] = value

    return data


def parse_faq_text(text: str):
    data = {"question": "", "answer": ""}

    for line in text.splitlines():
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        if key == "سوال":
            data["question"] = value
        elif key == "پاسخ":
            data["answer"] = value

    return data


def parse_objection_text(text: str):
    data = {"objection": "", "answer": ""}

    for line in text.splitlines():
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        if key in ["ابجکشن", "اعتراض"]:
            data["objection"] = value
        elif key == "پاسخ":
            data["answer"] = value

    return data


def product_template(product):
    return (
        f"کد محصول: {product.get('code') or ''}\n"
        f"نام فارسی: {product.get('fa_name') or ''}\n"
        f"نام انگلیسی: {product.get('en_name') or ''}\n"
        f"حجم: {product.get('volume') or ''}\n"
        f"دسته بندی: {product.get('category') or ''}\n"
        f"ویژگی‌ها: {product.get('features') or ''}\n"
        f"مزایا: {product.get('benefits') or ''}\n"
        f"نحوه استفاده: {product.get('usage_method') or ''}\n"
        f"نکات مهم: {product.get('important_notes') or ''}\n"
        f"متن معرفی: {product.get('intro_text') or ''}"
    )


def get_products_keyboard(products, action: str = "view", page: int = 0, total_count: int = 0):
    buttons = []

    for item in products:
        buttons.append([
            InlineKeyboardButton(
                text=f"{item.get('code')} - {item.get('fa_name')}",
                callback_data=f"product_action:{action}:{item.get('code')}",
            )
        ])

    navigation_buttons = []

    if page > 0:
        navigation_buttons.append(
            InlineKeyboardButton(
                text="⬅️ صفحه قبل",
                callback_data=f"product_page:{action}:{page - 1}",
            )
        )

    if (page + 1) * PRODUCT_LIST_PAGE_SIZE < total_count:
        navigation_buttons.append(
            InlineKeyboardButton(
                text="صفحه بعد ➡️",
                callback_data=f"product_page:{action}:{page + 1}",
            )
        )

    if navigation_buttons:
        buttons.append(navigation_buttons)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def clean_product_text(value, limit: int = 350):
    text = " ".join(str(value or "").split())
    if not text:
        return "برای دیدن اطلاعات کامل محصول، از دکمه‌های زیر استفاده کن."
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def get_product_overview_text(product):
    intro = product.get("intro_text") or product.get("benefits") or product.get("features")

    text = f"📦 {product.get('fa_name') or 'محصول'}\n\n"
    text += f"کد محصول: {product.get('code') or '-'}\n"
    text += f"نام انگلیسی: {product.get('en_name') or '-'}\n"
    text += f"حجم: {product.get('volume') or '-'}\n"
    text += f"دسته‌بندی: {product.get('category') or '-'}\n\n"
    text += "معرفی کوتاه:\n"
    text += f"{clean_product_text(intro)}\n\n"
    text += "👇 برای دیدن بخش‌های مختلف محصول، یکی از گزینه‌های زیر را انتخاب کن:"

    return text


def get_product_full_info_text(product):
    text = "📖 اطلاعات کامل محصول\n\n"
    text += f"📦 {product.get('fa_name') or '-'}\n\n"
    text += f"کد محصول: {product.get('code') or '-'}\n"
    text += f"نام انگلیسی: {product.get('en_name') or '-'}\n"
    text += f"حجم: {product.get('volume') or '-'}\n"
    text += f"دسته‌بندی: {product.get('category') or '-'}\n\n"
    text += f"ویژگی‌ها:\n{product.get('features') or '-'}\n\n"
    text += f"مزایا:\n{product.get('benefits') or '-'}\n\n"
    text += f"نحوه استفاده:\n{product.get('usage_method') or '-'}\n\n"
    text += f"نکات مهم:\n{product.get('important_notes') or '-'}\n\n"
    text += f"متن معرفی:\n{product.get('intro_text') or '-'}"

    return text


def get_product_page_keyboard(code: str, has_video: bool = False, has_catalog: bool = False, has_faqs: bool = False):
    buttons = [
        [InlineKeyboardButton(text="📖 اطلاعات کامل محصول", callback_data=f"product_section:full:{code}")],
    ]

    if has_faqs:
        buttons.append([InlineKeyboardButton(text="❓ سوالات پرتکرار محصول", callback_data=f"product_section:faq:{code}")])

    if has_video:
        buttons.append([InlineKeyboardButton(text="🎥 ویدئوی محصول", callback_data=f"product_section:video:{code}")])

    if has_catalog:
        buttons.append([InlineKeyboardButton(text="📄 کاتالوگ محصول", callback_data=f"product_section:catalog:{code}")])

    buttons.append([InlineKeyboardButton(text="📲 کپشن و استوری محصول", callback_data=f"product_section:story:{code}")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به محصولات", callback_data="products_list")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_product_back_keyboard(code: str):
    buttons = [
        [InlineKeyboardButton(text="🔙 بازگشت به صفحه محصول", callback_data=f"product_action:view:{code}")],
        [InlineKeyboardButton(text="📦 بازگشت به محصولات", callback_data="products_list")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_product_media(product_id: str, media_type: str):
    result = (
        supabase.table("product_media")
        .select("*")
        .eq("product_id", product_id)
        .eq("media_type", media_type)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def get_product_faqs(product_id: str):
    result = (
        supabase.table("product_faqs")
        .select("*")
        .eq("product_id", product_id)
        .eq("is_active", True)
        .execute()
    )
    return result.data or []


async def answer_long_text(target, text: str, reply_markup=None):
    text = str(text or "")

    if len(text) <= 3900:
        await target.answer(text, reply_markup=reply_markup)
        return

    chunks = []
    current = ""

    for line in text.splitlines(True):
        if len(current) + len(line) > 3900:
            chunks.append(current)
            current = line
        else:
            current += line

    if current:
        chunks.append(current)

    for index, chunk in enumerate(chunks):
        is_last = index == len(chunks) - 1
        await target.answer(chunk, reply_markup=reply_markup if is_last else None)


def get_training_levels_keyboard(levels, callback_prefix: str = "training_level"):
    buttons = []

    for item in levels:
        buttons.append([
            InlineKeyboardButton(
                text=f"سطح {item.get('level_number')}: {item.get('title')}",
                callback_data=f"{callback_prefix}:{item.get('level_number')}",
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_training_steps_keyboard(level_number, steps, callback_prefix: str = "training_step", back_callback: str = "training_levels"):
    buttons = []

    for step in steps:
        buttons.append([
            InlineKeyboardButton(
                text=f"مرحله {step.get('step_number')}: {step.get('title')}",
                callback_data=f"{callback_prefix}:{level_number}:{step.get('step_number')}",
            )
        ])

    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به سطح‌ها", callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_training_step_detail_keyboard(level_number, step_number, title):
    buttons = []

    if title == "پاسخ به ابجکشن‌ها":
        buttons.append([InlineKeyboardButton(text="🛡 دیدن پاسخ به ابجکشن‌ها", callback_data="show_objections")])

    buttons.append([InlineKeyboardButton(text="📝 شروع آزمون", callback_data=f"training_quiz:{level_number}:{step_number}")])
    buttons.append([InlineKeyboardButton(text="🔙 بازگشت به مرحله‌ها", callback_data=f"training_level:{level_number}")])
    buttons.append([InlineKeyboardButton(text="🏠 بازگشت به سطح‌ها", callback_data="training_levels")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_training_media_label(media_type: str):
    if media_type == "pdf":
        return "PDF آموزش"
    if media_type == "video":
        return "ویدئو آموزش"
    if media_type == "photo":
        return "عکس آموزش"
    return "فایل آموزش"


def get_training_media_column(media_type: str):
    if media_type == "pdf":
        return "pdf_url"
    if media_type == "video":
        return "video_url"
    if media_type == "photo":
        return "image_url"
    return ""


def get_training_media_type_keyboard(action: str):
    buttons = [
        [InlineKeyboardButton(text="📄 PDF آموزش", callback_data=f"{action}:pdf")],
        [InlineKeyboardButton(text="🎥 ویدئو آموزش", callback_data=f"{action}:video")],
        [InlineKeyboardButton(text="🖼 عکس آموزش", callback_data=f"{action}:photo")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_objections_text():
    objections = (
        supabase.table("objection_answers")
        .select("*")
        .is_("product_id", "null")
        .eq("is_active", True)
        .order("created_at", desc=True)
        .execute()
    )

    if not objections.data:
        return "هنوز پاسخی برای ابجکشن‌ها ثبت نشده است."

    text = "🛡 پاسخ به ابجکشن‌ها:\n\n"

    for item in objections.data:
        text += f"ابجکشن: {item.get('objection')}\n"
        text += f"پاسخ: {item.get('answer')}\n"
        text += "------------------\n"

    return text


async def send_users_list(target):
    users = (
        supabase.table("app_users")
        .select("*")
        .order("created_at", desc=True)
        .limit(40)
        .execute()
    )

    if not users.data:
        await target.answer("هیچ کاربری ثبت نشده است.")
        return

    buttons = []
    for item in users.data:
        active_text = "✅" if item.get("is_active") else "⏳"
        username = f"@{item.get('username')}" if item.get("username") else "بدون یوزرنیم"
        buttons.append([
            InlineKeyboardButton(
                text=f"{active_text} {item.get('full_name')} - {username}",
                callback_data=f"admin_user:{item.get('telegram_id')}",
            )
        ])

    await target.answer(
        "👥 لیست کاربران\n\nبرای مدیریت، روی کاربر بزن:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


async def send_admin_user_detail(target, telegram_id: int):
    user_result = (
        supabase.table("app_users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .limit(1)
        .execute()
    )

    if not user_result.data:
        await target.answer("❌ کاربر پیدا نشد.")
        return

    user = user_result.data[0]
    active_text = "فعال" if user.get("is_active") else "در انتظار تأیید"
    username = f"@{user.get('username')}" if user.get("username") else "-"

    text = "👤 مدیریت کاربر\n\n"
    text += f"نام: {user.get('full_name')}\n"
    text += f"یوزرنیم: {username}\n"
    text += f"تلگرام آیدی: {user.get('telegram_id')}\n"
    text += f"نقش: {get_role_label(user.get('role'))}\n"
    text += f"وضعیت: {active_text}\n"

    buttons = [
        [InlineKeyboardButton(text="✅ تأیید کاربر", callback_data=f"approve_user:{telegram_id}")],
        [InlineKeyboardButton(text="👤 نقش: مشتری", callback_data=f"set_user_role:{telegram_id}:approved_customer")],
        [InlineKeyboardButton(text="✍️ نقش: ویراستار", callback_data=f"set_user_role:{telegram_id}:content_contributor")],
        [InlineKeyboardButton(text="👑 نقش: ادمین", callback_data=f"set_user_role:{telegram_id}:admin")],
        [InlineKeyboardButton(text="🔙 بازگشت به کاربران", callback_data="users_list")],
    ]

    await target.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


async def send_products_list(target, action: str = "view", page: int = 0):
    products = (
        supabase.table("products")
        .select("*")
        .eq("is_active", True)
        .order("code")
        .execute()
    )

    if not products.data:
        await target.answer("هنوز محصولی ثبت نشده است.")
        return

    total_count = len(products.data)
    max_page = max((total_count - 1) // PRODUCT_LIST_PAGE_SIZE, 0)
    page = max(0, min(page, max_page))
    start_index = page * PRODUCT_LIST_PAGE_SIZE
    end_index = start_index + PRODUCT_LIST_PAGE_SIZE
    page_products = products.data[start_index:end_index]

    titles = {
        "view": "📦 لیست محصولات\n\nبرای باز کردن صفحه محصول، روی محصول موردنظر بزن:",
        "photo": "🖼 افزودن عکس محصول\n\nمحصول را انتخاب کن:",
        "video": "🎥 افزودن ویدئو محصول\n\nمحصول را انتخاب کن:",
        "catalog": "📄 افزودن کاتالوگ محصول\n\nمحصول را انتخاب کن:",
        "faq": "❓ افزودن سوال محصول\n\nمحصول را انتخاب کن:",
        "story": "📲 افزودن/ویرایش کپشن و استوری محصول\n\nمحصول را انتخاب کن:",
        "edit": "✏️ ویرایش محصول\n\nمحصول را انتخاب کن:",
    }

    page_text = f"\n\nصفحه {page + 1} از {max_page + 1}"

    await target.answer(
        titles.get(action, "محصول را انتخاب کن:") + page_text,
        reply_markup=get_products_keyboard(page_products, action, page, total_count),
    )


async def get_product_by_code(code: str):
    result = (
        supabase.table("products")
        .select("*")
        .eq("code", code)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


async def send_product_detail(target, code: str):
    product = await get_product_by_code(code)

    if not product:
        await target.answer("❌ محصولی با این کد پیدا نشد.")
        return

    photo = get_product_media(product.get("id"), "photo")
    video = get_product_media(product.get("id"), "video")
    catalog = get_product_media(product.get("id"), "catalog")
    faqs = get_product_faqs(product.get("id"))

    text = get_product_overview_text(product)
    keyboard = get_product_page_keyboard(
        code,
        has_video=bool(video),
        has_catalog=bool(catalog),
        has_faqs=bool(faqs),
    )

    if photo:
        await target.answer_photo(
            photo=photo.get("file_url"),
            caption=text[:1000],
            reply_markup=keyboard,
        )
        return

    await target.answer(text, reply_markup=keyboard)


async def send_product_full_info(target, code: str):
    product = await get_product_by_code(code)

    if not product:
        await target.answer("❌ محصولی با این کد پیدا نشد.")
        return

    await answer_long_text(target, get_product_full_info_text(product), reply_markup=get_product_back_keyboard(code))


async def send_product_faqs(target, code: str):
    product = await get_product_by_code(code)

    if not product:
        await target.answer("❌ محصولی با این کد پیدا نشد.")
        return

    faqs = get_product_faqs(product.get("id"))

    if not faqs:
        await target.answer(
            "❓ سوالات پرتکرار محصول\n\n"
            "برای این محصول هنوز سوال پرتکراری ثبت نشده است.",
            reply_markup=get_product_back_keyboard(code),
        )
        return

    text = f"❓ سوالات پرتکرار محصول\n\n📦 {product.get('fa_name') or '-'}\n\n"

    for index, faq in enumerate(faqs, start=1):
        text += f"{index}. سوال: {faq.get('question') or '-'}\n"
        text += f"پاسخ: {faq.get('answer') or '-'}\n\n"

    await answer_long_text(target, text, reply_markup=get_product_back_keyboard(code))


async def send_product_video(target, code: str):
    product = await get_product_by_code(code)

    if not product:
        await target.answer("❌ محصولی با این کد پیدا نشد.")
        return

    video = get_product_media(product.get("id"), "video")

    if not video:
        await target.answer(
            "🎥 ویدئوی محصول\n\n"
            "برای این محصول هنوز ویدئو ثبت نشده است.",
            reply_markup=get_product_back_keyboard(code),
        )
        return

    await target.answer_video(
        video=video.get("file_url"),
        caption=f"🎥 ویدئوی محصول: {product.get('fa_name') or '-'}",
        reply_markup=get_product_back_keyboard(code),
    )


async def send_product_catalog(target, code: str):
    product = await get_product_by_code(code)

    if not product:
        await target.answer("❌ محصولی با این کد پیدا نشد.")
        return

    catalog = get_product_media(product.get("id"), "catalog")

    if not catalog:
        await target.answer(
            "📄 کاتالوگ محصول\n\n"
            "برای این محصول هنوز کاتالوگ ثبت نشده است.",
            reply_markup=get_product_back_keyboard(code),
        )
        return

    await target.answer_document(
        document=catalog.get("file_url"),
        caption=f"📄 کاتالوگ محصول: {product.get('fa_name') or '-'}",
        reply_markup=get_product_back_keyboard(code),
    )


async def send_product_story_caption(target, code: str):
    product = await get_product_by_code(code)

    if not product:
        await target.answer("❌ محصولی با این کد پیدا نشد.")
        return

    story_caption = (product.get("story_caption") or "").strip()

    if not story_caption:
        await target.answer(
            "📲 کپشن و استوری محصول\n\n"
            f"📦 {product.get('fa_name') or '-'}\n\n"
            "برای این محصول هنوز کپشن و محتوای استوری ثبت نشده است.",
            reply_markup=get_product_back_keyboard(code),
        )
        return

    text = "📲 کپشن و استوری محصول\n\n"
    text += f"📦 {product.get('fa_name') or '-'}\n"
    text += f"کد محصول: {product.get('code') or '-'}\n\n"
    text += story_caption

    await answer_long_text(target, text, reply_markup=get_product_back_keyboard(code))


async def get_level_by_number(level_number: int):
    result = (
        supabase.table("training_levels")
        .select("*")
        .eq("level_number", level_number)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


async def get_step_by_numbers(level_number: int, step_number: int):
    level = await get_level_by_number(level_number)
    if not level:
        return None, None

    step = (
        supabase.table("training_steps")
        .select("*")
        .eq("level_id", level.get("id"))
        .eq("step_number", step_number)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if not step.data:
        return level, None

    return level, step.data[0]


async def send_training_levels(target):
    levels = (
        supabase.table("training_levels")
        .select("*")
        .eq("is_active", True)
        .order("level_number")
        .execute()
    )

    if not levels.data:
        await target.answer("هنوز سطح آموزشی ثبت نشده است.")
        return

    text = "🎓 مسیر آموزشی فوراور\n"
    text += "از صفر تا نتورکر حرفه‌ای\n\n"
    text += "برای شروع، یکی از سطح‌ها را انتخاب کن:"

    await target.answer(text, reply_markup=get_training_levels_keyboard(levels.data))


async def send_training_level_steps(target, level_number: int):
    level = await get_level_by_number(level_number)

    if not level:
        await target.answer("❌ این سطح آموزشی پیدا نشد.")
        return

    steps = (
        supabase.table("training_steps")
        .select("*")
        .eq("level_id", level.get("id"))
        .eq("is_active", True)
        .order("step_number")
        .execute()
    )

    if not steps.data:
        await target.answer("برای این سطح هنوز مرحله‌ای ثبت نشده است.")
        return

    text = f"🎓 سطح {level.get('level_number')}: {level.get('title')}\n\n"
    text += f"{level.get('description') or ''}\n\n"
    text += "یکی از مرحله‌ها را انتخاب کن:"

    await target.answer(text, reply_markup=get_training_steps_keyboard(level_number, steps.data))


async def send_training_step_detail(target, level_number: int, step_number: int):
    level, item = await get_step_by_numbers(level_number, step_number)

    if not level:
        await target.answer("❌ این سطح آموزشی پیدا نشد.")
        return

    if not item:
        await target.answer("❌ این مرحله آموزشی پیدا نشد.")
        return

    if item.get("image_url"):
        await target.answer_photo(photo=item.get("image_url"), caption=f"🖼 عکس آموزش: {item.get('title')}")

    if item.get("video_url"):
        await target.answer_video(video=item.get("video_url"), caption=f"🎥 ویدئو آموزش: {item.get('title')}")

    if item.get("pdf_url"):
        await target.answer_document(document=item.get("pdf_url"), caption=f"📄 PDF آموزش: {item.get('title')}")

    text = f"🎓 سطح {level_number} - مرحله {step_number}\n"
    text += f"{item.get('title')}\n\n"
    text += f"{item.get('content') or 'محتوای این آموزش بعداً تکمیل می‌شود.'}\n\n"
    text += "بعد از مطالعه، روی دکمه شروع آزمون بزن."

    await target.answer(text, reply_markup=get_training_step_detail_keyboard(level_number, step_number, item.get("title")))


async def send_training_level_selection(target, mode: str, title: str):
    levels = (
        supabase.table("training_levels")
        .select("*")
        .eq("is_active", True)
        .order("level_number")
        .execute()
    )

    if not levels.data:
        await target.answer("هنوز سطح آموزشی ثبت نشده است.")
        return

    await target.answer(
        f"{title}\n\nاول سطح آموزشی را انتخاب کن:",
        reply_markup=get_training_levels_keyboard(levels.data, f"{mode}_level"),
    )


async def send_training_step_selection(target, mode: str, level_number: int, title: str, back_callback: str):
    level = await get_level_by_number(level_number)

    if not level:
        await target.answer("❌ این سطح آموزشی پیدا نشد.")
        return

    steps = (
        supabase.table("training_steps")
        .select("*")
        .eq("level_id", level.get("id"))
        .eq("is_active", True)
        .order("step_number")
        .execute()
    )

    if not steps.data:
        await target.answer("برای این سطح هنوز مرحله‌ای ثبت نشده است.")
        return

    text = f"{title}\n\n"
    text += f"سطح {level_number}: {level.get('title')}\n\n"
    text += "حالا مرحله را انتخاب کن:"

    await target.answer(
        text,
        reply_markup=get_training_steps_keyboard(level_number, steps.data, f"{mode}_step", back_callback),
    )


async def prepare_edit_training_content(target, telegram_id: int, level_number: int, step_number: int):
    level, item = await get_step_by_numbers(level_number, step_number)

    if not level:
        await target.answer("❌ این سطح آموزشی پیدا نشد.")
        return

    if not item:
        await target.answer("❌ این مرحله آموزشی پیدا نشد.")
        return

    set_state(telegram_id, "training_edit_content", {
        "step_id": item.get("id"),
        "level_number": level_number,
        "step_number": step_number,
        "title": item.get("title"),
    })

    text = "✅ مرحله انتخاب شد.\n\n"
    text += f"سطح {level_number} - مرحله {step_number}\n"
    text += f"{item.get('title')}\n\n"
    text += "محتوای فعلی:\n"
    text += f"{item.get('content') or 'محتوایی ثبت نشده است.'}\n\n"
    text += "متن جدید آموزش را همینجا بفرست."

    await target.answer(text)


async def prepare_edit_training_title(target, telegram_id: int, level_number: int, step_number: int):
    level, item = await get_step_by_numbers(level_number, step_number)

    if not level:
        await target.answer("❌ این سطح آموزشی پیدا نشد.")
        return

    if not item:
        await target.answer("❌ این مرحله آموزشی پیدا نشد.")
        return

    set_state(telegram_id, "training_edit_title", {
        "step_id": item.get("id"),
        "level_number": level_number,
        "step_number": step_number,
        "old_title": item.get("title"),
    })

    await target.answer(
        "✅ مرحله انتخاب شد.\n\n"
        f"عنوان فعلی: {item.get('title')}\n\n"
        "عنوان جدید مرحله را بفرست."
    )


async def prepare_training_media_file(target, telegram_id: int, media_type: str, level_number: int, step_number: int):
    media_label = get_training_media_label(media_type)
    column_name = get_training_media_column(media_type)

    if not column_name:
        await target.answer("❌ نوع فایل آموزشی درست نیست.")
        return

    level, item = await get_step_by_numbers(level_number, step_number)

    if not level:
        await target.answer("❌ این سطح آموزشی پیدا نشد.")
        return

    if not item:
        await target.answer("❌ این مرحله آموزشی پیدا نشد.")
        return

    set_state(telegram_id, "training_media_file", {
        "step_id": item.get("id"),
        "level_number": level_number,
        "step_number": step_number,
        "title": item.get("title"),
        "media_type": media_type,
        "media_label": media_label,
        "column_name": column_name,
    })

    await target.answer(
        "✅ مرحله انتخاب شد.\n\n"
        f"سطح {level_number} - مرحله {step_number}\n"
        f"{item.get('title')}\n\n"
        f"حالا {media_label} را بفرست."
    )


async def delete_training_media(target, media_type: str, level_number: int, step_number: int):
    media_label = get_training_media_label(media_type)
    column_name = get_training_media_column(media_type)

    if not column_name:
        await target.answer("❌ نوع فایل آموزشی درست نیست.")
        return

    level, item = await get_step_by_numbers(level_number, step_number)

    if not level:
        await target.answer("❌ این سطح آموزشی پیدا نشد.")
        return

    if not item:
        await target.answer("❌ این مرحله آموزشی پیدا نشد.")
        return

    supabase.table("training_steps").update({column_name: None}).eq("id", item.get("id")).execute()

    await target.answer(
        f"✅ {media_label} برای این مرحله غیرفعال شد.\n\n"
        f"سطح {level_number} - مرحله {step_number}\n"
        f"{item.get('title')}"
    )


async def prepare_edit_level_description(target, telegram_id: int, level_number: int):
    level = await get_level_by_number(level_number)

    if not level:
        await target.answer("❌ این سطح آموزشی پیدا نشد.")
        return

    set_state(telegram_id, "training_edit_level_description", {
        "level_id": level.get("id"),
        "level_number": level_number,
        "title": level.get("title"),
    })

    await target.answer(
        "✅ سطح انتخاب شد.\n\n"
        f"سطح {level_number}: {level.get('title')}\n\n"
        "توضیح فعلی:\n"
        f"{level.get('description') or 'توضیحی ثبت نشده است.'}\n\n"
        "توضیح جدید سطح را بفرست."
    )



def get_question_status_label(status: str):
    if status == "new":
        return "جدید"
    if status == "answered":
        return "پاسخ‌داده‌شده"
    if status == "archived":
        return "آرشیو"
    return status or "نامشخص"


async def send_unanswered_questions_menu(target):
    await target.answer(
        "❓ مدیریت سوالات مشتری‌ها\n\n"
        "یکی از بخش‌ها را انتخاب کن:",
        reply_markup=get_questions_menu(),
    )


async def send_questions_list(target, status: str = "new"):
    title_map = {
        "new": "📋 سوالات جدید",
        "answered": "✅ سوالات پاسخ‌داده‌شده",
        "archived": "🗂 سوالات آرشیو",
    }

    try:
        query = (
            supabase.table("unanswered_questions")
            .select("*")
            .eq("status", status)
            .order("created_at", desc=True)
            .limit(30)
            .execute()
        )
    except Exception as e:
        await target.answer(
            "❌ خطا در خواندن سوالات.\n\n"
            "اگر هنوز جدول را نساختی، SQL مربوط به unanswered_questions را در Supabase اجرا کن."
        )
        return

    if not query.data:
        await target.answer(f"{title_map.get(status, 'سوالات')}\n\nموردی پیدا نشد.")
        return

    buttons = []
    for item in query.data:
        question_text = (item.get("question") or "").replace("\n", " ")
        if len(question_text) > 35:
            question_text = question_text[:35] + "..."

        name = item.get("full_name") or "کاربر"
        buttons.append([
            InlineKeyboardButton(
                text=f"{name}: {question_text}",
                callback_data=f"uq_detail:{item.get('id')}",
            )
        ])

    await target.answer(
        f"{title_map.get(status, 'سوالات')}\n\n"
        "برای دیدن جزئیات، روی سوال بزن:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


async def send_question_detail(target, question_id: str):
    result = (
        supabase.table("unanswered_questions")
        .select("*")
        .eq("id", question_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        await target.answer("❌ سوال پیدا نشد.")
        return

    item = result.data[0]
    username = f"@{item.get('username')}" if item.get("username") else "-"
    status = item.get("status") or "new"

    text = "❓ جزئیات سوال\n\n"
    text += f"نام: {item.get('full_name') or '-'}\n"
    text += f"یوزرنیم: {username}\n"
    text += f"تلگرام آیدی: {item.get('telegram_id') or '-'}\n"
    text += f"وضعیت: {get_question_status_label(status)}\n\n"
    text += f"سوال:\n{item.get('question') or '-'}\n\n"

    if item.get("answer"):
        text += f"پاسخ:\n{item.get('answer')}\n"

    buttons = []

    if status != "answered":
        buttons.append([
            InlineKeyboardButton(
                text="✍️ پاسخ دادن",
                callback_data=f"uq_answer:{question_id}",
            )
        ])

    if status != "archived":
        buttons.append([
            InlineKeyboardButton(
                text="🗂 آرشیو کردن",
                callback_data=f"uq_archive:{question_id}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="🔙 بازگشت به لیست",
            callback_data=f"uq_list:{status}",
        )
    ])

    await target.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


async def prepare_answer_question(target, telegram_id: int, question_id: str):
    result = (
        supabase.table("unanswered_questions")
        .select("*")
        .eq("id", question_id)
        .limit(1)
        .execute()
    )

    if not result.data:
        await target.answer("❌ سوال پیدا نشد.")
        return

    item = result.data[0]

    set_state(telegram_id, "unanswered_answer", {
        "question_id": question_id,
        "customer_telegram_id": item.get("telegram_id"),
        "question": item.get("question"),
        "full_name": item.get("full_name"),
    })

    await target.answer(
        "✍️ پاسخ به سوال\n\n"
        f"سوال مشتری:\n{item.get('question')}\n\n"
        "حالا پاسخ را ارسال کن."
    )


def get_public_faq_keyboard():
    buttons = [
        [InlineKeyboardButton(text="📋 مشاهده همه سوالات پرتکرار", callback_data="public_faq_list")],
        [InlineKeyboardButton(text="🔎 جستجو در سوالات پرتکرار", callback_data="public_faq_search")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def format_public_faqs(items, title: str):
    text = f"{title}\n\n"

    count = 0
    for item in items:
        question = (item.get("question") or "").strip()
        answer = (item.get("answer") or "").strip()

        if not question or not answer:
            continue

        count += 1
        text += f"{count}. سوال: {question}\n"
        text += f"پاسخ: {answer}\n"
        text += "------------------\n"

        if count >= 15:
            break

    if count == 0:
        return "❓ سوالات پرتکرار عمومی\n\nهنوز سوال پاسخ‌داده‌شده‌ای برای نمایش عمومی وجود ندارد.\n\nاگر سوالی داری، از دکمه ✍️ ارسال سوال استفاده کن."

    if len(items) > count:
        text += "\nبرای پیدا کردن سوال خاص، از دکمه 🔎 جستجو استفاده کن."

    return text


async def send_public_faq_menu(target):
    await target.answer(
        "❓ سوالات پرتکرار عمومی\n\n"
        "اینجا جواب سوال‌هایی را می‌بینی که مشتری‌ها قبلاً پرسیده‌اند و ادمین یا ویراستار پاسخ داده است.\n\n"
        "برای دیدن همه سوال‌ها، گزینه 📋 مشاهده همه سوالات پرتکرار را بزن.\n"
        "اگر دنبال موضوع خاصی هستی، گزینه 🔎 جستجو در سوالات پرتکرار را انتخاب کن.",
        reply_markup=get_public_faq_keyboard(),
    )


async def send_public_faq_list(target):
    try:
        result = (
            supabase.table("unanswered_questions")
            .select("*")
            .eq("status", "answered")
            .eq("is_active", True)
            .order("answered_at", desc=True)
            .limit(50)
            .execute()
        )
    except Exception:
        await target.answer("❌ خطا در خواندن سوالات پرتکرار عمومی.")
        return

    items = [
        item for item in (result.data or [])
        if (item.get("question") or "").strip() and (item.get("answer") or "").strip()
    ]

    await target.answer(format_public_faqs(items, "❓ سوالات پرتکرار عمومی"))


async def send_public_faq_search_result(target, keyword: str):
    keyword = keyword.strip()

    if not keyword:
        await target.answer("❌ عبارت جستجو نمی‌تواند خالی باشد.\n\nیک کلمه بفرست؛ مثلاً: آلوئه، سفارش، قیمت")
        return

    try:
        result = (
            supabase.table("unanswered_questions")
            .select("*")
            .eq("status", "answered")
            .eq("is_active", True)
            .order("answered_at", desc=True)
            .limit(200)
            .execute()
        )
    except Exception:
        await target.answer("❌ خطا در جستجوی سوالات پرتکرار عمومی.")
        return

    keyword_lower = keyword.lower()
    matched_items = []

    for item in result.data or []:
        question = (item.get("question") or "").lower()
        answer = (item.get("answer") or "").lower()

        if keyword_lower in question or keyword_lower in answer:
            matched_items.append(item)

    if not matched_items:
        await target.answer(
            "🔎 نتیجه جستجو\n\n"
            f"برای عبارت «{keyword}» موردی پیدا نشد.\n\n"
            "یک کلمه ساده‌تر امتحان کن؛ مثلاً:\n"
            "سفارش، ارسال، تخفیف، قیمت\n\n"
            "همینجا دوباره کلمه جدید را بفرست."
        )
        return


    await target.answer(format_public_faqs(matched_items, f"🔎 نتیجه جستجو برای: {keyword}"))


def normalize_search_text(value):
    text = str(value or "").strip().lower()
    replacements = {
        "ي": "ی",
        "ك": "ک",
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ة": "ه",
        "\u200c": " ",
        "‌": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return " ".join(text.split())


def contains_search_keyword(fields, keyword: str):
    normalized_keyword = normalize_search_text(keyword)
    if not normalized_keyword:
        return False

    for field in fields:
        if normalized_keyword in normalize_search_text(field):
            return True

    return False


def short_text(value, limit: int = 95):
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def format_global_search_section(title: str, items: list[str], limit: int = 5):
    if not items:
        return ""

    text = f"\n{title}\n"
    for index, item in enumerate(items[:limit], start=1):
        text += f"{index}. {item}\n"

    if len(items) > limit:
        text += f"و {len(items) - limit} مورد دیگر...\n"

    return text


async def send_global_search_result(target, keyword: str):
    keyword = keyword.strip()

    if not keyword:
        await target.answer("❌ عبارت جستجو نمی‌تواند خالی باشد.\n\nیک کلمه بفرست؛ مثلاً: آلوئه، سفارش، قیمت")
        return

    product_matches = []
    product_faq_matches = []
    training_matches = []
    objection_matches = []
    general_faq_matches = []

    try:
        products_result = (
            supabase.table("products")
            .select("*")
            .eq("is_active", True)
            .limit(300)
            .execute()
        )
        products = products_result.data or []
        product_by_id = {item.get("id"): item for item in products}

        for product in products:
            if contains_search_keyword([
                product.get("code"),
                product.get("fa_name"),
                product.get("en_name"),
                product.get("category"),
                product.get("features"),
                product.get("benefits"),
                product.get("usage_method"),
                product.get("important_notes"),
                product.get("intro_text"),
                product.get("story_caption"),
            ], keyword):
                product_matches.append(product)

        product_faqs_result = (
            supabase.table("product_faqs")
            .select("*")
            .eq("is_active", True)
            .limit(300)
            .execute()
        )

        for faq in product_faqs_result.data or []:
            if contains_search_keyword([faq.get("question"), faq.get("answer")], keyword):
                product_faq_matches.append(faq)

        levels_result = (
            supabase.table("training_levels")
            .select("*")
            .eq("is_active", True)
            .limit(100)
            .execute()
        )
        levels = levels_result.data or []
        level_by_id = {item.get("id"): item for item in levels}

        steps_result = (
            supabase.table("training_steps")
            .select("*")
            .eq("is_active", True)
            .limit(500)
            .execute()
        )

        for step in steps_result.data or []:
            level = level_by_id.get(step.get("level_id"), {})
            if contains_search_keyword([
                level.get("title"),
                level.get("description"),
                step.get("title"),
                step.get("content"),
            ], keyword):
                training_matches.append({"level": level, "step": step})

        objections_result = (
            supabase.table("objection_answers")
            .select("*")
            .eq("is_active", True)
            .limit(300)
            .execute()
        )

        for item in objections_result.data or []:
            if contains_search_keyword([item.get("objection"), item.get("answer")], keyword):
                objection_matches.append(item)

        general_faq_result = (
            supabase.table("unanswered_questions")
            .select("*")
            .eq("status", "answered")
            .eq("is_active", True)
            .limit(300)
            .execute()
        )

        for item in general_faq_result.data or []:
            if contains_search_keyword([item.get("question"), item.get("answer")], keyword):
                general_faq_matches.append(item)

    except Exception:
        await target.answer("❌ خطا در جستجو. چند لحظه بعد دوباره امتحان کن.")
        return

    text = f"🔎 نتیجه جستجو برای: {keyword}\n"

    product_lines = []
    for product in product_matches:
        product_lines.append(
            f"{product.get('code')} - {product.get('fa_name')}\n"
            f"   {short_text(product.get('intro_text') or product.get('benefits') or product.get('features'))}"
        )

    product_faq_lines = []
    for faq in product_faq_matches:
        product = product_by_id.get(faq.get("product_id"), {})
        product_name = product.get("fa_name") or "محصول"
        product_code = product.get("code") or "-"
        product_faq_lines.append(
            f"{product_name} ({product_code})\n"
            f"   سوال: {short_text(faq.get('question'))}\n"
            f"   پاسخ: {short_text(faq.get('answer'))}"
        )

    training_lines = []
    for item in training_matches:
        level = item.get("level") or {}
        step = item.get("step") or {}
        training_lines.append(
            f"سطح {level.get('level_number')} - مرحله {step.get('step_number')}: {step.get('title')}\n"
            f"   {short_text(step.get('content'))}"
        )

    objection_lines = []
    for item in objection_matches:
        objection_lines.append(
            f"ابجکشن: {short_text(item.get('objection'))}\n"
            f"   پاسخ: {short_text(item.get('answer'))}"
        )

    general_faq_lines = []
    for item in general_faq_matches:
        general_faq_lines.append(
            f"سوال: {short_text(item.get('question'))}\n"
            f"   پاسخ: {short_text(item.get('answer'))}"
        )

    text += format_global_search_section("\n📦 محصولات", product_lines)
    text += format_global_search_section("\n❓ سوالات محصول", product_faq_lines)
    text += format_global_search_section("\n🎓 آموزش‌ها", training_lines)
    text += format_global_search_section("\n🛡 ابجکشن‌ها", objection_lines)
    text += format_global_search_section("\n❓ سوالات پرتکرار عمومی", general_faq_lines)

    total = (
        len(product_matches)
        + len(product_faq_matches)
        + len(training_matches)
        + len(objection_matches)
        + len(general_faq_matches)
    )

    if total == 0:
        await target.answer(
            "🔎 نتیجه جستجو\n\n"
            f"برای عبارت «{keyword}» چیزی پیدا نشد.\n\n"
            "یک کلمه ساده‌تر امتحان کن؛ مثلاً:\n"
            "آلوئه، محصول، سفارش، قیمت، تخفیف\n\n"
            "همینجا دوباره کلمه جدید را بفرست یا از دکمه ✍️ ارسال سوال استفاده کن."
        )
        return

    text += "\nبرای باز کردن سریع محصول یا آموزش، از دکمه‌های زیر استفاده کن."

    buttons = []

    for product in product_matches[:5]:
        buttons.append([
            InlineKeyboardButton(
                text=f"📦 {product.get('code')} - {product.get('fa_name')}",
                callback_data=f"product_action:view:{product.get('code')}",
            )
        ])

    for item in training_matches[:5]:
        level = item.get("level") or {}
        step = item.get("step") or {}
        if level.get("level_number") and step.get("step_number"):
            buttons.append([
                InlineKeyboardButton(
                    text=f"🎓 سطح {level.get('level_number')} - مرحله {step.get('step_number')}",
                    callback_data=f"training_step:{level.get('level_number')}:{step.get('step_number')}",
                )
            ])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=buttons) if buttons else None

    if len(text) > 3900:
        text = text[:3900] + "\n\nنتایج بیشتر بود؛ برای نتیجه دقیق‌تر با کلمه کوتاه‌تر یا دقیق‌تر جستجو کن."

    await target.answer(text, reply_markup=reply_markup)


EDITOR_GUIDE_PARTS = [
    """📘 راهنمای کار ویراستار

سلام 👋
شما به عنوان ویراستار / واردکننده اطلاعات در ربات دسترسی دارید تا محصولات، آموزش‌ها، ابجکشن‌ها و پاسخ سوالات مشتریان را مدیریت کنید.

منوی شما شامل این بخش‌هاست:

📦 مدیریت محصولات
🛡 مدیریت ابجکشن‌ها
🎓 مدیریت آموزش‌ها
❓ سوالات بی‌جواب
📝 افزودن محتوا

هدف این است که محتواها ساده، مرتب، دقیق و قابل استفاده برای مشتری وارد شوند.""",

    """📦 مدیریت محصولات

از بخش مدیریت محصولات می‌توانید:

➕ محصول جدید اضافه کنید
🖼 عکس محصول اضافه کنید
🎥 ویدئو محصول اضافه کنید
📄 کاتالوگ محصول اضافه کنید
❓ سوالات پرتکرار محصول اضافه کنید
📲 کپشن و متن استوری محصول اضافه یا ویرایش کنید
✏️ محصول را ویرایش کنید

نکته مهم:
کد محصول نباید تکراری باشد.
مثلاً: 015، 022، 673

بعد از ثبت هر محصول، حتماً از سمت مشتری هم بررسی کنید که درست نمایش داده شود.""",

    """🎓 مدیریت آموزش‌ها

از بخش مدیریت آموزش‌ها می‌توانید:

✏️ متن آموزش را ویرایش کنید
✏️ عنوان مرحله را ویرایش کنید
✏️ توضیح سطح را ویرایش کنید
📄 PDF آموزش اضافه کنید
🎥 ویدئو آموزش اضافه کنید
🖼 عکس آموزش اضافه کنید
🗑 فایل آموزش را حذف/غیرفعال کنید

برای آموزش‌ها همیشه سطح و مرحله را با دکمه انتخاب کنید و بعد محتوا یا فایل را ارسال کنید.""",

    """🛡 مدیریت ابجکشن‌ها

از بخش مدیریت ابجکشن‌ها می‌توانید پاسخ‌های عمومی ثبت کنید.

قالب ثبت:

ابجکشن:
پاسخ:

مثال:
ابجکشن: قیمت محصولات بالاست
پاسخ: قیمت زمانی بهتر درک می‌شود که کیفیت، حجم، ماندگاری و نتیجه مصرف درست محصول بررسی شود.

این پاسخ‌ها برای همه مشتری‌ها نمایش داده می‌شود.""",

    """❓ سوالات بی‌جواب مشتریان

اگر مشتری از بخش ✍️ ارسال سوال سوالی بپرسد، سوال او در بخش سوالات بی‌جواب ذخیره می‌شود.

ویراستار می‌تواند به سوال پاسخ دهد.
بعد از پاسخ، آن سوال وارد بخش سوالات پرتکرار عمومی می‌شود و همه مشتری‌ها می‌توانند آن را ببینند.

اطلاعات شخصی مشتری مثل اسم، آیدی یا یوزرنیم برای بقیه مشتری‌ها نمایش داده نمی‌شود.""",

    """🔎 جستجو و تست نهایی

بعد از ثبت محصول، آموزش، ابجکشن یا پاسخ سوال، بهتر است از سمت مشتری هم تست کنید.

مواردی که باید بررسی شود:

📦 محصول درست نمایش داده شود
🎓 آموزش درست باز شود
📄 فایل PDF یا ویدئو اشتباه نباشد
❓ سوال و پاسخ درست ثبت شده باشد
📲 کپشن و استوری محصول درست نمایش داده شود
🔎 با جستجو قابل پیدا شدن باشد""",

    """✅ قوانین مهم ویراستار

1. قبل از ارسال، متن را کامل بخوانید.
2. از متن‌های خیلی طولانی و نامرتب استفاده نکنید.
3. اطلاعات محصول را دقیق و قابل فهم بنویسید.
4. متن آموزش باید ساده، مرحله‌ای و قابل اجرا باشد.
5. از ادعاهای پزشکی قطعی استفاده نکنید.
6. اگر مطمئن نیستید، از ادمین بپرسید.
7. اطلاعات تکراری وارد نکنید.
8. فایل اشتباه را روی محصول یا مرحله اشتباه ثبت نکنید.
9. بعد از ثبت محتوا، نمایش آن را از سمت مشتری تست کنید.
10. اگر اشتباهی رخ داد، سریع به ادمین اطلاع دهید.""",
]


async def send_editor_guide(message: Message):
    for part in EDITOR_GUIDE_PARTS:
        await message.answer(part)


@dp.message(CommandStart())
async def start_handler(message: Message):
    user = register_user(message)

    if not user.get("is_active"):
        await message.answer(
            "سلام 👋\n"
            "ثبت‌نام شما در ربات انجام شد.\n\n"
            "⏳ حساب شما هنوز توسط ادمین تأیید نشده است.\n\n"
            "بعد از اینکه ادمین حساب شما را تأیید کرد، لطفاً دوباره روی /start بزنید تا منوی اصلی برای شما فعال شود."
        )
        return

    if user.get("role") == "content_contributor":
        await send_editor_guide(message)

    await message.answer(
        "سلام 👋\n"
        "به سیستم آموزشی فوراور خوش آمدید ✅\n\n"
        "از دکمه‌های پایین شروع کن 👇",
        reply_markup=get_menu(user.get("role")),
    )


@dp.message(F.text == "🏠 منوی اصلی")
@dp.message(F.text == "🔙 بازگشت به منوی اصلی")
async def back_to_main_menu_handler(message: Message):
    user = get_current_user(message.from_user.id)
    clear_waiting_states(message.from_user.id)

    if not user or not user.get("is_active"):
        await message.answer("⛔ حساب شما هنوز فعال نیست.")
        return

    await message.answer("🏠 منوی اصلی\n\nاز دکمه‌های پایین یکی را انتخاب کن 👇", reply_markup=get_menu(user.get("role")))


@dp.message(F.text == "👥 مدیریت کاربران")
async def manage_users_handler(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ شما دسترسی ادمین ندارید.")
        return

    await message.answer("👥 مدیریت کاربران", reply_markup=get_users_menu())


@dp.message(F.text == "📋 لیست کاربران")
async def users_list_message_handler(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ شما دسترسی ادمین ندارید.")
        return

    await send_users_list(message)


@dp.callback_query(F.data == "users_list")
async def users_list_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ادمین ندارید.", show_alert=True)
        return

    await callback.answer()
    await send_users_list(callback.message)


@dp.callback_query(F.data.startswith("admin_user:"))
async def admin_user_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ادمین ندارید.", show_alert=True)
        return

    telegram_id_text = callback.data.split(":")[1]
    if not telegram_id_text.isdigit():
        await callback.answer("آیدی درست نیست.", show_alert=True)
        return

    await callback.answer()
    await send_admin_user_detail(callback.message, int(telegram_id_text))


@dp.callback_query(F.data.startswith("approve_user:"))
async def approve_user_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ادمین ندارید.", show_alert=True)
        return

    telegram_id = int(callback.data.split(":")[1])
    supabase.table("app_users").update({"is_active": True}).eq("telegram_id", telegram_id).execute()

    await callback.answer("✅ کاربر تأیید شد.", show_alert=True)
    await send_admin_user_detail(callback.message, telegram_id)


@dp.callback_query(F.data.startswith("set_user_role:"))
async def set_user_role_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ادمین ندارید.", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("اطلاعات درست نیست.", show_alert=True)
        return

    telegram_id = int(parts[1])
    new_role = parts[2]

    if new_role not in VALID_ROLES:
        await callback.answer("نقش درست نیست.", show_alert=True)
        return

    supabase.table("app_users").update({
        "role": new_role,
        "is_active": True,
    }).eq("telegram_id", telegram_id).execute()

    await callback.answer("✅ نقش کاربر تغییر کرد.", show_alert=True)
    await send_admin_user_detail(callback.message, telegram_id)


@dp.message(F.text.startswith("/approve "))
async def approve_user_command_handler(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ شما دسترسی ادمین ندارید.")
        return

    telegram_id_text = message.text.replace("/approve ", "").strip()
    if not telegram_id_text.isdigit():
        await message.answer("❌ آیدی تلگرام درست نیست.")
        return

    supabase.table("app_users").update({"is_active": True}).eq("telegram_id", int(telegram_id_text)).execute()
    await message.answer("✅ کاربر تأیید شد.")


@dp.message(F.text.startswith("/setrole "))
async def set_role_command_handler(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ شما دسترسی ادمین ندارید.")
        return

    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("❌ دستور درست نیست.")
        return

    telegram_id_text = parts[1]
    new_role = parts[2]

    if not telegram_id_text.isdigit() or new_role not in VALID_ROLES:
        await message.answer("❌ آیدی یا نقش درست نیست.")
        return

    supabase.table("app_users").update({"role": new_role, "is_active": True}).eq("telegram_id", int(telegram_id_text)).execute()
    await message.answer("✅ نقش کاربر تغییر کرد.")


@dp.message(F.text == "📦 مدیریت محصولات")
async def manage_products_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی مدیریت محصولات ندارید.")
        return

    await message.answer("📦 مدیریت محصولات", reply_markup=get_products_menu())


@dp.message(F.text == "🛡 مدیریت ابجکشن‌ها")
async def manage_objections_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی مدیریت ابجکشن‌ها ندارید.")
        return

    await message.answer("🛡 مدیریت ابجکشن‌ها", reply_markup=get_objections_menu())


@dp.message(F.text == "🎓 مدیریت آموزش‌ها")
async def manage_trainings_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی مدیریت آموزش‌ها ندارید.")
        return

    await message.answer("🎓 مدیریت آموزش‌ها", reply_markup=get_trainings_menu())


@dp.message(F.text == "➕ افزودن محصول")
async def add_product_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی ثبت اطلاعات ندارید.")
        return

    clear_waiting_states(message.from_user.id)
    set_state(message.from_user.id, "product_add")

    await message.answer(
        "اطلاعات محصول را با همین قالب پر کن و بفرست:\n\n"
        "کد محصول: \n"
        "نام فارسی: \n"
        "نام انگلیسی: \n"
        "حجم: \n"
        "دسته بندی: \n"
        "ویژگی‌ها: \n"
        "مزایا: \n"
        "نحوه استفاده: \n"
        "نکات مهم: \n"
        "متن معرفی: "
    )


@dp.message(F.text == "🖼 افزودن عکس محصول")
async def add_product_photo_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی ثبت اطلاعات ندارید.")
        return
    clear_waiting_states(message.from_user.id)
    await send_products_list(message, "photo")


@dp.message(F.text == "🎥 افزودن ویدئو محصول")
async def add_product_video_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی ثبت اطلاعات ندارید.")
        return
    clear_waiting_states(message.from_user.id)
    await send_products_list(message, "video")


@dp.message(F.text == "📄 افزودن کاتالوگ محصول")
async def add_product_catalog_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی ثبت اطلاعات ندارید.")
        return
    clear_waiting_states(message.from_user.id)
    await send_products_list(message, "catalog")


@dp.message(F.text == "❓ افزودن سوال محصول")
async def add_product_faq_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی ثبت سوال ندارید.")
        return
    clear_waiting_states(message.from_user.id)
    await send_products_list(message, "faq")


@dp.message(F.text == "📲 افزودن/ویرایش کپشن و استوری محصول")
async def edit_product_story_caption_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی ویرایش کپشن و استوری محصول ندارید.")
        return
    clear_waiting_states(message.from_user.id)
    await send_products_list(message, "story")


@dp.message(F.text == "✏️ ویرایش محصول")
async def edit_product_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی ویرایش محصول ندارید.")
        return
    clear_waiting_states(message.from_user.id)
    await send_products_list(message, "edit")


@dp.message(F.text == "📦 محصولات")
async def products_list_handler(message: Message):
    if not can_view_content(message.from_user.id):
        await message.answer("⛔ حساب شما هنوز فعال نیست.")
        return
    await send_products_list(message, "view")


@dp.callback_query(F.data == "products_list")
async def products_list_callback(callback: CallbackQuery):
    if not can_view_content(callback.from_user.id):
        await callback.answer("⛔ حساب شما هنوز فعال نیست.", show_alert=True)
        return
    await callback.answer()
    await send_products_list(callback.message, "view", 0)


@dp.callback_query(F.data.startswith("product_page:"))
async def product_page_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3 or not parts[2].isdigit():
        await callback.answer("اطلاعات صفحه درست نیست.", show_alert=True)
        return

    action = parts[1]
    page = int(parts[2])

    if action == "view":
        if not can_view_content(callback.from_user.id):
            await callback.answer("⛔ حساب شما هنوز فعال نیست.", show_alert=True)
            return
    elif not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی مدیریت محصولات ندارید.", show_alert=True)
        return

    await callback.answer()
    await send_products_list(callback.message, action, page)


@dp.callback_query(F.data.startswith("product_section:"))
async def product_section_callback(callback: CallbackQuery):
    if not can_view_content(callback.from_user.id):
        await callback.answer("⛔ حساب شما هنوز فعال نیست.", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("اطلاعات محصول درست نیست.", show_alert=True)
        return

    section = parts[1]
    code = parts[2]

    await callback.answer()

    if section == "full":
        await send_product_full_info(callback.message, code)
        return

    if section == "faq":
        await send_product_faqs(callback.message, code)
        return

    if section == "video":
        await send_product_video(callback.message, code)
        return

    if section == "catalog":
        await send_product_catalog(callback.message, code)
        return

    if section == "story":
        await send_product_story_caption(callback.message, code)
        return

    await send_product_detail(callback.message, code)


@dp.callback_query(F.data.startswith("product_action:"))
async def product_action_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("اطلاعات محصول درست نیست.", show_alert=True)
        return

    action = parts[1]
    code = parts[2]

    if action == "view":
        if not can_view_content(callback.from_user.id):
            await callback.answer("⛔ حساب شما هنوز فعال نیست.", show_alert=True)
            return
        await callback.answer()
        await send_product_detail(callback.message, code)
        return

    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی مدیریت محصولات ندارید.", show_alert=True)
        return

    product = (
        supabase.table("products")
        .select("*")
        .eq("code", code)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if not product.data:
        await callback.answer("❌ محصول پیدا نشد.", show_alert=True)
        return

    item = product.data[0]
    clear_waiting_states(callback.from_user.id)
    await callback.answer()

    if action in ["photo", "video", "catalog"]:
        media_labels = {
            "photo": "عکس محصول",
            "video": "ویدئوی محصول",
            "catalog": "کاتالوگ محصول",
        }
        set_state(callback.from_user.id, "product_media", {
            "product_id": item.get("id"),
            "product_name": item.get("fa_name"),
            "media_type": action,
            "media_label": media_labels[action],
        })
        await callback.message.answer(
            f"✅ محصول انتخاب شد: {item.get('fa_name')}\n\n"
            f"حالا {media_labels[action]} را بفرست."
        )
        return

    if action == "faq":
        set_state(callback.from_user.id, "product_faq", {
            "product_id": item.get("id"),
            "product_name": item.get("fa_name"),
        })
        await callback.message.answer(
            f"✅ محصول انتخاب شد: {item.get('fa_name')}\n\n"
            "حالا سوال و پاسخ را با این قالب بفرست:\n\n"
            "سوال: \n"
            "پاسخ: "
        )
        return

    if action == "story":
        set_state(callback.from_user.id, "product_story_caption", {
            "product_id": item.get("id"),
            "product_code": item.get("code"),
            "product_name": item.get("fa_name"),
        })

        current_story = (item.get("story_caption") or "").strip()
        current_text = current_story if current_story else "برای این محصول هنوز کپشن و استوری ثبت نشده است."

        await callback.message.answer(
            f"✅ محصول انتخاب شد: {item.get('fa_name')}\n\n"
            "متن فعلی کپشن و استوری:\n"
            f"{current_text}\n\n"
            "حالا متن جدید کپشن و استوری را بفرست.\n\n"
            "پیشنهاد قالب:\n\n"
            "استوری ۱:\n"
            "استوری ۲:\n"
            "استوری ۳:\n\n"
            "کپشن:\n\n"
            "هشتگ‌ها:\n\n"
            "برای پاک کردن این بخش، فقط کلمه حذف را بفرست."
        )
        return

    if action == "edit":
        set_state(callback.from_user.id, "product_edit", {
            "product_id": item.get("id"),
            "product_name": item.get("fa_name"),
        })
        await callback.message.answer(
            "اطلاعات فعلی محصول این است.\n"
            "هر چیزی را می‌خواهی تغییر بده و همین متن کامل را دوباره بفرست:\n\n"
            f"{product_template(item)}"
        )
        return


@dp.callback_query(F.data.startswith("product:"))
async def old_product_detail_callback(callback: CallbackQuery):
    if not can_view_content(callback.from_user.id):
        await callback.answer("⛔ حساب شما هنوز فعال نیست.", show_alert=True)
        return
    code = callback.data.replace("product:", "").strip()
    await callback.answer()
    await send_product_detail(callback.message, code)


@dp.message(F.text.startswith("/product "))
async def product_detail_command_handler(message: Message):
    if not can_view_content(message.from_user.id):
        await message.answer("⛔ حساب شما هنوز فعال نیست.")
        return
    code = message.text.replace("/product ", "").strip()
    await send_product_detail(message, code)


@dp.message(F.text == "➕ افزودن پاسخ ابجکشن")
async def add_objection_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی ثبت ابجکشن ندارید.")
        return

    clear_waiting_states(message.from_user.id)
    set_state(message.from_user.id, "objection_add")

    await message.answer(
        "ابجکشن و پاسخ را با همین قالب بفرست:\n\n"
        "ابجکشن: \n"
        "پاسخ: "
    )


@dp.message(F.text == "🛡 پاسخ به ابجکشن‌ها")
async def objections_list_handler(message: Message):
    if not can_view_content(message.from_user.id):
        await message.answer("⛔ حساب شما هنوز فعال نیست.")
        return
    await message.answer(build_objections_text())


@dp.callback_query(F.data == "show_objections")
async def show_objections_callback(callback: CallbackQuery):
    if not can_view_content(callback.from_user.id):
        await callback.answer("⛔ حساب شما هنوز فعال نیست.", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(build_objections_text())


@dp.message(F.text == "🎓 آموزش‌ها")
async def training_levels_handler(message: Message):
    if not can_view_content(message.from_user.id):
        await message.answer("⛔ حساب شما هنوز فعال نیست.")
        return
    await send_training_levels(message)


@dp.callback_query(F.data == "training_levels")
async def training_levels_callback(callback: CallbackQuery):
    if not can_view_content(callback.from_user.id):
        await callback.answer("⛔ حساب شما هنوز فعال نیست.", show_alert=True)
        return
    await callback.answer()
    await send_training_levels(callback.message)


@dp.callback_query(F.data.startswith("training_level:"))
async def training_level_callback(callback: CallbackQuery):
    if not can_view_content(callback.from_user.id):
        await callback.answer("⛔ حساب شما هنوز فعال نیست.", show_alert=True)
        return

    level_text = callback.data.split(":")[1]
    if not level_text.isdigit():
        await callback.answer("شماره سطح درست نیست.", show_alert=True)
        return

    await callback.answer()
    await send_training_level_steps(callback.message, int(level_text))


@dp.callback_query(F.data.startswith("training_step:"))
async def training_step_callback(callback: CallbackQuery):
    if not can_view_content(callback.from_user.id):
        await callback.answer("⛔ حساب شما هنوز فعال نیست.", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await callback.answer("اطلاعات مرحله درست نیست.", show_alert=True)
        return

    await callback.answer()
    await send_training_step_detail(callback.message, int(parts[1]), int(parts[2]))


@dp.callback_query(F.data.startswith("training_quiz:"))
async def training_quiz_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("📝 آزمون ۴ گزینه‌ای این مرحله در قدم بعدی اضافه می‌شود.")


@dp.message(F.text == "✏️ ویرایش محتوای آموزش")
async def edit_training_content_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی ویرایش آموزش‌ها ندارید.")
        return
    clear_waiting_states(message.from_user.id)
    await send_training_level_selection(message, "edit_content", "✏️ ویرایش محتوای آموزش")


@dp.callback_query(F.data == "edit_content_levels")
async def edit_content_levels_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ویرایش آموزش‌ها ندارید.", show_alert=True)
        return
    await callback.answer()
    await send_training_level_selection(callback.message, "edit_content", "✏️ ویرایش محتوای آموزش")


@dp.callback_query(F.data.startswith("edit_content_level:"))
async def edit_content_level_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ویرایش آموزش‌ها ندارید.", show_alert=True)
        return
    level_text = callback.data.split(":")[1]
    if not level_text.isdigit():
        await callback.answer("شماره سطح درست نیست.", show_alert=True)
        return
    await callback.answer()
    await send_training_step_selection(callback.message, "edit_content", int(level_text), "✏️ ویرایش محتوای آموزش", "edit_content_levels")


@dp.callback_query(F.data.startswith("edit_content_step:"))
async def edit_content_step_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ویرایش آموزش‌ها ندارید.", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await callback.answer("اطلاعات مرحله درست نیست.", show_alert=True)
        return
    await callback.answer()
    await prepare_edit_training_content(callback.message, callback.from_user.id, int(parts[1]), int(parts[2]))


@dp.message(F.text == "✏️ ویرایش عنوان مرحله")
async def edit_training_title_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی ویرایش آموزش‌ها ندارید.")
        return
    clear_waiting_states(message.from_user.id)
    await send_training_level_selection(message, "edit_title", "✏️ ویرایش عنوان مرحله")


@dp.callback_query(F.data == "edit_title_levels")
async def edit_title_levels_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ویرایش آموزش‌ها ندارید.", show_alert=True)
        return
    await callback.answer()
    await send_training_level_selection(callback.message, "edit_title", "✏️ ویرایش عنوان مرحله")


@dp.callback_query(F.data.startswith("edit_title_level:"))
async def edit_title_level_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ویرایش آموزش‌ها ندارید.", show_alert=True)
        return
    level_text = callback.data.split(":")[1]
    if not level_text.isdigit():
        await callback.answer("شماره سطح درست نیست.", show_alert=True)
        return
    await callback.answer()
    await send_training_step_selection(callback.message, "edit_title", int(level_text), "✏️ ویرایش عنوان مرحله", "edit_title_levels")


@dp.callback_query(F.data.startswith("edit_title_step:"))
async def edit_title_step_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ویرایش آموزش‌ها ندارید.", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await callback.answer("اطلاعات مرحله درست نیست.", show_alert=True)
        return
    await callback.answer()
    await prepare_edit_training_title(callback.message, callback.from_user.id, int(parts[1]), int(parts[2]))


@dp.message(F.text == "✏️ ویرایش توضیح سطح")
async def edit_level_description_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی ویرایش آموزش‌ها ندارید.")
        return
    clear_waiting_states(message.from_user.id)
    await send_training_level_selection(message, "edit_level_desc", "✏️ ویرایش توضیح سطح")


@dp.callback_query(F.data.startswith("edit_level_desc_level:"))
async def edit_level_desc_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ویرایش آموزش‌ها ندارید.", show_alert=True)
        return
    level_text = callback.data.split(":")[1]
    if not level_text.isdigit():
        await callback.answer("شماره سطح درست نیست.", show_alert=True)
        return
    await callback.answer()
    await prepare_edit_level_description(callback.message, callback.from_user.id, int(level_text))


@dp.message(F.text == "📄 افزودن PDF آموزش")
async def add_training_pdf_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی افزودن PDF آموزش ندارید.")
        return
    clear_waiting_states(message.from_user.id)
    await send_training_level_selection(message, "add_media_pdf", "📄 افزودن PDF آموزش")


@dp.message(F.text == "🎥 افزودن ویدئو آموزش")
async def add_training_video_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی افزودن ویدئو آموزش ندارید.")
        return
    clear_waiting_states(message.from_user.id)
    await send_training_level_selection(message, "add_media_video", "🎥 افزودن ویدئو آموزش")


@dp.message(F.text == "🖼 افزودن عکس آموزش")
async def add_training_photo_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی افزودن عکس آموزش ندارید.")
        return
    clear_waiting_states(message.from_user.id)
    await send_training_level_selection(message, "add_media_photo", "🖼 افزودن عکس آموزش")


@dp.callback_query(F.data.startswith("add_media_pdf_level:"))
async def add_media_pdf_level_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    level_text = callback.data.split(":")[1]
    await callback.answer()
    await send_training_step_selection(callback.message, "add_media_pdf", int(level_text), "📄 افزودن PDF آموزش", "add_media_pdf_levels")


@dp.callback_query(F.data.startswith("add_media_video_level:"))
async def add_media_video_level_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    level_text = callback.data.split(":")[1]
    await callback.answer()
    await send_training_step_selection(callback.message, "add_media_video", int(level_text), "🎥 افزودن ویدئو آموزش", "add_media_video_levels")


@dp.callback_query(F.data.startswith("add_media_photo_level:"))
async def add_media_photo_level_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    level_text = callback.data.split(":")[1]
    await callback.answer()
    await send_training_step_selection(callback.message, "add_media_photo", int(level_text), "🖼 افزودن عکس آموزش", "add_media_photo_levels")


@dp.callback_query(F.data == "add_media_pdf_levels")
async def add_media_pdf_levels_back(callback: CallbackQuery):
    await callback.answer()
    await send_training_level_selection(callback.message, "add_media_pdf", "📄 افزودن PDF آموزش")


@dp.callback_query(F.data == "add_media_video_levels")
async def add_media_video_levels_back(callback: CallbackQuery):
    await callback.answer()
    await send_training_level_selection(callback.message, "add_media_video", "🎥 افزودن ویدئو آموزش")


@dp.callback_query(F.data == "add_media_photo_levels")
async def add_media_photo_levels_back(callback: CallbackQuery):
    await callback.answer()
    await send_training_level_selection(callback.message, "add_media_photo", "🖼 افزودن عکس آموزش")


@dp.callback_query(F.data.startswith("add_media_pdf_step:"))
async def add_media_pdf_step_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    parts = callback.data.split(":")
    await callback.answer()
    await prepare_training_media_file(callback.message, callback.from_user.id, "pdf", int(parts[1]), int(parts[2]))


@dp.callback_query(F.data.startswith("add_media_video_step:"))
async def add_media_video_step_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    parts = callback.data.split(":")
    await callback.answer()
    await prepare_training_media_file(callback.message, callback.from_user.id, "video", int(parts[1]), int(parts[2]))


@dp.callback_query(F.data.startswith("add_media_photo_step:"))
async def add_media_photo_step_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    parts = callback.data.split(":")
    await callback.answer()
    await prepare_training_media_file(callback.message, callback.from_user.id, "photo", int(parts[1]), int(parts[2]))


@dp.message(F.text == "🗑 حذف/غیرفعال کردن فایل آموزش")
async def delete_training_media_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی حذف فایل آموزش ندارید.")
        return
    clear_waiting_states(message.from_user.id)
    await message.answer(
        "🗑 حذف/غیرفعال کردن فایل آموزش\n\n"
        "کدام نوع فایل را می‌خواهی غیرفعال کنی؟",
        reply_markup=get_training_media_type_keyboard("delete_media_type"),
    )


@dp.callback_query(F.data.startswith("delete_media_type:"))
async def delete_media_type_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    media_type = callback.data.split(":")[1]
    await callback.answer()
    await send_training_level_selection(callback.message, f"delete_media_{media_type}", f"🗑 حذف {get_training_media_label(media_type)}")


@dp.callback_query(F.data.startswith("delete_media_pdf_level:"))
async def delete_media_pdf_level_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    level_text = callback.data.split(":")[1]
    await callback.answer()
    await send_training_step_selection(callback.message, "delete_media_pdf", int(level_text), "🗑 حذف PDF آموزش", "delete_media_pdf_levels")


@dp.callback_query(F.data.startswith("delete_media_video_level:"))
async def delete_media_video_level_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    level_text = callback.data.split(":")[1]
    await callback.answer()
    await send_training_step_selection(callback.message, "delete_media_video", int(level_text), "🗑 حذف ویدئو آموزش", "delete_media_video_levels")


@dp.callback_query(F.data.startswith("delete_media_photo_level:"))
async def delete_media_photo_level_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    level_text = callback.data.split(":")[1]
    await callback.answer()
    await send_training_step_selection(callback.message, "delete_media_photo", int(level_text), "🗑 حذف عکس آموزش", "delete_media_photo_levels")


@dp.callback_query(F.data == "delete_media_pdf_levels")
async def delete_media_pdf_levels_back(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    await callback.answer()
    await send_training_level_selection(callback.message, "delete_media_pdf", "🗑 حذف PDF آموزش")


@dp.callback_query(F.data == "delete_media_video_levels")
async def delete_media_video_levels_back(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    await callback.answer()
    await send_training_level_selection(callback.message, "delete_media_video", "🗑 حذف ویدئو آموزش")


@dp.callback_query(F.data == "delete_media_photo_levels")
async def delete_media_photo_levels_back(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    await callback.answer()
    await send_training_level_selection(callback.message, "delete_media_photo", "🗑 حذف عکس آموزش")


@dp.callback_query(F.data.startswith("delete_media_pdf_step:"))
async def delete_media_pdf_step_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    await callback.answer()
    await delete_training_media(callback.message, "pdf", int(parts[1]), int(parts[2]))


@dp.callback_query(F.data.startswith("delete_media_video_step:"))
async def delete_media_video_step_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    await callback.answer()
    await delete_training_media(callback.message, "video", int(parts[1]), int(parts[2]))


@dp.callback_query(F.data.startswith("delete_media_photo_step:"))
async def delete_media_photo_step_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ دسترسی ندارید.", show_alert=True)
        return
    await callback.answer()
    await delete_training_media(callback.message, "photo", int(parts[1]), int(parts[2]))



@dp.message(F.text == "🔎 جستجو")
async def global_search_handler(message: Message):
    if not can_view_content(message.from_user.id):
        await message.answer("⛔ حساب شما هنوز فعال نیست.")
        return

    clear_waiting_states(message.from_user.id)
    set_state(message.from_user.id, "global_search")

    await message.answer(
        "🔎 جستجو در کل ربات\n\n"
        "یک کلمه یا عبارت بفرست تا داخل این بخش‌ها جستجو کنم:\n"
        "📦 محصولات\n"
        "❓ سوالات محصول\n"
        "🎓 آموزش‌ها\n"
        "🛡 ابجکشن‌ها\n"
        "❓ سوالات پرتکرار عمومی\n\n"
        "مثال‌های خوب برای جستجو:\n"
        "آلوئه ورا\n"
        "ثبت سفارش\n"
        "اعتراض قیمت\n\n"
        "اگر نتیجه نگرفتی، همینجا یک کلمه ساده‌تر بفرست.\n"
        "برای خروج هم از دکمه 🔙 بازگشت به منوی اصلی استفاده کن."
    )


@dp.message(F.text == "✍️ ارسال سوال")
async def ask_question_handler(message: Message):
    if not can_view_content(message.from_user.id):
        await message.answer("⛔ حساب شما هنوز فعال نیست.")
        return

    clear_waiting_states(message.from_user.id)
    set_state(message.from_user.id, "ask_question")

    await message.answer(
        "✍️ سوالت را همینجا بنویس و ارسال کن.\n\n"
        "ادمین یا ویراستار بعداً پاسخ می‌دهد."
    )


@dp.message(F.text == "❓ سوالات بی‌جواب")
async def unanswered_questions_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی مدیریت سوالات را ندارید.")
        return

    await send_unanswered_questions_menu(message)


@dp.message(F.text == "📋 سوالات جدید")
async def new_questions_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی مدیریت سوالات را ندارید.")
        return

    await send_questions_list(message, "new")


@dp.message(F.text == "✅ سوالات پاسخ‌داده‌شده")
async def answered_questions_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی مدیریت سوالات را ندارید.")
        return

    await send_questions_list(message, "answered")


@dp.message(F.text == "🗂 سوالات آرشیو")
async def archived_questions_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی مدیریت سوالات را ندارید.")
        return

    await send_questions_list(message, "archived")


@dp.callback_query(F.data.startswith("uq_list:"))
async def uq_list_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی مدیریت سوالات را ندارید.", show_alert=True)
        return

    status = callback.data.split(":")[1]
    await callback.answer()
    await send_questions_list(callback.message, status)


@dp.callback_query(F.data.startswith("uq_detail:"))
async def uq_detail_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی مدیریت سوالات را ندارید.", show_alert=True)
        return

    question_id = callback.data.replace("uq_detail:", "").strip()
    await callback.answer()
    await send_question_detail(callback.message, question_id)


@dp.callback_query(F.data.startswith("uq_answer:"))
async def uq_answer_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی مدیریت سوالات را ندارید.", show_alert=True)
        return

    question_id = callback.data.replace("uq_answer:", "").strip()
    await callback.answer()
    await prepare_answer_question(callback.message, callback.from_user.id, question_id)


@dp.callback_query(F.data.startswith("uq_archive:"))
async def uq_archive_callback(callback: CallbackQuery):
    if not can_manage_content(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی مدیریت سوالات را ندارید.", show_alert=True)
        return

    question_id = callback.data.replace("uq_archive:", "").strip()

    supabase.table("unanswered_questions").update({
        "status": "archived",
        "is_active": False,
    }).eq("id", question_id).execute()

    await callback.answer("✅ سوال آرشیو شد.", show_alert=True)
    await send_questions_list(callback.message, "new")


@dp.message(F.text == "❓ سوالات پرتکرار")
async def common_questions_handler(message: Message):
    if not can_view_content(message.from_user.id):
        await message.answer("⛔ حساب شما هنوز فعال نیست.")
        return

    await send_public_faq_menu(message)


@dp.callback_query(F.data == "public_faq_list")
async def public_faq_list_callback(callback: CallbackQuery):
    if not can_view_content(callback.from_user.id):
        await callback.answer("⛔ حساب شما هنوز فعال نیست.", show_alert=True)
        return

    await callback.answer()
    await send_public_faq_list(callback.message)


@dp.callback_query(F.data == "public_faq_search")
async def public_faq_search_callback(callback: CallbackQuery):
    if not can_view_content(callback.from_user.id):
        await callback.answer("⛔ حساب شما هنوز فعال نیست.", show_alert=True)
        return

    clear_waiting_states(callback.from_user.id)
    set_state(callback.from_user.id, "public_faq_search")

    await callback.answer()
    await callback.message.answer(
        "🔎 جستجو در سوالات پرتکرار عمومی\n\n"
        "یک کلمه یا عبارت از سوالت را بفرست.\n\n"
        "مثال:\n"
        "ثبت سفارش\n"
        "ارسال محصول\n"
        "تخفیف\n\n"
        "اگر نتیجه نگرفتی، همینجا یک کلمه ساده‌تر بفرست.\n"
        "برای خروج هم از دکمه 🔙 بازگشت به منوی اصلی استفاده کن."
    )


@dp.message(F.text == "📝 افزودن محتوا")
async def add_content_handler(message: Message):
    await message.answer("برای افزودن محتوا از بخش‌های مدیریت محصولات، ابجکشن‌ها و آموزش‌ها استفاده کن.")


@dp.message(F.photo)
async def photo_file_handler(message: Message):
    state = get_state(message.from_user.id)

    if not state:
        return

    if state.get("type") == "training_media_file":
        if state.get("media_type") != "photo":
            await message.answer("❌ لطفاً عکس آموزش را ارسال کن.")
            return

        photo_file_id = message.photo[-1].file_id
        supabase.table("training_steps").update({state["column_name"]: photo_file_id}).eq("id", state["step_id"]).execute()
        clear_waiting_states(message.from_user.id)

        await message.answer(
            "✅ عکس آموزش با موفقیت ثبت شد.\n\n"
            f"سطح {state['level_number']} - مرحله {state['step_number']}\n"
            f"{state['title']}"
        )
        return

    if state.get("type") == "product_media":
        if state.get("media_type") != "photo":
            await message.answer("❌ لطفاً فایل درست را بفرست.")
            return

        photo_file_id = message.photo[-1].file_id
        supabase.table("product_media").insert({
            "product_id": state["product_id"],
            "media_type": "photo",
            "title": "عکس محصول",
            "file_url": photo_file_id,
        }).execute()
        clear_waiting_states(message.from_user.id)
        await message.answer(f"✅ عکس محصول {state['product_name']} با موفقیت ثبت شد.")
        return


@dp.message(F.video)
async def video_file_handler(message: Message):
    state = get_state(message.from_user.id)

    if not state:
        return

    if state.get("type") == "training_media_file":
        if state.get("media_type") != "video":
            await message.answer("❌ لطفاً ویدئو آموزش را ارسال کن.")
            return

        video_file_id = message.video.file_id
        supabase.table("training_steps").update({state["column_name"]: video_file_id}).eq("id", state["step_id"]).execute()
        clear_waiting_states(message.from_user.id)

        await message.answer(
            "✅ ویدئو آموزش با موفقیت ثبت شد.\n\n"
            f"سطح {state['level_number']} - مرحله {state['step_number']}\n"
            f"{state['title']}"
        )
        return

    if state.get("type") == "product_media":
        if state.get("media_type") != "video":
            await message.answer("❌ لطفاً فایل درست را بفرست.")
            return

        video_file_id = message.video.file_id
        supabase.table("product_media").insert({
            "product_id": state["product_id"],
            "media_type": "video",
            "title": "ویدئوی محصول",
            "file_url": video_file_id,
        }).execute()
        clear_waiting_states(message.from_user.id)
        await message.answer(f"✅ ویدئوی محصول {state['product_name']} با موفقیت ثبت شد.")
        return


@dp.message(F.document)
async def document_file_handler(message: Message):
    state = get_state(message.from_user.id)

    if not state:
        return

    if state.get("type") == "training_media_file":
        if state.get("media_type") != "pdf":
            await message.answer("❌ لطفاً PDF آموزش را ارسال کن.")
            return

        document_file_id = message.document.file_id
        supabase.table("training_steps").update({state["column_name"]: document_file_id}).eq("id", state["step_id"]).execute()
        clear_waiting_states(message.from_user.id)

        await message.answer(
            "✅ PDF آموزش با موفقیت ثبت شد.\n\n"
            f"سطح {state['level_number']} - مرحله {state['step_number']}\n"
            f"{state['title']}"
        )
        return

    if state.get("type") == "product_media":
        if state.get("media_type") != "catalog":
            await message.answer("❌ لطفاً فایل درست را بفرست.")
            return

        document_file_id = message.document.file_id
        supabase.table("product_media").insert({
            "product_id": state["product_id"],
            "media_type": "catalog",
            "title": message.document.file_name or "کاتالوگ محصول",
            "file_url": document_file_id,
        }).execute()
        clear_waiting_states(message.from_user.id)
        await message.answer(f"✅ کاتالوگ محصول {state['product_name']} با موفقیت ثبت شد.")
        return


@dp.message()
async def text_handler(message: Message):
    state = get_state(message.from_user.id)

    if not state:
        user = get_current_user(message.from_user.id)
        if user and user.get("is_active"):
            await message.answer(
                "لطفاً از دکمه‌های پایین یکی را انتخاب کن 👇\n\n"
                "اگر دنبال چیزی هستی، از دکمه 🔎 جستجو استفاده کن.\n"
                "اگر جواب سوالت را پیدا نکردی، از دکمه ✍️ ارسال سوال استفاده کن.",
                reply_markup=get_menu(user.get("role")),
            )
        else:
            await message.answer("⛔ حساب شما هنوز فعال نیست یا ثبت‌نام کامل نشده است. لطفاً /start را بزن.")
        return

    state_type = state.get("type")

    if state_type == "global_search":
        keyword = message.text.strip()
        await send_global_search_result(message, keyword)
        return

    if state_type == "public_faq_search":
        keyword = message.text.strip()
        await send_public_faq_search_result(message, keyword)
        return

    if state_type == "ask_question":
        question_text = message.text.strip()

        if not question_text:
            await message.answer("❌ سوال نمی‌تواند خالی باشد.")
            return

        user = get_current_user(message.from_user.id)

        try:
            supabase.table("unanswered_questions").insert({
                "user_id": user.get("id") if user else None,
                "telegram_id": message.from_user.id,
                "full_name": message.from_user.full_name,
                "username": message.from_user.username,
                "question": question_text,
                "status": "new",
                "is_active": True,
            }).execute()

            clear_waiting_states(message.from_user.id)

            await message.answer(
                "✅ سوال شما ثبت شد.\n\n"
                "بعد از بررسی، پاسخ توسط ادمین یا ویراستار ارسال می‌شود."
            )

        except Exception:
            await message.answer(
                "❌ خطا در ثبت سوال.\n\n"
                "اگر این خطا تکرار شد، جدول unanswered_questions را در Supabase بررسی کن."
            )

        return

    if state_type == "unanswered_answer":
        answer_text = message.text.strip()

        if not answer_text:
            await message.answer("❌ پاسخ نمی‌تواند خالی باشد.")
            return

        try:
            supabase.table("unanswered_questions").update({
                "answer": answer_text,
                "status": "answered",
                "answered_by": message.from_user.id,
                "answered_at": datetime.now(timezone.utc).isoformat(),
                "is_active": True,
            }).eq("id", state["question_id"]).execute()

            customer_telegram_id = state.get("customer_telegram_id")
            if customer_telegram_id:
                try:
                    await bot.send_message(
                        chat_id=customer_telegram_id,
                        text=(
                            "✅ پاسخ سوال شما آماده شد.\n\n"
                            f"سوال:\n{state.get('question')}\n\n"
                            f"پاسخ:\n{answer_text}"
                        ),
                    )
                except Exception:
                    pass

            clear_waiting_states(message.from_user.id)

            await message.answer("✅ پاسخ ثبت شد و وضعیت سوال به پاسخ‌داده‌شده تغییر کرد.")

        except Exception:
            await message.answer("❌ خطا در ثبت پاسخ سوال.")

        return

    if state_type == "training_edit_content":
        new_content = message.text.strip()
        if not new_content:
            await message.answer("❌ متن آموزش نمی‌تواند خالی باشد.")
            return

        try:
            supabase.table("training_steps").update({"content": new_content}).eq("id", state["step_id"]).execute()
            clear_waiting_states(message.from_user.id)
            await message.answer(
                "✅ محتوای آموزش با موفقیت ویرایش شد.\n\n"
                f"سطح {state['level_number']} - مرحله {state['step_number']}\n"
                f"{state['title']}"
            )
        except Exception:
            await message.answer("❌ خطا در ویرایش محتوای آموزش.")
        return

    if state_type == "training_edit_title":
        new_title = message.text.strip()
        if not new_title:
            await message.answer("❌ عنوان مرحله نمی‌تواند خالی باشد.")
            return

        try:
            supabase.table("training_steps").update({"title": new_title}).eq("id", state["step_id"]).execute()
            clear_waiting_states(message.from_user.id)
            await message.answer(
                "✅ عنوان مرحله با موفقیت ویرایش شد.\n\n"
                f"سطح {state['level_number']} - مرحله {state['step_number']}\n"
                f"عنوان جدید: {new_title}"
            )
        except Exception:
            await message.answer("❌ خطا در ویرایش عنوان مرحله.")
        return

    if state_type == "training_edit_level_description":
        new_description = message.text.strip()
        if not new_description:
            await message.answer("❌ توضیح سطح نمی‌تواند خالی باشد.")
            return

        try:
            supabase.table("training_levels").update({"description": new_description}).eq("id", state["level_id"]).execute()
            clear_waiting_states(message.from_user.id)
            await message.answer(
                "✅ توضیح سطح با موفقیت ویرایش شد.\n\n"
                f"سطح {state['level_number']}: {state['title']}"
            )
        except Exception:
            await message.answer("❌ خطا در ویرایش توضیح سطح.")
        return

    if state_type == "objection_add":
        objection_data = parse_objection_text(message.text)

        if not objection_data["objection"] or not objection_data["answer"]:
            await message.answer("❌ ابجکشن و پاسخ هر دو الزامی هستند.")
            return

        supabase.table("objection_answers").insert({
            "product_id": None,
            "objection": objection_data["objection"],
            "answer": objection_data["answer"],
            "is_active": True,
        }).execute()

        clear_waiting_states(message.from_user.id)
        await message.answer("✅ پاسخ ابجکشن با موفقیت ثبت شد.")
        return

    if state_type == "product_story_caption":
        story_text = message.text.strip()

        if not story_text:
            await message.answer("❌ متن کپشن و استوری نمی‌تواند خالی باشد.")
            return

        try:
            if story_text in ["حذف", "پاک", "پاک کردن", "حذف شود"]:
                supabase.table("products").update({
                    "story_caption": None,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", state["product_id"]).execute()

                clear_waiting_states(message.from_user.id)
                await message.answer(f"✅ کپشن و استوری محصول {state['product_name']} پاک شد.")
                return

            supabase.table("products").update({
                "story_caption": story_text,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", state["product_id"]).execute()

            clear_waiting_states(message.from_user.id)
            await message.answer(f"✅ کپشن و استوری محصول {state['product_name']} با موفقیت ثبت شد.")

        except Exception:
            await message.answer(
                "❌ خطا در ثبت کپشن و استوری محصول.\n\n"
                "اگر این خطا را دیدی، یک‌بار این SQL را در Supabase اجرا کن:\n"
                "alter table products add column if not exists story_caption text;"
            )
        return

    if state_type == "product_faq":
        faq_data = parse_faq_text(message.text)

        if not faq_data["question"] or not faq_data["answer"]:
            await message.answer("❌ سوال و پاسخ هر دو الزامی هستند.")
            return

        supabase.table("product_faqs").insert({
            "product_id": state["product_id"],
            "question": faq_data["question"],
            "answer": faq_data["answer"],
            "is_active": True,
        }).execute()

        clear_waiting_states(message.from_user.id)
        await message.answer(f"✅ سوال و پاسخ محصول {state['product_name']} ثبت شد.")
        return

    if state_type == "product_edit":
        product_data = parse_product_text(message.text)

        if not product_data["code"] or not product_data["fa_name"]:
            await message.answer("❌ کد محصول و نام فارسی الزامی است.")
            return

        product_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        try:
            supabase.table("products").update(product_data).eq("id", state["product_id"]).execute()
            clear_waiting_states(message.from_user.id)
            await message.answer("✅ محصول با موفقیت ویرایش شد.")
        except Exception:
            await message.answer("❌ خطا در ویرایش محصول.")
        return

    if state_type == "product_add":
        product_data = parse_product_text(message.text)

        if not product_data["code"] or not product_data["fa_name"]:
            await message.answer("❌ کد محصول و نام فارسی الزامی است.")
            return

        try:
            supabase.table("products").insert(product_data).execute()
            clear_waiting_states(message.from_user.id)
            await message.answer(
                "✅ محصول با موفقیت ثبت شد.\n\n"
                f"کد محصول: {product_data['code']}\n"
                f"نام محصول: {product_data['fa_name']}"
            )
        except Exception:
            await message.answer("❌ خطا در ثبت محصول. احتمالاً کد محصول تکراری است.")
        return


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
