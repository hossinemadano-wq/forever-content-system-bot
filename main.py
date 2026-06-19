import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart

from database import supabase

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

VALID_ROLES = ["approved_customer", "content_contributor", "admin"]


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


def get_menu(role: str):
    if role == "admin":
        buttons = [
            [KeyboardButton(text="👥 مدیریت کاربران")],
            [KeyboardButton(text="📦 مدیریت محصولات")],
            [KeyboardButton(text="🎓 مدیریت آموزش‌ها")],
            [KeyboardButton(text="❓ سوالات بی‌جواب")]
        ]
    elif role == "content_contributor":
        buttons = [
            [KeyboardButton(text="➕ افزودن محصول")],
            [KeyboardButton(text="🎓 افزودن آموزش")],
            [KeyboardButton(text="📝 افزودن محتوا")]
        ]
    else:
        buttons = [
            [KeyboardButton(text="📦 محصولات")],
            [KeyboardButton(text="🎓 آموزش‌ها")],
            [KeyboardButton(text="❓ سوالات پرتکرار")]
        ]

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def is_admin(telegram_id: int):
    user = get_current_user(telegram_id)
    return user and user["role"] == "admin"


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
        await message.answer(
            "❌ دستور درست نیست.\n\n"
            "مثال:\n"
            "/setrole 123456789 content_contributor"
        )
        return

    telegram_id_text = parts[1]
    new_role = parts[2]

    if not telegram_id_text.isdigit():
        await message.answer("❌ آیدی تلگرام درست نیست.")
        return

    if new_role not in VALID_ROLES:
        await message.answer(
            "❌ نقش درست نیست.\n\n"
            "نقش‌های مجاز:\n"
            "approved_customer\n"
            "content_contributor\n"
            "admin"
        )
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


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())