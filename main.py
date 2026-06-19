import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart

from database import supabase

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


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

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True
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


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())