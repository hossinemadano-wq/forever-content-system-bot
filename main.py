import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart

from database import supabase

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start_handler(message: Message):
    supabase.table("products").select("id").limit(1).execute()

    await message.answer(
        "سلام 👋\n"
        "ربات آموزشی فوراور آماده است.\n"
        "اتصال به دیتابیس هم برقرار شد ✅"
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())