# meta developer: @whytezz
__version__ = (2, 0, 0)
import asyncio
import time
import re
from .. import loader, utils

@loader.tds
class TargetSenderProMod(loader.Module):
    """Target Sender"""
    strings = {"name": "TargetSenderPro"}

    async def client_ready(self, client, db):
        self.db = db
        self.client = client
        self.tasks = {}
        self._main_switch = self.db.get(self.strings["name"], "switch", True)

    def _parse_time(self, time_str: str) -> int:
        """Парсинг"""
        units = {
            'h': 3600,
            'm': 60,
            's': 1
        }
        total_seconds = 0
        matches = re.findall(r'(\d+)([hms])', time_str.lower())
        for amount, unit in matches:
            total_seconds += int(amount) * units[unit]
        return total_seconds

    async def tchatcmd(self, message):
        """<id> — Добавить/удалить чат в список привязки"""
        args = utils.get_args(message)
        if not args:
            chats = self.db.get(self.strings["name"], "chats", [])
            return await utils.answer(message, f"<b>📍 Привязанные чаты:</b>\n<code>{', '.join(map(str, chats)) if chats else 'Пусто'}</code>")
        
        try:
            chat_id = int(args[0])
            chats = self.db.get(self.strings["name"], "chats", [])
            if chat_id in chats:
                chats.remove(chat_id)
                res = f"<b>❌ Чат <code>{chat_id}</code> отвязан.</b>"
            else:
                chats.append(chat_id)
                res = f"<b>✅ Чат <code>{chat_id}</code> привязан.</b>"
            
            self.db.set(self.strings["name"], "chats", chats)
            await utils.answer(message, res)
        except:
            await utils.answer(message, "<b>⚠️ Введи корректный ID чата.</b>")

    async def tsendcmd(self, message):
        """<время> <сообщение> — Запустить рассылку"""
        if not self._main_switch:
            return await utils.answer(message, "<b>⚠️ Модуль выключен. Включи через .tswitch</b>")

        args = utils.get_args_raw(message)
        time_match = re.search(r'^((?:\d+[hms]\s*)+)(.*)', args)
        
        if not time_match:
            return await utils.answer(message, "<b>⚠️ Формат: .tsend 1h 30m Текст</b>")

        time_str = time_match.group(1).strip()
        text = time_match.group(2).strip()
        delay = self._parse_time(time_str)

        if delay < 1:
            return await utils.answer(message, "<b>⚠️ Неверное время.</b>")
        
        chats = self.db.get(self.strings["name"], "chats", [])
        if not chats:
            return await utils.answer(message, "<b>⚠️ Нет привязанных чатов. Используй .tchat</b>")

        for cid in chats:
            if cid in self.tasks:
                self.tasks[cid].cancel()

        for cid in chats:
            self.tasks[cid] = asyncio.create_task(self._sender_loop(cid, text, delay))

        await utils.answer(message, f"<b>🚀 Рассылка запущена!</b>\n🕒 Интервал: <code>{time_str}</code> ({delay} сек.)\n💬 Текст: <code>{text}</code>\n📍 Чатов: <code>{len(chats)}</code>")

    async def _sender_loop(self, chat_id, text, delay):
        while self._main_switch:
            try:
                await self.client.send_message(chat_id, text)
                
                stats = self.db.get(self.strings["name"], "stats", {})
                stats[str(chat_id)] = stats.get(str(chat_id), 0) + 1
                self.db.set(self.strings["name"], "stats", stats)
                
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(10)

    async def tstatscmd(self, message):
        """Показать детальную статистику"""
        stats = self.db.get(self.strings["name"], "stats", {})
        chats = self.db.get(self.strings["name"], "chats", [])
        
        res = "<b>📊 Target Sender Pro - Статистика:</b>\n"
        for cid in chats:
            count = stats.get(str(cid), 0)
            status = "🟢 В работе" if cid in self.tasks and not self.tasks[cid].done() else "⚪️ Ожидание"
            res += f"<blockquote><b>Chat ID:</b> <code>{cid}</code>\n<b>Отправлено:</b> <code>{count}</code>\n<b>Статус:</b> {status}</blockquote>\n"
        
        if not chats: res += "<i>Нет привязанных чатов</i>"
        await utils.answer(message, res)

    async def tswitchcmd(self, message):
        """Вкл/Выкл модуль"""
        self._main_switch = not self._main_switch
        self.db.set(self.strings["name"], "switch", self._main_switch)
        
        if not self._main_switch:
            for t in self.tasks.values():
                t.cancel()
            self.tasks = {}

        state = "ВКЛЮЧЕН" if self._main_switch else "ВЫКЛЮЧЕН"
        await utils.answer(message, f"<b>⚙️ Модуль Target Sender Pro теперь: {state}</b>")

    async def tstopcmd(self, message):
        """Остановить все текущие рассылки"""
        for t in self.tasks.values():
            t.cancel()
        self.tasks = {}
        await utils.answer(message, "<b>🛑 Все рассылки остановлены.</b>")