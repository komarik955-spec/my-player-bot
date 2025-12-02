import os
import jinja2
import aiohttp_jinja2
from aiohttp import web, WSMsgType
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
from dotenv import load_dotenv
import secrets
from aiogram.filters import Command
import re

def convert_to_embed(link: str) -> str | None:
    # YouTube
    if "youtube.com/watch?v=" in link or "youtu.be/" in link:
        yt_id = None
        if "youtube.com/watch?v=" in link:
            yt_id = link.split("v=")[-1].split("&")[0]
        elif "youtu.be/" in link:
            yt_id = link.split("youtu.be/")[-1].split("?")[0]
        if yt_id:
            return f"https://www.youtube.com/embed/{yt_id}"

    # RuTube
    m = re.match(r"https?://rutube\.ru/video/([a-zA-Z0-9]+)/?", link)
    if m:
        rutube_id = m.group(1)
        return f"https://rutube.ru/play/embed/{rutube_id}"

    # Mail.ru
    m = re.match(
        r"https?://my\.mail\.ru/(mail|community)/([^/]+)/video/(_myvideo/)?(\d+)\.html", link
    )
    if m:
        path_type, username, _, video_id = m.groups()
        return f"https://my.mail.ru/{path_type}/{username}/video/embed/_myvideo/{video_id}.html"

    # Одноклассники
    m = re.match(r"https?://ok\.ru/video/(\d+)", link)
    if m:
        ok_id = m.group(1)
        return f"https://ok.ru/videoembed/{ok_id}"

    # VK: только если пользователь сам берёт embed-ссылку!
    if "vk.com/video_ext.php" in link:
        # Сразу используем как embed
        return link

    return None  # Если не поддерживается

load_dotenv()

TG_BOT_TOKEN = os.getenv('TG_BOT_TOKEN')
BASE_URL = os.getenv('BASE_URL', 'http://localhost:8080')
HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8080'))

rooms = {}

from aiogram.client.default import DefaultBotProperties

bot = Bot(
    token=TG_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# ==== ПРОСТОЙ STATE: кто ждёт ссылку ====
waiting_for_link = set()

@dp.message(Command('start', 'help'))
async def start(message: types.Message):
    await message.answer("Привет! Я бот для совместного просмотра 👀\n\n- /create — создать новую комнату")

@dp.message(Command('create'))
async def create(message: types.Message):
    await message.answer("Вышли ссылку на видео (например, YouTube):")
    waiting_for_link.add(message.from_user.id)

@dp.message()
async def handle_link(message: types.Message):
    user_id = message.from_user.id
    if user_id in waiting_for_link:
        link = message.text.strip()
        embed_link = convert_to_embed(link)
        if not embed_link:
            await message.answer(
                "❌ Видео не поддерживается или ссылка некорректна.\n"
                "Поддерживаются:\n"
                "- YouTube, RuTube, Mail.ru, Одноклассники (обычные ссылки)\n"
                "- VK ТОЛЬКО embed-ссылки (https://vk.com/video_ext.php?...)\n"
            )
            waiting_for_link.remove(user_id)
            return
        room_id = secrets.token_urlsafe(5)
        rooms[room_id] = {'link': embed_link, 'owner': user_id}
        room_link = f"{BASE_URL}/room/{room_id}"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="▶️ Play", callback_data=f"play:{room_id}"),
                    InlineKeyboardButton(text="⏸ Pause", callback_data=f"pause:{room_id}"),
                    InlineKeyboardButton(text="❌ Close", callback_data=f"close:{room_id}")
                ]
            ]
        )
        await message.answer(
            f"Комната создана!\n\nСсылка на просмотр (открой её сам и/или отправь друзьям):\n{room_link}\n\nУправление доступно ниже:",
            reply_markup=kb
        )
        waiting_for_link.remove(user_id)
    else:
        await message.answer("Я не ожидал ссылку. Напиши /create для создания новой комнаты.")

@dp.callback_query()
async def handle_controls(call: types.CallbackQuery):
    data = call.data
    if not data or ":" not in data:
        return await call.answer("Некорректная команда")
    cmd, room_id = data.split(":")
    if room_id not in rooms:
        return await call.answer("Комната не найдена.")
    await call.answer(f"Отправлена команда {cmd.upper()} для комнаты {room_id}")

# ===== HTTP-сервер и шаблон =====

async def index(request):
    return web.Response(text="It works. Перейди по /room/код", content_type='text/html')

@aiohttp_jinja2.template('room.html')
async def room(request):
    room_id = request.match_info["room_id"]
    info = rooms.get(room_id)
    if not info:
        return {"room_id": room_id, "link": None}
    return {"room_id": room_id, "link": info["link"]}

# WebSocket-заглушка (упрощённо)
async def ws_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    await ws.send_str("Соединение установлено для room_id = " + request.match_info["room_id"])
    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            await ws.send_str(f"Echo: {msg.data}")
    return ws

app = web.Application()
aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(os.getcwd()))
app.router.add_get('/', index)
app.router.add_get('/room/{room_id}', room)
app.router.add_get('/ws/{room_id}', ws_handler)

# шаблон
room_html_content = """
<!DOCTYPE html>
<html>
<head>
  <title>Watch room {{ room_id }}</title>
</head>
<body>
  <h1>Watch room: {{ room_id }}</h1>
  {% if link %}
    <iframe width="640" height="360" src="{{ link | safe }}"></iframe>
  {% else %}
    <p>Комната не существует или неактивна.</p>
  {% endif %}
</body>
</html>
"""

with open("room.html", "w", encoding="utf-8") as f:
    f.write(room_html_content)

async def main():
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()
    print(f"Web server started at {BASE_URL}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())