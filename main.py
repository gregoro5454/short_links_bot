import asyncio
import logging
import time

import requests
import validators
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import BoundFilter
from aiogram.types import CallbackQuery, Message

import config
import functions
import migrations
from menu import main_menu


bot = Bot(token=config.bot_token, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())

start_text = """
Привет! Я бот, который может сокращать ссылки.
"""


@dp.message_handler(commands=["start"], state="*")
async def handler_start(message: types.Message, state: FSMContext):
    functions.first_join(message.from_user.id, message.from_user.username)
    if message.get_args() == "email" and message.from_user.id in config.admin_id:
        await state.set_state("Email.message")
        await message.answer("Отправьте сообщение для рассылки (текст, фото, видео или гиф)")
    else:
        await message.answer(start_text)


class IsAdmin(BoundFilter):
    async def check(self, message: Message):
        if message.chat.type != "private":
            return False
        return message.from_user.id in config.admin_id


@dp.message_handler(IsAdmin(), commands=["start", "admin"])
async def handler_admin_menu(message: Message):
    await message.answer("<b>Главное меню</b>", reply_markup=main_menu())


@dp.callback_query_handler(regexp=r"^admin_menu$")
async def handler_call_admin_menu(call: CallbackQuery):
    await call.message.edit_text("<b>Главное меню</b>", reply_markup=main_menu())


@dp.callback_query_handler(regexp=r"^statistic$")
async def handler_call_statistic(call: CallbackQuery):
    await call.message.edit_text(functions.admin_stats(), reply_markup=main_menu())


@dp.message_handler(state="Email.message", content_types=['text', 'photo', 'video', 'gif', 'animation'])
async def handler_admin_mail_message_id(message: types.Message, state: FSMContext):
    message_id = message.message_id
    await state.set_state("Email.confirm")
    await state.update_data(message_id=message_id)
    await bot.copy_message(message.from_user.id, message.from_user.id, message_id)
    await message.answer("Отправьте + для подтверждения")


@dp.message_handler(state="Email.confirm")
async def handler_admin_mail_confirm(message: types.Message, state: FSMContext):
    if message.text == '+':
        async with state.proxy() as data:
            message_id = data['message_id']
        await state.finish()
        asyncio.create_task(send_email(message, message_id))
    else:
        await state.finish()
        await message.answer("Рассылка отменена")


async def send_email(message, message_id):
    users = functions.get_users()
    await message.answer(f"Рассылка началась\n"
                         f"Всего пользователей: {len(users)}")
    time_start = time.time()
    true_send = 0
    for user_id, in users:
        try:
            await bot.copy_message(user_id, message.from_user.id, message_id)
            true_send += 1
            await asyncio.sleep(0.05)
        except:
            pass
    text = f"""
✅ Рассылка окончена
👍 Отправлено: {true_send}
👎 Не отправлено: {len(users) - true_send}
🕐 Время выполнения: {int(time.time() - time_start)} секунд
"""
    await message.answer(text)


@dp.message_handler()
async def handler_convert_message(message: types.Message):
    functions.update_user(message.from_user.id, message.from_user.username)
    if validators.url(message.text):
        await message.answer(shorten_link(message.text))


def shorten_link(url: str) -> str:
    headers = {
        'Authorization': f'Bearer {config.bitly_token}',
        'Content-Type': 'application/json',
    }
    data = {'long_url': url}
    response = requests.post('https://api-ssl.bitly.com/v4/shorten', headers=headers, json=data)
    response.raise_for_status()
    return response.json()['link']


async def on_startup(dp):
    info = await bot.get_me()
    config.bot_username = info.username
    print(f"~~~~~ Bot @{info.username} was started ~~~~~")


if __name__ == '__main__':
    from aiogram import executor

    migrations.run()
    logging.basicConfig(filename=f"logs.log", format='%(asctime)s - %(levelname)s - %(message)s', level=logging.ERROR)
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
