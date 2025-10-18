# telegram_bot.py
"""
Telegram Bot - интерфейс для мессенджера
API: Обработка команд и сообщений из Telegram
"""

import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from core.services.database.database import add_activity_log
from core.agent.agent_core import ai_agent  # Глобальный агент
from core.config.config import TELEGRAM_BOT_TOKEN

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, token: str = TELEGRAM_BOT_TOKEN):
        self.token = token
        self.application = None
        add_activity_log("INFO", "Telegram бот инициализирован", "system")
        logger.info("Telegram бот инициализирован")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        tg_user_id = f"tg_{user_id}"
        add_activity_log("INFO", "Пользователь запустил бота", tg_user_id)
        logger.info(f"Пользователь {user_id} запустил бота")
        await update.message.reply_text("🤖 Привет! Я Stark AI ассистент. Просто напиши мне сообщение!")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        tg_user_id = f"tg_{user_id}"
        user_message = update.message.text
        add_activity_log("INFO", f"Telegram сообщение: '{user_message}'", tg_user_id)
        logger.info(f"Обработка сообщения от {user_id}: {user_message}")

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        try:
            add_activity_log("DEBUG", "Начало обработки AI агентом", tg_user_id)
            response = await ai_agent.process_message(tg_user_id, user_message)
            add_activity_log("INFO", f"Ответ отправлен в Telegram ({len(response)} символов)", tg_user_id)
            await update.message.reply_text(response)
            logger.info(f"Ответ отправлен пользователю {user_id}")
        except Exception as e:
            error_msg = f"Ошибка Telegram бота: {e}"
            add_activity_log("ERROR", error_msg, tg_user_id)
            logger.error(f"Ошибка Telegram бота для пользователя {user_id}: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке сообщения")

    async def handle_error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        error = context.error
        user_id = f"tg_{update.effective_user.id}" if update and update.effective_user else "unknown"
        add_activity_log("ERROR", f"Ошибка в Telegram боте: {error}", user_id)
        logger.error(f"Ошибка в Telegram боте: {error}")

    def run(self):
        """Запуск бота с созданием event loop для потока"""
        try:
            # Создаем event loop для этого потока
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            self.application = Application.builder().token(self.token).build()
            self.application.add_handler(CommandHandler("start", self.start))
            self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
            self.application.add_error_handler(self.handle_error)

            logger.info("Telegram bot starting with dedicated event loop...")
            add_activity_log("INFO", "Telegram бот запускается с выделенным event loop", "system")

            # Запускаем в созданном loop
            loop.run_until_complete(self.application.run_polling())

        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")
            add_activity_log("ERROR", f"Ошибка запуска Telegram бота: {e}", "system")
            raise


telegram_bot = TelegramBot()


def main():
    bot = TelegramBot()
    bot.run()


if __name__ == "__main__":
    main()