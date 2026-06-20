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
    InlineKeyboardButton
)
from aiogram.filters import CommandStart

from database import supabase

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

VALID_ROLES = ["approved_customer", "content_contributor", "admin"]

WAITING_PRODUCT_INPUT = {}
WAITING_PHOTO_CODE = {}
WAITING_PHOTO_FILE = {}
WAITING_VIDEO_CODE = {}
WAITING_VIDEO_FILE = {}
WAITING_CATALOG_CODE = {}
WAITING_CATALOG_FILE = {}
WAITING_EDIT_CODE = {}
WAITING_EDIT_INPUT = {}
WAITING_FAQ_CODE = {}
WAITING_FAQ_INPUT = {}
WAITING_OBJECTION_INPUT = {}


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
            "username": username
        }).eq("telegram_id", telegram_id).execute()

        return existing_user.data[0]

    new_user = supabase.table("app_users").insert({
        "telegram_id": telegram_id,
        "full_name": full_name,
        "username": username,
        "role": "approved_customer",
        "is_active": False
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
    return user and user["role"] == "admin"


def can_manage_content(telegram_id: int):
    user = get_current_user(telegram_id)
    return user and user["role"] in ["admin", "content_contributor"]


def can_view_content(telegram_id: int):
    user = get_current_user(telegram_id)
    return user and user["is_active"]


def clear_waiting_states(telegram_id: int):
    WAITING_PRODUCT_INPUT.pop(telegram_id, None)
    WAITING_PHOTO_CODE.pop(telegram_id, None)
    WAITING_PHOTO_FILE.pop(telegram_id, None)
    WAITING_VIDEO_CODE.pop(telegram_id, None)
    WAITING_VIDEO_FILE.pop(telegram_id, None)
    WAITING_CATALOG_CODE.pop(telegram_id, None)
    WAITING_CATALOG_FILE.pop(telegram_id, None)
    WAITING_EDIT_CODE.pop(telegram_id, None)
    WAITING_EDIT_INPUT.pop(telegram_id, None)
    WAITING_FAQ_CODE.pop(telegram_id, None)
    WAITING_FAQ_INPUT.pop(telegram_id, None)
    WAITING_OBJECTION_INPUT.pop(telegram_id, None)


def get_menu(role: str):
    if role == "admin":
        buttons = [
            [KeyboardButton(text="👥 مدیریت کاربران")],
            [KeyboardButton(text="📦 مدیریت محصولات")],
            [KeyboardButton(text="🛡 مدیریت ابجکشن‌ها")],
            [KeyboardButton(text="🎓 مدیریت آموزش‌ها")],
            [KeyboardButton(text="❓ سوالات بی‌جواب")]
        ]
    elif role == "content_contributor":
        buttons = [
            [KeyboardButton(text="📦 مدیریت محصولات")],
            [KeyboardButton(text="🛡 مدیریت ابجکشن‌ها")],
            [KeyboardButton(text="🎓 مدیریت آموزش‌ها")],
            [KeyboardButton(text="📝 افزودن محتوا")]
        ]
    else:
        buttons = [
            [KeyboardButton(text="📦 محصولات")],
            [KeyboardButton(text="🛡 پاسخ به ابجکشن‌ها")],
            [KeyboardButton(text="🎓 آموزش‌ها")],
            [KeyboardButton(text="❓ سوالات پرتکرار")]
        ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_products_menu():
    buttons = [
        [KeyboardButton(text="➕ افزودن محصول")],
        [KeyboardButton(text="🖼 افزودن عکس محصول")],
        [KeyboardButton(text="🎥 افزودن ویدئو محصول")],
        [KeyboardButton(text="📄 افزودن کاتالوگ محصول")],
        [KeyboardButton(text="❓ افزودن سوال محصول")],
        [KeyboardButton(text="✏️ ویرایش محصول")],
        [KeyboardButton(text="📦 محصولات")],
        [KeyboardButton(text="🔙 بازگشت به منوی اصلی")]
    ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_objections_menu():
    buttons = [
        [KeyboardButton(text="➕ افزودن پاسخ ابجکشن")],
        [KeyboardButton(text="🛡 پاسخ به ابجکشن‌ها")],
        [KeyboardButton(text="🔙 بازگشت به منوی اصلی")]
    ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_trainings_menu():
    buttons = [
        [KeyboardButton(text="🎓 آموزش‌ها")],
        [KeyboardButton(text="🔙 بازگشت به منوی اصلی")]
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
        "intro_text": ""
    }

    lines = text.splitlines()

    for line in lines:
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
    data = {
        "question": "",
        "answer": ""
    }

    lines = text.splitlines()

    for line in lines:
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
    data = {
        "objection": "",
        "answer": ""
    }

    lines = text.splitlines()

    for line in lines:
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


def get_training_levels_keyboard(levels):
    buttons = []

    for item in levels:
        buttons.append([
            InlineKeyboardButton(
                text=f"سطح {item.get('level_number')}: {item.get('title')}",
                callback_data=f"training_level:{item.get('level_number')}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_training_steps_keyboard(level_number, steps):
    buttons = []

    for step in steps:
        buttons.append([
            InlineKeyboardButton(
                text=f"مرحله {step.get('step_number')}: {step.get('title')}",
                callback_data=f"training_step:{level_number}:{step.get('step_number')}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="🔙 بازگشت به سطح‌ها",
            callback_data="training_levels"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_training_step_detail_keyboard(level_number, step_number, title):
    buttons = []

    if title == "پاسخ به ابجکشن‌ها":
        buttons.append([
            InlineKeyboardButton(
                text="🛡 دیدن پاسخ به ابجکشن‌ها",
                callback_data="show_objections"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="📝 شروع آزمون",
            callback_data=f"training_quiz:{level_number}:{step_number}"
        )
    ])

    buttons.append([
        InlineKeyboardButton(
            text="🔙 بازگشت به مرحله‌ها",
            callback_data=f"training_level:{level_number}"
        )
    ])

    buttons.append([
        InlineKeyboardButton(
            text="🏠 بازگشت به سطح‌ها",
            callback_data="training_levels"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_products_keyboard(products):
    buttons = []

    for item in products:
        buttons.append([
            InlineKeyboardButton(
                text=f"{item.get('code')} - {item.get('fa_name')}",
                callback_data=f"product:{item.get('code')}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_product_detail_keyboard():
    buttons = [
        [
            InlineKeyboardButton(
                text="🔙 بازگشت به محصولات",
                callback_data="products_list"
            )
        ]
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

    await target.answer(
        text,
        reply_markup=get_training_levels_keyboard(levels.data)
    )


async def send_training_level_steps(target, level_number: int):
    level = (
        supabase.table("training_levels")
        .select("*")
        .eq("level_number", level_number)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if not level.data:
        await target.answer("❌ این سطح آموزشی پیدا نشد.")
        return

    level_item = level.data[0]

    steps = (
        supabase.table("training_steps")
        .select("*")
        .eq("level_id", level_item.get("id"))
        .eq("is_active", True)
        .order("step_number")
        .execute()
    )

    if not steps.data:
        await target.answer("برای این سطح هنوز مرحله‌ای ثبت نشده است.")
        return

    text = f"🎓 سطح {level_item.get('level_number')}: {level_item.get('title')}\n\n"
    text += f"{level_item.get('description') or ''}\n\n"
    text += "یکی از مرحله‌ها را انتخاب کن:"

    await target.answer(
        text,
        reply_markup=get_training_steps_keyboard(level_number, steps.data)
    )


async def send_training_step_detail(target, level_number: int, step_number: int):
    level = (
        supabase.table("training_levels")
        .select("*")
        .eq("level_number", level_number)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if not level.data:
        await target.answer("❌ این سطح آموزشی پیدا نشد.")
        return

    step = (
        supabase.table("training_steps")
        .select("*")
        .eq("level_id", level.data[0].get("id"))
        .eq("step_number", step_number)
        .eq("is_active", True)
        .limit(1)
        .execute()
    )

    if not step.data:
        await target.answer("❌ این مرحله آموزشی پیدا نشد.")
        return

    item = step.data[0]

    text = f"🎓 سطح {level_number} - مرحله {step_number}\n"
    text += f"{item.get('title')}\n\n"
    text += f"{item.get('content') or 'محتوای این آموزش بعداً تکمیل می‌شود.'}\n\n"
    text += "بعد از مطالعه، روی دکمه شروع آزمون بزن."

    await target.answer(
        text,
        reply_markup=get_training_step_detail_keyboard(
            level_number,
            step_number,
            item.get("title")
        )
    )


async def send_products_list(target):
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

    text = "📦 لیست محصولات\n\n"
    text += "برای دیدن اطلاعات کامل، روی محصول موردنظر بزن:"

    await target.answer(
        text,
        reply_markup=get_products_keyboard(products.data)
    )


async def send_product_detail(target, code: str):
    result = (
        supabase.table("products")
        .select("*")
        .eq("code", code)
        .eq("is_active", True)
        .execute()
    )

    if not result.data:
        await target.answer("❌ محصولی با این کد پیدا نشد.")
        return

    product = result.data[0]

    photo = (
        supabase.table("product_media")
        .select("*")
        .eq("product_id", product.get("id"))
        .eq("media_type", "photo")
        .limit(1)
        .execute()
    )

    if photo.data:
        await target.answer_photo(
            photo=photo.data[0].get("file_url"),
            caption=f"📦 {product.get('fa_name')}"
        )

    video = (
        supabase.table("product_media")
        .select("*")
        .eq("product_id", product.get("id"))
        .eq("media_type", "video")
        .limit(1)
        .execute()
    )

    if video.data:
        await target.answer_video(
            video=video.data[0].get("file_url"),
            caption=f"🎥 ویدئوی معرفی {product.get('fa_name')}"
        )

    catalog = (
        supabase.table("product_media")
        .select("*")
        .eq("product_id", product.get("id"))
        .eq("media_type", "catalog")
        .limit(1)
        .execute()
    )

    if catalog.data:
        await target.answer_document(
            document=catalog.data[0].get("file_url"),
            caption=f"📄 کاتالوگ {product.get('fa_name')}"
        )

    faqs = (
        supabase.table("product_faqs")
        .select("*")
        .eq("product_id", product.get("id"))
        .eq("is_active", True)
        .execute()
    )

    text = f"📦 {product.get('fa_name')}\n\n"
    text += f"کد محصول: {product.get('code')}\n"
    text += f"نام انگلیسی: {product.get('en_name') or '-'}\n"
    text += f"حجم: {product.get('volume') or '-'}\n"
    text += f"دسته‌بندی: {product.get('category') or '-'}\n\n"
    text += f"ویژگی‌ها:\n{product.get('features') or '-'}\n\n"
    text += f"مزایا:\n{product.get('benefits') or '-'}\n\n"
    text += f"نحوه استفاده:\n{product.get('usage_method') or '-'}\n\n"
    text += f"نکات مهم:\n{product.get('important_notes') or '-'}\n\n"
    text += f"متن معرفی:\n{product.get('intro_text') or '-'}\n\n"

    if faqs.data:
        text += "❓ سوالات پرتکرار:\n\n"
        for faq in faqs.data:
            text += f"سوال: {faq.get('question')}\n"
            text += f"پاسخ: {faq.get('answer')}\n\n"

    await target.answer(
        text,
        reply_markup=get_product_detail_keyboard()
    )


@dp.message(CommandStart())
async def start_handler(message: Message):
    user = register_user(message)

    if not user["is_active"]:
        await message.answer(
            "سلام 👋\n"
            "ثبت‌نام شما انجام شد.\n\n"
            "⏳ حساب شما هنوز توسط ادمین تأیید نشده است."
        )
        return

    await message.answer(
        "سلام 👋\n"
        "به سیستم آموزشی فوراور خوش آمدید ✅",
        reply_markup=get_menu(user["role"])
    )


@dp.message(F.text == "🔙 بازگشت به منوی اصلی")
async def back_to_main_menu_handler(message: Message):
    user = get_current_user(message.from_user.id)
    clear_waiting_states(message.from_user.id)

    if not user or not user["is_active"]:
        await message.answer("⛔ حساب شما هنوز فعال نیست.")
        return

    await message.answer(
        "منوی اصلی:",
        reply_markup=get_menu(user["role"])
    )


@dp.message(F.text == "👥 مدیریت کاربران")
async def manage_users_handler(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ شما دسترسی ادمین ندارید.")
        return

    users = (
        supabase.table("app_users")
        .select("*")
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )

    if not users.data:
        await message.answer("هیچ کاربری ثبت نشده است.")
        return

    text = "👥 لیست کاربران:\n\n"

    for item in users.data:
        active_text = "فعال" if item.get("is_active") else "در انتظار تأیید"

        text += f"نام: {item.get('full_name')}\n"
        text += f"یوزرنیم: @{item.get('username')}\n"
        text += f"تلگرام آیدی: {item.get('telegram_id')}\n"
        text += f"نقش: {item.get('role')}\n"
        text += f"وضعیت: {active_text}\n"
        text += f"تأیید: /approve {item.get('telegram_id')}\n"
        text += f"تغییر نقش: /setrole {item.get('telegram_id')} content_contributor\n"
        text += "------------------\n"

    await message.answer(text)


@dp.message(F.text.startswith("/approve "))
async def approve_user_handler(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ شما دسترسی ادمین ندارید.")
        return

    telegram_id_text = message.text.replace("/approve ", "").strip()

    if not telegram_id_text.isdigit():
        await message.answer("❌ آیدی تلگرام درست نیست.")
        return

    telegram_id = int(telegram_id_text)

    result = (
        supabase.table("app_users")
        .update({"is_active": True})
        .eq("telegram_id", telegram_id)
        .execute()
    )

    if result.data:
        await message.answer("✅ کاربر تأیید شد.")
    else:
        await message.answer("❌ کاربری با این آیدی پیدا نشد.")


@dp.message(F.text.startswith("/setrole "))
async def set_role_handler(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ شما دسترسی ادمین ندارید.")
        return

    parts = message.text.split()

    if len(parts) != 3:
        await message.answer("❌ دستور درست نیست.")
        return

    telegram_id_text = parts[1]
    new_role = parts[2]

    if not telegram_id_text.isdigit():
        await message.answer("❌ آیدی تلگرام درست نیست.")
        return

    if new_role not in VALID_ROLES:
        await message.answer("❌ نقش درست نیست.")
        return

    telegram_id = int(telegram_id_text)

    result = (
        supabase.table("app_users")
        .update({"role": new_role, "is_active": True})
        .eq("telegram_id", telegram_id)
        .execute()
    )

    if result.data:
        await message.answer("✅ نقش کاربر تغییر کرد.")
    else:
        await message.answer("❌ کاربری با این آیدی پیدا نشد.")


@dp.message(F.text == "📦 مدیریت محصولات")
async def manage_products_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی مدیریت محصولات ندارید.")
        return

    await message.answer(
        "📦 مدیریت محصولات",
        reply_markup=get_products_menu()
    )


@dp.message(F.text == "🛡 مدیریت ابجکشن‌ها")
async def manage_objections_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی مدیریت ابجکشن‌ها ندارید.")
        return

    await message.answer(
        "🛡 مدیریت ابجکشن‌ها",
        reply_markup=get_objections_menu()
    )


@dp.message(F.text == "🎓 مدیریت آموزش‌ها")
async def manage_trainings_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی مدیریت آموزش‌ها ندارید.")
        return

    await message.answer(
        "🎓 مدیریت آموزش‌ها",
        reply_markup=get_trainings_menu()
    )


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

    if len(parts) != 3:
        await callback.answer("اطلاعات مرحله درست نیست.", show_alert=True)
        return

    level_text = parts[1]
    step_text = parts[2]

    if not level_text.isdigit() or not step_text.isdigit():
        await callback.answer("شماره سطح و مرحله درست نیست.", show_alert=True)
        return

    await callback.answer()
    await send_training_step_detail(
        callback.message,
        int(level_text),
        int(step_text)
    )


@dp.callback_query(F.data.startswith("training_quiz:"))
async def training_quiz_callback(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "📝 آزمون ۴ گزینه‌ای این مرحله در قدم بعدی اضافه می‌شود."
    )


@dp.callback_query(F.data == "show_objections")
async def show_objections_callback(callback: CallbackQuery):
    if not can_view_content(callback.from_user.id):
        await callback.answer("⛔ حساب شما هنوز فعال نیست.", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(build_objections_text())


@dp.callback_query(F.data == "products_list")
async def products_list_callback(callback: CallbackQuery):
    if not can_view_content(callback.from_user.id):
        await callback.answer("⛔ حساب شما هنوز فعال نیست.", show_alert=True)
        return

    await callback.answer()
    await send_products_list(callback.message)


@dp.callback_query(F.data.startswith("product:"))
async def product_detail_callback(callback: CallbackQuery):
    if not can_view_content(callback.from_user.id):
        await callback.answer("⛔ حساب شما هنوز فعال نیست.", show_alert=True)
        return

    code = callback.data.replace("product:", "").strip()

    await callback.answer()
    await send_product_detail(callback.message, code)


@dp.message(F.text == "➕ افزودن پاسخ ابجکشن")
async def add_objection_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی ثبت ابجکشن ندارید.")
        return

    clear_waiting_states(message.from_user.id)
    WAITING_OBJECTION_INPUT[message.from_user.id] = True

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


@dp.message(F.text == "➕ افزودن محصول")
async def add_product_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی ثبت اطلاعات ندارید.")
        return

    clear_waiting_states(message.from_user.id)
    WAITING_PRODUCT_INPUT[message.from_user.id] = True

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
    WAITING_PHOTO_CODE[message.from_user.id] = True

    await message.answer("کد محصول را بفرست.\n\nمثال:\n015")


@dp.message(F.text == "🎥 افزودن ویدئو محصول")
async def add_product_video_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی ثبت اطلاعات ندارید.")
        return

    clear_waiting_states(message.from_user.id)
    WAITING_VIDEO_CODE[message.from_user.id] = True

    await message.answer("کد محصول را بفرست.\n\nمثال:\n015")


@dp.message(F.text == "📄 افزودن کاتالوگ محصول")
async def add_product_catalog_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی ثبت اطلاعات ندارید.")
        return

    clear_waiting_states(message.from_user.id)
    WAITING_CATALOG_CODE[message.from_user.id] = True

    await message.answer("کد محصول را بفرست.\n\nمثال:\n015")


@dp.message(F.text == "❓ افزودن سوال محصول")
async def add_product_faq_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی ثبت سوال ندارید.")
        return

    clear_waiting_states(message.from_user.id)
    WAITING_FAQ_CODE[message.from_user.id] = True

    await message.answer("کد محصول را بفرست.\n\nمثال:\n015")


@dp.message(F.text == "✏️ ویرایش محصول")
async def edit_product_handler(message: Message):
    if not can_manage_content(message.from_user.id):
        await message.answer("⛔ شما دسترسی ویرایش محصول ندارید.")
        return

    clear_waiting_states(message.from_user.id)
    WAITING_EDIT_CODE[message.from_user.id] = True

    await message.answer("کد محصول را بفرست.\n\nمثال:\n015")


@dp.message(F.text == "📦 محصولات")
async def products_list_handler(message: Message):
    if not can_view_content(message.from_user.id):
        await message.answer("⛔ حساب شما هنوز فعال نیست.")
        return

    await send_products_list(message)


@dp.message(F.text.startswith("/product "))
async def product_detail_handler(message: Message):
    if not can_view_content(message.from_user.id):
        await message.answer("⛔ حساب شما هنوز فعال نیست.")
        return

    code = message.text.replace("/product ", "").strip()
    await send_product_detail(message, code)


@dp.message(F.photo)
async def product_photo_file_handler(message: Message):
    if not WAITING_PHOTO_FILE.get(message.from_user.id):
        return

    product_id = WAITING_PHOTO_FILE.get(message.from_user.id)
    photo_file_id = message.photo[-1].file_id

    supabase.table("product_media").insert({
        "product_id": product_id,
        "media_type": "photo",
        "title": "عکس محصول",
        "file_url": photo_file_id
    }).execute()

    clear_waiting_states(message.from_user.id)

    await message.answer("✅ عکس محصول با موفقیت ثبت شد.")


@dp.message(F.video)
async def product_video_file_handler(message: Message):
    if not WAITING_VIDEO_FILE.get(message.from_user.id):
        return

    product_id = WAITING_VIDEO_FILE.get(message.from_user.id)
    video_file_id = message.video.file_id

    supabase.table("product_media").insert({
        "product_id": product_id,
        "media_type": "video",
        "title": "ویدئوی محصول",
        "file_url": video_file_id
    }).execute()

    clear_waiting_states(message.from_user.id)

    await message.answer("✅ ویدئوی محصول با موفقیت ثبت شد.")


@dp.message(F.document)
async def product_catalog_file_handler(message: Message):
    if not WAITING_CATALOG_FILE.get(message.from_user.id):
        return

    product_id = WAITING_CATALOG_FILE.get(message.from_user.id)
    document_file_id = message.document.file_id

    supabase.table("product_media").insert({
        "product_id": product_id,
        "media_type": "catalog",
        "title": message.document.file_name or "کاتالوگ محصول",
        "file_url": document_file_id
    }).execute()

    clear_waiting_states(message.from_user.id)

    await message.answer("✅ کاتالوگ محصول با موفقیت ثبت شد.")


@dp.message()
async def text_handler(message: Message):
    if WAITING_OBJECTION_INPUT.get(message.from_user.id):
        objection_data = parse_objection_text(message.text)

        if not objection_data["objection"] or not objection_data["answer"]:
            await message.answer("❌ ابجکشن و پاسخ هر دو الزامی هستند.")
            return

        supabase.table("objection_answers").insert({
            "product_id": None,
            "objection": objection_data["objection"],
            "answer": objection_data["answer"],
            "is_active": True
        }).execute()

        clear_waiting_states(message.from_user.id)

        await message.answer("✅ پاسخ ابجکشن با موفقیت ثبت شد.")
        return

    if WAITING_PHOTO_CODE.get(message.from_user.id):
        code = message.text.strip()

        product = (
            supabase.table("products")
            .select("*")
            .eq("code", code)
            .eq("is_active", True)
            .execute()
        )

        if not product.data:
            await message.answer("❌ محصولی با این کد پیدا نشد.")
            return

        WAITING_PHOTO_CODE.pop(message.from_user.id, None)
        WAITING_PHOTO_FILE[message.from_user.id] = product.data[0]["id"]

        await message.answer("محصول پیدا شد ✅\nحالا عکس محصول را بفرست.")
        return

    if WAITING_VIDEO_CODE.get(message.from_user.id):
        code = message.text.strip()

        product = (
            supabase.table("products")
            .select("*")
            .eq("code", code)
            .eq("is_active", True)
            .execute()
        )

        if not product.data:
            await message.answer("❌ محصولی با این کد پیدا نشد.")
            return

        WAITING_VIDEO_CODE.pop(message.from_user.id, None)
        WAITING_VIDEO_FILE[message.from_user.id] = product.data[0]["id"]

        await message.answer("محصول پیدا شد ✅\nحالا ویدئوی محصول را بفرست.")
        return

    if WAITING_CATALOG_CODE.get(message.from_user.id):
        code = message.text.strip()

        product = (
            supabase.table("products")
            .select("*")
            .eq("code", code)
            .eq("is_active", True)
            .execute()
        )

        if not product.data:
            await message.answer("❌ محصولی با این کد پیدا نشد.")
            return

        WAITING_CATALOG_CODE.pop(message.from_user.id, None)
        WAITING_CATALOG_FILE[message.from_user.id] = product.data[0]["id"]

        await message.answer("محصول پیدا شد ✅\nحالا فایل کاتالوگ را بفرست.")
        return

    if WAITING_FAQ_CODE.get(message.from_user.id):
        code = message.text.strip()

        product = (
            supabase.table("products")
            .select("*")
            .eq("code", code)
            .eq("is_active", True)
            .execute()
        )

        if not product.data:
            await message.answer("❌ محصولی با این کد پیدا نشد.")
            return

        WAITING_FAQ_CODE.pop(message.from_user.id, None)
        WAITING_FAQ_INPUT[message.from_user.id] = product.data[0]["id"]

        await message.answer(
            "محصول پیدا شد ✅\n"
            "حالا سوال و پاسخ را با این قالب بفرست:\n\n"
            "سوال: \n"
            "پاسخ: "
        )
        return

    if WAITING_FAQ_INPUT.get(message.from_user.id):
        product_id = WAITING_FAQ_INPUT.get(message.from_user.id)
        faq_data = parse_faq_text(message.text)

        if not faq_data["question"] or not faq_data["answer"]:
            await message.answer("❌ سوال و پاسخ هر دو الزامی هستند.")
            return

        supabase.table("product_faqs").insert({
            "product_id": product_id,
            "question": faq_data["question"],
            "answer": faq_data["answer"],
            "is_active": True
        }).execute()

        clear_waiting_states(message.from_user.id)

        await message.answer("✅ سوال و پاسخ محصول ثبت شد.")
        return

    if WAITING_EDIT_CODE.get(message.from_user.id):
        code = message.text.strip()

        product = (
            supabase.table("products")
            .select("*")
            .eq("code", code)
            .eq("is_active", True)
            .execute()
        )

        if not product.data:
            await message.answer("❌ محصولی با این کد پیدا نشد.")
            return

        WAITING_EDIT_CODE.pop(message.from_user.id, None)
        WAITING_EDIT_INPUT[message.from_user.id] = product.data[0]["id"]

        await message.answer(
            "اطلاعات فعلی محصول این است.\n"
            "هر چیزی را می‌خواهی تغییر بده و همین متن کامل را دوباره بفرست:\n\n"
            f"{product_template(product.data[0])}"
        )
        return

    if WAITING_EDIT_INPUT.get(message.from_user.id):
        product_id = WAITING_EDIT_INPUT.get(message.from_user.id)
        product_data = parse_product_text(message.text)

        if not product_data["code"] or not product_data["fa_name"]:
            await message.answer("❌ کد محصول و نام فارسی الزامی است.")
            return

        product_data["updated_at"] = datetime.now(timezone.utc).isoformat()

        try:
            supabase.table("products").update(product_data).eq("id", product_id).execute()
            clear_waiting_states(message.from_user.id)

            await message.answer("✅ محصول با موفقیت ویرایش شد.")

        except Exception:
            await message.answer("❌ خطا در ویرایش محصول.")

        return

    if WAITING_PRODUCT_INPUT.get(message.from_user.id):
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


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())